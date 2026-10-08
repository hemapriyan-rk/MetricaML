"""MetricaML API. Also serves the built React app so a single process fronts everything."""
import io
import json
import re
import shutil
import sqlite3
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import algorithms, config, runner, security
from .db import db, init_db, now_iso, row_to_experiment
from .pipeline import ARTIFACTS, STAGES
from .profiler import DatasetError, load_dataframe, profile_dataframe
from .system_info import get_host

SAMPLES = {
    "customer_churn.csv": "Which telecom customers will leave? Classification, with missing values and an ID column.",
    "housing_prices.csv": "Predict a house's sale price from size, age and neighbourhood. Regression.",
    "student_performance.xlsx": "Predict a student's grade band from study habits. Multi-class classification, Excel format.",
    "iris.txt": "The classic 3-species flower dataset, tab-separated. Classification.",
    "wine_cultivar.xls": "Chemical measurements of wines from three growers. Classification, legacy Excel format.",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    runner.mark_orphans_failed()
    yield


app = FastAPI(title="MetricaML", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body")
    return JSONResponse({"detail": f"{field}: {first['msg']}" if field else first["msg"]}, status_code=422)


# --------------------------------------------------------------------------- auth

def current_user(request: Request) -> dict:
    user = security.user_for_token(request.cookies.get(config.COOKIE_NAME))
    if user is None:
        raise HTTPException(401, "Please sign in to continue.")
    return user


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: str = Field(max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(max_length=128)


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(config.COOKIE_NAME, token, max_age=config.SESSION_DAYS * 86400, httponly=True,
                        samesite="lax", secure=config.COOKIE_SECURE, path="/")


@app.post("/api/auth/register")
def register(body: RegisterIn, response: Response):
    email = body.email.strip().lower()
    if not _EMAIL.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    try:
        with db() as conn:
            cur = conn.execute("INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                               (email, body.name.strip(), security.hash_password(body.password), now_iso()))
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    _set_cookie(response, security.create_session(user_id))
    return {"id": user_id, "email": email, "name": body.name.strip()}


@app.post("/api/auth/login")
def login(body: LoginIn, response: Response):
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (body.email.strip().lower(),)).fetchone()
    if row is None or not security.verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Incorrect email or password.")
    _set_cookie(response, security.create_session(row["id"]))
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    security.delete_session(request.cookies.get(config.COOKIE_NAME))
    response.delete_cookie(config.COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    with db() as conn:
        stats = conn.execute(
            "SELECT COUNT(*) AS total, SUM(status='completed') AS completed FROM experiments WHERE user_id = ?",
            (user["id"],)).fetchone()
        datasets = conn.execute("SELECT COUNT(*) FROM datasets WHERE user_id = ?", (user["id"],)).fetchone()[0]
    return {**user, "experiments": stats["total"], "completed": stats["completed"] or 0, "datasets": datasets}


# --------------------------------------------------------------------------- platform info

@app.get("/api/config")
def platform_config(_: dict = Depends(current_user)):
    return {
        "algorithms": algorithms.public_catalogue(),
        "stages": STAGES,
        "limits": {"max_file_mb": config.MAX_FILE_MB, "max_rows": config.MAX_ROWS,
                   "max_columns": config.MAX_COLUMNS, "max_train_seconds": config.MAX_TRAIN_SECONDS,
                   "concurrent_experiments": 1, "extensions": sorted(config.ALLOWED_EXTENSIONS)},
        "host": get_host(),
        "samples": [{"name": n, "description": d} for n, d in SAMPLES.items() if (config.SAMPLE_DIR / n).exists()],
    }


# --------------------------------------------------------------------------- datasets

def _dataset_payload(row) -> dict:
    return {"id": row["id"], "filename": row["filename"], "size_bytes": row["size_bytes"],
            "profile": json.loads(row["profile_json"])}


def _register_dataset(user_id: int, path: Path, ext: str, display_name: str) -> dict:
    try:
        df = load_dataframe(path, ext)
        profile = profile_dataframe(df, display_name)
    except DatasetError:
        path.unlink(missing_ok=True)
        raise
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO datasets (user_id, filename, stored_path, ext, size_bytes, n_rows, n_cols, profile_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, display_name, str(path), ext, path.stat().st_size, profile["rows"], profile["columns_count"],
             json.dumps(profile), now_iso()))
        row = conn.execute("SELECT * FROM datasets WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _dataset_payload(row)


@app.post("/api/datasets")
def upload_dataset(file: UploadFile = File(...), user: dict = Depends(current_user)):
    original = Path(file.filename or "").name
    ext = Path(original).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Unsupported file type. Upload a CSV, TXT, XLS or XLSX file.")
    config.ensure_dirs()
    dest = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    limit = config.MAX_FILE_MB * 1024 * 1024
    size = 0
    with open(dest, "wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"The file is larger than {config.MAX_FILE_MB} MB, the limit for this instance.")
            out.write(chunk)
    try:
        return _register_dataset(user["id"], dest, ext, original[:120])
    except DatasetError as exc:
        raise HTTPException(422, str(exc))


@app.post("/api/datasets/sample/{name}")
def use_sample(name: str, user: dict = Depends(current_user)):
    if name not in SAMPLES or not (config.SAMPLE_DIR / name).exists():
        raise HTTPException(404, "Sample dataset not found.")
    ext = Path(name).suffix.lower()
    config.ensure_dirs()
    dest = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    shutil.copyfile(config.SAMPLE_DIR / name, dest)
    try:
        return _register_dataset(user["id"], dest, ext, name)
    except DatasetError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/datasets/{dataset_id}")
def get_dataset(dataset_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id = ? AND user_id = ?", (dataset_id, user["id"])).fetchone()
    if row is None:
        raise HTTPException(404, "Dataset not found.")
    return _dataset_payload(row)


# --------------------------------------------------------------------------- experiments

class PreprocessingIn(BaseModel):
    missing: Literal["median", "mean", "most_frequent"] = "median"
    encoding: Literal["onehot", "ordinal"] = "onehot"
    scaling: Literal["standard", "minmax", "none"] = "standard"
    test_size: float = Field(0.2, ge=0.1, le=0.5)
    random_state: int = Field(42, ge=0, le=2**31 - 1)


class ExperimentIn(BaseModel):
    dataset_id: int
    target: str
    problem_type: Literal["classification", "regression"]
    features: list[str] = Field(min_length=1, max_length=config.MAX_COLUMNS)
    algorithm: str
    params: dict = Field(default_factory=dict)
    preprocessing: PreprocessingIn = Field(default_factory=PreprocessingIn)


def _summary(d: dict) -> dict:
    keys = ("id", "dataset_name", "algorithm", "algorithm_label", "problem_type", "target", "status",
            "primary_metric", "primary_value", "created_at", "finished_at", "duration_s", "error")
    return {k: d[k] for k in keys}


@app.post("/api/experiments", status_code=201)
def create_experiment(body: ExperimentIn, user: dict = Depends(current_user)):
    with db() as conn:
        ds = conn.execute("SELECT * FROM datasets WHERE id = ? AND user_id = ?", (body.dataset_id, user["id"])).fetchone()
    if ds is None:
        raise HTTPException(404, "Dataset not found. Upload it again.")
    cols = {c["name"]: c for c in json.loads(ds["profile_json"])["columns"]}
    if body.target not in cols:
        raise HTTPException(422, f"Target column '{body.target}' is not in the dataset.")
    if len(set(body.features)) != len(body.features):
        raise HTTPException(422, "Each feature can only be selected once.")
    unknown = [f for f in body.features if f not in cols]
    if unknown:
        raise HTTPException(422, f"Unknown feature columns: {', '.join(unknown[:5])}.")
    if body.target in body.features:
        raise HTTPException(422, "The target column can't also be a feature.")
    if body.problem_type == "regression" and cols[body.target]["kind"] not in ("integer", "float"):
        raise HTTPException(422, f"'{body.target}' is not numeric, so it can't be a regression target.")
    try:
        params = algorithms.validate_params(body.problem_type, body.algorithm, body.params)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    cfg = {"target": body.target, "problem_type": body.problem_type, "features": body.features,
           "algorithm": body.algorithm, "params": params, "preprocessing": body.preprocessing.model_dump()}
    label = algorithms.algorithm_label(body.problem_type, body.algorithm)

    def insert(conn):
        cur = conn.execute(
            "INSERT INTO experiments (user_id, dataset_id, dataset_name, algorithm, algorithm_label, problem_type, "
            "target, status, config_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)",
            (user["id"], ds["id"], ds["filename"], body.algorithm, label, body.problem_type, body.target,
             json.dumps(cfg), now_iso()))
        return cur.lastrowid

    exp_id = runner.submit(insert)
    if exp_id is None:
        raise HTTPException(409, "Another experiment is running. This instance runs one at a time; try again in a moment.")
    return {"id": exp_id}


@app.get("/api/experiments")
def list_experiments(user: dict = Depends(current_user)):
    with db() as conn:
        rows = conn.execute("SELECT * FROM experiments WHERE user_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
    return [_summary(row_to_experiment(r)) for r in rows]


def _owned(conn, exp_id: int, user_id: int):
    row = conn.execute("SELECT * FROM experiments WHERE id = ? AND user_id = ?", (exp_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Experiment not found.")
    return row


@app.get("/api/experiments/{exp_id}")
def get_experiment(exp_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        exp = row_to_experiment(_owned(conn, exp_id, user["id"]))
    payload = {**_summary(exp), "stages": exp["stages"], "config": exp["config"], "host": exp["host"],
               "results": None, "artifacts": []}
    folder = config.EXPERIMENT_DIR / str(exp_id)
    if exp["status"] == "completed" and (folder / "results.json").exists():
        payload["results"] = json.loads((folder / "results.json").read_text())
        payload["artifacts"] = [{"name": n, "description": d, "size": (folder / n).stat().st_size}
                                for n, d in ARTIFACTS.items() if (folder / n).exists()]
    return payload


@app.delete("/api/experiments/{exp_id}")
def delete_experiment(exp_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        exp = _owned(conn, exp_id, user["id"])
        if exp["status"] == "running":
            raise HTTPException(409, "This experiment is still running.")
        conn.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))
    shutil.rmtree(config.EXPERIMENT_DIR / str(exp_id), ignore_errors=True)
    return {"ok": True}


@app.get("/api/experiments/{exp_id}/download/{name}")
def download(exp_id: int, name: str, user: dict = Depends(current_user)):
    with db() as conn:
        exp = _owned(conn, exp_id, user["id"])
    if exp["status"] != "completed":
        raise HTTPException(409, "Files are available once the experiment has completed.")
    folder = config.EXPERIMENT_DIR / str(exp_id)
    if name == "all":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in ARTIFACTS:
                if (folder / fname).exists():
                    zf.write(folder / fname, fname)
        return Response(buf.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="metricaml_experiment_{exp_id}.zip"'})
    if name not in ARTIFACTS or not (folder / name).exists():
        raise HTTPException(404, "File not found.")
    return FileResponse(folder / name, filename=f"experiment_{exp_id}_{name}")


# --------------------------------------------------------------------------- web app

if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found.")
        candidate = (config.FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and config.FRONTEND_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(config.FRONTEND_DIST / "index.html")
