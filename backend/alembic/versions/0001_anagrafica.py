"""anagrafica: ingredienti, alias, prodotti

Revision ID: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("composition_ref", sa.String(60)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ingredient_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(120), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.UniqueConstraint("ingredient_id", "alias"),
    )
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("brand", sa.String(120)),
        sa.Column("barcode", sa.String(20), unique=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_payload", postgresql.JSONB),
        sa.Column("nutrients", postgresql.JSONB),
        sa.Column("image_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # autocomplete tollerante agli errori di battitura
    op.execute("CREATE INDEX ix_ingredients_name_trgm ON ingredients USING gin (name gin_trgm_ops)")
    op.execute("CREATE INDEX ix_aliases_alias_trgm ON ingredient_aliases USING gin (alias gin_trgm_ops)")
    op.execute("CREATE INDEX ix_products_name_trgm ON products USING gin (name gin_trgm_ops)")
    op.create_index("ix_products_ingredient_id", "products", ["ingredient_id"])


def downgrade() -> None:
    op.drop_table("products")
    op.drop_table("ingredient_aliases")
    op.drop_table("ingredients")
