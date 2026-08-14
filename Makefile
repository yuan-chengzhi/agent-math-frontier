.PHONY: check render sync

check:
	python3 -m unittest discover -s tests
	python3 scripts/validate.py
	python3 scripts/render.py --check

render:
	python3 scripts/render.py

sync:
	python3 scripts/sync_sources.py
	python3 scripts/render.py
	python3 scripts/validate.py
