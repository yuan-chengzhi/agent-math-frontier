.PHONY: activation-check activation-write active check experimental render sync

check:
	python3 -m unittest discover -s tests
	python3 scripts/validate.py
	python3 scripts/render.py --check
	python3 scripts/export_active.py --check
	python3 scripts/export_experimental.py --check

render:
	python3 scripts/render.py
	python3 scripts/export_active.py --output data/active-portfolio.json
	python3 scripts/export_experimental.py --output data/experimental-portfolio.json

active:
	python3 scripts/export_active.py --output data/active-portfolio.json

experimental:
	python3 scripts/export_experimental.py --output data/experimental-portfolio.json

activation-check:
	python3 scripts/prepare_activation.py --check

activation-write:
	python3 scripts/prepare_activation.py --write

sync:
	python3 scripts/sync_sources.py
	python3 scripts/render.py
	python3 scripts/validate.py
	python3 scripts/export_active.py --output data/active-portfolio.json
	python3 scripts/export_experimental.py --output data/experimental-portfolio.json
