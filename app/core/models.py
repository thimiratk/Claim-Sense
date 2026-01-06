"""
Claim Pydantic Models

Defines the data models for insurance claims with validation.
"""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .states import ClaimState


class AuditLogEntry(BaseModel):
    """Entry in the claim audit log for explainability."""
    agent_name: str = Field(..., description="Name of the agent or system that made the decision")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the event occurred")
    decision: str = Field(..., description="The decision or action taken")
    raw_reasoning: str = Field(default="", description="Detailed reasoning from the agent")
    confidence: Optional[float] = Field(default=None, description="Confidence score if available")


class ClaimCreate(BaseModel):
    """Request model for creating a new claim."""
    claimant_name: str = Field(..., min_length=1, description="Name of the claimant")
    amount: float = Field(..., gt=0, description="Claim amount in dollars")
    description: str = Field(..., min_length=1, description="Description of the claim")
    requires_investigation: bool = Field(
        default=False, 
        description="Flag indicating if fraud investigation is required"
    )


class Claim(BaseModel):
    """
    Insurance Claim Model
    
    Represents a claim moving through the state machine with full history tracking.
    """
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique claim identifier")
    claimant_name: str = Field(..., description="Name of the claimant")
    amount: float = Field(..., gt=0, description="Claim amount in dollars")
    description: str = Field(..., description="Description of the claim")
    requires_investigation: bool = Field(
        default=False, 
        description="Flag indicating if fraud investigation is required"
    )
    current_state: ClaimState = Field(
        default=ClaimState.SUBMITTED, 
        description="Current state of the claim"
    )
    state_history: List[ClaimState] = Field(
        default_factory=list, 
        description="History of all states the claim has been in"
    )
    pending_states: List[ClaimState] = Field(
        default_factory=list,
        description="States that have been dynamically inserted and are pending"
    )
    vision_analysis: Optional[dict] = Field(
        default=None,
        description="Results from vision-based damage analysis"
    )
    photo_path: Optional[str] = Field(
        default=None,
        description="Path to uploaded damage photo"
    )
    photo_base64: Optional[str] = Field(
        default=None,
        description="Base64 encoded photo for dashboard display"
    )
    call_log: Optional[str] = Field(
        default=None,
        description="Transcript of initial phone call with claimant"
    )
    text_analysis: Optional[dict] = Field(
        default=None,
        description="Results from text consistency analysis"
    )
    audit_log: List[AuditLogEntry] = Field(
        default_factory=list,
        description="Audit trail of all agent decisions and actions"
    )
    human_override: Optional[str] = Field(
        default=None,
        description="Human operator override decision if any"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, 
        description="Timestamp when claim was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, 
        description="Timestamp of last update"
    )

    class Config:
        use_enum_values = False  # Keep enum objects, not just values

    def record_state_change(self, new_state: ClaimState) -> None:
        """Record a state transition in history."""
        if self.current_state not in self.state_history:
            self.state_history.append(self.current_state)
        self.current_state = new_state
        self.updated_at = datetime.now()

    def add_audit_entry(
        self, 
        agent_name: str, 
        decision: str, 
        raw_reasoning: str = "",
        confidence: Optional[float] = None
    ) -> None:
        """Add an entry to the audit log."""
        entry = AuditLogEntry(
            agent_name=agent_name,
            decision=decision,
            raw_reasoning=raw_reasoning,
            confidence=confidence
        )
        self.audit_log.append(entry)
        self.updated_at = datetime.now()

