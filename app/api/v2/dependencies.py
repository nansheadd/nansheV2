import logging
import re
from urllib.parse import unquote

from typing import Generator, Optional, Union

from fastapi import Depends, HTTPException, Request, WebSocket, status
from starlette.datastructures import State
from sqlalchemy.orm import Session
from jose import JWTError, ExpiredSignatureError, jwt

from app.db.session import SessionLocal
from app.core import security
from app.models.user.user_model import User

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ScopeType = Union[Request, WebSocket]


def _get_state_container(scope: ScopeType | None) -> Optional[State]:
    """Return the mutable state object associated with the request/websocket."""

    if scope is None:
        return None

    state = getattr(scope, "state", None)
    if state is None:
        state = State()
        setattr(scope, "state", state)
    return state


def _resolve_scope(
    request: Request = None,  # type: ignore[assignment]
    websocket: WebSocket = None,  # type: ignore[assignment]
) -> ScopeType | None:
    """Return the current Request or WebSocket when used as a dependency."""

    return request or websocket


def get_db(
    scope: ScopeType | None = Depends(_resolve_scope),
) -> Generator[Session, None, None]:
    """Provide a scoped SQLAlchemy session shared within a single request.

    Vercel executes each HTTP invocation in a short-lived worker. When our
    dependencies requested a session multiple times during a request
    (``Depends(get_db)`` for the route handler *and* within
    ``get_current_user``) we ended up creating two independent sessions.  The
    authentication dependency closed its session immediately after returning the
    ``User`` instance, leaving the object detached and triggering 500 errors as
    soon as lazy relationships (enrolments, progress, notification counts…)
    were accessed in the actual route handler.

    We cache the session on ``request.state`` (or ``websocket.state``) and keep a
    simple reference counter so the session remains open until the last
    dependency exits. This mirrors the behaviour of scoped sessions in more
    traditional ASGI deployments while remaining compatible with background
    tasks that call ``get_db`` without a request context.
    """

    if scope is None:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
        return

    state = _get_state_container(scope)
    db = getattr(state, "_db_session", None)
    if db is None:
        db = SessionLocal()
        setattr(state, "_db_session", db)
        setattr(state, "_db_refcount", 0)

    refcount = getattr(state, "_db_refcount", 0) + 1
    setattr(state, "_db_refcount", refcount)

    try:
        yield db
    finally:
        refcount = getattr(state, "_db_refcount", 1) - 1
        if refcount <= 0:
            try:
                db.close()
            finally:
                for attr in ("_db_session", "_db_refcount"):
                    if hasattr(state, attr):
                        delattr(state, attr)
        else:
            setattr(state, "_db_refcount", refcount)

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
    except ExpiredSignatureError:
        log.warning("Validation échouée: Le token a expiré.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_expired")
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


def _iter_websocket_token_candidates(websocket: WebSocket) -> list[str | None]:
    """Collect potential JWT transport formats from a WebSocket handshake."""

    candidates: list[str | None] = [
        websocket.cookies.get("access_token"),
        websocket.cookies.get("token"),
        websocket.headers.get("Authorization"),
        websocket.headers.get("X-Access-Token"),
        websocket.headers.get("X-Auth-Token"),
        websocket.query_params.get("access_token"),
        websocket.query_params.get("token"),
    ]

    protocol_header = websocket.headers.get("sec-websocket-protocol")
    if protocol_header:
        protocols = [part.strip() for part in protocol_header.split(",") if part.strip()]

        if len(protocols) >= 2 and protocols[0].lower().rstrip(":") in {"bearer", "token"}:
            candidates.append(" ".join(protocols[:2]))

        candidates.extend(protocols)

    return candidates


def get_current_user_from_websocket(websocket: WebSocket, db: Session) -> User:
    """Authenticate a ``WebSocket`` connection using the same logic as HTTP requests."""

    last_unauthorized_error: HTTPException | None = None

    for candidate in _iter_websocket_token_candidates(websocket):
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

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
