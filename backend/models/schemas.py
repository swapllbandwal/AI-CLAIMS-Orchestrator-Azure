"""Pydantic data models for the Azure claims MVP.

Trimmed from the parent project's schemas.py — drops chat / guided-submission /
opus-workflow types since this MVP does not need them. Keeps the core agent
result protocol so the parent's regex-based prompt parsing ports verbatim.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClaimStatus(str, Enum):
    SUBMITTED = "submitted"
    VALIDATING = "validating"
    DAMAGE_ANALYSIS = "damage_analysis"
    DOCUMENT_ANALYSIS = "document_analysis"
    FRAUD_CHECK = "fraud_check"
    POLICY_CHECK = "policy_check"
    DECISION_PENDING = "decision_pending"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFO = "needs_info"
    ESCALATED = "escalated"


class ClaimType(str, Enum):
    AUTO_COLLISION = "auto_collision"
    AUTO_THEFT = "auto_theft"
    AUTO_VANDALISM = "auto_vandalism"
    AUTO_WEATHER = "auto_weather"


class ClaimSubmission(BaseModel):
    policy_number: str = Field(..., description="Insurance policy number")
    claim_type: ClaimType = Field(ClaimType.AUTO_COLLISION, description="Type of auto claim")
    claim_amount: float = Field(..., gt=0, description="Claimed amount in USD")
    incident_date: str = Field(..., description="Date of incident (YYYY-MM-DD)")
    description: str = Field(..., min_length=20, description="Detailed description of the claim")
    claimant_name: str = Field(..., description="Name of the claimant")
    claimant_email: str = Field(..., description="Email of the claimant")
    vehicle_make_model: Optional[str] = Field(None, description="Vehicle make and model")


class AgentResult(BaseModel):
    agent_name: str
    status: str  # "passed" | "failed" | "warning" | "approved" | "rejected" | "needs_info"
    confidence: float = Field(ge=0.0, le=1.0)
    findings: str
    recommendations: Optional[List[str]] = []
    metadata: Optional[Dict[str, Any]] = {}


class ClaimAnalysis(BaseModel):
    claim_id: str
    validation_result: Optional[AgentResult] = None
    damage_result: Optional[AgentResult] = None
    document_result: Optional[AgentResult] = None
    fraud_result: Optional[AgentResult] = None
    policy_result: Optional[AgentResult] = None
    final_decision: Optional[AgentResult] = None
    overall_status: ClaimStatus
    processing_time: Optional[float] = None


class HumanReviewAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_INFO = "request_info"
    ESCALATE = "escalate"


class HumanReviewDecision(BaseModel):
    action: HumanReviewAction
    reviewer_note: str = Field(..., min_length=3)
    reviewer_id: Optional[str] = "demo-analyst"


class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    actor: str  # "system" | reviewer_id
    event: str  # e.g. "claim_submitted", "stage:fraud_check", "human_review:approve"
    detail: Optional[str] = None


class Claim(BaseModel):
    claim_id: str
    submission: ClaimSubmission
    status: ClaimStatus = ClaimStatus.SUBMITTED
    current_step: str = "Submitted"
    progress_percentage: int = 0
    documents: List[str] = Field(default_factory=list)  # original filenames
    image_files: List[str] = Field(default_factory=list)  # car-photo filenames
    analysis: Optional[ClaimAnalysis] = None
    human_review: Optional[HumanReviewDecision] = None
    audit: List[AuditEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ClaimListItem(BaseModel):
    """Compact representation for the dashboard list view."""
    claim_id: str
    claimant_name: str
    claim_type: str
    claim_amount: float
    status: ClaimStatus
    current_step: str
    progress_percentage: int
    updated_at: datetime
