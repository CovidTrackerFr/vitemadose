
.DEFAULT_GOAL := help

URL =

.PHONY: help test install
help: ## provides cli help for this makefile (default) 📖
	@grep -E '^[a-zA-Z_0-9-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## sets up package and its dependencies
	scripts/install

test: ## sets up package and its dependencies
	scripts/test

coverage: ## reports test coverage (automatically run by `test`)
	scripts/coverage

scrape: ## runs the full scraping experience
	scripts/scrape $(URL)

stats: ## Run the statistiques scripts
	venv/bin/python -m stats_generation.generate_center_stats
