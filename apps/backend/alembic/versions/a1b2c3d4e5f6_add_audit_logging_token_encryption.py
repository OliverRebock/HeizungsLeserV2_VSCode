"""Add audit logging and prepare for token encryption

Revision ID: a1b2c3d4e5f6
Revises: e06013ff8435
Create Date: 2026-04-16 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'e06013ff8435'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_log_entry table
    op.create_table(
        'audit_log_entry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(255), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indices for efficient audit log queries
    op.create_index('idx_audit_event_type', 'audit_log_entry', ['event_type'])
    op.create_index('idx_audit_actor_user_id', 'audit_log_entry', ['actor_user_id'])
    op.create_index('idx_audit_resource_id', 'audit_log_entry', ['resource_id'])
    op.create_index('idx_audit_tenant_id', 'audit_log_entry', ['tenant_id'])
    op.create_index('idx_audit_timestamp', 'audit_log_entry', ['timestamp'])
    op.create_index('idx_audit_event_resource', 'audit_log_entry', ['event_type', 'resource_type', 'resource_id'])
    
    # Expand influx_token column to store encrypted data (encrypted data is larger than plaintext)
    # Change from String(255) to String(1024) to accommodate encrypted payload + Fernet overhead
    op.alter_column('device', 'influx_token',
               existing_type=sa.String(255),
               type_=sa.String(1024),
               existing_nullable=True)


def downgrade() -> None:
    # Revert influx_token column size
    op.alter_column('device', 'influx_token',
               existing_type=sa.String(1024),
               type_=sa.String(255),
               existing_nullable=True)
    
    # Drop audit log indices
    op.drop_index('idx_audit_event_resource', table_name='audit_log_entry')
    op.drop_index('idx_audit_timestamp', table_name='audit_log_entry')
    op.drop_index('idx_audit_tenant_id', table_name='audit_log_entry')
    op.drop_index('idx_audit_resource_id', table_name='audit_log_entry')
    op.drop_index('idx_audit_actor_user_id', table_name='audit_log_entry')
    op.drop_index('idx_audit_event_type', table_name='audit_log_entry')
    
    # Drop audit_log_entry table
    op.drop_table('audit_log_entry')
