import asyncio
import os
import random
from datetime import date, datetime, timedelta
from itertools import count
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from clients.nasa_power import NASAPowerClient


class Field:
    def __init__(self, name: str, latitude: float, longitude: float):
        self.id: int = next(_field_id_counter)
        self.name: str = name
        self.latitude: float = latitude
        self.longitude: float = longitude
        self.created_at: datetime = datetime.utcnow()
        self.last_risk: Optional[Dict] = None


class Alert:
    def __init__(self, field_id: int, field_name: str, risk_type: str, severity: int, message: str):
        self.id: int = next(_alert_id_counter)
        self.field_id: int = field_id
        self.field_name: str = field_name
        self.risk_type: str = risk_type
        self.severity: int = severity
        self.message: str = message
        self.created_at: datetime = datetime.utcnow()


_field_id_counter = count(1)
_alert_id_counter = count(1)

FIELDS: Dict[int, Field] = {}
ALERTS: List[Alert] = []


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


app = FastAPI(title="SpaceFarm AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)


nasa_power_client = NASAPowerClient()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}


@app.get("/api/fields")
async def list_fields():
    return [
        {
            "id": field.id,
            "name": field.name,
            "latitude": field.latitude,
            "longitude": field.longitude,
            "created_at": field.created_at.isoformat() + "Z",
            "last_risk": field.last_risk,
        }
        for field in FIELDS.values()
    ]


@app.post("/api/fields")
async def create_field(payload: Dict):
    for key in ("name", "latitude", "longitude"):
        if key not in payload:
            raise HTTPException(status_code=400, detail=f"Missing field: {key}")

    try:
        latitude = float(payload["latitude"])
        longitude = float(payload["longitude"])
    except Exception:
        raise HTTPException(status_code=400, detail="Latitude/Longitude must be numbers")

    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        raise HTTPException(status_code=400, detail="Invalid coordinates")

    field = Field(name=payload["name"], latitude=latitude, longitude=longitude)
    FIELDS[field.id] = field

    # Trigger a risk computation for the new field
    await compute_and_record_risk_for_all_fields()

    return {"id": field.id}


@app.delete("/api/fields/{field_id}")
async def delete_field(field_id: int):
    if field_id not in FIELDS:
        raise HTTPException(status_code=404, detail="Field not found")

    del FIELDS[field_id]
    return {"deleted": field_id}


@app.get("/api/alerts")
async def list_alerts():
    return [
        {
            "id": alert.id,
            "field_id": alert.field_id,
            "field_name": alert.field_name,
            "risk_type": alert.risk_type,
            "severity": alert.severity,
            "message": alert.message,
            "created_at": alert.created_at.isoformat() + "Z",
        }
        for alert in sorted(ALERTS, key=lambda a: a.created_at, reverse=True)
    ]


@app.post("/api/recompute")
async def recompute():
    await compute_and_record_risk_for_all_fields()
    return {"status": "recomputed"}


async def compute_and_record_risk_for_all_fields() -> None:
    if not FIELDS:
        return

    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    for field in FIELDS.values():
        precip_mm_last_7_days = await fetch_precip_sum_mm(field.latitude, field.longitude, start_date, end_date)

        # Simulations for soil moisture and NDVI anomaly for prototype
        random.seed(hash((field.id, end_date.toordinal())))
        simulated_soil_moisture = max(0.0, min(1.0, precip_mm_last_7_days / 100.0 + random.uniform(-0.15, 0.15)))
        simulated_ndvi_anomaly = random.uniform(-0.25, 0.25)

        risk = assess_risk(
            precip_mm_last_7_days=precip_mm_last_7_days,
            soil_moisture_fraction=simulated_soil_moisture,
            ndvi_anomaly=simulated_ndvi_anomaly,
        )

        field.last_risk = {
            "risk_type": risk["risk_type"],
            "severity": risk["severity"],
            "message": risk["message"],
            "metrics": {
                "precip_mm_7d": precip_mm_last_7_days,
                "soil_moisture_frac": simulated_soil_moisture,
                "ndvi_anomaly": simulated_ndvi_anomaly,
            },
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
        }

        if risk["risk_type"] != "normal" and risk["severity"] >= 50:
            alert = Alert(
                field_id=field.id,
                field_name=field.name,
                risk_type=risk["risk_type"],
                severity=risk["severity"],
                message=risk["message"],
            )
            ALERTS.append(alert)

    # Keep only latest 100 alerts
    if len(ALERTS) > 100:
        del ALERTS[:-100]


async def fetch_precip_sum_mm(latitude: float, longitude: float, start_date: date, end_date: date) -> float:
    data = await nasa_power_client.get_daily_precip_mm(
        latitude=latitude,
        longitude=longitude,
        start=start_date,
        end=end_date,
    )
    if not data:
        return 0.0
    return float(sum(v for v in data.values() if isinstance(v, (int, float))))


def assess_risk(precip_mm_last_7_days: float, soil_moisture_fraction: float, ndvi_anomaly: float) -> Dict:
    # Simple heuristic thresholds for prototype
    if precip_mm_last_7_days < 10 and soil_moisture_fraction < 0.3 and ndvi_anomaly < -0.1:
        severity = int(min(100, (0.3 - soil_moisture_fraction) * 250 + (10 - precip_mm_last_7_days) * 3))
        return {
            "risk_type": "drought",
            "severity": max(0, severity),
            "message": "Drought risk: very low rainfall, low soil moisture, and declining vegetation index",
        }

    if precip_mm_last_7_days > 120 or (precip_mm_last_7_days > 80 and soil_moisture_fraction > 0.8):
        severity = int(min(100, (precip_mm_last_7_days - 80) * 0.8 + (soil_moisture_fraction - 0.6) * 200))
        return {
            "risk_type": "flood",
            "severity": max(0, severity),
            "message": "Flood risk: heavy recent rainfall and saturated soils",
        }

    if ndvi_anomaly < -0.2:
        severity = int(min(100, (-ndvi_anomaly) * 400))
        return {
            "risk_type": "crop_stress",
            "severity": max(0, severity),
            "message": "Vegetation stress: NDVI anomaly is below normal",
        }

    return {"risk_type": "normal", "severity": 0, "message": "No significant risk detected"}


async def scheduler_loop() -> None:
    interval_seconds = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "900"))
    jitter_seconds = int(os.getenv("SCHEDULER_JITTER_SECONDS", "10"))

    while True:
        try:
            await compute_and_record_risk_for_all_fields()
        except Exception as exc:
            # In production, log this properly
            print(f"[scheduler] Error: {exc}")
        delay = interval_seconds + random.randint(0, jitter_seconds)
        await asyncio.sleep(delay)


@app.on_event("startup")
async def on_startup():
    # Seed demo fields unless disabled
    if get_bool_env("DISABLE_DEMO_FIELDS", False) is False and not FIELDS:
        demo_fields = [
            {"name": "Demo North Farm", "latitude": 38.5816, "longitude": -121.4944},  # Sacramento
            {"name": "Demo Rift Valley", "latitude": -0.0236, "longitude": 37.9062},   # Kenya-ish center
        ]
        for df in demo_fields:
            field = Field(df["name"], df["latitude"], df["longitude"])
            FIELDS[field.id] = field

    # Prime initial computation
    await compute_and_record_risk_for_all_fields()

    # Start background scheduler
    asyncio.create_task(scheduler_loop())


# Entry point for local running: uvicorn backend.app:app --reload