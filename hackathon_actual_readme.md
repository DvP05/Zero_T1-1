# 🌊 Coastal Flood Intelligence: "Singularity"
> **Know before the water arrives.**

An AI-powered coastal flood intelligence and emergency decision-support platform built for **Singularity 2026 — Track 1: AI for Coastal Flood Intelligence**.

The platform transforms environmental, geographic, and infrastructure data into actionable intelligence, answering: **Where will flooding occur? When? How severe? Who needs help first?**

---

## 💡 The Solution
Coastal Flood Intelligence combines environmental intelligence, machine learning, geospatial analysis, and emergency prioritization into a single workflow. It transforms heterogeneous data into **predictive, spatially-aware, explainable, and actionable intelligence**, moving from reactive flood warnings to proactive disaster management.

### 🌟 Key Standout Features
1.  **Immersive 3D Digital Twin:** Dynamic, extruded 3D visualization of coastal risk using `deck.gl`.
2.  **Temporal "Time-Machine" Scrubber:** Scrub through storm scenarios (T+0 to T+5h) to see predictions and risks evolve in real-time.
3.  **GenAI "Command Brief":** Deterministic, number-grounded templates generate plain-text emergency summaries, providing context by explaining why a zone is at risk (e.g., "Rising tides combined with heavy rainfall...").
4.  **Dynamic Isolation Detection:** Real-time network analysis of the road graph to identify enclaves where all egress routes are impassable.
5.  **Mitigation Suggestion Engine:** Prescriptive AI recommending interventions based on the exact threat vector (e.g., "Deploy high-capacity pumps to Node 4").
6.  **Topographical SOS Triage:** Cross-references SOS pings with live topographical data and flood depth to triage trapped individuals based on their elevation relative to rising water.
7.  **ML Telemetry Dashboard:** A dedicated diagnostic view for technical stakeholders displaying real-time model accuracy, F1 scores, and ROC curves using a live validation dataset.

---

## 🛠️ Technology Stack
*   **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, Framer Motion, `deck.gl` + MapLibre GL JS, Zustand (state management).
*   **Backend:** FastAPI (Python), WebSockets (for live scenario streaming), PostGIS (spatial queries), In-memory store (for demo purposes).
*   **ML Pipeline:** XGBoost (flood classification), `scikit-learn` (fallback), Tree SHAP (feature-level explainability).

---

## 🧠 Core Engine Details

### 1. Machine Learning Details
The platform uses a gradient-boosted flood classifier to determine flood risk at the zone level.
*   **Model:** XGBoost (Gradient Boosted Decision Tree).
*   **Training Data:** 40,000 synthetic, physically-grounded historical records.
*   **Labelling:** `hydrologic_depth()` function ensures consistency between map visualizations and model predictions.
*   **Performance:** ~91% Accuracy, ~0.90 AUC.
*   **Explainability:** Tree SHAP values (`predict(pred_contribs=True)`) identify top 4 contributing drivers per zone.

### 2. Mitigation Suggestion Engine (`mitigation_engine.py`)
An expert system that prescribes actionable interventions based on threat vectors:
*   **Threat Vectors:** `tidal_surge`, `rainfall`, `drainage`, `low_elevation`, `infrastructure`.
*   **Output:** Generates `MitigationPlan` containing `MitigationSuggestion` objects (Action, Priority, Cost, Time-to-Deploy, Resources, Effectiveness).
*   **Prioritization:** Rules-based sorting (IMMEDIATE > HIGH > MEDIUM > LOW).

### 3. Topographical SOS Triage Engine (`sos_engine.py`)
Triage stranded individuals by cross-referencing GPS with a Digital Elevation Model (DEM).
*   **Logic:** Computes `water_margin_m = elevation_m - flood_depth_m`.
*   **Triage:** Submerged or shallow-margin locations, especially with medical emergencies or vulnerable populations (children/elderly), are promoted to `CRITICAL`.
*   **Recommendation:** Automatically determines optimal rescue (`HELICOPTER`, `BOAT`, `WADE_TEAM`, `GROUND_VEHICLE`) based on water margin and emergency specifics.

### 4. ML Telemetry Engine (`telemetry.py`)
Feeds the diagnostic view with:
*   **Measured Metrics:** Actual F1, AUC, accuracy on hold-out set.
*   **Simulated Diagnostics (labelled):** Training history, PSI drift reports, streaming inference logs (`inference_log` showing probability/confidence/latency).

---

## ✅ Current Build Progress (As of Oct 8, 2026)
### All Phases (1-5) are complete:
- Foundation, Data Mocking, ML/Intelligence, 3D Digital Twin, Command-Center UI, and Demo Polishing.

---

## 🚀 Future Improvements
*   **Real-Time Data Integration:** Ingest live feeds from weather APIs, tide gauges, and satellite observations.
*   **Satellite Intelligence:** Computer vision for real-time flood monitoring.
*   **Advanced Spatiotemporal Models:** Move to hybrid `Space + Time + Weather + Terrain` models.
*   **Dynamic Evacuation Routing:** Compute real-time, safest evacuation routes.
*   **Public Warning System:** Integrate with SMS/mobile push notification gateways.
*   **Hydrodynamic Simulation:** Combine ML predictions with fine-grained 2D hydrodynamic modeling.

---

## ⚠️ Limitations (Not in Scope)
- **Operational Emergency Forecasts:** Demo predictions are synthetic; not for real-world use.
- **Full Production DB:** Current data storage is in-memory.
- **Autonomous Action:** Decision-support only; human oversight required.

---

## 💻 Runbook
```powershell
# Backend (project root)
.\.venv\Scripts\uvicorn backend.app.main:app --reload --port 8000
python -m scripts.generate_geo        # regenerates data/geo/*.geojson
pytest backend/tests -q

# Frontend (frontend/)
npm run lint && npm run build
npm run dev    # Vite on :5173, API on :8000
```
