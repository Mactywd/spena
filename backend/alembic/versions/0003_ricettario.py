"""ricettario: ricette, ingredienti di ricetta, eventi di cottura

Revision ID: 0003
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("instructions", sa.Text, nullable=False),
        sa.Column("servings", sa.Integer),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_ref", sa.String(500)),
        sa.Column("embedding", Vector(EMBEDDING_DIM)),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR,
            sa.Computed(
                "to_tsvector('italian', coalesce(title, '') || ' ' || coalesce(description, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint("source IN ('dataset', 'manual', 'ai')", name="ck_recipe_source"),
    )
    op.execute("CREATE INDEX ix_recipes_tsv ON recipes USING gin (search_tsv)")
    op.execute(
        "CREATE INDEX ix_recipes_embedding ON recipes "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "recipe_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("quantity_text", sa.String(100)),
        sa.Column("note", sa.String(300)),
        sa.UniqueConstraint("recipe_id", "ingredient_id"),
        sa.CheckConstraint("role IN ('primary', 'secondary')", name="ck_recipe_ingredient_role"),
    )
    op.create_index("ix_recipe_ingredients_ingredient", "recipe_ingredients", ["ingredient_id"])

    op.create_table(
        "cooking_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recipes.id", ondelete="SET NULL")),
        sa.Column("cooked_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("servings", sa.Integer),
        sa.Column("snapshot", postgresql.JSONB, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cooking_events")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipes")
