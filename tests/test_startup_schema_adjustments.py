"""Tests for lightweight startup schema adjustments."""

from sqlalchemy import create_engine, inspect, text

from app.main import _ensure_capsule_learning_plan_column


def test_ensure_capsule_learning_plan_column_adds_missing_column():
    engine = create_engine("sqlite:///:memory:", future=True)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE capsules (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    domain VARCHAR(100) NOT NULL,
                    area VARCHAR(100) NOT NULL,
                    main_skill VARCHAR(100) NOT NULL,
                    creator_id INTEGER,
                    is_public BOOLEAN NOT NULL DEFAULT 1,
                    generation_status VARCHAR(50) NOT NULL
                )
                """
            )
        )

        # Initial call should add the missing column without raising.
        _ensure_capsule_learning_plan_column(connection)

        inspector = inspect(connection)
        column_names = {column["name"] for column in inspector.get_columns("capsules")}
        assert "learning_plan_json" in column_names

        # Calling the helper again should be a no-op.
        _ensure_capsule_learning_plan_column(connection)

    engine.dispose()
