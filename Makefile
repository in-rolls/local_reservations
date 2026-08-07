PY ?= python3

.PHONY: help inventory probe goa jharkhand test coverage

help:
	@echo "make inventory   classify the source documents already in data/"
	@echo "make probe       fetch candidate web sources and classify them"
	@echo "make goa         parse + validate Goa ward reservation"
	@echo "make jharkhand   parse + validate Jharkhand, one file per tier"
	@echo "make test        unit tests for the shared normalizer"

inventory:
	$(PY) scripts/inventory.py

probe:
	$(PY) scripts/probe_sources.py --skip-unreachable

goa:
	$(PY) scripts/goa/parse.py
	$(PY) scripts/goa/validate.py

jharkhand:
	$(PY) scripts/jharkhand/parse.py
	$(PY) scripts/jharkhand/validate.py

test:
	cd scripts/common && $(PY) -m pytest -q
