.PHONY: install dev test lint docker-up docker-down

install:
	pip install -e .

dev:
	python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	python -m pytest -v

lint:
	ruff check src/

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
