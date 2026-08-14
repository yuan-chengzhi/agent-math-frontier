.PHONY: activation-check activation-write active check render sync

check:
	python3 -m unittest discover -s tests
	python3 scripts/validate.py
	python3 scripts/render.py --check
	python3 scripts/export_active.py --check

render:
	python3 scripts/render.py
	python3 scripts/export_active.py --output data/active-portfolio.json

active:
	python3 scripts/export_active.py --output data/active-portfolio.json

activation-check:
	python3 scripts/prepare_activation.py --check

activation-write:
	python3 scripts/prepare_activation.py --write

sync:
	python3 scripts/sync_sources.py
	python3 scripts/render.py
	python3 scripts/validate.py
	python3 scripts/export_active.py --output data/active-portfolio.json
