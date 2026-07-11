upgrade:
	pip install --upgrade pip setuptools

install: upgrade
	uv sync --frozen --no-dev

install-dev: upgrade
	uv sync --frozen --extra dev
	pre-commit install

install-all: upgrade install-dev

run:
	uvicorn ramsey.app:app --reload
