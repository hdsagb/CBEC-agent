"""add llm_config

Revision ID: 9f2c7d1a3b45
Revises: b51dc75a3c2f
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f2c7d1a3b45'
down_revision: Union[str, None] = 'b51dc75a3c2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 全局单行配置：全系统共用一套大模型
    op.create_table(
        'llm_config',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('base_url', sa.String(length=512), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('api_key_cipher', sa.Text(), nullable=False),
        sa.Column('vision_model', sa.String(length=128), nullable=False),
        sa.Column('vision_base_url', sa.String(length=512), nullable=False),
        sa.Column('vision_api_key_cipher', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_status', sa.String(length=32), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=False),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('llm_config')
