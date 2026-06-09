"""FastAPI application for AI-Claims-Orchestrator-Azure.

Single in-memory claims store — sufficient for the lecture demo.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from config import get_settings
from models.schemas import (
    AuditEntry,
    Claim,
    ClaimListItem,
    ClaimStatus,
    ClaimSubmission,
    ClaimType,
    HumanReviewAction,
    HumanReviewDecision,
)
from orchestrator import ClaimsOrchestrator
from utils.file_storage import file_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")

settings = get_settings()

app = FastAPI(
    title="AI Claims Orchestrator — Azure MVP",
    description="Insurance claims processing demo on Microsoft Azure AI stack (Computer Vision + Foundry/Claude).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store
CLAIMS: Dict[str, Claim] = {}
ORCHESTRATOR: ClaimsOrchestrator | None = None  # initialised on startup


# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    global ORCHESTRATOR
    log.info("Starting up — initialising orchestrator (this loads the embedding model)…")
    try:
        ORCHESTRATOR = ClaimsOrchestrator()
        log.info("Orchestrator ready.")
    except Exception as e:
        log.exception("Orchestrator init failed: %s", e)
        # Keep app running so /api/health still works; submit endpoint will 503.


@app.get("/api/health")
async def health():
    return {
        "status": "ok" if ORCHESTRATOR else "degraded",
        "orchestrator": "ready" if ORCHESTRATOR else "not_initialised",
        "azure_cv_endpoint": settings.azure_cv_endpoint,
        "foundry_endpoint": settings.foundry_endpoint,
        "model": settings.foundry_model,
        "policies_loaded": len(ORCHESTRATOR.rag.policies) if ORCHESTRATOR else 0,
        "past_claims_loaded": len(ORCHESTRATOR.rag.past_claims) if ORCHESTRATOR else 0,
    }


# ---------------------------------------------------------------------------

@app.post("/api/claims/submit")
async def submit_claim(
    background_tasks: BackgroundTasks,
    policy_number: str = Form(...),
    claimant_name: str = Form(...),
    claimant_email: str = Form(...),
    incident_date: str = Form(...),
    claim_type: str = Form("auto_collision"),
    claim_amount: float = Form(...),
    description: str = Form(...),
    vehicle_make_model: str = Form(""),
    images: List[UploadFile] = File(default_factory=list),
    documents: List[UploadFile] = File(default_factory=list),
):
    """Submit a claim with car-damage images and supporting documents."""
    if ORCHESTRATOR is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialised. Check backend logs.")

    try:
        ct = ClaimType(claim_type)
    except ValueError:
        ct = ClaimType.AUTO_COLLISION

    submission = ClaimSubmission(
        policy_number=policy_number,
        claim_type=ct,
        claim_amount=claim_amount,
        incident_date=incident_date,
        description=description,
        claimant_name=claimant_name,
        claimant_email=claimant_email,
        vehicle_make_model=vehicle_make_model or None,
    )

    claim_id = f"CLM-AZ-{uuid.uuid4().hex[:8].upper()}"
    claim = Claim(
        claim_id=claim_id,
        submission=submission,
        status=ClaimStatus.SUBMITTED,
        current_step="Submitted, awaiting analysis",
        progress_percentage=5,
    )

    # Persist uploads
    for f in images or []:
        if not f.filename:
            continue
        content = await f.read()
        saved = file_storage.save(claim_id, "images", content, f.filename)
        claim.image_files.append(saved)
    for f in documents or []:
        if not f.filename:
            continue
        content = await f.read()
        saved = file_storage.save(claim_id, "documents", content, f.filename)
        claim.documents.append(saved)

    claim.audit.append(AuditEntry(
        actor="system",
        event="claim_submitted",
        detail=f"{len(claim.image_files)} image(s), {len(claim.documents)} document(s)",
    ))
    CLAIMS[claim_id] = claim

    # Kick off pipeline in background
    background_tasks.add_task(_run_pipeline, claim_id)

    return {"claim_id": claim_id, "status": claim.status.value, "message": "Claim submitted; analysis started."}


async def _run_pipeline(claim_id: str):
    claim = CLAIMS.get(claim_id)
    if not claim or ORCHESTRATOR is None:
        return
    try:
        await ORCHESTRATOR.process_claim(claim, on_update=lambda c: CLAIMS.__setitem__(c.claim_id, c))
    except Exception as e:
        log.exception("Pipeline crashed for %s: %s", claim_id, e)
        claim.status = ClaimStatus.NEEDS_REVIEW
        claim.current_step = f"Pipeline error: {e}"
        claim.updated_at = datetime.now()
        claim.audit.append(AuditEntry(actor="system", event="pipeline_error", detail=str(e)))


# ---------------------------------------------------------------------------

@app.get("/api/claims")
async def list_claims():
    items: List[ClaimListItem] = []
    for c in sorted(CLAIMS.values(), key=lambda x: x.created_at, reverse=True):
        items.append(ClaimListItem(
            claim_id=c.claim_id,
            claimant_name=c.submission.claimant_name,
            claim_type=c.submission.claim_type.value,
            claim_amount=c.submission.claim_amount,
            status=c.status,
            current_step=c.current_step,
            progress_percentage=c.progress_percentage,
            updated_at=c.updated_at,
        ))
    return items


@app.get("/api/claims/{claim_id}")
async def get_claim(claim_id: str):
    claim = CLAIMS.get(claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")
    return claim


@app.get("/api/claims/{claim_id}/image/{filename}")
async def get_image(claim_id: str, filename: str):
    path = file_storage.get_path(claim_id, "images", filename)
    if not path.exists():
        # fall back to documents folder
        path = file_storage.get_path(claim_id, "documents", filename)
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


@app.post("/api/claims/{claim_id}/review")
async def human_review(claim_id: str, decision: HumanReviewDecision):
    """Human-in-the-loop override for NEEDS_REVIEW claims."""
    claim = CLAIMS.get(claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")

    claim.human_review = decision
    status_map = {
        HumanReviewAction.APPROVE: ClaimStatus.APPROVED,
        HumanReviewAction.REJECT: ClaimStatus.REJECTED,
        HumanReviewAction.REQUEST_INFO: ClaimStatus.NEEDS_INFO,
        HumanReviewAction.ESCALATE: ClaimStatus.ESCALATED,
    }
    claim.status = status_map[decision.action]
    claim.current_step = f"Human review: {decision.action.value.upper()}"
    claim.progress_percentage = 100
    claim.updated_at = datetime.now()
    claim.audit.append(AuditEntry(
        actor=decision.reviewer_id or "demo-analyst",
        event=f"human_review:{decision.action.value}",
        detail=decision.reviewer_note,
    ))

    return {"claim_id": claim_id, "status": claim.status.value, "message": "Review decision recorded."}


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port,
                reload=settings.debug_mode)
