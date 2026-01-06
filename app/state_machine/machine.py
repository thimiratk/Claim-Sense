"""
Claim State Machine

Manages state transitions and dynamic state insertion for insurance claims.
"""
from typing import Dict, List, Set

from app.core.states import ClaimState
from app.core.models import Claim


class ClaimStateMachine:
    """
    State machine for managing claim state transitions.
    
    Supports dynamic state insertion for routing claims through
    additional processing steps like fraud investigation.
    """
    
    # Define standard state flow
    STANDARD_FLOW: List[ClaimState] = [
        ClaimState.SUBMITTED,
        ClaimState.UNDER_REVIEW,
        ClaimState.ASSESSMENT,
        ClaimState.FINAL_DECISION
    ]
    
    # Define valid transitions (from_state -> set of valid to_states)
    TRANSITIONS: Dict[ClaimState, Set[ClaimState]] = {
        ClaimState.SUBMITTED: {ClaimState.UNDER_REVIEW},
        ClaimState.UNDER_REVIEW: {ClaimState.ASSESSMENT, ClaimState.FRAUD_INVESTIGATION},
        ClaimState.FRAUD_INVESTIGATION: {ClaimState.ASSESSMENT},
        ClaimState.ASSESSMENT: {ClaimState.FINAL_DECISION},
        ClaimState.FINAL_DECISION: set()  # Terminal state
    }

    def __init__(self):
        """Initialize the state machine."""
        pass

    def get_valid_transitions(self, claim: Claim) -> List[ClaimState]:
        """
        Get list of valid next states for a claim.
        
        If claim has pending states from dynamic insertion, those take priority.
        """
        # If there are pending states, the next state must be the first pending state
        if claim.pending_states:
            return [claim.pending_states[0]]
        
        # Otherwise, return standard valid transitions
        return list(self.TRANSITIONS.get(claim.current_state, set()))

    def can_transition(self, claim: Claim, target_state: ClaimState) -> bool:
        """Check if a transition to target_state is valid."""
        valid_states = self.get_valid_transitions(claim)
        return target_state in valid_states

    def transition(self, claim: Claim, target_state: ClaimState) -> Claim:
        """
        Execute a state transition.
        
        Args:
            claim: The claim to transition
            target_state: The desired next state
            
        Returns:
            Updated claim with new state
            
        Raises:
            ValueError: If the transition is not valid
        """
        if not self.can_transition(claim, target_state):
            valid = self.get_valid_transitions(claim)
            raise ValueError(
                f"Invalid transition from {claim.current_state} to {target_state}. "
                f"Valid transitions: {valid}"
            )
        
        # Remove from pending if it was a dynamically inserted state
        if claim.pending_states and target_state == claim.pending_states[0]:
            claim.pending_states.pop(0)
        
        # Record the state change
        claim.record_state_change(target_state)
        
        return claim

    def insert_state(
        self, 
        claim: Claim, 
        new_state: ClaimState, 
        before_state: ClaimState
    ) -> Claim:
        """
        Dynamically insert a state into the claim's workflow.
        
        The new state will be processed before the specified 'before_state'.
        
        Args:
            claim: The claim to modify
            new_state: The state to insert
            before_state: The state that should come after the inserted state
            
        Returns:
            Updated claim with new pending state
        """
        # Validate that the insertion makes sense
        if new_state not in self.TRANSITIONS:
            raise ValueError(f"Unknown state: {new_state}")
        
        if before_state not in self.TRANSITIONS.get(new_state, set()):
            raise ValueError(
                f"Cannot insert {new_state} before {before_state}. "
                f"{new_state} does not transition to {before_state}"
            )
        
        # Add to pending states (will be processed before continuing normal flow)
        if new_state not in claim.pending_states:
            claim.pending_states.insert(0, new_state)
        
        return claim

    def get_next_state(self, claim: Claim) -> ClaimState | None:
        """
        Get the next state in the workflow.
        
        Considers both pending states and standard flow.
        """
        valid_transitions = self.get_valid_transitions(claim)
        
        if not valid_transitions:
            return None
        
        # If there are pending states, return the first one
        if claim.pending_states:
            return claim.pending_states[0]
        
        # Otherwise, return the first valid transition (standard flow)
        return valid_transitions[0] if valid_transitions else None

    def advance(self, claim: Claim) -> Claim:
        """
        Advance the claim to the next state in its workflow.
        
        Returns:
            Updated claim
            
        Raises:
            ValueError: If there is no valid next state
        """
        next_state = self.get_next_state(claim)
        
        if next_state is None:
            raise ValueError(
                f"Cannot advance claim. Current state {claim.current_state} is terminal."
            )
        
        return self.transition(claim, next_state)
