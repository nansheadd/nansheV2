from pydantic import BaseModel, Field
from typing import List, Optional, Any


class TestCase(BaseModel):
    input: List[Any]
    expected_output: Any
    description: str

class TestResult(BaseModel):
    success: bool
    description: str
    input: List[Any]
    expected: Any
    got: Any

class CodeExecutionRequest(BaseModel):
    language: str = Field(..., description="Le langage du code à exécuter (ex: 'python')")
    code: str = Field(..., description="Le code source à exécuter")
    test_cases: Optional[List[TestCase]] = Field(None, description="Cas de test pour valider le code")


class CodeExecutionResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    language: str
    test_results: Optional[List[TestResult]] = None