"""Validator agent — Claude-based completeness/sanity check on the claim form."""

from typing import Any, Dict

from models.schemas import AgentResult
from services.claude_client import ClaudeClient

from ._common import parse_agent_response


SYSTEM = """You are a claims validation expert for auto insurance. Analyze the
claim submission for:
1. Completeness of required information
2. Data format correctness (dates, emails, amounts)
3. Reasonable claim amount for the described incident
4. Plausibility of the description for the claim type

Provide a confidence score (0-1) and specific findings."""


class ClaimValidatorAgent:
    name = "Claim Validator"

    def __init__(self, llm: ClaudeClient):
        self.llm = llm

    async def validate(self, claim_data: Dict[str, Any], n_images: int, n_docs: int) -> AgentResult:
        user = f"""Validate this auto-insurance claim:

Policy Number: {claim_data.get('policy_number')}
Claim Type: {claim_data.get('claim_type')}
Claim Amount: ${claim_data.get('claim_amount')}
Incident Date: {claim_data.get('incident_date')}
Description: {claim_data.get('description')}
Claimant: {claim_data.get('claimant_name')} <{claim_data.get('claimant_email')}>
Vehicle: {claim_data.get('vehicle_make_model') or 'not provided'}
Attachments: {n_images} car-damage photo(s), {n_docs} supporting document(s)

Respond strictly in this format:
STATUS: [PASSED/FAILED/WARNING]
CONFIDENCE: [0.0-1.0]
FINDINGS: [Your detailed validation analysis]
RECOMMENDATIONS: [Comma-separated list of recommendations]"""

        response = await self.llm.complete(SYSTEM, user, caller=self.name)
        parsed = parse_agent_response(response)
        return AgentResult(agent_name=self.name, **parsed)
