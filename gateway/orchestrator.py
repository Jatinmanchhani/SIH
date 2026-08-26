"""
orchestrator.py — the agent loop: plan, call a tool, observe the result, repeat.

This is the mechanism that answers two requirements from the PS at once:
  - "model auto-selection" — each tool below IS a specialist model or a local
    capability; the orchestrator calling `extract_from_image` is exactly the
    same mechanism as it calling `run_code`. There's no separate router module
    the orchestrator has to consult — delegation to a specialist model and
    calling a tool are literally the same code path.
  - "act like an agent, plan multi-step work, iterate" — the loop below doesn't
    stop after one tool call; it keeps going until the model decides it has
    enough to answer, capped at MAX_ITERATIONS so nothing can spin forever.

LLMClient is a Protocol so this file has zero dependency on which engine is
actually running the model. Point RealLLMClient at your Ollama/vLLM endpoint
on deployment; MockLLMClient below scripts a realistic tool-call sequence so
the loop's CONTROL FLOW is provably correct without needing live model weights
— which is exactly the constraint in this sandbox (no GPU, no downloaded models).
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Any

from tools import sandbox, file_tools, rag, docgen
from ocr import pipeline as ocr_pipeline

MAX_ITERATIONS = 8
SAMPLE_DATA_ROOT = (Path(__file__).parent.parent / "sample_data").resolve()


def _resolve_in_sample_data(name: str) -> Path:
    """
    Confines a model-supplied filename to sample_data/, the same way file_tools._resolve_safe
    confines everything under workspace/. Tool arguments (relative_path, reference_no) come
    straight from the LLM's tool call — once RealLLMClient is live, that means they can be
    influenced by anything the model has read (a prompt-injected scanned document, a poisoned
    SOP, etc.), so they're untrusted input and must never be joined onto a filesystem path
    without this check. Rejects any path that escapes sample_data/ (e.g. "../../etc/passwd")
    or that isn't a plain filename (e.g. absolute paths).
    """
    candidate = (SAMPLE_DATA_ROOT / name).resolve()
    if SAMPLE_DATA_ROOT != candidate and SAMPLE_DATA_ROOT not in candidate.parents:
        raise file_tools.PathEscapeError(
            f"'{name}' escapes sample_data/ — refused. Tool arguments are untrusted "
            "model output and must not be used to build filesystem paths directly."
        )
    return candidate


# --- Tool schema (OpenAI function-calling format) ---------------------------
TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "extract_from_image",
            "description": "Extract text and findings from a scanned document or photo.",
            "parameters": {
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search internal SOPs/manuals for grounding facts, with citations.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Run a Python snippet in the sandbox (no network access) and return stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_approval_note",
            "description": "Render structured findings into a Word approval note (draft, requires human sign-off).",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "reference_no": {"type": "string"},
                    "prepared_for": {"type": "string"},
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}, "source": {"type": "string"}},
                        },
                    },
                    "recommendation": {"type": "string"},
                },
                "required": ["title", "reference_no", "prepared_for", "findings", "recommendation"],
            },
        },
    },
]


# --- Tool dispatch ------------------------------------------------------------
def execute_tool(name: str, args: dict[str, Any], rag_store: rag.VectorStore) -> str:
    if name == "extract_from_image":
        try:
            path = _resolve_in_sample_data(args["relative_path"])
        except file_tools.PathEscapeError as e:
            return json.dumps({"error": str(e)})
        if not path.exists():
            return json.dumps({"error": f"'{args['relative_path']}' not found in sample_data"})
        result = ocr_pipeline.extract(path)
        return json.dumps({"text": result.text, "confidence": result.mean_confidence})

    if name == "search_documents":
        hits = rag_store.search(args["query"], k=3)
        return json.dumps([{"source": h.source, "text": h.text, "score": h.score} for h in hits])

    if name == "run_code":
        try:
            box = sandbox.get_sandbox()
        except sandbox.SandboxUnavailableError as e:
            return json.dumps({"error": str(e)})
        result = box.run_python(args["code"])
        return json.dumps({
            "stdout": result.stdout, "stderr": result.stderr,
            "exit_code": result.exit_code, "backend": result.backend,
        })

    if name == "generate_approval_note":
        try:
            out_path = _resolve_in_sample_data(f"{args['reference_no']}.docx")
        except file_tools.PathEscapeError as e:
            return json.dumps({"error": str(e)})
        note = docgen.ApprovalNote(
            title=args["title"],
            reference_no=args["reference_no"],
            prepared_for=args["prepared_for"],
            findings=[docgen.Finding(**f) for f in args["findings"]],
            recommendation=args["recommendation"],
        )
        docgen.build_approval_note(note, out_path)
        return json.dumps({"status": "written", "path": str(out_path)})

    return json.dumps({"error": f"unknown tool '{name}'"})


# --- LLM client interface ------------------------------------------------------
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    def chat(self, messages: list[dict], tools: list[dict]) -> ChatResponse: ...


class RealLLMClient:
    """
    Deployment client — talks to any OpenAI-compatible endpoint (Ollama, vLLM, llama.cpp).
    Requires: pip install openai
    """

    def __init__(self, base_url: str, model: str, api_key: str = "not-needed-locally"):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, tools=tools,
        )
        msg = resp.choices[0].message
        calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=json.loads(tc.function.arguments))
            for tc in (msg.tool_calls or [])
        ]
        return ChatResponse(content=msg.content, tool_calls=calls)


class MockLLMClient:
    """
    Scripted client for testing the LOOP MECHANICS without live model weights.
    Follows a fixed plan: read the scan -> ground one fact against the SOP corpus
    -> draft the approval note -> stop. This is the exact flagship demo task from
    the PS, proven end to end even without a GPU in this environment.
    """

    def __init__(self):
        self._step = 0

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatResponse:
        self._step += 1
        if self._step == 1:
            return ChatResponse(content=None, tool_calls=[
                ToolCall(id="1", name="extract_from_image",
                         arguments={"relative_path": "sample_inspection_scan.png"})
            ])
        if self._step == 2:
            return ChatResponse(content=None, tool_calls=[
                ToolCall(id="2", name="search_documents",
                         arguments={"query": "pressure relief valve calibration requirement"})
            ])
        if self._step == 3:
            return ChatResponse(content=None, tool_calls=[
                ToolCall(id="3", name="generate_approval_note", arguments={
                    "title": "Approval Note — PV-2201 Inspection Findings",
                    "reference_no": "AN-2026-DEMO",
                    "prepared_for": "Mechanical Integrity Lead",
                    "findings": [
                        {"text": "External corrosion on lower shell weld seam, approx 40mm, "
                                  "depth not visually measurable.",
                         "source": "Scanned inspection report, PV-2201, 22-Aug-2026"},
                        {"text": "PRV-2201-A calibration is overdue (last calibrated 14-Feb-2025).",
                         "source": "Scanned inspection report, PV-2201, 22-Aug-2026"},
                    ],
                    "recommendation": "Schedule UT thickness check within 30 days; recalibrate "
                                       "PRV-2201-A before the vessel returns to service.",
                })
            ])
        return ChatResponse(
            content="Task complete: extracted findings from the scanned report, "
                    "grounded the PRV requirement against internal SOPs, and drafted "
                    "AN-2026-DEMO.docx for reviewer sign-off.",
            tool_calls=[],
        )


# --- The agent loop itself ----------------------------------------------------
def run_agent(user_task: str, llm: LLMClient, rag_store: rag.VectorStore) -> str:
    messages = [
        {"role": "system", "content": (
            "You are an industrial operations assistant. Use tools to gather real "
            "evidence before drafting anything. Every finding in a generated note "
            "must cite its source. Never invent a citation."
        )},
        {"role": "user", "content": user_task},
    ]

    for i in range(MAX_ITERATIONS):
        response = llm.chat(messages, TOOL_SCHEMA)

        if not response.tool_calls:
            return response.content or "(no response)"

        # Record the assistant's tool-call turn, then execute each and feed results back —
        # this is the "observe" half of plan -> act -> observe -> repeat.
        messages.append({"role": "assistant", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
            for tc in response.tool_calls
        ]})
        for tc in response.tool_calls:
            print(f"  [iteration {i+1}] calling tool: {tc.name}({tc.arguments})")
            result = execute_tool(tc.name, tc.arguments, rag_store)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return "(stopped: exceeded MAX_ITERATIONS without a final answer — check for a looping tool call)"


if __name__ == "__main__":
    # End-to-end proof of the flagship PS task, using the mock client so the loop
    # mechanics are verified without needing a GPU or downloaded model in this sandbox.
    # Swap MockLLMClient() for RealLLMClient(base_url=..., model=...) on deployment —
    # nothing else in this function changes.
    store = rag.SimpleTfidfStore()
    rag.ingest_directory(store, Path(__file__).parent.parent / "sample_data")

    task = ("A pressure vessel inspection report was just scanned in. Read it, "
            "check any relevant internal SOP requirements, and draft an approval note.")
    print(f"Task: {task}\n")
    final = run_agent(task, MockLLMClient(), store)
    print(f"\nFinal response:\n{final}")