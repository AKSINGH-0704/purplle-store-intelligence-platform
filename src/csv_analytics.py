"""
CSV analytics module — revenue intelligence from POS transaction data.

Responsibilities (Phase 3):
Data source: data/Brigade_Bangalore_10_April_26.csv (date: 10-04-2026).
This dataset is separate from video data (16-04-2026). No individual-level
matching between datasets is performed or claimed.

Core metrics (mandatory):
- Total transaction count (unique order_id values)
- Total GMV and NMV
- Top categories by revenue (group by dep_name, sum GMV)
- Category distribution by dep_name
- Average basket depth (mean qty per order_id)

Enhancement metrics (implement if time allows; cut first if behind schedule):
- Salesperson performance ranking by NMV (group by salesperson_name, sum NMV)
- Private Brand (PB) vs External Brand revenue split (group by brand_type)
- Promotion effectiveness (group by offer_name, sum GMV)
- Time-of-day revenue curve (group order_time by hour, count orders)

Return a structured dict with clearly labelled source field:
  {"source": "pos_csv_10-04-2026", "transactions": ..., "gmv": ..., ...}
"""
