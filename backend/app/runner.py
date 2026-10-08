"""Launches experiments as child processes with a hard time limit."""
import json
import os
import subprocess
import sys
import threading
import time

from . import config
from .db import db, now_iso

_lock = threading.Lock()


def mark_orphans_failed() -> None:
    """Experiments still 'running' at startup were interrupted by a restart."""
    with db() as conn:
        conn.execute("UPDATE experiments SET status='failed', error=?, finished_at=? WHERE status='running'",
                     ("The server restarted while this experiment was running.", now_iso()))


def running_count() -> int:
    with db() as conn:
        return conn.execute("SELECT COUNT(*) FROM experiments WHERE status='running'").fetchone()[0]


def submit(insert_experiment) -> int | None:
    """Create the experiment row via `insert_experiment(conn)` unless one is already running.

    Returns the new id, or None if the single experiment slot is taken.
    """
    with _lock:
        if running_count() > 0:
            return None
        with db() as conn:
            exp_id = insert_experiment(conn)
        threading.Thread(target=_supervise, args=(exp_id,), daemon=True).start()
        return exp_id


def _supervise(exp_id: int) -> None:
    env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    kwargs = {}
    if os.name == "posix":
        kwargs["preexec_fn"] = lambda: os.nice(10)  # keep the web server responsive while training
    proc = subprocess.Popen([sys.executable, "-m", "app.worker", str(exp_id)], cwd=config.BACKEND_DIR, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **kwargs)
    started = time.time()
    try:
        _, stderr = proc.communicate(timeout=config.MAX_TRAIN_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        _fail_if_running(exp_id, f"Stopped after the {config.MAX_TRAIN_SECONDS} second limit. "
                                 "Try fewer rows, fewer features, or a lighter algorithm.", started)
        return
    if proc.returncode != 0:
        _fail_if_running(exp_id, "The worker stopped unexpectedly. The instance may have run out of memory; "
                                 "try a smaller dataset or fewer features.", started)


def _fail_if_running(exp_id: int, message: str, started: float) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE experiments SET status='failed', error=?, finished_at=?, duration_s=? "
            "WHERE id=? AND status='running'",
            (message, now_iso(), round(time.time() - started, 2), exp_id))
        # close the stage that was in flight so the UI can show where it stopped
        row = conn.execute("SELECT stages_json FROM experiments WHERE id=?", (exp_id,)).fetchone()
        stages = json.loads(row["stages_json"] or "[]")
        for s in stages:
            if s["started"] and not s["ended"]:
                s["ended"] = time.time()
        conn.execute("UPDATE experiments SET stages_json=? WHERE id=?", (json.dumps(stages), exp_id))
