"""The experiment engine: runs one configured experiment end to end.

This module only ever executes the approved algorithms from `algorithms.py`
with validated settings. It runs inside a separate worker process (see worker.py)
so a hard time limit can be enforced from outside.
"""
import hashlib
import json
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, mean_absolute_error,
                             mean_squared_error, precision_recall_fscore_support, r2_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, OrdinalEncoder, StandardScaler

from . import config, db, report
from .algorithms import algorithm_label, build_estimator
from .profiler import DatasetError, load_dataframe
from .system_info import get_host

STAGES = [
    "Preparing dataset",
    "Validating dataset",
    "Preprocessing",
    "Splitting dataset",
    "Training model",
    "Evaluating model",
    "Generating results",
]

ARTIFACTS = {
    "results.json": "Full results, metrics and chart data",
    "metrics.csv": "The headline metrics as a table",
    "predictions.csv": "Every held-out row with the actual and predicted value",
    "experiment_report.pdf": "A printable summary of this experiment",
    "model.joblib": "The trained scikit-learn pipeline",
    "experiment_config.json": "Everything needed to reproduce this run",
}


class StageTracker:
    """Writes stage progress to the database so the UI can follow along."""

    def __init__(self, exp_id: int):
        self.exp_id = exp_id
        self.stages = [{"name": n, "started": None, "ended": None} for n in STAGES]
        self.current = -1

    def begin(self, index: int) -> None:
        now = time.time()
        if self.current >= 0:
            self.stages[self.current]["ended"] = now
        self.current = index
        self.stages[index]["started"] = now
        self._save()

    def finish(self) -> None:
        if self.current >= 0:
            self.stages[self.current]["ended"] = time.time()
            self._save()

    def _save(self) -> None:
        with db.db() as conn:
            conn.execute("UPDATE experiments SET stages_json = ? WHERE id = ?",
                         (json.dumps(self.stages), self.exp_id))


def natural_sort_key(label: str):
    try:
        return (0, float(label), label)
    except ValueError:
        return (1, 0.0, label)


def _label_series(y: pd.Series) -> pd.Series:
    def fmt(v):
        if isinstance(v, (float, np.floating)) and float(v).is_integer():
            return str(int(v))
        return str(v)
    return y.map(fmt)


def _feature_types(X: pd.DataFrame):
    """Split features into numeric and categorical, converting dates to numbers."""
    numeric, categorical = [], []
    X = X.copy()
    for col in X.columns:
        s = X[col]
        if pd.api.types.is_bool_dtype(s):
            X[col] = s.astype(object).map(lambda v: np.nan if pd.isna(v) else str(v))
            categorical.append(col)
        elif pd.api.types.is_datetime64_any_dtype(s):
            X[col] = s.astype("int64").where(s.notna()) / 1e9
            numeric.append(col)
        elif pd.api.types.is_numeric_dtype(s):
            numeric.append(col)
        else:
            X[col] = s.astype(object).map(lambda v: np.nan if pd.isna(v) else str(v))
            categorical.append(col)
    return X, numeric, categorical


def _build_preprocessor(numeric, categorical, prep_cfg):
    scaler = {"standard": StandardScaler(), "minmax": MinMaxScaler(), "none": "passthrough"}[prep_cfg["scaling"]]
    if prep_cfg["encoding"] == "onehot":
        encoder = OneHotEncoder(handle_unknown="infrequent_if_exist", max_categories=25, sparse_output=False)
    else:
        encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    parts = []
    if numeric:
        parts.append(("numeric", Pipeline([
            ("impute", SimpleImputer(strategy=prep_cfg["missing"], keep_empty_features=True)),
            ("scale", scaler),
        ]), numeric))
    if categorical:
        parts.append(("categorical", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
            ("encode", encoder),
        ]), categorical))
    return ColumnTransformer(parts, remainder="drop", verbose_feature_names_out=False)


def _round(x, digits=4):
    return None if x is None else round(float(x), digits)


def run_experiment(exp_id: int) -> None:
    started = time.time()
    tracker = StageTracker(exp_id)
    with db.db() as conn:
        row = conn.execute(
            "SELECT e.*, d.stored_path, d.ext, d.filename AS dataset_filename FROM experiments e "
            "LEFT JOIN datasets d ON d.id = e.dataset_id WHERE e.id = ?", (exp_id,)).fetchone()
    if row is None:
        raise RuntimeError("Experiment not found.")
    cfg = json.loads(row["config_json"])
    out_dir = config.EXPERIMENT_DIR / str(exp_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    host = get_host()

    try:
        results = _execute(row, cfg, tracker, out_dir, host, started)
        tracker.finish()
        with db.db() as conn:
            conn.execute(
                "UPDATE experiments SET status='completed', primary_metric=?, primary_value=?, host_json=?, "
                "finished_at=?, duration_s=? WHERE id=?",
                (results["primary"]["name"], results["primary"]["value"], json.dumps(host), db.now_iso(),
                 round(time.time() - started, 2), exp_id))
    except Exception as exc:  # noqa: BLE001 - every failure must be reported to the user
        tracker.finish()
        message = str(exc) if isinstance(exc, (DatasetError, ValueError)) else f"{type(exc).__name__}: {exc}"
        with db.db() as conn:
            conn.execute(
                "UPDATE experiments SET status='failed', error=?, host_json=?, finished_at=?, duration_s=? WHERE id=?",
                (message[:400], json.dumps(host), db.now_iso(), round(time.time() - started, 2), exp_id))
        raise


def _execute(row, cfg, tracker: StageTracker, out_dir: Path, host: dict, started: float) -> dict:
    problem = cfg["problem_type"]
    target = cfg["target"]
    seed = cfg["preprocessing"]["random_state"]
    prep_cfg = cfg["preprocessing"]

    # 1. Preparing ----------------------------------------------------------
    tracker.begin(0)
    path = Path(row["stored_path"])
    if not path.exists():
        raise DatasetError("The uploaded dataset is no longer on disk. Upload it again.")
    df = load_dataframe(path, row["ext"])
    sha = hashlib.sha256(path.read_bytes()).hexdigest()

    # 2. Validating ---------------------------------------------------------
    tracker.begin(1)
    missing_cols = [c for c in [target, *cfg["features"]] if c not in df.columns]
    if missing_cols:
        raise DatasetError(f"Columns not found in the dataset: {', '.join(missing_cols)}.")
    data = df[[*cfg["features"], target]]
    n_before = len(data)
    data = data[data[target].notna()]
    dropped_target = n_before - len(data)

    if problem == "regression":
        y_num = pd.to_numeric(data[target], errors="coerce")
        if y_num.isna().mean() > 0.02:
            raise DatasetError(f"'{target}' is not numeric, so it can't be used for regression. Choose classification instead.")
        data = data[y_num.notna()]
        y = y_num[y_num.notna()].astype(float)
        classes = None
    else:
        labels = _label_series(data[target])
        classes = sorted(labels.unique(), key=natural_sort_key)
        if len(classes) < 2:
            raise DatasetError(f"'{target}' has only one class, so there is nothing to predict.")
        if len(classes) > 50:
            raise DatasetError(f"'{target}' has {len(classes)} distinct values. Classification supports up to 50 classes; "
                               "choose regression if this is a continuous number.")
        index = {c: i for i, c in enumerate(classes)}
        y = labels.map(index).astype(int)
    if len(data) < 20:
        raise DatasetError("Fewer than 20 usable rows remain after removing rows with no target value.")

    X, numeric, categorical = _feature_types(data[cfg["features"]])

    # 3. Preprocessing ------------------------------------------------------
    tracker.begin(2)
    preprocessor = _build_preprocessor(numeric, categorical, prep_cfg)
    estimator = build_estimator(problem, cfg["algorithm"], cfg["params"], seed)
    pipe = Pipeline([("prep", preprocessor), ("model", estimator)])

    # 4. Splitting ----------------------------------------------------------
    tracker.begin(3)
    stratify = None
    if problem == "classification" and y.value_counts().min() >= 2:
        stratify = y
    try:
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=prep_cfg["test_size"], random_state=seed,
                                                  stratify=stratify)
    except ValueError:
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=prep_cfg["test_size"], random_state=seed)

    # 5. Training -----------------------------------------------------------
    tracker.begin(4)
    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pipe.fit(X_tr, y_tr)
    train_seconds = time.time() - t0
    feature_names = [str(n) for n in pipe.named_steps["prep"].get_feature_names_out()]

    # 6. Evaluating ---------------------------------------------------------
    tracker.begin(5)
    pred_te = pipe.predict(X_te)
    pred_tr = pipe.predict(X_tr)
    charts: dict = {}
    if problem == "classification":
        k = len(classes)
        p, r, f1, _ = precision_recall_fscore_support(y_te, pred_te, average="weighted", zero_division=0)
        metrics = {"accuracy": accuracy_score(y_te, pred_te), "precision": p, "recall": r, "f1": f1}
        primary = {"name": "accuracy", "label": "Accuracy", "value": metrics["accuracy"]}
        majority = int(y_tr.value_counts().idxmax())
        baseline = {"name": "accuracy", "value": float((y_te == majority).mean()),
                    "description": f"Always predicting '{classes[majority]}'"}
        extra = {
            "train_accuracy": accuracy_score(y_tr, pred_tr),
            "average": "weighted",
        }
        rep = classification_report(y_te, pred_te, labels=list(range(k)), target_names=classes,
                                    output_dict=True, zero_division=0)
        extra["per_class"] = [
            {"class": c, "precision": _round(rep[c]["precision"]), "recall": _round(rep[c]["recall"]),
             "f1": _round(rep[c]["f1-score"]), "support": int(rep[c]["support"])} for c in classes]
        charts["confusion"] = {"labels": classes, "matrix": confusion_matrix(y_te, pred_te, labels=list(range(k))).tolist()}
        charts["class_distribution"] = {
            "labels": classes,
            "actual": np.bincount(y_te, minlength=k).tolist(),
            "predicted": np.bincount(pred_te.astype(int), minlength=k).tolist(),
        }
        scoring = "accuracy"
    else:
        mse = mean_squared_error(y_te, pred_te)
        metrics = {"mae": mean_absolute_error(y_te, pred_te), "mse": mse, "rmse": float(np.sqrt(mse)),
                   "r2": r2_score(y_te, pred_te)}
        primary = {"name": "r2", "label": "R²", "value": metrics["r2"]}
        base_rmse = float(np.sqrt(np.mean((y_te - y_tr.mean()) ** 2)))
        baseline = {"name": "rmse", "value": base_rmse, "description": "Always predicting the training average"}
        extra = {"train_r2": r2_score(y_tr, pred_tr),
                 "target_stats": {"min": float(y.min()), "max": float(y.max()), "mean": float(y.mean()),
                                  "std": float(y.std())}}
        rng = np.random.default_rng(seed)
        pick = rng.choice(len(y_te), size=min(400, len(y_te)), replace=False)
        charts["scatter"] = [[_round(a, 6), _round(b, 6)] for a, b in zip(y_te.to_numpy()[pick], pred_te[pick])]
        resid = y_te.to_numpy() - pred_te
        counts, edges = np.histogram(resid, bins=20)
        charts["residuals"] = {"edges": [_round(e, 6) for e in edges], "counts": counts.tolist(),
                               "mean": _round(resid.mean(), 6), "std": _round(resid.std(), 6)}
        scoring = "r2"

    # Feature importance by permutation on the original columns: works for every algorithm.
    n_feat = X_te.shape[1]
    repeats = 5 if n_feat <= 20 else 3 if n_feat <= 60 else 2
    sub = min(len(X_te), 1500)
    sub_idx = np.random.default_rng(seed).choice(len(X_te), size=sub, replace=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        imp = permutation_importance(pipe, X_te.iloc[sub_idx], y_te.iloc[sub_idx], n_repeats=repeats,
                                     random_state=seed, scoring=scoring, n_jobs=1)
    order = np.argsort(-imp.importances_mean)[:15]
    charts["importance"] = [{"feature": X_te.columns[i], "importance": _round(imp.importances_mean[i], 5),
                             "std": _round(imp.importances_std[i], 5)} for i in order]

    # 7. Generating ---------------------------------------------------------
    tracker.begin(6)
    decode = (lambda arr: [classes[int(i)] for i in arr]) if classes else (lambda arr: [float(a) for a in arr])
    actual_out, pred_out = decode(y_te), decode(pred_te)
    preds_df = X_te.copy()
    preds_df.insert(0, "row_index", X_te.index)
    preds_df["actual"] = actual_out
    preds_df["predicted"] = pred_out
    if problem == "classification":
        preds_df["correct"] = [a == b for a, b in zip(actual_out, pred_out)]
    else:
        preds_df["error"] = np.round(np.asarray(actual_out) - np.asarray(pred_out), 6)
    preds_df.to_csv(out_dir / "predictions.csv", index=False)
    sample = preds_df.head(10)[["row_index", "actual", "predicted"]].to_dict(orient="records")

    stage_secs = {}
    results = {
        "experiment_id": row["id"],
        "problem_type": problem,
        "algorithm": {"key": cfg["algorithm"], "label": algorithm_label(problem, cfg["algorithm"]),
                      "params": cfg["params"]},
        "dataset": {"filename": row["dataset_filename"] or row["dataset_name"], "sha256": sha,
                    "rows_total": n_before, "rows_used": int(len(data)), "rows_missing_target": dropped_target,
                    "rows_train": int(len(X_tr)), "rows_test": int(len(X_te))},
        "target": target,
        "classes": classes,
        "features": {"selected": cfg["features"], "numeric": numeric, "categorical": categorical,
                     "after_encoding": len(feature_names)},
        "preprocessing": prep_cfg,
        "metrics": {k: _round(v, 6) for k, v in metrics.items()},
        "primary": {"name": primary["name"], "label": primary["label"], "value": _round(primary["value"], 6)},
        "baseline": {**baseline, "value": _round(baseline["value"], 6)},
        "extra": {k: (_round(v, 6) if isinstance(v, (float, np.floating)) else v) for k, v in extra.items()},
        "charts": charts,
        "sample_predictions": sample,
        "training_seconds": round(train_seconds, 3),
        "stage_seconds": stage_secs,
        "host": host,
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))

    pd.DataFrame([{"metric": k, "value": v} for k, v in results["metrics"].items()]).to_csv(
        out_dir / "metrics.csv", index=False)

    joblib.dump({"pipeline": pipe, "classes": classes, "features": cfg["features"], "target": target,
                 "problem_type": problem, "scikit_learn": host["scikit_learn"]}, out_dir / "model.joblib")

    (out_dir / "experiment_config.json").write_text(json.dumps({
        "metrica_version": "1.0",
        "experiment_id": row["id"],
        "dataset": {"filename": results["dataset"]["filename"], "sha256": sha},
        "target": target,
        "problem_type": problem,
        "features": cfg["features"],
        "preprocessing": prep_cfg,
        "algorithm": {"key": cfg["algorithm"], "params": cfg["params"]},
        "environment": {k: host[k] for k in ("provider", "instance_type", "os", "python", "scikit_learn", "pandas", "numpy")},
        "how_to_reproduce": "Upload the same dataset, choose the same target, features, preprocessing and algorithm "
                            "settings, and use the same random state. Results will match when library versions match.",
    }, indent=2))

    report.build_report(out_dir / "experiment_report.pdf", results, row)
    # fill in measured stage durations for the saved results file
    tracker.finish()
    results["stage_seconds"] = {s["name"]: round((s["ended"] or s["started"]) - s["started"], 3)
                                for s in tracker.stages if s["started"]}
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    return results
