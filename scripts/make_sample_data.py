"""Generates the datasets in sample_data/. Run from the repo root: python scripts/make_sample_data.py"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.datasets import load_iris, load_wine

OUT = Path(__file__).resolve().parent.parent / "sample_data"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(7)


def customer_churn(n=1500):
    cities = ["Chennai", "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Pune", "Kolkata", "Jaipur", "Kochi",
              "Lucknow", "Indore", "Surat"]
    age = rng.integers(18, 71, n)
    contract = rng.choice(["Month-to-month", "One year", "Two year"], n, p=[0.55, 0.25, 0.20])
    tenure = np.clip(rng.gamma(2.2, 11, n).astype(int) + 1, 1, 72)
    monthly = np.round(rng.normal(65, 22, n).clip(18, 120), 2)
    calls = rng.poisson(1.6, n)
    income = np.round(rng.normal(52000, 16000, n).clip(15000, 140000), 0)
    city = rng.choice(cities, n)
    internet = rng.choice(["Fiber", "DSL", "None"], n, p=[0.45, 0.4, 0.15])
    z = 2.3 * (-0.4 + 1.5 * (contract == "Month-to-month") - 1.1 * (contract == "Two year") - 0.035 * tenure
         + 0.018 * (monthly - 65) + 0.35 * calls + 0.5 * (internet == "Fiber") - 0.00001 * (income - 52000)) - 0.3
    churn = np.where(rng.random(n) < 1 / (1 + np.exp(-z)), "Yes", "No")
    df = pd.DataFrame({"customer_id": np.arange(10001, 10001 + n), "age": age, "city": city, "contract": contract,
                       "internet_service": internet, "tenure_months": tenure, "monthly_charges": monthly,
                       "support_calls": calls, "income": income, "churn": churn})
    df.loc[rng.choice(n, 12, replace=False), "income"] = np.nan
    df.loc[rng.choice(n, 9, replace=False), "city"] = np.nan
    df = pd.concat([df, df.sample(7, random_state=1)], ignore_index=True)
    df.to_csv(OUT / "customer_churn.csv", index=False)


def housing(n=1200):
    hoods = {"Riverside": 1.25, "Old Town": 1.1, "Greenfield": 1.0, "Harbour": 1.4, "Eastgate": 0.85, "Hillcrest": 1.15}
    hood = rng.choice(list(hoods), n)
    area = rng.normal(1650, 520, n).clip(450, 4200).round()
    bedrooms = np.clip((area / 600 + rng.normal(0, 0.7, n)).round(), 1, 6).astype(int)
    baths = np.clip((bedrooms * 0.6 + rng.normal(0, 0.5, n)).round(), 1, 5).astype(int)
    age = rng.integers(0, 70, n)
    garage = rng.choice(["Yes", "No"], n, p=[0.6, 0.4])
    dist = np.round(rng.gamma(2.5, 3.0, n).clip(0.5, 30), 1)
    price = (area * 118 + bedrooms * 6500 + baths * 9000 - age * 850 + (garage == "Yes") * 14000 - dist * 2100)
    price = price * np.array([hoods[h] for h in hood]) + rng.normal(0, 18000, n)
    df = pd.DataFrame({"property_id": [f"P{i:05d}" for i in range(n)], "area_sqft": area, "bedrooms": bedrooms,
                       "bathrooms": baths, "age_years": age, "neighborhood": hood, "garage": garage,
                       "distance_to_center_km": dist, "price": price.round(-2).clip(40000)})
    df.loc[rng.choice(n, 10, replace=False), "age_years"] = np.nan
    df.to_csv(OUT / "housing_prices.csv", index=False)


def students(n=900):
    hours = np.round(rng.gamma(3, 1.6, n).clip(0, 14), 1)
    attendance = np.round(rng.normal(82, 11, n).clip(35, 100), 0)
    previous = np.round(rng.normal(64, 15, n).clip(10, 100), 0)
    sleep = np.round(rng.normal(6.9, 1.1, n).clip(3.5, 10), 1)
    internet = rng.choice(["Yes", "No"], n, p=[0.85, 0.15])
    parent = rng.choice(["High school", "Bachelor", "Master", "Doctorate"], n, p=[0.35, 0.4, 0.2, 0.05])
    score = (0.45 * previous + 3.1 * hours + 0.22 * attendance + 1.2 * sleep + 3 * (internet == "Yes")
             + rng.normal(0, 7, n))
    grade = pd.cut(score, bins=[-np.inf, 52, 64, 76, np.inf], labels=["D", "C", "B", "A"]).astype(str)
    pd.DataFrame({"student_id": np.arange(1, n + 1), "hours_studied_per_day": hours, "attendance_pct": attendance,
                  "previous_score": previous, "sleep_hours": sleep, "internet_access": internet,
                  "parent_education": parent, "grade": grade}).to_excel(OUT / "student_performance.xlsx", index=False)


def iris():
    d = load_iris(as_frame=True)
    df = d.frame.copy()
    df["species"] = df["target"].map(dict(enumerate(d.target_names)))
    df = df.drop(columns="target")
    df.columns = [c.replace(" (cm)", "").replace(" ", "_") for c in df.columns]
    df.to_csv(OUT / "iris.txt", index=False, sep="\t")


def wine():
    d = load_wine(as_frame=True)
    df = d.frame.copy()
    df["cultivar"] = df["target"].map({0: "Grower A", 1: "Grower B", 2: "Grower C"})
    df = df.drop(columns="target")
    try:
        import xlwt  # only needed to generate the legacy .xls format (pandas 3 dropped its xlwt writer)
    except ImportError:
        print("Skipped wine_cultivar.xls: pip install xlwt to generate it")
        return
    book = xlwt.Workbook()
    sheet = book.add_sheet("wine")
    for j, col in enumerate(df.columns):
        sheet.write(0, j, col)
    for i, row in enumerate(df.itertuples(index=False), start=1):
        for j, val in enumerate(row):
            sheet.write(i, j, val if isinstance(val, str) else float(val))
    book.save(str(OUT / "wine_cultivar.xls"))


if __name__ == "__main__":
    customer_churn(); housing(); students(); iris(); wine()
    print("Wrote", *sorted(p.name for p in OUT.iterdir()))
