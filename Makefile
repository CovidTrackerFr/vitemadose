
.DEFAULT_GOAL := help

URL =

.PHONY: help test install
help: ## provides cli help for this makefile (default) 📖
	@grep -E '^[a-zA-Z_0-9-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## sets up package and its dependencies
	scripts/install

test: ## runs tests
	scripts/test

coverage: ## reports test coverage (automatically run by `test`)
	scripts/coverage

scrape: ## runs the full scraping experience
	scripts/scrape $(URL)

stats: ## Run the statistic scripts
	venv/bin/python -m stats_generation.stats_available_centers
	venv/bin/python -m stats_generation.chronodoses
	venv/bin/python -m stats_generation.by_vaccine

doctoscrap: ## Scrap all doctolib centers, output : data/output/doctolib-centers.json
	venv/bin/python -m scraper.doctolib.doctolib_center_scrap

keldocscrap: ## Scrap all doctolib centers, output : data/output/keldoc-centers.json
	venv/bin/python -m scraper.keldoc.keldoc_center_scrap

maiiascrap: ## Retrieve maiia centers from API
	venv/bin/python -m scraper.maiia.maiia_center_scrap
