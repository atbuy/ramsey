.PHONY: lock dep-update upgrade install install-dev install-all run

.DEFAULT_GOAL := run

lock:
	uv lock

dep-update:
	uv lock --upgrade-package $(pkg)

upgrade:
	pip install --upgrade pip setuptools

install: upgrade
	uv sync --frozen --no-dev

install-dev: upgrade
	uv sync --frozen --extra dev
	prek install --overwrite

install-all: upgrade install-dev

run:
	uvicorn ramsey.app:app --reload
