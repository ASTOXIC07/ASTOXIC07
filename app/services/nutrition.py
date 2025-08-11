import json
import os
import re
from typing import List, Tuple, Dict

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "nutrition.json")

_DEFAULT_DB = {
    "grilled chicken breast": {"per": "100 g", "calories": 165},
    "rice": {"per": "100 g", "calories": 130},
    "brown rice": {"per": "100 g", "calories": 111},
    "salad": {"per": "1 cup", "calories": 15},
    "tomato-based dish": {"per": "1 cup", "calories": 90},
    "mixed meal": {"per": "1 serving", "calories": 400},
    "blueberry topping": {"per": "1 tbsp", "calories": 10},
    "bread": {"per": "1 slice", "calories": 80},
    "egg": {"per": "1 large", "calories": 78},
}


def _load_db() -> Dict[str, Dict]:
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return _DEFAULT_DB


_DB = _load_db()


_QUANTITY_PATTERNS = [
    (re.compile(r"(?i)([0-9]+(?:\.[0-9]+)?)\s*(g|gram|grams)"), ("g", 1.0)),
    (re.compile(r"(?i)([0-9]+(?:\.[0-9]+)?)\s*(kg|kilogram|kilograms)"), ("g", 1000.0)),
    (re.compile(r"(?i)([0-9]+(?:\.[0-9]+)?)\s*(ml|milliliter|milliliters)"), ("ml", 1.0)),
    (re.compile(r"(?i)([0-9]+(?:\.[0-9]+)?)\s*(l|liter|liters)"), ("ml", 1000.0)),
    (re.compile(r"(?i)([0-9]+(?:\.[0-9]+)?)\s*(cup|cups)"), ("cup", 1.0)),
    (re.compile(r"(?i)([0-9]+(?:\.[0-9]+)?)\s*(tbsp|tablespoon|tablespoons)"), ("tbsp", 1.0)),
    (re.compile(r"(?i)([0-9]+(?:\.[0-9]+)?)\s*(tsp|teaspoon|teaspoons)"), ("tsp", 1.0)),
    (re.compile(r"(?i)([0-9]+)\s*(slice|slices)"), ("slice", 1.0)),
    (re.compile(r"(?i)([0-9]+)\s*(piece|pieces|serving|servings)"), ("serving", 1.0)),
    (re.compile(r"(?i)([0-9]+)\s*(large|medium|small)"), ("unit", 1.0)),
]


_UNIT_TO_REF_GRAMS = {
    "g": 1.0,
    "ml": 1.0,  # assumes water-like density
    "cup": 240.0,
    "tbsp": 15.0,
    "tsp": 5.0,
    "slice": 30.0,
    "serving": 150.0,
    "unit": 50.0,
}


_DEF_PER_UNIT = {
    "100 g": ("g", 100.0),
    "1 cup": ("cup", 1.0),
    "1 tbsp": ("tbsp", 1.0),
    "1 tsp": ("tsp", 1.0),
    "1 slice": ("slice", 1.0),
    "1 serving": ("serving", 1.0),
    "1 large": ("unit", 1.0),
}


def _parse_quantity_to_grams(quantity: str) -> float:
    if not quantity:
        return 150.0
    for regex, (unit, scale) in _QUANTITY_PATTERNS:
        m = regex.search(quantity)
        if m:
            amount = float(m.group(1))
            if unit in ("g", "ml"):
                return amount * scale
            ref = _UNIT_TO_REF_GRAMS.get(unit, 150.0)
            return amount * ref * scale
    return 150.0


def _per_to_grams(per_str: str) -> float:
    unit_tuple = _DEF_PER_UNIT.get(per_str)
    if not unit_tuple:
        # try to parse generic like "100 g"
        m = re.match(r"(?i)([0-9]+)\s*g", per_str or "")
        if m:
            return float(m.group(1))
        return 100.0
    unit, amount = unit_tuple
    if unit in ("g", "ml"):
        return amount
    return amount * _UNIT_TO_REF_GRAMS.get(unit, 100.0)


def estimate_meal_calories(items: List[Dict]) -> Tuple[List[Dict], float]:
    enriched: List[Dict] = []
    total = 0.0
    for item in items:
        name = (item.get("name") or "").strip().lower()
        quantity = item.get("quantity") or ""

        # naive synonym resolution
        candidates = [name]
        if name.endswith(" dish"):
            candidates.append(name.replace(" dish", ""))

        calories = None
        for cand in candidates:
            if cand in _DB:
                entry = _DB[cand]
                base_cals = float(entry["calories"])  # per base unit
                per_grams = _per_to_grams(entry["per"])  # grams/ml per base unit
                qty_grams = _parse_quantity_to_grams(quantity)
                # scale linearly
                calories = base_cals * (qty_grams / per_grams)
                break

        if calories is None:
            # fallback
            qty_grams = _parse_quantity_to_grams(quantity)
            calories = 2.0 * qty_grams  # 2 kcal/g heuristic

        calories = round(calories, 1)
        total += calories
        enriched.append({"name": item.get("name", name), "quantity": quantity, "calories": calories})

    return enriched, round(total, 1)