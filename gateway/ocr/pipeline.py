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

PDFs: rendered page-by-page to PNG first (via pymupdf), then each page goes
through the exact same OCR/VLM path as any scanned image — nothing downstream
needs to know or care that the original file was a PDF.
"""

from __future__ import annotations
import base64
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
import pymupdf
import pytesseract
from PIL import Image


@dataclass
class ExtractionResult:
    text: str
    method: str          # "ocr" | "vlm" | "text" | "ocr_unavailable" | "ocr_error"
    mean_confidence: float | None = None  # 0-100, OCR only


def _locate_tesseract() -> str | None:
    """A usable `tesseract` binary path, or None. Checks PATH first, then the
    standard install locations — so a fresh `winget install UB-Mannheim.TesseractOCR`
    works without restarting the shell, and an air-gapped box with a fixed layout
    just needs one more entry here."""
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


_TESSERACT_BIN = _locate_tesseract()
if _TESSERACT_BIN:
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_BIN


def extract_with_ocr(image_path: Path) -> ExtractionResult:
    """OCR one image. Never raises: a missing or broken Tesseract comes back as a
    result with method 'ocr_unavailable' / 'ocr_error' and an explanatory text, so
    the agent loop keeps going instead of the whole request 500ing."""
    if _TESSERACT_BIN is None:
        return ExtractionResult(
            text="[OCR unavailable: the Tesseract binary is not installed on this host. "
                 "Install it (winget install UB-Mannheim.TesseractOCR) to read scanned "
                 "images and image-only PDFs. Text-native PDFs are unaffected.]",
            method="ocr_unavailable",
            mean_confidence=None,
        )
    try:
        img = Image.open(image_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as e:  # TesseractNotFoundError, TesseractError, PIL decode errors
        return ExtractionResult(
            text=f"[OCR failed: {type(e).__name__}: {e}]",
            method="ocr_error",
            mean_confidence=None,
        )
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


PDF_MAX_PAGES = 8
# A PDF page is treated as "text-native" (skip OCR entirely) once its embedded
# text layer clears this many characters — enough to tell a real digital document
# from the stray watermark/footer text a scanned page sometimes carries.
PDF_TEXT_LAYER_MIN_CHARS = 200


def _pdf_text_layer(pdf_path: Path, max_pages: int = PDF_MAX_PAGES) -> list[str]:
    """Per-page embedded text from a PDF, via pymupdf. Empty strings for pages that
    have no text layer (i.e. scanned images) — those need the OCR/VLM path instead."""
    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pages.append(page.get_text().strip())
    doc.close()
    return pages


def _pdf_to_images(pdf_path: Path, max_pages: int = 5) -> list[Path]:
    """Renders each page of a PDF to a real PNG file on disk, so the rest of this
    pipeline can treat it exactly like any scanned image. max_pages caps very long
    PDFs so one upload can't stall the agent loop for minutes."""
    doc = pymupdf.open(pdf_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="pdf_pages_"))
    image_paths = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pix = page.get_pixmap(dpi=200)
        out_path = tmp_dir / f"page_{i + 1}.png"
        pix.save(str(out_path))
        image_paths.append(out_path)
    doc.close()
    return image_paths


# Confidence below this triggers escalation to the VLM stage.
OCR_CONFIDENCE_THRESHOLD = 60.0


def extract(image_path: Path, vlm_client=None, vision_model_name: str = "llava:7b") -> ExtractionResult:
    if image_path.suffix.lower() == ".pdf":
        # Fast path: a digital/text-native PDF (exported slides, a Word→PDF SOP) already
        # carries its text — read it straight out, no rendering and no Tesseract needed.
        text_pages = _pdf_text_layer(image_path)
        if sum(len(t) for t in text_pages) >= PDF_TEXT_LAYER_MIN_CHARS:
            combined = "\n\n---\n\n".join(
                f"[Page {i + 1}]\n{t}" for i, t in enumerate(text_pages) if t
            )
            return ExtractionResult(text=combined, method="pdf+text", mean_confidence=None)

        # Otherwise it's a scanned/image PDF — render each page and run OCR/VLM.
        pages = _pdf_to_images(image_path)
        if not pages:
            return ExtractionResult(text="(PDF had no pages)", method="pdf", mean_confidence=None)
        page_results = [extract(p, vlm_client=vlm_client, vision_model_name=vision_model_name) for p in pages]
        combined_text = "\n\n---\n\n".join(
            f"[Page {i + 1}]\n{r.text}" for i, r in enumerate(page_results)
        )
        confidences = [r.mean_confidence for r in page_results if r.mean_confidence is not None]
        avg_conf = sum(confidences) / len(confidences) if confidences else None
        return ExtractionResult(text=combined_text, method=f"pdf+{page_results[0].method}", mean_confidence=avg_conf)

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
