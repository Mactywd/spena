"""la scadenza in dispensa

Revision ID: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"


def upgrade() -> None:
    # Nessun CHECK: una data nel passato è legittima (vedi il commento sul modello).
    op.add_column("pantry_items", sa.Column("expires_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("pantry_items", "expires_on")
