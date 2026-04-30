.PHONY: help up build down logs test format

help:
	@echo "Available commands:"
	@echo "  make up      - Start all services (Docker)"
	@echo "  make build   - Build and start all services (Docker)"
	@echo "  make down    - Stop all services (Docker)"
	@echo "  make logs    - View logs of all services"
	@echo "  make test    - Run Python unit tests"

up:
	docker-compose up -d

build:
	docker-compose up --build -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	cd python && python test_anomaly_detector.py
