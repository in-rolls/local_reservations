PY ?= uv run python
# The OCR cannot share an environment with the parsers: savitr pins pillow<11
# where pdfplumber needs >=12.2. That used to mean a hand-made ocrenv/; it is
# now a uv dependency group declared as conflicting, so uv refuses to install
# both together rather than leaving whichever came second broken.
# --no-group dev: dev is on by default and conflicts with ocr, so asking
# for ocr alone is an error rather than a swap.
OCR_PY ?= uv run --no-group dev --group ocr python
UV_DOCKER_IMAGE ?= ghcr.io/astral-sh/uv:0.12.7-python3.12-trixie

.PHONY: help inventory probe assam assam-2025 assam-2025-extract assam-2025-ocr assam-harvest gujarat gujarat-ocr gujarat-harvest gujarat-validate goa jharkhand jharkhand-ocr jharkhand-bench jharkhand-bench-record jk jk-2010-extract jk-2016-extract ap karnataka telangana wb validate test ci-docker coverage state-readmes stats worklist master manifest verify release-check expect dictionary

help:
	@echo "make inventory   classify the source documents already in data/"
	@echo "make probe       fetch candidate web sources and classify them"
	@echo "make assam      parse + validate held Assam reservation sources"
	@echo "make assam-2025 parse + validate held Assam 2025 PRI sources"
	@echo "make assam-2025-extract  extract reviewed Assam 2025 source tables"
	@echo "make assam-2025-ocr DISTRICT=...  OCR one Assam district scan"
	@echo "make assam-harvest  fetch Assam's 2025 district PRI notifications"
	@echo "make gujarat     parse + validate held Gujarat rotation orders"
	@echo "make gujarat-ocr extract raw cells from Gujarat's encoded PDFs"
	@echo "make gujarat-harvest  fetch Gujarat's 2020 PRI rotation orders"
	@echo "make gujarat-validate verify Gujarat's held sources offline"
	@echo "make goa         parse + validate Goa ward reservation"
	@echo "make jharkhand   parse + validate Jharkhand, one file per tier"
	@echo "make jharkhand-ocr  re-read the Jharkhand scans with Surya (~6h)"
	@echo "make jharkhand-bench  gates for a Jharkhand parser change"
	@echo "make jk          parse + validate Jammu & Kashmir"
	@echo "make jk-2010-extract  extract J&K 2010 digital tables"
	@echo "make jk-2016-extract  extract J&K 2016 digital tables"
	@echo "make ap          parse + validate Andhra Pradesh"
	@echo "make karnataka   parse + validate Karnataka's held source series"
	@echo "make telangana   parse + validate Telangana"
	@echo "make wb          parse + validate West Bengal"
	@echo "make validate    run every state validator without reparsing"
	@echo "make coverage    regenerate the readme table and check every link"
	@echo "make expect      triage every column against the data dictionary"
	@echo "make dictionary  regenerate DICTIONARY.md from the declarations"
	@echo "make test        unit tests for the shared normalizer"
	@echo "make ci-docker   run the release checks in a clean Python 3.12 container"
	@echo "make sweep       what the web archive holds, per state commission"
	@echo "make karnataka-ocr  read the Kannada scans; resumable, ~10 hours"
	@echo "make transliterate  Indic names -> Latin, into a committed table"
	@echo "make sources        rebuild SOURCES.md's holdings table from disk"

inventory:
	$(PY) -m local_reservations.tools.inventory

probe:
	$(PY) -m local_reservations.tools.probe_sources --skip-unreachable

assam: assam-2025-extract
	$(PY) -m local_reservations.states.assam.parse
	$(PY) -m local_reservations.states.assam.parse_2025
	$(PY) -m local_reservations.states.assam.validate

assam-harvest:
	$(PY) -m local_reservations.states.assam.harvest

assam-2025-extract:
	$(PY) -m local_reservations.states.assam.extract_2025

assam-2025-ocr:
	$(OCR_PY) -m local_reservations.states.assam.ocr_2025 --district "$(DISTRICT)"

assam-2025: assam-2025-extract
	$(PY) -m local_reservations.states.assam.parse_2025
	$(PY) -m local_reservations.states.assam.validate

gujarat-harvest:
	$(PY) -m local_reservations.states.gujarat.harvest

gujarat-ocr:
	$(PY) -m local_reservations.states.gujarat.ocr

gujarat:
	$(PY) -m local_reservations.states.gujarat.parse
	$(PY) -m local_reservations.states.gujarat.validate

gujarat-validate:
	$(PY) -m local_reservations.states.gujarat.validate

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

jk-2010-extract:
	$(PY) -m local_reservations.states.jk.extract_2010

jk-2016-extract:
	$(PY) -m local_reservations.states.jk.extract_2016

jk: jk-2010-extract jk-2016-extract
	$(PY) -m local_reservations.states.jk.parse
	$(PY) -m local_reservations.states.jk.validate

ap:
	$(PY) -m local_reservations.states.ap.parse
	$(PY) -m local_reservations.states.ap.validate

karnataka:
	$(PY) -m local_reservations.states.karnataka.parse
	$(PY) -m local_reservations.states.karnataka.parse_tzp
	$(PY) -m local_reservations.states.karnataka.validate

telangana:
	$(PY) -m local_reservations.states.telangana.parse
	$(PY) -m local_reservations.states.telangana.validate

wb:
	$(PY) -m local_reservations.states.wb.parse
	$(PY) -m local_reservations.states.wb.validate

validate:
	$(PY) -m local_reservations.states.ap.validate
	$(PY) -m local_reservations.states.assam.validate
	$(PY) -m local_reservations.states.goa.validate
	$(PY) -m local_reservations.states.gujarat.validate
	$(PY) -m local_reservations.states.jharkhand.validate
	$(PY) -m local_reservations.states.jk.validate
	$(PY) -m local_reservations.states.karnataka.validate
	$(PY) -m local_reservations.states.telangana.validate
	$(PY) -m local_reservations.states.wb.validate

master:
	$(PY) -m local_reservations.tools.build_master

manifest:
	$(PY) -m local_reservations.tools.build_manifest

verify:
	$(PY) -m local_reservations.tools.verify_manifest

# Prepares and checks a release. It deliberately does not tag: a tag is one of
# the few things you cannot take back, so this prints the command and a human
# runs it.
release-check: test validate master stats worklist coverage manifest verify
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

ci-docker:
	docker run --rm --pull=always \
		--mount type=bind,source="$(abspath ..)",target=/workspace \
		--workdir /workspace/local_elections \
		--env UV_PROJECT_ENVIRONMENT=/tmp/local-reservations-venv \
		--env UV_CACHE_DIR=/tmp/uv-cache \
		--env RUFF_CACHE_DIR=/tmp/ruff-cache \
		$(UV_DOCKER_IMAGE) \
		sh -c 'apt-get update && \
			apt-get install -y --no-install-recommends poppler-utils && \
			uv sync --no-default-groups --frozen --group dev --all-extras && \
			uv run ruff check . && \
			uv run ruff format --check . && \
			uv run pyright && \
			uvx --from pydoclint==0.9.1 pydoclint src/ && \
			uvx preen check --strict --skip tests && \
			uv run pytest tests -q -p no:cacheprovider && \
			uv build --out-dir /tmp/dist && \
			uvx twine check /tmp/dist/*'
