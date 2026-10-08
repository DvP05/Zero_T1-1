# 🌊 TIDALIS — Frontend (Map-First Command Cockpit & 3D Digital Twin)

This is the interactive frontend for the **TIDALIS Coastal Flood Intelligence Platform**. Built with **React 19**, **Vite**, **Mapbox GL JS (v3)**, **Recharts**, and **Zustand**.

> 💡 For the complete full-stack platform overview, backend instructions, and demo guide, see the [Root README](../README.md).

---

## 🚀 Quick Start

### 1. Prerequisites
- **Node.js**: `>= 18.0.0`
- **npm**: `>= 9.0.0`
- **TIDALIS Backend**: Running on `http://localhost:8000` (see [Root README](../README.md#1-backend-setup-fastapi))

### 2. Installation
From the `frontend/` directory:

```bash
npm install
```

### 3. Environment Variables
Create a `.env` file in `frontend/` (or copy `.env.example`):

```ini
# Backend API Base URL
VITE_API_URL=http://localhost:8000

# Mapbox Public Access Token (optional but recommended for 3D terrain & satellite layers)
# Get a free public token from https://account.mapbox.com
VITE_MAPBOX_TOKEN=
```

> 💡 **No Mapbox token yet?** The application gracefully defaults to a dark vector tile base style, and allows you to paste your Mapbox token directly inside the in-app `🔑 Mapbox` HUD tool.

### 4. Development Server
Run the local Vite development server:

```bash
npm run dev
```

The application will be live at:
👉 **[http://localhost:5173](http://localhost:5173)**

---

## 🛠️ Available Scripts

| Script | Command | Purpose |
| :--- | :--- | :--- |
| **`npm run dev`** | `vite` | Starts Vite HMR dev server on `http://localhost:5173` |
| **`npm run build`** | `vite build` | Compiles production assets into `dist/` |
| **`npm run preview`** | `vite preview` | Previews the production build locally |
| **`npm run lint`** | `oxlint` | Runs fast code quality linter across all JSX/JS files |

---

## 🧱 Component Architecture: Map-First Command Cockpit

The frontend is organized around an uncluttered, high-productivity **Map-First Command Cockpit**:

```text
frontend/src/
├── components/
│   ├── map/
│   │   ├── MapView.jsx         # 3D Digital Twin (Mapbox GL JS v3 + 3D terrain + atmospheric fog)
│   │   ├── MapHUD.jsx          # Floating HUD: 2D/3D tilt toggle, style switcher, recenter, token modal
│   │   ├── MapLegend.jsx       # Floating collapsible symbology legend pill
│   │   ├── mapboxStyles.js     # Mapbox styles, expressions, risk color matching
│   │   └── pulseMarker.js      # Dynamic canvas pulse animation for epicenter beacons
│   ├── TacticalRail.jsx        # Collapsible Left Sidebar (Incidents feed, alerts, layer toggles)
│   ├── ContextInspector.jsx    # Unified Right Inspector (Command Brief, Priorities, Zone Intel, Event Detail)
│   ├── TimelineScrubber.jsx    # Sleek floating timeline scrubber (T+0 to T+5h) with WS play/pause
│   ├── OperationsDrawer.jsx    # Expandable bottom operations console (Copilot, What-If, Mitigation, SOS, etc.)
│   ├── Header.jsx              # System status, live pill, and coastal condition badge
│   ├── IncidentList.jsx        # Live detected event cards
│   ├── AlertStream.jsx         # Real-time alert notifications
│   ├── LayersPanel.jsx         # Granular layer visibility controls
│   ├── CommandBriefPanel.jsx   # Natural-language situational brief grounded in SHAP drivers
│   ├── PriorityPanel.jsx       # Ranked emergency priority board (auto-promotes isolated enclaves)
│   ├── ZoneIntelPanel.jsx      # Detailed metrics for the currently selected flood zone
│   ├── SOSPanel.jsx            # Topographical SOS distress signal triage interface
│   ├── MitigationPanel.jsx     # Prescriptive tactical intervention recommendations
│   ├── TelemetryPanel.jsx      # Technical ML diagnostic dashboard
│   ├── ForecastPanel.jsx       # Recharts hydrodynamic projections
│   ├── ExposurePanel.jsx       # Asset vulnerability cards
│   └── WhatIfPanel.jsx         # Hydrodynamic parameter perturbation simulator
├── lib/
│   └── api.js                  # Typed API fetcher with graceful offline fallbacks & WebSocket URL
├── store.js                    # Global Zustand store (Mapbox state, layout state, snapshots, playback)
├── App.jsx                     # Top-level cockpit layout with dynamic sidebar collapsing
└── index.css                   # Custom design system with dark oceanic palette and glassmorphism
```

---

## 🎨 UI De-Cluttering Highlights

1. **Map-First Canvas**: The map now takes up to 85–100% of the screen.
2. **Collapsible Tactical Rail**: Left sidebar collapses to a 52px slim icon rail preserving 1-click access to incidents, alerts, and layer toggles.
3. **Unified Context Inspector**: Consolidates 4 separate stacked panels into 1 tabbed inspector with auto-focusing on map click (clicking a zone switches to Zone Intel; clicking an event switches to Event Details).
4. **Expandable Operations Console**: Replaces the permanent 260px footer with an expandable drawer (minimized to 38px when monitoring the map, slides up to 320px for simulations and Copilot).
5. **Floating Glassmorphism Overlays**: Floating 2D/3D controls, map style switcher, collapsible legend pill, and floating timeline scrubber.
