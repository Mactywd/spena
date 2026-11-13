"""la pianificazione: proposte di pasti, schede dei cambi, posto di partenza, ricetta chiesta

Revision ID: 0022
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"

STATI = "('available', 'low', 'finished')"


def _uuid_fk(nome: str, target: str, ondelete: str, nullable: bool = True) -> sa.Column:
    return sa.Column(
        nome,
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
    )


def upgrade() -> None:
    op.add_column("conversations", sa.Column("focus_day", sa.Date(), nullable=True))
    op.add_column("conversations", sa.Column("focus_slot", sa.String(10), nullable=True))
    op.create_check_constraint(
        "ck_conversation_focus",
        "conversations",
        "(focus_day IS NULL) = (focus_slot IS NULL) "
        "AND (focus_slot IS NULL OR focus_slot IN ('lunch', 'dinner'))",
    )
    op.add_column("meals", sa.Column("recipe_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("meals", sa.Column("recipe_notice", sa.Text(), nullable=True))

    op.create_table(
        "meal_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("conversation_id", "conversations.id", "CASCADE", nullable=False),
        _uuid_fk("turn_message_id", "conversation_messages.id", "SET NULL"),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), server_default="open", nullable=False),
        sa.Column("rows", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('official', 'draft')", name="ck_proposal_kind"),
        sa.CheckConstraint(
            "status IN ('open', 'placed', 'superseded')", name="ck_proposal_status"
        ),
    )
    op.create_index(
        "ix_meal_proposals_conversation_created",
        "meal_proposals",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "change_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), server_default="proposed", nullable=False),
        sa.Column("list_only", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("meal_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        _uuid_fk("conversation_id", "conversations.id", "SET NULL"),
        _uuid_fk("turn_message_id", "conversation_messages.id", "SET NULL"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('forward', 'inverse')", name="ck_card_kind"),
        sa.CheckConstraint(
            "status IN ('proposed', 'applied', 'discarded')", name="ck_card_status"
        ),
    )
    op.create_index("ix_change_cards_status", "change_cards", ["status"])

    op.create_table(
        "change_card_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _uuid_fk("card_id", "change_cards.id", "CASCADE", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        _uuid_fk("pantry_item_id", "pantry_items.id", "SET NULL"),
        _uuid_fk("ingredient_id", "ingredients.id", "SET NULL"),
        _uuid_fk("shopping_item_id", "shopping_list_items.id", "SET NULL"),
        sa.Column("to_status", sa.String(10), nullable=True),
        sa.Column("before_status", sa.String(10), nullable=True),
        sa.Column("checked", sa.Boolean(), nullable=False),
        sa.Column("editable", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("meal_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("applied", sa.Boolean(), nullable=True),
        sa.Column("list_added", sa.Boolean(), nullable=True),
        _uuid_fk("source_row_id", "change_card_rows.id", "SET NULL"),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('pantry', 'list', 'unlist')", name="ck_card_row_kind"),
        sa.CheckConstraint(
            f"(to_status IS NULL OR to_status IN {STATI}) "
            f"AND (before_status IS NULL OR before_status IN {STATI})",
            name="ck_card_row_status",
        ),
        sa.CheckConstraint(
            "kind <> 'pantry' OR to_status IS NOT NULL", name="ck_card_row_pantry_has_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("change_card_rows")
    op.drop_table("change_cards")
    op.drop_table("meal_proposals")
    op.drop_column("meals", "recipe_notice")
    op.drop_column("meals", "recipe_requested_at")
    op.drop_constraint("ck_conversation_focus", "conversations", type_="check")
    op.drop_column("conversations", "focus_slot")
    op.drop_column("conversations", "focus_day")
