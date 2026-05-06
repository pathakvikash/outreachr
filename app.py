import streamlit as st
import json
from main import run_recruiter_outreach, run_profile_parsing, get_user_profile

st.set_page_config(page_title="Recruiter Outreach", layout="wide")

st.title("Recruiter Outreach MVP")

# --- Sidebar: User Profile Manager ---
with st.sidebar:
    st.header("My Profile")
    
    # Fetch existing profile
    current_profile = get_user_profile()
    
    if current_profile:
        st.success(f"Profile Active (Last Updated: {current_profile['updated_at'].strftime('%Y-%m-%d %H:%M')})")
        with st.expander("View Stored Summary"):
            try:
                summary_data = json.loads(current_profile['summary_json'])
                st.write("**Bio:**", summary_data.get("bio", "N/A"))
                st.write("**Top Skills:**", ", ".join(summary_data.get("skills", [])))
            except:
                st.text(current_profile['summary_json'])
    else:
        st.info("No profile stored. Upload a resume to get started.")


def parse_pdf(uploaded_file):
    """Helper to extract text from an uploaded PDF file."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None
        
# --- Main Interface ---
tab1, tab2, tab3, tab4 = st.tabs(["New Outreach (Recruiters)", "Job Application Assistant", "History", "Settings"])

# TAB 1: Recruiter Outreach
with tab1:
    st.header("Find Recruiters")
    company_name = st.text_input("Company Name", placeholder="e.g. Google")
    job_role = st.text_input("Job Role", placeholder="e.g. Software Engineer")
    
    # Resume Logic: Sidebar Profile vs Manual Upload
    resume_context = None
    use_stored_profile = False
    
    if current_profile:
        use_stored_profile = st.checkbox(f"Use Stored Profile", value=True)
    
    if not use_stored_profile:
        uploaded_resume_manual = st.file_uploader("Upload Specific Resume (Optional Override)", type="pdf", key="manual_resume")
        if uploaded_resume_manual:
             resume_context = parse_pdf(uploaded_resume_manual)
    else:
        # Use stored raw text or summary for context
        resume_context = current_profile.get("raw_text")

    uploaded_resume_sidebar = st.file_uploader("Update/Upload Resume (PDF)", type="pdf", key="sidebar_resume")
    
    if uploaded_resume_sidebar:
        if st.button("Process & Update Profile"):
            with st.spinner("Parsing resume and building profile..."):
                raw_text = parse_pdf(uploaded_resume_sidebar)
                if raw_text:
                    # Run Agent
                    run_profile_parsing(raw_text)
                    st.success("Profile Updated Successfully!")
                    st.rerun()

    force_refresh = st.checkbox("Force Refresh (Ignore Cache)")
    
    if st.button("Search & Draft"):
        if not company_name or not job_role:
            st.error("Please provide both Company Name and Job Role.")
        else:
            with st.spinner(f"Agents are working on finding recruiters for {job_role} at {company_name}..."):
                try:
                    data = run_recruiter_outreach(company_name, job_role, resume_context, force_refresh=force_refresh)
                    results = data.get("results")
                    usage = data.get("usage")
                    
                    if usage:
                        st.markdown("### Session Usage")
                        col1, col2 = st.columns(2)
                        col1.metric("Total Tokens", usage.get("total_tokens", 0))
                        col2.metric("Approx. Cost", "N/A" if usage.get("total_cost") is None else f"${usage.get('total_cost'):.4f}")

                    if results:
                        st.success(f"Found {len(results)} recruiters!")
                        for item in results:
                            with st.expander(f"{item.get('recruiter_name')} (Ranked)", expanded=True):
                                st.markdown(f"**LinkedIn:** [{item.get('linkedin_url')}]({item.get('linkedin_url')})")
                                st.markdown(f"**Reason:** {item.get('reason_for_ranking')}")
                                st.text_area("Draft Message", value=item.get('draft_message'), height=150)
                    else:
                        st.warning("No results found or an error occurred.")
                except Exception as e:
                    st.error(f"An error occurred: {e}")

ation Assistant
with tab2:
    st.header("Job Application Assistant")
    st.markdown("Generate a tailored Cold DM and Cover Letter for a specific Job Description.")
    
    if not current_profile:
        st.warning("⚠️ Please upload your resume in the Sidebar to use this feature.")
    else:
        jd_input = st.text_area("Paste Job Description (JD)", height=300, placeholder="Paste the full job description here...")
        
        if st.button("Generate Application Kit"):
            if not jd_input:
                st.error("Please paste a Job Description.")
            else:
                 with st.spinner("Analyzing JD and crafting tailored assets..."):
                    try:
                        app_data = run_job_application(jd_input)
                        results = app_data.get("results", {})
                        usage = app_data.get("usage", {})
                        
                        if results:
                             st.success("Assets Generated!")
                             
                             col_dm, col_cov = st.columns(2)
                             
                             with col_dm:
                                 st.subheader("Cold DM (LinkedIn)")
                                 st.info(results.get("cold_dm", "No DM generated."))
                                 st.button("Copy DM", disabled=True, help="Streamlit copy coming soon")

                             with col_cov:
                                 st.subheader("Cover Letter / Email Pitch")
                                 st.text_area("Email Content", value=results.get("cover_letter", ""), height=400)
                        else:
                            st.error("Failed to generate assets.")
                            
                    except Exception as e:
                        st.error(f"Error: {e}")

# TAB 3: History
with tab3:
    st.header("Outreach History")
    if st.button("Refresh History"):
        st.rerun()
        
    db = next(get_db())
    
    st.subheader("Accumulated Usage")
    usage_logs = db.query(UsageLog).all()
    if usage_logs:
        total_tokens = sum(log.total_tokens for log in usage_logs)
        st.metric("Total Tokens Used (All Time)", total_tokens)
    else:
        st.info("No usage logs yet.")

    st.markdown("---")
    history = db.query(RecruiterOutreach).order_by(RecruiterOutreach.created_at.desc()).all()
    
    if history:
        data = [r.to_dict() | {"created_at": r.created_at, "company_name": r.company_name, "job_role": r.job_role} for r in history]
        df = pd.DataFrame(data)
        st.dataframe(df.drop(columns=["draft_message", "reason_for_ranking"]), use_container_width=True)
        
        selected_id = st.selectbox("Select a Record to View Details", options=range(len(data)), format_func=lambda x: f"{data[x]['company_name']} - {data[x]['recruiter_name']}")
        if selected_id is not None:
             record = data[selected_id]
             st.markdown(f"### {record['recruiter_name']} at {record['company_name']}")
             st.markdown(f"**Role:** {record['job_role']}")
             st.markdown(f"**LinkedIn:** {record['linkedin_url']}")
             st.info(f"**Reason:** {record['reason_for_ranking']}")
             st.success(f"**Draft Message:**\n\n{record['draft_message']}")
    else:
        st.info("No history found.")

# TAB 4: Settings
with tab4:
    st.header("Settings")
    st.markdown("### API Keys")
    openai_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...", key="openai_key")
    tavily_key = st.text_input("Tavily API Key", type="password", placeholder="sk-...", key="tavily_key")
    
    if st.button("Save API Keys"):
        os.environ["OPENAI_API_KEY"] = openai_key
        os.environ["TAVILY_API_KEY"] = tavily_key
        st.success("API keys saved successfully!")

    st.markdown("---")
    st.markdown("### Database Settings")
    database_url = st.text_input("Database URL", placeholder="sqlite:///recruiter_outreach.db", key="database_url")
    
    if st.button("Save Database Settings"):
        os.environ["DATABASE_URL"] = database_url
        st.success("Database settings saved successfully!")

