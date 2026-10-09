"""init schema

Revision ID: b51dc75a3c2f
Revises:
Create Date: 2026-10-09 17:49:43.280478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b51dc75a3c2f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('asset',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('type', sa.String(length=16), nullable=False),
    sa.Column('file_url', sa.String(length=512), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('declaration_element',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('hs_code', sa.String(length=32), nullable=False),
    sa.Column('product_name', sa.String(length=255), nullable=False),
    sa.Column('name_en', sa.String(length=255), nullable=False),
    sa.Column('customer_name', sa.String(length=128), nullable=False),
    sa.Column('brand', sa.String(length=128), nullable=False),
    sa.Column('model', sa.String(length=128), nullable=False),
    sa.Column('spec', sa.String(length=255), nullable=False),
    sa.Column('material', sa.String(length=255), nullable=False),
    sa.Column('usage', sa.String(length=255), nullable=False),
    sa.Column('elements_json', sa.Text(), nullable=False),
    sa.Column('source_file_url', sa.String(length=512), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_declaration_element_customer_name'), 'declaration_element', ['customer_name'], unique=False)
    op.create_index(op.f('ix_declaration_element_hs_code'), 'declaration_element', ['hs_code'], unique=False)
    op.create_index(op.f('ix_declaration_element_product_name'), 'declaration_element', ['product_name'], unique=False)
    op.create_table('user',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=128), nullable=False),
    sa.Column('display_name', sa.String(length=64), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)
    op.create_table('chat_session',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_session_user_id'), 'chat_session', ['user_id'], unique=False)
    op.create_table('mark_template',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('layout_json', sa.Text(), nullable=False),
    sa.Column('thumbnail_url', sa.String(length=512), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('quote_batch',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('uploader_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['uploader_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('chat_message',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('tool_calls_json', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['chat_session.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_message_session_id'), 'chat_message', ['session_id'], unique=False)
    op.create_table('comparison',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('weight_config_json', sa.Text(), nullable=False),
    sa.Column('result_json', sa.Text(), nullable=False),
    sa.Column('recommended_source_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['quote_batch.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comparison_batch_id'), 'comparison', ['batch_id'], unique=False)
    op.create_table('mark_job',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('template_id', sa.Integer(), nullable=False),
    sa.Column('order_no', sa.String(length=64), nullable=False),
    sa.Column('total_boxes', sa.Integer(), nullable=False),
    sa.Column('start_no', sa.Integer(), nullable=False),
    sa.Column('fields_json', sa.Text(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['template_id'], ['mark_template.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('quote_source',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('file_type', sa.String(length=16), nullable=False),
    sa.Column('raw_file_url', sa.String(length=512), nullable=False),
    sa.Column('parse_status', sa.String(length=32), nullable=False),
    sa.Column('supplier_name', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['quote_batch.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quote_source_batch_id'), 'quote_source', ['batch_id'], unique=False)
    op.create_table('quote_item',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('product_name', sa.String(length=255), nullable=False),
    sa.Column('spec', sa.String(length=255), nullable=False),
    sa.Column('unit_price', sa.Float(), nullable=True),
    sa.Column('currency', sa.String(length=8), nullable=False),
    sa.Column('moq', sa.Integer(), nullable=True),
    sa.Column('lead_time_days', sa.Integer(), nullable=True),
    sa.Column('valid_until', sa.String(length=32), nullable=False),
    sa.Column('remarks', sa.String(length=512), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('confirmed', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['quote_source.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quote_item_source_id'), 'quote_item', ['source_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_quote_item_source_id'), table_name='quote_item')
    op.drop_table('quote_item')
    op.drop_index(op.f('ix_quote_source_batch_id'), table_name='quote_source')
    op.drop_table('quote_source')
    op.drop_table('mark_job')
    op.drop_index(op.f('ix_comparison_batch_id'), table_name='comparison')
    op.drop_table('comparison')
    op.drop_index(op.f('ix_chat_message_session_id'), table_name='chat_message')
    op.drop_table('chat_message')
    op.drop_table('quote_batch')
    op.drop_table('mark_template')
    op.drop_index(op.f('ix_chat_session_user_id'), table_name='chat_session')
    op.drop_table('chat_session')
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_declaration_element_product_name'), table_name='declaration_element')
    op.drop_index(op.f('ix_declaration_element_hs_code'), table_name='declaration_element')
    op.drop_index(op.f('ix_declaration_element_customer_name'), table_name='declaration_element')
    op.drop_table('declaration_element')
    op.drop_table('asset')
