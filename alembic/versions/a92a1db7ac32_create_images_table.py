"""create images table

Revision ID: a92a1db7ac32
Revises:
Create Date: 2026-10-01 23:03:51.428646

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a92a1db7ac32'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('image',
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=127), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('pending_upload', 'uploading', 'uploaded', 'queued', 'processing', 'failed', 'finished', name='processingstatus'), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('blob_key', sa.String(), nullable=True),
    sa.Column('upload_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_image_blob_key'), 'image', ['blob_key'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_image_blob_key'), table_name='image')
    op.drop_table('image')
