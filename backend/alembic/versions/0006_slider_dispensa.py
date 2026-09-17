"""la posizione del cursore accanto allo stato, in dispensa

Revision ID: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    # annullabile perché le voci già in dispensa non hanno mai visto un cursore, e
    # un valore di comodo sarebbe una misura inventata. SmallInteger: sono 0–100
    op.add_column("pantry_items", sa.Column("fill_percent", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "ck_pantry_fill_percent", "pantry_items", "fill_percent BETWEEN 0 AND 100"
    )


def downgrade() -> None:
    op.drop_constraint("ck_pantry_fill_percent", "pantry_items", type_="check")
    op.drop_column("pantry_items", "fill_percent")
