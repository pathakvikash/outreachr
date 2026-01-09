import os
import json
import datetime
import argparse
from typing import List, Dict
from crewai import Crew, Process
from dotenv import load_dotenv
from pypdf import PdfReader

from models import init_db, get_db, RecruiterOutreach, UsageLog, UserProfile
from agents import RecruiterOutreachAgents, RecruiterOutreachTasks

# Load environment variables
load_dotenv()

def save_user_profile(raw_text: str, summary_json: str):
    """Save or update the user profile."""
    try:
        db = next(get_db())
        # Check if profile exists (Single User Mode)
        profile = db.query(UserProfile).first()
        if profile:
            profile.raw_text = raw_text
            profile.summary_json = summary_json
            profile.updated_at = datetime.datetime.utcnow()
        else:
            profile = UserProfile(raw_text=raw_text, summary_json=summary_json)
            db.add(profile)
        db.commit()
    except Exception as e:
        print(f"Error saving profile: {e}")

def get_user_profile() -> Dict:
    """Fetch the user profile."""
    db = next(get_db())
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
        db = next(get_db())
        
        if usage_metrics is None:
            return
  
        prompt_tokens = usage_metrics.get("prompt_tokens", 0)
        completion_tokens = usage_metrics.get("completion_tokens", 0)
        total_tokens = usage_metrics.get("total_tokens", 0)
        
        log = UsageLog(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            total_cost=0.0 
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Error saving usage log: {e}")

def get_recent_outreach(company: str, role: str) -> List[Dict]:
    """Check database for outreach generated in the last 24 hours."""
    db = next(get_db())
    one_day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    
    results = db.query(RecruiterOutreach).filter(
        RecruiterOutreach.company_name == company,
        RecruiterOutreach.job_role == role,
        RecruiterOutreach.created_at >= one_day_ago
    ).all()
    
    return [r.to_dict() for r in results]

def save_outreach(company: str, role: str, outreach_data: List[Dict]):
    """Save generated outreach to database (Upsert)."""
    db = next(get_db())
    for item in outreach_data:
        existing = db.query(RecruiterOutreach).filter(
            RecruiterOutreach.company_name == company,
            RecruiterOutreach.job_role == role,
            RecruiterOutreach.linkedin_url == item.get("linkedin_url")
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
                recruiter_name=item.get("recruiter_name"),
                linkedin_url=item.get("linkedin_url"),
                reason_for_ranking=item.get("reason_for_ranking"),
                draft_message=item.get("draft_message")
            )
            db.add(record)
    db.commit()

def clean_json_output(output_str: str) -> List[Dict]:
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

    # 1. Check Cache (Skip if force_refresh is True)
    if not force_refresh:
        recent_outreach = get_recent_outreach(company_name, job_role)
        if recent_outreach and not resume_content: # Only use cache if no resume provided (personalization changes output)
             return {"results": recent_outreach, "usage": None}

    # 2. Setup Agents and Tasks
    agents = RecruiterOutreachAgents()
    tasks = RecruiterOutreachTasks()

    research_agent = agents.research_agent()
    ranking_agent = agents.ranking_agent()
    copywriter_agent = agents.copywriter_agent()

    research_task = tasks.research_task(research_agent, company_name, job_role)
    ranking_task = tasks.ranking_task(ranking_agent, company_name, job_role)
    drafting_task = tasks.drafting_task(copywriter_agent, resume_content) # Pass resume content

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
    usage = {}
    try:
        raw_usage = None
        if hasattr(crew, 'usage_metrics'):
             raw_usage = crew.usage_metrics
        elif hasattr(result, 'token_usage'):
             raw_usage = result.token_usage
        
        if raw_usage:
            # Convert object to dict to ensure .get() works downstream
            if isinstance(raw_usage, dict):
                usage = raw_usage
            elif hasattr(raw_usage, 'model_dump'): # Pydantic v2
                usage = raw_usage.model_dump()
            elif hasattr(raw_usage, 'dict'): # Pydantic v1
                usage = raw_usage.dict()
            else:
                # Fallback: access attributes directly
                usage = {
                    "prompt_tokens": getattr(raw_usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(raw_usage, "completion_tokens", 0),
                    "total_tokens": getattr(raw_usage, "total_tokens", 0),
                    "total_cost": getattr(raw_usage, "total_cost", 0.0)
                }
            
            # Save to DB
            save_usage_log(usage)
            
    except Exception as e:
        print(f"Could not extract usage metrics: {e}")

    # 5. Parse and Save Results
    try:
        output_str = str(result)
        outreach_data = clean_json_output(output_str)
        
        if outreach_data:
            save_outreach(company_name, job_role, outreach_data)
            return {"results": outreach_data, "usage": usage}
        else:
            print("Failed to generate valid outreach data.")
            print(f"Raw Output: {output_str}")
            return {"results": [], "usage": usage}

    except Exception as e:
        print(f"An error occurred: {e}")
        return {"results": [], "usage": usage}

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
    
    # Usage Tracking (Simplified repetition of logic - could be refactored)
    usage = {}
    if hasattr(crew, 'usage_metrics'):
         usage = crew.usage_metrics if isinstance(crew.usage_metrics, dict) else crew.usage_metrics.dict()
         save_usage_log(usage)

    summary_json = str(result)
    # Clean JSON
    parsed = clean_json_output(summary_json)
    
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
    
    usage = {}
    if hasattr(crew, 'usage_metrics'):
         usage = crew.usage_metrics if isinstance(crew.usage_metrics, dict) else crew.usage_metrics.dict()
         save_usage_log(usage)

    output = clean_json_output(str(result))
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
