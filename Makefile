PYTHON ?= python
FLAKE8 ?= $(PYTHON) -m flake8
PYTEST ?= $(PYTHON) -m pytest
MYPY ?= $(PYTHON) -m mypy
PRE_COMMIT ?= $(PYTHON) -m pre_commit
CONTAINER_ENGINE ?= podman

.PHONY: lint typecheck test pre-commit check-dependencies-loose

lint:
	$(FLAKE8) ocapi

typecheck:
	ENV=development LC_ALL=C $(MYPY)

test:
	$(PYTEST)

pre-commit:
	$(PRE_COMMIT) run --hook-stage pre-commit

# Run Trivy filesystem scan (loose, used by pre-commit)
check-dependencies-loose:
	@set -e; \
	mkdir -p tmp; \
	tmp_req=tmp/requirements.txt; \
	trap 'rm -f "$$tmp_req"' EXIT; \
	$(PYTHON) -m pip freeze --exclude-editable > "$$tmp_req"; \
	$(CONTAINER_ENGINE) run --rm -v ./:/workspace:Z -v "$$PWD/$$tmp_req:/workspace/$$tmp_req:Z" aquasec/trivy:latest fs --exit-code 1 --severity CRITICAL --scanners vuln /workspace/$$tmp_req
