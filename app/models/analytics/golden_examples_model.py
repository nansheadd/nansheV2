from sqlalchemy import Integer, Text, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base
from pgvector.sqlalchemy import Vector

class GoldenExample(Base):
    __tablename__ = "golden_examples"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    example_type: Mapped[str] = mapped_column(String(100), index=True) # 'exercise', 'lesson', 'essay_evaluation'
    content: Mapped[str] = mapped_column(Text) # Le contenu JSON ou textuel de l'exemple
    embedding: Mapped[list[float]] = mapped_column(Vector(384))