"""[User]: Add Role and State

Revision ID: 5a580877595d
Revises: 80b0a98ce379
Create Date: 2021-03-23 17:10:44.624613

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '5a580877595d'
down_revision = '80b0a98ce379'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users_v2', sa.Column('email', sa.String(length=255), nullable=True, comment='email of user'))
    op.add_column('users_v2', sa.Column('name', sa.String(length=255), nullable=True, comment='name of user'))
    op.add_column('users_v2', sa.Column('role', sa.Enum('USER', 'ADMIN', name='role', native_enum=False), nullable=True, comment='role of user'))
    op.add_column('users_v2', sa.Column('state', sa.Enum('ACTIVE', 'DELETED', name='state', native_enum=False), nullable=True, comment='state of user'))
    op.alter_column('users_v2', 'username',
               existing_type=mysql.VARCHAR(length=255),
               comment='unique name of user',
               existing_comment='user name of user',
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('users_v2', 'username',
               existing_type=mysql.VARCHAR(length=255),
               comment='user name of user',
               existing_comment='unique name of user',
               existing_nullable=True)
    op.drop_column('users_v2', 'state')
    op.drop_column('users_v2', 'role')
    op.drop_column('users_v2', 'name')
    op.drop_column('users_v2', 'email')
    # ### end Alembic commands ###
