"""MetricaML MCP server.

Lets an MCP client (Claude Desktop, Claude Code, ...) drive a MetricaML deployment: upload a dataset,
profile it, run or compare experiments on the EC2 instance, and fetch metrics and artifacts.
It talks to the normal MetricaML HTTP API, so every limit and per-user rule still applies.

Configuration (environment variables):
    METRICA_URL       base URL of the deployment, e.g. http://13.203.226.207  (default http://127.0.0.1:8000)
    METRICA_EMAIL     account email
    METRICA_PASSWORD  account password

Run:  python mcp_server/server.py        (stdio transport)
"""
import os
import re
import time
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

INSTRUCTIONS = """MetricaML trains classical machine-learning models on an AWS EC2 instance.
Typical flow: list_sample_datasets or upload_dataset -> read the profile it returns -> run_experiment
(or compare_algorithms if unsure which algorithm to use) -> read the metrics -> download_artifact for files.
Limits: 50 MB files, 100,000 rows, one experiment at a time, 120 seconds per experiment."""


class MetricaError(RuntimeError):
    """An error message that is safe to show to the model and the user."""


class MetricaApi:
    """A small authenticated client for the MetricaML HTTP API."""

    def __init__(self, client: httpx.Client | None = None):
        self._injected = client is not None
        self.base = os.environ.get("METRICA_URL", "http://127.0.0.1:8000").rstrip("/")
        self.client = client or httpx.Client(base_url=self.base, timeout=120)
        self._logged_in = self._injected  # an injected client is already authenticated

    def _login(self) -> None:
        email, password = os.environ.get("METRICA_EMAIL"), os.environ.get("METRICA_PASSWORD")
        if not email or not password:
            raise MetricaError("Set METRICA_EMAIL and METRICA_PASSWORD (and METRICA_URL) for the MetricaML MCP server.")
        r = self.client.post("/api/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            raise MetricaError(self._detail(r))
        self._logged_in = True

    @staticmethod
    def _detail(r: httpx.Response) -> str:
        try:
            return str(r.json().get("detail") or r.text)
        except ValueError:
            return f"MetricaML returned HTTP {r.status_code}."

    def request(self, method: str, path: str, **kw) -> httpx.Response:
        if not self._logged_in:
            self._login()
        try:
            r = self.client.request(method, f"/api{path}", **kw)
            if r.status_code == 401 and not self._injected:
                self._login()
                r = self.client.request(method, f"/api{path}", **kw)
        except httpx.HTTPError as exc:
            raise MetricaError(f"Could not reach MetricaML at {self.base}: {exc}") from exc
        if r.status_code >= 400:
            raise MetricaError(self._detail(r))
        return r

    def json(self, method: str, path: str, **kw):
        return self.request(method, path, **kw).json()


mcp = MCPServer("metricaml", instructions=INSTRUCTIONS)
api = MetricaApi.__new__(MetricaApi)  # replaced lazily so importing this module never needs credentials
_ready = False


def _api() -> MetricaApi:
    global api, _ready
    if not _ready:
        api = MetricaApi()
        _ready = True
    return api


def use_client(client: httpx.Client) -> None:
    """Swap in an already-authenticated client (used by the tests)."""
    global api, _ready
    api, _ready = MetricaApi(client), True


# ----------------------------------------------------------------------------- summaries

def _dataset_summary(ds: dict) -> dict:
    p = ds["profile"]
    return {
        "dataset_id": ds["id"],
        "filename": ds["filename"],
        "rows": p["rows"],
        "columns": p["columns_count"],
        "missing_values": p["missing_values"],
        "duplicate_rows": p["duplicate_rows"],
        "suggested_target": p["suggested_target"],
        "target_candidates": p["target_candidates"],
        "column_details": [
            {"name": c["name"], "type": c["type"], "unique": c["unique"], "missing": c["missing"],
             "recommendation": c["recommendation"]} for c in p["columns"]],
    }


def _experiment_summary(exp: dict, base: str) -> dict:
    out = {
        "experiment_id": exp["id"],
        "status": exp["status"],
        "algorithm": exp["algorithm_label"],
        "dataset": exp["dataset_name"],
        "target": exp["target"],
        "problem_type": exp["problem_type"],
        "duration_seconds": exp.get("duration_s"),
        "view_in_browser": f"{base}/experiments/{exp['id']}",
    }
    if exp["status"] == "failed":
        out["error"] = exp.get("error")
    r = exp.get("results")
    if r:
        out["metrics"] = r["metrics"]
        out["baseline"] = {"metric": r["baseline"]["name"], "value": r["baseline"]["value"],
                           "meaning": r["baseline"]["description"]}
        out["rows"] = {"train": r["dataset"]["rows_train"], "test": r["dataset"]["rows_test"]}
        out["top_features"] = [{"feature": f["feature"], "importance": f["importance"]}
                               for f in r["charts"]["importance"][:5]]
        if r.get("comparison"):
            out["leaderboard"] = [{"algorithm": e["label"], "validation_score": e["score"]}
                                  for e in r["comparison"]["entries"] if e["status"] == "ok"]
        host = r["host"]
        out["ran_on"] = f"{host['provider']} {host.get('instance_type') or ''}".strip()
        out["artifacts"] = [a["name"] for a in exp["artifacts"]]
    return out


def _wait(experiment_id: int, timeout: int) -> dict:
    a = _api()
    end = time.time() + timeout
    while True:
        exp = a.json("GET", f"/experiments/{experiment_id}")
        if exp["status"] != "running" or time.time() > end:
            return exp
        time.sleep(1)


# ----------------------------------------------------------------------------- tools

@mcp.tool()
def list_algorithms(problem_type: str = "") -> dict:
    """List the approved algorithms and their hyperparameters (names, defaults, ranges, choices).

    problem_type: "classification" or "regression"; leave empty for both. The special algorithm key
    "auto_compare" is also accepted by run_experiment and ranks all of them.
    """
    cat = _api().json("GET", "/config")["algorithms"]
    if problem_type:
        if problem_type not in cat:
            raise MetricaError("problem_type must be 'classification' or 'regression'.")
        cat = {problem_type: cat[problem_type]}
    return {pt: [{"key": a["key"], "label": a["label"], "family": a["family"], "description": a["description"],
                  "parameters": [{k: v for k, v in p.items() if k in ("name", "type", "default", "min", "max", "choices")}
                                 for p in a["params"]]} for a in algos]
            for pt, algos in cat.items()}


@mcp.tool()
def list_sample_datasets() -> list[dict]:
    """List the built-in sample datasets that can be used with upload_dataset(sample=...)."""
    return _api().json("GET", "/config")["samples"]


@mcp.tool()
def upload_dataset(path: str = "", sample: str = "") -> dict:
    """Upload a dataset and get its profile (row/column counts, types, missing values, suggested target).

    Provide either `path` (a CSV, TXT, XLS or XLSX file on the machine running this MCP server) or
    `sample` (the name of a built-in sample dataset). Returns a dataset_id for run_experiment.
    """
    a = _api()
    if bool(path) == bool(sample):
        raise MetricaError("Provide exactly one of `path` or `sample`.")
    if sample:
        ds = a.json("POST", f"/datasets/sample/{sample}")
    else:
        f = Path(path).expanduser()
        if not f.is_file():
            raise MetricaError(f"File not found: {path}")
        with open(f, "rb") as fh:
            ds = a.json("POST", "/datasets", files={"file": (f.name, fh)})
    return _dataset_summary(ds)


def _launch(dataset_id, algorithm, target, problem_type, features, params, missing, encoding, scaling,
            test_size, random_state, wait, timeout) -> dict:
    a = _api()
    ds = a.json("GET", f"/datasets/{dataset_id}")
    p = ds["profile"]
    target = target or p["suggested_target"]
    if not problem_type:
        problem_type = next((t["problem_type"] for t in p["target_candidates"] if t["name"] == target), None)
        if problem_type is None:
            raise MetricaError(f"Could not infer the problem type for '{target}'. Pass problem_type explicitly.")
    if not features:
        features = [c["name"] for c in p["columns"] if not c["exclude_default"] and c["name"] != target]
    body = {"dataset_id": dataset_id, "target": target, "problem_type": problem_type, "features": features,
            "algorithm": algorithm, "params": params or {},
            "preprocessing": {"missing": missing, "encoding": encoding, "scaling": scaling,
                              "test_size": test_size, "random_state": random_state}}
    exp_id = a.json("POST", "/experiments", json=body)["id"]
    exp = _wait(exp_id, timeout) if wait else a.json("GET", f"/experiments/{exp_id}")
    return _experiment_summary(exp, a.base)


@mcp.tool()
def run_experiment(dataset_id: int, algorithm: str = "random_forest", target: str = "", problem_type: str = "",
                   features: list[str] | None = None, params: dict | None = None, missing: str = "median",
                   encoding: str = "onehot", scaling: str = "standard", test_size: float = 0.2,
                   random_state: int = 42, wait: bool = True) -> dict:
    """Train and evaluate one model on the EC2 instance and return its metrics.

    Defaults: target = the dataset's suggested target, problem_type inferred from it, features = every
    column not flagged as an identifier/constant/text. `algorithm` is a key from list_algorithms, or
    "auto_compare". `params` overrides hyperparameters. missing: median|mean|most_frequent;
    encoding: onehot|ordinal; scaling: standard|minmax|none. With wait=False it returns immediately;
    poll with get_experiment.
    """
    return _launch(dataset_id, algorithm, target, problem_type, features, params, missing, encoding, scaling,
                   test_size, random_state, wait, timeout=150)


@mcp.tool()
def compare_algorithms(dataset_id: int, target: str = "", problem_type: str = "",
                       features: list[str] | None = None, test_size: float = 0.2, random_state: int = 42) -> dict:
    """Train every approved algorithm with default settings, rank them, and return the winner's test metrics.

    Ranking uses a validation slice of the training rows; the held-out test rows only measure the winner.
    """
    return _launch(dataset_id, "auto_compare", target, problem_type, features, None, "median", "onehot",
                   "standard", test_size, random_state, True, timeout=150)


@mcp.tool()
def get_experiment(experiment_id: int) -> dict:
    """Get the status and, once finished, the metrics, top features and artifact names of an experiment."""
    a = _api()
    return _experiment_summary(a.json("GET", f"/experiments/{experiment_id}"), a.base)


@mcp.tool()
def list_experiments() -> list[dict]:
    """List your experiments, newest first, with their status and headline metric."""
    return [{"experiment_id": e["id"], "status": e["status"], "algorithm": e["algorithm_label"],
             "dataset": e["dataset_name"], "target": e["target"], "headline_metric": e["primary_metric"],
             "headline_value": e["primary_value"]} for e in _api().json("GET", "/experiments")]


@mcp.tool()
def download_artifact(experiment_id: int, name: str = "all", save_dir: str = ".") -> dict:
    """Download an experiment file to a local folder.

    name: results.json, metrics.csv, predictions.csv, experiment_report.pdf, model.joblib,
    experiment_config.json, or "all" for a zip of everything. model.joblib is a pickle; only load it
    if you trust this MetricaML server.
    """
    r = _api().request("GET", f"/experiments/{experiment_id}/download/{name}")
    folder = Path(save_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    target = folder / (f"metricaml_experiment_{experiment_id}.zip" if name == "all"
                       else f"experiment_{experiment_id}_{safe}")
    target.write_bytes(r.content)
    return {"saved_to": str(target.resolve()), "bytes": len(r.content)}


if __name__ == "__main__":
    mcp.run()
