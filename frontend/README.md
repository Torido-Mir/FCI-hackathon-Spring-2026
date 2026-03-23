# Frontend — MillionReady 
 
React + Vite dashboard for visualizing the Vision One Million Scorecard metrics. Displays live employment (and other sector) scores with trend charts, and provides manual controls to refresh or re-fetch data.
 
## Tech Stack
 
| Tool | Purpose |
|---|---|
| React 18 | UI framework |
| Vite | Dev server + bundler |
| Rechart (possibly) | Trend line charts |
| Axios or Fetch | HTTP calls to FastAPI backend |
| TailwindCSS | Styling |
 
## Setup
 
### 1. Install dependencies
```bash
npm install
```
 
### 2. Configure environment variables
```bash
cp .env.example .env
```
 
Fill in `.env`:
```
VITE_API_URL=http://localhost:8000
```
 
In production, point this at your deployed backend URL.
 
### 3. Run the dev server
```bash
npm run dev
```
 
App available at: http://localhost:5173
 
### 4. Build for production
```bash
npm run build
```
 
## Project Structure
 
```
frontend/
├── public/
├── src/
│   ├── main.jsx
│   ├── App.jsx               # Root layout, sector tabs
│   ├── api/
│   │   └── client.js         # Axios instance + API calls (fetchData, getMetrics, getHistory)
│   ├── components/
│   │   ├── ScoreCard.jsx     # Single metric card (score, status badge, source link)
│   │   ├── TrendChart.jsx    # Recharts line chart for historical data
│   │   ├── SectorPanel.jsx   # Grid of ScoreCards for one sector
│   │   ├── RefreshButton.jsx # Polls /metrics for newer data
│   │   └── RefetchButton.jsx # Triggers POST /fetchData pipeline
│   └── hooks/
│       └── useMetrics.js     # Data fetching + polling logic
├── .env.example
├── index.html
├── vite.config.js
└── package.json
```
 
## Key Components
 
### RefreshButton
Calls `GET /metrics` and compares the returned `fetched_at` timestamp against what's currently displayed. If newer data exists, updates the dashboard. This is a lightweight read from the database — no external API calls are made.
 
```
[Refresh] → GET /metrics → compare timestamp → update if newer
```
 
### RefetchButton
Calls `POST /fetchData` which triggers the full pipeline on the backend — external API calls, scraping, transformation, and database write. Use this during the demo to show the live pipeline running.
 
```
[Refetch] → POST /fetchData → pipeline runs → GET /metrics → update dashboard
```
 
### ScoreCard
Displays a single metric with:
- Metric name and current value with unit
- Numerical score (0–100)
- Status badge: `On track` (green) / `In progress` (amber) / `Needs attention` (red)
- Source name + link
- Last updated timestamp
 
### TrendChart
A Recharts `LineChart` showing the historical values for a metric over time. Data comes from `GET /metrics/history?metric=<name>`.
 
## Status Badge Colours
 
| Status | Colour | Meaning |
|---|---|---|
| `on_track` | Green | Meeting or exceeding target |
| `in_progress` | Amber | Moving toward target but not there yet |
| `needs_attention` | Red | Below target, action required |
 
## API Integration
 
All API calls are defined in `src/api/client.js`:
 
```js
// Get latest metrics from DB (fast — no external calls)
getMetrics()              → GET /metrics
 
// Trigger full pipeline (slow — hits external sources)
triggerFetch()            → POST /fetchData
 
// Get historical data for trend charts
getHistory(metricName)    → GET /metrics/history?metric=<name>
```

getHistory may or may not be necessary.
 
## Adding a New Sector
 
1. Add a new tab in `App.jsx`
2. Create a `SectorPanel` entry pointing at the new sector's metrics
3. No changes needed to `ScoreCard` or `TrendChart` — they're data-agnostic
 
## Demo Flow
 
1. App loads → calls `GET /metrics` → displays current scores and trend charts
2. Presenter clicks **Refetch** → `POST /fetchData` runs live → spinner shows pipeline working
3. Pipeline completes → dashboard auto-updates with newest data point appended to charts
4. Presenter clicks **Refresh** at any point to check for newer data without re-running the pipeline