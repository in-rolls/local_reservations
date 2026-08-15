PY ?= uv run python
# The OCR cannot share an environment with the parsers: savitr pins pillow<11
# where pdfplumber needs >=12.2. That used to mean a hand-made ocrenv/; it is
# now a uv dependency group declared as conflicting, so uv refuses to install
# both together rather than leaving whichever came second broken.
# --no-group dev: dev is on by default and conflicts with ocr, so asking
# for ocr alone is an error rather than a swap.
OCR_PY ?= uv run --no-group dev --group ocr python

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
	@echo "make transliterate  Indic names -> Latin, into a committed table"
	@echo "make sources        rebuild SOURCES.md's holdings table from disk"

inventory:
	$(PY) -m local_reservations.tools.inventory

probe:
	$(PY) -m local_reservations.tools.probe_sources --skip-unreachable

sweep:
	$(PY) -m local_reservations.tools.archive_sweep

# Both resume. The OCR skips documents it has already cached and, within a
# document, pages it has already read; the harvest skips files whose bytes on
# disk still hash to what the manifest recorded. Re-running either is how you
# resume it - there is no separate command and no state to clean up.
# The third stage: collect -> parse -> transliterate -> pool. Writes a lookup
# table keyed on the name, which is committed; the pooled build only reads it.
# --with indicate rather than a dependency group: it pulls torch and is needed
# only when the table is regenerated, which is rarely.
transliterate:
	uv run --with indicate python -m local_reservations.tools.transliterate

karnataka-ocr:
	uv run --group ocr python -m local_reservations.states.karnataka.ocr

goa:
	$(PY) -m local_reservations.states.goa.parse
	$(PY) -m local_reservations.states.goa.validate

jharkhand:
	$(PY) -m local_reservations.states.jharkhand.parse
	$(PY) -m local_reservations.states.jharkhand.validate

# The gates a parser change has to clear, against data/stats/jharkhand_bench.json.
# `make jharkhand-bench-record` stores what the code does now; run it only when
# you have decided the current numbers are the ones to defend.
jharkhand-bench:
	$(PY) -m local_reservations.states.jharkhand.bench

jharkhand-bench-record:
	$(PY) -m local_reservations.states.jharkhand.bench --record

# Not part of `make jharkhand`, and not a dependency of anything. Its output is
# committed, it takes about six hours, and it needs an interpreter the rest of
# the repository cannot share - see requirements-ocr.txt.
jharkhand-ocr:
	$(OCR_PY) -m local_reservations.states.jharkhand.ocr
	$(PY) -m local_reservations.states.jharkhand.ocr_seats

jk:
	$(PY) -m local_reservations.states.jk.parse
	$(PY) -m local_reservations.states.jk.validate

ap:
	$(PY) -m local_reservations.states.ap.parse
	$(PY) -m local_reservations.states.ap.validate

master:
	$(PY) -m local_reservations.tools.build_master

manifest:
	$(PY) -m local_reservations.tools.build_manifest

verify:
	$(PY) -m local_reservations.tools.verify_manifest

# Prepares and checks a release. It deliberately does not tag: a tag is one of
# the few things you cannot take back, so this prints the command and a human
# runs it.
release-check: test master stats worklist coverage manifest verify
	@$(PY) -m local_reservations.tools.release_check $(VERSION)

stats:
	$(PY) -m local_reservations.tools.build_stats --quiet

worklist:
	$(PY) -m local_reservations.tools.build_worklist

coverage: stats worklist state-readmes sources
	$(PY) -m local_reservations.tools.build_coverage --check

# SOURCES.md is a feasibility survey and most of it is judgement, which stays
# hand-written. Its holdings table is not: it is a count of what is on disk,
# and it drifted to "1 scan, 7 pages" for a state holding 649 documents.
sources:
	$(PY) -m local_reservations.tools.build_sources

state-readmes:
	$(PY) -m local_reservations.tools.build_state_readmes

expect:
	$(PY) -m local_reservations.common.expectations

dictionary:
	$(PY) -m local_reservations.common.make_dictionary

test:
	$(PY) -m pytest tests -q
