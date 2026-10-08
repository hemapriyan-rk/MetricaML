"""The approved algorithm catalogue.

Users submit configuration, never code: every algorithm and hyperparameter is
declared here, and anything outside this catalogue is rejected.
The same catalogue is sent to the UI so the parameter forms are generated from it.
"""
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


def _int(name, label, default, lo, hi, hint=None):
    return {"name": name, "label": label, "type": "int", "default": default, "min": lo, "max": hi, "hint": hint}


def _float(name, label, default, lo, hi, step, hint=None):
    return {"name": name, "label": label, "type": "float", "default": default, "min": lo, "max": hi,
            "step": step, "hint": hint}


def _choice(name, label, default, choices, hint=None):
    return {"name": name, "label": label, "type": "choice", "default": default, "choices": choices, "hint": hint}


_DEPTH_HINT = "0 means no limit"

CATALOGUE = {
    "classification": {
        "logistic_regression": {
            "label": "Logistic Regression",
            "description": "A fast linear baseline. Works well when classes are roughly separable by a straight boundary.",
            "params": [
                _float("C", "Regularisation strength (C)", 1.0, 0.001, 100, 0.1, "Higher values fit the training data more closely"),
                _int("max_iter", "Maximum iterations", 300, 50, 2000),
                _choice("class_weight", "Class weights", "none", ["none", "balanced"], "Balanced helps when one class is rare"),
            ],
        },
        "knn": {
            "label": "K-Nearest Neighbors",
            "description": "Predicts from the closest training rows. Simple and intuitive, slower on large datasets.",
            "params": [
                _int("n_neighbors", "Number of neighbors", 5, 1, 50),
                _choice("metric", "Distance metric", "euclidean", ["euclidean", "manhattan", "chebyshev"]),
                _choice("weights", "Weights", "uniform", ["uniform", "distance"], "Distance gives closer rows more say"),
            ],
        },
        "decision_tree": {
            "label": "Decision Tree",
            "description": "A readable set of yes/no splits. Fast, but can overfit if allowed to grow deep.",
            "params": [
                _int("max_depth", "Maximum depth", 5, 0, 30, _DEPTH_HINT),
                _int("min_samples_split", "Minimum samples to split", 2, 2, 100),
                _choice("criterion", "Criterion", "gini", ["gini", "entropy", "log_loss"]),
            ],
        },
        "random_forest": {
            "label": "Random Forest",
            "description": "Many decision trees voting together. A strong all-round choice for tabular data.",
            "params": [
                _int("n_estimators", "Number of trees", 50, 10, 300),
                _int("max_depth", "Maximum depth", 5, 0, 30, _DEPTH_HINT),
                _int("min_samples_split", "Minimum samples to split", 2, 2, 100),
                _choice("criterion", "Criterion", "gini", ["gini", "entropy"]),
            ],
        },
        "svm": {
            "label": "Support Vector Machine",
            "description": "Finds the widest margin between classes. Accurate on small and medium data, slow on large data.",
            "params": [
                _float("C", "Regularisation strength (C)", 1.0, 0.01, 100, 0.1),
                _choice("kernel", "Kernel", "rbf", ["rbf", "linear", "poly"]),
                _choice("gamma", "Gamma", "scale", ["scale", "auto"]),
            ],
        },
    },
    "regression": {
        "linear_regression": {
            "label": "Linear Regression",
            "description": "Fits a straight-line relationship between the features and the target.",
            "params": [
                _choice("fit_intercept", "Fit intercept", "yes", ["yes", "no"]),
            ],
        },
        "ridge": {
            "label": "Ridge Regression",
            "description": "Linear regression with a penalty that keeps coefficients small and stable.",
            "params": [
                _float("alpha", "Regularisation strength (alpha)", 1.0, 0.001, 1000, 0.1),
            ],
        },
        "decision_tree_regressor": {
            "label": "Decision Tree Regressor",
            "description": "Splits the data into regions and predicts the average of each region.",
            "params": [
                _int("max_depth", "Maximum depth", 5, 0, 30, _DEPTH_HINT),
                _int("min_samples_split", "Minimum samples to split", 2, 2, 100),
                _choice("criterion", "Criterion", "squared_error", ["squared_error", "friedman_mse"]),
            ],
        },
        "random_forest_regressor": {
            "label": "Random Forest Regressor",
            "description": "Many regression trees averaged together. Handles non-linear patterns well.",
            "params": [
                _int("n_estimators", "Number of trees", 50, 10, 300),
                _int("max_depth", "Maximum depth", 5, 0, 30, _DEPTH_HINT),
                _int("min_samples_split", "Minimum samples to split", 2, 2, 100),
                _choice("criterion", "Criterion", "squared_error", ["squared_error", "friedman_mse"]),
            ],
        },
    },
}


def public_catalogue() -> dict:
    return {
        pt: [{"key": key, **spec} for key, spec in algos.items()]
        for pt, algos in CATALOGUE.items()
    }


def algorithm_label(problem_type: str, key: str) -> str:
    return CATALOGUE[problem_type][key]["label"]


def validate_params(problem_type: str, key: str, raw: dict | None) -> dict:
    """Return a cleaned copy of the hyperparameters or raise ValueError."""
    if problem_type not in CATALOGUE:
        raise ValueError("Problem type must be classification or regression.")
    if key not in CATALOGUE[problem_type]:
        raise ValueError(f"'{key}' is not an available {problem_type} algorithm.")
    raw = raw or {}
    clean = {}
    for spec in CATALOGUE[problem_type][key]["params"]:
        name = spec["name"]
        value = raw.get(name, spec["default"])
        if spec["type"] == "choice":
            if value not in spec["choices"]:
                raise ValueError(f"{spec['label']} must be one of: {', '.join(spec['choices'])}.")
        else:
            if isinstance(value, bool):
                raise ValueError(f"{spec['label']} must be a number.")
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{spec['label']} must be a number.")
            if number != number or number in (float("inf"), float("-inf")):
                raise ValueError(f"{spec['label']} must be a finite number.")
            if spec["type"] == "int":
                if number != int(number):
                    raise ValueError(f"{spec['label']} must be a whole number.")
                value = int(number)
            else:
                value = number
            if not spec["min"] <= value <= spec["max"]:
                raise ValueError(f"{spec['label']} must be between {spec['min']} and {spec['max']}.")
        clean[name] = value
    return clean


def build_estimator(problem_type: str, key: str, params: dict, random_state: int):
    p = dict(params)
    depth = p.get("max_depth")
    if "max_depth" in p:
        p["max_depth"] = None if depth == 0 else depth

    if key == "logistic_regression":
        return LogisticRegression(C=p["C"], max_iter=p["max_iter"],
                                  class_weight=None if p["class_weight"] == "none" else "balanced",
                                  random_state=random_state)
    if key == "knn":
        return KNeighborsClassifier(n_neighbors=p["n_neighbors"], metric=p["metric"], weights=p["weights"])
    if key == "decision_tree":
        return DecisionTreeClassifier(random_state=random_state, **p)
    if key == "random_forest":
        return RandomForestClassifier(random_state=random_state, n_jobs=1, **p)
    if key == "svm":
        return SVC(random_state=random_state, **p)
    if key == "linear_regression":
        return LinearRegression(fit_intercept=p["fit_intercept"] == "yes")
    if key == "ridge":
        return Ridge(alpha=p["alpha"], random_state=random_state)
    if key == "decision_tree_regressor":
        return DecisionTreeRegressor(random_state=random_state, **p)
    if key == "random_forest_regressor":
        return RandomForestRegressor(random_state=random_state, n_jobs=1, **p)
    raise ValueError(f"Unknown algorithm '{key}'.")
