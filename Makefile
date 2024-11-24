upgrade:
	pip install --upgrade pip setuptools wheel

install: upgrade
	pip install -e .

install-dev: upgrade
	pip install -e '.[dev]'
	pre-commit install

install-all: upgrade install-dev

run:
	uvicorn ramsey.app:app --reload
