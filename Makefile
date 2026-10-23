PYTHON ?= python
FLAKE8 ?= $(PYTHON) -m flake8
PYTEST ?= $(PYTHON) -m pytest
MYPY ?= $(PYTHON) -m mypy
PRE_COMMIT ?= $(PYTHON) -m pre_commit

.PHONY: lint typecheck test pre-commit

lint:
	$(FLAKE8) ocapi

typecheck:
	ENV=development LC_ALL=C $(MYPY)

test:
	$(PYTEST)

pre-commit:
	$(PRE_COMMIT) run --hook-stage pre-commit
