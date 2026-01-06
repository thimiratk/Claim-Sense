"""
Process Monitor

Watches claim state changes and triggers appropriate actions.
"""
import asyncio
import logging
from typing import Callable, Awaitable, Optional

from app.core.models import Claim
from app.core.states import ClaimState
from app.state_machine.machine import ClaimStateMachine
from app.agents.evaluator import agent_evaluation

logger = logging.getLogger(__name__)


class ProcessMonitor:
    """
    Monitors claim processing and triggers event hooks.
    
    When a claim enters specific states, the monitor triggers
    appropriate async actions like agent evaluation.
    """
    
    def __init__(self, state_machine: ClaimStateMachine):
        """
        Initialize the process monitor.
        
        Args:
            state_machine: The state machine to use for transitions
        """
        self.state_machine = state_machine
        self._event_handlers: dict[ClaimState, list[Callable[[Claim], Awaitable[Claim]]]] = {}
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """Register default event handlers for states."""
        # When entering UNDER_REVIEW, trigger agent evaluation
        self.register_handler(ClaimState.UNDER_REVIEW, self._on_under_review)
    
    def register_handler(
        self, 
        state: ClaimState, 
        handler: Callable[[Claim], Awaitable[Claim]]
    ) -> None:
        """
        Register an async handler to be called when a claim enters a state.
        
        Args:
            state: The state that triggers the handler
            handler: Async function to call with the claim
        """
        if state not in self._event_handlers:
            self._event_handlers[state] = []
        self._event_handlers[state].append(handler)
        logger.info(f"Registered handler for state {state}")
    
    async def _on_under_review(self, claim: Claim) -> Claim:
        """
        Handler for when a claim enters UNDER_REVIEW state.
        
        Triggers agent evaluation and potentially inserts
        FRAUD_INVESTIGATION state.
        """
        logger.info(f"Claim {claim.id} entered UNDER_REVIEW - triggering agent evaluation")
        
        # Run the agent evaluation
        requires_investigation, results = await agent_evaluation(claim)
        
        if requires_investigation:
            logger.info(
                f"Claim {claim.id} flagged for investigation - "
                f"inserting FRAUD_INVESTIGATION state"
            )
            # Dynamically insert FRAUD_INVESTIGATION before ASSESSMENT
            self.state_machine.insert_state(
                claim,
                ClaimState.FRAUD_INVESTIGATION,
                ClaimState.ASSESSMENT
            )
        else:
            logger.info(f"Claim {claim.id} passed evaluation - no investigation needed")
        
        return claim
    
    async def on_state_entered(self, claim: Claim, state: ClaimState) -> Claim:
        """
        Called when a claim enters a new state.
        
        Triggers all registered handlers for the state.
        
        Args:
            claim: The claim that changed state
            state: The state that was entered
            
        Returns:
            Updated claim after all handlers have run
        """
        handlers = self._event_handlers.get(state, [])
        
        for handler in handlers:
            claim = await handler(claim)
        
        return claim
    
    async def advance_claim(self, claim: Claim) -> Claim:
        """
        Advance a claim to its next state and trigger handlers.
        
        This is the main method for processing claims through
        the state machine with event hooks.
        
        Args:
            claim: The claim to advance
            
        Returns:
            Updated claim after transition and handlers
        """
        # Get the next state
        next_state = self.state_machine.get_next_state(claim)
        
        if next_state is None:
            raise ValueError(f"Claim {claim.id} is in terminal state {claim.current_state}")
        
        # Perform the transition
        claim = self.state_machine.transition(claim, next_state)
        
        logger.info(f"Claim {claim.id} transitioned to {next_state}")
        
        # Trigger state entry handlers
        claim = await self.on_state_entered(claim, next_state)
        
        return claim
