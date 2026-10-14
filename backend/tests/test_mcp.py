import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mcp_server"))
server = pytest.importorskip("server")  # needs the `mcp` package (see mcp_server/requirements.txt)


@pytest.fixture(autouse=True)
def _use_test_client(client):
    server.use_client(client)


def test_tools_are_registered():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert names == {"list_algorithms", "list_sample_datasets", "upload_dataset", "run_experiment",
                     "compare_algorithms", "get_experiment", "list_experiments", "download_artifact"}


def test_catalogue_and_samples():
    algos = server.list_algorithms("classification")
    assert {"random_forest", "gradient_boosting", "mlp"} <= {a["key"] for a in algos["classification"]}
    assert "regression" not in algos
    assert any(s["name"] == "iris.txt" for s in server.list_sample_datasets())
    with pytest.raises(server.MetricaError):
        server.list_algorithms("clustering")


def test_upload_run_and_download(tmp_path):
    ds = server.upload_dataset(sample="iris.txt")
    assert ds["suggested_target"] == "species" and ds["rows"] == 150
    exp = server.run_experiment(ds["dataset_id"], algorithm="knn", params={"n_neighbors": 7})
    assert exp["status"] == "completed", exp
    assert exp["metrics"]["accuracy"] > 0.85 and "model.joblib" in exp["artifacts"]
    assert server.get_experiment(exp["experiment_id"])["metrics"] == exp["metrics"]
    assert any(e["experiment_id"] == exp["experiment_id"] for e in server.list_experiments())
    saved = server.download_artifact(exp["experiment_id"], "metrics.csv", str(tmp_path))
    assert Path(saved["saved_to"]).read_text().startswith("metric,value")


def test_upload_local_file_and_compare(tmp_path):
    f = tmp_path / "mini.csv"
    f.write_text("x1,x2,label\n" + "\n".join(f"{i},{i % 7},{'a' if i % 3 else 'b'}" for i in range(120)))
    ds = server.upload_dataset(path=str(f))
    assert ds["rows"] == 120
    exp = server.compare_algorithms(ds["dataset_id"])
    assert exp["status"] == "completed", exp
    assert len(exp["leaderboard"]) >= 10


def test_clear_errors():
    with pytest.raises(server.MetricaError, match="exactly one"):
        server.upload_dataset()
    with pytest.raises(server.MetricaError, match="not found"):
        server.upload_dataset(path="/definitely/not/here.csv")
    with pytest.raises(server.MetricaError, match="not found|Dataset"):
        server.run_experiment(999999)
    ds = server.upload_dataset(sample="iris.txt")
    with pytest.raises(server.MetricaError):
        server.run_experiment(ds["dataset_id"], algorithm="ridge")  # regression algorithm on a classification target
    with pytest.raises(server.MetricaError):
        server.download_artifact(999999, "all")
