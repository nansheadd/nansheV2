from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, TYPE_CHECKING

from app.db.base_class import Base

if TYPE_CHECKING:
    from .capsule_model import Capsule
    from .molecule_model import Molecule

class Granule(Base):
    """Représente un grand Niveau ou une section ('level') du plan de cours."""
    __tablename__ = "granules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    capsule_id: Mapped[int] = mapped_column(Integer, ForeignKey("capsules.id"))

    # --- Relations ---
    capsule: Mapped["Capsule"] = relationship(back_populates="granules")
    molecules: Mapped[List["Molecule"]] = relationship(
        back_populates="granule", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<⚪️Granule(id={self.id}, title='{self.title}', order={self.order})>"