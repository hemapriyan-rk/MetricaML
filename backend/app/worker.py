"""Entry point for the experiment worker process: `python -m app.worker <experiment_id>`."""
import sys

from .pipeline import run_experiment

if __name__ == "__main__":
    try:
        run_experiment(int(sys.argv[1]))
    except Exception:
        # The failure has already been recorded on the experiment; exit non-zero for the runner.
        sys.exit(1)
