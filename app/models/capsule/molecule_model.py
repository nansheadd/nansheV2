from sqlalchemy import Integer, String, ForeignKey, Enum as EnumSQL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, TYPE_CHECKING

from app.db.base_class import Base
from .capsule_model import GenerationStatus

if TYPE_CHECKING:
    from .granule_model import Granule
    from .atom_model import Atom
    from ..progress.user_molecule_review_model import UserMoleculeReview

class Molecule(Base):
    """Représente une leçon ou un chapitre cohérent à l'intérieur d'un Granule."""
    __tablename__ = "molecules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    granule_id: Mapped[int] = mapped_column(Integer, ForeignKey("granules.id"))
    generation_status: Mapped[GenerationStatus] = mapped_column(
        EnumSQL(GenerationStatus, name="molecule_generation_status_enum"),
        default=GenerationStatus.COMPLETED,
        nullable=False
    )

    # --- Relations ---
    granule: Mapped["Granule"] = relationship(back_populates="molecules")
    atoms: Mapped[List["Atom"]] = relationship(
        back_populates="molecule", cascade="all, delete-orphan"
    )
    reviews: Mapped[List["UserMoleculeReview"]] = relationship(
        "UserMoleculeReview", back_populates="molecule", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<⚛️Molecule(id={self.id}, title='{self.title}', order={self.order})>"
