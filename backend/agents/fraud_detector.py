"""Fraud Detector — Claude + RAG over past_claims.json + fraud_patterns.json.

Replaces the parent project's Qdrant-backed similarity search with the local
in-memory RAG service. Output protocol is identical to the parent so the
frontend's risk-score visualisation works unchanged.
"""

from typing import Any, Dict

from models.schemas import AgentResult
from services.claude_client import ClaudeClient
from services.rag_service import RAGService

from ._common import parse_agent_response


SYSTEM = """You are a fraud-detection specialist for auto-insurance claims.
Analyze for:
1. Suspicious patterns or inconsistencies in the claim narrative
2. Unusually high claim amounts relative to described damage
3. Vague or generic descriptions
4. Red flags in timing (e.g. recent policy purchase, late FIR)
5. Similarities with known fraudulent claims (provided)
6. Patterns from the known-fraud playbook (provided)

Provide a risk score (0-1, where 1 is highest fraud risk)."""


class FraudDetectorAgent:
    name = "Fraud Detector"

    def __init__(self, llm: ClaudeClient, rag: RAGService):
        self.llm = llm
        self.rag = rag

    async def analyze(self, claim_data: Dict[str, Any], damage_summary: str = "") -> AgentResult:
        # RAG: top-k similar past claims
        query = (
            f"{claim_data.get('claim_type','')} {claim_data.get('description','')} "
            f"amount {claim_data.get('claim_amount','')}"
        )
        similar = self.rag.similar_past_claims(query, k=4)

        if similar:
            similar_text = "\n".join(
                f"- [{c.get('claim_id')}] amount=${c.get('amount')} status={c.get('status')}: "
                f"{c.get('description','')[:140]}"
                for c in similar
            )
        else:
            similar_text = "No similar past claims found."

        pattern_text = "\n".join(
            f"- ({p['weight']}) {p['pattern']}: {p['description']}"
            for p in self.rag.fraud_patterns
        ) or "(no patterns loaded)"

        user = f"""Assess fraud risk for this claim:

Policy Number: {claim_data.get('policy_number')}
Claim Type: {claim_data.get('claim_type')}
Claim Amount: ${claim_data.get('claim_amount')}
Incident Date: {claim_data.get('incident_date')}
Description: {claim_data.get('description')}
Vehicle: {claim_data.get('vehicle_make_model') or 'not provided'}

Damage assessment summary from CV/Claude:
{damage_summary or '(none available yet)'}

Top Similar Past Claims (from RAG):
{similar_text}

Known Fraud Patterns to weigh against:
{pattern_text}

Respond strictly in this format:
STATUS: [PASSED/FAILED/WARNING]
CONFIDENCE: [0.0-1.0]  (use as fraud risk score — 1 = highest risk)
FINDINGS: [Detailed fraud-risk analysis, citing similar claims and matched patterns]
RECOMMENDATIONS: [Comma-separated list of investigative or processing actions]"""

        response = await self.llm.complete(SYSTEM, user, max_tokens=900, caller=self.name)
        parsed = parse_agent_response(response)
        result = AgentResult(agent_name=self.name, **parsed)
        result.metadata = {
            "fraud_risk": parsed["confidence"],
            "similar_claims": [
                {
                    "claim_id": c.get("claim_id"),
                    "amount": c.get("amount"),
                    "status": c.get("status"),
                    "description": c.get("description"),
                    "similarity_rank": c.get("_rank"),
                }
                for c in similar
            ],
        }
        return result
