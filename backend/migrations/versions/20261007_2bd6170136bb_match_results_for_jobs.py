"""match results for jobs

Revision ID: 2bd6170136bb
Revises: 69bdcba430b6
Create Date: 2026-10-07 18:43:20.171155

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2bd6170136bb"
down_revision: str | Sequence[str] | None = "69bdcba430b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Alembic doesn't detect CHECK constraint changes, so this one is written by hand.
NAME = "ck_match_results_candidate_type"


def upgrade() -> None:
    """Allow 'job' candidates: students are matched to jobs."""
    op.drop_constraint(op.f(NAME), "match_results", type_="check")
    op.create_check_constraint(
        op.f(NAME), "match_results", "candidate_type IN ('member', 'startup', 'job')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM match_results WHERE candidate_type = 'job'")
    op.drop_constraint(op.f(NAME), "match_results", type_="check")
    op.create_check_constraint(
        op.f(NAME), "match_results", "candidate_type IN ('member', 'startup')"
    )
