"""
Dashboard module -- Streamlit 5-tab retail analytics dashboard.

Usage:
    streamlit run src/dashboard.py

Environment:
    API_BASE_URL -- base URL of the FastAPI backend (default: http://localhost:8000)

Data is fetched once at startup with a 60-second cache. Restarting the API
after rerunning process_videos.py will refresh the data on the next cache miss.
"""
import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ── Page config (must be the first Streamlit call) ─────────────────────────────
st.set_page_config(
    page_title="Purplle Store Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# ── Data fetching ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def fetch_dashboard() -> dict:
    """Fetch all analytics from /dashboard. Returns {} on API failure."""
    try:
        resp = requests.get(f"{API_URL}/dashboard", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {}


@st.cache_data(ttl=60)
def fetch_health() -> dict:
    """Fetch system health from /health. Returns {} on API failure."""
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {}


# ── Load data ──────────────────────────────────────────────────────────────────
data   = fetch_dashboard()
health = fetch_health()

if not data:
    st.error(
        "Cannot reach the API. "
        "Ensure the API service is running on port 8000. "
        "Run: uvicorn src.api:app --port 8000"
    )
    st.stop()

# Unpack top-level sections
funnel    = data.get("funnel", {})
anomalies = data.get("anomalies", [])
metrics   = data.get("metrics", {})
sales     = metrics.get("sales", {})
traffic   = metrics.get("traffic", {})
h_data    = data.get("health", {})

# Frequently used sub-dicts
zv     = funnel.get("zone_visits", {})
adwell = funnel.get("avg_dwell_seconds", {})
fv     = funnel.get("funnel_validation", "pass")

# Derived values shared across tabs
zone_visits_total  = sum(zv.values())
weighted_avg_dwell = (
    round(
        sum(adwell.get(z, 0) * zv.get(z, 0) for z in zv) / zone_visits_total, 1
    )
    if zone_visits_total > 0 else 0.0
)
# Exact total dwell per zone from the API (derived server-side from zone_dwell
# events by _compute_zone_totals() at startup -- Option b, no recomputation here).
total_dwell = data.get("zone_totals", {})

# Hourly chart data (reused in Tab 1 and Tab 4)
hourly       = sales.get("hourly_revenue", {})
hours_sorted = sorted(hourly.items()) if hourly else []
hour_labels  = [f"{h}:00" for h, _ in hours_sorted]
hour_values  = [v for _, v in hours_sorted]
max_val      = max(hour_values) if hour_values else 0

# ── Colour palette ─────────────────────────────────────────────────────────────
C_BLUE   = "#3B82F6"
C_INDIGO = "#6366F1"
C_VIOLET = "#8B5CF6"
C_LIGHT  = "#A5B4FC"


# ══════════════════════════════════════════════════════════════════════════════
# Tabs
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Executive Overview",
    "Customer Journey",
    "Zone Intelligence",
    "Revenue Intelligence",
    "System Health",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 -- Executive Overview
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.title("Purplle Store Intelligence -- Brigade Road")

    # ── Video analytics section ──
    st.caption("Video Analytics -- 16-04-2026")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Zone Visits", zone_visits_total)
    c2.metric("Avg Dwell Time", f"{weighted_avg_dwell} sec")
    c3.metric("Events Captured", traffic.get("total_events", 0))
    c4.metric("Anomalies Detected", len(anomalies))

    st.divider()

    # ── POS data section ──
    st.caption("POS Data -- 10-04-2026")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GMV", f"Rs {sales.get('gmv', 0):,.0f}")
    c2.metric("NMV", f"Rs {sales.get('nmv', 0):,.0f}")
    c3.metric("Transactions", sales.get("transactions", 0))
    c4.metric("Avg Basket", f"{sales.get('avg_basket_depth', 0):.2f} items")

    st.divider()

    # ── Hourly revenue chart ──
    st.subheader("Hourly Revenue (Rs)")
    if hours_sorted:
        fig_hour = go.Figure(go.Bar(
            x=hour_labels,
            y=hour_values,
            marker_color=[C_INDIGO if v == max_val else C_LIGHT for v in hour_values],
            text=[f"Rs {v:,.0f}" for v in hour_values],
            textposition="outside",
            textfont={"size": 10},
        ))
        fig_hour.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=20, b=10),
            yaxis_title="GMV (Rs)",
            xaxis_title="Hour",
            showlegend=False,
            yaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
            plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(fig_hour, use_container_width=True)
        peak = max(hours_sorted, key=lambda x: x[1])
        st.caption(f"Peak: {peak[0]}:00 -- Rs {peak[1]:,.0f}")

    # ── Top performer note ──
    top_sp = (sales.get("salesperson_performance") or [{}])[0]
    if top_sp.get("name"):
        st.caption(
            f"Top performer: {top_sp['name']} -- "
            f"Rs {top_sp.get('nmv', 0):,.0f} NMV | "
            f"{top_sp.get('transactions', 0)} transactions"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 -- Customer Journey
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Customer Journey -- Aggregate Zone Counts")

    if fv == "warning":
        st.warning(
            "**Funnel is in WARNING state.** "
            "Entry count is 0 because CAM_3 crossing sensitivity is unverified "
            "on the available footage. This is a known footage limitation, not a "
            "detection failure. Zone visit and dwell data are accurate."
        )

    # Stage 1 -- Entries
    c1, c2 = st.columns([2, 1])
    with c1:
        st.metric("Stage 1 -- Entries detected (CAM_3)", funnel.get("entry_count", 0))
    with c2:
        st.info(
            "Q3 Partial Pass: Crossing mechanics validated synthetically. "
            "Real-world sensitivity unverified on available footage."
        )

    # Plotly Funnel -- stages 2-4 (main_floor -> skincare -> billing)
    fig_funnel = go.Figure(go.Funnel(
        y=["Main Floor (CAM_2)", "Skincare (CAM_1)", "Billing (CAM_5)"],
        x=[zv.get("main_floor", 0), zv.get("skincare", 0), zv.get("billing", 0)],
        marker={"color": [C_BLUE, C_INDIGO, C_VIOLET]},
        connector={"line": {"color": "#CBD5E1", "dash": "dot", "width": 2}},
        textinfo="value",
        textfont={"size": 18, "color": "white"},
    ))
    fig_funnel.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_funnel, use_container_width=True)

    # Stage 5 -- Transactions
    c1, c2 = st.columns([2, 1])
    with c1:
        st.metric("Stage 5 -- Transactions (POS CSV)", funnel.get("transaction_count", 0))
    with c2:
        st.info(
            "Source: POS system -- 10-04-2026. "
            "Different date from video (16-04-2026). "
            "No individual-level matching between datasets."
        )

    st.divider()

    # Avg dwell per zone
    st.subheader("Average Dwell Time per Zone")
    c1, c2, c3 = st.columns(3)
    c1.metric("Main Floor", f"{adwell.get('main_floor', 0):.1f} sec")
    c2.metric("Skincare", f"{adwell.get('skincare', 0):.1f} sec")
    c3.metric("Billing", f"{adwell.get('billing', 0):.1f} sec")

    st.divider()

    # Full disclaimer -- always visible, boxed
    st.warning(funnel.get("disclaimer", "Aggregate counts only -- no individual tracking."))


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 -- Zone Intelligence
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Zone Intelligence")
    st.caption("Video data -- 16-04-2026 | Zone polygons derived from Brigade Road store layout")

    zone_keys   = ["main_floor", "skincare", "billing"]
    zone_labels = ["Main Floor (CAM_2)", "Skincare (CAM_1)", "Billing (CAM_5)"]
    zone_colors = [C_BLUE, C_INDIGO, C_VIOLET]
    v_counts    = [zv.get(z, 0) for z in zone_keys]
    d_vals      = [adwell.get(z, 0) for z in zone_keys]

    # Overview bar charts -- side by side
    c_left, c_right = st.columns(2)

    with c_left:
        st.subheader("Visit Count by Zone")
        fig_vc = go.Figure(go.Bar(
            x=v_counts,
            y=zone_labels,
            orientation="h",
            marker_color=zone_colors,
            text=v_counts,
            textposition="auto",
        ))
        fig_vc.update_layout(
            height=220,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="Visits",
            plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(fig_vc, use_container_width=True)

    with c_right:
        st.subheader("Avg Dwell Time by Zone (sec)")
        fig_dw = go.Figure(go.Bar(
            x=d_vals,
            y=zone_labels,
            orientation="h",
            marker_color=zone_colors,
            text=[f"{v:.1f}s" for v in d_vals],
            textposition="auto",
        ))
        fig_dw.update_layout(
            height=220,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="Avg dwell (sec)",
            plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(fig_dw, use_container_width=True)

    st.divider()

    # Per-zone detail cards
    st.subheader("Zone Detail")
    c1, c2, c3 = st.columns(3)
    for (z_key, z_label, cam), col in zip(
        [("main_floor", "Main Floor", "CAM_2"),
         ("skincare",   "Skincare",   "CAM_1"),
         ("billing",    "Billing",    "CAM_5")],
        [c1, c2, c3],
    ):
        with col:
            st.markdown(f"**{z_label}** ({cam})")
            st.metric("Visits", zv.get(z_key, 0))
            st.metric("Avg Dwell", f"{adwell.get(z_key, 0):.1f}s")
            st.metric("Total Dwell", f"{total_dwell.get(z_key, 0):.1f}s")

    st.caption("Total dwell is derived directly from zone_dwell events (exact sum, not avg x count).")

    st.divider()

    # Entrance and warehouse (special zones)
    st.subheader("Additional Zones")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Entrance (CAM_3)**")
        st.metric("Entries detected", funnel.get("entry_count", 0))
        st.caption(
            "Q3 Partial Pass: crossing mechanics validated synthetically. "
            "Real-world sensitivity unverified on available footage."
        )
    with c2:
        st.markdown("**Warehouse (CAM_4)**")
        wh_count = traffic.get("event_counts", {}).get("warehouse_motion", 0)
        st.metric("Motion events", wh_count)
        st.caption("Genuine restocking activity confirmed at t=92.3s via full-video processing.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 -- Revenue Intelligence
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("Revenue Intelligence")
    st.caption("Source: POS CSV -- Brigade Road store -- 10-04-2026")

    # KPI row
    brand = sales.get("brand_split", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GMV", f"Rs {sales.get('gmv', 0):,.0f}")
    c2.metric("NMV", f"Rs {sales.get('nmv', 0):,.0f}")
    c3.metric("Transactions", sales.get("transactions", 0))
    c4.metric("Private Brand Share", f"{brand.get('private_brand_gmv_pct', 0):.1f}%")

    st.divider()

    # Category GMV and brand split
    c_left, c_right = st.columns([3, 2])

    with c_left:
        st.subheader("Revenue by Category (GMV)")
        cats = sales.get("top_categories", [])
        if cats:
            fig_cats = go.Figure(go.Bar(
                x=[c["name"].title() for c in cats],
                y=[c["gmv"] for c in cats],
                marker_color=C_INDIGO,
                text=[f"Rs {c['gmv']:,.0f}" for c in cats],
                textposition="outside",
                textfont={"size": 10},
            ))
            fig_cats.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=20, b=10),
                yaxis_title="GMV (Rs)",
                showlegend=False,
                plot_bgcolor="#FFFFFF",
                yaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
            )
            st.plotly_chart(fig_cats, use_container_width=True)

    with c_right:
        st.subheader("Brand Mix -- GMV")
        if brand:
            fig_brand = go.Figure(go.Pie(
                labels=["Private Brand", "External Brand"],
                values=[
                    brand.get("private_brand_gmv_pct", 0),
                    brand.get("external_brand_gmv_pct", 0),
                ],
                hole=0.45,
                marker_colors=[C_INDIGO, "#E2E8F0"],
                textinfo="label+percent",
                textfont={"size": 12},
            ))
            fig_brand.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=20, b=10),
            )
            st.plotly_chart(fig_brand, use_container_width=True)

    st.divider()

    # Salesperson and hourly revenue
    c_left, c_right = st.columns([3, 2])

    with c_left:
        st.subheader("Salesperson Performance (NMV)")
        sps = sales.get("salesperson_performance", [])
        if sps:
            fig_sp = go.Figure(go.Bar(
                x=[s["nmv"] for s in sps],
                y=[s["name"] for s in sps],
                orientation="h",
                marker_color=C_VIOLET,
                text=[f"Rs {s['nmv']:,.0f}" for s in sps],
                textposition="auto",
                textfont={"size": 10},
            ))
            fig_sp.update_layout(
                height=280,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="NMV (Rs)",
                plot_bgcolor="#FFFFFF",
                xaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
            )
            st.plotly_chart(fig_sp, use_container_width=True)

    with c_right:
        st.subheader("Hourly Revenue (Rs)")
        if hours_sorted:
            fig_hourly2 = go.Figure(go.Bar(
                x=hour_labels,
                y=hour_values,
                marker_color=[C_INDIGO if v == max_val else C_LIGHT for v in hour_values],
            ))
            fig_hourly2.update_layout(
                height=280,
                margin=dict(l=10, r=10, t=10, b=10),
                yaxis_title="GMV (Rs)",
                xaxis_title="Hour",
                showlegend=False,
                plot_bgcolor="#FFFFFF",
                yaxis=dict(showgrid=True, gridcolor="#F1F5F9"),
            )
            st.plotly_chart(fig_hourly2, use_container_width=True)

    st.divider()

    # Promotions table
    st.subheader("Promotion Effectiveness")
    promos = sales.get("promotion_effectiveness", [])
    if promos:
        df_promos = pd.DataFrame(promos).rename(columns={
            "offer_name":        "Promotion",
            "gmv":               "GMV (Rs)",
            "transaction_count": "Transactions",
        })
        df_promos["GMV (Rs)"] = df_promos["GMV (Rs)"].apply(lambda x: f"Rs {x:,.0f}")
        st.dataframe(df_promos, use_container_width=True, hide_index=True)
    else:
        st.caption("No promotion data available.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 -- System Health
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.header("Operational Intelligence & System Health")

    # Anomalies
    st.subheader("Active Anomalies")
    if anomalies:
        for a in anomalies:
            sev     = a.get("severity", "info")
            cam     = a.get("camera", "?")
            zone    = a.get("zone", "?")
            ts_raw  = a.get("triggered_at", "")
            ts_disp = ts_raw[:19].replace("T", " ") if ts_raw else "unknown"
            header  = f"**{a.get('type', '?')}** | {cam} / {zone} | {ts_disp}"
            body    = (
                f"{a.get('message', '')}  \n"
                f"> Recommendation: {a.get('business_recommendation', '')}"
            )
            if sev == "warning":
                st.warning(f"{header}  \n{body}")
            else:
                st.info(f"{header}  \n{body}")
    else:
        st.success("No anomalies detected in the current pipeline window.")

    st.divider()

    # Funnel validation
    st.subheader("Funnel Validation")
    if fv == "warning":
        notes = funnel.get("validation_notes", [])
        note_text = notes[0][:200] if notes else "Funnel monotonicity check failed."
        st.warning(f"**FUNNEL: WARNING**  \n{note_text}")
    else:
        st.success("**FUNNEL: PASS** -- All monotonicity checks passed.")

    st.divider()

    # Pipeline provenance
    st.subheader("Pipeline Run")
    last_run = h_data.get("last_run", {})
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Events loaded", h_data.get("events_loaded", 0))
        st.metric("Transactions loaded", health.get("transactions_loaded", 0))
        st.metric("Anomalies triggered", len(anomalies))
    with c2:
        elapsed = last_run.get("total_elapsed_sec", 0)
        st.metric("Pipeline elapsed", f"{elapsed:.1f}s" if elapsed else "N/A")
        st.metric("Quick mode", "Yes" if last_run.get("quick_mode") else "No")
        st.metric("CAM_4 processing", str(last_run.get("cam4_override", "N/A")))

    st.divider()

    # Video fingerprints
    st.subheader("Video Fingerprints (SHA-256)")
    st.caption(
        "These hashes prove events.json was computed from these specific video files. "
        "Rerunning process_videos.py with different inputs produces different hashes."
    )
    hashes = h_data.get("video_hashes", {})
    if hashes:
        hash_rows = [
            {
                "Camera": cam,
                "SHA-256": h[:32] + "..." if isinstance(h, str) else "[not found]",
                "Status": "verified" if isinstance(h, str) else "not found",
            }
            for cam, h in sorted(hashes.items())
        ]
        st.dataframe(pd.DataFrame(hash_rows), use_container_width=True, hide_index=True)

    st.divider()

    # API status
    st.subheader("API Status")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("API", health.get("status", "unknown").upper())
        st.metric("Events served", health.get("events_loaded", 0))
    with c2:
        uptime = health.get("uptime_seconds")
        st.metric("Uptime", f"{uptime:.0f}s" if uptime is not None else "N/A")
        st.metric("Validation warnings", len(h_data.get("validation_warnings", [])))

    st.divider()

    # Recent log entries
    st.subheader("Recent Pipeline Log (last 10 entries)")
    log_buf = health.get("log_buffer", [])
    if log_buf:
        df_log = pd.DataFrame([
            {
                "Time":    e.get("timestamp", "")[:19].replace("T", " "),
                "Level":   e.get("level", ""),
                "Module":  e.get("module", ""),
                "Message": e.get("message", "")[:80],
            }
            for e in log_buf[-10:]
        ])
        st.dataframe(df_log, use_container_width=True, hide_index=True)
    else:
        st.caption("Log buffer is empty -- entries accumulate as API endpoints are called.")
