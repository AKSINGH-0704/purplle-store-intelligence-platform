# PURPLLE STORE INTELLIGENCE PLATFORM — FINAL MASTER PLAN

---

## 1. FOUNDATIONAL TRUTH

You are building a Retail Intelligence Platform, not a CCTV detection project. Every design decision passes through this filter: will a judge see this in under 10 minutes and think this person built a product?

The system answers three business questions:

- How many customers came, where did they go, how long did they stay?
- What did the store sell, which categories performed, what was the revenue, who sold it?
- What operational issues occurred and where?

Computer vision is a component. Business logic is the product.

---

## 2. GROUND TRUTH — WHAT YOU HAVE

### 2.1 Video Assets

Five MP4 files from 16-04-2026. CAM 1 and CAM 3 are approximately 1.76GB and 1.86GB respectively. These are large files. Processing time is real and must be tested before submission.

| Camera | Zone | Intelligence Layer | Detection Method |
|--------|------|--------------------|-----------------|
| CAM 1 | Skincare / Bath | Customer Intelligence | YOLOv8-nano |
| CAM 2 | Main Floor / Circulation | Customer Intelligence | YOLOv8-nano |
| CAM 3 | Entrance / Exit | Customer Intelligence (Primary) | YOLOv8-nano |
| CAM 4 | Warehouse / Storage | Operational Intelligence ONLY | Background subtraction (OpenCV MOG2) |
| CAM 5 | Billing Counter | Customer + Operational | YOLOv8-nano |

CAM 4 does not use YOLO. Background subtraction via OpenCV is CPU-instant, requires no model weights, and is fully sufficient for detecting warehouse motion events. This is an architectural decision documented in CHOICES.md.

### 2.2 Transaction Data (CSV)

Brigade_Bangalore_10_April_26.csv — POS data from 10-04-2026. Different date than video.

Key columns: order_id, order_time, order_date, customer_number, product_name, dep_name, sub_category, qty, GMV, NMV, salesperson_id, employee_code, salesperson_name, brand_type, offer_name, coupon_code.

### 2.3 Store Layout

Brigade_Road_Store_layout.xlsx — contains floorplan images and zone mapping. Source for zones.json. Must be inspected in Phase 0 to determine if machine-readable coordinates exist or if manual polygon extraction from video frames is needed.

### 2.4 Date Mismatch

Video is 16-04, CSV is 10-04. Different dates, no unique customer ID across datasets. These are treated as separate intelligence layers. No individual-level matching is claimed anywhere in the system.

---

## 3. CORE DESIGN PRINCIPLES

### Principle 1 — Reviewer Experience First

When a judge runs docker compose up, they see container healthy, events loaded, API ready, and dashboard accessible within 30 seconds. If startup takes longer, many reviewers will assume the system is broken. This is non-negotiable. Every other design decision is filtered through it.

### Principle 2 — Separate Batch Processing from Live Serving

Precomputed events.json loads at startup for instant API response. process_videos.py is a separate command judges can optionally run to see computation happening. This is how production systems work. This is also the integrity defence.

### Principle 3 — Aggregate Metrics Only

No cross-camera person tracking. No person-to-purchase matching. Zone-level aggregate counts are honest, defensible, and valuable business intelligence.

### Principle 4 — Store Layout-Aware Intelligence as Headline Feature

zones.json is a first-class system component derived from the store layout file. This makes the USP tangible. Most contestants will ignore the layout file. You will have a dedicated config file that drives the entire detection pipeline.

### Principle 5 — Honest Limitations Win Trust

Acknowledging what you cannot do scores better than overclaiming what you can. Judges have seen hundreds of overconfident submissions.

### Principle 6 — Decisions Log from Day One

Every non-obvious decision is recorded in a running text file immediately when made. CHOICES.md is assembled from this log, not written from memory at the end. This is the single biggest quality difference between a 13/15 and an 8/15 on engineering thinking.

---

## 4. SYSTEM ARCHITECTURE

```
Zone Configuration (zones.json) + System Config (config.json)
        |
        v
Video Input (5 MP4s) + CSV (POS data)
        |
        v
Detection Layer
(YOLOv8-nano for CAM 1,2,3,5 | Background subtraction with min contour filter for CAM 4)
        |
        v
Tracking Layer
(Centroid tracker or ByteTrack within-camera only, no cross-camera)
(Distance threshold: 80px at 640x360, configurable)
        |
        v
Zone Event Layer
(Entry line crossings with direction vector | Zone dwell | Motion events)
(Dwell merge rule: merge only if no other active track in zone)
        |
        v
Validation Layer
(Funnel monotonicity check | Sanity checks logged to System Health)
        |
        v
Business Logic Layer
(Aggregate funnel | Mandatory staff filtering | 5 anomaly rules | CSV analytics)
        |
        v
Intelligence Layer
(Traffic metrics | Revenue metrics | Operational metrics — kept separate)
        |
        v
API Layer (FastAPI service) + Dashboard Layer (Streamlit service)
(Two Docker services communicating via internal network)
(Dashboard uses API_BASE_URL environment variable for service discovery)
```

---

## 5. ZONES.JSON — FIRST-CLASS COMPONENT

This file is the bridge between the store layout Excel and the detection code. Created in Phase 0 after opening the Excel file. Contains polygon coordinates for every zone in pixel space for each camera.

Structure:

```json
{
  "CAM_1": {
    "zone": "skincare",
    "polygon": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
    "intelligence_layer": "customer"
  },
  "CAM_2": {
    "zone": "main_floor",
    "polygon": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
    "intelligence_layer": "customer"
  },
  "CAM_3": {
    "zone": "entrance",
    "entry_line": [[x1,y1], [x2,y2]],
    "entry_direction_vector": [dx, dy],
    "intelligence_layer": "customer"
  },
  "CAM_4": {
    "zone": "warehouse",
    "polygon": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
    "intelligence_layer": "operational",
    "detection_method": "background_subtraction"
  },
  "CAM_5": {
    "zone": "billing",
    "polygon": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
    "intelligence_layer": "customer_and_operational"
  }
}
```

The entry_direction_vector for CAM 3 defines which direction across the line counts as entry versus exit. This is determined in Phase 2 by inspecting the actual camera angle: from street side to store interior is entry, the reverse is exit.

---

## 6. CONFIG.JSON — SYSTEM CONFIGURATION

All tunable parameters are centralised in a single configuration file. No magic numbers in code.

```json
{
  "max_frames_per_camera": 1000,
  "frame_skip": 5,
  "detection_resolution": [640, 360],
  "confidence_threshold": 0.5,
  "tracker_distance_threshold": 80,
  "warehouse_motion_threshold": 500,
  "dwell_merge_window_seconds": 30,
  "zone_abandonment_window_seconds": 300,
  "repeat_visit_threshold": 3,
  "min_dwell_for_visit_seconds": 10,
  "queue_occupancy_threshold": 2,
  "queue_duration_threshold_seconds": 300,
  "staff_filter_enabled": true
}
```

Rationale for key values:

- tracker_distance_threshold at 80 pixels: at 640x360 with frame skip 5, a walking person moves 15-30px between processed frames. 80px catches normal and fast movement without merging nearby people. Configurable for different store layouts.
- warehouse_motion_threshold at 500 square pixels: filters out lighting flicker noise (small scattered pixels) while catching real human movement (large contiguous blobs). OpenCV MOG2 adapts to slow lighting changes but is sensitive to sudden shifts. The minimum contour area prevents false positives from flickering lights or opening doors.
- min_dwell_for_visit_seconds at 10: prevents 2-second pass-throughs from counting as zone visits in Anomaly 5 (repeat zone visits). Only genuine browsing behaviour is counted.

---

## 7. ENTRY LINE CROSSING LOGIC

The entire funnel depends on counting entry crossings at CAM 3. The detection method is centroid crossing.

How it works: a person's bounding box centroid is tracked across consecutive processed frames. If the centroid moves from one side of the entry_line to the other between two consecutive frames, a crossing event is generated. The entry_direction_vector determines which direction is entry and which is exit.

Why centroid crossing over bounding box crossing: on CPU with frame skip 5, centroid crossing is more reliable. Fast crossings that happen entirely within skipped frames are missed by either method, but centroid crossing catches the majority of normal-speed crossings.

The entry_line coordinates and entry_direction_vector are defined in zones.json and validated in Phase 2 by testing on at least 10 actual crossings from the CAM 3 video.

---

## 8. TRACKING STRATEGY

### 8.1 Primary: Centroid Tracker (Recommended)

A lightweight centroid tracker with zero external dependencies. Maintains a dictionary of active detections, matches new detections to existing ones by minimum Euclidean distance within the configurable tracker_distance_threshold (default 80px at 640x360).

Validation requirement: in Phase 2, visually verify that a single walking person maintains one consistent ID for at least 20 consecutive processed frames. Record the result in the decisions log.

### 8.2 Fallback: ByteTrack (If Validated)

ByteTrack may be used if it passes the Phase 2 reliability test: run on the actual local machine across at least 100 consecutive frames of a walking person. If track IDs reset more than 3 times per minute on a single visible person, ByteTrack is unreliable in the environment.

ByteTrack has installation friction on CPU-only environments — it requires specific versions of scipy, lap or lapjv, and sometimes cython compilation. Inside Docker without a clean dependency chain, it can initialise but produce garbage track IDs silently.

CHOICES.md entry if centroid tracker is chosen: "Evaluated ByteTrack but implemented lightweight centroid tracker for reliability in CPU-only evaluation environments. Centroid tracking has no external dependency chain and produces consistent IDs sufficient for zone-level analytics."

### 8.3 Dwell Time Merge Rule

When a track disappears due to occlusion and reappears, the tracking system may assign a new ID. This splits a single person's visit into two sessions with artificially short dwell times.

Corrected merge rule: if a new track appears in the same zone within 30 seconds of a previous track ending, AND the zone currently has no other active tracks at that moment, merge the sessions. The "no other active track" condition prevents merging two different people who happen to visit the same zone in quick succession.

CHOICES.md entry: "Dwell time merge accounts for track ID reassignment after occlusion. Sessions are only merged when no other active tracks exist in the zone, preventing false consolidation of different visitors."

---

## 9. CAM 4 — BACKGROUND SUBTRACTION

Instead of running YOLO on warehouse footage, OpenCV's MOG2 background subtractor detects motion events. When significant motion is detected, a warehouse activity event is generated. Multiple consecutive motion frames constitute a restocking event.

Sensitivity calibration: a minimum contour area threshold of 500 square pixels at 640x360 resolution filters out lighting flicker noise while catching real human movement. This threshold is configurable via warehouse_motion_threshold in config.json.

CHOICES.md entry: "CAM 4 uses background subtraction rather than person detection because the warehouse zone requires activity detection, not customer identification. Background subtraction is faster, lighter, and more appropriate for the task. A minimum contour area threshold filters lighting-induced false positives, retaining only motion events consistent with human presence."

---

## 10. INTEGRITY DEFENCE — VIDEO HASH FINGERPRINTING

When process_videos.py runs, it computes a SHA256 hash of every video file in the inputs directory and stores it alongside the generated events.json in a file called video_hashes.json.

The System Health tab displays this hash. This proves the events.json was generated from specific video files, not fabricated. If a judge replaces video files and runs process_videos.py, a new hash is computed, events are regenerated, and API metrics change.

The README documents this under a section called How Integrity Is Verified.

---

## 11. STAFF FILTERING HEURISTIC (Applied by Default)

Staff filtering is applied by default to the entry count. In a beauty retail store like Purplle Brigade Road, there are likely 8-15 staff members. Over a full day of footage, staff walking through the entrance account for a significant portion of crossings. An unfiltered count inflates the funnel top and deflates conversion rate. The filtering is presented as a heuristic, not a guarantee — judges know perfect staff detection is not feasible without badges or face recognition.

Three heuristic rules (all CAM 3-local, no cross-camera dependency):

1. A track detected crossing the entry line in both directions more than 3 times within 30 minutes — likely staff making multiple trips in and out. This uses CAM 3 crossing data only and requires no cross-camera identity.
2. Person at billing desk area (CAM 5) without entering from the main floor direction — likely staff stationed at checkout.
3. Person already positioned inside the store in the first frame of the recording — likely staff on duty at opening.

If any rule matches, the track is excluded from customer metrics and counted separately.

CHOICES.md entry: "Staff detection uses entry line crossing patterns and positional heuristics only. Cross-camera identity is not available in the aggregate tracking architecture, so all staff rules operate within individual camera views."

A "Staff Movements Detected" count is shown in the System Health tab, displaying how many crossings were filtered. This transparency strengthens the submission.

---

## 12. THREE INTELLIGENCE LAYERS

### Layer 1 — Customer Intelligence (from video)

- Total entry and exit counts (CAM 3, staff-filtered via heuristic)
- Per-zone visit counts (CAM 1, 2, 5)
- Average dwell time per zone (with merge rule applied)
- Peak traffic hours
- Zone popularity ranking

### Layer 2 — Revenue Intelligence (from CSV only)

Core metrics (implement first, these are essential):

- Total transactions
- Total GMV and NMV
- Top categories by revenue
- Category distribution by dep_name
- Average basket depth (avg qty per order)

Enhancement metrics (implement only if time allows, cut these first if behind schedule):

- Salesperson performance ranking by NMV
- Private Brand (PB) versus External Brand revenue split
- Promotion effectiveness (which offer_name drove most GMV)
- Time-of-day revenue curve (orders grouped by hour of order_time)

### Layer 3 — Operational Intelligence (CAM 4 + CAM 5)

- Warehouse activity detection timeline (CAM 4, background subtraction)
- Restocking events (sustained motion in warehouse zone)
- Queue length at checkout (CAM 5 occupancy exceeding threshold)
- Queue duration alerts
- Crowding alerts by zone

These three layers are shown separately on the dashboard and returned separately from the API. No attempt is made to claim causation between Layer 1 and Layer 2.

---

## 13. AGGREGATE FUNNEL DEFINITION

The funnel uses aggregate zone counts, not person-level cross-camera tracking.

```
CAM 3 (Entrance):     Entry crossings detected (staff-filtered)
CAM 2 (Main Floor):   Zone visits detected (dwell > 10 seconds)
CAM 1 (Skincare):     Zone visits detected (dwell > 10 seconds)
CAM 5 (Billing):      Checkout interactions detected
CSV:                   Transactions recorded (separate dataset, different date)
```

No claim is made that Person A entered and then purchased. The story is: the store received 87 entries, traffic through skincare was 45 visits, 40 checkout interactions were observed, and sales data shows 25 transactions during a comparable time window.

### Funnel Monotonicity Validation

After computing funnel counts, a post-processing step checks logical consistency:

- Checkout count from CAM 5 should not significantly exceed entry count from CAM 3.
- Main floor visits from CAM 2 should generally be higher than or comparable to skincare visits from CAM 1 (main floor is between entrance and skincare).

If either check fails, a warning is logged and visible in System Health tab. Judges will see this transparency as a sign of engineering maturity.

---

## 14. TRAFFIC-SALES ALIGNMENT

What was previously called "Conversion Proxy" is named "Traffic-Sales Alignment (Experimental)." This wording is accurate. Conversion implies a proven causal relationship. Alignment is an observational framing.

This section sits in its own clearly separated panel on the dashboard Tab 2, visually distinct from both Traffic Metrics and Sales Metrics. It carries a visible note: "Traffic from 16-04-2026, sales from 10-04-2026. Datasets are separate. Alignment is illustrative only."

---

## 15. FIVE ANOMALY DEFINITIONS

All five anomalies use video data only. No anomaly crosses datasets.

### Anomaly 1 — Extended Zone Occupancy

A track dwelling in any single product zone (CAM 1 skincare or CAM 5 billing) for longer than 15 minutes continuously. This is computed entirely within one camera — no cross-camera proof of downstream activity is required. Recommendation: Customer may need assistance or may be experiencing decision fatigue. Review staff deployment in this zone.

### Anomaly 2 — Queue Buildup at Billing

CAM 5 occupancy count exceeds queue_occupancy_threshold (default 2) persons simultaneously for more than queue_duration_threshold_seconds (default 300 seconds) continuously. Implementation: if person count in billing zone polygon exceeds the threshold at the same frame, flag as queue event. Recommendation: Consider opening additional checkout lane.

### Anomaly 3 — Unusual Warehouse Activity

CAM 4 background subtraction detects significant motion (contour area exceeding warehouse_motion_threshold) outside a configurable expected time window. Recommendation: Investigate unscheduled warehouse access.

### Anomaly 4 — Zone Abandonment

Entry detected at CAM 3 but no subsequent zone visit detected at CAM 1 or CAM 2 within zone_abandonment_window_seconds (default 300 seconds). Customer entered and left immediately. Recommendation: Review entrance experience, signage, or store opening state.

Important boundary guard: this anomaly is computed only for entries detected in the first 70% of the processing window. Entries near the end of the window are excluded because their subsequent zone visit may have occurred after the processing window ended, which would cause false positives. CHOICES.md entry: "Zone abandonment is computed only for entries in the first 70% of the processing window to prevent false positives from truncated observation."

### Anomaly 5 — Repeat Zone Visits

A track that enters the same product zone more than repeat_visit_threshold (default 3) times within a single session, where each visit requires minimum dwell of min_dwell_for_visit_seconds (default 10 seconds). Two-second pass-throughs do not count. This isolates genuine repeated browsing behaviour without converting. Recommendation: Customer may be undecided. Review product display and pricing in this zone.

Each anomaly returns a business_recommendation field in the API response and includes a triggered_at timestamp from actual computation to prove it was dynamically generated.

---

## 16. API CONTRACTS

```
GET /health
Returns:
{
  "status": "healthy",
  "timestamp": "ISO8601",
  "events_loaded": 1523,
  "transactions_loaded": 156,
  "uptime_seconds": 234,
  "video_hashes": {"CAM_1": "abc123...", "CAM_3": "def456..."},
  "last_processing_time_seconds": 1394,
  "config": { ...loaded config.json values... }
}

GET /metrics
Returns:
{
  "traffic": {
    "total_entries": 87,
    "total_exits": 83,
    "avg_dwell_seconds": 320,
    "peak_hour": "16:00-17:00",
    "zone_visits": {"skincare": 45, "main_floor": 60, "billing": 40},
    "staff_filtered_count": 12,
    "source": "video_detection_16-04-2026"
  },
  "sales": {
    "transactions": 25,
    "gmv": 12500,
    "nmv": 9800,
    "top_categories": [...],
    "avg_basket_depth": 2.3,
    "source": "pos_csv_10-04-2026"
  },
  "operations": {
    "queue_alerts": [...],
    "warehouse_activity_events": 8,
    "crowding_events": 2
  }
}

GET /funnel
Returns:
{
  "entry_count": 87,
  "zone_visits": {"main_floor": 60, "skincare": 45, "billing": 40},
  "transaction_count": 25,
  "funnel_validation": "pass",
  "disclaimer": "Aggregate zone counts only. No person-level matching. Traffic and sales are from different dates."
}

GET /anomalies
Returns:
[
  {
    "type": "queue_buildup",
    "severity": "warning",
    "message": "Billing zone occupancy exceeded 2 persons for 8 continuous minutes",
    "business_recommendation": "Consider opening additional checkout lane",
    "triggered_at": "2026-04-16T16:42:00Z"
  }
]

GET /zone_metrics/{zone}
Returns per-zone stats including visit count, average dwell, peak time. Validates zone name against known zones (entrance, skincare, main_floor, billing, warehouse). Returns HTTP 404 with {"error": "Zone not found", "valid_zones": ["entrance", "skincare", "main_floor", "billing", "warehouse"]} for invalid zone names. This prevents 500 errors from typos and shows API robustness.

GET /events/sample
Returns 10 raw events from events.json showing actual timestamped, structured events with frame numbers, zone names, track IDs, and confidence scores. This endpoint costs 10 lines of code and is extremely high value — when a judge wants to verify events are real and dynamically computed, they see the raw pipeline output directly.

GET /dashboard
Returns all data in single call for Streamlit frontend consumption.
```

All endpoints respond in under 500ms. Data is loaded in memory at startup from events.json and CSV.

---

## 17. DASHBOARD — 5 TAB STRUCTURE

### Tab 1 — Executive Overview

KPI cards: total entries (staff-filtered), average dwell time, zone visits count, total revenue from CSV, transaction count. Timeline chart showing entries per hour. This is what a store manager checks first thing. First thing judges see.

### Tab 2 — Customer Journey (Aggregate)

Funnel chart with five stages: entry count, main floor visits, skincare visits, billing interactions, transaction count. Conversion percentages between each stage. Clear label visible: "Aggregate zone counts, no individual tracking." Traffic-Sales Alignment panel below the funnel, visually separated, with disclaimer text: "Traffic from 16-04-2026, sales from 10-04-2026. Alignment is illustrative only."

### Tab 3 — Zone Intelligence

Per-zone breakdown for CAM 1, 2, 3, 5. Metrics per zone: visit count, average dwell, peak time. Zone popularity heatmap. Store layout image with zone markers overlaid from zones.json if possible. This is where the layout-aware USP is most visible.

### Tab 4 — Revenue Intelligence

Total transactions, GMV, NMV. Top categories by revenue. Private Brand vs External Brand split. Salesperson performance table (ranked by NMV). Promotion effectiveness chart (offer_name by GMV contribution). Time-of-day revenue curve (orders by hour). This tab looks like a retail analytics product.

### Tab 5 — Operational Intelligence and System Health

CAM 4 warehouse activity timeline showing motion events detected via background subtraction. Restocking events. Queue alerts from CAM 5 with duration. Crowding events. Funnel monotonicity validation results (pass or warning). Staff movements detected count. Events loaded count and source. Video hash fingerprint displayed. Last processing run timestamp and duration. API status for all endpoints. Recent log entries (last 50). Processing time from last test run with hardware description.

---

## 18. STARTUP ARCHITECTURE

### At docker compose up (target under 30 seconds):

1. Backend service starts.
2. Checks if events.json exists (precomputed).
3. If yes, loads events.json instantly (under 2 seconds).
4. Loads CSV data into memory.
5. Calculates all metrics.
6. Starts FastAPI on port 8000.
7. Health check endpoint responds healthy.
8. Dashboard service starts after backend health check passes (depends_on with condition service_healthy).
9. Dashboard fetches data from backend via API_BASE_URL environment variable (http://api:8000 inside Docker, http://localhost:8000 during local development).
10. All five tabs are populated and accessible.

### Separate processing command (NOT on startup):

```
python process_videos.py
```

This command reads all MP4 files from the inputs directory, computes SHA256 hash of each file, processes up to MAX_FRAMES frames per camera using YOLOv8-nano at 640x360 with frame skip 5, uses background subtraction for CAM 4 with minimum contour area filter, applies entry line crossing with direction vector for CAM 3, generates zone events with dwell calculation and merge rule, validates funnel monotonicity, writes events.json, writes video_hashes.json, prints a summary of what was detected including actual processing time.

This command is tested end-to-end on all 5 actual video files before submission. The resulting events.json is committed to the repository.

---

## 19. DOCKER ARCHITECTURE — TWO SERVICES

docker-compose.yml defines two separate services: api (FastAPI backend) and dashboard (Streamlit frontend). They communicate over the Docker internal network using service names as hostnames.

The backend Dockerfile includes an explicit HEALTHCHECK instruction:

```
HEALTHCHECK --interval=5s --timeout=3s --retries=6 CMD curl -f http://localhost:8000/health || exit 1
```

The dashboard service uses depends_on with condition service_healthy to wait for the backend. Without the explicit HEALTHCHECK, depends_on is silently ignored by Docker and both services start simultaneously, causing the dashboard to fail on first API call.

The Streamlit code uses an environment variable for the API URL: API_URL = os.getenv("API_BASE_URL", "http://localhost:8000"). In docker-compose.yml, the dashboard service has API_BASE_URL=http://api:8000 as an environment variable. During local development outside Docker, the default localhost works. Inside Docker, the compose variable overrides to use the service name.

The Streamlit dashboard uses a cache decorator with 60-second TTL on the API fetch function. This prevents repeated API calls on tab switches (Streamlit reruns the full script on any user interaction). Tab switching becomes instant.

### YOLO Weights Bundled

yolov8n.pt (approximately 6MB) is downloaded once during development, placed in models/ directory in the repository, and COPYed into the Docker image during build. The Ultralytics configuration points to this local weights file. No network access is required at any point during startup or processing.

CHOICES.md entry: "Model weights are bundled in the Docker image to ensure fully offline operation in evaluation environments."

---

## 20. PROCESS_VIDEOS.PY — SEPARATE COMMAND

This command is not called at docker compose up. It is a standalone script.

What it does:

- Reads all MP4 files from the inputs directory
- Computes SHA256 hash of each file, writes video_hashes.json
- Processes up to max_frames_per_camera (default 1000) frames per camera
- Uses YOLOv8-nano at detection_resolution with frame_skip from config.json
- Uses centroid tracker with tracker_distance_threshold from config.json
- Uses background subtraction for CAM 4 with warehouse_motion_threshold from config.json
- Detects entry line crossings with direction vector for CAM 3
- Calculates zone dwell with merge rule (no other active track condition)
- Applies staff filtering heuristic
- Validates funnel monotonicity
- Writes events.json
- Prints summary with actual measured processing time and hardware info
- Supports --quick flag (MAX_FRAMES=300, frame_skip=10) for fast verification under 5 minutes

At 1000 frames per camera with frame skip 5, this covers roughly 2-3 minutes of actual footage per camera. Total processing varies significantly by CPU and video codec — from 15 minutes on a modern i7 to 60+ minutes on older hardware or inside Docker with resource limits.

The script supports a --quick flag that sets MAX_FRAMES to 300 and frame_skip to 10 for a fast verification run completing in under 5 minutes. This gives judges a way to verify computation quickly without waiting for the full run. The full events.json from the complete run is already committed.

README documents: "For quick verification (under 5 minutes): python process_videos.py --quick. For full analysis: python process_videos.py. Last full test run: [actual time] on [your CPU model]."

CHOICES.md entry: "The --quick flag is a deliberate evaluation environment affordance, processing a reduced frame set to demonstrate live computation within a practical time window."

Important: the system should be fully impressive without requiring judges to run regeneration. docker compose up is the primary path. process_videos.py is the secondary integrity verification path.

---

## 21. README — WHAT TO LOOK FOR

Seven bullet points directing judges to differentiating features:

1. Open the dashboard and check Tab 3 (Zone Intelligence) to see how the official store layout drives the analytics.
2. Run curl against /anomalies to see five specific business-actionable alerts with recommendations.
3. Check Tab 4 (Revenue Intelligence) for salesperson performance and promotion effectiveness from the POS data.
4. Check Tab 5 (System Health) to see the video hash fingerprint that proves events were computed from these specific files.
5. Run python process_videos.py --quick to verify live computation in under 5 minutes and observe metrics updating.
6. Check CHOICES.md for the architectural rationale behind using background subtraction for CAM 4 instead of person detection — this reflects a deliberate design decision, not a limitation.
7. Call GET /events/sample to inspect 10 raw detection events directly from the pipeline output, showing the underlying data that drives all metrics.

---

## 22. CHOICES.MD — FUTURE ROADMAP SECTION

A final section titled Future Architecture Roadmap demonstrates system thinking at zero cost.

- Cross-camera re-identification: would require deep learning ReID models such as OSNet or Fast-ReID, enabling true person-level journey tracking rather than aggregate zone counts. Not implemented due to CPU constraints and time scope.
- Real-time streaming: replacing batch processing with a Kafka event bus would enable live zone occupancy dashboards with sub-second latency.
- Multi-store deployment: the zones.json configuration approach was deliberately designed to be portable. Different store layouts require new zone configuration files with no code changes.
- LLM-generated insights: the structured events and business metrics could feed a language model to generate natural-language store manager reports.

---

## 23. LOGGING AND OBSERVABILITY

Python's logging module with a JSON formatter is implemented from day one. Every API call logs: timestamp, endpoint, response_time_ms, events_count. Anomaly triggers are logged. Staff filtering decisions are logged. Funnel validation results are logged.

Last 50 log entries are accessible via the System Health tab. This takes 30 minutes to implement and scores full marks on observability.

---

## 24. REPOSITORY STRUCTURE

```
store-intelligence-platform/
|-- src/
|   |-- detection.py          # YOLO detection + centroid tracker
|   |-- background_motion.py  # CAM 4 background subtraction
|   |-- zone_classifier.py    # Zone polygon membership checks
|   |-- entry_counter.py      # Entry line crossing with direction
|   |-- session_manager.py    # Session aggregation + dwell merge
|   |-- staff_filter.py       # Staff filtering heuristic (applied by default)
|   |-- funnel.py             # Aggregate funnel + monotonicity validation
|   |-- anomalies.py          # Five anomaly detectors
|   |-- csv_analytics.py      # Revenue intelligence from CSV
|   |-- api.py                # FastAPI endpoints
|   |-- dashboard.py          # Streamlit 5-tab dashboard
|   |-- utils.py              # Helpers, logging, hashing
|-- models/
|   |-- yolov8n.pt            # Bundled YOLO weights (~6MB)
|-- events/
|   |-- events.json           # Precomputed detection events
|   |-- video_hashes.json     # SHA256 hashes of processed videos
|-- data/
|   |-- Brigade_Bangalore_10_April_26.csv
|-- config.json               # All configurable parameters
|-- zones.json                # Store layout zone definitions
|-- process_videos.py         # Standalone processing script
|-- Dockerfile.api            # Backend Dockerfile with HEALTHCHECK
|-- Dockerfile.dashboard      # Dashboard Dockerfile
|-- docker-compose.yml        # Two-service configuration
|-- requirements.txt          # Pinned dependency versions
|-- DESIGN.md                 # System architecture document
|-- CHOICES.md                # Engineering decisions with rationale
|-- README.md                 # Quick start + What to Look For
|-- decisions_log.txt         # Running decisions log (raw notes)
|-- .gitignore                # Excludes *.mp4, __pycache__, logs/
```

---

## 25. PHASE BREAKDOWN

### Phase 0 — Prerequisites and Zone Extraction (5-6 hours)

Objective: Establish ground truth, create all configuration files, start decisions log.

Tasks:

- Open Brigade_Road_Store_layout.xlsx. Determine if machine-readable coordinates exist or if manual extraction from video frames is needed. Spend maximum 30 minutes on this determination.
- Open each video file briefly to confirm camera-to-zone mapping matches expectations. Note actual camera angles.
- Download yolov8n.pt and place in models/ directory. Verify approximately 6MB.
- Create zones.json with zone definitions for all 5 cameras. For CAM 3, define entry_line and entry_direction_vector based on camera angle.
- Write a 20-line OpenCV polygon visualisation script that draws zones.json polygons overlaid on a video frame from each camera. Use this to iteratively correct polygon boundaries until they visually match actual zone locations. Budget 4 hours for zone extraction and visual validation across all cameras.
- Create config.json with all fields defined.
- Create requirements.txt with pinned versions: ultralytics, opencv-python-headless (not opencv-python — headless has no GUI dependency and is smaller and safer in Docker), fastapi, uvicorn, streamlit, pandas, numpy. Use pip freeze after confirming your working environment. Pin every version.
- Freeze event schema and document it.
- Freeze API contracts with exact field names.
- Write all five anomaly rules with implementation notes.
- Start decisions_log.txt and record at least 5 entries from Phase 0 decisions (camera mapping rationale, zone extraction method, config values chosen, etc.).

Tools: Local machine, Excel, text editor.

Phase 0 completion criteria (all must exist):

- Camera mapping confirmed from actual video inspection
- zones.json created with polygon visualisation script verifying all coordinates
- config.json created with all fields defined
- requirements.txt created with pinned versions using opencv-python-headless
- Event schema frozen
- API contracts frozen with exact field names
- All five anomaly rules written with implementation notes
- decisions_log.txt started with at least 5 entries
- yolov8n.pt downloaded and in models/ directory

---

### Phase 1 — Business Logic Design (5-6 hours)

Objective: Architecture and retail intelligence framework on paper before any code.

Tasks:

- Design the three intelligence layers with specific metrics for each.
- Document the aggregate funnel logic precisely.
- Document background subtraction approach for CAM 4 with minimum contour area filter.
- Document the five anomaly rules with implementation approach for each.
- Document entry line crossing logic with centroid method and direction vector.
- Design the 5-tab dashboard structure with specific content per tab.
- Design startup vs processing command separation.
- Design two-service Docker architecture with HEALTHCHECK and API_BASE_URL.
- Request Claude Code to review architecture and generate preliminary DESIGN.md template.
- Continue recording decisions in decisions_log.txt.

Tools: Local machine, text editor, Claude Code for template generation, Antigravity for architecture review.

---

### Phase 2 — CV Validation (2-3 hours)

Objective: Answer four validation questions and calibrate all detection parameters.

Questions to answer:

1. Can YOLOv8-nano detect people in these videos at 640x360? Run on actual machine, not just Colab.
2. Can the centroid tracker maintain consistent IDs? Verify a single walking person keeps one ID for at least 20 consecutive processed frames. If ByteTrack is tested, verify IDs do not reset more than 3 times per minute.
3. Can you count entry crossings from CAM 3? Test on at least 10 actual crossings from the video and count how many are detected correctly.
4. Can you detect zone visits from other cameras?

Additional calibration:

- Confirm background subtraction produces motion events from CAM 4. Adjust warehouse_motion_threshold if needed.
- Final visual verification of all zone polygons from zones.json overlay on video frames.
- Record all validation results in decisions_log.txt.

If all questions are answered positively, stop. Move to Phase 3.

Tools: Google Colab for 1-2 hours of initial YOLO testing. Local machine for tracker validation and zone verification.

---

### Phase 3 — Backend and Event Pipeline (12-14 hours)

Objective: Core event generation, business metric calculation, and full pipeline testing.

Tasks:

- Build event pipeline with zone-aware detection from zones.json.
- Implement centroid tracker with configurable distance threshold from config.json.
- Implement entry line crossing with direction vector for CAM 3.
- Implement dwell time calculation with merge rule (no other active track condition).
- Implement background subtraction for CAM 4 with minimum contour area from config.json.
- Implement funnel monotonicity validation with logging.
- Implement staff filtering heuristic with count logging.
- Implement video hash computation (SHA256 per file).
- Implement MAX_FRAMES configurable parameter.
- Implement --quick flag for process_videos.py (MAX_FRAMES=300, frame_skip=10 for fast verification).
- Implement all five anomaly detectors with triggered_at timestamps.
- Implement CSV analytics: core metrics first (transactions, GMV, NMV, top categories, basket depth), then enhancement metrics if time allows (salesperson ranking, PB vs external brand split, promotion effectiveness, time-of-day revenue curve).
- Run process_videos.py end-to-end on all 5 actual video files.

Tools: Claude Code for code generation. Local machine for testing.

Phase 3 completion checklist (all must pass before proceeding to Phase 4):

- process_videos.py runs on all 5 actual video files without error
- events.json is generated and is non-empty
- events.json contains events from all 5 cameras
- video_hashes.json exists alongside events.json
- /metrics returns three populated sections (traffic, sales, operations) with non-zero values
- /funnel shows entry count greater than zero from CAM 3
- /anomalies endpoint returns valid JSON with correct schema for all five anomaly types, and at least one anomaly has a non-null triggered_at timestamp from actual computation
- Staff heuristic code runs without error and logs its filtering decisions (even if zero staff are detected in the test run)
- Funnel monotonicity validation produces a visible log output showing either pass or warning
- Actual processing time is measured and recorded

If any item fails, Phase 3 is not done and Phase 4 does not begin.

---

### Phase 4 — API Development (8-10 hours)

Objective: FastAPI serving all metrics with correct structure.

Tasks:

- Build all endpoints (/health, /metrics, /funnel, /anomalies, /zone_metrics, /events/sample, /dashboard).
- Add zone name validation to /zone_metrics/{zone} with clean 404 response for invalid zone names listing valid options.
- Add /events/sample endpoint returning 10 raw events from events.json.
- Ensure all data loaded in memory at startup from events.json and CSV.
- Ensure all endpoints respond under 500ms.
- Ensure /health returns full system status including video hashes and config values.
- Implement structured JSON logging with Python's logging module: timestamp, endpoint, response_time_ms, events_count.
- Expose last 50 log entries via /health or System Health data.
- Add input validation.
- Add clear notes and disclaimers in API responses about data sources.
- Test every endpoint locally with curl before proceeding.

Tools: Claude Code for generation. Local machine for testing.

---

### Phase 5 — Dashboard (10-12 hours)

Objective: 5-tab Streamlit dashboard telling a retail story.

Tasks:

- Build Tab 1 (Executive Overview) first.
- Build Tab 5 (System Health) second.
- Build Tabs 2, 3, 4 in order.
- Implement API_BASE_URL environment variable in Streamlit code: API_URL = os.getenv("API_BASE_URL", "http://localhost:8000").
- Implement cache decorator with 60-second TTL on the API fetch function to prevent repeated calls on tab switches.
- Ensure all charts are labelled with data sources.
- Ensure Traffic-Sales Alignment panel in Tab 2 is visually separated with disclaimer.
- Ensure funnel validation result is visible in Tab 5.
- Ensure video hash is visible in Tab 5.
- Ensure staff movements count is visible in Tab 5.
- Ensure actual processing time from last run is visible in Tab 5.
- If store layout image can be overlaid with zone markers in Tab 3, include it.

Tools: Claude Code for generation. Local machine for testing.

---

### Phase 6 — Docker and Processing Script (6-8 hours)

Objective: Two-service deployment with integrity defence.

Tasks:

- Build Dockerfile.api with multi-stage build, bundled yolov8n.pt, explicit HEALTHCHECK instruction.
- Build Dockerfile.dashboard.
- Build docker-compose.yml with two services, depends_on with condition service_healthy, API_BASE_URL environment variable for dashboard, port mappings, volume mounts, restart policy.
- Test startup: docker compose up must complete in under 30 seconds.
- Test HEALTHCHECK: introduce artificial 5-second delay in backend startup, verify dashboard still loads correctly because it waits for health check to pass. Remove delay before submission.
- Test all API endpoints from inside Docker.
- Test dashboard data population when running inside Docker (not just locally). Verify API calls from dashboard container succeed using the Docker network.
- Run process_videos.py end-to-end on all 5 videos. Commit resulting events.json and video_hashes.json.
- Verify that changing a video file and rerunning process_videos.py updates events.json and API returns different metrics.
- Measure and record actual processing time on your hardware.

Tools: Claude Code for Dockerfile generation. Local machine for all Docker testing.

---

### Phase 7 — Documentation (6-8 hours)

Objective: Professional documentation showing ownership and depth.

Tasks:

- Assemble CHOICES.md from decisions_log.txt. Every decision should reference actual data from Phase 2 validation and Phase 3 testing. Include future roadmap section.
- Write DESIGN.md with: executive summary, system architecture (all layers), three intelligence layers, detection pipeline (YOLOv8-nano rationale), tracking strategy (centroid tracker decision), entry line crossing logic, background subtraction for CAM 4, aggregate funnel design with validation, zones.json and config.json as configuration system, store layout integration as headline feature, event schema, API design, startup vs processing separation, Docker two-service architecture, honest limitations.
- Write README.md with: quick start (3 lines), what the platform does, architecture overview, data sources and disclaimers, how to run processing command with expected processing time, How Integrity Is Verified section, What to Look For section (6 bullets), limitations section.
- Add the CAM 4 background subtraction bullet to What to Look For.
- Add staff movements count description.
- Review all documentation against: does this read like someone who owns this system?

Tools: Claude Code for initial drafts. Local machine for personalisation.

---

## 26. EFFORT ALLOCATION

| Phase | Hours | Percentage |
|-------|-------|-----------|
| 0 Prerequisites and Zone Extraction | 5-6 | 7% |
| 1 Business Logic Design | 5-6 | 7% |
| 2 CV Validation | 2-3 | 4% |
| 3 Backend and Pipeline | 12-14 | 18% |
| 4 API Development | 8-10 | 12% |
| 5 Dashboard | 10-12 | 15% |
| 6 Docker and Processing | 6-8 | 10% |
| 7 Documentation | 6-8 | 9% |
| Buffer | 10-13 | 18% |
| **Total** | **64-80** | **100%** |

If time runs out, cut in this specific order only:

1. Zone layout overlay visual in Tab 3 (nice to have)
2. Enhancement CSV metrics in Tab 4: salesperson ranking, PB vs external, promotion chart (secondary)
3. Warehouse correlation observations (speculative)

Never cut: documentation, Docker testing, anomaly endpoint, staff filtering heuristic, core CSV metrics (GMV, NMV, transactions, top categories).

---

## 27. TOOL ALLOCATION MATRIX

| Phase | Colab | Claude Code | Antigravity | Local Machine |
|-------|-------|-------------|-------------|---------------|
| 0 Prerequisites | — | Review templates | — | All work, Excel parsing |
| 1 Design | — | Generate frameworks | Review architecture | Finalise documents |
| 2 CV Validation | 1-2 hrs YOLO test | — | — | Tracker validation, zone verification |
| 3 Backend | — | Generate 80% of code | — | Test, customise, run pipeline |
| 4 API | — | Generate FastAPI | — | Test endpoints |
| 5 Dashboard | — | Generate Streamlit | — | Test dashboard |
| 6 Docker | — | Generate Dockerfiles | — | All Docker testing |
| 7 Documentation | — | Generate initial drafts | Review quality | Personalise and finalise |

Colab is used for two hours maximum in Phase 2 only. Everything else runs locally. Claude Code generates the majority of the codebase. You make decisions and customise. Antigravity is used for architecture review in Phase 1 and documentation quality check in Phase 7.

---

## 28. RISK MITIGATION TABLE

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| process_videos.py fails silently | High | Score capped at 50 | Test end-to-end on all 5 videos. Phase 3 checklist enforced. |
| Docker startup exceeds 30 seconds | Medium | Immediate bad impression | Test on clean machine. Bundle weights. No network calls. |
| Hardcoding accusation | Medium | Score capped at 50 | Video hash fingerprinting in System Health. |
| Funnel numbers fail sanity check | Medium | -5 to -8 points | Monotonicity validation with visible output. |
| CHOICES.md reads like template | High | -5 to -7 points | Decisions log from Day 1. Assembled from real notes. |
| CAM 4 produces no output | Medium | Missed differentiator | Background subtraction has no model dependency. Calibrate threshold. |
| Phase 3 runs over time | High | Eats dashboard and docs | Protect buffer. Begin Phase 3 early. |
| ByteTrack breaks in Docker | Medium | Garbage tracking | Use centroid tracker (zero dependencies). |
| YOLO downloads weights in Docker | High | Startup hangs indefinitely | Bundle yolov8n.pt in image. |
| Dashboard API calls fail in Docker | Medium | Broken dashboard | API_BASE_URL environment variable. Test inside compose. |
| Dwell merge creates false sessions | Low | Inflated metrics | No other active track condition. |

---

## 29. ACCEPTANCE GATE CHECKLIST

Before submission, verify every item in order:

- [ ] docker compose up completes in under 30 seconds
- [ ] No errors in startup logs
- [ ] curl /health returns 200 with all fields populated
- [ ] curl /metrics returns valid JSON with three separate data sections and source labels
- [ ] curl /funnel returns aggregate counts with disclaimer
- [ ] curl /anomalies returns all five anomaly types with business recommendations and triggered_at timestamps
- [ ] curl /zone_metrics/entrance returns valid data
- [ ] Dashboard loads in browser with all five tabs populated
- [ ] Dashboard API calls succeed when running inside Docker (not just locally)
- [ ] events.json present in repository and non-empty
- [ ] video_hashes.json present in repository
- [ ] config.json present in repository with all required fields
- [ ] zones.json present in repository with polygon coordinates for all 5 cameras
- [ ] CSV data present in repository
- [ ] yolov8n.pt present in models/ directory
- [ ] requirements.txt present with pinned versions using opencv-python-headless
- [ ] process_videos.py runs without error on all 5 videos
- [ ] process_videos.py --quick completes in under 5 minutes
- [ ] After running process_videos.py, API metrics reflect updated computation
- [ ] curl /events/sample returns 10 raw events with valid structure
- [ ] curl /zone_metrics/invalid_name returns clean 404 with valid zone list
- [ ] DESIGN.md exists and is specific with actual numbers
- [ ] CHOICES.md exists and explains actual decisions with rationale
- [ ] README.md has quick start, What to Look For, limitations section
- [ ] decisions_log.txt committed (shows honest working)
- [ ] .gitignore excludes all MP4 files
- [ ] No TODO comments in submitted code
- [ ] No hardcoded metric values anywhere
- [ ] Staff filtering count visible in System Health
- [ ] Funnel validation result visible in System Health
- [ ] Video hash visible in System Health
- [ ] Actual processing time visible in README and System Health

---

## 30. SCORING PROJECTION

| Category | Max | Target | How |
|----------|-----|--------|-----|
| Detection | 30 | 24-26 | Zone detection works, entries counted with crossing logic, edge cases documented, staff filtered |
| API and Business Logic | 35 | 31-33 | All endpoints correct, 5 anomalies specific with recommendations, funnel logically consistent with validation |
| Production | 20 | 18-20 | Docker under 30 sec, two services, observability complete, integrity defence visible, bundled weights |
| Thinking | 15 | 13-14 | CHOICES.md built from decisions log, honest limitations, future roadmap, background subtraction rationale |
| **Total** | **100** | **86-93** | **Shortlisted** |

---

## 31. PROJECT POSITIONING

The system is presented as the **Purplle Store Intelligence Platform**.

Three intelligence layers: Customer, Revenue, Operational. Store layout-aware zone analytics via zones.json. Configurable system via config.json. Five-tab dashboard telling a retail story. Background subtraction for warehouse intelligence. Honest aggregate metrics with clear disclaimers. Complete integrity defence via video hashing. Two-service Docker architecture with explicit health checks. Staff filtering heuristic with transparency. Quick verification mode for judges. Raw event inspection via /events/sample. Documentation that shows engineering ownership built from a running decisions log.

When a judge opens this, they think: this person built a product a retailer would pay for.

That is the outcome this plan optimises for.
