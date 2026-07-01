import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
import enum


class Base(DeclarativeBase):
    pass


class AudienceType(str, enum.Enum):
    engineering = "engineering"
    product = "product"
    support = "support"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Release(Base):
    """One release per repo per batch window."""
    __tablename__ = "releases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pr_numbers: Mapped[str] = mapped_column(Text, nullable=False)
    pr_titles: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(50), default="webhook")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    notes: Mapped[list["ReleaseNote"]] = relationship(
        "ReleaseNote", back_populates="release", cascade="all, delete-orphan"
    )


class ReleaseNote(Base):
    """One note per audience per release."""
    __tablename__ = "release_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("releases.id"), nullable=False, index=True
    )
    audience: Mapped[AudienceType] = mapped_column(
        Enum(AudienceType), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.pending
    )
    slack_channel_id: Mapped[str] = mapped_column(String(50), nullable=True)
    slack_message_ts: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    release: Mapped["Release"] = relationship("Release", back_populates="notes")
class PREmbedding(Base):
    """Vector embedding for a single PR, used for similarity and clustering."""
    __tablename__ = "pr_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("releases.id"), nullable=False, index=True
    )
    repo: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pr_title: Mapped[str] = mapped_column(Text, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

class TrackedRepo(Base):
    """Registry of repos included in the aggregated public changelog feed.
    Adding a repo here is the only step needed to include it on the homepage aside from setting up its GitHub webhook.
    """
    __tablename__ = "tracked_repos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repo: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )