"""
Vision AI module - analyzes uploaded design images.
Uses OpenAI GPT-4o for image analysis.
"""

import json
import os
import re
from openai import OpenAI

ANALYSIS_PROMPT = """You are analyzing a print design/logo for merchandise pricing.

For this image, estimate:
1. logo_size: How much of the printable area does the design cover?
   - "small": < 15% (small logo, text, icon)
   - "medium": 15-40% (medium graphic)
   - "large": 40-70% (large design)
   - "full": > 70% (full print, all-over)

2. color_count: How many distinct solid colors are in the design? (Count gradients as 1 unless very complex. Round to nearest integer.)

3. notes: Brief relevant details (e.g. "gradient", "halftone", "text only") or "none".

Return ONLY valid JSON, no markdown or extra text:
{"logo_size":"small|medium|large|full","color_count":N,"notes":"..."}"""


def analyze_image(image_base64: str) -> dict:
    """
    Analyze a single image and return structured design analysis.
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    base64_data = image_base64.split(",")[1] if "," in image_base64 else image_base64

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_data}"},
                    },
                ],
            }
        ],
        max_tokens=150,
    )

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise ValueError("No response from Vision API")

    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    json_str = match.group(1).strip() if match else content

    parsed = json.loads(json_str)

    logo_size = (
        parsed["logo_size"]
        if parsed.get("logo_size") in ["small", "medium", "large", "full"]
        else "small"
    )
    color_count = max(1, min(20, round(float(parsed.get("color_count", 1)))))
    notes = str(parsed.get("notes", "none"))[:100]

    return {"logo_size": logo_size, "color_count": color_count, "notes": notes}


def analyze_images(images_base64: list[str]) -> dict:
    """
    Analyze multiple images (e.g. front and back design).
    """
    keys = ["front", "back"]
    results = {}

    for i, img in enumerate(images_base64):
        if i >= len(keys):
            break
        if img and len(img) > 100:
            try:
                results[keys[i]] = analyze_image(img)
            except Exception as err:
                print(f"Vision analysis failed for {keys[i]}: {err}")
                results[keys[i]] = {
                    "logo_size": "small",
                    "color_count": 1,
                    "notes": "analysis failed",
                }

    return results
