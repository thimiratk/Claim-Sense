"""
Multi-Agent Orchestration System for Insurance Claims

FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as claims_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info("Starting Multi-Agent Orchestration System")
    yield
    logger.info("Shutting down Multi-Agent Orchestration System")


# Create FastAPI application
app = FastAPI(
    title="Multi-Agent Claim Orchestration System",
    description="""
    An MVP for orchestrating insurance claim processing using a multi-agent system.
    
    ## Features
    
    - **State Machine**: Claims flow through states: SUBMITTED → UNDER_REVIEW → ASSESSMENT → FINAL_DECISION
    - **Dynamic Routing**: Claims requiring investigation get routed through FRAUD_INVESTIGATION
    - **Event Hooks**: Async agent evaluation triggered when claims enter UNDER_REVIEW
    - **Multi-Agent Evaluation**: Two agents evaluate claims in parallel
    
    ## Workflow
    
    1. Create a claim with `POST /claims`
    2. Advance the claim with `POST /claims/{id}/advance`
    3. When entering UNDER_REVIEW, agents evaluate if investigation is needed
    4. If `requires_investigation=true`, FRAUD_INVESTIGATION state is dynamically inserted
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(claims_router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with system info."""
    return {
        "system": "Multi-Agent Claim Orchestration System",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
