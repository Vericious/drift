# Sample Makefile for testing drift MakefileExtractor

# Build targets
.PHONY: all
all: build test

# Build the project
.PHONY: build
build: ## Build the project
	@echo "Building..."
	python setup.py build

# Run tests
.PHONY: test
test: ## Run the test suite
	pytest tests/

# Lint code
.PHONY: lint
lint:
	flake8 .

# Format code
.PHONY: format
format: ## Format code with black and isort
	black .
	isort .

# Clean build artifacts
.PHONY: clean
clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info/

# Install dependencies
.PHONY: install
install: ## Install dependencies
	pip install -e .

# Run with coverage
.PHONY: coverage
coverage: ## Run tests with coverage
	pytest --cov=src tests/

# Docker build
.PHONY: docker-build
docker-build: ## Build Docker image
	docker build -t myapp:latest .

# Deploy
deploy: build docker-build  ## Deploy the application
	@echo "Deploying..."
