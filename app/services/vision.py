import os
import io
import base64
from typing import List, Tuple
from PIL import Image

OPENAI_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
VISION_BACKEND = os.getenv("VISION_BACKEND", "heuristic").strip().lower()


def _image_to_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


async def _analyze_with_openai(image: Image.Image) -> List[dict]:
    from openai import OpenAI

    client = OpenAI()
    b64 = _image_to_base64(image)

    prompt = (
        "You are a nutrition assistant. Look at the meal photo and list distinct foods with rough quantities. "
        "Return a JSON array where each element has: name (string) and quantity (string, e.g., '1 cup', '150 g', '2 slices'). "
        "Do not include calories. Example: [{\"name\": \"grilled chicken breast\", \"quantity\": \"150 g\"}]."
    )

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content or "{}"
    # The assistant might return an object like {"items": [...]}
    import json
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
            return data["items"]
    except Exception:
        pass
    return []


async def _analyze_with_heuristic(image: Image.Image) -> List[dict]:
    # Extremely naive color-based guess to provide some baseline offline.
    small = image.resize((64, 64))
    pixels = list(small.getdata())
    avg_r = sum(p[0] for p in pixels) / len(pixels)
    avg_g = sum(p[1] for p in pixels) / len(pixels)
    avg_b = sum(p[2] for p in pixels) / len(pixels)
    avg_brightness = (avg_r + avg_g + avg_b) / 3.0

    items: List[dict] = []

    # Heuristic: detect greens
    if avg_g > avg_r + 10 and avg_g > avg_b + 10:
        items.append({"name": "salad", "quantity": "1 bowl"})

    # Heuristic: detect tomato-ish
    if avg_r > avg_g + 15 and avg_r > avg_b + 15:
        items.append({"name": "tomato-based dish", "quantity": "1 cup"})

    # Heuristic: bright/white -> rice
    if avg_brightness > 200 and abs(avg_r - avg_g) < 20 and abs(avg_g - avg_b) < 20:
        items.append({"name": "rice", "quantity": "1 cup"})

    # Heuristic: blueberry-ish
    if avg_b > 140 and avg_b > avg_r + 20:
        items.append({"name": "blueberry topping", "quantity": "2 tbsp"})

    if not items:
        items.append({"name": "mixed meal", "quantity": "1 serving"})
    return items


async def analyze_meal(image: Image.Image) -> Tuple[str, List[dict]]:
    # Force heuristic unless explicitly requested
    if VISION_BACKEND == "openai" and os.getenv("OPENAI_API_KEY"):
        try:
            items = await _analyze_with_openai(image)
            if items:
                return "openai", items
        except Exception:
            pass
    items = await _analyze_with_heuristic(image)
    return "heuristic", items