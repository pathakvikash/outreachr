import os
import json
import re
from crewai.tools import BaseTool

class RecruiterSearchTool(BaseTool):
    name: str = "Recruiter Search"
    description: str = (
        "Search for recruiters on LinkedIn using their titles. "
        "Inputs: company_name and optional job_role. "
        "Useful for finding role-relevant recruiter, sourcer, and talent acquisition profiles."
    )

    def _run(self, company_name: str, job_role: str = "") -> str:
        """
        Search for recruiters for the given company and role.
        """
        company_name = (company_name or "").strip()
        job_role = (job_role or "").strip()
        api_key = os.getenv("TAVILY_API_KEY")
        mock_search = os.getenv("MOCK_SEARCH", "False").lower() == "true"

        if mock_search:
            return self._mock_search(company_name, job_role)

        if not api_key:
            return "Error: TAVILY_API_KEY is not set. Enable MOCK_SEARCH or provide an API key."

        try:
            from tavily import TavilyClient
            tavily = TavilyClient(api_key=api_key)

            role_terms = f'("{job_role}" OR "{self._role_family(job_role)}")' if job_role else ""
            queries = [
                (
                    f'site:linkedin.com/in/ "{company_name}" '
                    f'("Technical Recruiter" OR "Engineering Recruiter" OR "Talent Acquisition" '
                    f'OR Sourcer OR Recruiter) {role_terms}'
                ).strip(),
                f'site:linkedin.com/in/ "{company_name}" ("Recruiter" OR "Talent Acquisition" OR Sourcer)',
                f'"{company_name}" recruiter LinkedIn',
            ]

            results = []
            seen_urls = set()
            for query in queries:
                response = tavily.search(query=query, search_depth="basic", max_results=10)
                for result in response.get("results", []):
                    url = result.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    results.append({
                        "title": result.get("title", ""),
                        "url": url,
                        "snippet": result.get("content", ""),
                    })
                if len(results) >= 5:
                    break

            return json.dumps(results, indent=2)

        except ImportError:
            return "Error: 'tavily' package not found. Please install it."
        except Exception as e:
            return f"Error during search: {str(e)}"

    def _mock_search(self, company_name: str, job_role: str = "") -> str:
        """
        Return mock search results.
        """
        company_slug = self._slugify(company_name)
        role_text = job_role or "target"
        return json.dumps([

            {
                "title": f"John Doe - Technical Recruiter at {company_name} | LinkedIn",
                "url": f"https://www.linkedin.com/in/johndoe-{company_slug}",
                "snippet": f"Experienced Technical Recruiter at {company_name} specializing in {role_text} roles."
            },
            {
                "title": f"Jane Smith - Talent Acquisition Manager at {company_name}",
                "url": f"https://www.linkedin.com/in/janesmith-{company_slug}",
                "snippet": f"Leading Talent Acquisition at {company_name} for {role_text} hiring."
            },
            {
                "title": f"Mike Ross - HR Manager at {company_name}",
                "url": f"https://www.linkedin.com/in/mikeross-{company_slug}",
                "snippet": f"HR Manager at {company_name} focusing on employee relations and recruitment."
            },
             {
                "title": f"Sarah Connor - Technical Recruiter at {company_name}",
                "url": f"https://www.linkedin.com/in/sarahconnor-{company_slug}",
                "snippet": f"Technical Recruiter at {company_name} for {role_text} candidates."
            },
             {
                "title": f"Kyle Reese - Senior Recruiter at {company_name}",
                "url": f"https://www.linkedin.com/in/kylereese-{company_slug}",
                "snippet": f"Senior Recruiter at {company_name} with hiring ownership across technical teams."
            }
        ], indent=2)

    def _role_family(self, job_role: str) -> str:
        role = job_role.lower()
        if any(term in role for term in ["software", "engineer", "developer", "data", "machine learning", "ai"]):
            return "engineering"
        if any(term in role for term in ["sales", "account executive", "business development"]):
            return "sales"
        if any(term in role for term in ["product", "designer", "ux", "ui"]):
            return "product"
        return "recruiting"

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "company"
