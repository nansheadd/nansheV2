from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import subprocess
import tempfile
import textwrap

from app.api.v2.dependencies import get_current_user, get_db
from app.models.user.user_model import User

router = APIRouter()


class CodeExecutionRequest(BaseModel):
    language: str
    code: str
    stdin: str | None = None


class CodeExecutionResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


@router.post("/execute", response_model=CodeExecutionResponse, summary="Exécuter un snippet de code")
def execute_code(
    payload: CodeExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    language = payload.language.lower()
    if language not in {"python", "py"}:
        raise HTTPException(status_code=400, detail="Seul Python est supporté pour le moment.")

    code = textwrap.dedent(payload.code)
    stdin_data = payload.stdin or ""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["python3", tmp_path],
            input=stdin_data.encode(),
            capture_output=True,
            timeout=5,
        )
        return CodeExecutionResponse(
            stdout=result.stdout.decode(),
            stderr=result.stderr.decode(),
            exit_code=result.returncode,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CodeExecutionResponse(
            stdout=exc.stdout.decode() if exc.stdout else "",
            stderr="Temps d'exécution dépassé (5s).",
            exit_code=-1,
            timed_out=True,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
