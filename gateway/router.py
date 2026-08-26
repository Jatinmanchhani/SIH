"""
router.py — decides which registered model should handle an incoming request.

Two-stage classification, cheapest check first:
  1. Structural signals (attachments present? file type?) — free, instant, no model call.
  2. Keyword/pattern signals on the text itself — free, instant.
  3. (Optional) LLM fallback classification — only invoked when 1 and 2 are ambiguous,
     using a small, fast model so it doesn't become the bottleneck.

This file is deliberately readable end-to-end so you can defend every branch to a judge.
"""

from __future__ import annotations
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REGISTRY_PATH = Path(__file__).parent / "model_registry.yaml"


@dataclass
class ModelEntry:
    key: str
    display_name: str
    endpoint: str
    model_name: str
    task_tags: list[str]
    supports_tools: bool
    priority: int = 1


@dataclass
class RoutingDecision:
    task_type: str
    model: ModelEntry
    reason: str
    confidence: str = field(default="rule")  # "rule" | "attachment" | "llm_fallback"


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, ModelEntry]:
    with open(path) as f:
        raw = yaml.safe_load(f)["models"]
    return {
        key: ModelEntry(key=key, **cfg)
        for key, cfg in raw.items()
    }


# --- Stage 2: keyword rules -------------------------------------------------
# Ordered; first match wins. Keep these tight — false positives are worse than
# falling through to the LLM fallback.
_CODE_PATTERNS = re.compile(
    r"\b(write|fix|debug|refactor)\b.*\b(script|function|code|program)\b"
    r"|```|def |class |import |SELECT .* FROM|traceback|stack trace",
    re.IGNORECASE,
)
_DOC_PATTERNS = re.compile(
    r"\b(approval note|summarize|summarise|draft|report|memo|BOM|bill of materials|"
    r"calculate|calculation|should-cost|cost model)\b",
    re.IGNORECASE,
)


def classify_by_rules(
    text: str,
    has_image: bool,
    has_pdf: bool,
) -> Optional[str]:
    """Returns a task_tag or None if the rules can't confidently decide."""
    if has_image:
        return "vision"
    if has_pdf:
        # A PDF could be a scanned doc (vision) or a text-native SOP (RAG/reasoning).
        # Cheap heuristic: let the caller pass has_pdf only for image-heavy/scanned PDFs;
        # text-native PDFs should be pre-ingested into RAG, not routed here at all.
        return "vision"
    if _CODE_PATTERNS.search(text):
        return "code"
    if _DOC_PATTERNS.search(text):
        return "document"
    return None


def classify_by_llm_fallback(text: str, orchestrator: ModelEntry) -> str:
    """
    Ambiguous case: ask the orchestrator model itself to classify, in one cheap call.
    This function only builds the prompt — wiring it to an actual HTTP call happens
    in llm_client.py so this module has no network dependency and stays unit-testable.
    """
    prompt = (
        "Classify the following user request into exactly one label: "
        "code, vision, document, or general. Reply with only the label.\n\n"
        f"Request: {text}"
    )
    return prompt  # llm_client.classify() sends this and parses the single-word reply


def route(
    text: str,
    registry: dict[str, ModelEntry],
    has_image: bool = False,
    has_pdf: bool = False,
    llm_classify_fn=None,
) -> RoutingDecision:
    """
    Main entry point. llm_classify_fn, if provided, is a callable(prompt: str) -> str
    used only when rules can't decide — keeps this function testable without a live model.
    """
    task_type = classify_by_rules(text, has_image, has_pdf)
    confidence = "attachment" if (has_image or has_pdf) else "rule"

    if task_type is None:
        if llm_classify_fn is not None:
            orchestrator = _pick(registry, "orchestrate")
            prompt = classify_by_llm_fallback(text, orchestrator)
            task_type = llm_classify_fn(prompt).strip().lower()
            confidence = "llm_fallback"
        else:
            task_type = "general"
            confidence = "default"

    model = _pick(registry, task_type)
    reason = f"matched tag '{task_type}' via {confidence}"
    return RoutingDecision(task_type=task_type, model=model, reason=reason, confidence=confidence)


def _pick(registry: dict[str, ModelEntry], tag: str) -> ModelEntry:
    candidates = [m for m in registry.values() if tag in m.task_tags]
    if not candidates:
        # Fall back to whichever model is tagged "general" or "reasoning"
        candidates = [m for m in registry.values() if "general" in m.task_tags or "reasoning" in m.task_tags]
    if not candidates:
        raise ValueError(f"No model in registry can handle task tag '{tag}'")
    return sorted(candidates, key=lambda m: m.priority)[0]


if __name__ == "__main__":
    # Quick self-test — run `python router.py` to see routing decisions with no server needed.
    registry = load_registry()
    tests = [
        ("Write a Python script to calculate flow rate for this pipe spec", False, False),
        ("Summarize the findings in this scanned inspection report", False, True),
        ("Draft an approval note for the vendor onboarding exception", False, False),
        ("What's the BOM cost delta between vendor A and vendor B this quarter?", False, False),
    ]
    for text, img, pdf in tests:
        decision = route(text, registry, has_image=img, has_pdf=pdf)
        print(f"[{decision.confidence:12}] '{text[:55]}...' -> {decision.model.display_name} ({decision.model.model_name})")
