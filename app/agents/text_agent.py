"""
Text Analysis Agent Module

Provides textual consistency analysis using Ollama + Llama 3 for
forensic linguistic comparison between call logs and written claims.
"""
import json
import logging
import re
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TextAnalysisResult(BaseModel):
    """Structured result from text consistency analysis."""
    inconsistency_score: int = Field(..., ge=0, le=10, description="Score from 0 (consistent) to 10 (highly suspicious)")
    contradictions: List[str] = Field(default_factory=list, description="List of specific contradictions found")
    verdict: str = Field(..., description="CONSISTENT or SUSPICIOUS")
    reasoning: str = Field(default="", description="Detailed analysis reasoning")
    raw_response: Optional[str] = None


# System prompt for the Forensic Linguist role
FORENSIC_LINGUIST_PROMPT = """You are an expert Forensic Linguist specializing in insurance fraud detection. Your task is to compare a phone call transcript with a written insurance claim to identify inconsistencies.

ANALYSIS FOCUS AREAS:

1. **FACT MISMATCHES**: Look for contradictory facts between the two accounts.
   - Weather conditions (e.g., call says "raining" vs claim says "clear skies")
   - Time of incident
   - Location details
   - Number of people/vehicles involved
   - Sequence of events

2. **STORY SHIFTS**: Detect changes in the narrative.
   - Cause of accident (e.g., call says "I hit a pole" vs claim says "another car hit me")
   - Who was at fault
   - What damage occurred
   - Actions taken before/after incident

3. **URGENCY/PRESSURE INDICATORS**: Detect suspicious behavioral patterns.
   - Evasive language in the call
   - Pressure to process claim quickly
   - Reluctance to provide details
   - Overly rehearsed statements

SCORING GUIDE:
- 0-2: Accounts are consistent, minor variations are normal
- 3-4: Some discrepancies that may warrant review
- 5-6: Notable inconsistencies that raise concerns
- 7-8: Significant contradictions suggesting possible fraud
- 9-10: Major fabrication indicators, accounts are fundamentally incompatible

You MUST respond with ONLY a valid JSON object in this exact format:
{
    "inconsistency_score": <0-10>,
    "contradictions": ["contradiction 1", "contradiction 2", ...],
    "verdict": "CONSISTENT" or "SUSPICIOUS",
    "reasoning": "Detailed explanation of your analysis"
}

Verdict should be "SUSPICIOUS" if inconsistency_score >= 5, otherwise "CONSISTENT".

Do not include any text outside the JSON object. Do not use markdown code blocks."""


async def analyze_text_consistency(
    call_log: str,
    written_claim: str,
    model: str = "llama3"
) -> TextAnalysisResult:
    """
    Analyze consistency between a call log transcript and written claim.
    
    Uses Ollama with Llama 3 to perform forensic linguistic analysis,
    detecting fact mismatches, story shifts, and suspicious patterns.
    
    Args:
        call_log: Transcript or summary of the phone call with the claimant
        written_claim: The written claim description submitted by the claimant
        model: Ollama model to use (default: llama3)
        
    Returns:
        TextAnalysisResult with inconsistency_score, contradictions, and verdict
    """
    try:
        import ollama
    except ImportError:
        logger.error("ollama package not installed. Run: pip install ollama")
        raise ImportError("ollama package required. Install with: pip install ollama")
    
    if not call_log or not call_log.strip():
        raise ValueError("Call log cannot be empty")
    
    if not written_claim or not written_claim.strip():
        raise ValueError("Written claim cannot be empty")
    
    # Construct the analysis prompt
    user_prompt = f"""Compare these two accounts from the same insurance claimant and identify any inconsistencies:

=== PHONE CALL TRANSCRIPT ===
{call_log}

=== WRITTEN CLAIM SUBMISSION ===
{written_claim}

Analyze for fact mismatches, story shifts, and suspicious patterns. Provide your analysis as a JSON object."""

    logger.info(f"Sending texts to Ollama model '{model}' for forensic analysis")
    logger.info(f"Call log length: {len(call_log)} chars, Written claim length: {len(written_claim)} chars")
    
    try:
        # Call Ollama with the text model
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": FORENSIC_LINGUIST_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )
        
        raw_response = response["message"]["content"]
        logger.info(f"Received response from Ollama: {raw_response[:200]}...")
        
        # Parse the JSON response
        result = _parse_text_analysis_response(raw_response)
        result.raw_response = raw_response
        
        return result
        
    except Exception as e:
        logger.error(f"Error calling Ollama: {e}")
        raise RuntimeError(f"Failed to analyze text with Ollama: {e}")


def _parse_text_analysis_response(response_text: str) -> TextAnalysisResult:
    """
    Parse the text model's response into structured data.
    
    Handles various response formats and extracts JSON.
    """
    # Try to extract JSON from the response
    try:
        # First, try direct JSON parsing
        data = json.loads(response_text.strip())
    except json.JSONDecodeError:
        # Try to find JSON in the response using regex
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                # Fallback: create a result from keyword analysis
                logger.warning("Could not parse JSON from response, using fallback")
                return _fallback_analysis(response_text)
        else:
            logger.warning("No JSON found in response, using fallback analysis")
            return _fallback_analysis(response_text)
    
    # Validate and extract fields
    score = int(data.get("inconsistency_score", 0))
    score = max(0, min(10, score))  # Clamp to 0-10
    
    contradictions = data.get("contradictions", [])
    if isinstance(contradictions, str):
        contradictions = [contradictions]
    
    verdict = data.get("verdict", "CONSISTENT")
    if verdict not in ["CONSISTENT", "SUSPICIOUS"]:
        verdict = "SUSPICIOUS" if score >= 5 else "CONSISTENT"
    
    return TextAnalysisResult(
        inconsistency_score=score,
        contradictions=list(contradictions),
        verdict=verdict,
        reasoning=data.get("reasoning", "No detailed reasoning provided")
    )


def _fallback_analysis(response_text: str) -> TextAnalysisResult:
    """
    Fallback analysis when JSON parsing fails.
    
    Uses keyword detection to estimate the result.
    """
    response_lower = response_text.lower()
    
    # Look for suspicion indicators
    suspicion_keywords = [
        "inconsistent", "contradiction", "mismatch", "suspicious",
        "discrepancy", "differs", "conflicting", "fabricat",
        "doesn't match", "does not match", "story changed"
    ]
    
    suspicion_count = sum(1 for kw in suspicion_keywords if kw in response_lower)
    
    # Estimate score based on keyword frequency
    if suspicion_count >= 4:
        score = 8
    elif suspicion_count >= 2:
        score = 5
    elif suspicion_count >= 1:
        score = 3
    else:
        score = 1
    
    return TextAnalysisResult(
        inconsistency_score=score,
        contradictions=["Unable to parse specific contradictions - see reasoning"],
        verdict="SUSPICIOUS" if score >= 5 else "CONSISTENT",
        reasoning=response_text[:500]
    )


async def quick_consistency_check(
    text1: str,
    text2: str,
    context: str = "insurance claim",
    model: str = "llama3"
) -> bool:
    """
    Quick check if two texts are consistent.
    
    Returns True if texts are consistent, False if suspicious.
    """
    result = await analyze_text_consistency(text1, text2, model)
    return result.verdict == "CONSISTENT"
