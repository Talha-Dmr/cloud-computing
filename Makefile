.PHONY: help dev test build deploy clean create-cluster delete-cluster

# Default target
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development
dev: ## Start all services in development mode
	docker-compose up --build

dev-bg: ## Start all services in background
	docker-compose up -d --build

stop: ## Stop all services
	docker-compose down

logs: ## Show logs from all services
	docker-compose logs -f

# Testing
test: ## Run all tests
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-integration: ## Run integration tests
	pytest tests/integration/ -v

test-load: ## Run load tests
	locust -f tests/load/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 60s

# Code Quality
lint: ## Run code linting
	flake8 services/ shared/
	black --check services/ shared/
	isort --check-only services/ shared/

format: ## Format code
	black services/ shared/
	isort services/ shared/

# Building
build: ## Build all Docker images
	docker-compose build

push: ## Push Docker images to registry
	docker-compose push

# Kubernetes
create-cluster: ## Create local Kubernetes cluster
	kind create cluster --name iot-platform --config k8s/cluster.yaml

delete-cluster: ## Delete local Kubernetes cluster
	kind delete cluster --name iot-platform

deploy: ## Deploy to Kubernetes
	kubectl apply -f k8s/namespaces/
	helm upgrade --install iot-platform ./helm/iot-platform/

undeploy: ## Remove from Kubernetes
	helm uninstall iot-platform
	kubectl delete namespace iot-platform monitoring logging

forward: ## Forward ports to local services
	kubectl port-forward -n iot-platform svc/api-gateway 8000:80 &
	kubectl port-forward -n monitoring svc/grafana 3000:3000 &
	kubectl port-forward -n monitoring svc/prometheus 9090:9090 &

# Database
db-migrate: ## Run database migrations
	docker-compose exec device-registry alembic upgrade head

db-reset: ## Reset all databases
	docker-compose down -v
	docker-compose up -d postgres redis influxdb
	sleep 10
	$(MAKE) db-migrate

# Monitoring
monitor: ## Start monitoring stack
	docker-compose -f docker-compose.monitoring.yml up -d

# Clean
clean: ## Clean up all resources
	docker-compose down -v --remove-orphans
	docker system prune -f
	docker volume prune -f

# Install dependencies
install: ## Install Python dependencies
	pip install -r services/device-registry/requirements.txt
	pip install -r services/data-ingestion/requirements.txt
	pip install -r services/alert-engine/requirements.txt

# Development setup
setup: ## Set up development environment
	python -m venv venv
	source venv/bin/activate && pip install --upgrade pip
	$(MAKE) install
	pre-commit install