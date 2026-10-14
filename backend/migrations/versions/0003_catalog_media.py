"""Catalog media + category: cuisine/image on restaurants, category/image on items.

Additive and backward compatible: existing rows keep working (empty defaults),
ids and relationships are untouched.
"""

revision = "0003_catalog_media"
down_revision = "0002_outbox_attempt"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column("cuisine", sa.String(64), nullable=False, server_default=""),
    )
    op.add_column(
        "restaurants",
        sa.Column("image_url", sa.String(512), nullable=False, server_default=""),
    )
    op.add_column(
        "menu_items",
        sa.Column("category", sa.String(32), nullable=False, server_default=""),
    )
    op.add_column(
        "menu_items",
        sa.Column("image_url", sa.String(512), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("menu_items", "image_url")
    op.drop_column("menu_items", "category")
    op.drop_column("restaurants", "image_url")
    op.drop_column("restaurants", "cuisine")
