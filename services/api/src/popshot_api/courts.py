"""A crew's saved courts (migration 0036, ADR 0007): shared by the routes that read or change them.

Writes run as the signed-in person, so the database decides who may: leads and co-leads.
Adding goes through a savepoint, so the two refusals the database makes (a sixth court, or a
Google place saved twice) come back as CourtRefusedError instead of failing the request.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

MAX_COURTS = 5


@dataclass(frozen=True, slots=True)
class SavedCourt:
    id: UUID
    label: str
    google_place_id: str | None
    is_default: bool


class CourtRefusedError(Exception):
    """The crew already has MAX_COURTS courts ('full'), or this place already ('saved')."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def list_courts(session: Session, group_id: UUID) -> list[SavedCourt]:
    """In the crew's order. Empty unless you're an active member (the table's policy)."""
    rows = session.execute(
        text(
            """
            SELECT c.id, c.label, p.google_place_id, c.is_default
            FROM crew_courts c LEFT JOIN places p ON p.id = c.place_id
            WHERE c.group_id = :g
            ORDER BY c.position, c.created_at, c.id
            """
        ),
        {"g": group_id},
    ).all()
    return [SavedCourt(r.id, r.label, r.google_place_id, r.is_default) for r in rows]


def add_court(
    session: Session, group_id: UUID, me: UUID, label: str, place_id: UUID | None = None
) -> UUID:
    """Save a court at the end of the list. The crew's first court becomes its default."""
    try:
        with session.begin_nested():
            court_id: UUID = session.execute(
                text(
                    """
                    INSERT INTO crew_courts (group_id, place_id, label, position, created_by)
                    SELECT :g, :place, :label,
                           coalesce((SELECT max(position) + 1 FROM crew_courts
                                     WHERE group_id = :g), 0),
                           :me
                    RETURNING id
                    """
                ),
                {"g": group_id, "place": place_id, "label": label, "me": me},
            ).scalar_one()
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == "crew_courts_limit":
            raise CourtRefusedError("full") from None
        if constraint == "crew_courts_place_once":
            raise CourtRefusedError("saved") from None
        raise
    return court_id


def make_default(session: Session, group_id: UUID, court_id: UUID) -> None:
    """The crew's default court from now on (one at a time: the old one first lets go)."""
    session.execute(
        text(
            "UPDATE crew_courts SET is_default = false, updated_at = now() "
            "WHERE group_id = :g AND is_default AND id <> :c"
        ),
        {"g": group_id, "c": court_id},
    )
    session.execute(
        text(
            "UPDATE crew_courts SET is_default = true, updated_at = now() "
            "WHERE group_id = :g AND id = :c AND NOT is_default"
        ),
        {"g": group_id, "c": court_id},
    )


def remove_court(session: Session, group_id: UUID, court_id: UUID) -> bool:
    """Whether it was there. Removing the default passes it on (the database does)."""
    removed = session.execute(
        text("DELETE FROM crew_courts WHERE group_id = :g AND id = :c RETURNING id"),
        {"g": group_id, "c": court_id},
    ).first()
    return removed is not None
