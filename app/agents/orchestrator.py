"""
Multi-Agent Orchestrator

Coordinates multiple agents (Vision, Text) and aggregates their results
to make fraud detection decisions.
"""
import logging
from dataclasses import dataclass
from typing import Optional, List

from pydantic import BaseModel

from app.core.models import Claim
from app.core.states import ClaimState
from app.agents.vision_agent import VisionAnalysisResult
from app.agents.text_agent import TextAnalysisResult

logger = logging.getLogger(__name__)


class OrchestratorResult(BaseModel):
    """Combined result from all agents."""
    requires_investigation: bool
    fraud_score: float  # 0.0 to 1.0
    vision_flagged: bool
    text_flagged: bool
    reasons: List[str]
    summary: str


class MultiAgentOrchestrator:
    """
    Orchestrates multiple analysis agents and aggregates their results.
    
    Decision logic:
    - If ANY agent flags suspicious activity, trigger investigation
    - Combine scores from all agents for overall fraud probability
    """
    
    # Thresholds for triggering investigation
    VISION_MISMATCH_THRESHOLD = True  # Any mismatch triggers
    TEXT_INCONSISTENCY_THRESHOLD = 5  # Score >= 5 triggers
    
    def __init__(self):
        self.vision_result: Optional[VisionAnalysisResult] = None
        self.text_result: Optional[TextAnalysisResult] = None
    
    def evaluate_results(
        self,
        vision_result: Optional[VisionAnalysisResult] = None,
        text_result: Optional[TextAnalysisResult] = None
    ) -> OrchestratorResult:
        """
        Evaluate results from all available agents.
        
        Args:
            vision_result: Result from vision agent (optional)
            text_result: Result from text agent (optional)
            
        Returns:
            OrchestratorResult with combined decision
        """
        self.vision_result = vision_result
        self.text_result = text_result
        
        vision_flagged = False
        text_flagged = False
        reasons = []
        fraud_scores = []
        
        # Evaluate vision agent result
        if vision_result:
            vision_flagged = vision_result.mismatch_found
            if vision_flagged:
                reasons.append(f"Vision Agent: {vision_result.reasoning}")
                fraud_scores.append(0.8 if vision_result.confidence > 0.7 else 0.5)
            else:
                fraud_scores.append(0.1)
        
        # Evaluate text agent result
        if text_result:
            text_flagged = text_result.inconsistency_score >= self.TEXT_INCONSISTENCY_THRESHOLD
            if text_flagged:
                reasons.append(f"Text Agent: {text_result.verdict} (score: {text_result.inconsistency_score}/10)")
                if text_result.contradictions:
                    reasons.extend([f"  - {c}" for c in text_result.contradictions[:3]])
                fraud_scores.append(text_result.inconsistency_score / 10.0)
            else:
                fraud_scores.append(text_result.inconsistency_score / 20.0)  # Lower weight if not flagged
        
        # Calculate overall fraud score
        fraud_score = max(fraud_scores) if fraud_scores else 0.0
        
        # Decision: investigate if ANY agent flags
        requires_investigation = vision_flagged or text_flagged
        
        # Build summary
        agents_run = []
        if vision_result:
            agents_run.append(f"Vision({'⚠️' if vision_flagged else '✓'})")
        if text_result:
            agents_run.append(f"Text({'⚠️' if text_flagged else '✓'})")
        
        summary = f"Agents: {', '.join(agents_run)}. "
        if requires_investigation:
            summary += f"FRAUD INVESTIGATION REQUIRED. Score: {fraud_score:.2f}"
        else:
            summary += f"No suspicious activity detected. Score: {fraud_score:.2f}"
        
        logger.info(f"Orchestrator decision: investigation={requires_investigation}, score={fraud_score:.2f}")
        
        return OrchestratorResult(
            requires_investigation=requires_investigation,
            fraud_score=fraud_score,
            vision_flagged=vision_flagged,
            text_flagged=text_flagged,
            reasons=reasons,
            summary=summary
        )
    
    def should_trigger_investigation(
        self,
        vision_result: Optional[VisionAnalysisResult] = None,
        text_result: Optional[TextAnalysisResult] = None
    ) -> bool:
        """Quick check if investigation should be triggered."""
        result = self.evaluate_results(vision_result, text_result)
        return result.requires_investigation


# Global orchestrator instance
orchestrator = MultiAgentOrchestrator()


def update_claim_for_investigation(
    claim: Claim,
    orchestrator_result: OrchestratorResult
) -> Claim:
    """
    Update claim based on orchestrator decision.
    
    If investigation required, insert FRAUD_INVESTIGATION state.
    """
    if orchestrator_result.requires_investigation:
        claim.requires_investigation = True
        
        # Insert FRAUD_INVESTIGATION if not already pending
        if ClaimState.FRAUD_INVESTIGATION not in claim.pending_states:
            claim.pending_states.insert(0, ClaimState.FRAUD_INVESTIGATION)
            logger.info(f"Claim {claim.id}: FRAUD_INVESTIGATION state inserted")
    
    return claim
