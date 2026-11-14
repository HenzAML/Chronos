"""classes per week, multi-hour assignments, partial schedules

Revision ID: a1c2e3f4b5d6
Revises: 6f50d42afae8
Create Date: 2026-11-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1c2e3f4b5d6'
down_revision = '6f50d42afae8'
branch_labels = None
depends_on = None

OLD = "status in ('pending', 'optimal', 'feasible', 'infeasible', 'failed')"
NEW = "status in ('pending', 'optimal', 'feasible', 'partial', 'infeasible', 'failed')"


def upgrade():
    op.add_column('course', sa.Column('classes_per_week', sa.Integer(),
                                      nullable=False, server_default='1'))
    op.create_check_constraint('ck_course_classes_positive', 'course', 'classes_per_week > 0')

    op.add_column('course_assignment', sa.Column('class_index', sa.Integer(),
                                                 nullable=False, server_default='1'))
    op.add_column('course_assignment', sa.Column('duration_hours', sa.Integer(),
                                                 nullable=False, server_default='1'))
    op.drop_constraint('uq_assignment_schedule_course', 'course_assignment', type_='unique')
    op.create_unique_constraint('uq_assignment_schedule_course_class', 'course_assignment',
                                ['schedule_id', 'course_id', 'class_index'])

    op.add_column('schedule', sa.Column('unscheduled', sa.JSON(),
                                        nullable=False, server_default='[]'))
    op.drop_constraint('ck_schedule_status', 'schedule', type_='check')
    op.create_check_constraint('ck_schedule_status', 'schedule', NEW)


def downgrade():
    op.drop_constraint('ck_schedule_status', 'schedule', type_='check')
    op.create_check_constraint('ck_schedule_status', 'schedule', OLD)
    op.drop_column('schedule', 'unscheduled')
    op.drop_constraint('uq_assignment_schedule_course_class', 'course_assignment', type_='unique')
    op.create_unique_constraint('uq_assignment_schedule_course', 'course_assignment',
                                ['schedule_id', 'course_id'])
    op.drop_column('course_assignment', 'duration_hours')
    op.drop_column('course_assignment', 'class_index')
    op.drop_constraint('ck_course_classes_positive', 'course', type_='check')
    op.drop_column('course', 'classes_per_week')
