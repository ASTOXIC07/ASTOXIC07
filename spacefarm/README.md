# SpaceFarm AI (Prototype)

From Space Data to Sustainable Harvests

This is a minimal prototype: FastAPI backend + Leaflet frontend. It ingests real NASA POWER precipitation for a location, simulates soil moisture and NDVI anomalies, computes simple drought/flood/crop-stress risks, and visualizes fields and alerts on a map.

## Run locally

Requirements: Python 3.10+

```bash
cd /workspace/spacefarm/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open: http://localhost:8000/

## Environment variables

- `SCHEDULER_INTERVAL_SECONDS` (default 900): how often to recompute risks
- `SCHEDULER_JITTER_SECONDS` (default 10)
- `DISABLE_DEMO_FIELDS` (default false): set to `true` to start with no demo fields

## Notes

- Real data integrated: NASA POWER PRECTOTCORR (daily precipitation, mm). SMAP/MODIS/GPM can be added via additional clients.
- Alerts are stored in-memory for the demo.
- Click on the map to auto-fill coordinates; add fields, then "Recompute Risks" to force immediate update.