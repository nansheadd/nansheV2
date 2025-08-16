# Fichier : app/utils/json_utils.py

from __future__ import annotations
import json
from typing import Any, Optional

def _strip_code_fences(s: str) -> str:
    """Supprime des fences ```...``` éventuels (ex: ```json ... ```)."""
    s = s.strip()
    if s.startswith("```"):
        # Enlève la première ligne (```[lang]?)
        nl = s.find("\n")
        inner = s[nl + 1 :] if nl != -1 else s
        end = inner.rfind("```")
        if end != -1:
            inner = inner[:end]
        return inner.strip()
    return s

def _extract_balanced_json(s: str) -> Optional[str]:
    """
    Extrait le premier objet/array JSON équilibré en ignorant les accolades dans les chaînes.
    Retourne None si rien trouvé.
    """
    s = s.strip()
    start = None
    opener = None
    for i, ch in enumerate(s):
        if ch in "{[":
            start = i
            opener = ch
            break
    if start is None:
        return None

    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(s)):
        c = s[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None

def safe_json_loads(raw: str) -> Any:
    """
    Tente json.loads; si échec:
      1) enlève des fences ``` ```
      2) extrait le premier bloc JSON équilibré (objet ou array) et parse.
    Relève l’exception initiale si tout échoue.
    """
    if raw is None:
        raise ValueError("safe_json_loads: input is None")

    text = _strip_code_fences(str(raw))
    try:
        return json.loads(text)
    except Exception as first_exc:
        candidate = _extract_balanced_json(text)
        if candidate:
            return json.loads(candidate)
        raise first_exc
