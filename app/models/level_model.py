# Fichier: nanshe/backend/app/models/level_model.py (CORRIGÉ)
from sqlalchemy import Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .course_model import Course
    from .knowledge_component_model import KnowledgeComponent

class Level(Base):
    __tablename__ = "levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    level_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"))

    course: Mapped["Course"] = relationship(back_populates="levels")

    # --- CORRECTION ICI ---
    # On définit la relation en utilisant des chaînes de caractères
    # pour éviter les problèmes d'ordre de chargement.
    knowledge_components: Mapped[List["KnowledgeComponent"]] = relationship(
        "KnowledgeComponent", 
        back_populates="level"
    )
    # --- FIN DE LA CORRECTION ---