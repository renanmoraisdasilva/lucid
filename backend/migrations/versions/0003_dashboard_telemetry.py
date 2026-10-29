"""dashboard telemetry fields

Revision ID: 0003_dashboard_telemetry
Revises: 0002_chat_schema
Create Date: 2026-10-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_dashboard_telemetry"
down_revision: str | None = "0002_chat_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_attempts",
        sa.Column("first_token_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_attempts",
        sa.Column("http_status", sa.Integer(), nullable=True),
    )
    op.add_column(
        "generation_attempts",
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "generation_attempts",
        sa.Column("context_tokens", sa.Integer(), nullable=True),
    )

    op.create_check_constraint(
        "ck_attempts_http_status",
        "generation_attempts",
        "http_status IS NULL OR http_status BETWEEN 100 AND 599",
    )
    op.create_check_constraint(
        "ck_attempts_retry_count",
        "generation_attempts",
        "retry_count >= 0",
    )
    op.create_check_constraint(
        "ck_attempts_context_tokens",
        "generation_attempts",
        "context_tokens IS NULL OR context_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_attempts_first_token_after_start",
        "generation_attempts",
        "first_token_at IS NULL OR first_token_at >= started_at",
    )

    op.create_index("ix_attempts_started_at", "generation_attempts", ["started_at"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_attempts_started_at", table_name="generation_attempts")

    op.drop_constraint("ck_attempts_first_token_after_start", "generation_attempts", type_="check")
    op.drop_constraint("ck_attempts_context_tokens", "generation_attempts", type_="check")
    op.drop_constraint("ck_attempts_retry_count", "generation_attempts", type_="check")
    op.drop_constraint("ck_attempts_http_status", "generation_attempts", type_="check")

    op.drop_column("generation_attempts", "context_tokens")
    op.drop_column("generation_attempts", "retry_count")
    op.drop_column("generation_attempts", "http_status")
    op.drop_column("generation_attempts", "first_token_at")
