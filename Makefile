db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	alembic upgrade head

run:
	python -m uvicorn app.main:app --reload

test:
	pytest -m "not postgres"

test-pg:
	pytest -m "postgres"

era-validate:
	python scripts/era_validate.py --file "$(FILE)" --base-url "$(BASE_URL)" $(if $(TOKEN),--token "$(TOKEN)")
