# Fichier : nanshe/backend/app/core/prompt_manager.py

import os
import re
from functools import lru_cache
from typing import Any, Dict

# --- Emplacement des prompts .md ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS_DIR = os.path.join(BASE_DIR, 'prompts')

# --- Défauts globaux (ajuste selon ton usage) ---
GLOBAL_DEFAULTS: Dict[str, Any] = {
    "start_cefr": "A1",
    "end_cefr": "B2",
    "levels_count": 6,
    "chapters_per_level": 4,
    "items_per_chapter": 15,
    "grammar_points_per_chapter": 2,
    "max_turns": 8,
    "include_transliteration": True,
    "include_french_gloss": True,
    "transliteration_system": None,
    "script_ordering": None,
}

# --- Défauts par langue (clé: code ISO 639-1) ---
LANGUAGE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "ja": {"include_transliteration": True, "transliteration_system": "Hepburn", "script_ordering": "gojuon"},
    "ar": {"include_transliteration": True, "transliteration_system": "UNGEGN", "script_ordering": None},
    "ru": {"include_transliteration": True, "transliteration_system": "ISO 9", "script_ordering": None},
    "es": {"include_transliteration": False},
    "it": {"include_transliteration": False},
    "en": {"include_transliteration": False},
}

# --- Regex pour {{ var }} et {{ var|default(...) }} ---
PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][\w\.]*)\s*(?:\|default\(([^)]*)\))?\s*}}")

def _coerce_literal(s: str) -> Any:
    """Transforme 'true'/'false'/nombre/'null' en littéraux Python; sinon string sans guillemets."""
    t = s.strip()
    if t.lower() in ("true", "false"):
        return t.lower() == "true"
    if t.lower() == "null":
        return None
    # nombres simples
    try:
        if "." in t:
            return float(t)
        return int(t)
    except ValueError:
        pass
    # guillemets éventuels
    if (t.startswith("'") and t.endswith("'")) or (t.startswith('"') and t.endswith('"')):
        return t[1:-1]
    return t  # mot nu

def _lookup(context: Dict[str, Any], dotted: str) -> Any:
    """
    Looks up a dotted path in a nested context of dicts and objects.
    """
    cur: Any = context
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        # --- AJOUT ---
        # S'il ne s'agit pas d'un dictionnaire, on essaie de le traiter comme un objet.
        elif hasattr(cur, part):
            cur = getattr(cur, part)
        # --- FIN DE L'AJOUT ---
        else:
            return None
    return cur

def _bool_to_json_literal(val: Any) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    return None  # signal: pas bool

def _render_template_jinja_like(template: str, context: Dict[str, Any]) -> str:
    def repl(m: re.Match):
        var = m.group(1)
        default_raw = m.group(2)
        val = _lookup(context, var)

        if val is None and default_raw is not None:
            val = _coerce_literal(default_raw)

        # Booleans en minuscule si utilisés sans guillemets
        b = _bool_to_json_literal(val)
        if b is not None:
            return b

        # None → null si inséré sans guillemets
        if val is None:
            return "null"

        return str(val)

    return PLACEHOLDER_RE.sub(repl, template)

def _merge_defaults(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Fusionne GLOBAL_DEFAULTS <- LANGUAGE_DEFAULTS[lang_code] <- kwargs."""
    lang_code = kwargs.get("lang_code")
    merged = dict(GLOBAL_DEFAULTS)
    if lang_code and lang_code in LANGUAGE_DEFAULTS:
        merged.update(LANGUAGE_DEFAULTS[lang_code])
    merged.update(kwargs)
    return merged

JSON_GUARDRAIL = (
    "\n\n[CONTRAINTE DE SORTIE]\n"
    "- Réponds STRICTEMENT avec un unique objet JSON valide.\n"
    "- Pas de backticks, pas de texte hors JSON."
)

@lru_cache(maxsize=128)
def get_prompt_template(path: str) -> str:
    """
    Charge un modèle de prompt depuis un fichier .md.
    """
    parts = path.split('.')
    file_name = f"{parts[-1]}.md"
    full_path = os.path.join(PROMPTS_DIR, *parts[:-1], file_name)

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"Erreur: Prompt non trouvé à l'emplacement {full_path}"

def get_prompt(path: str, ensure_json: bool = False, **kwargs) -> str:
    """
    Récupère un template et injecte variables + défauts.
    - Supporte {{ var }} et {{ var|default(...) }}.
    - Paramètre optionnel ensure_json pour ajouter une garde 'JSON only'.
    - Param optionnel lang_code pour activer LANGUAGE_DEFAULTS.
    """
    template = get_prompt_template(path)
    context = _merge_defaults(kwargs)

    rendered = _render_template_jinja_like(template, context)
    if ensure_json:
        rendered = rendered + JSON_GUARDRAIL
    return rendered
