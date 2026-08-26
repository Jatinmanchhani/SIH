# Sovereign AI Workbench — SIH prototype

An air-gapped, multi-model agentic assistant for industrial knowledge work: reads scanned
reports, grounds answers in internal SOPs, runs code in a sandbox, and drafts real Word
approval notes — with model auto-selection and zero external network calls.

## What's actually proven to work right now (tested, in this repo)

Every piece below was built and run end to end while developing this repo — not just
written, actually executed and verified:

| Piece | File | Proof |
|---|---|---|
| Model router | `gateway/router.py` | `python router.py` — routes 4 sample tasks to 2 different specialists correctly |
| RAG / grounding | `gateway/tools/rag.py` | `python rag.py` — retrieves the right SOP for 2 sample queries, with citations |
| Document generation | `gateway/tools/docgen.py` | `python docgen.py` — produces a real, correctly formatted `.docx` approval note |
| OCR pipeline | `gateway/ocr/pipeline.py` | `python pipeline.py` — extracts text from a sample scanned report at 91.8% confidence |
| Code sandbox | `gateway/tools/sandbox.py` | `python sandbox.py` — runs and returns real code output, with automatic Docker/subprocess fallback |
| File tools | `gateway/tools/file_tools.py` | `python file_tools.py` — scoped read/write, blocks path escape |
| **Full agent loop** | `gateway/orchestrator.py` | `python orchestrator.py` — runs the flagship task end to end: scan → OCR → SOP grounding → drafted `.docx` |
| API gateway | `gateway/main.py` | `uvicorn main:app` — all endpoints tested live over HTTP |
| Network monitor | `network-monitor/monitor.py` | `python monitor.py` — reads real interface byte counters |

## What still needs your GPU hardware

This was built in a sandboxed environment with **no GPU and no access to Ollama/Hugging
Face**, so the actual open-weight model inference is stubbed with a scripted
`MockLLMClient` that proves the *loop mechanics* are correct — tool calling, iteration,
routing — without live model intelligence behind it. On your GPU machine:

1. Install Ollama, pull the models listed in `gateway/model_registry.yaml`.
2. In `gateway/main.py`, set `DEMO_MODE = False`. This switches `RealLLMClient` in —
   already written, already wired to the same `run_agent()` function, same tool schema.
   Nothing else in the codebase changes.
3. Swap `SimpleTfidfStore` for a proper embedding-based store once you can pull
   `BAAI/bge-m3` or similar locally — see the `QdrantStore` stub in `rag.py` for the shape.
4. Bring up the full stack: `docker compose up`.

## Quickstart (on your GPU machine)

```bash
# 1. Pull models (needs internet once, then never again)
docker compose run --network host ollama ollama pull qwen2.5:14b-instruct
docker compose run --network host ollama ollama pull qwen2.5-coder:14b
docker compose run --network host ollama ollama pull qwen2-vl:7b

# 2. Flip DEMO_MODE = False in gateway/main.py

# 3. Bring up the fully air-gapped stack
docker compose up --build

# 4. Open Open WebUI
# http://localhost:3000  (points at your gateway, which points at Ollama)

# 5. Run the network monitor on a second screen for your entire demo
python network-monitor/monitor.py
```

## Repo layout

```
gateway/
  main.py              FastAPI gateway — /v1/chat/completions and /agent/run
  router.py             Task classification -> model selection
  orchestrator.py        The agent loop: plan, call tools, observe, repeat
  model_registry.yaml    THE file to edit to add/swap/remove a model
  tools/
    sandbox.py            Code execution, Docker (--network none) + subprocess fallback
    file_tools.py          Scoped file read/write
    rag.py                  Document grounding, swappable vector store
    docgen.py                Approval-note generation (python-docx)
  ocr/
    pipeline.py             Tesseract OCR + VLM escalation stub
network-monitor/
  monitor.py               Live egress proof for your demo screen
docker-compose.yml        Full stack, isolated network, GPU passthrough for Ollama
sample_data/               Sample SOPs + sample scanned report used in all the tests above
```

## Demo script (matches the PS's "Expected Solution" checklist exactly)

1. **Model auto-selection** — hit `/v1/chat/completions` with a coding request, then a
   document request. Show the `[route]` log line picking a different model each time.
2. **Agentic task end to end** — hit `/agent/run` with the inspection-report task. Watch
   it call `extract_from_image` → `search_documents` → `generate_approval_note` and
   produce a real `.docx`.
3. **Coding task in the sandbox** — ask for a BOM total calculation, show it execute and
   return real stdout from inside the sandbox.
4. **Multimodal understanding** — same scanned report, or a P&ID once you've wired the
   vision model in on your GPU box.
5. **Zero external calls** — `network-monitor/monitor.py` running the entire time on a
   second screen, egress column flat at zero throughout.

## Honest limitations to say out loud if asked

- The vision-language-model escalation path (`extract_with_vlm` in `ocr/pipeline.py`) is
  a stub — Tesseract handles typed text well, but P&ID/handwriting understanding needs
  the VLM wired to a real endpoint on your GPU box before demo day.
- `SimpleTfidfStore` is keyword-based, not semantic — good enough for a focused SOP
  corpus, but swap to `QdrantStore` + a real embedding model before you scale past a
  few dozen documents.
- `SubprocessSandbox` is a development fallback, not what you should demo — it shares
  the host network. Confirm `DockerSandbox` is actually active (`get_sandbox()` prints
  which backend it picked) before your run.
