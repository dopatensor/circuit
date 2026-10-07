"""intro forwarding and capacity window

Adds the "forwarded" (the mutual passed the request on) and "withdrawn" statuses, the
time the mutual forwarded it, and an index for counting requests in the last 7 days.

Revision ID: a5cb711b8b42
Revises: 2bd6170136bb
Create Date: 2026-10-07 20:49:07.126618

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5cb711b8b42"
down_revision: str | Sequence[str] | None = "2bd6170136bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("pending", "accepted", "declined", "expired", "completed")
NEW = ("pending", "forwarded", "accepted", "declined", "expired", "completed", "withdrawn")


def _status_check(values: tuple[str, ...]) -> str:
    return f"status IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.add_column(
        "intro_requests", sa.Column("forwarded_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_intro_requests_created_at", "intro_requests", ["created_at"], unique=False)
    op.drop_constraint(op.f("ck_intro_requests_status"), "intro_requests", type_="check")
    op.create_check_constraint("status", "intro_requests", _status_check(NEW))


def downgrade() -> None:
    op.execute("UPDATE intro_requests SET status = 'pending' WHERE status = 'forwarded'")
    op.execute("UPDATE intro_requests SET status = 'declined' WHERE status = 'withdrawn'")
    op.drop_constraint(op.f("ck_intro_requests_status"), "intro_requests", type_="check")
    op.create_check_constraint("status", "intro_requests", _status_check(OLD))
    op.drop_index("ix_intro_requests_created_at", table_name="intro_requests")
    op.drop_column("intro_requests", "forwarded_at")
