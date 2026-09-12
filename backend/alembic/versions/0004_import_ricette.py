"""import ricette: pagine scaricate, dizionario dei termini, colonne nuove

Revision ID: 0004
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.add_column("recipes", sa.Column("image_url", sa.String(500)))
    op.add_column("recipes", sa.Column("prep_minutes", sa.Integer))
    op.add_column("recipes", sa.Column("cook_minutes", sa.Integer))
    op.add_column("recipes", sa.Column("category", sa.String(60)))
    op.create_index("ix_recipes_category", "recipes", ["category"])

    op.create_table(
        "recipe_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("skipped_reason", sa.String(200)),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recipes.id", ondelete="SET NULL")),
        sa.UniqueConstraint("source", "url"),
        sa.CheckConstraint("state IN ('pending', 'imported', 'skipped')",
                           name="ck_recipe_import_state"),
    )
    op.create_index("ix_recipe_imports_state", "recipe_imports", ["state"])

    op.create_table(
        "import_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("term_key", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("occurrences", sa.Integer, nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="RESTRICT")),
        sa.Column("role_override", sa.String(20)),
        sa.Column("decided_by", sa.String(20)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source", "term_key"),
        sa.CheckConstraint("decision IN ('pending', 'mapped', 'ignored')",
                           name="ck_import_term_decision"),
        sa.CheckConstraint("role_override IS NULL OR role_override IN ('primary', 'secondary')",
                           name="ck_import_term_role"),
        sa.CheckConstraint("decision <> 'mapped' OR ingredient_id IS NOT NULL",
                           name="ck_import_term_mapped_has_ingredient"),
    )
    op.create_index("ix_import_terms_queue", "import_terms", ["decision", "occurrences"])


def downgrade() -> None:
    op.drop_table("import_terms")
    op.drop_table("recipe_imports")
    op.drop_index("ix_recipes_category", table_name="recipes")
    for colonna in ("category", "cook_minutes", "prep_minutes", "image_url"):
        op.drop_column("recipes", colonna)
