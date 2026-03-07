from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.db import Base
except ModuleNotFoundError:
    from db import Base  # type: ignore


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Center(Base):
    __tablename__ = "centers"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    members: Mapped[list["CenterMember"]] = relationship(
        back_populates="center",
        cascade="all, delete-orphan",
        order_by="CenterMember.created_at",
    )


class CenterMember(Base):
    __tablename__ = "center_members"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    center_id: Mapped[str] = mapped_column(ForeignKey("centers.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    linkedin_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    center: Mapped["Center"] = relationship(back_populates="members")


class Presentation(Base):
    __tablename__ = "presentations"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    storage: Mapped[str] = mapped_column(String(80), nullable=False, default="media")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class AlumniProfile(Base):
    __tablename__ = "alumni_profiles"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    linkedin_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    image_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class SiteSetting(Base):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class SharedBoardState(Base):
    __tablename__ = "shared_board_states"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StudentAccount(Base):
    __tablename__ = "student_accounts"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
