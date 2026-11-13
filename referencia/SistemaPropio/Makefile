# Atajos para desarrollo local sin Docker (requiere PostgreSQL en marcha y apps/api/.env)
.PHONY: api-install migrate seed api web-install web test cobertura
api-install: ; cd apps/api && pip install -e ".[dev]"
migrate:     ; cd apps/api && alembic upgrade head
seed:        ; cd apps/api && python -m app.seed
api:         ; cd apps/api && uvicorn app.main:app --reload --port 8000
web-install: ; cd apps/web && npm install
web:         ; cd apps/web && npm run dev
test:        ; cd apps/api && pytest -v && cd ../web && npm test && npm run lint
cobertura:   ; python scripts/build_coverage.py
