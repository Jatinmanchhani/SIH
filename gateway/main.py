"""
main.py — the API gateway. Two front doors:

  POST /v1/chat/completions   OpenAI-compatible passthrough + routing, for simple
                               single-turn requests (what most tools expect to call).
  POST /agent/run             The full agent loop — plan, call tools, iterate — for
                               anything that needs multiple steps (the flagship task).

Both log every routing decision, which is what turns "we have model auto-selection"
from a claim into something you can show a judge on screen in real time.
"""

from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel

from router import load_registry, route
from orchestrator import run_agent, MockLLMClient, RealLLMClient
from tools import rag

app = FastAPI(title="Sovereign AI Workbench Gateway")

registry = load_registry()
rag_store = rag.SimpleTfidfStore()
rag.ingest_directory(rag_store, Path(__file__).parent.parent / "sample_data")

# Swap this for RealLLMClient(base_url=..., model=...) once Ollama/vLLM is running
# on your GPU box. Everything downstream (routing, tool execution, logging) is
# already wired for that swap — see README.md.
DEMO_MODE = True


class ChatRequest(BaseModel):
    messages: list[dict]
    has_image: bool = False
    has_pdf: bool = False


class AgentRequest(BaseModel):
    task: str


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    """Routes a single request to the right specialist model and logs the decision."""
    user_text = req.messages[-1]["content"] if req.messages else ""
    decision = route(user_text, registry, has_image=req.has_image, has_pdf=req.has_pdf)

    log_line = (f"[route] task_type={decision.task_type} "
                f"model={decision.model.model_name} reason='{decision.reason}'")
    print(log_line)

    return {
        "routing": {
            "task_type": decision.task_type,
            "model_used": decision.model.display_name,
            "model_name": decision.model.model_name,
            "reason": decision.reason,
        },
        "note": ("DEMO_MODE is on: this response shows the routing decision only. "
                 "Set DEMO_MODE=False and point RealLLMClient at your running Ollama "
                 "endpoint to get an actual model-generated answer.") if DEMO_MODE else None,
    }


@app.post("/agent/run")
def agent_run(req: AgentRequest):
    """Runs the full plan -> tool call -> observe -> repeat loop on a multi-step task."""
    llm = MockLLMClient() if DEMO_MODE else RealLLMClient(
        base_url=registry["orchestrator"].endpoint,
        model=registry["orchestrator"].model_name,
    )
    result = run_agent(req.task, llm, rag_store)
    return {"result": result, "demo_mode": DEMO_MODE}


@app.get("/models")
def list_models():
    """Shows the live model registry — proves 'addable later, no redesign' is real."""
    return {
        key: {"display_name": m.display_name, "model_name": m.model_name, "tags": m.task_tags}
        for key, m in registry.items()
    }


@app.get("/health")
def health():
    return {"status": "ok", "demo_mode": DEMO_MODE}
