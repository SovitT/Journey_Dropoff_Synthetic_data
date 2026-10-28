import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from common import (SEED, customer_id, product_id, page_id, experiment_id)

COUNTRIES = ["IN", "US", "GB", "DE", "SG"]
COUNTRY_P = [0.60, 0.15, 0.10, 0.10, 0.05]
CATEGORIES = ["electronics", "fashion", "home", "beauty", "sports"]
PAGE_TYPES = ["home", "search", "product", "cart", "checkout",
              "payment", "support", "faq", "login"]


def make_customers(rng, n):
    offsets = rng.integers(0, 365, n)
    signup = pd.Timestamp("2025-01-01") + pd.to_timedelta(offsets, unit="D")
    return pd.DataFrame({
        "customer_id": [customer_id(i) for i in range(1, n + 1)],
        "signup_date": signup.strftime("%Y-%m-%d"),
        "country": rng.choice(COUNTRIES, n, p=COUNTRY_P),
        "consent_status": rng.choice(["granted", "denied"], n, p=[0.75, 0.25]),
    })


def make_products(rng, n=200):
    price = np.round(rng.lognormal(3.5, 0.6, n), 2).clip(5, 500)
    return pd.DataFrame({
        "product_id": [product_id(i) for i in range(1, n + 1)],
        "category": rng.choice(CATEGORIES, n),
        "price": price,
        "stock_status": rng.choice(["in_stock", "out_of_stock"], n,
                                   p=[0.90, 0.10]),
    })


def make_pages():
    rows, n = [], 1
    for channel in ["web", "app"]:
        for page_type in PAGE_TYPES:
            rows.append({"page_id": page_id(n), "page_type": page_type,
                         "channel": channel})
            n += 1
    return pd.DataFrame(rows)


def make_experiments():
    items = [
        ("checkout_button_color", "2026-01-15", "2026-02-15"),
        ("simplified_checkout", "2026-02-01", "2026-03-15"),
        ("free_shipping_banner", "2026-03-01", "2026-03-31"),
    ]
    return pd.DataFrame([
        {"experiment_id": experiment_id(i), "name": name,
         "start_date": start, "end_date": end}
        for i, (name, start, end) in enumerate(items, 1)
    ])


def write_csv(df, name, out_dir):
    df = df.sort_values(df.columns[0])
    df.to_csv(out_dir / f"{name}.csv", index=False,
              lineterminator="\n", float_format="%.2f")
    print(f"{name}: {len(df)} rows")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=1000)
    parser.add_argument("--out", default="data/starter")
    args = parser.parse_args()

    rng = np.random.default_rng([SEED, 1])
    n_customers = max(50, args.sessions // 4)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(make_customers(rng, n_customers), "customers", out_dir)
    write_csv(make_products(rng), "products", out_dir)
    write_csv(make_pages(), "pages", out_dir)
    write_csv(make_experiments(), "experiments", out_dir)


if __name__ == "__main__":
    main()