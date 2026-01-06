"""
FastAPI Endpoints for Claim Processing

Provides REST API for creating and managing insurance claims.
"""
import logging
import os
from typing import Dict, List

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from pydantic import BaseModel

from app.core.models import Claim, ClaimCreate
from app.core.states import ClaimState
from app.state_machine.machine import ClaimStateMachine
from app.monitors.process_monitor import ProcessMonitor
from app.agents.vision_agent import analyze_damage_from_bytes, VisionAnalysisResult
from app.agents.text_agent import analyze_text_consistency, TextAnalysisResult
from app.agents.orchestrator import orchestrator, OrchestratorResult, update_claim_for_investigation

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/claims", tags=["claims"])

# In-memory store for claims (would be a database in production)
claims_store: Dict[str, Claim] = {}

# Initialize state machine and monitor
state_machine = ClaimStateMachine()
process_monitor = ProcessMonitor(state_machine)


class ClaimResponse(BaseModel):
    """Response model for claim operations."""
    claim: Claim
    message: str
    next_valid_states: List[ClaimState]


class StateHistoryResponse(BaseModel):
    """Response model for state history."""
    claim_id: str
    current_state: ClaimState
    state_history: List[ClaimState]
    pending_states: List[ClaimState]


class AdvanceRequest(BaseModel):
    """Request model for advancing claim state."""
    target_state: ClaimState | None = None  # If None, auto-advance to next state


@router.post("/", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(claim_data: ClaimCreate) -> ClaimResponse:
    """
    Create a new insurance claim.
    
    The claim starts in SUBMITTED state.
    """
    # Create the claim
    claim = Claim(
        claimant_name=claim_data.claimant_name,
        amount=claim_data.amount,
        description=claim_data.description,
        requires_investigation=claim_data.requires_investigation
    )
    
    # Record initial state in history
    claim.state_history.append(claim.current_state)
    
    # Store the claim
    claims_store[claim.id] = claim
    
    logger.info(f"Created new claim {claim.id} for {claim.claimant_name}")
    
    return ClaimResponse(
        claim=claim,
        message=f"Claim created successfully with ID {claim.id}",
        next_valid_states=state_machine.get_valid_transitions(claim)
    )


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(claim_id: str) -> ClaimResponse:
    """
    Get details of a specific claim.
    """
    claim = claims_store.get(claim_id)
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found"
        )
    
    return ClaimResponse(
        claim=claim,
        message=f"Claim {claim_id} retrieved",
        next_valid_states=state_machine.get_valid_transitions(claim)
    )


@router.get("/", response_model=List[Claim])
async def list_claims() -> List[Claim]:
    """
    List all claims in the system.
    """
    return list(claims_store.values())


@router.post("/{claim_id}/advance", response_model=ClaimResponse)
async def advance_claim(claim_id: str, request: AdvanceRequest | None = None) -> ClaimResponse:
    """
    Advance a claim to its next state.
    
    If target_state is provided, validates and transitions to that state.
    Otherwise, auto-advances to the next state in the workflow.
    
    When entering UNDER_REVIEW, agent evaluation is triggered which may
    dynamically insert FRAUD_INVESTIGATION state.
    """
    claim = claims_store.get(claim_id)
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found"
        )
    
    # Check if claim is in terminal state
    if claim.current_state == ClaimState.FINAL_DECISION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Claim is already in FINAL_DECISION state (terminal)"
        )
    
    try:
        previous_state = claim.current_state
        
        if request and request.target_state:
            # Transition to specific state
            if not state_machine.can_transition(claim, request.target_state):
                valid = state_machine.get_valid_transitions(claim)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot transition from {claim.current_state} to {request.target_state}. "
                           f"Valid transitions: {[s.value for s in valid]}"
                )
            claim = state_machine.transition(claim, request.target_state)
            claim = await process_monitor.on_state_entered(claim, request.target_state)
        else:
            # Auto-advance using process monitor
            claim = await process_monitor.advance_claim(claim)
        
        # Update store
        claims_store[claim_id] = claim
        
        message = f"Claim advanced from {previous_state} to {claim.current_state}"
        
        # Add note about dynamic state insertion
        if claim.pending_states:
            message += f". Pending states: {[s.value for s in claim.pending_states]}"
        
        return ClaimResponse(
            claim=claim,
            message=message,
            next_valid_states=state_machine.get_valid_transitions(claim)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{claim_id}/history", response_model=StateHistoryResponse)
async def get_claim_history(claim_id: str) -> StateHistoryResponse:
    """
    Get the state transition history for a claim.
    """
    claim = claims_store.get(claim_id)
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found"
        )
    
    return StateHistoryResponse(
        claim_id=claim.id,
        current_state=claim.current_state,
        state_history=claim.state_history,
        pending_states=claim.pending_states
    )


class PhotoAnalysisResponse(BaseModel):
    """Response model for photo upload and analysis."""
    claim_id: str
    analysis: VisionAnalysisResult
    fraud_detected: bool
    claim_state: ClaimState
    message: str


@router.post("/{claim_id}/upload-photo", response_model=PhotoAnalysisResponse)
async def upload_photo(
    claim_id: str,
    photo: UploadFile = File(..., description="Photo of the vehicle damage")
) -> PhotoAnalysisResponse:
    """
    Upload a damage photo for vision-based analysis.
    
    The Vision Agent (Ollama + Llama 3.2-Vision) will:
    1. Analyze the visible damage in the photo
    2. Compare it with the claim's description
    3. Flag mismatches as potential fraud
    
    If a mismatch is found, the claim is automatically moved to FRAUD_INVESTIGATION.
    """
    claim = claims_store.get(claim_id)
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found"
        )
    
    # Validate file type
    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (JPEG, PNG, etc.)"
        )
    
    try:
        # Read the uploaded image
        image_bytes = await photo.read()
        
        logger.info(f"Analyzing photo for claim {claim_id} ({len(image_bytes)} bytes)")
        
        # Store base64 encoded photo for dashboard display
        import base64
        claim.photo_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # Call the vision agent for analysis
        analysis = await analyze_damage_from_bytes(
            image_bytes=image_bytes,
            claim_description=claim.description
        )
        
        # Store analysis results on the claim
        claim.vision_analysis = analysis.model_dump()
        claim.updated_at = __import__("datetime").datetime.now()
        
        fraud_detected = analysis.mismatch_found
        message = "Photo analysis complete."
        
        # If mismatch found, trigger fraud investigation
        if fraud_detected:
            logger.warning(
                f"FRAUD ALERT: Mismatch detected for claim {claim_id}. "
                f"Reason: {analysis.reasoning}"
            )
            
            # Override to FRAUD_INVESTIGATION regardless of current state
            if claim.current_state != ClaimState.FRAUD_INVESTIGATION:
                # Insert FRAUD_INVESTIGATION as the next required state
                if ClaimState.FRAUD_INVESTIGATION not in claim.pending_states:
                    claim.pending_states.insert(0, ClaimState.FRAUD_INVESTIGATION)
                
                message = (
                    f"⚠️ FRAUD DETECTED: Photo analysis found mismatch. "
                    f"Claim flagged for investigation. Reason: {analysis.reasoning}"
                )
            
            # Update requires_investigation flag
            claim.requires_investigation = True
        else:
            message = f"✓ Photo analysis complete. No mismatch detected. {analysis.reasoning}"
        
        # Save updated claim
        claims_store[claim_id] = claim
        
        return PhotoAnalysisResponse(
            claim_id=claim_id,
            analysis=analysis,
            fraud_detected=fraud_detected,
            claim_state=claim.current_state,
            message=message
        )
        
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vision service not available: {str(e)}"
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vision analysis failed: {str(e)}"
        )


class TextAnalysisRequest(BaseModel):
    """Request model for text consistency analysis."""
    call_log: str
    written_claim: str | None = None  # If not provided, uses claim.description


class TextAnalysisResponse(BaseModel):
    """Response model for text analysis."""
    claim_id: str
    analysis: TextAnalysisResult
    fraud_detected: bool
    claim_state: ClaimState
    message: str


@router.post("/{claim_id}/analyze-text", response_model=TextAnalysisResponse)
async def analyze_text(
    claim_id: str,
    request: TextAnalysisRequest
) -> TextAnalysisResponse:
    """
    Analyze text consistency between call log and written claim.
    
    The Text Agent (Ollama + Llama 3) acts as a 'Forensic Linguist' to detect:
    - Fact mismatches (weather, time, location differences)
    - Story shifts (changing who was at fault)
    - Urgency/pressure indicators
    
    If inconsistency_score >= 5, the claim is flagged for FRAUD_INVESTIGATION.
    """
    claim = claims_store.get(claim_id)
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found"
        )
    
    try:
        # Use provided written claim or fall back to claim description
        written_claim = request.written_claim or claim.description
        
        logger.info(f"Analyzing text consistency for claim {claim_id}")
        
        # Call the text agent for analysis
        analysis = await analyze_text_consistency(
            call_log=request.call_log,
            written_claim=written_claim
        )
        
        # Store analysis results and call log on the claim
        claim.call_log = request.call_log
        claim.text_analysis = analysis.model_dump()
        claim.updated_at = __import__("datetime").datetime.now()
        
        fraud_detected = analysis.verdict == "SUSPICIOUS"
        message = "Text analysis complete."
        
        # If suspicious, trigger fraud investigation
        if fraud_detected:
            logger.warning(
                f"FRAUD ALERT: Text inconsistency detected for claim {claim_id}. "
                f"Score: {analysis.inconsistency_score}/10"
            )
            
            # Insert FRAUD_INVESTIGATION if not already pending
            if ClaimState.FRAUD_INVESTIGATION not in claim.pending_states:
                claim.pending_states.insert(0, ClaimState.FRAUD_INVESTIGATION)
            
            claim.requires_investigation = True
            
            message = (
                f"⚠️ SUSPICIOUS: Inconsistency score {analysis.inconsistency_score}/10. "
                f"Contradictions: {', '.join(analysis.contradictions[:2]) if analysis.contradictions else 'See reasoning'}"
            )
        else:
            message = f"✓ Text analysis complete. Consistent (score: {analysis.inconsistency_score}/10)"
        
        # Save updated claim
        claims_store[claim_id] = claim
        
        return TextAnalysisResponse(
            claim_id=claim_id,
            analysis=analysis,
            fraud_detected=fraud_detected,
            claim_state=claim.current_state,
            message=message
        )
        
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Text analysis service not available: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text analysis failed: {str(e)}"
        )


class FullAnalysisRequest(BaseModel):
    """Request model for full multi-agent analysis."""
    call_log: str | None = None
    written_claim: str | None = None


class FullAnalysisResponse(BaseModel):
    """Response model for combined multi-agent analysis."""
    claim_id: str
    orchestrator_result: OrchestratorResult
    vision_analysis: VisionAnalysisResult | None = None
    text_analysis: TextAnalysisResult | None = None
    claim_state: ClaimState
    pending_states: List[ClaimState]
    message: str


@router.post("/{claim_id}/full-analysis", response_model=FullAnalysisResponse)
async def full_analysis(
    claim_id: str,
    request: FullAnalysisRequest,
    photo: UploadFile | None = File(None, description="Optional photo of vehicle damage")
) -> FullAnalysisResponse:
    """
    Run BOTH Vision and Text agents on a claim.
    
    The Multi-Agent Orchestrator combines results:
    - Vision Agent: Compares photo damage with claim description
    - Text Agent: Compares call log with written claim
    
    If EITHER agent flags suspicious activity, the claim is routed to FRAUD_INVESTIGATION.
    """
    claim = claims_store.get(claim_id)
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found"
        )
    
    vision_result = None
    text_result = None
    
    try:
        # Run Vision Agent if photo provided
        if photo and photo.content_type and photo.content_type.startswith("image/"):
            image_bytes = await photo.read()
            logger.info(f"Running Vision Agent for claim {claim_id}")
            
            vision_result = await analyze_damage_from_bytes(
                image_bytes=image_bytes,
                claim_description=claim.description
            )
            claim.vision_analysis = vision_result.model_dump()
        
        # Run Text Agent if call log provided
        if request.call_log:
            written_claim = request.written_claim or claim.description
            logger.info(f"Running Text Agent for claim {claim_id}")
            
            text_result = await analyze_text_consistency(
                call_log=request.call_log,
                written_claim=written_claim
            )
            claim.call_log = request.call_log
            claim.text_analysis = text_result.model_dump()
        
        # Run the orchestrator to combine results
        orch_result = orchestrator.evaluate_results(
            vision_result=vision_result,
            text_result=text_result
        )
        
        # Update claim based on orchestrator decision
        claim = update_claim_for_investigation(claim, orch_result)
        claim.updated_at = __import__("datetime").datetime.now()
        
        # Save updated claim
        claims_store[claim_id] = claim
        
        return FullAnalysisResponse(
            claim_id=claim_id,
            orchestrator_result=orch_result,
            vision_analysis=vision_result,
            text_analysis=text_result,
            claim_state=claim.current_state,
            pending_states=claim.pending_states,
            message=orch_result.summary
        )
        
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Analysis service not available: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Full analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


# ============================================
# HUMAN OVERRIDE ENDPOINTS (for Dashboard)
# ============================================

class HumanOverrideRequest(BaseModel):
    """Request model for human override actions."""
    operator_name: str = "Human Operator"
    reason: str = ""


class HumanOverrideResponse(BaseModel):
    """Response model for human override."""
    claim_id: str
    action: str
    previous_state: ClaimState
    new_state: ClaimState
    message: str


@router.post("/{claim_id}/approve", response_model=HumanOverrideResponse)
async def approve_claim(
    claim_id: str,
    request: HumanOverrideRequest | None = None
) -> HumanOverrideResponse:
    """
    Human operator approves a claim.
    
    If the claim was in FRAUD_INVESTIGATION, it moves to ASSESSMENT
    with a note that it was 'Cleared by Human Operator.'
    """
    claim = claims_store.get(claim_id)
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found"
        )
    
    operator = request.operator_name if request else "Human Operator"
    reason = request.reason if request and request.reason else "Manual review completed"
    
    previous_state = claim.current_state
    
    # Clear fraud investigation if pending
    if ClaimState.FRAUD_INVESTIGATION in claim.pending_states:
        claim.pending_states.remove(ClaimState.FRAUD_INVESTIGATION)
    
    # If in FRAUD_INVESTIGATION, move to ASSESSMENT
    if claim.current_state == ClaimState.FRAUD_INVESTIGATION:
        claim.record_state_change(ClaimState.ASSESSMENT)
        claim.human_override = f"Cleared by {operator}"
        message = f"Claim cleared by {operator}. Moved from FRAUD_INVESTIGATION to ASSESSMENT."
    elif claim.current_state == ClaimState.SUBMITTED:
        claim.record_state_change(ClaimState.UNDER_REVIEW)
        message = f"Claim approved by {operator}. Moved to UNDER_REVIEW."
    elif claim.current_state == ClaimState.UNDER_REVIEW:
        claim.record_state_change(ClaimState.ASSESSMENT)
        message = f"Claim approved by {operator}. Moved to ASSESSMENT."
    elif claim.current_state == ClaimState.ASSESSMENT:
        claim.record_state_change(ClaimState.FINAL_DECISION)
        message = f"Claim approved by {operator}. Moved to FINAL_DECISION."
    else:
        message = f"Claim acknowledged by {operator}. State unchanged."
    
    # Reset investigation flag
    claim.requires_investigation = False
    
    # Add audit entry
    claim.add_audit_entry(
        agent_name=operator,
        decision="APPROVED",
        raw_reasoning=f"{reason}. Previous state: {previous_state.value}"
    )
    
    claims_store[claim_id] = claim
    
    return HumanOverrideResponse(
        claim_id=claim_id,
        action="APPROVED",
        previous_state=previous_state,
        new_state=claim.current_state,
        message=message
    )


@router.post("/{claim_id}/reject", response_model=HumanOverrideResponse)
async def reject_claim(
    claim_id: str,
    request: HumanOverrideRequest | None = None
) -> HumanOverrideResponse:
    """
    Human operator rejects a claim.
    
    The claim is moved to FINAL_DECISION with a rejection note.
    """
    claim = claims_store.get(claim_id)
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found"
        )
    
    operator = request.operator_name if request else "Human Operator"
    reason = request.reason if request and request.reason else "Claim rejected after review"
    
    previous_state = claim.current_state
    
    # Clear any pending states
    claim.pending_states.clear()
    
    # Move to final decision
    claim.record_state_change(ClaimState.FINAL_DECISION)
    claim.human_override = f"Rejected by {operator}: {reason}"
    
    # Add audit entry
    claim.add_audit_entry(
        agent_name=operator,
        decision="REJECTED",
        raw_reasoning=reason
    )
    
    claims_store[claim_id] = claim
    
    return HumanOverrideResponse(
        claim_id=claim_id,
        action="REJECTED",
        previous_state=previous_state,
        new_state=claim.current_state,
        message=f"Claim rejected by {operator}. Reason: {reason}"
    )


# ============================================
# DASHBOARD HELPER ENDPOINTS
# ============================================

@router.get("/dashboard/summary")
async def get_dashboard_summary():
    """Get summary statistics for the dashboard."""
    claims = list(claims_store.values())
    
    state_counts = {}
    for state in ClaimState:
        state_counts[state.value] = sum(1 for c in claims if c.current_state == state)
    
    fraud_flagged = sum(1 for c in claims if c.requires_investigation)
    
    return {
        "total_claims": len(claims),
        "state_counts": state_counts,
        "fraud_flagged": fraud_flagged,
        "claims": [
            {
                "id": c.id,
                "claimant": c.claimant_name,
                "amount": c.amount,
                "state": c.current_state.value,
                "requires_investigation": c.requires_investigation,
                "created_at": c.created_at.isoformat()
            }
            for c in claims
        ]
    }
