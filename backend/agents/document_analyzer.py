"""Document Analyzer — Azure CV Read OCR on bills / receipts / police reports.

Ports the parent project's cross-verification logic (dates, amounts, names must
be consistent with the claim form) but swaps the OCR engine from Gemini Vision
to Azure Computer Vision Read API.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List

from models.schemas import AgentResult
from services.azure_vision import AzureVisionService
from services.claude_client import ClaudeClient

from ._common import parse_agent_response

log = logging.getLogger(__name__)


SYSTEM = """You are a document analysis expert for auto-insurance claims.
You will receive OCR text extracted from supporting documents (repair invoices,
police reports, receipts, witness statements).

Evaluate:
1. Completeness of supporting documentation for the claim type
2. Document authenticity indicators (header, totals, formatting)
3. Consistency between documents and the claim (dates, amounts, claimant name,
   policy number, vehicle)
4. Quality and clarity of extracted information

Provide a confidence score (0-1) for overall document validity."""


class DocumentAnalyzerAgent:
    name = "Document Analyzer"

    def __init__(self, llm: ClaudeClient, vision: AzureVisionService):
        self.llm = llm
        self.vision = vision

    async def analyze(
        self,
        claim_data: Dict[str, Any],
        document_paths: List[Path],
    ) -> AgentResult:
        if not document_paths:
            return AgentResult(
                agent_name=self.name,
                status="warning",
                confidence=0.3,
                findings="No supporting documents were uploaded with this claim.",
                recommendations=[
                    "Request repair invoice and (if applicable) police report from claimant.",
                ],
                metadata={"per_document": []},
            )

        per_document: List[Dict[str, Any]] = []
        combined_text_parts: List[str] = []

        for path in document_paths:
            try:
                image_bytes = path.read_bytes()
            except Exception as e:
                log.warning("Failed to read %s: %s", path, e)
                continue

            try:
                ocr = await asyncio.to_thread(self.vision.ocr_document, image_bytes)
            except Exception as e:
                log.warning("OCR failed for %s: %s", path, e)
                per_document.append({
                    "filename": path.name,
                    "ocr_text": "",
                    "lines": [],
                    "error": str(e),
                })
                continue

            per_document.append({
                "filename": path.name,
                "ocr_text": ocr.get("read_text", ""),
                "lines": ocr.get("read_lines", []),
            })
            if ocr.get("read_text"):
                combined_text_parts.append(f"--- {path.name} ---\n{ocr['read_text']}")

        combined = "\n\n".join(combined_text_parts) if combined_text_parts else "(no readable text extracted)"
        # Keep prompt size sane
        if len(combined) > 4000:
            combined = combined[:4000] + "\n[...truncated]"

        doc_summary_lines = [
            f"- {d['filename']}: {len(d.get('ocr_text','').split())} words extracted"
            + (f"  (OCR error: {d['error']})" if d.get("error") else "")
            for d in per_document
        ]
        doc_summary = "\n".join(doc_summary_lines)

        user = f"""Analyze documents for this claim:

Claim Information:
- Policy: {claim_data.get('policy_number')}
- Type: {claim_data.get('claim_type')}
- Amount: ${claim_data.get('claim_amount')}
- Incident Date: {claim_data.get('incident_date')}
- Claimant: {claim_data.get('claimant_name')}
- Vehicle: {claim_data.get('vehicle_make_model') or 'not provided'}
- Description: {claim_data.get('description')}

Submitted Documents ({len(per_document)} total):
{doc_summary}

OCR Text from All Documents:
{combined}

Verify:
- Dates in documents match the incident_date
- Amounts in invoices roughly match the claim_amount
- Claimant name appears in documents
- For auto_collision: a repair estimate is present
- For amounts > $10,000: a police report is desirable

Respond strictly in this format:
STATUS: [PASSED/FAILED/WARNING]
CONFIDENCE: [0.0-1.0]
FINDINGS: [Your detailed document-cross-check analysis]
RECOMMENDATIONS: [Comma-separated list of missing or follow-up documents]"""

        response = await self.llm.complete(SYSTEM, user, max_tokens=900, caller=self.name)
        parsed = parse_agent_response(response)

        result = AgentResult(agent_name=self.name, **parsed)
        result.metadata = {"per_document": per_document}
        return result
