import os
import json
from crewai.tools import BaseTool

class RecruiterSearchTool(BaseTool):
    name: str = "Recruiter Search"
    description: str = (
        "Search for recruiters on LinkedIn using their titles. "
        "Useful for finding 'Technical Recruiter', 'Talent Acquisition', or 'HR Manager' profiles."
    )

    def _run(self, company_name: str) -> str:
        """
        Search for recruiters for the given company.
        """
        api_key = os.getenv("TAVILY_API_KEY")
        mock_search = os.getenv("MOCK_SEARCH", "False").lower() == "true"

        if mock_search:
            return self._mock_search(company_name)
        
        if not api_key:
            return "Error: TAVILY_API_KEY is not set. Enable MOCK_SEARCH or provide an API key."

        try:
            from tavily import TavilyClient
            tavily = TavilyClient(api_key=api_key)
            
            query = f"site:linkedin.com/in/ \"{company_name}\" AND (\"Technical Recruiter\" OR \"Talent Acquisition\" OR \"HR Manager\")"
            response = tavily.search(query=query, search_depth="basic", max_results=5)
            
            results = []
            for result in response.get("results", []):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", "")
                })
            return json.dumps(results, indent=2)

        except ImportError:
            return "Error: 'tavily' package not found. Please install it."
        except Exception as e:
            return f"Error during search: {str(e)}"

    def _mock_search(self, company_name: str) -> str:
        """
        Return mock search results.
        """
        return json.dumps([

            {
                "title": f"John Doe - Technical Recruiter at {company_name} | LinkedIn",
                "url": f"https://www.linkedin.com/in/johndoe-{company_name}",
                "snippet": f"Experienced Technical Recruiter at {company_name} specializing in engineering roles."
            },
            {
                "title": f"Jane Smith - Talent Acquisition Manager at {company_name}",
                "url": f"https://www.linkedin.com/in/janesmith-{company_name}",
                "snippet": f"Leading Talent Acquisition at {company_name}. Passionate about building great teams."
            },
            {
                "title": f"Mike Ross - HR Manager at {company_name}",
                "url": f"https://www.linkedin.com/in/mikeross-{company_name}",
                "snippet": f"HR Manager at {company_name} focusing on employee relations and recruitment."
            },
             {
                "title": f"Sarah Connor - Technical Recruiter at {company_name}",
                "url": f"https://www.linkedin.com/in/sarahconnor-{company_name}",
                "snippet": f"Technical Recruiter at {company_name}."
            },
             {
                "title": f"Kyle Reese - Senior Recruiter at {company_name}",
                "url": f"https://www.linkedin.com/in/kylereese-{company_name}",
                "snippet": f"Senior Recruiter at {company_name}."
            }
        ], indent=2)
