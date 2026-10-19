"""developer name comes only from the developers table (drops games.developer)

Revision ID: 0008_developer_from_relation
Revises: 0007_replay_links
Create Date: 2026-10-18 20:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0008_developer_from_relation'
down_revision = '0007_replay_links'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if "developer" not in {c["name"] for c in sa.inspect(conn).get_columns("games")}:
        return
    # Jogos legados só com o nome em texto: liga (ou cria) a desenvolvedora antes de apagar a coluna
    known = {name.casefold(): dev_id for dev_id, name in conn.execute(sa.text("select id, name from developers"))}
    rows = conn.execute(sa.text(
        "select id, developer from games where developer_id is null and trim(coalesce(developer, '')) != ''"
    )).fetchall()
    for game_id, raw_name in rows:
        name = raw_name.strip()
        dev_id = known.get(name.casefold())
        if dev_id is None:
            dev_id = conn.execute(sa.text("insert into developers (name) values (:n)"), {"n": name}).lastrowid
            known[name.casefold()] = dev_id
        conn.execute(sa.text("update games set developer_id = :d where id = :g"), {"d": dev_id, "g": game_id})
    # Coluna sem índice nem restrição: o SQLite (3.35+) remove sem recriar a tabela
    op.execute("ALTER TABLE games DROP COLUMN developer")


def downgrade() -> None:
    op.add_column('games', sa.Column('developer', sa.String(length=150), nullable=True))
    op.execute("update games set developer = (select name from developers where developers.id = games.developer_id)")
