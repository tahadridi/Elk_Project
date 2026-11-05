SHELL := /bin/bash

COMPOSE ?= docker compose
ES_URL ?= http://localhost:9200
KIBANA_URL ?= http://localhost:5601
VENV := .venv
VENV_PY := $(VENV)/bin/python
GEN_ARGS ?= --count 2000 --days 3 --with-errors --seed 42

.DEFAULT_GOAL := help

.PHONY: help setup up down reset clean ps logs wait init kibana dashboard gen verify demo restart-logstash

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

$(VENV_PY):
	python3 -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r scripts/requirements.txt

setup: $(VENV_PY) ## Create the Python virtualenv and install dependencies

up: ## Start the whole stack in the background
	$(COMPOSE) up -d

down: ## Stop the stack (keeps volumes)
	$(COMPOSE) down

reset: ## Stop the stack and delete volumes + generated logs (full reset)
	$(COMPOSE) down -v
	$(MAKE) clean

clean: ## Delete generated input files
	rm -f data/input/*.csv data/input/*.json

ps: ## Show container status
	$(COMPOSE) ps

logs: ## Follow container logs
	$(COMPOSE) logs -f --tail=100

wait: ## Wait until Elasticsearch, Logstash and Kibana are healthy
	@echo "Waiting for Elasticsearch..."
	@for i in $$(seq 1 60); do curl -fsS $(ES_URL)/_cluster/health >/dev/null 2>&1 && break; sleep 2; done
	@echo "Waiting for Logstash..."
	@for i in $$(seq 1 60); do [ "$$(docker inspect -f '{{.State.Health.Status}}' sm-logstash 2>/dev/null)" = "healthy" ] && break; sleep 2; done
	@echo "Waiting for Kibana..."
	@for i in $$(seq 1 90); do curl -fsS $(KIBANA_URL)/api/status >/dev/null 2>&1 && break; sleep 2; done
	@echo "All services are ready."

init: ## Install the Elasticsearch index template
	./scripts/init_elasticsearch.sh

kibana: ## Import the Kibana data view and dashboard from the NDJSON export
	KIBANA_URL=$(KIBANA_URL) ./scripts/init_kibana.sh

dashboard: $(VENV_PY) ## Rebuild the Kibana dashboard and refresh the NDJSON export
	KIBANA_URL=$(KIBANA_URL) $(VENV_PY) scripts/build_kibana_dashboard.py
	KIBANA_URL=$(KIBANA_URL) ./scripts/init_kibana.sh

gen: $(VENV_PY) ## Generate fake security logs (CSV + JSON)
	$(VENV_PY) scripts/generate_logs.py $(GEN_ARGS) --out data/input

verify: ## Verify the end-to-end ingestion
	python3 scripts/verify_ingestion.py --es $(ES_URL)

restart-logstash: ## Restart Logstash to reload pipeline configuration
	$(COMPOSE) restart logstash
	@for i in $$(seq 1 60); do [ "$$(docker inspect -f '{{.State.Health.Status}}' sm-logstash 2>/dev/null)" = "healthy" ] && break; sleep 2; done

demo: up wait init kibana gen ## Full demo: start, configure, generate, verify
	@echo "Waiting for Logstash to ingest the generated logs..."
	@sleep 20
	$(MAKE) verify
	@echo "Kibana: $(KIBANA_URL)  (Discover -> logs-security-*, Dashboard -> Security Overview)"
