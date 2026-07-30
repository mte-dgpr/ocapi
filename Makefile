PYTHON ?= python
FLAKE8 ?= $(PYTHON) -m flake8
PYTEST ?= $(PYTHON) -m pytest
MYPY ?= $(PYTHON) -m mypy

.PHONY: lint typecheck test

lint:
	$(FLAKE8) ocapi

typecheck:
	ENV=development LC_ALL=C $(MYPY)

test:
	$(PYTEST)
