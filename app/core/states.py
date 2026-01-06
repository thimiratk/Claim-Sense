"""
Claim State Definitions

Defines all possible states for an insurance claim in the orchestration system.
"""
from enum import Enum


class ClaimState(str, Enum):
    """
    Enum representing the possible states of an insurance claim.
    
    Standard Flow: SUBMITTED -> UNDER_REVIEW -> ASSESSMENT -> FINAL_DECISION
    With Investigation: SUBMITTED -> UNDER_REVIEW -> FRAUD_INVESTIGATION -> ASSESSMENT -> FINAL_DECISION
    """
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    FRAUD_INVESTIGATION = "FRAUD_INVESTIGATION"  # Dynamic state - inserted when needed
    ASSESSMENT = "ASSESSMENT"
    FINAL_DECISION = "FINAL_DECISION"
