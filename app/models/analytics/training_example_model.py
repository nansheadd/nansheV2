from sqlalchemy import Column, Integer, String, ForeignKey
from app.db.base_class import Base

class TrainingExample(Base):
    __tablename__ = "training_examples"

    id = Column(Integer, primary_key=True, index=True)
    input_text = Column(String, index=True, nullable=False)
    predicted_category = Column(String, nullable=True)
    corrected_category = Column(String, index=True, nullable=False)
    # --- MODIFICATION --- On ajoute nullable=True
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)