"""
pipeline.py — two-stage document/image understanding.

Stage A (this file, working now): Tesseract OCR for clean printed text extraction.
    Fast, CPU-only, no model weights needed. Good for typed reports, forms, tables.

Stage B (stub below, needs your GPU box): a vision-language model (Qwen2-VL /
    InternVL2) for anything OCR alone can't handle — handwriting, P&ID diagrams,
    equipment photos, damaged/skewed scans. Same interface, so the orchestrator
    calls one function and doesn't need to know which stage actually answered.

Routing between them: try OCR first (cheap); if confidence is low or the source
looks like a diagram/photo rather than typed text, escalate to the VLM.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import pytesseract
from PIL import Image


@dataclass
class ExtractionResult:
    text: str
    method: str          # "ocr" | "vlm"
    mean_confidence: float | None = None  # 0-100, OCR only


def extract_with_ocr(image_path: Path) -> ExtractionResult:
    img = Image.open(image_path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = [w for w in data["text"] if w.strip()]
    confidences = [int(c) for c, w in zip(data["conf"], data["text"]) if w.strip() and int(c) >= 0]
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
    full_text = " ".join(words)
    return ExtractionResult(text=full_text, method="ocr", mean_confidence=mean_conf)


def extract_with_vlm(image_path: Path, vlm_client) -> ExtractionResult:
    """
    STUB — wire this to your vision model's OpenAI-compatible endpoint on deployment.
    vlm_client is expected to expose .describe(image_path, prompt) -> str, e.g.:

        response = vlm_client.chat.completions.create(
            model="qwen2-vl:7b",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe all text and describe any diagrams or damage shown."},
                    {"type": "image_url", "image_url": {"url": f"file://{image_path}"}},
                ],
            }],
        )
        text = response.choices[0].message.content
    """
    raise NotImplementedError(
        "Connect this to your vision model endpoint (see model_registry.yaml -> 'vision'). "
        "This stub exists so orchestrator.py has a real call site to wire up on deployment."
    )


# Confidence below this triggers escalation to the VLM stage.
OCR_CONFIDENCE_THRESHOLD = 60.0


def extract(image_path: Path, vlm_client=None) -> ExtractionResult:
    ocr_result = extract_with_ocr(image_path)
    if ocr_result.mean_confidence is not None and ocr_result.mean_confidence >= OCR_CONFIDENCE_THRESHOLD:
        return ocr_result
    if vlm_client is not None:
        return extract_with_vlm(image_path, vlm_client)
    # No VLM wired up yet (e.g. running in this sandbox) — return OCR's best effort anyway.
    return ocr_result


if __name__ == "__main__":
    sample = Path(__file__).parent.parent.parent / "sample_data" / "sample_inspection_scan.png"
    result = extract(sample)
    print(f"Method: {result.method}   Mean confidence: {result.mean_confidence:.1f}\n")
    print("Extracted text:\n")
    print(result.text)
