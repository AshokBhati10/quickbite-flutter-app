"""Initial schema: all assignment tables with unique constraints."""

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "restaurants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "menu_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("restaurant_id", sa.String(64), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("price_minor", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "drivers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("customer_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("restaurant_id", sa.String(64), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("delivery_address", sa.String(500), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("total_minor", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("driver_id", sa.String(64), sa.ForeignKey("drivers.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "order_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("menu_item_id", sa.String(64), sa.ForeignKey("menu_items.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit_price_minor", sa.Integer, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
    )
    op.create_table(
        "order_status_history",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("order_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("order_id", "order_version"),
    )
    op.create_table(
        "simulated_payments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("orders.id"), nullable=False, unique=True),
        sa.Column("idempotency_id", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "driver_assignments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("orders.id"), nullable=False, unique=True),
        sa.Column("driver_id", sa.String(64), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("customer_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("orders.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("customer_id", "event_id"),
    )
    op.create_table(
        "processed_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("consumer_name", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("order_id", sa.String(64), nullable=True),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("consumer_name", "event_id"),
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(128), nullable=False, index=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("exchange", sa.String(128), nullable=False),
        sa.Column("routing_key", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "exchange", "routing_key"),
    )
    op.create_table(
        "retry_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("consumer_name", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("consumer_name", "event_id", "attempt"),
    )
    op.create_table(
        "quarantine_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(128), nullable=False, index=True),
        sa.Column("consumer_name", sa.String(64), nullable=False),
        sa.Column("source_queue", sa.String(128), nullable=False),
        sa.Column("event_payload", sa.JSON, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(128), nullable=False),
        sa.Column("response_body", sa.JSON, nullable=False),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "key"),
    )


def downgrade() -> None:
    for table in (
        "idempotency_keys",
        "quarantine_records",
        "retry_jobs",
        "outbox_events",
        "processed_events",
        "notifications",
        "driver_assignments",
        "simulated_payments",
        "order_status_history",
        "order_items",
        "orders",
        "drivers",
        "menu_items",
        "restaurants",
        "users",
    ):
        op.drop_table(table)
