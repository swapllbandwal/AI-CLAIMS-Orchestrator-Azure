"""6-step claims orchestration pipeline (no Opus, no Qdrant).

Sequential by design — easier to narrate for the student demo than a parallel
state machine. Each step updates the in-memory claim record so the frontend
polling endpoint can show live progress.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from agents.car_damage_analyzer import CarDamageAnalyzerAgent
from agents.decision_maker import DecisionMakerAgent
from agents.document_analyzer import DocumentAnalyzerAgent
from agents.fraud_detector import FraudDetectorAgent
from agents.policy_checker import PolicyCheckerAgent
from agents.validator import ClaimValidatorAgent

from config import get_settings
from models.schemas import (
    AgentResult,
    AuditEntry,
    Claim,
    ClaimAnalysis,
    ClaimStatus,
)
from services.azure_vision import AzureVisionService
from services.claude_client import ClaudeClient
from services.rag_service import RAGService
from utils.file_storage import file_storage

log = logging.getLogger(__name__)


class ClaimsOrchestrator:
    """Wires services + agents and runs the 6-step pipeline."""

    def __init__(self):
        s = get_settings()

        self.vision = AzureVisionService(s.azure_cv_endpoint, s.azure_cv_key)
        self.llm = ClaudeClient(s.foundry_endpoint, s.foundry_api_key, s.foundry_model)

        # RAG — initialise embeddings once at startup
        data_dir = Path(__file__).parent / "data"
        self.rag = RAGService(data_dir, s.embedding_model)
        self.rag.initialize()

        self.validator = ClaimValidatorAgent(self.llm)
        self.car_damage = CarDamageAnalyzerAgent(self.llm, self.vision)
        self.document_analyzer = DocumentAnalyzerAgent(self.llm, self.vision)
        self.fraud_detector = FraudDetectorAgent(self.llm, self.rag)
        self.policy_checker = PolicyCheckerAgent(self.llm, self.rag)
        self.decision_maker = DecisionMakerAgent(self.llm)

        log.info("Orchestrator initialised — Azure CV, Foundry/Claude, RAG ready.")

    # ------------------------------------------------------------------------

    async def process_claim(
        self,
        claim: Claim,
        on_update: Optional[Callable[[Claim], None]] = None,
    ) -> ClaimAnalysis:
        """Run the 6-step pipeline for a claim, calling on_update after each step."""
        start = time.time()
        cd = claim.submission.model_dump()

        image_paths = [
            file_storage.get_path(claim.claim_id, "images", fn)
            for fn in claim.image_files
        ]
        doc_paths = [
            file_storage.get_path(claim.claim_id, "documents", fn)
            for fn in claim.documents
        ]

        analysis = ClaimAnalysis(claim_id=claim.claim_id, overall_status=ClaimStatus.VALIDATING)

        # --- 1. Validator ----------------------------------------------------
        self._advance(claim, ClaimStatus.VALIDATING, "Validating claim", 10, on_update, "stage:validator")
        try:
            validation = await self.validator.validate(cd, len(image_paths), len(doc_paths))
        except Exception as e:
            log.exception("Validator failed")
            validation = _fallback_result("Claim Validator", e)
        analysis.validation_result = validation

        # --- 2. Car Damage Analyzer (Azure CV) -------------------------------
        self._advance(claim, ClaimStatus.DAMAGE_ANALYSIS, "Analyzing car damage photos (Azure Computer Vision)", 25, on_update, "stage:car_damage")
        try:
            damage = await self.car_damage.analyze(cd, image_paths)
        except Exception as e:
            log.exception("Car damage analyzer failed")
            damage = _fallback_result("Car Damage Analyzer", e)
        analysis.damage_result = damage

        # --- 3. Document Analyzer (Azure CV Read) ----------------------------
        self._advance(claim, ClaimStatus.DOCUMENT_ANALYSIS, "Running OCR on supporting documents (Azure CV Read)", 45, on_update, "stage:documents")
        try:
            doc_res = await self.document_analyzer.analyze(cd, doc_paths)
        except Exception as e:
            log.exception("Document analyzer failed")
            doc_res = _fallback_result("Document Analyzer", e)
        analysis.document_result = doc_res

        # --- 4. Fraud Detector (Claude + RAG) --------------------------------
        self._advance(claim, ClaimStatus.FRAUD_CHECK, "Checking fraud indicators (Claude + RAG)", 60, on_update, "stage:fraud")
        try:
            fraud = await self.fraud_detector.analyze(cd, damage_summary=damage.findings)
        except Exception as e:
            log.exception("Fraud detector failed")
            fraud = _fallback_result("Fraud Detector", e)
        analysis.fraud_result = fraud

        # --- 5. Policy Checker (Claude + RAG) --------------------------------
        self._advance(claim, ClaimStatus.POLICY_CHECK, "Verifying policy coverage", 75, on_update, "stage:policy")
        try:
            policy = await self.policy_checker.verify(cd)
        except Exception as e:
            log.exception("Policy checker failed")
            policy = _fallback_result("Policy Checker", e)
        analysis.policy_result = policy

        # --- 6. Decision Maker ----------------------------------------------
        self._advance(claim, ClaimStatus.DECISION_PENDING, "Making final decision", 90, on_update, "stage:decision")
        try:
            final, final_status = await self.decision_maker.decide(
                cd, validation, damage, doc_res, fraud, policy
            )
        except Exception as e:
            log.exception("Decision maker failed")
            final = _fallback_result("Decision Maker", e)
            final_status = ClaimStatus.NEEDS_REVIEW
        analysis.final_decision = final
        analysis.overall_status = final_status
        analysis.processing_time = time.time() - start

        # Persist final state on the claim record
        claim.status = final_status
        claim.current_step = f"Completed: {final_status.value.upper()}"
        claim.progress_percentage = 100
        claim.analysis = analysis
        claim.updated_at = datetime.now()
        claim.audit.append(AuditEntry(
            actor="system",
            event="pipeline_complete",
            detail=f"final={final_status.value}, conf={final.confidence:.2f}, "
                   f"fraud_risk={fraud.confidence:.2f}",
        ))
        if on_update:
            on_update(claim)

        log.info("[%s] pipeline done in %.2fs → %s", claim.claim_id, analysis.processing_time, final_status.value)
        return analysis

    # ------------------------------------------------------------------------

    @staticmethod
    def _advance(
        claim: Claim,
        status: ClaimStatus,
        message: str,
        pct: int,
        on_update: Optional[Callable[[Claim], None]],
        audit_event: str,
    ) -> None:
        claim.status = status
        claim.current_step = message
        claim.progress_percentage = pct
        claim.updated_at = datetime.now()
        claim.audit.append(AuditEntry(actor="system", event=audit_event, detail=message))
        if on_update:
            on_update(claim)


def _fallback_result(agent_name: str, error: Exception) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        status="warning",
        confidence=0.0,
        findings=f"Agent error: {error}",
        recommendations=["Retry this stage; check service connectivity and credentials."],
        metadata={"error": str(error)},
    )
