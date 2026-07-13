from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import os
import json
import re
import traceback

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

class AuditRequest(BaseModel):
    url: str
    bizName: str = ""

@app.get("/health")
def health():
    return {"status": "ok", "live": True}

@app.post("/search")
def search(req: SearchRequest):
    niche_label = NICHE_LABELS.get(req.niche, "private clinic")
    avg_value = AVG_VALUES.get(req.niche, 3000)
    city = req.location.split(",")[0].strip()
    prompt = f"""Search the web for real "{niche_label}" businesses in "{req.location}" UK. Find up to {req.maxResults} REAL businesses. Return a JSON array only:\n[\n  {{\n    "name": "Full clinic name",\n    "area": "{city}",\n    "phone": "phone number or null",\n    "website": "full URL or null",\n    "rating": 4.2,\n    "reviewCount": 87,\n    "hasWhatsApp": false,\n    "hasWebsite": true,\n    "leakageSignals": ["No WhatsApp", "Web form only"]\n  }}\n]\nleakageSignals pick 2-4 from: "No WhatsApp", "Web form only", "No after-hours response", "No online booking", "Phone only", "Limited hours", "Single coordinator likely"\nReturn ONLY the JSON array. No markdown. No explanation."""
    response = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, tools=[{"type": "web_search_20250305", "name": "web_search"}], messages=[{"role": "user", "content": prompt}])
    raw = "".join(block.text for block in response.content if hasattr(block, "text"))
    match = re.search(r'\[[\s\S]*\]', raw)
    if not match:
        return {"success": False, "error": "No clinic data found", "businesses": []}
    try:
        clinics = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"success": False, "error": "Failed to parse", "businesses": []}
    businesses = []
    for c in clinics:
        leakage = c.get("leakageSignals", [])
        score = 50
        if not c.get("hasWhatsApp", True): score += 15
        if "Web form only" in leakage: score += 12
        if "No after-hours response" in leakage: score += 10
        if "No online booking" in leakage: score += 8
        if c.get("reviewCount", 0) > 100: score += 10
        website = c.get("website") or ""
        domain = website.replace("https://","").replace("http://","").replace("www.","").split("/")[0]
        businesses.append({"name": c.get("name","Unknown Clinic"), "area": c.get("area", city), "phone": c.get("phone") or "Check website", "email": f"info@{domain}" if domain else "Check website", "website": c.get("website"), "hasWebsite": bool(c.get("website")), "hasWhatsApp": c.get("hasWhatsApp", False), "rating": c.get("rating", 4.0), "reviewCount": c.get("reviewCount", 20), "leakageSignals": leakage, "score": min(score, 95), "estimatedMonthlyLoss": len(leakage) * AVG_VALUES.get(req.niche, 3000) * 2, "sources": ["Live Google Search"], "status": "new", "contacted": False, "isRealData": True})
    return {"success": True, "businesses": businesses, "count": len(businesses)}

@app.post("/enrich")
def enrich(req: EnrichRequest):
    prompt = f"""Revenue intelligence analyst for Lexbridge Intelligence.\nBusiness: {req.name}\nLocation: {req.area}\nRating: {req.rating} ({req.reviewCount} reviews)\nLeakage Signals: {', '.join(req.leakageSignals)}\n\nOutput three paragraphs:\nLEAKAGE TYPE: (most likely revenue leakage)\nREVENUE AT RISK: (monthly estimate in £)\nOPENING QUESTION: (one question for Terry to open the call)\n\nKeep each under 2 sentences. Never mention AI, chatbots, or software."""
    response = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=400, messages=[{"role": "user", "content": prompt}])
    return {"success": True, "analysis": "".join(block.text for block in response.content if hasattr(block, "text"))}

@app.post("/audit")
def audit(req: AuditRequest):
    prompt = f"""You are a revenue intelligence analyst for Lexbridge Intelligence. Audit this UK hair transplant clinic website and identify where they are losing revenue.\n\nURL: {req.url}\nClinic: {req.bizName}\n\nSearch the web for this clinic. Then return ONLY this exact JSON structure:\n{{\n  "overallScore": 45,\n  "revenueAtRisk": "£28,000-£42,000",\n  "primaryLeakage": "After-hours enquiry gap",\n  "responseSpeedRisk": "Specific finding about their response speed based on their contact options.",\n  "followUpInfrastructure": "Specific finding about their follow-up systems.",\n  "leakageEstimate": "Conservative monthly revenue at risk calculation.",\n  "lexbridgePitch": "Three sentences Terry can use referencing something specific from this clinic website.",\n  "recommendedTier": "Intelligence",\n  "tierPrice": "£749/mo (60-day free trial)",\n  "keyFindings": ["Finding 1", "Finding 2", "Finding 3", "Finding 4"],\n  "sections": {{\n    "responseSpeed": {{"score": 30, "status": "fail", "findings": [{{"status": "fail", "label": "Label", "detail": "Detail", "impact": "£X,000/month"}}]}},\n    "followUp": {{"score": 25, "status": "fail", "findings": [{{"status": "fail", "label": "Label", "detail": "Detail", "impact": "£X,000/month"}}]}},\n    "booking": {{"score": 50, "status": "warn", "findings": [{{"status": "warn", "label": "Label", "detail": "Detail", "impact": "£X,000/month"}}]}},\n    "afterHours": {{"score": 20, "status": "fail", "findings": [{{"status": "fail", "label": "Label", "detail": "Detail", "impact": "£X,000/month"}}]}}\n  }},\n  "priorityFixes": [\n    {{"rank": 1, "title": "Fix title", "description": "Description", "value": "£X,000/month"}},\n    {{"rank": 2, "title": "Fix title", "description": "Description", "value": "£X,000/month"}},\n    {{"rank": 3, "title": "Fix title", "description": "Description", "value": "£X,000/month"}}\n  ]\n}}\n\nBe specific to THIS clinic. Return ONLY valid JSON."""
    try:
        response = client.messages.create(model="claude-sonnet-4-6", max_tokens=2000, tools=[{"type": "web_search_20250305", "name": "web_search"}], messages=[{"role": "user", "content": prompt}])
        raw = "".join(block.text for block in response.content if hasattr(block, "text"))
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            return {"success": True, "audit": json.loads(match.group(0))}
        return {"success": False, "error": "Could not parse response", "raw": raw[:300]}
    except Exception as e:
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "traceback": traceback.format_exc()}
