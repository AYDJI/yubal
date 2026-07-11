"""Database repository for Last.fm discovery models."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from yubal_api.db.discovery import (
    DiscoverySuggestion,
    LastFmSettings,
    SuggestionFields,
    SuggestionStatus,
)


class LastFmSettingsRepository:
    """Repository for Last.fm settings operations."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self) -> LastFmSettings | None:
        """Get the Last.fm settings (single row)."""
        with Session(self._engine) as session:
            stmt = select(LastFmSettings).limit(1)
            return session.exec(stmt).first()

    def upsert(self, settings: LastFmSettings) -> LastFmSettings:
        """Create or update Last.fm settings."""
        with Session(self._engine) as session:
            existing = session.exec(select(LastFmSettings).limit(1)).first()
            if existing:
                excluded = {"id", "created_at"}
                for key, value in settings.model_dump(exclude=excluded).items():
                    setattr(existing, key, value)
                session.commit()
                session.refresh(existing)
                return existing
            session.add(settings)
            session.commit()
            session.refresh(settings)
            return settings

    def delete(self) -> bool:
        """Delete Last.fm settings. Returns True if deleted."""
        with Session(self._engine) as session:
            existing = session.exec(select(LastFmSettings).limit(1)).first()
            if existing is None:
                return False
            session.delete(existing)
            session.commit()
            return True


class DiscoverySuggestionRepository:
    """Repository for discovery suggestion operations."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_suggestions(
        self,
        *,
        status: SuggestionStatus | None = None,
    ) -> list[DiscoverySuggestion]:
        """List suggestions with optional status filter."""
        with Session(self._engine) as session:
            stmt = select(DiscoverySuggestion).order_by(
                col(DiscoverySuggestion.created_at).desc()
            )
            if status is not None:
                stmt = stmt.where(DiscoverySuggestion.status == status)
            return list(session.exec(stmt).all())

    def get(self, id: UUID) -> DiscoverySuggestion | None:
        """Get suggestion by ID."""
        with Session(self._engine) as session:
            return session.get(DiscoverySuggestion, id)

    def create(self, suggestion: DiscoverySuggestion) -> DiscoverySuggestion:
        """Create a new suggestion."""
        with Session(self._engine) as session:
            session.add(suggestion)
            session.commit()
            session.refresh(suggestion)
            return suggestion

    def bulk_create(
        self, suggestions: list[DiscoverySuggestion]
    ) -> list[DiscoverySuggestion]:
        """Create multiple suggestions at once."""
        with Session(self._engine) as session:
            for s in suggestions:
                session.add(s)
            session.commit()
            for s in suggestions:
                session.refresh(s)
            return suggestions

    def update(self, id: UUID, fields: SuggestionFields) -> DiscoverySuggestion | None:
        """Update suggestion fields by ID."""
        with Session(self._engine) as session:
            suggestion = session.get(DiscoverySuggestion, id)
            if suggestion is None:
                return None
            for key, value in fields.items():
                setattr(suggestion, key, value)
            session.commit()
            session.refresh(suggestion)
            return suggestion

    def count(self, *, status: SuggestionStatus | None = None) -> int:
        """Count suggestions with optional status filter."""
        from sqlmodel import func

        with Session(self._engine) as session:
            stmt = select(func.count()).select_from(DiscoverySuggestion)
            if status is not None:
                stmt = stmt.where(DiscoverySuggestion.status == status)
            return session.exec(stmt).one()

    def clear(self, *, status: SuggestionStatus | None = None) -> int:
        """Clear suggestions, optionally filtered by status. Returns count deleted."""
        with Session(self._engine) as session:
            stmt = select(DiscoverySuggestion)
            if status is not None:
                stmt = stmt.where(DiscoverySuggestion.status == status)
            suggestions = list(session.exec(stmt).all())
            count = len(suggestions)
            for s in suggestions:
                session.delete(s)
            session.commit()
            return count
