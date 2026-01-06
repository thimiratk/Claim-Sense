"""
Vision Agent Module

Provides local vision analysis using Ollama + Llama 3.2-Vision for damage detection
and fraud identification in insurance claims.
"""
import base64
import json
import logging
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class VisionAnalysisResult(BaseModel):
    """Structured result from vision analysis."""
    detected_damage: str
    mismatch_found: bool
    reasoning: str
    confidence: float = 0.0
    raw_response: Optional[str] = None


# System prompt for the Insurance Adjuster role
INSURANCE_ADJUSTER_PROMPT = """You are an expert Insurance Adjuster AI. Your task is to analyze vehicle damage photos and compare them with the claimant's description.

IMPORTANT INSTRUCTIONS:
1. Carefully examine the image to identify ALL visible damage (scratches, dents, broken parts, etc.)
2. Note the LOCATION of damage (front, rear, left side, right side, roof, etc.)
3. Compare your observations with the claimant's description
4. Flag any MISMATCH between what you see and what was described

MISMATCH EXAMPLES:
- Claimant says "front hit" but photo shows rear damage = MISMATCH
- Claimant says "minor scratch" but photo shows major dent = MISMATCH
- Claimant says "left door damage" but damage is on right side = MISMATCH

You MUST respond with ONLY a valid JSON object in this exact format:
{
    "detected_damage": "Description of damage visible in the photo including location",
    "mismatch_found": true or false,
    "reasoning": "Explanation of why there is or isn't a mismatch between photo and description"
}

Do not include any text outside the JSON object. Do not use markdown code blocks."""


async def analyze_damage_locally(
    image_path: str,
    claim_description: str,
    model: str = "llama3.2-vision"
) -> VisionAnalysisResult:
    """
    Analyze vehicle damage using local Ollama with Llama 3.2-Vision.
    
    Args:
        image_path: Path to the image file
        claim_description: The claimant's description of the damage
        model: Ollama model to use (default: llama3.2-vision)
        
    Returns:
        VisionAnalysisResult with detected damage and mismatch analysis
    """
    try:
        import ollama
    except ImportError:
        logger.error("ollama package not installed. Run: pip install ollama")
        raise ImportError("ollama package required. Install with: pip install ollama")
    
    # Read and encode the image
    image_file = Path(image_path)
    if not image_file.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    with open(image_file, "rb") as f:
        image_data = f.read()
    
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    
    # Construct the prompt
    user_prompt = f"""Analyze this vehicle damage photo.

CLAIMANT'S DESCRIPTION: "{claim_description}"

Examine the image carefully and determine:
1. What damage is actually visible in the photo?
2. Does the visible damage match the claimant's description?
3. Is there any mismatch or inconsistency?

Respond with ONLY a JSON object as specified."""

    logger.info(f"Sending image to Ollama model '{model}' for analysis")
    logger.info(f"Claim description: {claim_description}")
    
    try:
        # Call Ollama with the vision model
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": INSURANCE_ADJUSTER_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": [image_base64]
                }
            ]
        )
        
        raw_response = response["message"]["content"]
        logger.info(f"Received response from Ollama: {raw_response[:200]}...")
        
        # Parse the JSON response
        result = _parse_vision_response(raw_response)
        result.raw_response = raw_response
        
        return result
        
    except Exception as e:
        logger.error(f"Error calling Ollama: {e}")
        raise RuntimeError(f"Failed to analyze image with Ollama: {e}")


def _parse_vision_response(response_text: str) -> VisionAnalysisResult:
    """
    Parse the vision model's response into structured data.
    
    Handles various response formats and extracts JSON.
    """
    # Try to extract JSON from the response
    try:
        # First, try direct JSON parsing
        data = json.loads(response_text.strip())
    except json.JSONDecodeError:
        # Try to find JSON in the response using regex
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                # Fallback: create a result from the raw text
                logger.warning("Could not parse JSON from response, using fallback")
                return VisionAnalysisResult(
                    detected_damage="Unable to parse structured response",
                    mismatch_found=False,
                    reasoning=response_text[:500],
                    confidence=0.3
                )
        else:
            # No JSON found, analyze keywords
            logger.warning("No JSON found in response, analyzing keywords")
            mismatch_keywords = ["mismatch", "inconsistent", "doesn't match", "does not match", "suspicious"]
            has_mismatch = any(kw.lower() in response_text.lower() for kw in mismatch_keywords)
            
            return VisionAnalysisResult(
                detected_damage="See reasoning for details",
                mismatch_found=has_mismatch,
                reasoning=response_text[:500],
                confidence=0.5
            )
    
    # Validate and extract fields
    return VisionAnalysisResult(
        detected_damage=data.get("detected_damage", "No damage description provided"),
        mismatch_found=bool(data.get("mismatch_found", False)),
        reasoning=data.get("reasoning", "No reasoning provided"),
        confidence=0.85 if data.get("mismatch_found") else 0.75
    )


async def analyze_damage_from_bytes(
    image_bytes: bytes,
    claim_description: str,
    model: str = "llama3.2-vision"
) -> VisionAnalysisResult:
    """
    Analyze vehicle damage from image bytes directly.
    
    This is useful when receiving uploads via FastAPI.
    
    Args:
        image_bytes: Raw image bytes
        claim_description: The claimant's description of the damage
        model: Ollama model to use
        
    Returns:
        VisionAnalysisResult with detected damage and mismatch analysis
    """
    try:
        import ollama
    except ImportError:
        raise ImportError("ollama package required. Install with: pip install ollama")
    
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    user_prompt = f"""Analyze this vehicle damage photo.

CLAIMANT'S DESCRIPTION: "{claim_description}"

Examine the image carefully and determine:
1. What damage is actually visible in the photo?
2. Does the visible damage match the claimant's description?
3. Is there any mismatch or inconsistency?

Respond with ONLY a JSON object as specified."""

    logger.info(f"Analyzing image bytes with Ollama model '{model}'")
    
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": INSURANCE_ADJUSTER_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": [image_base64]
                }
            ]
        )
        
        raw_response = response["message"]["content"]
        logger.info(f"Vision analysis complete")
        
        result = _parse_vision_response(raw_response)
        result.raw_response = raw_response
        
        return result
        
    except Exception as e:
        logger.error(f"Error calling Ollama: {e}")
        raise RuntimeError(f"Failed to analyze image with Ollama: {e}")
