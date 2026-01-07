"""
Claimant Portal - Insurance Claim Submission App

A mobile-friendly Streamlit application for submitting insurance claims.
Connects to the Multi-Agent Orchestration System FastAPI backend.
"""
import streamlit as st
import requests
import time
from typing import Optional

# ============================================
# CONFIGURATION
# ============================================

# Default API URL (can be overridden in sidebar)
DEFAULT_API_URL = "http://localhost:8000"


def get_api_url() -> str:
    """Get the API base URL from session state."""
    return st.session_state.get("api_url", DEFAULT_API_URL)


# ============================================
# PAGE CONFIG & STYLING
# ============================================

st.set_page_config(
    page_title="ClaimSense - Submit Your Claim",
    page_icon="🚗",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Mobile-friendly CSS
st.markdown("""
<style>
    /* Modern, mobile-friendly styling */
    .stApp {
        max-width: 100%;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 16px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 1rem;
    }
    
    /* Card styling */
    .claim-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        margin-bottom: 1rem;
        border: 1px solid #f0f0f0;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.875rem;
        text-transform: uppercase;
    }
    
    .status-submitted {
        background: #e3f2fd;
        color: #1976d2;
    }
    
    .status-analysis {
        background: #fff3e0;
        color: #f57c00;
    }
    
    .status-review {
        background: #e8f5e9;
        color: #388e3c;
    }
    
    .status-fraud {
        background: #ffebee;
        color: #d32f2f;
    }
    
    /* Progress tracker */
    .progress-tracker {
        display: flex;
        justify-content: space-between;
        margin: 2rem 0;
        position: relative;
    }
    
    .progress-step {
        flex: 1;
        text-align: center;
        position: relative;
        z-index: 1;
    }
    
    .step-circle {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #e0e0e0;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 0.5rem;
        font-weight: 700;
        color: white;
        transition: all 0.3s ease;
    }
    
    .step-circle.active {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    
    .step-circle.completed {
        background: #4caf50;
    }
    
    .step-label {
        font-size: 0.75rem;
        color: #666;
        font-weight: 500;
    }
    
    /* Success message */
    .success-box {
        background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 16px;
        text-align: center;
        margin: 1rem 0;
    }
    
    /* Analysis results */
    .analysis-result {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
    }
    
    .fraud-alert {
        background: #fff5f5;
        border-left-color: #e53e3e;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Mobile responsiveness */
    @media (max-width: 768px) {
        .main-header {
            padding: 1.5rem;
        }
        .main-header h1 {
            font-size: 1.5rem;
        }
        .step-label {
            font-size: 0.65rem;
        }
    }
</style>
""", unsafe_allow_html=True)


# ============================================
# API HELPER FUNCTIONS
# ============================================

def create_claim(policy_id: str, description: str, amount: float = 1000.0) -> Optional[dict]:
    """Create a new claim via the FastAPI backend."""
    try:
        response = requests.post(
            f"{get_api_url()}/claims/",
            json={
                "claimant_name": policy_id,  # Using policy ID as claimant name
                "amount": amount,
                "description": description,
                "requires_investigation": False
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to create claim: {str(e)}")
        return None


def upload_photo(claim_id: str, photo_bytes: bytes, filename: str) -> Optional[dict]:
    """Upload a damage photo for the claim."""
    try:
        files = {"photo": (filename, photo_bytes, "image/jpeg")}
        response = requests.post(
            f"{get_api_url()}/claims/{claim_id}/upload-photo",
            files=files,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to upload photo: {str(e)}")
        return None


def run_full_analysis(claim_id: str, call_log: Optional[str] = None) -> Optional[dict]:
    """Run the full multi-agent analysis on the claim."""
    try:
        data = {}
        if call_log:
            data["call_log"] = call_log
        
        response = requests.post(
            f"{get_api_url()}/claims/{claim_id}/full-analysis",
            json=data,
            timeout=120  # Analysis can take time
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to run analysis: {str(e)}")
        return None


def get_claim_status(claim_id: str) -> Optional[dict]:
    """Get the current status of a claim."""
    try:
        response = requests.get(
            f"{get_api_url()}/claims/{claim_id}",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to get claim status: {str(e)}")
        return None


# ============================================
# UI COMPONENTS
# ============================================

def render_header():
    """Render the main header."""
    st.markdown("""
    <div class="main-header">
        <h1>🚗 ClaimSense</h1>
        <p>Submit your insurance claim in minutes</p>
    </div>
    """, unsafe_allow_html=True)


def render_progress_tracker(current_step: int):
    """Render the claim progress tracker."""
    steps = ["Submitted", "AI Analysis", "Under Review"]
    
    cols = st.columns(3)
    for i, (col, step) in enumerate(zip(cols, steps)):
        with col:
            if i < current_step:
                st.markdown(f"✅ **{step}**")
            elif i == current_step:
                st.markdown(f"🔄 **{step}**")
            else:
                st.markdown(f"⬜ {step}")


def render_status_badge(state: str) -> str:
    """Get the appropriate status badge class."""
    state_lower = state.lower()
    if "submitted" in state_lower:
        return "status-submitted"
    elif "analysis" in state_lower or "review" in state_lower:
        return "status-analysis"
    elif "fraud" in state_lower:
        return "status-fraud"
    else:
        return "status-review"


# ============================================
# MAIN APPLICATION
# ============================================

def main():
    """Main application entry point."""
    
    # Initialize session state
    if "claim_submitted" not in st.session_state:
        st.session_state.claim_submitted = False
    if "claim_id" not in st.session_state:
        st.session_state.claim_id = None
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0
    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None
    
    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Settings")
        api_url = st.text_input(
            "API Server URL",
            value=DEFAULT_API_URL,
            help="URL of the FastAPI backend server"
        )
        st.session_state.api_url = api_url
        
        st.divider()
        st.caption("🔗 Connected to Multi-Agent Orchestration System")
        
        # Health check
        if st.button("Test Connection"):
            try:
                response = requests.get(f"{api_url}/health", timeout=5)
                if response.status_code == 200:
                    st.success("✅ Connected!")
                else:
                    st.error("❌ Connection failed")
            except:
                st.error("❌ Cannot reach server")
    
    # Main header
    render_header()
    
    # Show different views based on state
    if not st.session_state.claim_submitted:
        render_submission_form()
    else:
        render_claim_tracking()


def render_submission_form():
    """Render the claim submission form."""
    
    st.subheader("📝 Submit Your Claim")
    
    with st.form("claim_form"):
        # Policy ID
        policy_id = st.text_input(
            "Policy ID *",
            placeholder="e.g., POL-12345",
            help="Enter your insurance policy number"
        )
        
        # Claim amount
        amount = st.number_input(
            "Estimated Damage Amount ($)",
            min_value=100.0,
            max_value=100000.0,
            value=5000.0,
            step=100.0
        )
        
        st.divider()
        
        # Incident description
        description = st.text_area(
            "Describe the Incident *",
            placeholder="Please describe what happened in detail. Include information like:\n- Date and time of incident\n- Location\n- How the damage occurred\n- Weather conditions\n- Any other relevant details",
            height=150,
            help="This will be analyzed by our AI Text Agent"
        )
        
        st.divider()
        
        # Photo upload
        st.markdown("**📸 Upload Damage Photo**")
        photo = st.file_uploader(
            "Take or upload a photo of the damage",
            type=["jpg", "jpeg", "png"],
            help="This will be analyzed by our AI Vision Agent"
        )
        
        if photo:
            st.image(photo, caption="Uploaded Photo", use_container_width=True)
        
        st.divider()
        
        # Optional call log (for text analysis)
        with st.expander("📞 Optional: Add Phone Call Details"):
            call_log = st.text_area(
                "Call Transcript/Notes",
                placeholder="If you spoke with an agent, paste the call notes here...",
                height=100
            )
        
        # Submit button
        submitted = st.form_submit_button(
            "🚀 Submit Claim",
            use_container_width=True,
            type="primary"
        )
        
        if submitted:
            # Validation
            if not policy_id:
                st.error("Please enter your Policy ID")
            elif not description:
                st.error("Please describe the incident")
            else:
                process_claim_submission(
                    policy_id=policy_id,
                    description=description,
                    amount=amount,
                    photo=photo,
                    call_log=call_log if 'call_log' in dir() and call_log else None
                )


def process_claim_submission(
    policy_id: str,
    description: str,
    amount: float,
    photo,
    call_log: Optional[str]
):
    """Process the claim submission through all steps."""
    
    progress_bar = st.progress(0, text="Initializing...")
    status_text = st.empty()
    
    # Step 1: Create claim
    status_text.info("📤 Creating your claim record...")
    progress_bar.progress(20, text="Creating claim...")
    
    claim_result = create_claim(policy_id, description, amount)
    if not claim_result:
        progress_bar.empty()
        return
    
    claim_id = claim_result["claim"]["id"]
    st.session_state.claim_id = claim_id
    st.session_state.current_step = 1
    
    progress_bar.progress(40, text="Claim created!")
    time.sleep(0.5)
    
    # Step 2: Upload photo if provided
    if photo:
        status_text.info("📸 Uploading damage photo for AI analysis...")
        progress_bar.progress(60, text="Analyzing photo...")
        
        photo_bytes = photo.getvalue()
        photo_result = upload_photo(claim_id, photo_bytes, photo.name)
        
        if photo_result:
            st.session_state.photo_analysis = photo_result
            if photo_result.get("fraud_detected"):
                status_text.warning("⚠️ Photo analysis flagged potential issues")
    
    progress_bar.progress(80, text="Running AI analysis...")
    time.sleep(0.5)
    
    # Step 3: Run full analysis (if we have call log)
    status_text.info("🤖 Running Multi-Agent Analysis...")
    analysis_result = run_full_analysis(claim_id, call_log)
    
    if analysis_result:
        st.session_state.analysis_result = analysis_result
        st.session_state.current_step = 2
    
    progress_bar.progress(100, text="Complete!")
    
    # Mark as submitted
    st.session_state.claim_submitted = True
    time.sleep(0.5)
    
    # Rerun to show tracking view
    st.rerun()


def render_claim_tracking():
    """Render the claim tracking view."""
    
    claim_id = st.session_state.claim_id
    
    # Success header
    st.markdown(f"""
    <div class="success-box">
        <h2 style="margin: 0;">✅ Claim Submitted!</h2>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.1rem;">
            Reference: <strong>{claim_id[:8]}...</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Progress tracker
    st.subheader("📊 Claim Status")
    render_progress_tracker(st.session_state.current_step)
    
    # Get current status
    status_data = get_claim_status(claim_id)
    
    if status_data:
        claim = status_data.get("claim", {})
        current_state = claim.get("current_state", "SUBMITTED")
        
        # Status card
        st.markdown("---")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"**Current Status:** `{current_state}`")
            
            if claim.get("requires_investigation"):
                st.warning("⚠️ This claim has been flagged for additional review")
        
        with col2:
            st.metric("Claim Amount", f"${claim.get('amount', 0):,.2f}")
    
    # Analysis Results
    if st.session_state.analysis_result:
        st.subheader("🤖 AI Analysis Results")
        
        result = st.session_state.analysis_result
        orch_result = result.get("orchestrator_result", {})
        
        # Overall verdict
        verdict = orch_result.get("final_verdict", "PASS")
        if verdict == "PASS":
            st.success(f"✅ **Verdict:** {verdict}")
        else:
            st.error(f"⚠️ **Verdict:** {verdict}")
        
        # Summary
        summary = orch_result.get("summary", "Analysis complete.")
        st.info(f"📋 {summary}")
        
        # Detailed results in expanders
        with st.expander("🔍 Vision Agent (Photo Analysis)"):
            vision = result.get("vision_analysis")
            if vision:
                st.json(vision)
            else:
                st.caption("No photo was analyzed")
        
        with st.expander("📝 Text Agent (Consistency Check)"):
            text = result.get("text_analysis")
            if text:
                st.json(text)
            else:
                st.caption("No call log was provided for analysis")
    
    # Actions
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Refresh Status", use_container_width=True):
            st.rerun()
    
    with col2:
        if st.button("📝 Submit Another Claim", use_container_width=True):
            # Reset state
            st.session_state.claim_submitted = False
            st.session_state.claim_id = None
            st.session_state.current_step = 0
            st.session_state.analysis_result = None
            st.rerun()
    
    # Claim ID for reference
    with st.expander("📋 Full Claim ID"):
        st.code(claim_id)
        st.caption("Save this ID to track your claim")


if __name__ == "__main__":
    main()
