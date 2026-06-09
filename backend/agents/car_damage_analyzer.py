"""Car Damage Analyzer — the headline CV agent for the lecture demo.

Pipeline per image:
  1. Azure CV Image Analysis 4.0  → Objects, Tags, Caption, DenseCaptions
  2. Azure CV v3.2 Brands         → detected vehicle brand (separate REST call)
  3. Heuristic filter             → damage-relevant regions (for bbox overlay)
  4. Claude reasoning             → severity (MINOR/MODERATE/SEVERE) + summary

Returns an AgentResult whose metadata carries per-image CV evidence for the
frontend to render bounding boxes and the raw-CV showcase ribbon.
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


SYSTEM = """You are an automotive damage assessor for insurance claims.
You are given structured Azure Computer Vision output for one or more car-damage
photos (captions, tags, detected objects, brand if any).
Estimate the damage severity (MINOR / MODERATE / SEVERE), identify the
affected vehicle parts, and note any inconsistencies with the claim
description. Provide a confidence score (0-1) for your assessment."""


class CarDamageAnalyzerAgent:
    name = "Car Damage Analyzer"

    def __init__(self, llm: ClaudeClient, vision: AzureVisionService):
        self.llm = llm
        self.vision = vision

    async def analyze(
        self,
        claim_data: Dict[str, Any],
        image_paths: List[Path],
    ) -> AgentResult:
        if not image_paths:
            return AgentResult(
                agent_name=self.name,
                status="warning",
                confidence=0.0,
                findings="No car-damage photos were uploaded with this claim.",
                recommendations=["Request damage photos from the claimant before proceeding."],
                metadata={"per_image": [], "damage_regions": [], "brand": None,
                          "severity": "UNKNOWN"},
            )

        per_image: List[Dict[str, Any]] = []
        all_regions: List[Dict[str, Any]] = []
        detected_brand = None

        # Run CV calls per image, sequentially — for the demo, sequential is
        # easier to narrate and avoids hammering the Azure CV throttle.
        for path in image_paths:
            try:
                image_bytes = path.read_bytes()
            except Exception as e:
                log.warning("Failed to read %s: %s", path, e)
                continue

            analysis = await asyncio.to_thread(self.vision.analyze_damage, image_bytes)
            brand_result = await asyncio.to_thread(self.vision.detect_brands, image_bytes)
            regions = AzureVisionService.damage_regions(analysis)
            brand = AzureVisionService.primary_brand(brand_result)

            if brand and not detected_brand:
                detected_brand = brand

            per_image.append({
                "filename": path.name,
                "caption": analysis.get("caption"),
                "tags": analysis.get("tags", [])[:10],
                "objects": analysis.get("objects", []),
                "dense_captions": analysis.get("dense_captions", []),
                "damage_regions": regions,
                "brand": brand,
            })
            # Tag regions back to their source image so the frontend can render
            for r in regions:
                r_copy = dict(r)
                r_copy["image"] = path.name
                all_regions.append(r_copy)

        # Build evidence digest for Claude
        evidence_lines = []
        for item in per_image:
            cap = (item.get("caption") or {}).get("text", "")
            tags = ", ".join(t["name"] for t in item.get("tags", [])[:8])
            captions = "; ".join(dc["text"] for dc in item.get("dense_captions", [])[:6])
            evidence_lines.append(
                f"- {item['filename']}: caption='{cap}'. tags=[{tags}]. "
                f"dense_captions=[{captions}]. brand={item.get('brand') or 'none'}"
            )
        evidence = "\n".join(evidence_lines) if evidence_lines else "(no CV evidence)"

        user = f"""Assess the car damage based on Azure CV evidence below.

Claim Description: {claim_data.get('description')}
Claim Amount: ${claim_data.get('claim_amount')}
Vehicle (claimant-supplied): {claim_data.get('vehicle_make_model') or 'unspecified'}
Detected brand from photos: {detected_brand or 'none detected'}

Computer-Vision Evidence (per image):
{evidence}

Determine:
- Affected vehicle parts (from the dense captions / objects)
- Damage severity: MINOR (cosmetic, <$2k typical) / MODERATE ($2-10k typical) / SEVERE (>$10k)
- Consistency between photos and the claimant's description

Respond strictly in this format:
STATUS: [PASSED/FAILED/WARNING]
CONFIDENCE: [0.0-1.0]
FINDINGS: severity=<MINOR|MODERATE|SEVERE>; <one-paragraph assessment>
RECOMMENDATIONS: [Comma-separated list of next steps]"""

        response = await self.llm.complete(SYSTEM, user, max_tokens=800, caller=self.name)
        parsed = parse_agent_response(response)

        # Extract severity tag from findings if Claude included it as we asked
        severity = "UNKNOWN"
        for s in ("SEVERE", "MODERATE", "MINOR"):
            if s in parsed["findings"].upper():
                severity = s
                break

        result = AgentResult(agent_name=self.name, **parsed)
        result.metadata = {
            "per_image": per_image,
            "damage_regions": all_regions,
            "brand": detected_brand,
            "severity": severity,
        }
        return result
