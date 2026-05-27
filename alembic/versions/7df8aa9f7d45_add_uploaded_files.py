"""add uploaded files

Revision ID: 7df8aa9f7d45
Revises: bcba90111f67
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7df8aa9f7d45"
down_revision: Union[str, Sequence[str], None] = "bcba90111f67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_uploaded_files_id"), "uploaded_files", ["id"], unique=False)
    op.create_index(op.f("ix_uploaded_files_owner_id"), "uploaded_files", ["owner_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_uploaded_files_owner_id"), table_name="uploaded_files")
    op.drop_index(op.f("ix_uploaded_files_id"), table_name="uploaded_files")
    op.drop_table("uploaded_files")
