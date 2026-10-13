"""Outbox attempt column: retries carry attempt N+1 in their identity."""

revision = "0002_outbox_attempt"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
    )
    op.drop_constraint(
        "outbox_events_event_id_exchange_routing_key_key",
        "outbox_events",
        type_="unique",
    )
    op.create_unique_constraint(
        "outbox_events_event_pub_key",
        "outbox_events",
        ["event_id", "exchange", "routing_key", "attempt"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "outbox_events_event_pub_key", "outbox_events", type_="unique"
    )
    op.create_unique_constraint(
        "outbox_events_event_id_exchange_routing_key_key",
        "outbox_events",
        ["event_id", "exchange", "routing_key"],
    )
    op.drop_column("outbox_events", "attempt")
