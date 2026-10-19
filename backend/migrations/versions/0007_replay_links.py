"""link replays to the original game record

Revision ID: 0007_replay_links
Revises: 0006_yearbook_picks
Create Date: 2026-10-18 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0007_replay_links'
down_revision = '0006_yearbook_picks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN simples (sem recriar a tabela): recriar `games` com as FKs ligadas apagaria em
    # cascata gêneros, vínculos de loja e pódios. O SQLite aceita REFERENCES em ADD COLUMN.
    # (o Alembic só cria FK no SQLite via batch, daí o SQL direto)
    op.execute("ALTER TABLE games ADD COLUMN replay_of_id INTEGER REFERENCES games (id) ON DELETE SET NULL")
    op.create_index('ix_games_replay_of_id', 'games', ['replay_of_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_games_replay_of_id', table_name='games')
    with op.batch_alter_table('games', schema=None) as batch_op:  # a FK some junto com a coluna
        batch_op.drop_column('replay_of_id')
