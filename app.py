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

# --- Main Interface ---
tab1 = st.tabs(["New Outreach (Recruiters)"])

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
             from pypdf import PdfReader
             try:
                reader = PdfReader(uploaded_resume_manual)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                resume_context = text.strip()
             except:
                 pass
    else:
        # Use stored raw text or summary for context
        resume_context = current_profile.get("raw_text")

    uploaded_resume_sidebar = st.file_uploader("Update/Upload Resume (PDF)", type="pdf", key="sidebar_resume")
    
    if uploaded_resume_sidebar:
        if st.button("Process & Update Profile"):
            with st.spinner("Parsing resume and building profile..."):
                from pypdf import PdfReader
                try:
                    reader = PdfReader(uploaded_resume_sidebar)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    raw_text = text.strip()
                    
                    # Run Agent
                    run_profile_parsing(raw_text)
                    st.success("Profile Updated Successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing resume: {e}")

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
