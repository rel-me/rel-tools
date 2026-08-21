NPM ?= npm
DOCS_HOST ?= 127.0.0.1
DOCS_PORT ?= 4321
DOCS_NPM := $(NPM) --prefix docs
DOCS_INSTALL_STAMP := docs/node_modules/.package-lock.json

.PHONY: docs-dev

docs-dev: $(DOCS_INSTALL_STAMP)
	$(DOCS_NPM) run dev -- --host "$(DOCS_HOST)" --port "$(DOCS_PORT)"

$(DOCS_INSTALL_STAMP): docs/package.json docs/package-lock.json
	$(DOCS_NPM) ci
