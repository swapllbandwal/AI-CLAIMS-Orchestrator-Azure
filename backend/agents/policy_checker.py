"""Policy Checker — direct RAG lookup by policy_number + Claude reasoning."""

from typing import Any, Dict

from models.schemas import AgentResult
from services.claude_client import ClaudeClient
from services.rag_service import RAGService

from ._common import parse_agent_response


SYSTEM = """You are a policy-verification expert. Analyze the claim against
the policy record:
1. Policy must be active and not expired/suspended on the incident date
2. Incident type must be covered by the policy coverage_type
3. Claim amount must not exceed max_coverage; deductible must be applied
4. Incident date must fall within the policy effective→expiry window
5. Flag any prior-claims notes that affect this decision

Provide a confidence score (0-1) for policy compliance."""


class PolicyCheckerAgent:
    name = "Policy Checker"

    def __init__(self, llm: ClaudeClient, rag: RAGService):
        self.llm = llm
        self.rag = rag

    async def verify(self, claim_data: Dict[str, Any]) -> AgentResult:
        policy_number = claim_data.get("policy_number", "")
        policy = self.rag.find_policy(policy_number)

        if not policy:
            return AgentResult(
                agent_name=self.name,
                status="failed",
                confidence=1.0,
                findings=(
                    f"Policy number '{policy_number}' was not found in the "
                    "policy database. Claim cannot be verified against a valid policy."
                ),
                recommendations=[
                    "Verify the policy number with the claimant",
                    "Reject the claim if the policy genuinely does not exist",
                ],
                metadata={"policy": None},
            )

        user = f"""Verify policy coverage for this claim:

Claim Details:
- Policy Number: {claim_data.get('policy_number')}
- Claim Type: {claim_data.get('claim_type')}
- Claim Amount: ${claim_data.get('claim_amount')}
- Incident Date: {claim_data.get('incident_date')}
- Vehicle: {claim_data.get('vehicle_make_model') or 'not provided'}

Matched Policy Record:
- Holder: {policy.get('holder_name')}
- Coverage Type: {policy.get('coverage_type')}
- Status: {policy.get('status')}
- Max Coverage: ${policy.get('max_coverage')}
- Deductible: ${policy.get('deductible')}
- Effective: {policy.get('effective_date')} → Expiry: {policy.get('expiry_date')}
- Vehicle on record: {policy.get('vehicle')}
- Notes: {policy.get('notes')}

Respond strictly in this format:
STATUS: [PASSED/FAILED/WARNING]
CONFIDENCE: [0.0-1.0]
FINDINGS: [Detailed policy compliance analysis including any deductible to apply]
RECOMMENDATIONS: [Comma-separated list of actions]"""

        response = await self.llm.complete(SYSTEM, user, max_tokens=700, caller=self.name)
        parsed = parse_agent_response(response)
        result = AgentResult(agent_name=self.name, **parsed)
        result.metadata = {"policy": policy}
        return result
