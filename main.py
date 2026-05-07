import os
import json
import datetime
import argparse
import hashlib
from typing import Any, Dict, List, Optional
from crewai import Crew, Process
from dotenv import load_dotenv
from pypdf import PdfReader

from models import db_session, init_db, RecruiterOutreach, UsageLog, UserProfile
from agents import RecruiterOutreachAgents, RecruiterOutreachTasks

# Load environment variables
load_dotenv()

PROMPT_VERSION = "2026-05-07"


def normalize_key(value: str) -> str:
    """Normalize cache key inputs so whitespace/case changes do not miss cache."""
    return " ".join((value or "").strip().lower().split())


def get_profile_hash(profile_context: Optional[str]) -> str:
    if not profile_context:
        return "no-profile"
    return hashlib.sha256(profile_context.encode("utf-8")).hexdigest()[:16]


def get_search_mode() -> str:
    return "mock" if os.getenv("MOCK_SEARCH", "False").lower() == "true" else "real"

def save_user_profile(raw_text: str, summary_json: str):
    """Save or update the user profile."""
    try:
        with db_session() as db:
            # Single-user MVP profile. Add user_id before deploying this as multi-user.
            profile = db.query(UserProfile).first()
            if profile:
                profile.raw_text = raw_text
                profile.summary_json = summary_json
                profile.updated_at = datetime.datetime.utcnow()
            else:
                profile = UserProfile(raw_text=raw_text, summary_json=summary_json)
                db.add(profile)
    except Exception as e:
        print(f"Error saving profile: {e}")

def get_user_profile() -> Dict:
    """Fetch the user profile."""
    with db_session() as db:
        profile = db.query(UserProfile).first()
        if profile:
            return {
                "raw_text": profile.raw_text,
                "summary_json": profile.summary_json,
                "updated_at": profile.updated_at
            }
    return None

def save_usage_log(usage_metrics: dict):
    """Save crew usage metrics to database."""
    try:
        if usage_metrics is None:
            return

        prompt_tokens = usage_metrics.get("prompt_tokens", 0)
        completion_tokens = usage_metrics.get("completion_tokens", 0)
        total_tokens = usage_metrics.get("total_tokens", 0)

        with db_session() as db:
            log = UsageLog(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                total_cost=usage_metrics.get("total_cost", 0.0) or 0.0,
            )
            db.add(log)
    except Exception as e:
        print(f"Error saving usage log: {e}")

def get_recent_outreach(
    company: str,
    role: str,
    profile_hash: str,
    prompt_version: str,
    search_mode: str,
) -> List[Dict]:
    """Check database for outreach generated in the last 24 hours."""
    one_day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)

    with db_session() as db:
        results = db.query(RecruiterOutreach).filter(
            RecruiterOutreach.company_name == company,
            RecruiterOutreach.job_role == role,
            RecruiterOutreach.profile_hash == profile_hash,
            RecruiterOutreach.prompt_version == prompt_version,
            RecruiterOutreach.search_mode == search_mode,
            RecruiterOutreach.created_at >= one_day_ago
        ).all()

        return [r.to_dict() for r in results]

def save_outreach(
    company: str,
    role: str,
    outreach_data: List[Dict],
    profile_hash: str,
    prompt_version: str,
    search_mode: str,
):
    """Save generated outreach to database (Upsert)."""
    with db_session() as db:
        for item in outreach_data:
            linkedin_url = str(item.get("linkedin_url", "")).strip()
            if not linkedin_url:
                continue

            existing = db.query(RecruiterOutreach).filter(
                RecruiterOutreach.company_name == company,
                RecruiterOutreach.job_role == role,
                RecruiterOutreach.linkedin_url == linkedin_url,
                RecruiterOutreach.profile_hash == profile_hash,
                RecruiterOutreach.prompt_version == prompt_version,
                RecruiterOutreach.search_mode == search_mode,
            ).first()

            if existing:
                existing.recruiter_name = item.get("recruiter_name")
                existing.reason_for_ranking = item.get("reason_for_ranking")
                existing.draft_message = item.get("draft_message")
                existing.created_at = datetime.datetime.utcnow()
            else:
                record = RecruiterOutreach(
                    company_name=company,
                    job_role=role,
                    profile_hash=profile_hash,
                    prompt_version=prompt_version,
                    search_mode=search_mode,
                    recruiter_name=item.get("recruiter_name"),
                    linkedin_url=linkedin_url,
                    reason_for_ranking=item.get("reason_for_ranking"),
                    draft_message=item.get("draft_message")
                )
                db.add(record)

def clean_json_output(output_str: str) -> Any:
    """Clean and parse JSON output from LLM."""
    try:
        # Remove markdown code blocks if present
        cleaned = output_str.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print(f"Raw output: {output_str}")
        return []


def object_to_dict(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return to_json_safe(value)
    if hasattr(value, "model_dump"):
        return to_json_safe(value.model_dump(mode="json"))
    if hasattr(value, "dict"):
        return to_json_safe(value.dict())
    return None


def to_json_safe(value: Any) -> Any:
    """Recursively convert Pydantic/LiteLLM helper types into JSON-native values."""
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [to_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    return str(value)


def get_structured_output(task, result) -> Any:
    """Read CrewAI structured task output, falling back to raw JSON cleanup."""
    for candidate in [getattr(task, "output", None), result]:
        if candidate is None:
            continue

        json_dict = getattr(candidate, "json_dict", None)
        if json_dict:
            return json_dict

        pydantic_value = getattr(candidate, "pydantic", None)
        parsed = object_to_dict(pydantic_value)
        if parsed:
            return parsed

        parsed = object_to_dict(candidate)
        if parsed:
            return parsed

    return clean_json_output(str(result))


def extract_outreach_items(parsed_output: Any) -> List[Dict]:
    if isinstance(parsed_output, dict):
        items = parsed_output.get("recruiters", [])
    elif isinstance(parsed_output, list):
        items = parsed_output
    else:
        items = []

    cleaned_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cleaned_items.append({
            "recruiter_name": item.get("recruiter_name", "").strip(),
            "linkedin_url": str(item.get("linkedin_url", "")).strip(),
            "reason_for_ranking": item.get("reason_for_ranking", "").strip(),
            "draft_message": item.get("draft_message", "").strip(),
        })
    return [item for item in cleaned_items if item["recruiter_name"] and item["linkedin_url"]][:3]


def extract_usage_metrics(crew, result=None) -> Dict:
    raw_usage = None
    if hasattr(crew, "usage_metrics"):
        raw_usage = crew.usage_metrics
    elif result is not None and hasattr(result, "token_usage"):
        raw_usage = result.token_usage

    usage = object_to_dict(raw_usage)
    if usage is not None:
        return usage

    if raw_usage:
        return {
            "prompt_tokens": getattr(raw_usage, "prompt_tokens", 0),
            "completion_tokens": getattr(raw_usage, "completion_tokens", 0),
            "total_tokens": getattr(raw_usage, "total_tokens", 0),
            "total_cost": getattr(raw_usage, "total_cost", 0.0),
        }

    return {}


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

def run_recruiter_outreach(company_name: str, job_role: str, resume_content: str = None, force_refresh: bool = False) -> Dict:
    """
    Run the recruiter outreach process: Check cache, or run agents.
    Returns dictionary with 'results' (list) and 'usage' (dict).
    """
    init_db()
    company_key = normalize_key(company_name)
    role_key = normalize_key(job_role)
    profile_hash = get_profile_hash(resume_content)
    search_mode = get_search_mode()

    # 1. Check Cache (Skip if force_refresh is True)
    if not force_refresh:
        recent_outreach = get_recent_outreach(
            company_key,
            role_key,
            profile_hash,
            PROMPT_VERSION,
            search_mode,
        )
        if recent_outreach:
            return {"results": recent_outreach, "usage": None, "cached": True}

    # 2. Setup Agents and Tasks
    agents = RecruiterOutreachAgents()
    tasks = RecruiterOutreachTasks()

    research_agent = agents.research_agent()
    ranking_agent = agents.ranking_agent()
    copywriter_agent = agents.copywriter_agent()

    research_task = tasks.research_task(research_agent, company_name, job_role)
    ranking_task = tasks.ranking_task(ranking_agent, company_name, job_role, context=[research_task])
    drafting_task = tasks.drafting_task(
        copywriter_agent,
        company_name,
        job_role,
        resume_content,
        context=[ranking_task],
    )

    # 3. Create Crew
    crew = Crew(
        agents=[research_agent, ranking_agent, copywriter_agent],
        tasks=[research_task, ranking_task, drafting_task],
        process=Process.sequential,
        verbose=True
    )

    # 4. Run Crew
    result = crew.kickoff()

    # Capture Usage
    try:
        usage = extract_usage_metrics(crew, result)
        if usage:
            save_usage_log(usage)
    except Exception as e:
        print(f"Could not extract usage metrics: {e}")
        usage = {}

    # 5. Parse and Save Results
    try:
        parsed_output = to_json_safe(get_structured_output(drafting_task, result))
        outreach_data = extract_outreach_items(parsed_output)

        if outreach_data:
            save_outreach(
                company_key,
                role_key,
                outreach_data,
                profile_hash,
                PROMPT_VERSION,
                search_mode,
            )
            return {"results": outreach_data, "usage": usage, "cached": False}
        else:
            print("Failed to generate valid outreach data.")
            print(f"Raw Output: {result}")
            return {"results": [], "usage": usage, "cached": False}

    except Exception as e:
        print(f"An error occurred: {e}")
        return {"results": [], "usage": usage, "cached": False}

def run_profile_parsing(resume_text: str) -> Dict:
    """Run the agent to parse and summarize the resume."""
    init_db()
    
    agents = RecruiterOutreachAgents()
    tasks = RecruiterOutreachTasks()
    
    profile_agent = agents.profile_agent()
    parsing_task = tasks.profile_parsing_task(profile_agent, resume_text)
    
    crew = Crew(
        agents=[profile_agent],
        tasks=[parsing_task],
        verbose=True
    )
    
    result = crew.kickoff()

    usage = extract_usage_metrics(crew, result)
    if usage:
        save_usage_log(usage)

    parsed = to_json_safe(get_structured_output(parsing_task, result))

    # Save the RAW text and the SUMMARIZED json
    save_user_profile(resume_text, json.dumps(parsed))
    
    return parsed

def run_job_application(job_description: str) -> Dict:
    """Run the agent to generate application assets."""
    init_db()
    
    # Fetch Profile
    profile = get_user_profile()
    if not profile:
        return {"error": "No profile found. Please upload a resume first."}
    
    # Use Summary if available, else Raw (but Agent expects summary structure preferably)
    profile_context = profile.get("summary_json") or profile.get("raw_text")

    agents = RecruiterOutreachAgents()
    tasks = RecruiterOutreachTasks()
    
    app_agent = agents.application_agent()
    drafting_task = tasks.application_drafting_task(app_agent, profile_context, job_description)
    
    crew = Crew(
        agents=[app_agent],
        tasks=[drafting_task],
        verbose=True
    )
    
    result = crew.kickoff()

    usage = extract_usage_metrics(crew, result)
    if usage:
        save_usage_log(usage)

    output = to_json_safe(get_structured_output(drafting_task, result))
    return {"results": output, "usage": usage}

def main():
    parser = argparse.ArgumentParser(description="Find and draft outreach for recruiters.")
    parser.add_argument("--company", required=True, help="Target Company Name")
    parser.add_argument("--role", required=True, help="Target Job Role")
    parser.add_argument("--resume", help="Path to candidate's resume (PDF)")
    parser.add_argument("--force", action="store_true", help="Force refresh (ignore cache)")
    args = parser.parse_args()

    resume_content = None
    if args.resume:
        resume_content = extract_text_from_pdf(args.resume)
        if not resume_content:
            print("Could not read resume file. Proceeding without personalization.")

    data = run_recruiter_outreach(args.company, args.role, resume_content, force_refresh=args.force)
    print("USAGE METRICS:", data.get("usage"))
    print(json.dumps(data.get("results"), indent=2))

if __name__ == "__main__":
    main()
