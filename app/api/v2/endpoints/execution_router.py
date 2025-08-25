from fastapi import APIRouter, HTTPException, status
from app.schemas import execution_schema
from app.core.docker_manager import run_code_in_docker

router = APIRouter()

@router.post("/run", response_model=execution_schema.CodeExecutionResponse)
def execute_code(request: execution_schema.CodeExecutionRequest):
    """
    Exécute du code et/ou des cas de test de manière sécurisée.
    """
    try:
        # Transforme les objets Pydantic en dictionnaires si nécessaire
        tests = [test.dict() for test in request.test_cases] if request.test_cases else None
        
        stdout, stderr, exit_code, test_results = run_code_in_docker(
            request.language, request.code, test_cases=tests
        )
        
        return execution_schema.CodeExecutionResponse(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            test_results=test_results
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne du serveur : {str(e)}"
        )