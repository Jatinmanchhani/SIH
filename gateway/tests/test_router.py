from router import load_registry, route


def test_image_attachment_routes_to_vision():
    registry = load_registry()
    decision = route("what does this show?", registry, has_image=True)
    assert decision.task_type == "vision"
    assert decision.confidence == "attachment"


def test_code_keywords_route_to_code():
    registry = load_registry()
    decision = route("write a python script to sum a list", registry)
    assert decision.task_type == "code"


def test_document_keywords_route_to_document():
    registry = load_registry()
    decision = route("draft an approval note for this exception", registry)
    assert decision.task_type == "document"


def test_ambiguous_text_without_fallback_defaults_to_general():
    registry = load_registry()
    decision = route("hello there", registry)
    assert decision.task_type == "general"
    assert decision.confidence == "default"


def test_ambiguous_text_uses_llm_fallback_when_provided():
    registry = load_registry()
    decision = route("hello there", registry, llm_classify_fn=lambda prompt: "code")
    assert decision.task_type == "code"
    assert decision.confidence == "llm_fallback"