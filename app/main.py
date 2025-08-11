from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import io
import base64
from PIL import Image

from .services.vision import analyze_meal
from .services.nutrition import estimate_meal_calories

app = FastAPI(title="Image Calorie Tracker")

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


class FoodEstimate(BaseModel):
    name: str
    quantity: Optional[str] = None
    calories: Optional[float] = None


class AnalyzeResponse(BaseModel):
    items: List[FoodEstimate]
    total_calories: Optional[float]
    backend: str


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def api_analyze(file: UploadFile = File(...)):
    content = await file.read()
    image = Image.open(io.BytesIO(content)).convert("RGB")

    backend, items = await analyze_meal(image)
    enriched_items, total = estimate_meal_calories(items)

    return AnalyzeResponse(items=[FoodEstimate(**i) for i in enriched_items], total_calories=total, backend=backend)


@app.post("/api/analyze_url", response_model=AnalyzeResponse)
async def api_analyze_url(image_base64: str = Form(...)):
    raw = base64.b64decode(image_base64)
    image = Image.open(io.BytesIO(raw)).convert("RGB")

    backend, items = await analyze_meal(image)
    enriched_items, total = estimate_meal_calories(items)

    return AnalyzeResponse(items=[FoodEstimate(**i) for i in enriched_items], total_calories=total, backend=backend)