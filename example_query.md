# Example Queries — Try These

Copy-paste these into the Streamlit UI or CLI to test the pipeline. Three levels of complexity, each demonstrating different features.

---

## 1. Simple (single-file)

```
Write a function that checks if a string is a palindrome. Include assert-based tests.
```

**What to observe:** Basic pipeline flow. Researcher searches → Coder writes one file → Evaluator scores quality → Reviewer sandbox-tests → Approval gate → Final report with token costs.

---

## 2. Medium (single-file, algorithmic)

```
Implement a thread-safe least-recently-used (LRU) cache with configurable capacity. Include assert-based tests covering: basic get/put, eviction when full, updating existing keys, and capacity of 1.
```

**What to observe:** The evaluator gives nuanced scores across 5 dimensions. If the first attempt has a bug, the coder retries with the failure output fed back. Watch the retry count in the final report.

---

## 3. Advanced (multi-file project)

```
Build a command-line task tracker with add, list, complete, and delete commands. Store tasks in a JSON file. Include a main.py for CLI handling, a storage.py for file I/O, and a test_tasker.py with assert-based tests covering all four commands.
```

**What to observe:** Multi-file generation. The coder outputs a JSON with multiple files. The approval gate shows tabs for each file. The sandbox runs the project entrypoint. The final report renders per-file code blocks.

---

## Usage

**Streamlit:**
```bash
streamlit run frontend/app.py
```
Paste any query above into the text area, click **Run**, approve when prompted.

**CLI:**
```bash
python run_cli.py "Write a function that checks if a string is a palindrome. Include assert-based tests."
```

**Benchmark (all 5 built-in tasks):**
```bash
python scripts/run_benchmark.py --quick
```
