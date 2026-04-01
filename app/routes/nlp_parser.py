"""
nlp_parser.py — Smart Update NLP extractor powered by Groq (FREE)
──────────────────────────────────────────────────────────────────
Worker types plain English → Groq llama-3.3-70b extracts structured fields.
Falls back to regex engine if no GROQ_API_KEY is set.
"""

import os
import json
import re
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

EXTRACTION_PROMPT = """\
You are a construction site data extractor. Parse the worker's update and extract structured fields.

Worker update: "{text}"

Return ONLY valid JSON — no markdown, no explanation, no extra text:
{{
  "quantity_done": <number or null>,
  "quantity_unit": <"m" | "km" | "m3" | "m2" | "ton" | "rings" | "panels" | "nos" | null>,
  "hours_worked": <number or null>,
  "work_type": <one of: "TBM Excavation" | "TBM Advance" | "Segment Erection" | "Dam Concrete Pouring" | "Metro Viaduct Construction" | "Highway Paving" | "Reinforcement Work" | "Earthwork / Excavation" | "Grouting / Waterproofing" | "Survey & Alignment" | "Equipment Maintenance" | "Safety Inspection" | "Other">,
  "work_description": <clean description string>,
  "issue_type": <"None" | "Equipment Breakdown" | "Material Delay" | "Geological Issues" | "Labour Shortage" | "Safety Incident" | "Design Change" | "Power Failure">,
  "weather_condition": <"Clear" | "Cloudy" | "Rain" | "Heavy Rain" | "Fog" | "Extreme Heat" | null>,
  "crew_size": <number or null>,
  "confidence": <integer 0-100>
}}

Rules:
- quantity_unit: use "m3" for cubic meters, "m2" for square meters (not unicode chars)
- issue_type defaults to "None" if not mentioned
- confidence: 85+ if all fields found, 50-84 if some missing, below 50 if very little info
"""


def _regex_fallback(text: str) -> dict:
    result = {
        "quantity_done": None, "quantity_unit": None,
        "hours_worked": None, "work_type": None,
        "work_description": text, "issue_type": "None",
        "weather_condition": None, "crew_size": None,
        "confidence": 25, "source": "regex_fallback"
    }

    for pat, unit in [
        (r'(\d+(?:\.\d+)?)\s*(?:metre|meter|meters|metres|m)\b(?!\d)', 'm'),
        (r'(\d+(?:\.\d+)?)\s*km\b', 'km'),
        (r'(\d+(?:\.\d+)?)\s*(?:cubic|cu\.?\s*m|m3|m³)', 'm3'),
        (r'(\d+(?:\.\d+)?)\s*(?:sq\.?\s*m|m2|m²)', 'm2'),
        (r'(\d+(?:\.\d+)?)\s*(?:ring|rings)', 'rings'),
        (r'(\d+(?:\.\d+)?)\s*(?:ton|tonne)', 'ton'),
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result["quantity_done"] = float(m.group(1))
            result["quantity_unit"] = unit
            break

    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:hour|hr|hrs|h)\b', text, re.IGNORECASE)
    if m:
        result["hours_worked"] = float(m.group(1))

    m = re.search(r'(\d+)\s*(?:worker|crew|men|person|people|staff)', text, re.IGNORECASE)
    if m:
        result["crew_size"] = int(m.group(1))

    for kw, issue in {
        "equipment": "Equipment Breakdown", "breakdown": "Equipment Breakdown",
        "material":  "Material Delay",      "delay":     "Material Delay",
        "safety":    "Safety Incident",     "accident":  "Safety Incident",
        "geological":"Geological Issues",   "rock":      "Geological Issues",
        "power":     "Power Failure",       "labour":    "Labour Shortage",
    }.items():
        if kw in text.lower():
            result["issue_type"] = issue
            break

    for kw, w in {"rain": "Rain", "fog": "Fog", "cloudy": "Cloudy",
                  "heat": "Extreme Heat", "clear": "Clear", "sunny": "Clear"}.items():
        if kw in text.lower():
            result["weather_condition"] = w
            break

    for kw, wt in {
        "tbm": "TBM Advance", "tunnel": "TBM Excavation", "segment": "Segment Erection",
        "concrete": "Dam Concrete Pouring", "paving": "Highway Paving", "pave": "Highway Paving",
        "viaduct": "Metro Viaduct Construction", "grout": "Grouting / Waterproofing",
        "survey": "Survey & Alignment", "reinforce": "Reinforcement Work",
    }.items():
        if kw in text.lower():
            result["work_type"] = wt
            break

    result["confidence"] = 40 if result["quantity_done"] else 20
    return result


@router.post("/parse-update")
async def parse_update(request: Request):
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "No text provided"}, status_code=400)

    if not GROQ_API_KEY:
        parsed = _regex_fallback(text)
        return JSONResponse(parsed)

    prompt = EXTRACTION_PROMPT.format(text=text)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       GROQ_MODEL,
                    "max_tokens":  400,
                    "temperature": 0.1,   # low temp for deterministic extraction
                    "messages": [
                        {"role": "system", "content": "You extract structured JSON from construction updates. Return only valid JSON."},
                        {"role": "user",   "content": prompt},
                    ],
                },
            )

        data = resp.json()
        if resp.status_code != 200 or not data.get("choices"):
            raise ValueError(data.get("error", {}).get("message", "Groq error"))

        raw = data["choices"][0]["message"]["content"]
        # Strip accidental markdown fences
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        parsed = json.loads(raw)
        parsed["source"] = "groq_llm"
        return JSONResponse(parsed)

    except Exception as e:
        fallback = _regex_fallback(text)
        fallback["note"] = f"Groq error, used regex: {str(e)[:80]}"
        return JSONResponse(fallback)