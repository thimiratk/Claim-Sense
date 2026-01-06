"""
Agent Evaluation Module

Simulates multi-agent evaluation of insurance claims.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Tuple

from app.core.models import Claim

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from an individual agent's evaluation."""
    agent_name: str
    requires_investigation: bool
    confidence: float
    reason: str


async def _agent_alpha_evaluate(claim: Claim) -> AgentResult:
    """
    Agent Alpha: Primary fraud detection agent.
    
    Simulates analysis based on claim amount and flags.
    """
    # Simulate processing time
    await asyncio.sleep(0.1)
    
    # Simple heuristic: high amounts or explicit flag triggers investigation
    suspicious = claim.amount > 50000 or claim.requires_investigation
    
    return AgentResult(
        agent_name="Agent Alpha",
        requires_investigation=suspicious,
        confidence=0.85 if suspicious else 0.75,
        reason="High claim amount detected" if claim.amount > 50000 
               else "Investigation flag set" if claim.requires_investigation
               else "No anomalies detected"
    )


async def _agent_beta_evaluate(claim: Claim) -> AgentResult:
    """
    Agent Beta: Secondary validation agent.
    
    Simulates cross-validation of claim data.
    """
    # Simulate processing time
    await asyncio.sleep(0.1)
    
    # Simple heuristic: respects the requires_investigation flag
    suspicious = claim.requires_investigation
    
    return AgentResult(
        agent_name="Agent Beta",
        requires_investigation=suspicious,
        confidence=0.90 if suspicious else 0.80,
        reason="Cross-validation flagged for review" if suspicious
               else "Cross-validation passed"
    )


async def agent_evaluation(claim: Claim) -> Tuple[bool, list[AgentResult]]:
    """
    Orchestrate multi-agent evaluation of a claim.
    
    Runs two agents in parallel to evaluate whether a claim
    requires fraud investigation.
    
    Args:
        claim: The claim to evaluate
        
    Returns:
        Tuple of (requires_investigation: bool, agent_results: list)
    """
    logger.info(f"Starting agent evaluation for claim {claim.id}")
    
    # Run both agents concurrently
    results = await asyncio.gather(
        _agent_alpha_evaluate(claim),
        _agent_beta_evaluate(claim)
    )
    
    # Decision: if ANY agent flags for investigation, we investigate
    requires_investigation = any(r.requires_investigation for r in results)
    
    logger.info(
        f"Agent evaluation complete for claim {claim.id}. "
        f"Investigation required: {requires_investigation}"
    )
    
    for result in results:
        logger.info(
            f"  - {result.agent_name}: "
            f"investigate={result.requires_investigation}, "
            f"confidence={result.confidence:.2f}, "
            f"reason='{result.reason}'"
        )
    
    return requires_investigation, list(results)
