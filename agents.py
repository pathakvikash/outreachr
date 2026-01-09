from crewai import Agent, Task
from textwrap import dedent
from tools import RecruiterSearchTool
from llm_manager import LLMManager

class RecruiterOutreachAgents:
    def __init__(self):
        self.llm = LLMManager.get_llm()

    def profile_agent(self):
        return Agent(
            role='Senior Career Strategist',
            goal='Analyze resumes to extract key skills, achievements, and professional narrative.',
            backstory=dedent("""\
                You are a world-class career coach. You can look at a messy resume and identify 
                the core value proposition of a candidate. You are obsessive about "Show, Don't Tell"."""),
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def application_agent(self):
        return Agent(
            role='Job Application Specialist',
            goal='Craft tailored job application materials (Cover Letter, Cold DM) based on JD and Candidate Profile.',
            backstory=dedent("""\
                You are an expert at tailoring job applications. You know how to map a candidate's 
                specific skills to the requirements in a Job Description. 
                Your writing style is professional yet modern and punchy."""),
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def research_agent(self):
        return Agent(
            role='Lead Recruitment Researcher',
            goal='Find recruiters and talent acquisition specialists at target companies.',
            backstory=dedent("""\
                You are an expert researcher. You know how to find the right people on LinkedIn.
                You are tenacious and creative in your search queries."""),
            tools=[RecruiterSearchTool()],
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def ranking_agent(self):
        return Agent(
            role='Candidate Relevance Strategist',
            goal='Rank recruiters based on their relevance to the specific job role.',
            backstory=dedent("""\
                You understand organizational structures. You know that a 'Technical Recruiter' 
                is better for engineering roles than a generic 'HR Manager'."""),
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def copywriter_agent(self):
        return Agent(
            role='High-Conversion Outreach Copywriter',
            goal='Draft highly effective, personalized LinkedIn connection messages that get responses.',
            backstory=dedent("""\
                You are a top-tier recruiter and career coach who knows exactly how to get a hiring manager's attention.
                You strictly follow a 4-part structure for cold DMs:
                1. The Hook (Personalization): Specific mention of their role or company news.
                2. The "Why You" (Value Prop): One sentence on relevant experience/achievement.
                3. The "Why Them" (Alignment): Why you want THIS specific company.
                4. The Low-Friction CTA: Ask for a connection or referral, never a "coffee chat"."""),
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

class RecruiterOutreachTasks:
    def profile_parsing_task(self, agent, resume_text):
        return Task(
            description=dedent(f"""\
                Analyze the following resume text and extract a structured summary.
                
                **Resume Text**:
                {resume_text}
                
                **Requirements**:
                1. Identify Key Skills (Technical & Soft).
                2. Summarize top 3 Professional Achievements (STAR method).
                3. Create a short "Professional Bio" (2 sentences).
                
                Return the output as a JSON object with keys: "skills", "achievements", "bio".
                IMPORTANT: Return PURE JSON.
                """),
            agent=agent,
            expected_output="A JSON object with skills, achievements, and bio."
        )

    def application_drafting_task(self, agent, user_profile_summary, job_description):
        return Task(
            description=dedent(f"""\
                Create a tailored application kit for the following Job Description using the Candidate's Profile.
                
                **Candidate Profile**:
                {user_profile_summary}
                
                **Job Description**:
                {job_description}
                
                **Deliverables**:
                1. **Cold DM**: A LinkedIn message to the hiring manager (max 75 words).
                2. **Cover Letter / Email**: A short, punchy email pitch (max 200 words).
                
                Return the output as a JSON object with keys: "cold_dm", "cover_letter".
                IMPORTANT: Return PURE JSON.
                """),
            agent=agent,
            expected_output="A JSON object with cold_dm and cover_letter."
        )

    def research_task(self, agent, company_name, job_role):
        return Task(
            description=dedent(f"""\
                Find at least 5 recruiters at {company_name} who might be hiring for a {job_role}.
                Use the Recruiter Search tool to find profiles.
                Return a list of Recruiter profiles including Name, Title, and LinkedIn URL.
                """),
            agent=agent,
            expected_output="A list of 5 recruiter profiles with Name, Title, and URL."
        )

    def ranking_task(self, agent, company_name, job_role):
        return Task(
            description=dedent(f"""\
                Analyze the list of recruiters found for {company_name}.
                Select the top 3 recruiters who are most relevant for a {job_role}.
                Explain why you chose them.
                """),
            agent=agent,
            expected_output="Top 3 ranked recruiters with reasons for their selection."
        )

    def drafting_task(self, agent, resume_content: str = None):
        personalization_context = ""
        if resume_content:
            personalization_context = f"\n\nHere is the candidate's resume content:\n{resume_content}\n\nUse this information to personalize the message, highlighting relevant experience matches."

        return Task(
            description=dedent(f"""\
                Draft a personalized LinkedIn connection message (max 75 words) for each of the top 3 recruiters.
                
                **Strict Rules of Engagement:**
                - Keep it under 75 words.
                - NO "I hope you are doing well". Start directly with the hook.
                - NO "coffee chat" requests.
                - Mention the specific Job Role.
                - Do NOT say "I'm looking for any job".
                
                **Use one of these 4 Templates based on the context:**
                
                1. **The "Direct Application" Follow-up** (If applying to a specific req):
                   "Hi [Name], I recently applied for the [Job Title] role and noticed you lead recruitment for [Department]. With [X] years in [Skill], I’ve helped companies like [Previous] achieve [Metric]. Would you be open to a brief chat, or is there someone else I should connect with?"
                   
                2. **The "Strategic Inquiry"** (Hidden Job Market):
                   "Hi [Name], I’ve been following [Company]’s work on [Project]. I’m a [Role] specializing in [Skill]. Are you planning to expand your [Department] team this quarter? If so, I’d love to share my portfolio."
                   
                3. **The "Post-Referral" / Connection**:
                   "Hi [Name], I saw we both [Commonality]. I’m currently a [Role] at [Current] and very interested in the [Job Title] opening. Given my background in [Skill], I thought I might be a fit. Do you have advice on how to stand out?"
                   
                4. **The "Short & Punchy"**:
                   "Hi [Name], I’m a [Role] focused on [Skill]. I just applied for the [Job Title] role. I’d love to discuss how my background in [Achievement] aligns with [Company]'s goals. Are you the right person to speak with?"
                
                {personalization_context}
                
                Return the final output as a JSON object with the following schema:
                [
                    {{
                        "recruiter_name": "Name",
                        "linkedin_url": "URL",
                        "reason_for_ranking": "Reason",
                        "draft_message": "Message"
                    }},
                    ...
                ]
                IMPORTANT: Ensure the output is PURE JSON, nothing else.
                """),
            agent=agent,
            expected_output="A JSON list of object containing recruiter_name, linkedin_url, reason_for_ranking, and draft_message."
        )
