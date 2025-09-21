from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class MoleculeNote(Base):
    """Note prise par un utilisateur pour une molécule donnée."""

    __tablename__ = "molecule_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    molecule_id: Mapped[int] = mapped_column(ForeignKey("molecules.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # --- Relations ---
    user = relationship("User", back_populates="molecule_notes")
    molecule = relationship("Molecule", back_populates="notes")


from app.models.user.user_model import User  # pylint: disable=wrong-import-position
from app.models.capsule.molecule_model import Molecule  # pylint: disable=wrong-import-position

User.molecule_notes = relationship(
    "MoleculeNote",
    back_populates="user",
    cascade="all, delete-orphan",
    lazy="selectin",
)

Molecule.notes = relationship(
    "MoleculeNote",
    back_populates="molecule",
    cascade="all, delete-orphan",
    lazy="selectin",
)
