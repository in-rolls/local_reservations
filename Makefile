PY ?= python3

.PHONY: help inventory probe goa jharkhand jk ap test coverage expect dictionary

help:
	@echo "make inventory   classify the source documents already in data/"
	@echo "make probe       fetch candidate web sources and classify them"
	@echo "make goa         parse + validate Goa ward reservation"
	@echo "make jharkhand   parse + validate Jharkhand, one file per tier"
	@echo "make jk          parse + validate Jammu & Kashmir"
	@echo "make ap          parse + validate Andhra Pradesh"
	@echo "make coverage    regenerate the readme table and check every link"
	@echo "make expect      triage every column against the data dictionary"
	@echo "make dictionary  regenerate DICTIONARY.md from the declarations"
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

jk:
	$(PY) scripts/jk/parse.py
	$(PY) scripts/jk/validate.py

ap:
	$(PY) scripts/ap/parse.py
	$(PY) scripts/ap/validate.py

coverage:
	$(PY) scripts/build_coverage.py --check

expect:
	cd scripts/common && $(PY) expectations.py

dictionary:
	cd scripts/common && $(PY) make_dictionary.py

test:
	cd scripts/common && $(PY) -m pytest -q
