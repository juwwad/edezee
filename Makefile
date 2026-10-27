.PHONY: help dev backend frontend test eval mock-eval baseline clean install

help:
	@echo "Edezee — common tasks"
	@echo ""
	@echo "  make install    Install backend and frontend dependencies"
	@echo "  make dev        Run backend (:8000) and frontend (:3000) together"
	@echo "  make backend    Run the API only"
	@echo "  make frontend   Run the UI only"
	@echo "  make test       Run the backend test suite"
	@echo "  make mock-eval  Run the 12-case evaluation set offline (no API key)"
	@echo "  make eval       Run the 12-case evaluation set against a live server"
	@echo "  make baseline   Compare naive one-prompt use against Edezee"
	@echo "  make clean      Remove build and cache artefacts"

install:
	cd backend && python3 -m venv .venv && ./.venv/bin/pip install -q --upgrade pip && ./.venv/bin/pip install -q -r requirements.txt
	cd frontend && npm install --no-audit --no-fund

backend:
	cd backend && ./run.sh

frontend:
	cd frontend && npm run dev

# Run both services and stop them together on Ctrl-C.
dev:
	@echo "Starting Edezee backend on :8000 and frontend on :3000 ..."
	@trap 'kill 0' EXIT INT TERM; \
	( cd backend && ./run.sh ) & \
	( cd frontend && npm run dev ) & \
	wait

test:
	cd backend && ./.venv/bin/python -m pytest
	backend/.venv/bin/python -m pytest evaluation/harness_tests -q

mock-eval:
	backend/.venv/bin/python evaluation/run_eval.py --mode mock

eval:
	backend/.venv/bin/python evaluation/run_eval.py --mode live

baseline:
	backend/.venv/bin/python evaluation/baseline.py

clean:
	rm -rf backend/.venv backend/.pytest_cache frontend/.next frontend/node_modules
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
