# Fichier : app/utils/lang_utils.py
from __future__ import annotations

def detect_lang(title: str) -> tuple[str, str]:
    """
    Retourne (lang_code ISO 639-1, lang_name anglais) depuis un titre FR.
    Ex: "le japonais" -> ("ja","Japanese"), "russe"->("ru","Russian")
    Fallback: ("", "").
    """
    t = (title or "").strip().lower()
    mapping = {
        "japonais": ("ja", "Japanese"),
        "japanese": ("ja", "Japanese"),
        "日本語": ("ja", "Japanese"),
        "russe": ("ru", "Russian"),
        "russian": ("ru", "Russian"),
        "русский": ("ru", "Russian"),
        "arabe": ("ar", "Arabic"),
        "arabic": ("ar", "Arabic"),
        "العربية": ("ar", "Arabic"),
        "espagnol": ("es", "Spanish"),
        "spanish": ("es", "Spanish"),
        "español": ("es", "Spanish"),
        "italien": ("it", "Italian"),
        "italian": ("it", "Italian"),
        "anglais": ("en", "English"),
        "english": ("en", "English"),
        # ajoute au besoin
    }
    for k, v in mapping.items():
        if k in t:
            return v
    return ("", "")
