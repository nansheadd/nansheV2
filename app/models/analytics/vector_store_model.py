from sqlalchemy import Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base
from pgvector.sqlalchemy import Vector

class VectorStore(Base):
    __tablename__ = "vector_store"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"))
    chunk_text: Mapped[str] = mapped_column(Text)
    
    # The vector embedding. 384 is the dimension for the model we'll use.
    embedding: Mapped[list[float]] = mapped_column(Vector(384))