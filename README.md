# MetricaML

Cloud-based machine learning experimentation platform. Upload a dataset, let MetricaML profile it, pick a target, features and algorithm, run the experiment **on an AWS EC2 instance**, then inspect the results and download the model.

**Flow:** Upload → Profile → Target → Features → Preprocessing → Algorithm → Run on EC2 → Results → Download

## Why this is IaaS

The ML computation itself runs on a virtual machine that we control: the OS, the Python runtime, the ML libraries (scikit-learn, pandas, NumPy), CPU and memory, process execution and the filesystem. AWS provides the physical server and virtualisation; everything above the VM boundary is ours. EC2 is not just hosting a website here: each experiment is a separate worker process on the instance, with a time limit and resource limits.

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React (Vite), plain CSS |
| Backend | Python, FastAPI |
| ML | pandas, NumPy, scikit-learn, joblib |
| Database / files | SQLite and the EC2 filesystem |
| Infrastructure | AWS EC2 (Ubuntu), Nginx, systemd |

## Features

- Register / login / logout (scrypt-hashed passwords, HttpOnly session cookie, per-user data)
- CSV, TXT, XLS, XLSX upload with drag and drop
- Automatic profiling: rows, column types, missing values, duplicates, ID / constant / text column warnings
- Target suggestion and classification / regression detection (overridable)
- Preprocessing: imputation, one-hot / ordinal encoding, scaling, train/test split, random state
- 5 classification and 4 regression algorithms, with parameter forms generated from `backend/app/algorithms.py`
- Live processing screen showing the instance the work runs on
- Results: accuracy / precision / recall / F1 or MAE / MSE / RMSE / R², confusion matrix, feature importance, class distribution, actual vs predicted, residuals
- Downloads: `results.json`, `metrics.csv`, `predictions.csv`, `experiment_report.pdf`, `model.joblib`, `experiment_config.json` (or all as a zip)
- Experiment history

## Limits (protect a t3.micro)

50 MB file, 100,000 rows, 1 experiment at a time, 120 s per experiment. Only approved algorithms can run, and users submit configuration, never code.

## Run locally

```bash
# backend
cd backend
python -m venv .venv
.venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :8000)
```

To serve everything from one process, run `npm run build` in `frontend` and open http://localhost:8000.

Tests: `cd backend && pip install -r requirements-dev.txt && pytest`

## Sample datasets

In `sample_data/` (also available as one-click samples in the app):

| File | Format | Task |
| --- | --- | --- |
| `customer_churn.csv` | CSV | Classification, has missing values, duplicates and an ID column |
| `housing_prices.csv` | CSV | Regression |
| `student_performance.xlsx` | XLSX | Multi-class classification |
| `iris.txt` | TXT (tab separated) | Classification |
| `wine_cultivar.xls` | XLS | Classification |

## Deploy on AWS EC2 from GitHub

1. In the AWS console launch an **Ubuntu 24.04** instance, type **t3.micro**, 16 GB disk. Security group: allow SSH (22) from your IP, and HTTP (80) and HTTPS (443) from anywhere.
2. SSH in and run:
   ```bash
   sudo apt-get update && sudo apt-get install -y git
   git clone https://github.com/hemapriyan-rk/MetricaML.git
   bash MetricaML/deploy/setup_ec2.sh
   ```
   The script installs Python, Node and Nginx, adds swap, builds the app, and starts it as a `systemd` service behind Nginx. It prints the URL at the end (`http://<public-ip>/`).
3. Update later with `bash /opt/metricaml/deploy/update.sh` after pushing to GitHub.

**HTTPS** needs a domain pointing at the instance:
```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
sudo systemctl edit metricaml      # add:  [Service]  Environment=METRICA_COOKIE_SECURE=1
sudo systemctl restart metricaml
```

## Project layout

```
backend/app/    main.py (API), profiler.py, pipeline.py (experiment engine), algorithms.py,
                runner.py (worker process + time limit), report.py (PDF), security.py, db.py
backend/tests/  API and end-to-end tests
frontend/src/   React app (pages/, components/)
deploy/         EC2 setup, systemd unit, Nginx config
sample_data/    test datasets
```

Note: `model.joblib` is a pickle. Only load models you created yourself.
