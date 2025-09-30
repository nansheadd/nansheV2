"""Services utilitaires pour l'entraînement aux alphabets / caractères."""

from __future__ import annotations

import zlib
from typing import Any, Dict, Iterable, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.data.language_assets import (
    FALLBACK_CHARACTER_SETS,
    LANGUAGE_CODE_MAP,
    normalise_language_key,
)
from app.models.progress.user_atomic_progress import UserCharacterProgress
from app.models.user.user_model import User
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.utility_models import UserCapsuleEnrollment

_DECAY = 0.7
_INCREMENT = 0.3


class LanguageToolService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_character_trainer(self, language: str) -> Dict[str, Any]:
        lang_key, lang_code = self._resolve_language(language)
        character_sets = self._load_character_sets(lang_key)
        progress_map = self._load_progress()

        flattened: List[Dict[str, Any]] = []
        total_items = 0
        mastered_read = mastered_write = 0
        aggregate_strength_read = 0.0
        aggregate_strength_write = 0.0

        enriched_sets: List[Dict[str, Any]] = []
        for set_index, char_set in enumerate(character_sets):
            chars: List[Dict[str, Any]] = []
            for character in char_set.get("characters", []):
                char_id = self._character_id(lang_code, char_set.get("name", str(set_index)), character.get("symbol"))
                hashed = self._character_hash(char_id)
                read_strength = progress_map.get((hashed, "read"), 0.0)
                write_strength = progress_map.get((hashed, "write"), 0.0)

                aggregate_strength_read += read_strength
                aggregate_strength_write += write_strength
                total_items += 1
                if read_strength >= 0.7:
                    mastered_read += 1
                if write_strength >= 0.7:
                    mastered_write += 1

                entry = {
                    "character_id": char_id,
                    "symbol": character.get("symbol", ""),
                    "romanization": character.get("romanization", ""),
                    "ipa": character.get("ipa", ""),
                    "category": character.get("category", ""),
                    "strength_read": round(read_strength, 3),
                    "strength_write": round(write_strength, 3),
                }
                chars.append(entry)
                flattened.append(entry)

            enriched_sets.append(
                {
                    "name": char_set.get("name", f"Set {set_index+1}"),
                    "notes": char_set.get("notes", ""),
                    "characters": chars,
                }
            )

        if total_items == 0:
            total_items = 1  # éviter division par zéro

        summary = {
            "read": {
                "mastered": mastered_read,
                "total": total_items,
                "progress": round(aggregate_strength_read / total_items, 3),
            },
            "write": {
                "mastered": mastered_write,
                "total": total_items,
                "progress": round(aggregate_strength_write / total_items, 3),
            },
        }

        virtual_keyboard = self._build_virtual_keyboard(character_sets)
        transliteration_map = self._build_transliteration_map(character_sets)

        return {
            "language": language,
            "language_code": lang_code,
            "character_sets": enriched_sets,
            "practice_summary": summary,
            "virtual_keyboard": virtual_keyboard,
            "transliteration_map": transliteration_map,
        }

    def list_available_languages(self) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(Capsule)
            .outerjoin(
                UserCapsuleEnrollment,
                (UserCapsuleEnrollment.capsule_id == Capsule.id)
                & (UserCapsuleEnrollment.user_id == self.user.id),
            )
            .filter(
                or_(
                    Capsule.creator_id == self.user.id,
                    UserCapsuleEnrollment.id.isnot(None),
                )
            )
            .filter(Capsule.domain.isnot(None))
            .all()
        )

        languages: Dict[str, Dict[str, Any]] = {}
        for capsule in rows:
            domain = (capsule.domain or "").strip().lower()
            if "lang" not in domain:
                continue

            label_source = capsule.main_skill or capsule.title or capsule.area
            if not label_source:
                continue

            norm_key = normalise_language_key(label_source) or label_source.strip().lower()
            if not norm_key:
                continue

            raw_code = LANGUAGE_CODE_MAP.get(norm_key) or norm_key[:2]
            lang_code = (raw_code or "xx").lower()
            entry = languages.setdefault(
                norm_key,
                {
                    "key": norm_key,
                    "label": label_source.strip(),
                    "code": lang_code,
                    "capsule_ids": set(),
                },
            )
            entry["capsule_ids"].add(capsule.id)

        results: List[Dict[str, Any]] = []
        for entry in languages.values():
            results.append(
                {
                    "key": entry["key"],
                    "label": entry["label"],
                    "code": entry["code"],
                    "capsule_ids": sorted(entry["capsule_ids"]),
                }
            )

        results.sort(key=lambda item: item["label"].lower())
        return results

    def record_character_session(self, language: str, items: Iterable[Dict[str, Any]]) -> None:
        lang_key, lang_code = self._resolve_language(language)
        for item in items:
            char_id = item.get("character_id")
            mode = item.get("mode")
            success = bool(item.get("success"))
            if mode not in {"read", "write"} or not char_id:
                continue
            hashed = self._character_hash(char_id)
            progress = (
                self.db.query(UserCharacterProgress)
                .filter(
                    UserCharacterProgress.user_id == self.user.id,
                    UserCharacterProgress.character_atom_id == hashed,
                    UserCharacterProgress.direction == mode,
                )
                .first()
            )
            strength = 0.0
            if progress:
                strength = progress.strength or 0.0
            new_strength = self._update_strength(strength, success)

            if progress:
                progress.strength = new_strength
            else:
                progress = UserCharacterProgress(
                    user_id=self.user.id,
                    character_atom_id=hashed,
                    direction=mode,
                    strength=new_strength,
                )
                self.db.add(progress)
        self.db.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_language(self, language: str) -> Tuple[str, str]:
        lang_key = normalise_language_key(language) or language.lower()
        lang_code = LANGUAGE_CODE_MAP.get(lang_key, lang_key[:2])
        return lang_key, lang_code

    def _load_character_sets(self, lang_key: str) -> List[Dict[str, Any]]:
        if lang_key in FALLBACK_CHARACTER_SETS:
            return FALLBACK_CHARACTER_SETS[lang_key]
        # Essayer avec la langue normalisée (ex: 'japanese' si 'japonais')
        for key, value in LANGUAGE_CODE_MAP.items():
            if value == LANGUAGE_CODE_MAP.get(lang_key):
                if key in FALLBACK_CHARACTER_SETS:
                    return FALLBACK_CHARACTER_SETS[key]
        return []

    def _load_progress(self) -> Dict[Tuple[int, str], float]:
        rows = (
            self.db.query(UserCharacterProgress)
            .filter(UserCharacterProgress.user_id == self.user.id)
            .all()
        )
        mapping: Dict[Tuple[int, str], float] = {}
        for row in rows:
            mapping[(row.character_atom_id, row.direction)] = row.strength or 0.0
        return mapping

    def _character_id(self, language_code: str, set_name: str, symbol: str | None) -> str:
        symbol = symbol or ""
        return f"{language_code}:{set_name}:{symbol}"

    def _character_hash(self, character_id: str) -> int:
        return zlib.crc32(character_id.encode("utf-8")) & 0xFFFFFFFF

    def _update_strength(self, current: float, success: bool) -> float:
        target = 1.0 if success else 0.0
        new_value = current * _DECAY + target * _INCREMENT
        return max(0.0, min(1.0, new_value))

    def _build_virtual_keyboard(self, character_sets: List[Dict[str, Any]]) -> List[str]:
        keys: List[str] = []
        for char_set in character_sets or []:
            for character in char_set.get("characters", []):
                symbol = character.get("symbol")
                if symbol and symbol not in keys:
                    keys.append(symbol)
        return keys

    def _build_transliteration_map(self, character_sets: List[Dict[str, Any]]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for char_set in character_sets or []:
            for character in char_set.get("characters", []):
                roman = character.get("romanization")
                symbol = character.get("symbol")
                if roman and symbol:
                    mapping.setdefault(roman.lower(), symbol)
        return mapping
