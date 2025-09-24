import logging
import re
from urllib.parse import unquote

from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.session import SessionLocal
from app.core import security
from app.models.user.user_model import User

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _normalize_token_value(raw_token: str | None) -> str | None:
    """Return a clean JWT string extracted from various transport formats.

    Tokens may reach the API through cookies, headers, or query parameters.
    Browsers can percent-encode cookie values (``Bearer%20…``) and some
    frontends send quoted strings. We normalise those cases and also accept
    case-insensitive ``Bearer`` prefixes.
    """

    if raw_token is None:
        return None

    token = raw_token.strip().strip('"').strip("'")
    if not token:
        return None

    # Convert percent-encoded sequences such as ``Bearer%20``.
    token = unquote(token)

    match = re.match(r"^(bearer|token)[\s,:]+(.+)$", token, flags=re.IGNORECASE)
    if match:
        token = match.group(2)
    else:
        parts = token.split()
        if len(parts) >= 2 and parts[0].lower().rstrip(",") in {"bearer", "token"}:
            token = parts[1]

    token = token.strip()
    return token or None


def _decode_user_from_token(token: str | None, db: Session) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    token = _normalize_token_value(token)
    if not token:
        log.warning("Validation échouée: Pas de token fourni.")
        raise credentials_exception

    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            log.warning("Validation échouée: Le token ne contient pas de 'sub'.")
            raise credentials_exception
        
        user_id = int(user_id_str)
    except (JWTError, ValueError, TypeError):
        log.warning("Validation échouée: Le token est invalide ou mal formé.")
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None:
        log.warning(f"Validation échouée: Utilisateur avec ID {user_id} non trouvé.")
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="inactive_user")

    if user.account_deletion_requested_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account_deletion_scheduled")

    log.info(f"Utilisateur {user.id} validé avec succès via token.")
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:

    token_sources = (
        request.cookies.get("access_token"),
        request.headers.get("Authorization"),
        request.headers.get("X-Access-Token"),
        request.headers.get("X-Auth-Token"),
        request.query_params.get("access_token"),
        request.query_params.get("token"),
    )

    last_unauthorized_error: HTTPException | None = None

    for candidate in token_sources:
        token = _normalize_token_value(candidate)
        if not token:
            continue

        try:
            return _decode_user_from_token(token, db)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_401_UNAUTHORIZED:
                raise
            last_unauthorized_error = exc

    if last_unauthorized_error is not None:
        raise last_unauthorized_error

    return _decode_user_from_token(None, db)
