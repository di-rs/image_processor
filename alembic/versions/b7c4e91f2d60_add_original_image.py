"""Add source image reference.

Revision ID: b7c4e91f2d60
Revises: a92a1db7ac32
"""

from alembic import op
import sqlalchemy as sa

revision: str = "b7c4e91f2d60"
down_revision: str | None = "a92a1db7ac32"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("image", sa.Column("original_image", sa.Integer(), nullable=True))
    op.create_index("ix_image_original_image", "image", ["original_image"])
    op.create_foreign_key(
        "fk_image_original_image",
        "image",
        "image",
        ["original_image"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_image_original_image", "image", type_="foreignkey")
    op.drop_index("ix_image_original_image", table_name="image")
    op.drop_column("image", "original_image")
