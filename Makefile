PYTHON ?= python
FLAKE8 ?= $(PYTHON) -m flake8
PYTEST ?= $(PYTHON) -m pytest
MYPY ?= $(PYTHON) -m mypy

.PHONY: lint typecheck test

lint:
\t$(FLAKE8) ocapi

typecheck:
\t$(MYPY) .

test:
\t$(PYTEST)

