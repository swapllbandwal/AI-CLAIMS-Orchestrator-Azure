"""Shared response-parsing helper for all Claude-based agents.

Every Claude agent in this MVP asks the model to respond in the same
STATUS / CONFIDENCE / FINDINGS / RECOMMENDATIONS block format. Centralising
the regex parse avoids the copy-paste duplication that the parent project has
across every agent.
"""

import re
from typing import Dict, Optional


def parse_agent_response(response: str) -> Dict[str, object]:
    """Parse a STATUS / CONFIDENCE / FINDINGS / RECOMMENDATIONS block."""
    status = re.search(r"STATUS:\s*([\w_]+)", response, re.IGNORECASE)
    confidence = re.search(r"CONFIDENCE:\s*([\d.]+)", response, re.IGNORECASE)
    findings = re.search(
        r"FINDINGS:\s*(.+?)(?=RECOMMENDATIONS:|$)", response, re.IGNORECASE | re.DOTALL
    )
    recommendations = re.search(
        r"RECOMMENDATIONS:\s*(.+)", response, re.IGNORECASE | re.DOTALL
    )

    try:
        conf_val = float(confidence.group(1)) if confidence else 0.5
        conf_val = max(0.0, min(1.0, conf_val))
    except (ValueError, AttributeError):
        conf_val = 0.5

    return {
        "status": status.group(1).lower() if status else "warning",
        "confidence": conf_val,
        "findings": findings.group(1).strip() if findings else response.strip(),
        "recommendations": (
            [r.strip() for r in recommendations.group(1).split(",") if r.strip()]
            if recommendations else []
        ),
    }
