"""Shared authentication security state

Revision ID: 0006_auth_security_state
Revises: 0005_accounting_integrity
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0006_auth_security_state'
down_revision = '0005_accounting_integrity'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _indexes(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {item.get('name') for item in inspect(op.get_bind()).get_indexes(table)}


def _index(name: str, table: str, columns: list[str], *, unique: bool = False):
    if _has_table(table) and name not in _indexes(table):
        op.create_index(name, table, columns, unique=unique)


def upgrade():
    if not _has_table('auth_login_failures'):
        op.create_table(
            'auth_login_failures',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('key_hash', sa.String(length=64), nullable=False),
            sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    _index('ix_auth_login_failures_key_hash', 'auth_login_failures', ['key_hash'])
    _index('ix_auth_login_failures_attempted_at', 'auth_login_failures', ['attempted_at'])

    if not _has_table('revoked_access_tokens'):
        op.create_table(
            'revoked_access_tokens',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('subject', sa.String(length=100), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    _index('ix_revoked_access_tokens_token_hash', 'revoked_access_tokens', ['token_hash'], unique=True)
    _index('ix_revoked_access_tokens_subject', 'revoked_access_tokens', ['subject'])
    _index('ix_revoked_access_tokens_expires_at', 'revoked_access_tokens', ['expires_at'])
    _index('ix_revoked_access_tokens_revoked_at', 'revoked_access_tokens', ['revoked_at'])


def downgrade():
    if _has_table('revoked_access_tokens'):
        op.drop_table('revoked_access_tokens')
    if _has_table('auth_login_failures'):
        op.drop_table('auth_login_failures')
