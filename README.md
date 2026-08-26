# Rakshak AI — Sovereign Industrial Workbench

Prototype for **SIH 2026 PS 26117**: a self-hosted, air-gapped agentic AI workbench for confidential industrial work.

Rakshak AI demonstrates the operating path required by the problem statement: local multimodal intake, automatic specialist-model routing, an iterative tool-using agent, grounded internal knowledge search, isolated code execution, Word-document output, and a visible zero-egress posture.

## What the prototype demonstrates

- **Sovereign by design:** Docker services run on an internal-only network; the code sandbox is launched with no network attachment.
- **Automatic model selection:** a lightweight local router selects vision, document/reasoning, or code specialists based on task and attachments.
- **Agentic execution:** the flagship task reads a scanned report, retrieves internal SOP evidence, and generates a reviewable Word approval note.
- **Multimodal workflow:** OCR handles scanned documents today and has a clean escalation path for a local vision-language model.
- **Human control:** generated approval notes carry source citations, a draft banner, and a mandatory reviewer-sign-off area.
- **Evidence for judges:** the operator console displays routing decisions, agent stages, a local model registry, audit records, and zero outbound traffic.

## Run locally

```bash
cd gateway
python -m pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`. The UI works as a polished operator-console prototype even before models are installed. With the API running, the document task executes the actual demo workflow and writes `sample_data/AN-2026-DEMO.docx`.

Code execution (`run_code`) requires a local Docker daemon by default — this is what enforces the "no network access" guarantee, so the gateway refuses to run generated code without it rather than silently falling back to an unisolated subprocess. If you're developing on a machine without Docker and only need to exercise the rest of the loop, opt into the weaker fallback explicitly:

cd gateway python -m pip install -r requirements.txt pytest pytest

Covers routing rules, retrieval, the docgen path, and — most importantly — that tool arguments (`relative_path`, `reference_no`) can't be used to escape `sample_data/` even if a compromised or prompt-injected model tries to supply something like `../../etc/passwd`.

## GPU deployment

On the demonstration workstation, pre-download the selected open-weight models to Ollama, then switch `DEMO_MODE = False` in `gateway/main.py`. The same router and agent loop use `RealLLMClient`, which supports any OpenAI-compatible local endpoint (Ollama, vLLM, or llama.cpp).

```bash
# One-time controlled download before entering the air-gapped environment
docker compose run --network host ollama ollama pull qwen2.5:14b-instruct
docker compose run --network host ollama ollama pull qwen2.5-coder:14b
docker compose run --network host ollama ollama pull qwen2-vl:7b

# Thereafter all application services are restricted to the internal network
docker compose up --build
```

## Repository layout

```text
gateway/
  main.py                 FastAPI gateway and operator-console server
  static/                 Dark-mode local operator experience
  router.py               Capability-based local model routing
  orchestrator.py         Plan → tool → observe → iterate agent loop
  model_registry.yaml     Add / replace models without redesign
  ocr/pipeline.py         Tesseract OCR with local VLM escalation seam
  tools/rag.py            Local SOP/document grounding
  tools/sandbox.py        Network-isolated code execution
  tools/docgen.py         Cited Word approval-note generation
network-monitor/          Live host egress monitor for the demo
sample_data/              Inspection scan, SOP corpus, sample outputs
docker-compose.yml        GPU-capable, internal-network deployment
```

## Demo sequence

1. Open the workbench and select **Document analysis**.
2. Run the preloaded pressure-vessel inspection task.
3. Show the selected model, local OCR/SOP stages, and drafted approval note.
4. Switch to **Code & calculations** to show separate routing to the code specialist and isolated execution.
5. Keep `network-monitor/monitor.py` visible: outbound traffic stays at `0 B/s` throughout.

## Current scope

The repository provides a functional orchestration and document-output proof using `MockLLMClient` for a machine without locally downloaded weights. Before the final on-GPU presentation, activate a local open-weight endpoint, replace the basic TF-IDF store with Qdrant plus local embeddings for a large corpus, and connect the existing VLM hook for handwriting/P&ID interpretation. No confidential document needs to leave the deployment environment at any point.

