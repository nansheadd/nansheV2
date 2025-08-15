# Fichier: backend/app/models/level_model.py (MIS À JOUR)
from sqlalchemy import Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .course_model import Course
    from .chapter_model import Chapter # On importe le nouveau modèle

class Level(Base):
    __tablename__ = "levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    level_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Indique si les chapitres de ce niveau ont été générés
    are_chapters_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"))

    course: Mapped["Course"] = relationship(back_populates="levels")

    # Un niveau a maintenant une liste de chapitres
    chapters: Mapped[List["Chapter"]] = relationship(back_populates="level")