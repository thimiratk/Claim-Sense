"""
Full Cycle Test Script for Multi-Agent Insurance System

Tests the complete workflow:
1. Customer submits claim (Claimant Portal)
2. Photo is uploaded and analyzed (Vision Agent)
3. Text is analyzed for consistency (Text Agent)
4. Admin reviews claim (Dashboard)
5. Claim is approved/rejected

Run with: python test_full_cycle.py

Prerequisites:
- FastAPI server running on http://localhost:8000
- Ollama running with llama3.2-vision and llama3
"""
import requests
import time
import os

# Configuration
API_URL = "http://localhost:8000"
TEST_IMAGE_PATH = "test_rear_damage.png"  # Use existing test image

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_step(step_num: int, message: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}[Step {step_num}]{Colors.END} {message}")


def print_success(message: str):
    print(f"  {Colors.GREEN}✓ {message}{Colors.END}")


def print_warning(message: str):
    print(f"  {Colors.YELLOW}⚠ {message}{Colors.END}")


def print_error(message: str):
    print(f"  {Colors.RED}✗ {message}{Colors.END}")


def print_info(message: str):
    print(f"  → {message}")


def test_health_check():
    """Test API connection."""
    print_step(0, "Testing API Connection")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("API is healthy and responding")
            return True
        else:
            print_error(f"API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to API. Is the server running?")
        print_info(f"Expected: uvicorn app.main:app --reload --port 8000")
        return False


def test_create_claim():
    """Step 1: Create a new claim (simulates Claimant Portal submission)."""
    print_step(1, "Creating Claim (Claimant Portal)")
    
    claim_data = {
        "claimant_name": "John Doe - POL-12345",
        "amount": 7500.00,
        "description": """
        On January 5th, 2026, at approximately 3:30 PM, I was rear-ended 
        while stopped at a red light on Main Street. The weather was clear 
        and sunny. The other driver was texting and didn't see me stop.
        My rear bumper, trunk lid, and tail lights are damaged.
        """,
        "requires_investigation": False
    }
    
    response = requests.post(f"{API_URL}/claims/", json=claim_data)
    
    if response.status_code == 201:
        result = response.json()
        claim_id = result["claim"]["id"]
        print_success(f"Claim created with ID: {claim_id[:8]}...")
        print_info(f"State: {result['claim']['current_state']}")
        return claim_id
    else:
        print_error(f"Failed to create claim: {response.text}")
        return None


def test_upload_photo(claim_id: str):
    """Step 2: Upload damage photo (Vision Agent analysis)."""
    print_step(2, "Uploading Photo for Vision Analysis")
    
    if not os.path.exists(TEST_IMAGE_PATH):
        print_warning(f"Test image not found: {TEST_IMAGE_PATH}")
        print_info("Skipping photo upload...")
        return None
    
    with open(TEST_IMAGE_PATH, "rb") as f:
        files = {"photo": (TEST_IMAGE_PATH, f, "image/png")}
        
        print_info("Sending to Vision Agent (this may take 30-60 seconds)...")
        start_time = time.time()
        
        response = requests.post(
            f"{API_URL}/claims/{claim_id}/upload-photo",
            files=files,
            timeout=120
        )
        
        elapsed = time.time() - start_time
    
    if response.status_code == 200:
        result = response.json()
        print_success(f"Photo analyzed in {elapsed:.1f}s")
        print_info(f"Fraud Detected: {result['fraud_detected']}")
        print_info(f"Message: {result['message'][:100]}...")
        return result
    else:
        print_error(f"Photo upload failed: {response.text}")
        return None


def test_text_analysis(claim_id: str):
    """Step 3: Run text consistency analysis (Text Agent)."""
    print_step(3, "Running Text Consistency Analysis")
    
    # Simulated call log that should be consistent with the claim
    call_log_consistent = """
    Agent: Thank you for calling. Can you describe what happened?
    Customer: I was rear-ended at a red light on Main Street around 3:30 PM.
    Agent: What was the weather like?
    Customer: It was clear and sunny.
    Agent: And what damage occurred?
    Customer: The rear bumper, trunk, and tail lights were damaged.
    """
    
    print_info("Analyzing call log vs written claim...")
    start_time = time.time()
    
    response = requests.post(
        f"{API_URL}/claims/{claim_id}/analyze-text",
        json={
            "call_log": call_log_consistent,
            "written_claim": None  # Use claim description
        },
        timeout=120
    )
    
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        result = response.json()
        analysis = result["analysis"]
        print_success(f"Text analyzed in {elapsed:.1f}s")
        print_info(f"Verdict: {analysis['verdict']}")
        print_info(f"Inconsistency Score: {analysis['inconsistency_score']}/10")
        return result
    else:
        print_error(f"Text analysis failed: {response.text}")
        return None


def test_get_claim_status(claim_id: str):
    """Step 4: Check claim status (Dashboard view)."""
    print_step(4, "Fetching Claim Status (Dashboard View)")
    
    response = requests.get(f"{API_URL}/claims/{claim_id}")
    
    if response.status_code == 200:
        result = response.json()
        claim = result["claim"]
        print_success("Claim retrieved")
        print_info(f"State: {claim['current_state']}")
        print_info(f"Requires Investigation: {claim['requires_investigation']}")
        print_info(f"State History: {claim['state_history']}")
        
        if claim.get("vision_analysis"):
            print_info("Vision Analysis: ✓ Complete")
        if claim.get("text_analysis"):
            print_info("Text Analysis: ✓ Complete")
            
        return result
    else:
        print_error(f"Failed to get claim: {response.text}")
        return None


def test_advance_claim(claim_id: str):
    """Step 5: Advance claim through states."""
    print_step(5, "Advancing Claim State")
    
    response = requests.post(f"{API_URL}/claims/{claim_id}/advance")
    
    if response.status_code == 200:
        result = response.json()
        print_success(f"Claim advanced to: {result['claim']['current_state']}")
        print_info(f"Next valid states: {[s for s in result['next_valid_states']]}")
        return result
    else:
        print_error(f"Failed to advance: {response.text}")
        return None


def test_approve_claim(claim_id: str):
    """Step 6: Human operator approves claim (Dashboard action)."""
    print_step(6, "Approving Claim (Human Operator)")
    
    response = requests.post(
        f"{API_URL}/claims/{claim_id}/approve",
        json={
            "operator_name": "Test Operator",
            "reason": "All checks passed - automated test"
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print_success(f"Claim approved!")
        print_info(f"Previous State: {result['previous_state']}")
        print_info(f"New State: {result['new_state']}")
        print_info(f"Message: {result['message']}")
        return result
    else:
        print_error(f"Failed to approve: {response.text}")
        return None


def test_dashboard_summary():
    """Step 7: View dashboard summary."""
    print_step(7, "Dashboard Summary")
    
    response = requests.get(f"{API_URL}/claims/dashboard/summary")
    
    if response.status_code == 200:
        result = response.json()
        print_success("Dashboard summary retrieved")
        print_info(f"Total Claims: {result['total_claims']}")
        print_info(f"Fraud Flagged: {result['fraud_flagged']}")
        print_info(f"State Counts: {result['state_counts']}")
        return result
    else:
        print_error(f"Failed to get summary: {response.text}")
        return None


def run_full_cycle_test():
    """Run the complete test cycle."""
    print(f"\n{'='*60}")
    print(f"{Colors.BOLD}  FULL CYCLE TEST - Multi-Agent Insurance System{Colors.END}")
    print(f"{'='*60}")
    print(f"\nAPI URL: {API_URL}")
    
    # Step 0: Health check
    if not test_health_check():
        return
    
    # Step 1: Create claim
    claim_id = test_create_claim()
    if not claim_id:
        return
    
    # Step 2: Upload photo
    test_upload_photo(claim_id)
    
    # Step 3: Text analysis
    test_text_analysis(claim_id)
    
    # Step 4: Check status
    test_get_claim_status(claim_id)
    
    # Step 5: Advance claim
    test_advance_claim(claim_id)
    
    # Step 6: Approve claim
    test_approve_claim(claim_id)
    
    # Step 7: Dashboard summary
    test_dashboard_summary()
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"{Colors.BOLD}{Colors.GREEN}  ✓ FULL CYCLE TEST COMPLETE{Colors.END}")
    print(f"{'='*60}")
    print(f"\nClaim ID: {claim_id}")
    print("\nYou can now:")
    print(f"  1. View this claim in Dashboard: streamlit run dashboard.py")
    print(f"  2. Submit more claims: streamlit run client_app.py")
    print(f"  3. Check API docs: {API_URL}/docs")


if __name__ == "__main__":
    run_full_cycle_test()
