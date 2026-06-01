"""
CSV analytics — revenue intelligence from POS transaction data.

Data source: data/Brigade_Bangalore_10_April_26.csv (date: 10-04-2026).
Separate from video data (16-04-2026). No individual-level matching between
datasets is performed or claimed anywhere in the system.

Mandatory metrics: transactions, GMV, NMV, top categories by revenue,
category distribution, average basket depth.

Enhancement metrics: salesperson performance (by NMV), Private Brand vs
External Brand GMV split, promotion effectiveness, hourly revenue curve.

Note on brand_type: the CSV contains 14 distinct brand_type values.
"PB" is Private Brand; all other values are External Brand.

This module does NOT process video events. It reads only the POS CSV file
and returns a structured dict of revenue metrics.
"""
import os

import pandas as pd

from src.utils import get_logger

_log = get_logger(__name__)


def run_csv_analytics(csv_path: str) -> dict:
    """Read the POS CSV and return structured revenue intelligence metrics.

    Args:
        csv_path: Absolute path to the Brigade Bangalore CSV file.

    Returns:
        Dict with source tag, mandatory metrics, and enhancement metrics.
        All monetary values are in original currency units (INR, rounded to 2dp).

    Raises:
        FileNotFoundError: If csv_path does not exist.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    _log.info("csv_analytics: loaded %d rows from %s", len(df), os.path.basename(csv_path))

    total_gmv = float(df["GMV"].sum())

    # ── Mandatory metrics ────────────────────────────────────────────────────

    transactions    = int(df["order_id"].nunique())
    gmv             = round(total_gmv, 2)
    nmv             = round(float(df["NMV"].sum()), 2)
    avg_basket_depth = round(
        float(df.groupby("order_id")["qty"].sum().mean()), 2
    )

    # Top categories by GMV (dep_name), sorted descending
    cat_perf = (
        df.groupby("dep_name", as_index=False)
          .agg(gmv=("GMV", "sum"), transaction_count=("order_id", "nunique"))
          .sort_values("gmv", ascending=False)
    )
    top_categories = [
        {
            "name":              row["dep_name"],
            "gmv":               round(float(row["gmv"]), 2),
            "transaction_count": int(row["transaction_count"]),
        }
        for _, row in cat_perf.iterrows()
    ]
    category_distribution = {
        row["dep_name"]: round(float(row["gmv"]) / total_gmv * 100, 2)
        for _, row in cat_perf.iterrows()
    }

    # ── Enhancement metrics ──────────────────────────────────────────────────

    # Salesperson performance ranked by NMV
    sp_perf = (
        df.groupby("salesperson_name", as_index=False)
          .agg(nmv=("NMV", "sum"), transactions=("order_id", "nunique"))
          .sort_values("nmv", ascending=False)
    )
    salesperson_performance = [
        {
            "name":         row["salesperson_name"],
            "nmv":          round(float(row["nmv"]), 2),
            "transactions": int(row["transactions"]),
        }
        for _, row in sp_perf.iterrows()
    ]

    # Private Brand vs External Brand GMV split
    # brand_type == "PB" is Private Brand; all other values are External Brand
    pb_gmv  = float(df[df["brand_type"] == "PB"]["GMV"].sum())
    ext_gmv = total_gmv - pb_gmv
    brand_split = {
        "private_brand_gmv_pct":  round(pb_gmv  / total_gmv * 100, 2),
        "external_brand_gmv_pct": round(ext_gmv / total_gmv * 100, 2),
    }

    # Promotion effectiveness — rows with a non-empty offer_name, by GMV
    promo_df = df[
        df["offer_name"].notna()
        & (df["offer_name"].astype(str).str.strip() != "")
    ]
    promo_perf = (
        promo_df.groupby("offer_name", as_index=False)
                .agg(gmv=("GMV", "sum"), transaction_count=("order_id", "nunique"))
                .sort_values("gmv", ascending=False)
    )
    promotion_effectiveness = [
        {
            "offer_name":        row["offer_name"],
            "gmv":               round(float(row["gmv"]), 2),
            "transaction_count": int(row["transaction_count"]),
        }
        for _, row in promo_perf.iterrows()
    ]

    # Hourly revenue curve — order_time is HH:MM:SS; key is zero-padded hour
    hours = pd.to_datetime(df["order_time"], format="%H:%M:%S").dt.hour
    hourly = df.assign(_hour=hours).groupby("_hour")["GMV"].sum().sort_index()
    hourly_revenue = {f"{int(h):02d}": round(float(v), 2) for h, v in hourly.items()}

    _log.info(
        "csv_analytics complete: transactions=%d gmv=%.2f nmv=%.2f categories=%d",
        transactions, gmv, nmv, len(top_categories),
    )

    return {
        "source":                  "pos_csv_10-04-2026",
        "transactions":            transactions,
        "gmv":                     gmv,
        "nmv":                     nmv,
        "top_categories":          top_categories,
        "category_distribution":   category_distribution,
        "avg_basket_depth":        avg_basket_depth,
        "salesperson_performance": salesperson_performance,
        "brand_split":             brand_split,
        "promotion_effectiveness": promotion_effectiveness,
        "hourly_revenue":          hourly_revenue,
    }
