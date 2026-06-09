r"""Standalone demo: Azure Computer Vision (Image Analysis 4.0) on one image.

A minimal script — no FastAPI, no agents, no orchestrator — to show what
Azure Computer Vision returns for a single image. Useful for the first 2-3
slides of the lecture: "here is the raw API, here is the JSON we get back."

Usage (from project root, using the backend venv):

    .\backend\venv\Scripts\python test_azure_vision_ai.py
    .\backend\venv\Scripts\python test_azure_vision_ai.py path\to\my_image.jpg
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_IMAGE = (
    PROJECT_ROOT / "sample_documents" / "Sample Docs"
    / "Genhine case approval" / "Car Damage photo.png"
)


def main() -> int:
    # Load AZURE_CV_ENDPOINT / AZURE_CV_KEY from the project .env
    load_dotenv(PROJECT_ROOT / ".env")
    endpoint = os.getenv("AZURE_CV_ENDPOINT")
    key = os.getenv("AZURE_CV_KEY")

    if not endpoint or not key:
        print("ERROR: AZURE_CV_ENDPOINT and AZURE_CV_KEY must be set in .env",
              file=sys.stderr)
        return 1

    image_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IMAGE
    if not image_path.exists():
        print(f"ERROR: image not found: {image_path}", file=sys.stderr)
        return 1

    print(f"Endpoint : {endpoint}")
    print(f"Image    : {image_path}")
    print(f"Size     : {image_path.stat().st_size // 1024} KB")
    print("-" * 70)

    client = ImageAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))

    result = client.analyze(
        image_data=image_path.read_bytes(),
        visual_features=[
            VisualFeatures.CAPTION,
            VisualFeatures.DENSE_CAPTIONS,
            VisualFeatures.TAGS,
            VisualFeatures.OBJECTS,
            VisualFeatures.READ,
        ],
        gender_neutral_caption=True,
    )

    # ---- Caption -----------------------------------------------------------
    if result.caption:
        print("\n[CAPTION]")
        print(f'  "{result.caption.text}"  '
              f"(confidence {result.caption.confidence:.2f})")

    # ---- Tags --------------------------------------------------------------
    if result.tags:
        print("\n[TAGS]  (top 10)")
        for t in result.tags.list[:10]:
            print(f"  - {t.name:<25} {t.confidence:.2f}")

    # ---- Dense captions (per region) ---------------------------------------
    if result.dense_captions:
        print("\n[DENSE CAPTIONS]  (regions in the image)")
        for dc in result.dense_captions.list:
            bb = dc.bounding_box
            print(f"  - \"{dc.text}\"  ({dc.confidence:.2f})  "
                  f"bbox=({bb.x},{bb.y},{bb.width}x{bb.height})")

    # ---- Detected objects --------------------------------------------------
    if result.objects:
        print("\n[OBJECTS]  (detected with bounding boxes)")
        for obj in result.objects.list:
            tag = obj.tags[0] if obj.tags else None
            bb = obj.bounding_box
            name = tag.name if tag else "object"
            conf = tag.confidence if tag else 0.0
            print(f"  - {name:<20} {conf:.2f}  "
                  f"bbox=({bb.x},{bb.y},{bb.width}x{bb.height})")

    # ---- OCR / Read --------------------------------------------------------
    if result.read and result.read.blocks:
        print("\n[OCR / READ]  (text extracted from the image)")
        for block in result.read.blocks:
            for line in block.lines:
                print(f"  | {line.text}")

    print("\n" + "-" * 70)
    print(f"Model version: {result.model_version}")
    print(f"Image size   : {result.metadata.width} x {result.metadata.height}")
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
