"""store links and ignored store games

Revision ID: 0002_store_links
Revises: 0001_baseline
Create Date: 2026-10-16 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0002_store_links'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('game_store_links',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('game_id', sa.Integer(), nullable=False),
    sa.Column('store', sa.String(length=30), nullable=False),
    sa.Column('external_id', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('store', 'external_id', name='uq_store_link_store_external')
    )
    with op.batch_alter_table('game_store_links', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_game_store_links_game_id'), ['game_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_game_store_links_id'), ['id'], unique=False)

    op.create_table('ignored_store_games',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('store', sa.String(length=30), nullable=False),
    sa.Column('external_id', sa.String(length=100), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('store', 'external_id', name='uq_ignored_store_external')
    )
    with op.batch_alter_table('ignored_store_games', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ignored_store_games_id'), ['id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('ignored_store_games', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ignored_store_games_id'))
    op.drop_table('ignored_store_games')
    with op.batch_alter_table('game_store_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_game_store_links_id'))
        batch_op.drop_index(batch_op.f('ix_game_store_links_game_id'))
    op.drop_table('game_store_links')
