# Runbook — Multi-Agent Research → Code → Review System

Step-by-step guide to set up and run the project.

---

## 1. Environment Setup

```bash
cd /e/KSL-FILES/PI/pjct_july26/multi-agent-research-coder_july18/multi-agent-research-coder
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

---

## 2. API Keys

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
GROQ_API_KEY=***     # REQUIRED — get from console.groq.com
```

Optional:

```
OPENAI_API_KEY=***    # Fallback if Groq errors
TAVILY_API_KEY=***   # Web search for the researcher agent
```

---

## 3. Run Offline Tests

```bash
source .venv/Scripts/activate
pytest tests/ -v
```

Expected: **5/5 passing**. These need no API keys.

If the Docker sandbox test fails, either start Docker Desktop or let it fall back to subprocess (the fix in `sandbox/executor.py` handles this automatically).

---

## 4. Run CLI — Simple Task

```bash
source .venv/Scripts/activate
python run_cli.py "Write a function that reverses a string. Include assert tests."
```

Pipeline flow:
1. **Researcher** — generates search queries
2. **Coder** — writes code based on research
3. **Reviewer** — runs code in sandbox (Docker if available, else subprocess)
4. If tests fail → loops back to Coder (up to 3 retries)
5. **Human approval** — pauses and asks y/N
6. **Final report** — with code, test results, token summary

---

## 5. Resume a Run (Checkpointing Demo)

Kill the process mid-run (Ctrl+C), then resume:

```bash
python run_cli.py --resume <thread_id>
```

(The `thread_id` was printed when the run started.)

---

## 6. Streamlit UI

```bash
source .venv/Scripts/activate
streamlit run frontend/app.py
```

Opens a browser UI with approve/reject buttons.

---

## 7. Run the Benchmark

```bash
source .venv/Scripts/activate
python scripts/run_benchmark.py --quick
```

Runs 3 benchmark tasks end-to-end. Results in `reports/`.

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Docker sandbox test fails | Docker Desktop not running | Start Docker Desktop, or ignore — falls back to subprocess |
| `GROQ_API_KEY not set` | Missing `.env` | Copy `.env.example` to `.env` and fill in your key |
| `ModuleNotFoundError` | Dependencies not installed | `pip install -r requirements.txt` |

## File Layout

```
run_cli.py              # CLI entry point
frontend/app.py         # Streamlit UI
tests/                  # Offline tests (no API keys)
scripts/run_benchmark.py  # Benchmark runner
notebooks/              # Jupyter notebooks
reports/                # Generated reports
```
