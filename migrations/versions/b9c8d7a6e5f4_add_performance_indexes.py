"""Add performance indexes on sale and log_entry

Revision ID: b9c8d7a6e5f4
Revises: 0295071a0e38
Create Date: 2025-09-20 21:25:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b9c8d7a6e5f4'
down_revision = '0295071a0e38'
branch_labels = None
depends_on = None


def upgrade():
    # Single-column indexes
    op.create_index('ix_sale_date', 'sale', ['date'], unique=False)
    op.create_index('ix_sale_product_id', 'sale', ['product_id'], unique=False)
    # cashier_id column exists from prior migration; safe to index now
    op.create_index('ix_sale_cashier_id', 'sale', ['cashier_id'], unique=False)
    # Composite index for common dashboard query (date + cashier)
    op.create_index('ix_sale_date_cashier', 'sale', ['date', 'cashier_id'], unique=False)

    # Logs table timestamp index
    op.create_index('ix_logentry_timestamp', 'log_entry', ['timestamp'], unique=False)


def downgrade():
    op.drop_index('ix_logentry_timestamp', table_name='log_entry')
    op.drop_index('ix_sale_date_cashier', table_name='sale')
    op.drop_index('ix_sale_cashier_id', table_name='sale')
    op.drop_index('ix_sale_product_id', table_name='sale')
    op.drop_index('ix_sale_date', table_name='sale')
