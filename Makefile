.PHONY: help setup dev down test lint clean purge

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Initial project setup
	@echo "=== Setting up TelemetryScope ==="
	cd services/ingestion-service && python3 -m venv venv && venv/bin/pip install -r requirements.txt
	cd services/processing-service && python3 -m venv venv && venv/bin/pip install -r requirements.txt
	cd services/query-service && python3 -m venv venv && venv/bin/pip install -r requirements.txt
	cd frontend && npm install
	@echo "=== Setup complete ==="

dev: ## Start all services with Docker Compose
	docker compose up --build

dev-d: ## Start all services in background
	docker compose up --build -d

down: ## Stop all services
	docker compose down

down-v: ## Stop all services and remove volumes
	docker compose down -v

test-ingestion: ## Run ingestion service tests
	cd services/ingestion-service && venv/bin/python -m pytest tests/ -v

test-processing: ## Run processing service tests
	cd services/processing-service && venv/bin/python -m pytest tests/ -v

test-query: ## Run query service tests
	cd services/query-service && venv/bin/python -m pytest tests/ -v

test: test-ingestion test-processing test-query ## Run all backend tests

lint: ## Lint all Python services
	cd services/ingestion-service && venv/bin/python -m flake8 . --max-line-length=120
	cd services/processing-service && venv/bin/python -m flake8 . --max-line-length=120
	cd services/query-service && venv/bin/python -m flake8 . --max-line-length=120

format: ## Format all Python services
	cd services/ingestion-service && venv/bin/python -m black .
	cd services/processing-service && venv/bin/python -m black .
	cd services/query-service && venv/bin/python -m black .

frontend-dev: ## Start frontend dev server
	cd frontend && npm run dev

frontend-build: ## Build frontend
	cd frontend && npm run build

docker-build: ## Build all Docker images
	docker build -t telemetryscope-ingestion:dev services/ingestion-service
	docker build -t telemetryscope-processing:dev services/processing-service
	docker build -t telemetryscope-query:dev services/query-service

k8s-local: ## Deploy to local Kubernetes
	kubectl apply -f kubernetes/namespace.yaml
	kubectl apply -f kubernetes/ --recursive

k8s-status: ## Check Kubernetes status
	kubectl get all -n telemetryscope

k8s-down: ## Remove from local Kubernetes
	kubectl delete namespace telemetryscope --ignore-not-found

clean: ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	rm -rf frontend/dist frontend/node_modules/.cache

purge-data: ## Purge demo data via API
	@echo "Purging demo data..."
	curl -s -X POST http://localhost:8003/api/v1/demo/purge \
		-H 'Content-Type: application/json' \
		-d '{"confirm": true}' | python3 -m json.tool
