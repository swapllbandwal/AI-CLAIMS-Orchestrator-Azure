"""Azure Computer Vision wrapper.

One service class with three demo verbs — exactly what the MVP needs:

    analyze_damage(...)  → Image Analysis 4.0 (Objects, Tags, Caption, DenseCaptions)
    ocr_document(...)    → Image Analysis 4.0 Read API
    detect_brands(...)   → Computer Vision v3.2 Brands (separate REST call; the
                           Florence v4.0 model dropped the dedicated Brands feature
                           and rolls brand info into general tags/objects — for
                           the lecture demo we keep the explicit call)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

log = logging.getLogger("azurecv")


# Heuristic vocabulary for damage-keyword filtering on dense captions / tags.
DAMAGE_TERMS = {
    "dent", "dented", "scratch", "scratched", "scrape", "broken", "shattered",
    "cracked", "smashed", "damaged", "damage", "deformed", "bent", "crushed",
    "punctured", "torn", "rust", "rusted", "burnt", "burned",
}

VEHICLE_PARTS = {
    "bumper", "fender", "hood", "door", "windshield", "headlight", "taillight",
    "mirror", "wheel", "tire", "grille", "trunk", "tailgate", "panel", "roof",
}


class AzureVisionService:
    def __init__(self, endpoint: str, key: str):
        endpoint = endpoint.rstrip("/")
        self._endpoint = endpoint
        self._key = key
        self._v4 = ImageAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        self._v32_url = f"{endpoint}/vision/v3.2/analyze"

    # --- v4.0 Image Analysis -------------------------------------------------

    def analyze_damage(self, image_bytes: bytes) -> Dict[str, Any]:
        """Run Image Analysis 4.0 for objects/tags/caption/dense-captions."""
        log.info("→ Azure CV analyze_damage  (%d KB)", len(image_bytes) // 1024)
        t0 = time.time()
        result = self._v4.analyze(
            image_data=image_bytes,
            visual_features=[
                VisualFeatures.OBJECTS,
                VisualFeatures.TAGS,
                VisualFeatures.CAPTION,
                VisualFeatures.DENSE_CAPTIONS,
            ],
        )
        log.info("← Azure CV analyze_damage done in %.2fs", time.time() - t0)
        return self._serialize_v4(result)

    def ocr_document(self, image_bytes: bytes) -> Dict[str, Any]:
        """Run Azure CV Read API on a document/invoice image."""
        log.info("→ Azure CV ocr_document  (%d KB)", len(image_bytes) // 1024)
        t0 = time.time()
        result = self._v4.analyze(
            image_data=image_bytes,
            visual_features=[VisualFeatures.READ],
        )
        log.info("← Azure CV ocr_document done in %.2fs", time.time() - t0)
        return self._serialize_v4(result)

    # --- v3.2 Brands ---------------------------------------------------------

    def detect_brands(self, image_bytes: bytes) -> Dict[str, Any]:
        """v3.2 Brands feature (v4.0 doesn't expose it as a dedicated feature)."""
        log.info("→ Azure CV detect_brands (v3.2)  (%d KB)", len(image_bytes) // 1024)
        t0 = time.time()
        try:
            r = httpx.post(
                self._v32_url,
                params={"visualFeatures": "Brands"},
                headers={
                    "Ocp-Apim-Subscription-Key": self._key,
                    "Content-Type": "application/octet-stream",
                },
                content=image_bytes,
                timeout=30.0,
            )
            r.raise_for_status()
            log.info("← Azure CV detect_brands done in %.2fs", time.time() - t0)
            return r.json()
        except Exception as e:
            log.warning("← Azure CV detect_brands FAILED in %.2fs: %s", time.time() - t0, e)
            return {"brands": [], "error": str(e)}

    # --- Serialization / interpretation --------------------------------------

    @staticmethod
    def _serialize_v4(result) -> Dict[str, Any]:
        """Convert Azure SDK result object to a JSON-friendly dict."""
        out: Dict[str, Any] = {
            "caption": None,
            "dense_captions": [],
            "tags": [],
            "objects": [],
            "read_text": "",
            "read_lines": [],
        }

        if getattr(result, "caption", None):
            out["caption"] = {
                "text": result.caption.text,
                "confidence": result.caption.confidence,
            }

        if getattr(result, "dense_captions", None):
            for dc in result.dense_captions.list:
                out["dense_captions"].append({
                    "text": dc.text,
                    "confidence": dc.confidence,
                    "bbox": {
                        "x": dc.bounding_box.x, "y": dc.bounding_box.y,
                        "w": dc.bounding_box.width, "h": dc.bounding_box.height,
                    },
                })

        if getattr(result, "tags", None):
            for t in result.tags.list:
                out["tags"].append({"name": t.name, "confidence": t.confidence})

        if getattr(result, "objects", None):
            for obj in result.objects.list:
                tag = obj.tags[0] if obj.tags else None
                out["objects"].append({
                    "name": tag.name if tag else "object",
                    "confidence": tag.confidence if tag else 0.0,
                    "bbox": {
                        "x": obj.bounding_box.x, "y": obj.bounding_box.y,
                        "w": obj.bounding_box.width, "h": obj.bounding_box.height,
                    },
                })

        if getattr(result, "read", None):
            lines = []
            text_parts = []
            for block in result.read.blocks:
                for line in block.lines:
                    lines.append({
                        "text": line.text,
                        "bbox": [{"x": p.x, "y": p.y} for p in line.bounding_polygon],
                    })
                    text_parts.append(line.text)
            out["read_lines"] = lines
            out["read_text"] = "\n".join(text_parts)

        return out

    # --- Helpers for agents --------------------------------------------------

    @staticmethod
    def damage_regions(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Pick dense captions / objects that look damage-related.

        Returns a list of {label, confidence, bbox} suitable for the frontend
        bounding-box overlay.
        """
        regions: List[Dict[str, Any]] = []
        for dc in analysis.get("dense_captions", []):
            text_l = dc["text"].lower()
            if any(term in text_l for term in DAMAGE_TERMS) or \
               any(part in text_l for part in VEHICLE_PARTS):
                regions.append({
                    "label": dc["text"],
                    "confidence": dc["confidence"],
                    "bbox": dc["bbox"],
                })
        # Fall back to all objects on a car if no damage-specific captions
        if not regions:
            for obj in analysis.get("objects", []):
                regions.append({
                    "label": obj["name"],
                    "confidence": obj["confidence"],
                    "bbox": obj["bbox"],
                })
        return regions

    @staticmethod
    def primary_brand(brand_result: Dict[str, Any]) -> Optional[str]:
        brands = brand_result.get("brands", [])
        if not brands:
            return None
        # Highest confidence first
        brands = sorted(brands, key=lambda b: b.get("confidence", 0), reverse=True)
        return brands[0].get("name")
