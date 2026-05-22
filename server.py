import os
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP

VALID_STAGES = [
    "new",
    "contacted",
    "qualified",
    "proposal",
    "won",
    "lost",
]

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY", "")

REST_BASE_URL = f"{SUPABASE_URL}/rest/v1"

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
}

mcp = FastMCP("sales-assistant")


def get_company_by_name(company_name: str):
    params = {
        "name": f"eq.{company_name}",
        "select": "id,name,industry,stage",
        "limit": "1",
    }

    response = httpx.get(
        f"{REST_BASE_URL}/companies",
        headers=HEADERS,
        params=params,
        timeout=20.0,
    )
    response.raise_for_status()

    rows = response.json()
    if not rows:
        return None

    return rows[0]


@mcp.tool()
def log_activity(
    company_name: str,
    activity_type: str,
    notes: str,
    happened_at: str = "",
) -> str:
    """Log a sales activity against a named company."""

    company_name = company_name.strip()
    activity_type = activity_type.strip().lower()
    notes = notes.strip()
    happened_at = happened_at.strip()

    if not company_name:
        return "Company name is required."

    if not activity_type:
        return "Activity type is required."

    if not notes:
        return "Notes are required."

    if not SUPABASE_URL or not SUPABASE_API_KEY:
        return "Missing SUPABASE_URL or SUPABASE_API_KEY in .env."

    company = get_company_by_name(company_name)
    if not company:
        return f"Company '{company_name}' was not found. Create it first."

    if not happened_at:
        happened_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "company_id": company["id"],
        "activity_type": activity_type,
        "notes": notes,
        "happened_at": happened_at,
    }

    response = httpx.post(
        f"{REST_BASE_URL}/activity_log",
        headers=HEADERS,
        json=payload,
        timeout=20.0,
    )
    response.raise_for_status()

    return f"Logged {activity_type} for {company['name']} at {happened_at}."

@mcp.tool()
def create_company(name: str, industry: str = "") -> str:
    """Create a new company record in Supabase."""

    name = name.strip()
    industry = industry.strip()

    if not name:
        return "Company name is required."

    if not SUPABASE_URL or not SUPABASE_API_KEY:
        return "Missing SUPABASE_URL or SUPABASE_API_KEY in .env."

    payload = {
        "name": name,
        "industry": industry or None,
    }

    response = httpx.post(
        f"{REST_BASE_URL}/companies",
        headers=HEADERS,
        json=payload,
        timeout=20.0,
    )

    if response.status_code == 409:
        return f"Company '{name}' already exists."

    response.raise_for_status()

    return f"Created company '{name}'."

@mcp.tool()
def get_recent_activity(company_name: str, limit: int = 5) -> str:
    """Get recent activity for a named company."""

    company_name = company_name.strip()

    if not company_name:
        return "Company name is required."

    if limit < 1:
        return "Limit must be at least 1."

    if not SUPABASE_URL or not SUPABASE_API_KEY:
        return "Missing SUPABASE_URL or SUPABASE_API_KEY in .env."

    company = get_company_by_name(company_name)
    if not company:
        return f"Company '{company_name}' was not found."

    params = {
        "company_id": f"eq.{company['id']}",
        "select": "activity_type,notes,happened_at",
        "order": "happened_at.desc",
        "limit": str(limit),
    }

    response = httpx.get(
        f"{REST_BASE_URL}/activity_log",
        headers=HEADERS,
        params=params,
        timeout=20.0,
    )
    response.raise_for_status()

    rows = response.json()

    if not rows:
        return f"No recent activity found for {company['name']}."

    lines = [f"Recent activity for {company['name']}:"]
    for row in rows:
        happened_at = row.get("happened_at", "unknown time")
        activity_type = row.get("activity_type", "activity")
        notes = row.get("notes", "")
        lines.append(f"- {happened_at}: {activity_type} — {notes}")

    return "\n".join(lines)

@mcp.tool()
def get_company(company_name: str) -> str:
    """Get a company record by name."""

    company_name = company_name.strip()

    if not company_name:
        return "Company name is required."

    if not SUPABASE_URL or not SUPABASE_API_KEY:
        return "Missing SUPABASE_URL or SUPABASE_API_KEY in .env."

    company = get_company_by_name(company_name)
    if not company:
        return f"Company '{company_name}' was not found."

    industry = company.get("industry", "")
    if industry:
        return f"Company: {company['name']}\nIndustry: {industry}"

    return f"Company: {company['name']}"

@mcp.tool()
def update_pipeline_stage(company_name: str, stage: str) -> str:
    """Update the pipeline stage for a named company."""

    company_name = company_name.strip()
    stage = stage.strip().lower()

    if not company_name:
        return "Company name is required."

    if not stage:
        return "Stage is required."

    if stage not in VALID_STAGES:
        return f"Invalid stage. Use one of: {', '.join(VALID_STAGES)}."

    if not SUPABASE_URL or not SUPABASE_API_KEY:
        return "Missing SUPABASE_URL or SUPABASE_API_KEY in .env."

    company = get_company_by_name(company_name)
    if not company:
        return f"Company '{company_name}' was not found."

    params = {
        "id": f"eq.{company['id']}",
    }

    payload = {
        "stage": stage,
    }

    response = httpx.patch(
        f"{REST_BASE_URL}/companies",
        headers=HEADERS,
        params=params,
        json=payload,
        timeout=20.0,
    )
    response.raise_for_status()

    return f"Updated {company['name']} to pipeline stage '{stage}'."
    
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)