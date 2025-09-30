"""Service utilitaire pour l'entraînement au vocabulaire."""

from __future__ import annotations

import zlib
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy.orm import Session, joinedload

from app.data.language_assets import (
    FALLBACK_VOCABULARY,
    LANGUAGE_CODE_MAP,
    normalise_language_key,
)
from app.models.capsule.atom_model import Atom, AtomContentType
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.capsule_model import Capsule
from app.models.progress.user_atomic_progress import UserVocabularyProgress
from app.services.language_tool_service import LanguageToolService

_DECAY = 0.7
_INCREMENT = 0.3


class VocabularyToolService:
    def __init__(self, db: Session, user):
        self.db = db
        self.user = user
        self.language_tool_service = LanguageToolService(db=db, user=user)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_available_languages(self) -> List[Dict[str, Any]]:
        return self.language_tool_service.list_available_languages()

    def get_vocabulary_trainer(self, language: str) -> Dict[str, Any]:
        lang_key, lang_code = self._resolve_language(language)
        vocabulary_sets, unique_words = self._load_vocabulary_sets(lang_key, lang_code)
        progress_map = self._load_progress()

        total_items = max(len(unique_words), 1)
        sum_target = 0.0
        sum_reverse = 0.0
        mastered_target = 0
        mastered_reverse = 0

        for vocab_id in unique_words:
            hash_id = self._hash_identifier(vocab_id)
            strength_target = progress_map.get((hash_id, "target_to_fr"), 0.0)
            strength_reverse = progress_map.get((hash_id, "fr_to_target"), 0.0)
            sum_target += strength_target
            sum_reverse += strength_reverse
            if strength_target >= 0.7:
                mastered_target += 1
            if strength_reverse >= 0.7:
                mastered_reverse += 1

        practice_summary = {
            "target_to_fr": {
                "mastered": mastered_target,
                "total": total_items,
                "progress": round(sum_target / total_items, 3),
            },
            "fr_to_target": {
                "mastered": mastered_reverse,
                "total": total_items,
                "progress": round(sum_reverse / total_items, 3),
            },
        }

        # Inject progress into each word entry
        for vocab_set in vocabulary_sets:
            words = vocab_set.get("words", [])
            for word in words:
                vocab_id = word["vocabulary_id"]
                hash_id = self._hash_identifier(vocab_id)
                word["strength_target_to_fr"] = round(
                    progress_map.get((hash_id, "target_to_fr"), 0.0), 3
                )
                word["strength_fr_to_target"] = round(
                    progress_map.get((hash_id, "fr_to_target"), 0.0), 3
                )

        return {
            "language": language,
            "language_code": lang_code,
            "vocabulary_sets": vocabulary_sets,
            "practice_summary": practice_summary,
        }

    def record_vocabulary_session(self, language: str, items: Iterable[Dict[str, Any]]) -> None:
        _, lang_code = self._resolve_language(language)
        if not lang_code:
            return

        for item in items:
            vocab_id = item.get("vocabulary_id")
            direction = item.get("direction")
            success = bool(item.get("success"))

            if not vocab_id or direction not in {"target_to_fr", "fr_to_target"}:
                continue

            hashed = self._hash_identifier(vocab_id)
            progress = (
                self.db.query(UserVocabularyProgress)
                .filter(
                    UserVocabularyProgress.user_id == self.user.id,
                    UserVocabularyProgress.vocabulary_atom_id == hashed,
                    UserVocabularyProgress.direction == direction,
                )
                .first()
            )
            current = progress.memorization_strength if progress else 0.0
            new_strength = self._update_strength(current, success)

            if progress:
                progress.memorization_strength = new_strength
            else:
                progress = UserVocabularyProgress(
                    user_id=self.user.id,
                    vocabulary_atom_id=hashed,
                    direction=direction,
                    memorization_strength=new_strength,
                )
                self.db.add(progress)

        self.db.commit()

    # ------------------------------------------------------------------
    # Data loaders
    # ------------------------------------------------------------------

    def _resolve_language(self, language: str) -> Tuple[str, str]:
        lang_key = normalise_language_key(language) or (language or "").strip().lower()
        lang_code = LANGUAGE_CODE_MAP.get(lang_key, (lang_key or "")[:2])
        return lang_key, lang_code

    def _load_progress(self) -> Dict[Tuple[int, str], float]:
        rows = (
            self.db.query(UserVocabularyProgress)
            .filter(UserVocabularyProgress.user_id == self.user.id)
            .all()
        )
        mapping: Dict[Tuple[int, str], float] = {}
        for row in rows:
            mapping[(row.vocabulary_atom_id, row.direction)] = row.memorization_strength or 0.0
        return mapping

    def _load_vocabulary_sets(
        self,
        lang_key: str,
        lang_code: str,
    ) -> Tuple[List[Dict[str, Any]], Set[str]]:
        available_languages = self.list_available_languages()
        matching_entry = next(
            (
                entry
                for entry in available_languages
                if entry["key"] == lang_key
                or entry.get("code") == lang_code
                or normalise_language_key(entry["label"]) == lang_key
            ),
            None,
        )

        vocabulary_sets: List[Dict[str, Any]] = []
        unique_words: Set[str] = set()

        if not matching_entry:
            fallback = FALLBACK_VOCABULARY.get(lang_key, [])
            if fallback:
                words = []
                for entry in fallback:
                    vocab_id = self._build_vocabulary_identifier(lang_code, entry.get("term"), entry.get("translation_fr"))
                    unique_words.add(vocab_id)
                    words.append(
                        {
                            "vocabulary_id": vocab_id,
                            "term": entry.get("term", ""),
                            "transliteration": entry.get("transliteration") or entry.get("reading"),
                            "translation_fr": entry.get("translation_fr", ""),
                            "example": entry.get("example_tl") or entry.get("example"),
                            "example_translation": entry.get("example_fr") or entry.get("translation_example"),
                            "tags": entry.get("tags", []),
                            "ipa": entry.get("ipa", ""),
                            "strength_target_to_fr": 0.0,
                            "strength_fr_to_target": 0.0,
                        }
                    )
                if words:
                    vocabulary_sets.append(
                        {
                            "name": "Vocabulaire de base",
                            "notes": "Liste de référence pour démarrer.",
                            "capsule_id": None,
                            "molecule_id": None,
                            "words": sorted(
                                words,
                                key=lambda item: item["term"].lower() if item["term"] else "",
                            ),
                        }
                    )
            return vocabulary_sets, unique_words

        capsule_ids = matching_entry.get("capsule_ids", [])
        if not capsule_ids:
            return vocabulary_sets, unique_words

        vocab_query = (
            self.db.query(Atom)
            .join(Molecule, Atom.molecule_id == Molecule.id)
            .join(Granule, Molecule.granule_id == Granule.id)
            .join(Capsule, Granule.capsule_id == Capsule.id)
            .filter(Capsule.id.in_(capsule_ids))
            .filter(Atom.content_type.in_([AtomContentType.VOCABULARY]))
            .options(joinedload(Atom.molecule).joinedload(Molecule.granule))
        )

        atoms = vocab_query.all()

        grouped: Dict[int, Dict[str, Any]] = {}

        for atom in atoms:
            molecule = atom.molecule
            if not molecule:
                continue
            set_entry = grouped.setdefault(
                molecule.id,
                {
                    "name": molecule.title,
                    "notes": None,
                    "capsule_id": self._capsule_id_from_molecule(molecule),
                    "molecule_id": molecule.id,
                    "words": [],
                },
            )

            items = []
            content_items = atom.content.get("items") if isinstance(atom.content, dict) else None
            if isinstance(content_items, list):
                items = content_items

            for item in items:
                term = item.get("word") or item.get("term")
                translation = item.get("meaning") or item.get("translation_fr")
                if not term or not translation:
                    continue
                vocab_id = self._build_vocabulary_identifier(lang_code, term, translation)
                unique_words.add(vocab_id)

                if any(word["vocabulary_id"] == vocab_id for word in set_entry["words"]):
                    continue

                set_entry["words"].append(
                    {
                        "vocabulary_id": vocab_id,
                        "term": term,
                        "transliteration": item.get("reading") or item.get("transliteration"),
                        "translation_fr": translation,
                        "example": item.get("example") or item.get("example_tl"),
                        "example_translation": item.get("example_translation") or item.get("example_fr"),
                        "tags": item.get("tags", []),
                        "ipa": item.get("ipa", ""),
                        "strength_target_to_fr": 0.0,
                        "strength_fr_to_target": 0.0,
                    }
                )

        vocabulary_sets = list(grouped.values())
        for vocab_set in vocabulary_sets:
            vocab_set["words"].sort(key=lambda item: item["term"].lower() if item["term"] else "")
        vocabulary_sets.sort(key=lambda entry: entry["name"].lower())

        return vocabulary_sets, unique_words

    def _capsule_id_from_molecule(self, molecule: Molecule) -> Optional[int]:
        granule = molecule.granule
        if granule and isinstance(granule, Granule):
            return granule.capsule_id
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_vocabulary_identifier(self, lang_code: str, term: str, translation: str) -> str:
        normalised_term = (term or "").strip()
        normalised_translation = (translation or "").strip()
        return f"{lang_code}:{normalised_term}:{normalised_translation}".lower()

    def _hash_identifier(self, identifier: str) -> int:
        return zlib.crc32(identifier.encode("utf-8")) & 0xFFFFFFFF

    def _update_strength(self, current: float, success: bool) -> float:
        target = 1.0 if success else 0.0
        new_value = current * _DECAY + target * _INCREMENT
        return max(0.0, min(1.0, new_value))
