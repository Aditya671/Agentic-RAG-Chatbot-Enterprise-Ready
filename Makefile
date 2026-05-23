PYTHON_VERSION := $(shell cat .python-version)

.PHONY: venv
venv:
	uv venv --python $(PYTHON_VERSION) .venv
	@echo "Virtual environment created at ./.venv"
	@echo "Run 'source .venv/bin/activate' to activate it"

.PHONY: install
install:
	uv sync --no-dev
	@echo "Dependencies installed"

.PHONY: install-dev
install-dev:
	uv sync
	@echo "Dev dependencies installed"

.PHONY: sync
sync:
	uv sync
	@echo "Dependencies synced"

.PHONY: clean
clean:
	rm -rf .venv
	rm -rf *.egg-info
	rm -rf build
	rm -rf dist
	@echo "Cleaned up the project"
