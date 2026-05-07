from textwrap import dedent

from crewai import Agent, Task

from llm_manager import LLMManager
from schemas import (
    ApplicationKit,
    OutreachResult,
    ProfileSummary,
    RankedRecruiters,
    ResearchCandidates,
)
from tools import RecruiterSearchTool


class RecruiterOutreachAgents:
    def __init__(self):
        self.llm = LLMManager.get_llm()

    def profile_agent(self):
        return Agent(
            role="Senior Career Strategist",
            goal="Analyze resumes to extract key skills, achievements, and professional narrative.",
            backstory=dedent(
                """\
                You are a world-class career coach. You can look at a messy resume and identify
                the core value proposition of a candidate. You are obsessive about "Show, Don't Tell"."""
            ),
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
        )

    def application_agent(self):
        return Agent(
            role="Job Application Specialist",
            goal="Craft tailored job application materials based on a JD and candidate profile.",
            backstory=dedent(
                """\
                You are an expert at tailoring job applications. You map a candidate's specific
                skills to the requirements in a job description. Your writing style is professional,
                modern, and punchy."""
            ),
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
        )

    def research_agent(self):
        return Agent(
            role="Lead Recruitment Researcher",
            goal="Find recruiters and talent acquisition specialists at target companies.",
            backstory=dedent(
                """\
                You are an expert researcher. You know how to find the right people on LinkedIn.
                You are tenacious, skeptical, and careful not to invent profiles."""
            ),
            tools=[RecruiterSearchTool()],
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
        )

    def ranking_agent(self):
        return Agent(
            role="Candidate Relevance Strategist",
            goal="Rank recruiters based on their relevance to the specific job role.",
            backstory=dedent(
                """\
                You understand recruiting org structures. You know that an engineering recruiter
                is usually better for software roles than a generic HR manager."""
            ),
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
        )

    def copywriter_agent(self):
        return Agent(
            role="High-Conversion Outreach Copywriter",
            goal="Draft effective, personalized LinkedIn connection messages that get responses.",
            backstory=dedent(
                """\
                You are a top-tier recruiter and career coach who knows how to get a hiring team's
                attention without sounding generic, needy, or overfamiliar."""
            ),
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
        )


class RecruiterOutreachTasks:
    def profile_parsing_task(self, agent, resume_text):
        return Task(
            description=dedent(
                f"""\
                Analyze the following resume text and extract a structured summary.

                Resume text:
                {resume_text}

                Requirements:
                1. Identify key technical and soft skills.
                2. Summarize the top 3 professional achievements using specific evidence.
                3. Create a short professional bio in 2 sentences.

                Return valid JSON only:
                {{
                    "skills": ["skill"],
                    "achievements": ["achievement"],
                    "bio": "2 sentence professional bio"
                }}
                """
            ),
            agent=agent,
            expected_output="A JSON object with skills, achievements, and bio.",
            output_json=ProfileSummary,
        )

    def application_drafting_task(self, agent, user_profile_summary, job_description):
        return Task(
            description=dedent(
                f"""\
                Create a tailored application kit for the job description using the candidate profile.

                Candidate profile:
                {user_profile_summary}

                Job description:
                {job_description}

                Deliverables:
                1. Cold DM: a LinkedIn message to the hiring manager, max 75 words.
                2. Cover letter/email: a short email pitch, max 200 words.

                Use only facts present in the candidate profile and job description.
                Do not invent employers, metrics, credentials, or shared connections.

                Return valid JSON only:
                {{
                    "cold_dm": "LinkedIn message under 75 words",
                    "cover_letter": "Email pitch under 200 words"
                }}
                """
            ),
            agent=agent,
            expected_output="A JSON object with cold_dm and cover_letter.",
            output_json=ApplicationKit,
        )

    def research_task(self, agent, company_name, job_role, context=None):
        return Task(
            description=dedent(
                f"""\
                Find recruiter profiles for company="{company_name}" and role="{job_role}".

                Use the Recruiter Search tool with both inputs:
                - company_name: "{company_name}"
                - job_role: "{job_role}"

                Search for role-relevant recruiting titles, including Technical Recruiter,
                Engineering Recruiter, Talent Acquisition Partner, Sourcer, Campus Recruiter,
                and Executive Recruiter.

                Return only profiles with evidence that they work at or recruit for the target company.
                Do not invent names or URLs. If fewer than 5 credible profiles exist, return only the credible profiles.

                Return valid JSON only:
                {{
                    "candidates": [
                        {{
                            "name": "Recruiter name",
                            "title": "Current title",
                            "linkedin_url": "https://www.linkedin.com/in/...",
                            "evidence": "Search result evidence for company and role relevance",
                            "confidence": 0.0
                        }}
                    ]
                }}
                """
            ),
            agent=agent,
            expected_output="A JSON object containing recruiter candidates.",
            context=context or [],
            output_json=ResearchCandidates,
        )

    def ranking_task(self, agent, company_name, job_role, context=None):
        return Task(
            description=dedent(
                f"""\
                Using only the recruiter candidates from the previous task, rank the best
                3 contacts for role="{job_role}" at company="{company_name}".

                Scoring:
                - 40 points: role-specific recruiting relevance
                - 30 points: current company match
                - 20 points: seniority or ownership of hiring area
                - 10 points: evidence quality

                Do not add new recruiters. Preserve the LinkedIn URLs from the previous task.
                If fewer than 3 credible recruiters are available, return fewer than 3.

                Return valid JSON only:
                {{
                    "recruiters": [
                        {{
                            "recruiter_name": "Name",
                            "title": "Title",
                            "linkedin_url": "https://www.linkedin.com/in/...",
                            "reason_for_ranking": "Specific scoring rationale",
                            "score": 0
                        }}
                    ]
                }}
                """
            ),
            agent=agent,
            expected_output="A JSON object containing up to 3 ranked recruiters.",
            context=context or [],
            output_json=RankedRecruiters,
        )

    def drafting_task(self, agent, company_name, job_role, resume_content=None, context=None):
        personalization_context = ""
        if resume_content:
            personalization_context = dedent(
                f"""\

                Candidate profile context:
                {resume_content}

                Use only these facts to personalize the message. Do not invent metrics, employers,
                schools, projects, or shared connections.
                """
            )

        return Task(
            description=dedent(
                f"""\
                Write one personalized LinkedIn connection message for each ranked recruiter.

                Target company: {company_name}
                Target role: {job_role}

                Strict rules:
                - Keep each message under 75 words.
                - Do not start with "I hope you are doing well".
                - Do not ask for a coffee chat.
                - Mention the target role exactly once.
                - Use only candidate facts provided in the profile context.
                - Do not claim a shared background, referral, metric, or company project unless it appears in the context.
                - Preserve the recruiter name, LinkedIn URL, and ranking reason from the ranking task.
                {personalization_context}

                Return valid JSON only:
                {{
                    "recruiters": [
                        {{
                            "recruiter_name": "Name",
                            "linkedin_url": "https://www.linkedin.com/in/...",
                            "reason_for_ranking": "Reason",
                            "draft_message": "Message under 75 words"
                        }}
                    ]
                }}
                """
            ),
            agent=agent,
            expected_output="A JSON object containing up to 3 outreach messages.",
            context=context or [],
            output_json=OutreachResult,
        )
