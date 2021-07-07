
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
	venv/bin/python -m scraper.centerscraper.doctolib_center_scrap

keldocscrap: ## Scrap all doctolib centers, output : data/output/keldoc-centers.json
	venv/bin/python -m scraper.centerscraper.keldoc_center_scrap

maiiascrap: ## Retrieve maiia centers from API
	venv/bin/python -m scraper.centerscraper.maiia_center_scrap

mesoignerscrap: ## Scrap all mesoigner centers, output : data/output/mesoigner_centers.json
	venv/bin/python -m scraper.centerscraper.mesoigner_center_scrap

blocklistmanager: ## Blocklist command line manager
	venv/bin/python -m management_scripts.manage_blocklist

lint: install
	venv/bin/pip install black
	venv/bin/black $$(git ls-files | grep .py$$)

lint-check: install
	venv/bin/pip install black
	venv/bin/black --check $$(git ls-files | grep .py$$)

contributors: install
	scripts/contributors

clean:
	rm -rf data/output
	git checkout data/output
