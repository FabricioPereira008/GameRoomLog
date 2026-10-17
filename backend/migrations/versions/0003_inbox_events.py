"""inbox events from the portable app

Revision ID: 0003_inbox_events
Revises: 0002_store_links
Create Date: 2026-10-17 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0003_inbox_events'
down_revision = '0002_store_links'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('inbox_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.String(length=64), nullable=False),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('platform', sa.String(length=100), nullable=True),
    sa.Column('game_id', sa.Integer(), nullable=True),
    sa.Column('event_date', sa.Date(), nullable=False),
    sa.Column('device_created_at', sa.DateTime(), nullable=True),
    sa.Column('played_hours', sa.Float(), nullable=True),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('difficulty', sa.Float(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('applied_game_id', sa.Integer(), nullable=True),
    sa.Column('received_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('inbox_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inbox_events_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_inbox_events_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_inbox_events_uuid'), ['uuid'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('inbox_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_inbox_events_uuid'))
        batch_op.drop_index(batch_op.f('ix_inbox_events_status'))
        batch_op.drop_index(batch_op.f('ix_inbox_events_id'))
    op.drop_table('inbox_events')
