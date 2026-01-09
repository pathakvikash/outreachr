# Outreachr

This project automates the process of finding and drafting outreach messages to recruiters using a multi-agent system powered by CrewAI.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Variables**:
    Create a `.env` file in the root directory or set the variables.

    Required:
    - `OPENAI_API_KEY`: API key for your LLM provider (e.g., OpenAI).

    Optional:
    - `TAVILY_API_KEY`: API key for Tavily Search (required for real search).
    - `MOCK_SEARCH`: Set to `True` (case-insensitive) to use mock search results (no API key needed).
    - `DATABASE_URL`: Connection string for SQLAlchemy (defaults to `sqlite:///recruiter_outreach.db`).

## Usage

Run the script with the company name and target role:

```bash
python main.py --company "Google" --role "Software Engineer"
```
