# Every common operation as a single verb. Reproducible from a clean machine.
.PHONY: up down build test lint smoke logs clean

up:            ## run the full stack locally
	docker compose up --build -d

down:          ## stop the stack
	docker compose down

build:         ## build all images
	docker compose build

test:          ## run unit tests in a container (source mounted; HOME writable for pip --user)
	docker compose run --rm --entrypoint sh -e HOME=/tmp \
		-v "$(CURDIR)/apps/api:/app" api -c \
		"pip install --user -q pytest httpx && python -m pytest tests -q"

lint:          ## run pre-commit hooks against all files
	pre-commit run --all-files

smoke:         ## hit the health endpoints of a running stack
	curl -fsS http://localhost:8000/health/live
	curl -fsS http://localhost:8000/health/ready
	curl -fsS http://localhost:8001/health/live
	curl -fsS -X POST http://localhost:8001/v1/classify \
		-H 'x-api-key: dev-local-key' -H 'content-type: application/json' \
		-d '{"venue_id": "smoke-test", "description": "late night drinks with groups"}'

logs:          ## tail all service logs
	docker compose logs -f

clean:         ## remove containers, volumes and dangling images
	docker compose down -v --remove-orphans
