# Image-based Calorie Tracker

A minimal FastAPI service that estimates calories from a meal photo using a pluggable vision backend (OpenAI or a lightweight local heuristic) and a tiny nutrition DB.

## Features
- Upload a meal photo and get estimated foods and calories
- OpenAI Vision backend if `OPENAI_API_KEY` is set
- Local heuristic fallback when offline
- Simple web UI

## Quickstart

```bash
# 1) Create virtualenv (optional)
python3 -m venv .venv && source .venv/bin/activate

# 2) Install deps
pip install -r requirements.txt

# 3) Run server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4) Open UI
xdg-open http://localhost:8000 || open http://localhost:8000
```

## Environment
- `OPENAI_API_KEY` (optional): enables OpenAI vision-backed parsing

## Notes
- This is not medical advice; estimates can be wrong.
- Improve accuracy by adding food items in `app/data/nutrition.json` or wiring a full nutrition API.
