"""Reading uploaded datasets and profiling their structure."""
import csv
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


class DatasetError(ValueError):
    """Raised with a message that is safe to show to the user."""


_DATE_LIKE = re.compile(r"^\s*\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}([ T]\d{1,2}:\d{2}.*)?\s*$")
_TARGET_HINTS = {
    "target", "label", "class", "y", "outcome", "result", "churn", "survived", "species", "diagnosis",
    "default", "fraud", "passed", "quality", "price", "salary", "grade", "status", "response", "category",
    "cultivar", "attrition", "converted", "spam",
}
# "None" and "No" are legitimate category names, so unlike pandas' defaults they don't count as missing.
_NA_VALUES = ["", "NA", "N/A", "n/a", "NaN", "nan", "NULL", "null", "#N/A", "?", "-"]
_ID_NAME = re.compile(r"(^id$|_id$|^id_|\bid$|^uuid$|^index$|^unnamed)", re.I)


def load_dataframe(path: Path, ext: str) -> pd.DataFrame:
    """Read a CSV / TXT / XLS / XLSX file into a cleaned DataFrame, enforcing limits."""
    try:
        if ext in (".csv", ".txt"):
            df = _read_delimited(path)
        elif ext == ".xlsx":
            df = pd.read_excel(path, engine="openpyxl", keep_default_na=False, na_values=_NA_VALUES)
        elif ext == ".xls":
            df = pd.read_excel(path, engine="xlrd", keep_default_na=False, na_values=_NA_VALUES)
        else:
            raise DatasetError("Unsupported file type. Use CSV, TXT, XLS or XLSX.")
    except DatasetError:
        raise
    except Exception as exc:  # any parser failure becomes a friendly message
        raise DatasetError(f"The file could not be read as a table ({type(exc).__name__}). "
                           "Check that it has a header row and consistent columns.") from exc

    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.shape[0] < 10:
        raise DatasetError("The dataset needs at least 10 rows.")
    if df.shape[1] < 2:
        raise DatasetError("The dataset needs at least 2 columns (one target and one feature).")
    if df.shape[0] > config.MAX_ROWS:
        raise DatasetError(f"The dataset has more than {config.MAX_ROWS:,} rows, which is the limit for this instance.")
    if df.shape[1] > config.MAX_COLUMNS:
        raise DatasetError(f"The dataset has more than {config.MAX_COLUMNS} columns, which is the limit for this instance.")

    df.columns = _clean_names(df.columns)
    df = df.reset_index(drop=True)
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            df[col] = _tidy_object_column(df[col])
    return df


def _read_delimited(path: Path) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        sample = fh.read(16384)
    if not sample.strip():
        raise DatasetError("The file is empty.")
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    return pd.read_csv(path, sep=delimiter, encoding="utf-8-sig", encoding_errors="replace",
                       nrows=config.MAX_ROWS + 1, skipinitialspace=True,
                       keep_default_na=False, na_values=_NA_VALUES)


def _clean_names(columns) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for i, c in enumerate(columns):
        name = str(c).strip() or f"column_{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        out.append(name)
    return out


def _tidy_object_column(s: pd.Series) -> pd.Series:
    """Trim strings, turn blanks into NaN, and parse columns that are really dates or numbers."""
    def tidy(v):
        if isinstance(v, str):
            v = v.strip()
            return np.nan if v == "" else v
        return v

    s = s.map(tidy)
    non_null = s.dropna()
    if non_null.empty:
        return s
    numeric = pd.to_numeric(non_null, errors="coerce")
    if numeric.notna().mean() >= 0.98:
        return pd.to_numeric(s, errors="coerce")
    strings = non_null.astype(str)
    if strings.head(200).map(lambda v: bool(_DATE_LIKE.match(v))).mean() >= 0.9:
        parsed = pd.to_datetime(s, errors="coerce", format="mixed")
        if parsed.notna().sum() >= 0.9 * len(non_null):
            return parsed
    return s


def column_kind(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if pd.api.types.is_numeric_dtype(s):
        vals = s.dropna()
        if len(vals) and np.all(np.isclose(vals, np.round(vals))):
            return "integer"
        return "float"
    nunique = s.nunique(dropna=True)
    if nunique > 50 and nunique / max(len(s.dropna()), 1) > 0.5:
        return "text"
    return "categorical"


_KIND_LABEL = {"integer": "Integer", "float": "Float", "categorical": "Categorical",
               "boolean": "Boolean", "datetime": "Datetime", "text": "Text"}


def _recommendation(name: str, s: pd.Series, kind: str, n_rows: int) -> tuple[str, bool]:
    """Return (recommendation key, exclude_by_default)."""
    non_null = int(s.notna().sum())
    unique = int(s.nunique(dropna=True))
    if unique <= 1:
        return "constant", True
    if non_null and non_null < 0.4 * n_rows:
        return "sparse", True
    if kind in ("integer", "text", "categorical") and non_null > 1 and unique == non_null and kind != "float":
        # every value different: an identifier, unless it's a plain measurement column
        if kind != "integer" or _ID_NAME.search(name) or _is_sequence(s):
            return "id", True
    if kind == "integer" and _ID_NAME.search(name) and unique / max(non_null, 1) > 0.9:
        return "id", True
    if kind == "datetime":
        return "datetime", True
    if kind == "text":
        return "text", True
    return "feature", False


def _is_sequence(s: pd.Series) -> bool:
    vals = s.dropna()
    if len(vals) < 3:
        return False
    diffs = np.diff(vals.to_numpy(dtype=float))
    return bool(np.all(diffs == 1) or np.all(diffs == -1))


def guess_problem_type(s: pd.Series, kind: str) -> str:
    if kind in ("categorical", "boolean", "text"):
        return "classification"
    if kind == "integer" and s.nunique(dropna=True) <= 10:
        return "classification"
    return "regression"


def _target_candidates(df: pd.DataFrame, cols: list[dict]) -> list[dict]:
    scored = []
    last = df.columns[-1]
    for c in cols:
        if c["recommendation"] in ("id", "constant", "sparse", "datetime", "text"):
            continue
        name, kind, unique = c["name"], c["kind"], c["unique"]
        score, why = 0.0, []
        if name.lower() in _TARGET_HINTS:
            score += 3
            why.append("name looks like an outcome")
        if name == last:
            score += 2
            why.append("last column")
        if kind in ("categorical", "boolean") and 2 <= unique <= 20:
            score += 2
            why.append(f"{unique} distinct values")
        elif kind == "integer" and 2 <= unique <= 10:
            score += 1
            why.append(f"{unique} distinct values")
        elif kind == "float":
            score += 0.5
        if score > 0:
            scored.append((score, c, why))
    scored.sort(key=lambda t: -t[0])
    out = []
    for _, c, why in scored[:6]:
        out.append({
            "name": c["name"],
            "problem_type": guess_problem_type(df[c["name"]], c["kind"]),
            "reason": ", ".join(why) or "numeric column",
        })
    return out


def _json_safe(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def profile_dataframe(df: pd.DataFrame, filename: str) -> dict:
    n_rows = len(df)
    columns = []
    for name in df.columns:
        s = df[name]
        kind = column_kind(s)
        rec, exclude = _recommendation(name, s, kind, n_rows)
        info = {
            "name": name,
            "kind": kind,
            "type": _KIND_LABEL[kind],
            "unique": int(s.nunique(dropna=True)),
            "missing": int(s.isna().sum()),
            "missing_pct": round(float(s.isna().mean()) * 100, 1),
            "recommendation": rec,
            "exclude_default": exclude,
        }
        if kind in ("integer", "float") and s.notna().any():
            info["stats"] = {"min": float(s.min()), "max": float(s.max()),
                             "mean": float(s.mean()), "std": float(s.std()) if s.notna().sum() > 1 else 0.0}
        elif kind in ("categorical", "boolean", "text"):
            top = s.astype(str).where(s.notna()).value_counts().head(5)
            info["top_values"] = [{"value": str(k), "count": int(v)} for k, v in top.items()]
        columns.append(info)

    candidates = _target_candidates(df, columns)
    for c in columns:
        if any(t["name"] == c["name"] for t in candidates[:3]) and c["recommendation"] == "feature" \
                and c["kind"] in ("categorical", "boolean"):
            c["recommendation"] = "target_candidate"

    kinds = [c["kind"] for c in columns]
    return {
        "filename": filename,
        "rows": n_rows,
        "columns_count": len(columns),
        "numeric": sum(k in ("integer", "float") for k in kinds),
        "categorical": sum(k in ("categorical", "boolean", "text") for k in kinds),
        "datetime": sum(k == "datetime" for k in kinds),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "columns": columns,
        "suggested_target": candidates[0]["name"] if candidates else columns[-1]["name"],
        "target_candidates": candidates,
        "preview": _json_safe(df.head(8)),
    }
