# Presidio Analyzer (Hoop custom build)
# -------------------------------------
# Default goal is `help` — run `make` for the target list.

IMAGE          ?= hoophq/presidio-analyzer
VERSION        ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
PLATFORMS      ?= linux/amd64,linux/arm64
BUILDX_BUILDER ?= presidio-builder
PORT           ?= 3000

IMAGE_TAG    := $(IMAGE):$(VERSION)
IMAGE_LATEST := $(IMAGE):latest

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@printf "\nUsage: make <target> [VAR=value ...]\n\nTargets:\n"
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\nVariables (override on the command line):\n"
	@printf "  %-16s %s\n" IMAGE          "$(IMAGE)"
	@printf "  %-16s %s\n" VERSION        "$(VERSION)"
	@printf "  %-16s %s\n" PLATFORMS      "$(PLATFORMS)"
	@printf "  %-16s %s\n" BUILDX_BUILDER "$(BUILDX_BUILDER)"
	@printf "  %-16s %s\n" PORT           "$(PORT) (host port for 'make run')"
	@printf "\n"

# --- Build -----------------------------------------------------------------

.PHONY: build
build: ## Build single-arch (host) image for local dev
	docker build -t $(IMAGE_TAG) -t $(IMAGE_LATEST) .

.PHONY: buildx-setup
buildx-setup: ## One-time: create the multi-arch buildx builder
	@if ! docker buildx inspect $(BUILDX_BUILDER) >/dev/null 2>&1; then \
		echo "creating buildx builder '$(BUILDX_BUILDER)'..."; \
		docker buildx create --name $(BUILDX_BUILDER) --bootstrap --use; \
	else \
		docker buildx use $(BUILDX_BUILDER); \
	fi

.PHONY: buildx
buildx: buildx-setup ## Multi-arch build (kept in buildx cache; not pushed)
	docker buildx build --builder $(BUILDX_BUILDER) \
		--platform $(PLATFORMS) \
		-t $(IMAGE_TAG) -t $(IMAGE_LATEST) .

.PHONY: release
release: buildx-setup ## Multi-arch build AND push to the registry
	@case "$(VERSION)" in \
	  dev|*dirty*) echo "refusing to release '$(VERSION)': commit and tag first"; exit 1;; \
	esac
	docker buildx build --builder $(BUILDX_BUILDER) \
		--platform $(PLATFORMS) \
		-t $(IMAGE_TAG) -t $(IMAGE_LATEST) \
		--push .

# --- Test ------------------------------------------------------------------

.PHONY: test
test: ## Run unit tests locally (needs: pip install presidio-analyzer pytest)
	uv run --with presidio-analyzer --with pytest pytest -v tests/

.PHONY: test-image
test-image: build ## Run unit tests inside the built image (validates runtime layout)
	docker run --rm \
		--user 0 \
		--entrypoint /bin/sh \
		-v $(CURDIR)/tests:/tmp/tests:ro \
		$(IMAGE_TAG) -c '\
			pip install --quiet --break-system-packages pytest >/dev/null 2>&1 || \
			pip install --quiet pytest >/dev/null 2>&1; \
			cd /tmp/tests && python -m pytest -v .'

# --- Run / smoke -----------------------------------------------------------

.PHONY: run
run: build ## Run the analyzer locally on :$(PORT) (foreground, Ctrl-C to stop)
	docker run --rm -it -p $(PORT):3000 --name presidio-analyzer-local $(IMAGE_TAG)

.PHONY: run-detached
run-detached: build ## Run the analyzer in the background; pair with 'make stop'
	docker run -d --rm -p $(PORT):3000 --name presidio-analyzer-local $(IMAGE_TAG)
	@echo "waiting for /supportedentities..."
	@for i in $$(seq 1 60); do \
	  curl -fsS -o /dev/null http://localhost:$(PORT)/supportedentities 2>/dev/null && break; \
	  sleep 1; \
	done
	@echo "ready: http://localhost:$(PORT)"

.PHONY: stop
stop: ## Stop the locally-running analyzer started by 'make run-detached'
	-docker stop presidio-analyzer-local 2>/dev/null

.PHONY: smoke
smoke: ## Hit the running analyzer at :$(PORT) with the test script
	@ANALYZER_URL=http://localhost:$(PORT) ./scripts/analyzer-test.sh "Meu CPF é 111.444.777-35"

.PHONY: e2e
e2e: build ## End-to-end: build, start container, smoke-test, tear down
	@./scripts/e2e.sh $(IMAGE_TAG) $(PORT)

# --- Maintenance -----------------------------------------------------------

.PHONY: shell
shell: build ## Open an interactive bash inside the built image (as root)
	docker run --rm -it --user 0 --entrypoint /bin/bash $(IMAGE_TAG)

.PHONY: clean
clean: ## Remove local image tags and the buildx builder
	-docker rmi $(IMAGE_TAG) $(IMAGE_LATEST) 2>/dev/null
	-docker buildx rm $(BUILDX_BUILDER) 2>/dev/null

.PHONY: version
version: ## Print the resolved VERSION
	@echo $(VERSION)
