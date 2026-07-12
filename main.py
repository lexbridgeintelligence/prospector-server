from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import os
import json
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

NICHE_LABELS = {
    "hair": "hair transplant clinic",
    "ivf": "IVF fertility clinic",
    "cosmetic": "cosmetic surgery clinic",
    "dental": "dental implant clinic",
    "laser": "laser eye surgery clinic",
    "aesthetics": "aesthetics clinic",
    "ortho": "private orthopaedic clinic",
    "weight": "weight loss surgery clinic",
    "custom": "private clinic",
}

AVG_VALUES = {
    "hair": 5500, "ivf": 5000, "cosmetic": 6000, "dental": 3000,
    "laser": 2800, "aesthetics": 1200, "ortho": 4500, "weight": 8000, "custom": 3000,
}

# ── Models defined BEFORE they are used ──────────────────────────────────────

class SearchRequest(BaseModel):
    niche: str = "hair"
    location: str = "London, UK"
    maxResults: int = 20

class EnrichRequest(BaseModel):
    name: str
    area: str
    rating: float = 4.0
    reviewCount: int = 20
    leakageSignals: list = []
    niche: str = "hair"

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "live": True}

@app.post("/search")
def search(req: SearchRequest):
    niche_label = NICHE_LABELS.get(req.niche, "private clinic")
    avg_value = AVG_VALUES.get(req.niche, 3000)
    city = req.location.split(",")[0].strip()

    prompt = f"""Search the web for real "{niche_label}" businesses in "{req.location}" UK.

Find up to {req.maxResults} REAL businesses that actually exist.

Return a JSON array only, no other text:
[
  {{
    "name": "Full clinic name",
    "area": "{city}",
    "phone": "phone number or null",
    "website": "full URL or null",
    "rating": 4.2,
    "reviewCount": 87,
    "hasWhatsApp": false,
    "hasWebsite": true,
    "leakageSignals": ["No WhatsApp", "Web form only"]
  }}
]

leakageSignals pick 2-4 from: "No WhatsApp", "Web form only", "No after-hours response", "No online booking", "Phone only", "Limited hours", "Single coordinator likely"

Return ONLY the JSON array. No markdown. No explanation."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    raw = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw += block.text

    match = re.search(r'\[[\s\S]*\]', raw)
    if not match:
        return {"success": False, "error": "No clinic data found", "businesses": []}

    try:
        clinics = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"success": False, "error": "Failed to parse clinic data", "businesses": []}

    businesses = []
    for c in clinics:
        leakage = c.get("leakageSignals", [])
        score = 50
        if not c.get("hasWhatsApp", True): score += 15
        if "Web form only" in leakage: score += 12
        if "No after-hours response" in leakage: score += 10
        if "No online booking" in leakage: score += 8
        if c.get("reviewCount", 0) > 100: score += 10
        if c.get("reviewCount", 0) > 300: score += 5

        estimated_loss = len(leakage) * avg_value * 2

        website = c.get("website") or ""
        domain = website.replace("https://","").replace("http://","").replace("www.","").split("/")[0]

        businesses.append({
            "name": c.get("name", "Unknown Clinic"),
            "area": c.get("area", city),
            "phone": c.get("phone") or "Check website",
            "email": f"info@{domain}" if domain else "Check website",
            "website": c.get("website"),
            "hasWebsite": bool(c.get("website")),
            "hasWhatsApp": c.get("hasWhatsApp", False),
            "rating": c.get("rating", 4.0),
            "reviewCount": c.get("reviewCount", 20),
            "leakageSignals": leakage,
            "score": min(score, 95),
            "estimatedMonthlyLoss": estimated_loss,
            "sources": ["Live Google Search"],
            "status": "new",
            "contacted": False,
            "isRealData": True,
        })

    return {"success": True, "businesses": businesses, "count": len(businesses)}

@app.post("/enrich")
def enrich(req: EnrichRequest):
    prompt = f"""You are a revenue intelligence analyst for Lexbridge Intelligence.

Analyse this UK private clinic and identify their specific revenue leakage pattern.

Business: {req.name}
Location: {req.area}
Rating: {req.rating} ({req.reviewCount} reviews)
Leakage Signals: {', '.join(req.leakageSignals)}
Niche: {NICHE_LABELS.get(req.niche, 'private clinic')}

Output exactly three short paragraphs:
LEAKAGE TYPE: (their most likely revenue leakage)
REVENUE AT RISK: (conservative monthly estimate in £)
OPENING QUESTION: (one question for Terry to open the call with)

Keep each under 2 sentences. Never mention AI, chatbots, or software."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    return {"success": True, "analysis": text}
