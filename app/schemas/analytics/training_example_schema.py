from pydantic import BaseModel

class TrainingExampleCreate(BaseModel):
    input_text: str
    predicted_category: str | None
    corrected_category: str

class TrainingExampleResponse(TrainingExampleCreate):
    id: int
    user_id: int

    class Config:
        from_attributes = True