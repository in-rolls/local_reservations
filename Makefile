PY ?= python3
# The OCR cannot run under $(PY): surya-ocr pins pillow<11 where pdfplumber
# needs >=12.2, so it gets its own venv. Only `make jharkhand-ocr` uses this.
OCR_PY ?= ./ocrenv/bin/python

.PHONY: help inventory probe goa jharkhand jharkhand-ocr jharkhand-bench jharkhand-bench-record jk ap test coverage state-readmes stats worklist master manifest verify release-check expect dictionary

help:
	@echo "make inventory   classify the source documents already in data/"
	@echo "make probe       fetch candidate web sources and classify them"
	@echo "make goa         parse + validate Goa ward reservation"
	@echo "make jharkhand   parse + validate Jharkhand, one file per tier"
	@echo "make jharkhand-ocr  re-read the Jharkhand scans with Surya (~6h)"
	@echo "make jharkhand-bench  gates for a Jharkhand parser change"
	@echo "make jk          parse + validate Jammu & Kashmir"
	@echo "make ap          parse + validate Andhra Pradesh"
	@echo "make coverage    regenerate the readme table and check every link"
	@echo "make expect      triage every column against the data dictionary"
	@echo "make dictionary  regenerate DICTIONARY.md from the declarations"
	@echo "make test        unit tests for the shared normalizer"
	@echo "make sweep       what the web archive holds, per state commission"
	@echo "make karnataka-ocr  read the Kannada scans; resumable, ~10 hours"

inventory:
	$(PY) scripts/inventory.py

probe:
	$(PY) scripts/probe_sources.py --skip-unreachable

sweep:
	$(PY) scripts/archive_sweep.py

# Both resume. The OCR skips documents it has already cached and, within a
# document, pages it has already read; the harvest skips files whose bytes on
# disk still hash to what the manifest recorded. Re-running either is how you
# resume it - there is no separate command and no state to clean up.
karnataka-ocr:
	./ocrenv/bin/python scripts/karnataka/ocr.py

goa:
	$(PY) scripts/goa/parse.py
	$(PY) scripts/goa/validate.py

jharkhand:
	$(PY) scripts/jharkhand/parse.py
	$(PY) scripts/jharkhand/validate.py

# The gates a parser change has to clear, against data/stats/jharkhand_bench.json.
# `make jharkhand-bench-record` stores what the code does now; run it only when
# you have decided the current numbers are the ones to defend.
jharkhand-bench:
	$(PY) scripts/jharkhand/bench.py

jharkhand-bench-record:
	$(PY) scripts/jharkhand/bench.py --record

# Not part of `make jharkhand`, and not a dependency of anything. Its output is
# committed, it takes about six hours, and it needs an interpreter the rest of
# the repository cannot share - see requirements-ocr.txt.
jharkhand-ocr:
	$(OCR_PY) scripts/jharkhand/ocr.py
	$(PY) scripts/jharkhand/ocr_seats.py

jk:
	$(PY) scripts/jk/parse.py
	$(PY) scripts/jk/validate.py

ap:
	$(PY) scripts/ap/parse.py
	$(PY) scripts/ap/validate.py

master:
	$(PY) scripts/build_master.py

manifest:
	$(PY) scripts/build_manifest.py

verify:
	$(PY) scripts/verify_manifest.py

# Prepares and checks a release. It deliberately does not tag: a tag is one of
# the few things you cannot take back, so this prints the command and a human
# runs it.
release-check: test master stats worklist coverage manifest verify
	@$(PY) scripts/release_check.py $(VERSION)

stats:
	$(PY) scripts/build_stats.py --quiet

worklist:
	$(PY) scripts/build_worklist.py

coverage: stats worklist state-readmes
	$(PY) scripts/build_coverage.py --check

state-readmes:
	$(PY) scripts/build_state_readmes.py

expect:
	cd scripts/common && $(PY) expectations.py

dictionary:
	cd scripts/common && $(PY) make_dictionary.py

test:
	cd scripts/common && $(PY) -m pytest -q
