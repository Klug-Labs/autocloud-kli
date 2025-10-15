# Autoklug Makefile

.PHONY: help install install-dev test test-unit test-integration lint format clean build publish docs

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install autoklug
	pip install -e .

install-dev: ## Install autoklug with development dependencies
	pip install -e .[dev]

test: ## Run all tests
	python test_runner.py

test-unit: ## Run unit tests only
	python test_runner.py unit

test-integration: ## Run integration tests only
	python test_runner.py integration

lint: ## Run linting
	flake8 autoklug tests --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 autoklug tests --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	mypy autoklug --ignore-missing-imports

format: ## Format code with black
	black autoklug tests

format-check: ## Check code formatting
	black --check autoklug tests

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: ## Build package
	python -m build

build-check: ## Check package
	twine check dist/*

publish-test: ## Publish to test PyPI
	twine upload --repository testpypi dist/*

publish: ## Publish to PyPI
	twine upload dist/*

docs: ## Build documentation
	mkdocs build

docs-serve: ## Serve documentation locally
	mkdocs serve

security: ## Run security checks
	safety check
	bandit -r autoklug/ -f txt

pre-commit: ## Run pre-commit hooks
	pre-commit run --all-files

setup-pre-commit: ## Setup pre-commit hooks
	pre-commit install

# Development workflow
dev-setup: install-dev setup-pre-commit ## Setup development environment
	@echo "Development environment setup complete!"

dev-test: format-check lint test ## Run all development checks

# CI/CD helpers
ci-test: ## Run tests for CI
	pytest tests/ -v --cov=autoklug --cov-report=xml --cov-report=term-missing

ci-lint: ## Run linting for CI
	flake8 autoklug tests --count --select=E9,F63,F7,F82 --show-source --statistics
	black --check autoklug tests
	mypy autoklug --ignore-missing-imports

# Release helpers
release-check: clean build build-check test lint security ## Run all release checks
	@echo "Release checks passed! Ready to publish."

version: ## Show current version
	python -c "import autoklug; print(autoklug.__version__)"

# Docker helpers (if needed)
docker-build: ## Build Docker image
	docker build -t autoklug .

docker-test: ## Run tests in Docker
	docker run --rm autoklug python test_runner.py
