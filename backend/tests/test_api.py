import io
import sqlite3

import pytest

from app import config
from app.algorithms import CATALOGUE
from .conftest import wait_for

SAMPLES = ["customer_churn.csv", "housing_prices.csv", "student_performance.xlsx", "iris.txt", "wine_cultivar.xls"]


def use_sample(client, name):
    r = client.post(f"/api/datasets/sample/{name}")
    assert r.status_code == 200, r.text
    return r.json()


def run(client, dataset, **overrides):
    profile = dataset["profile"]
    target = overrides.pop("target", profile["suggested_target"])
    cols = {c["name"]: c for c in profile["columns"]}
    guess = {t["name"]: t["problem_type"] for t in profile["target_candidates"]}
    body = {
        "dataset_id": dataset["id"],
        "target": target,
        "problem_type": guess.get(target, "classification"),
        "features": [n for n, c in cols.items() if not c["exclude_default"] and n != target],
        "algorithm": "random_forest",
        "params": {},
    }
    body.update(overrides)
    return client.post("/api/experiments", json=body)


# ------------------------------------------------------------------ auth

def test_requires_login():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anon:
        assert anon.get("/api/experiments").status_code == 401
        assert anon.get("/api/auth/me").status_code == 401


def test_register_login_logout(client):
    me = client.get("/api/auth/me").json()
    assert me["email"] == "main@example.com"
    dup = client.post("/api/auth/register", json={"name": "x", "email": "MAIN@example.com", "password": "12345678"})
    assert dup.status_code == 409
    assert client.post("/api/auth/register", json={"name": "x", "email": "nope", "password": "12345678"}).status_code == 422
    assert client.post("/api/auth/register", json={"name": "x", "email": "a@b.co", "password": "short"}).status_code == 422
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "main@example.com", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "main@example.com", "password": "correct-horse"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 200


# ------------------------------------------------------------------ upload and profiling

@pytest.mark.parametrize("name", SAMPLES)
def test_sample_profiles(client, name):
    ds = use_sample(client, name)
    p = ds["profile"]
    assert p["rows"] >= 100 and p["columns_count"] >= 5
    assert p["suggested_target"] in {c["name"] for c in p["columns"]}
    assert len(p["preview"]) == 8


def test_churn_profile_details(client):
    p = use_sample(client, "customer_churn.csv")["profile"]
    cols = {c["name"]: c for c in p["columns"]}
    assert p["rows"] == 1507 and p["duplicate_rows"] == 7
    assert p["missing_values"] == 21
    assert cols["customer_id"]["recommendation"] == "id" and cols["customer_id"]["exclude_default"]
    assert cols["age"]["recommendation"] == "feature"
    assert p["suggested_target"] == "churn"
    assert p["target_candidates"][0]["problem_type"] == "classification"


def test_rejects_bad_uploads(client, monkeypatch):
    assert client.post("/api/datasets", files={"file": ("evil.py", b"print(1)", "text/plain")}).status_code == 415
    assert client.post("/api/datasets", files={"file": ("../../x.csv", b"", "text/csv")}).status_code == 422
    junk = client.post("/api/datasets", files={"file": ("a.csv", b"a,b\n1,2\n", "text/csv")})
    assert junk.status_code == 422 and "at least 10 rows" in junk.json()["detail"]
    fake_xlsx = client.post("/api/datasets", files={"file": ("a.xlsx", b"not really excel", "application/octet-stream")})
    assert fake_xlsx.status_code == 422
    monkeypatch.setattr(config, "MAX_FILE_MB", 0)
    big = client.post("/api/datasets", files={"file": ("a.csv", io.BytesIO(b"a,b\n" + b"1,2\n" * 50), "text/csv")})
    assert big.status_code == 413


def test_row_limit(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_ROWS", 20)
    r = client.post("/api/datasets/sample/iris.txt")
    assert r.status_code == 422 and "rows" in r.json()["detail"]


# ------------------------------------------------------------------ experiments

def test_classification_end_to_end(client):
    ds = use_sample(client, "customer_churn.csv")
    r = run(client, ds, params={"n_estimators": 40, "max_depth": 6})
    assert r.status_code == 201, r.text
    exp = wait_for(client, r.json()["id"])
    assert exp["status"] == "completed", exp
    res = exp["results"]
    assert res["metrics"]["accuracy"] > 0.65
    assert set(res["metrics"]) == {"accuracy", "precision", "recall", "f1"}
    assert len(res["charts"]["confusion"]["matrix"]) == 2
    assert res["charts"]["importance"]
    assert res["dataset"]["rows_train"] + res["dataset"]["rows_test"] == res["dataset"]["rows_used"]
    assert [s["name"] for s in exp["stages"]][-1] == "Generating results"
    assert {a["name"] for a in exp["artifacts"]} == {"results.json", "metrics.csv", "predictions.csv",
                                                   "experiment_report.pdf", "model.joblib", "experiment_config.json"}
    pdf = client.get(f"/api/experiments/{exp['id']}/download/experiment_report.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/experiments/{exp['id']}/download/all").content.startswith(b"PK")
    assert client.get(f"/api/experiments/{exp['id']}/download/secret.txt").status_code == 404
    assert client.get("/api/experiments").json()[0]["id"] == exp["id"]


def test_regression_end_to_end(client):
    ds = use_sample(client, "housing_prices.csv")
    r = run(client, ds, algorithm="ridge", params={"alpha": 2})
    exp = wait_for(client, r.json()["id"])
    assert exp["status"] == "completed", exp
    m = exp["results"]["metrics"]
    assert m["r2"] > 0.8 and set(m) == {"mae", "mse", "rmse", "r2"}
    assert exp["results"]["charts"]["scatter"] and exp["results"]["charts"]["residuals"]["counts"]


def test_model_artifact_predicts(client):
    import joblib
    import pandas as pd
    ds = use_sample(client, "iris.txt")
    exp = wait_for(client, run(client, ds, algorithm="knn").json()["id"])
    bundle = joblib.load(config.EXPERIMENT_DIR / str(exp["id"]) / "model.joblib")
    row = pd.DataFrame([{f: 1.0 for f in bundle["features"]}])
    assert bundle["classes"][int(bundle["pipeline"].predict(row)[0])] in {"setosa", "versicolor", "virginica"}


@pytest.mark.parametrize("problem,key", [(p, k) for p, algos in CATALOGUE.items() for k in algos])
def test_every_algorithm_runs(client, problem, key):
    ds = use_sample(client, "iris.txt" if problem == "classification" else "housing_prices.csv")
    target = "species" if problem == "classification" else "price"
    exp = wait_for(client, run(client, ds, target=target, problem_type=problem, algorithm=key).json()["id"])
    assert exp["status"] == "completed", exp.get("error")


def test_multiclass_excel(client):
    ds = use_sample(client, "student_performance.xlsx")
    exp = wait_for(client, run(client, ds, algorithm="logistic_regression").json()["id"])
    assert exp["status"] == "completed", exp.get("error")
    assert len(exp["results"]["classes"]) == 4
    assert exp["results"]["metrics"]["accuracy"] > 0.5


def test_validation(client):
    ds = use_sample(client, "iris.txt")
    assert run(client, ds, params={"n_estimators": 100000}).status_code == 422
    assert run(client, ds, params={"n_estimators": 12.5}).status_code == 422
    assert run(client, ds, params={"criterion": "__import__('os')"}).status_code == 422
    assert run(client, ds, algorithm="ridge").status_code == 422  # regression algorithm, classification problem
    assert run(client, ds, algorithm="os.system").status_code == 422
    assert run(client, ds, problem_type="regression", algorithm="ridge").status_code == 422  # categorical target
    assert run(client, ds, features=["species", "sepal_length"]).status_code == 422
    assert run(client, ds, features=["nope"]).status_code == 422
    assert run(client, ds, features=[]).status_code == 422
    assert run(client, ds, dataset_id=99999).status_code == 404
    assert run(client, ds, preprocessing={"scaling": "robust"}).status_code == 422
    assert run(client, ds, preprocessing={"test_size": 0.9}).status_code == 422


def test_single_experiment_at_a_time(client):
    ds = use_sample(client, "iris.txt")
    con = sqlite3.connect(config.DB_PATH)
    con.execute("INSERT INTO experiments (user_id, dataset_name, algorithm, algorithm_label, problem_type, target, "
                "status, config_json, created_at) VALUES (1, 'x', 'knn', 'KNN', 'classification', 't', 'running', '{}', 'now')")
    con.commit()
    assert run(client, ds).status_code == 409
    con.execute("UPDATE experiments SET status='failed' WHERE dataset_name='x'")
    con.commit()
    con.close()


def test_time_limit_enforced(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_TRAIN_SECONDS", 1)
    ds = use_sample(client, "iris.txt")
    exp = wait_for(client, run(client, ds).json()["id"])
    assert exp["status"] == "failed" and "limit" in exp["error"]


def test_failed_run_reports_reason(client):
    ds = use_sample(client, "customer_churn.csv")
    r = run(client, ds, target="monthly_charges", problem_type="classification", features=["age"])
    exp = wait_for(client, r.json()["id"])
    assert exp["status"] == "failed" and "distinct values" in exp["error"]


def test_users_are_isolated(client, make_client):
    ds = use_sample(client, "iris.txt")
    exp = wait_for(client, run(client, ds).json()["id"])
    other = make_client("other@example.com")
    assert other.get(f"/api/experiments/{exp['id']}").status_code == 404
    assert other.get(f"/api/datasets/{ds['id']}").status_code == 404
    assert other.get(f"/api/experiments/{exp['id']}/download/results.json").status_code == 404
    assert other.delete(f"/api/experiments/{exp['id']}").status_code == 404
    assert run(other, ds).status_code == 404
    assert other.get("/api/experiments").json() == []


def test_delete_experiment(client):
    ds = use_sample(client, "iris.txt")
    exp = wait_for(client, run(client, ds).json()["id"])
    assert client.delete(f"/api/experiments/{exp['id']}").status_code == 200
    assert client.get(f"/api/experiments/{exp['id']}").status_code == 404
    assert not (config.EXPERIMENT_DIR / str(exp["id"])).exists()
