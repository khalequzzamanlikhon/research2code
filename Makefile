.PHONY: setup test lint typecheck benchmark benchmark-quick ablate clean

setup:
	pip install -r requirements.txt

test:
	python -m pytest tests/ -v

lint:
	ruff check .

typecheck:
	mypy graph/ tools/ sandbox/ mcp_servers/ --ignore-missing-imports

benchmark:
	python scripts/run_benchmark.py

benchmark-quick:
	python scripts/run_benchmark.py --quick

ablate:
	python scripts/run_ablations.py

clean:
	rm -rf checkpoints.sqlite checkpoints.sqlite-journal sandbox_workspace/ reports/*.md .pytest_cache/ __pycache__/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
