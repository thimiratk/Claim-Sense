"""
Explainability Dashboard for Multi-Agent Insurance Claim System

A Streamlit dashboard providing:
- Claims overview with state filtering
- Visual evidence display (damage photos)
- The 'Why' panel comparing call logs vs written claims
- Agent timeline showing decision flow
- Human override controls
"""
import streamlit as st
import requests
from datetime import datetime
import base64

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page configuration
st.set_page_config(
    page_title="Claims Explainability Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stAlert {margin-top: 1rem;}
    .timeline-item {
        padding: 10px 15px;
        border-left: 3px solid #4CAF50;
        margin-left: 20px;
        margin-bottom: 10px;
        background: #f8f9fa;
        border-radius: 0 8px 8px 0;
    }
    .timeline-item.fraud {border-left-color: #f44336;}
    .timeline-item.human {border-left-color: #2196F3;}
    .comparison-table {width: 100%;}
    .highlight-mismatch {background-color: #ffebee; padding: 2px 5px; border-radius: 3px;}
    .state-badge {
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .state-SUBMITTED {background: #e3f2fd; color: #1565c0;}
    .state-UNDER_REVIEW {background: #fff3e0; color: #ef6c00;}
    .state-FRAUD_INVESTIGATION {background: #ffebee; color: #c62828;}
    .state-ASSESSMENT {background: #e8f5e9; color: #2e7d32;}
    .state-FINAL_DECISION {background: #f3e5f5; color: #7b1fa2;}
</style>
""", unsafe_allow_html=True)


def get_claims_summary():
    """Fetch claims summary from API."""
    try:
        response = requests.get(f"{API_BASE_URL}/claims/dashboard/summary", timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        pass
    return None


def get_claim_detail(claim_id: str):
    """Fetch detailed claim information."""
    try:
        response = requests.get(f"{API_BASE_URL}/claims/{claim_id}", timeout=5)
        if response.status_code == 200:
            return response.json()["claim"]
    except requests.exceptions.RequestException:
        pass
    return None


def approve_claim(claim_id: str, operator: str, reason: str):
    """Approve a claim via API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/claims/{claim_id}/approve",
            json={"operator_name": operator, "reason": reason},
            timeout=5
        )
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except requests.exceptions.RequestException as e:
        return False, str(e)


def reject_claim(claim_id: str, operator: str, reason: str):
    """Reject a claim via API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/claims/{claim_id}/reject",
            json={"operator_name": operator, "reason": reason},
            timeout=5
        )
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except requests.exceptions.RequestException as e:
        return False, str(e)


def render_state_badge(state: str) -> str:
    """Render a styled state badge."""
    return f'<span class="state-badge state-{state}">{state}</span>'


def render_timeline(claim: dict):
    """Render the agent decision timeline."""
    st.subheader("📊 Agent Timeline")
    
    # Start with claim creation
    created_at = claim.get("created_at", "")
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            time_str = dt.strftime("%H:%M")
        except:
            time_str = "00:00"
    else:
        time_str = "00:00"
    
    # Timeline entries
    timeline = []
    
    # 1. Claim submitted
    timeline.append({
        "time": time_str,
        "event": "Claim Submitted",
        "agent": "System",
        "detail": f"Claim created for {claim.get('claimant_name', 'Unknown')}",
        "type": "normal"
    })
    
    # 2. State history
    state_history = claim.get("state_history", [])
    for i, state in enumerate(state_history[1:] if len(state_history) > 1 else []):
        state_val = state if isinstance(state, str) else state.get("value", str(state))
        timeline.append({
            "time": "",
            "event": f"State: {state_val}",
            "agent": "State Machine",
            "detail": "",
            "type": "fraud" if state_val == "FRAUD_INVESTIGATION" else "normal"
        })
    
    # 3. Vision analysis
    if claim.get("vision_analysis"):
        va = claim["vision_analysis"]
        mismatch = va.get("mismatch_found", False)
        timeline.append({
            "time": "",
            "event": "Vision Agent Analysis",
            "agent": "Vision Agent (Llama 3.2-Vision)",
            "detail": f"{'⚠️ MISMATCH DETECTED' if mismatch else '✓ No mismatch'}: {va.get('detected_damage', 'N/A')[:100]}",
            "type": "fraud" if mismatch else "normal"
        })
    
    # 4. Text analysis
    if claim.get("text_analysis"):
        ta = claim["text_analysis"]
        score = ta.get("inconsistency_score", 0)
        verdict = ta.get("verdict", "CONSISTENT")
        timeline.append({
            "time": "",
            "event": "Text Agent Analysis",
            "agent": "Text Agent (Llama 3)",
            "detail": f"Score: {score}/10 - {verdict}",
            "type": "fraud" if verdict == "SUSPICIOUS" else "normal"
        })
    
    # 5. Audit log entries
    for entry in claim.get("audit_log", []):
        agent = entry.get("agent_name", "Unknown")
        decision = entry.get("decision", "")
        timeline.append({
            "time": "",
            "event": decision,
            "agent": agent,
            "detail": entry.get("raw_reasoning", "")[:150],
            "type": "human" if "Human" in agent or "Operator" in agent else "normal"
        })
    
    # 6. Human override
    if claim.get("human_override"):
        timeline.append({
            "time": "",
            "event": "Human Override",
            "agent": "Human Operator",
            "detail": claim["human_override"],
            "type": "human"
        })
    
    # Render timeline
    for item in timeline:
        type_class = item["type"]
        st.markdown(f"""
        <div class="timeline-item {type_class}">
            <strong>[{item['time']}] {item['event']}</strong><br>
            <small>Agent: {item['agent']}</small><br>
            {item['detail']}
        </div>
        """, unsafe_allow_html=True)


def render_visual_evidence(claim: dict):
    """Render the visual evidence panel with photo and analysis."""
    st.subheader("📷 Visual Evidence")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Uploaded Photo**")
        if claim.get("photo_base64"):
            st.image(
                f"data:image/jpeg;base64,{claim['photo_base64']}", 
                caption="Damage Photo",
                use_container_width=True
            )
        elif claim.get("photo_path"):
            st.info(f"Photo path: {claim['photo_path']}")
        else:
            st.info("No photo uploaded for this claim")
    
    with col2:
        st.markdown("**Vision Agent Findings**")
        if claim.get("vision_analysis"):
            va = claim["vision_analysis"]
            
            if va.get("mismatch_found"):
                st.error("⚠️ MISMATCH DETECTED")
            else:
                st.success("✓ Photo matches description")
            
            st.markdown(f"**Detected Damage:** {va.get('detected_damage', 'N/A')}")
            st.markdown(f"**Reasoning:** {va.get('reasoning', 'N/A')}")
            
            if va.get("confidence"):
                st.progress(va["confidence"], text=f"Confidence: {va['confidence']:.0%}")
        else:
            st.info("No vision analysis performed yet")


def render_why_panel(claim: dict):
    """Render the 'Why' panel comparing call log vs written claim."""
    st.subheader("🔍 The 'Why' Panel - Text Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📞 Call Log (Phone Transcript)**")
        call_log = claim.get("call_log", "")
        if call_log:
            st.text_area("Call Log", call_log, height=200, disabled=True, key="call_log_display")
        else:
            st.info("No call log recorded")
    
    with col2:
        st.markdown("**📝 Written Claim Description**")
        description = claim.get("description", "")
        st.text_area("Written Claim", description, height=200, disabled=True, key="description_display")
    
    # Text analysis results
    if claim.get("text_analysis"):
        ta = claim["text_analysis"]
        
        st.markdown("---")
        st.markdown("**📊 Text Agent Analysis Results**")
        
        score = ta.get("inconsistency_score", 0)
        verdict = ta.get("verdict", "CONSISTENT")
        
        # Score visualization
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            color = "red" if score >= 5 else "orange" if score >= 3 else "green"
            st.markdown(f"""
            <div style="text-align: center; padding: 20px; background: {'#ffebee' if score >= 5 else '#fff3e0' if score >= 3 else '#e8f5e9'}; border-radius: 10px;">
                <h2 style="color: {color}; margin: 0;">{score}/10</h2>
                <p style="margin: 5px 0;">Inconsistency Score</p>
                <strong style="color: {color};">{verdict}</strong>
            </div>
            """, unsafe_allow_html=True)
        
        # Contradictions
        contradictions = ta.get("contradictions", [])
        if contradictions:
            st.markdown("**⚠️ Contradictions Found:**")
            for i, c in enumerate(contradictions, 1):
                st.markdown(f'<span class="highlight-mismatch">• {c}</span>', unsafe_allow_html=True)
        
        # Reasoning
        if ta.get("reasoning"):
            with st.expander("View Full Reasoning"):
                st.write(ta["reasoning"])


def render_human_override(claim: dict):
    """Render the human override controls."""
    st.subheader("👤 Human Override Controls")
    
    current_state = claim.get("current_state", "SUBMITTED")
    if isinstance(current_state, dict):
        current_state = current_state.get("value", "SUBMITTED")
    
    # Show current state
    st.markdown(f"**Current State:** {render_state_badge(current_state)}", unsafe_allow_html=True)
    
    if claim.get("human_override"):
        st.info(f"Previous override: {claim['human_override']}")
    
    # Override form
    col1, col2 = st.columns(2)
    
    with col1:
        operator_name = st.text_input("Operator Name", value="Human Operator", key="operator_name")
    
    with col2:
        reason = st.text_input("Reason (optional)", key="override_reason")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("✅ Approve Claim", type="primary", use_container_width=True):
            success, result = approve_claim(claim["id"], operator_name, reason)
            if success:
                st.success(result.get("message", "Claim approved!"))
                st.rerun()
            else:
                st.error(f"Failed to approve: {result}")
    
    with col2:
        if st.button("❌ Reject Claim", type="secondary", use_container_width=True):
            success, result = reject_claim(claim["id"], operator_name, reason)
            if success:
                st.success(result.get("message", "Claim rejected!"))
                st.rerun()
            else:
                st.error(f"Failed to reject: {result}")


def main():
    """Main dashboard application."""
    st.title("🔍 Claims Explainability Dashboard")
    st.markdown("Multi-Agent Insurance Claim Processing System")
    
    # Sidebar - Claims List
    with st.sidebar:
        st.header("📋 Active Claims")
        
        # Refresh button
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
        
        # Fetch claims
        summary = get_claims_summary()
        
        if summary is None:
            st.error("⚠️ Cannot connect to API. Is the server running?")
            st.code("uvicorn app.main:app --reload")
            return
        
        # State filter
        st.markdown("**Filter by State:**")
        state_counts = summary.get("state_counts", {})
        selected_state = st.selectbox(
            "State",
            options=["ALL"] + list(state_counts.keys()),
            format_func=lambda x: f"{x} ({state_counts.get(x, summary.get('total_claims', 0))})" if x != "ALL" else f"ALL ({summary.get('total_claims', 0)})"
        )
        
        # Claims list
        st.markdown("---")
        claims = summary.get("claims", [])
        
        if selected_state != "ALL":
            claims = [c for c in claims if c["state"] == selected_state]
        
        selected_claim_id = None
        
        for claim in claims:
            state = claim["state"]
            flag = "🚨" if claim.get("requires_investigation") else ""
            
            if st.button(
                f"{flag} {claim['claimant'][:15]}... - ${claim['amount']:,.0f}",
                key=f"claim_{claim['id']}",
                use_container_width=True,
                help=f"ID: {claim['id']}\nState: {state}"
            ):
                st.session_state.selected_claim = claim["id"]
        
        # Stats
        st.markdown("---")
        st.markdown("**📊 Statistics**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total", summary.get("total_claims", 0))
        with col2:
            st.metric("Flagged", summary.get("fraud_flagged", 0))
    
    # Main content
    if "selected_claim" in st.session_state:
        claim = get_claim_detail(st.session_state.selected_claim)
        
        if claim:
            # Claim header
            current_state = claim.get("current_state", "SUBMITTED")
            if isinstance(current_state, dict):
                current_state = current_state.get("value", "SUBMITTED")
            
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"### {claim.get('claimant_name', 'Unknown Claimant')}")
            with col2:
                st.markdown(f"**Amount:** ${claim.get('amount', 0):,.2f}")
            with col3:
                st.markdown(render_state_badge(current_state), unsafe_allow_html=True)
            
            st.markdown(f"**Claim ID:** `{claim.get('id', 'N/A')}`")
            
            if claim.get("requires_investigation"):
                st.warning("🚨 This claim is flagged for fraud investigation")
            
            st.markdown("---")
            
            # Tabs for different views
            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 Timeline", 
                "📷 Visual Evidence", 
                "🔍 Why Panel",
                "👤 Human Override"
            ])
            
            with tab1:
                render_timeline(claim)
            
            with tab2:
                render_visual_evidence(claim)
            
            with tab3:
                render_why_panel(claim)
            
            with tab4:
                render_human_override(claim)
        else:
            st.error("Could not load claim details")
    else:
        # Welcome message
        st.info("👈 Select a claim from the sidebar to view details")
        
        # Quick stats
        summary = get_claims_summary()
        if summary:
            st.markdown("### 📈 Quick Overview")
            
            cols = st.columns(5)
            state_counts = summary.get("state_counts", {})
            
            for i, (state, count) in enumerate(state_counts.items()):
                with cols[i % 5]:
                    st.metric(state, count)


if __name__ == "__main__":
    main()
