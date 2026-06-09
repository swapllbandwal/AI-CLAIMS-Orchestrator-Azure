"""Decision Maker — aggregates all upstream agent results into a final verdict.

Maps Claude's APPROVED/REJECTED/NEEDS_INFO/NEEDS_REVIEW string to ClaimStatus.

A deterministic post-LLM override enforces the business rule that fraud risk
alone may only reject a claim when the score is >= FRAUD_REJECTION_THRESHOLD.
This guards against the LLM being over-cautious on moderate fraud signals.
"""

from typing import Tuple

from models.schemas import AgentResult, ClaimStatus
from services.claude_client import ClaudeClient

from ._common import parse_agent_response


# Business rule: fraud-only rejection is only allowed at or above this score.
# Below the threshold, a Claude-issued REJECTED is downgraded to NEEDS_REVIEW
# unless the policy check also failed (e.g. expired / suspended policy).
FRAUD_REJECTION_THRESHOLD = 0.70


SYSTEM = f"""You are the final decision maker for auto-insurance claims. Based
on the upstream agent analyses (validation, car damage CV, document OCR, fraud,
policy), produce a final decision and a clear adjuster-style summary.

Decision guidelines — apply STRICTLY:

- APPROVED: All checks passed with reasonable confidence; fraud risk
  < {FRAUD_REJECTION_THRESHOLD:.2f}; policy valid; CV evidence consistent
  with claim description.

- REJECTED: Permitted ONLY when at least one of the following hard
  conditions is true:
    (a) Policy check FAILED (expired / suspended / not-covered / wrong policy)
    (b) Fraud risk score is >= {FRAUD_REJECTION_THRESHOLD:.2f}
    (c) Photos are clearly inconsistent with the described incident (e.g.
        rear-end claim but photo shows front damage only).
  IMPORTANT: A fraud risk strictly below {FRAUD_REJECTION_THRESHOLD:.2f}
  is NOT sufficient on its own to reject the claim — choose NEEDS_REVIEW
  instead and let a human adjuster decide.

- NEEDS_INFO: Missing critical documents (e.g. high-value claim with no
  repair invoice or police report).

- NEEDS_REVIEW: Default for borderline cases — moderate fraud signal
  (between 0.40 and {FRAUD_REJECTION_THRESHOLD - 0.01:.2f}), high-value
  claim, or any agent strongly disagreeing with others.

Provide a single-sentence customer-facing message and a 2-3 sentence adjuster brief."""


class DecisionMakerAgent:
    name = "Decision Maker"

    def __init__(self, llm: ClaudeClient):
        self.llm = llm

    async def decide(
        self,
        claim_data: dict,
        validation: AgentResult,
        damage: AgentResult,
        document: AgentResult,
        fraud: AgentResult,
        policy: AgentResult,
    ) -> Tuple[AgentResult, ClaimStatus]:
        severity = (damage.metadata or {}).get("severity", "UNKNOWN")
        brand = (damage.metadata or {}).get("brand")
        n_damage_regions = len((damage.metadata or {}).get("damage_regions", []))

        user = f"""Make the final decision for this claim:

Claim Snapshot:
- Policy: {claim_data.get('policy_number')}
- Type: {claim_data.get('claim_type')}
- Amount: ${claim_data.get('claim_amount')}
- Vehicle: {claim_data.get('vehicle_make_model') or 'not provided'} (CV-detected brand: {brand or 'n/a'})

Upstream agent results:

1. Validation → {validation.status.upper()} (conf {validation.confidence:.2f})
   {validation.findings[:400]}

2. Car Damage CV → {damage.status.upper()} (conf {damage.confidence:.2f})
   Severity={severity}, {n_damage_regions} damage region(s) detected.
   {damage.findings[:400]}

3. Document OCR → {document.status.upper()} (conf {document.confidence:.2f})
   {document.findings[:400]}

4. Fraud Risk → {fraud.status.upper()} (risk {fraud.confidence:.2f})
   {fraud.findings[:400]}

5. Policy Check → {policy.status.upper()} (conf {policy.confidence:.2f})
   {policy.findings[:400]}

Reminder: Fraud risk is {fraud.confidence:.2f}. Reject on fraud alone is only
permitted if this is >= {FRAUD_REJECTION_THRESHOLD:.2f}.

Respond strictly in this format:
STATUS: [APPROVED/REJECTED/NEEDS_INFO/NEEDS_REVIEW]
CONFIDENCE: [0.0-1.0]
FINDINGS: Adjuster brief (2-3 sentences) + Customer message (1 sentence prefixed with "Customer: ")
RECOMMENDATIONS: [Comma-separated list of next steps]"""

        response = await self.llm.complete(SYSTEM, user, max_tokens=900, caller=self.name)
        parsed = parse_agent_response(response)
        result = AgentResult(agent_name=self.name, **parsed)

        status_map = {
            "approved": ClaimStatus.APPROVED,
            "rejected": ClaimStatus.REJECTED,
            "needs_info": ClaimStatus.NEEDS_INFO,
            "needs_review": ClaimStatus.NEEDS_REVIEW,
            # Defensive fallbacks if model substitutes synonyms
            "passed": ClaimStatus.APPROVED,
            "failed": ClaimStatus.REJECTED,
            "warning": ClaimStatus.NEEDS_REVIEW,
        }
        claim_status = status_map.get(parsed["status"], ClaimStatus.NEEDS_REVIEW)

        # --- Deterministic override -----------------------------------------
        # If the LLM said REJECTED but fraud is below threshold AND policy did
        # not actually fail, downgrade to NEEDS_REVIEW. This enforces the
        # business rule even when the LLM is over-cautious.
        override_applied = False
        if (
            claim_status == ClaimStatus.REJECTED
            and fraud.confidence < FRAUD_REJECTION_THRESHOLD
            and policy.status.lower() != "failed"
        ):
            claim_status = ClaimStatus.NEEDS_REVIEW
            override_note = (
                f"\n\n[Auto-override] Fraud risk {fraud.confidence:.2f} is below "
                f"the {FRAUD_REJECTION_THRESHOLD:.2f} rejection threshold and the "
                f"policy check did not fail. Verdict downgraded from REJECTED to "
                f"NEEDS_REVIEW for human adjuster decision."
            )
            result.findings = (result.findings or "") + override_note
            override_applied = True

        result.metadata = {
            "validation_score": validation.confidence,
            "damage_severity": severity,
            "document_quality": document.confidence,
            "fraud_risk": fraud.confidence,
            "policy_compliance": policy.confidence,
            "fraud_threshold": FRAUD_REJECTION_THRESHOLD,
            "override_applied": override_applied,
        }
        return result, claim_status
