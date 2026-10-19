"""l'attività da Health Connect via HC Webhook (H2)

Revision ID: 0018
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
# La testa di `master` quando H2 è stato scritto. I piani R5, S4 e H2 partono tutti da
# lì con numeri riservati (0015–0018): al merge questa riga va ripuntata sulla testa di
# `master` di quel momento, e `alembic heads` deve tornare una riga sola.
down_revision = "0012"


def upgrade() -> None:
    # La chiave del webhook: una sola, quindi una riga sola. Se ne tiene l'impronta
    # SHA-256, mai la chiave (app/core/webhook_token.py).
    op.create_table(
        "activity_tokens",
        sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_activity_token_single"),
    )
    # Un totale dei passi per giorno di Roma, con l'intervallo che copre: serve a
    # `merge_steps_day` per decidere se un totale nuovo lo sostituisce. Mai una somma.
    op.create_table(
        "activity_steps_days",
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("steps", sa.Integer, nullable=False),
        sa.Column("covered_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("covered_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("steps >= 0", name="ck_activity_steps_non_negative"),
        sa.CheckConstraint("covered_to > covered_from", name="ck_activity_steps_span"),
    )
    # Un allenamento per app e istante d'inizio: lo stesso, rimandato, aggiorna la sua
    # riga. Due app sullo stesso tempo restano due righe (il tempo in comune è di P2).
    op.create_table(
        "activity_exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("exercise_type", sa.Integer, nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("distance_m", sa.Float, nullable=True),
        sa.Column("steps", sa.Integer, nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source", "started_at", name="uq_activity_exercises_source_started_at"),
        sa.CheckConstraint("ended_at >= started_at", name="ck_activity_exercise_span"),
    )
    op.create_table(
        "activity_weights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("kilograms", sa.Float, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source", "measured_at", name="uq_activity_weights_source_measured_at"),
        sa.CheckConstraint("kilograms > 0", name="ck_activity_weight_positive"),
    )
    # Il registro delle sincronizzazioni: nomi, conteggi e frasi, mai il corpo ricevuto
    # (porterebbe dati di salute che Spena non ha chiesto). Restano le ultime 200 righe.
    op.create_table(
        "activity_syncs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("app_version", sa.String(40), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body_bytes", sa.Integer, nullable=False),
        sa.Column("steps_days", sa.Integer, nullable=False),
        sa.Column("exercises", sa.Integer, nullable=False),
        sa.Column("weights", sa.Integer, nullable=False),
        sa.Column("ignored_keys", postgresql.JSONB, nullable=False),
        sa.Column("problems", postgresql.JSONB, nullable=False),
        sa.CheckConstraint("status IN ('ok', 'test', 'rejected')", name="ck_activity_sync_status"),
    )


def downgrade() -> None:
    # Scendere perde tutto quel che è arrivato da Health Connect, e la chiave: HC Webhook
    # riceverà 401 finché, risaliti, non se ne crea una nuova.
    for table in (
        "activity_syncs",
        "activity_weights",
        "activity_exercises",
        "activity_steps_days",
        "activity_tokens",
    ):
        op.drop_table(table)
