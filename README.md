# Burbot

## Sources / Acquisition — Layer 2

The root API serves Layer 2 at `/sources`, using the same database as the business
layer. It includes source/file registration, metadata, schedules, warnings, and
versioned tracking of concrete business object fields. Clients manage these bindings
directly; entity-field tracking and source/object links are internal and automatic.
Changes append SCD Type 2 snapshots, with history and optimistic version checks.
`SourcesService` uses `AsyncSession` directly. See [Sources service](docs/sources.md)
for the contract, API, Layer 3 observation boundary and verification commands.

## Database migrations

Copy the example environment file and start PostgreSQL:

```bash
cp .env.example .env
docker compose up -d db
```

Install dependencies and generate revisions with Alembic from the registered models:

```bash
python -m pip install -e '.[dev]'
mkdir -p migrations/versions
python -m alembic revision --autogenerate --version-path migrations/versions -m "describe the schema change"
```

Review the generated revision and then apply it:

```bash
python -m alembic upgrade head
```

Useful inspection and rollback commands:

```bash
python -m alembic current
python -m alembic history
python -m alembic check
python -m alembic downgrade -1
```

The Sources implementation supplies ORM models and model registration; it does not
include a handwritten Alembic revision or change the database on application startup.
