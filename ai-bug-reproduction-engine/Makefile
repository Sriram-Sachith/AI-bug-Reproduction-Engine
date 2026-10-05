PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PY := $(BIN)/python

.PHONY: venv install test demo demo-retest api docker-build zip

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(PIP) install -r requirements.txt

test:
	$(BIN)/pytest

demo:
	$(PY) -m bugrepro run \
		--report examples/bug_report.json \
		--repo examples/sample-shop \
		--local

demo-retest:
	$(PY) -m bugrepro retest RUN-0001 \
		--repo examples/sample-shop-fixed \
		--local

api:
	$(PY) -m uvicorn bugrepro.api:app --reload --port 8000

docker-build:
	docker build -t bugrepro-runner:latest runner

zip:
	cd .. && zip -r AI_Bug_Reproduction_Engine.zip ai-bug-reproduction-engine \
		-x 'ai-bug-reproduction-engine/.venv/*' \
		-x 'ai-bug-reproduction-engine/data/*' \
		-x 'ai-bug-reproduction-engine/.git/*'
