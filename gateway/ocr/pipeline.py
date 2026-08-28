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
import base64
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


def _image_to_data_uri(image_path: Path) -> str:
    """Ollama (and most OpenAI-compatible servers) want the image embedded directly
    in the request as base64 — a plain file:// path doesn't work, since the server
    has no access to your filesystem."""
    suffix = image_path.suffix.lstrip(".").lower()
    mime = "jpeg" if suffix in ("jpg", "jpeg") else (suffix or "png")
    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:image/{mime};base64,{b64}"


def extract_with_vlm(image_path: Path, vlm_client, model_name: str = "llava:7b") -> ExtractionResult:
    """
    vlm_client: an OpenAI-compatible client (from the `openai` package) pointed at
    your vision model's endpoint — see model_registry.yaml's 'vision' entry for the
    base_url and model_name to use when constructing it.
    """
    data_uri = _image_to_data_uri(image_path)
    response = vlm_client.chat.completions.create(
        model=model_name,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Transcribe all readable text, and separately describe "
                                          "any diagrams, damage, or handwriting shown."},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }],
    )
    text = response.choices[0].message.content or ""
    return ExtractionResult(text=text, method="vlm", mean_confidence=None)


# Confidence below this triggers escalation to the VLM stage.
OCR_CONFIDENCE_THRESHOLD = 60.0


def extract(image_path: Path, vlm_client=None, vision_model_name: str = "llava:7b") -> ExtractionResult:
    ocr_result = extract_with_ocr(image_path)
    if ocr_result.mean_confidence is not None and ocr_result.mean_confidence >= OCR_CONFIDENCE_THRESHOLD:
        return ocr_result
    if vlm_client is not None:
        return extract_with_vlm(image_path, vlm_client, model_name=vision_model_name)
    # No VLM wired up (e.g. DEMO_MODE, or no vision model pulled yet) — return OCR's best effort.
    return ocr_result


if __name__ == "__main__":
    sample = Path(__file__).parent.parent.parent / "sample_data" / "sample_inspection_scan.png"
    result = extract(sample)
    print(f"Method: {result.method}   Mean confidence: {result.mean_confidence:.1f}\n")
    print("Extracted text:\n")
    print(result.text)
