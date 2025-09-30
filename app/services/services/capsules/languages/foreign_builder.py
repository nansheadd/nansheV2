import logging
import json
from typing import List, Dict, Any, Optional, Set, Tuple

from app.data.language_assets import (
    FALLBACK_CHARACTER_SETS,
    FALLBACK_DIALOGUES,
    FALLBACK_GRAMMAR,
    FALLBACK_TRANSLATION_PAIRS,
    FALLBACK_VOCABULARY,
    LANGUAGE_CODE_MAP,
    normalise_language_key,
)
from sqlalchemy.orm import Session
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.atom_model import Atom, AtomContentType
from app.services.services.capsules.base_builder import BaseCapsuleBuilder
from openai import OpenAI
from app.core.config import settings
from app.models.user.user_model import User
from app.services.atom_service import AtomService
from app.core import ai_service

logger = logging.getLogger(__name__)

class ForeignBuilder(BaseCapsuleBuilder):
    """
    Builder spécialisé pour les langues, implémentant toutes les méthodes requises.
    """

    SCRIPT_KEYWORDS = {
        "alphabet",
        "écriture",
        "ecriture",
        "hiragana",
        "katakana",
        "kanji",
        "kana",
        "prononciation",
        "pronunciation",
        "script",
        "lettres",
    }

    CONVERSATION_KEYWORDS = {
        "conversation",
        "dialogue",
        "parler",
        "situations",
        "scenario",
        "scénario",
    }

    TRANSLATION_KEYWORDS = {
        "traduction",
        "phrases",
        "production",
        "écriture",
        "writing",
        "expression",
    }

    DEFAULT_RECIPE = [
        AtomContentType.LESSON,
        AtomContentType.VOCABULARY,
        AtomContentType.TRANSLATION,
        AtomContentType.DIALOGUE_PRACTICE,
        AtomContentType.MATCHING,
        AtomContentType.FLASHCARDS,
        AtomContentType.QUIZ,
    ]

    def __init__(
        self,
        db: Session,
        capsule: Capsule,
        user: User,
        *,
        source_material: Optional[dict] = None,
    ):
        """
        Constructeur qui accepte db et capsule et les passe au parent.
        """
        super().__init__(db=db, capsule=capsule, user=user, source_material=source_material)
        self.atom_service = AtomService(
            db=db,
            user=user,
            capsule=capsule,
            source_material=source_material,
        )
        self._language_key = normalise_language_key(capsule.main_skill)
        self._language_code = LANGUAGE_CODE_MAP.get(self._language_key or "", None)
        self._assets_cache: Dict[int, Dict[str, Any]] = {}

        try:
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        except Exception as e:
            self.openai_client = None
            logger.error(f"❌ Erreur de configuration OpenAI dans ForeignBuilder: {e}")

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def _coerce_atom_type(self, value: Any) -> AtomContentType:
        if isinstance(value, AtomContentType):
            return value
        if isinstance(value, str):
            try:
                return AtomContentType(value)
            except ValueError:
                return AtomContentType(value.lower())
        raise ValueError(f"Unsupported atom content type: {value!r}")

    def _lang_code(self) -> Optional[str]:
        return self._language_code

    def _language_name(self) -> str:
        return self.capsule.main_skill or "langue"

    def _infer_cefr(self, molecule: Molecule) -> str:
        """Approximate the CEFR level based on the granule order."""

        granule = getattr(molecule, "granule", None)
        order = getattr(granule, "order", None) or molecule.order or 1
        if order <= 2:
            return "A1"
        if order <= 4:
            return "A2"
        if order <= 6:
            return "B1"
        if order <= 8:
            return "B2"
        if order <= 10:
            return "C1"
        return "C2"

    def _is_script_molecule(self, molecule: Molecule) -> bool:
        title = (molecule.title or "").lower()
        return any(keyword in title for keyword in self.SCRIPT_KEYWORDS)

    def _is_conversation_molecule(self, molecule: Molecule) -> bool:
        title = (molecule.title or "").lower()
        return any(keyword in title for keyword in self.CONVERSATION_KEYWORDS)

    def _assets_for(self, molecule: Molecule) -> Dict[str, Any]:
        cached = self._assets_cache.get(molecule.id)
        if cached:
            return cached

        assets = self._build_assets(molecule)
        self._assets_cache[molecule.id] = assets
        return assets

    def _build_assets(self, molecule: Molecule) -> Dict[str, Any]:
        language = self._language_name()
        lang_key = self._language_key or language.lower()
        fallback_key = lang_key if lang_key in FALLBACK_VOCABULARY else None
        cefr = self._infer_cefr(molecule)

        pedago: Dict[str, Any] = {}
        if self.openai_client:
            try:
                pedago = ai_service.generate_language_pedagogical_content(
                    course_title=self.capsule.title or language,
                    chapter_title=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                    lang_code=self._lang_code(),
                )
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("Generation pédagogique indisponible: %s", exc)
                pedago = {}

        vocabulary = self._normalise_vocabulary(
            pedago.get("vocabulary") if isinstance(pedago, dict) else None,
            fallback_key,
        )
        grammar = self._normalise_grammar(
            pedago.get("grammar") if isinstance(pedago, dict) else None,
            fallback_key,
        )

        dialogue = self._build_dialogue_assets(molecule, vocabulary, grammar, fallback_key)
        translations = self._build_translation_assets(fallback_key)
        character_sets = self._build_character_sets_assets(molecule, fallback_key)
        virtual_keyboard = self._build_virtual_keyboard(character_sets)
        transliteration_map = self._build_transliteration_map(character_sets)
        character_practice = self._build_character_practice(
            character_sets,
            virtual_keyboard,
            transliteration_map,
        )
        character_flashcards = self._build_character_flashcards(character_sets)

        if dialogue and isinstance(dialogue, dict):
            metadata = dialogue.setdefault("metadata", {})
            metadata.setdefault("cefr", cefr)
            metadata.setdefault("learning_focus", "dialogue")
            metadata.setdefault("language", self._lang_code() or self._language_name())
            dialogue["virtual_keyboard"] = virtual_keyboard
            dialogue["transliteration_map"] = transliteration_map

        assets = {
            "cefr": cefr,
            "vocabulary": vocabulary,
            "grammar": grammar,
            "phrases": pedago.get("phrases", []) if isinstance(pedago, dict) else [],
            "dialogue": dialogue,
            "translations": translations,
            "character_sets": character_sets,
            "virtual_keyboard": virtual_keyboard,
            "transliteration_map": transliteration_map,
            "character_practice": character_practice,
            "character_flashcards": character_flashcards,
        }

        assets["matching_pairs"] = [
            {"left": item["term"], "right": item["translation_fr"], "id": item["id"]}
            for item in vocabulary
        ]

        assets["flashcards"] = [
            {
                "id": entry["id"],
                "front": entry["term"],
                "front_extra": entry.get("transliteration", ""),
                "back": entry["translation_fr"],
                "example_tl": entry.get("example_tl"),
                "example_fr": entry.get("example_fr"),
            }
            for entry in vocabulary
        ]

        return assets

    def _normalise_vocabulary(
        self,
        payload: Optional[List[Dict[str, Any]]],
        fallback_key: Optional[str],
    ) -> List[Dict[str, Any]]:
        source = payload if isinstance(payload, list) and payload else []
        if not source and fallback_key:
            source = FALLBACK_VOCABULARY.get(fallback_key, [])

        normalised: List[Dict[str, Any]] = []
        for index, entry in enumerate(source):
            if not isinstance(entry, dict):
                continue
            term = entry.get("term") or entry.get("word")
            translation = entry.get("translation_fr") or entry.get("meaning")
            if not term or not translation:
                continue
            normalised.append(
                {
                    "id": entry.get("id") or f"vocab-{index}",
                    "term": term,
                    "lemma": entry.get("lemma", term),
                    "translation_fr": translation,
                    "pos": entry.get("pos", ""),
                    "gender": entry.get("gender", "-"),
                    "register": entry.get("register", "neutre"),
                    "ipa": entry.get("ipa", ""),
                    "transliteration": entry.get("transliteration") or entry.get("reading", ""),
                    "example_tl": entry.get("example_tl") or entry.get("example"),
                    "example_fr": entry.get("example_fr") or entry.get("translation_example"),
                    "tags": entry.get("tags", []),
                }
            )
        return normalised

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
                symbol = character.get("symbol")
                roman = character.get("romanization")
                if symbol and roman:
                    mapping.setdefault(roman.lower(), symbol)
        return mapping

    def _normalise_grammar(
        self,
        payload: Optional[List[Dict[str, Any]]],
        fallback_key: Optional[str],
    ) -> List[Dict[str, Any]]:
        source = payload if isinstance(payload, list) and payload else []
        if not source and fallback_key:
            source = FALLBACK_GRAMMAR.get(fallback_key, [])
        normalised: List[Dict[str, Any]] = []
        for index, entry in enumerate(source):
            if not isinstance(entry, dict):
                continue
            rule = entry.get("rule_name") or entry.get("name")
            explanation = entry.get("explanation_fr") or entry.get("description")
            if not rule:
                continue
            normalised.append(
                {
                    "id": entry.get("id") or f"grammar-{index}",
                    "rule_name": rule,
                    "explanation_fr": explanation or "",
                    "patterns": entry.get("patterns", []),
                    "examples": entry.get("examples", []),
                    "common_errors_fr": entry.get("common_errors_fr", []),
                }
            )
        return normalised

    def _build_dialogue_assets(
        self,
        molecule: Molecule,
        vocabulary: List[Dict[str, Any]],
        grammar: List[Dict[str, Any]],
        fallback_key: Optional[str],
    ) -> Dict[str, Any]:
        dialogue_data: Optional[Dict[str, Any]] = None

        if self.openai_client:
            try:
                raw = ai_service.generate_language_dialogue(
                    course_title=self.capsule.title or self._language_name(),
                    chapter_title=molecule.title,
                    vocabulary=vocabulary,
                    grammar=grammar,
                    model_choice="gpt-5-mini-2025-08-07",
                    target_cefr=self._infer_cefr(molecule),
                    lang_code=self._lang_code(),
                )
                if raw:
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict) and parsed.get("dialogue"):
                            dialogue_data = parsed["dialogue"]
                    except json.JSONDecodeError:
                        logger.warning("Dialogue JSON invalide, utilisation du fallback.")
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("G\u00e9n\u00e9ration de dialogue indisponible: %s", exc)

        if dialogue_data is None and fallback_key:
            dialogue_data = FALLBACK_DIALOGUES.get(fallback_key)

        if not dialogue_data:
            return {"setting": molecule.title, "turns": []}

        vocab_index = {entry["id"]: entry for entry in vocabulary}

        turns: List[Dict[str, Any]] = []
        raw_turns = dialogue_data.get("turns", []) if isinstance(dialogue_data, dict) else []
        for idx, turn in enumerate(raw_turns):
            if not isinstance(turn, dict):
                continue
            speaker = str(turn.get("speaker", "")).strip() or ("A" if idx % 2 == 0 else "B")
            is_user = bool(turn.get("is_user_turn")) or speaker.upper() in {"B", "YOU", "USER"}
            keywords = turn.get("expected_keywords")
            if not keywords:
                keywords = []
                for ref in turn.get("vocab_refs", []) or []:
                    vocab_entry = vocab_index.get(ref)
                    if vocab_entry:
                        keywords.append(vocab_entry["term"])
            turns.append(
                {
                    "speaker": speaker,
                    "text_tl": turn.get("text_tl") or turn.get("text") or "",
                    "transliteration": turn.get("transliteration", ""),
                    "translation_fr": turn.get("translation_fr") or "",
                    "notes_fr": turn.get("notes_fr") or "",
                    "vocab_refs": turn.get("vocab_refs", []),
                    "grammar_refs": turn.get("grammar_refs", []),
                    "is_user_turn": is_user,
                    "expected_keywords": keywords,
                }
            )

        return {
            "setting": dialogue_data.get("setting") or molecule.title,
            "turns": turns,
            "metadata": {
                "learning_focus": "dialogue",
                "language": self._lang_code() or self._language_name(),
            },
        }

    def _build_translation_assets(self, fallback_key: Optional[str]) -> Dict[str, Any]:
        data = FALLBACK_TRANSLATION_PAIRS.get(fallback_key or "", {})
        fr_to_tl = data.get("fr_to_tl", [])
        tl_to_fr = data.get("tl_to_fr", [])
        return {
            "fr_to_tl": fr_to_tl,
            "tl_to_fr": tl_to_fr,
        }

    def _build_character_sets_assets(
        self,
        molecule: Molecule,
        fallback_key: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not self._is_script_molecule(molecule):
            return []

        character_sets: List[Dict[str, Any]] = []
        if self.openai_client:
            try:
                character_sets = ai_service.generate_language_character_sets(
                    language=self._language_name(),
                    title=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                    lang_code=self._lang_code(),
                )
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("G\u00e9n\u00e9ration de jeu de caract\u00e8res indisponible: %s", exc)

        if not character_sets and fallback_key:
            character_sets = FALLBACK_CHARACTER_SETS.get(fallback_key, [])

        return character_sets or []

    def _build_character_practice(
        self,
        character_sets: List[Dict[str, Any]],
        virtual_keyboard: List[str],
        transliteration_map: Dict[str, str],
    ) -> Dict[str, Any]:
        if not character_sets:
            return {}

        practice_items: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str]] = set()
        limit = 12

        for set_index, char_set in enumerate(character_sets):
            set_name = char_set.get("name", f"Set {set_index + 1}")
            for character in char_set.get("characters", []):
                symbol = character.get("symbol")
                roman = character.get("romanization")
                if not symbol or not roman:
                    continue
                key = (symbol, roman)
                if key in seen:
                    continue
                seen.add(key)
                practice_items.append(
                    {
                        "symbol": symbol,
                        "romanization": roman,
                        "ipa": character.get("ipa", ""),
                        "category": character.get("category", ""),
                        "set_name": set_name,
                        "character_id": character.get("character_id")
                        or f"{self._lang_code() or 'xx'}:{set_name}:{symbol}",
                    }
                )
                if len(practice_items) >= limit:
                    break
            if len(practice_items) >= limit:
                break

        if not practice_items:
            return {}

        recognition_items = [dict(item) for item in practice_items]
        production_items = [dict(item) for item in practice_items]

        modes = [
            {
                "id": "recognition",
                "label": "Reconnaître les caractères",
                "prompt_label": "Caractère",
                "answer_label": "Romanisation",
                "instructions": "Observe le caractère et saisis sa romanisation.",
                "items": recognition_items,
            },
            {
                "id": "production",
                "label": "Écrire le caractère",
                "prompt_label": "Romanisation",
                "answer_label": "Caractère",
                "instructions": "Lis la romanisation et écris le caractère correspondant.",
                "items": production_items,
            },
        ]

        return {
            "default_mode": "recognition",
            "modes": modes,
            "items": recognition_items,
            "virtual_keyboard": virtual_keyboard,
            "transliteration_map": transliteration_map,
        }

    def _build_character_flashcards(
        self,
        character_sets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        cards: List[Dict[str, Any]] = []
        if not character_sets:
            return cards

        for set_index, char_set in enumerate(character_sets):
            set_name = char_set.get("name", f"set-{set_index + 1}")
            for index, character in enumerate(char_set.get("characters", [])):
                symbol = character.get("symbol")
                if not symbol:
                    continue
                roman = character.get("romanization", "")
                ipa = character.get("ipa")
                category = character.get("category")
                back_lines = []
                if roman:
                    back_lines.append(roman)
                if ipa:
                    back_lines.append(f"IPA : {ipa}")
                if category:
                    back_lines.append(f"Catégorie : {category}")

                card_id = f"char-{self._lang_code() or 'xx'}-{set_index}-{index}"
                cards.append(
                    {
                        "id": card_id,
                        "front": symbol,
                        "front_extra": roman,
                        "back": "\n".join(back_lines) or roman or symbol,
                        "hint": None,
                    }
                )

        return cards

    # ------------------------------------------------------------------
    # Atom builders
    # ------------------------------------------------------------------

    def _build_lesson_atom(
        self,
        molecule: Molecule,
        assets: Dict[str, Any],
        *,
        context_atoms: List[Atom],
        difficulty: Optional[str],
    ) -> Dict[str, Any] | None:
        cefr = assets.get("cefr")

        if self._is_script_molecule(molecule):
            lesson_text = ""
            if self.openai_client:
                try:
                    lesson_text = ai_service.generate_writing_system_lesson(
                        course_title=self._language_name(),
                        chapter_title=molecule.title,
                        model_choice="gpt-5-mini-2025-08-07",
                        lang_code=self._lang_code(),
                    )
                except Exception as exc:  # pragma: no cover - defensive fallback
                    logger.warning("G\u00e9n\u00e9ration de le\u00e7on d'\u00e9criture indisponible: %s", exc)
            if not lesson_text:
                characters = assets.get("character_sets", [])
                bullet_lines = []
                for char_set in characters[:1]:
                    items = [
                        f"- {item['symbol']} ({item.get('romanization', '')})"
                        for item in char_set.get("characters", [])[:10]
                    ]
                    bullet_lines.extend(items)
                lesson_text = "\n".join(
                    [
                        f"# {molecule.title}",
                        "Cette le\u00e7on pr\u00e9sente les caract\u00e8res de base du syst\u00e8me d'\u00e9criture.",
                        "", *bullet_lines
                    ]
                )
            return {
                "text": lesson_text,
                "metadata": {
                    "cefr": cefr,
                    "learning_focus": "writing_system",
                },
            }

        if self.atom_service:
            lesson_content = self.atom_service.create_atom_content(
                AtomContentType.LESSON,
                molecule,
                context_atoms,
                difficulty=difficulty,
            )
            if lesson_content:
                metadata = lesson_content.setdefault("metadata", {})
                metadata.setdefault("cefr", cefr)
                metadata.setdefault("learning_focus", "lesson")
                metadata.setdefault("language", self._lang_code() or self._language_name())
                return lesson_content

        summary_lines = [f"# {molecule.title}", ""]
        if assets.get("vocabulary"):
            summary_lines.append("## Vocabulaire cl\u00e9")
            for entry in assets["vocabulary"][:5]:
                summary_lines.append(
                    f"- {entry['term']} ({entry.get('transliteration', '')}) : {entry['translation_fr']}"
                )
        if assets.get("grammar"):
            summary_lines.append("")
            summary_lines.append("## Points de grammaire")
            for item in assets["grammar"][:2]:
                summary_lines.append(f"- **{item['rule_name']}** : {item.get('explanation_fr', '')}")

        return {
            "text": "\n".join(summary_lines),
            "metadata": {
                "cefr": cefr,
                "learning_focus": "lesson",
                "generated": "fallback",
            },
        }

    def _build_vocabulary_atom(
        self,
        molecule: Molecule,
        assets: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any] | None:
        items = assets.get("vocabulary", [])
        if not items:
            return None

        content_items = []
        for entry in items:
            content_items.append(
                {
                    "id": entry["id"],
                    "word": entry["term"],
                    "reading": entry.get("transliteration", ""),
                    "meaning": entry["translation_fr"],
                    "ipa": entry.get("ipa", ""),
                    "tags": entry.get("tags", []),
                    "example": entry.get("example_tl"),
                    "example_translation": entry.get("example_fr"),
                }
            )

        return {
            "prompt": f"Vocabulaire important : {molecule.title}",
            "items": content_items,
            "metadata": {
                "cefr": assets.get("cefr"),
                "learning_focus": "vocabulary",
                "language": self._lang_code() or self._language_name(),
                "notebook_suggestions": [
                    "Ajoute les mots que tu trouves difficiles dans ton carnet pour pouvoir les revoir.",
                    "Note une phrase personnelle utilisant deux nouvelles expressions.",
                ],
                "srs_items": [entry["id"] for entry in items],
            },
        }

    def _build_flashcards_atom(
        self,
        molecule: Molecule,
        assets: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any] | None:
        cards: List[Dict[str, Any]] = []
        if self._is_script_molecule(molecule):
            cards.extend(assets.get("character_flashcards", []))
        cards.extend(assets.get("flashcards", []))

        if not cards:
            return None
        transformed = []
        seen_ids: Set[str] = set()
        for card in cards:
            if not isinstance(card, dict):
                continue
            card_id = str(card.get("id") or f"flash-{len(transformed)}")
            if card_id in seen_ids:
                continue
            seen_ids.add(card_id)
            front = card.get("front", "")
            if card.get("front_extra"):
                front = f"{front}\n({card['front_extra']})"
            transformed.append(
                {
                    "id": card_id,
                    "front": front,
                    "back": card.get("back"),
                    "hint": card.get("example_fr") or card.get("hint"),
                }
            )
        return {
            "prompt": f"Révise les cartes du chapitre : {molecule.title}",
            "cards": transformed,
            "metadata": {
                "cefr": assets.get("cefr"),
                "learning_focus": "flashcards",
                "language": self._lang_code() or self._language_name(),
                "srs_items": [entry["id"] for entry in transformed],
            },
        }

    def _build_matching_atom(
        self,
        molecule: Molecule,
        assets: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any] | None:
        pairs = assets.get("matching_pairs", [])
        if not pairs:
            return None
        return {
            "prompt": f"Associe les mots {self._language_name()} avec leur traduction",
            "pairs": pairs,
            "metadata": {
                "cefr": assets.get("cefr"),
                "learning_focus": "association",
                "language": self._lang_code() or self._language_name(),
            },
        }

    def _build_translation_atom(
        self,
        molecule: Molecule,
        assets: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any] | None:
        data = assets.get("translations", {})
        fr_to_tl = data.get("fr_to_tl", [])
        tl_to_fr = data.get("tl_to_fr", [])
        if not fr_to_tl and not tl_to_fr:
            return None

        directions: List[Dict[str, Any]] = []
        if fr_to_tl:
            directions.append(
                {
                    "id": "fr_to_target",
                    "mode": "fr_to_target",
                    "instruction": f"Traduisez du fran\u00e7ais vers le {self._language_name()}.",
                    "items": fr_to_tl,
                    "threshold": 0.6,
                }
            )
        if tl_to_fr:
            directions.append(
                {
                    "id": "target_to_fr",
                    "mode": "target_to_fr",
                    "instruction": f"Traduisez du {self._language_name()} vers le fran\u00e7ais.",
                    "items": tl_to_fr,
                    "threshold": 0.6,
                }
            )

        return {
            "prompt": f"Travail de traduction - {molecule.title}",
            "directions": directions,
            "virtual_keyboard": assets.get("virtual_keyboard", []),
            "transliteration_map": assets.get("transliteration_map", {}),
            "metadata": {
                "cefr": assets.get("cefr"),
                "learning_focus": "translation",
                "language": self._lang_code() or self._language_name(),
            },
        }

    def _build_dialogue_atom(
        self,
        molecule: Molecule,
        assets: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any] | None:
        dialogue = assets.get("dialogue")
        if not dialogue:
            return None
        return {
            "prompt": dialogue.get("setting") or molecule.title,
            "turns": dialogue.get("turns", []),
            "metadata": {
                "cefr": assets.get("cefr"),
                "learning_focus": "dialogue",
            },
        }

    def _build_dialogue_practice_atom(
        self,
        molecule: Molecule,
        assets: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any] | None:
        dialogue = assets.get("dialogue") or {}
        scenario = dialogue.get("setting") or molecule.title
        turns = dialogue.get("turns", []) if isinstance(dialogue, dict) else []

        focus_vocab: List[Dict[str, Any]] = []
        for entry in assets.get("vocabulary", [])[:10]:
            focus_vocab.append(
                {
                    "term": entry.get("term", ""),
                    "translation_fr": entry.get("translation_fr", ""),
                    "transliteration": entry.get("transliteration") or entry.get("reading"),
                    "tags": entry.get("tags", []),
                    "ipa": entry.get("ipa", ""),
                }
            )

        grammar_focus: List[Dict[str, Any]] = []
        for rule in assets.get("grammar", [])[:3]:
            grammar_focus.append(
                {
                    "rule_name": rule.get("rule_name", ""),
                    "explanation_fr": rule.get("explanation_fr", ""),
                }
            )

        practice_guidelines = [
            "Réponds en plusieurs phrases courtes en restant dans le contexte.",
            "Réutilise un mot clé du vocabulaire quand c'est pertinent.",
            "Pose régulièrement une question de relance à ton interlocuteur.",
        ]

        seed_turns = []
        for turn in turns[:6]:
            if not isinstance(turn, dict):
                continue
            seed_turns.append(
                {
                    "speaker": turn.get("speaker"),
                    "text_tl": turn.get("text_tl") or turn.get("text"),
                    "translation_fr": turn.get("translation_fr"),
                    "transliteration": turn.get("transliteration"),
                }
            )

        ai_context = {
            "persona": "Tu es un partenaire de conversation bienveillant qui aide un apprenant à pratiquer.",
            "scenario": scenario,
            "goals": [
                "Encourager l'apprenant à parler librement dans la langue cible.",
                "Introduire ou reformuler le vocabulaire du chapitre.",
                "Donner un retour bienveillant et des suggestions concrètes en français.",
            ],
        }

        return {
            "prompt": f"Atelier de conversation : {molecule.title}",
            "scenario": scenario,
            "language_name": self._language_name(),
            "language_code": self._lang_code(),
            "cefr": assets.get("cefr"),
            "seed_turns": seed_turns,
            "focus_vocabulary": focus_vocab,
            "grammar_focus": grammar_focus,
            "practice_guidelines": practice_guidelines,
            "virtual_keyboard": assets.get("virtual_keyboard", []),
            "transliteration_map": assets.get("transliteration_map", {}),
            "ai_context": ai_context,
            "metadata": {
                "cefr": assets.get("cefr"),
                "learning_focus": "dialogue_practice",
                "language": self._lang_code() or self._language_name(),
            },
        }


    def _build_character_atom(
        self,
        molecule: Molecule,
        assets: Dict[str, Any],
        **_: Any,
    ) -> Dict[str, Any] | None:
        character_sets = assets.get("character_sets", [])
        if not character_sets:
            return None

        practice_data = assets.get("character_practice") or {}
        modes_source = practice_data.get("modes") or []
        sanitized_modes: List[Dict[str, Any]] = []

        def _normalise_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            cleaned: List[Dict[str, Any]] = []
            seen_local: Set[str] = set()
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                symbol = entry.get("symbol")
                roman = entry.get("romanization")
                if not symbol or not roman:
                    continue
                key = f"{symbol}:{roman}"
                if key in seen_local:
                    continue
                seen_local.add(key)
                cleaned.append(
                    {
                        "symbol": symbol,
                        "romanization": roman,
                        "ipa": entry.get("ipa", ""),
                        "category": entry.get("category", ""),
                        "set_name": entry.get("set_name", ""),
                        "character_id": entry.get("character_id"),
                    }
                )
            return cleaned

        for mode in modes_source:
            if not isinstance(mode, dict):
                continue
            normalised_items = _normalise_items(mode.get("items", []))
            if not normalised_items:
                continue
            sanitized_modes.append(
                {
                    "id": mode.get("id", "mode"),
                    "label": mode.get("label") or "Mode",
                    "prompt_label": mode.get("prompt_label", ""),
                    "answer_label": mode.get("answer_label", ""),
                    "instructions": mode.get("instructions", ""),
                    "items": normalised_items,
                }
            )

        if not sanitized_modes:
            fallback_items: List[Dict[str, Any]] = []
            for char_set in character_sets:
                for item in char_set.get("characters", [])[:12]:
                    symbol = item.get("symbol")
                    roman = item.get("romanization")
                    if not symbol or not roman:
                        continue
                    fallback_items.append(
                        {
                            "symbol": symbol,
                            "romanization": roman,
                            "ipa": item.get("ipa", ""),
                            "category": item.get("category", ""),
                            "set_name": char_set.get("name", ""),
                            "character_id": item.get("character_id"),
                        }
                    )
                if fallback_items:
                    break
            if fallback_items:
                sanitized_modes = [
                    {
                        "id": "recognition",
                        "label": "Reconnaître les caractères",
                        "prompt_label": "Caractère",
                        "answer_label": "Romanisation",
                        "instructions": "Observe le caractère et saisis sa romanisation.",
                        "items": fallback_items,
                    }
                ]

        if not sanitized_modes:
            return None

        default_mode = practice_data.get("default_mode") or sanitized_modes[0]["id"]
        practice_payload = {
            "default_mode": default_mode,
            "modes": sanitized_modes,
            "items": sanitized_modes[0].get("items", []),
            "virtual_keyboard": practice_data.get("virtual_keyboard")
            or assets.get("virtual_keyboard", []),
            "transliteration_map": practice_data.get("transliteration_map")
            or assets.get("transliteration_map", {}),
        }

        return {
            "prompt": f"Pratique d'écriture : {molecule.title}",
            "character_sets": character_sets,
            "practice": practice_payload,
            "metadata": {
                "cefr": assets.get("cefr"),
                "learning_focus": "writing_system",
            },
        }

    def generate_learning_plan(self, db: Session, capsule: Capsule) -> dict | None:
        """
        Surcharge la génération de plan pour utiliser un prompt spécialisé.
        """
        logger.info("====== ✅ GÉNÉRATION DE PLAN SPÉCIALISÉE (LANGUES) ✅ ======")
        inspirational_examples = self._find_inspirational_examples(db, capsule.domain, capsule.area)
        
        if not self.openai_client: return None
        
        language = capsule.main_skill
        system_prompt = (
            "Tu es un polyglotte et un ingénieur pédagogique. Crée un plan d'apprentissage JSON pour une langue étrangère. "
            "Le plan doit être complet, progressif (A1 à C1), et contenir entre 16 et 25 'levels' (compétences majeures). "
            "Chaque 'level' contient des 'chapters' (leçons spécifiques)."
        )
        user_prompt = f"Crée un plan de cours exceptionnel pour apprendre le {language}."

        if inspirational_examples:
            examples_str = "\n\n---\n\n".join(
                f"Exemple pour '{ex['main_skill']}':\n{json.dumps(ex['plan'], indent=2, ensure_ascii=False)}"
                for ex in inspirational_examples
            )
            user_prompt += (
                f"\n\nInspire-toi de la structure de ces plans pour créer un plan "
                f"entièrement nouveau et adapté pour le {language}.\n\n{examples_str}"
            )

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-5-mini-2025-08-07",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Erreur API OpenAI dans ForeignBuilder : {e}")
            return None

    def _generate_plan_from_source(
        self,
        db: Session,
        capsule: Capsule,
        source_material: dict,
    ) -> dict | None:
        document_text = (source_material or {}).get("text")
        if not document_text:
            return None
        try:
            return ai_service.generate_learning_plan_from_document(
                document_text=document_text,
                title=capsule.title,
                domain=capsule.domain,
                area=capsule.area,
                main_skill=capsule.main_skill,
                model_choice="gpt-5-mini-2025-08-07",
            )
        except Exception as exc:
            logger.error("Erreur lors de la génération du plan contextualisé pour la capsule de langue : %s", exc, exc_info=True)
            return None

    # === IMPLÉMENTATION OBLIGATOIRE N°1 ===
    def _get_molecule_recipe(self, molecule: Molecule) -> List[Dict[str, Any]]:
        """
        Définit les "recettes" pour les leçons de langue.
        """
        if self._is_script_molecule(molecule):
            return [
                {"type": AtomContentType.LESSON},
                {"type": AtomContentType.CHARACTER},
                {"type": AtomContentType.DIALOGUE},
                {"type": AtomContentType.DIALOGUE_PRACTICE},
                {"type": AtomContentType.TRANSLATION},
                {"type": AtomContentType.FLASHCARDS},
                {"type": AtomContentType.MATCHING},
                {"type": AtomContentType.QUIZ},
            ]

        recipe = list(self.DEFAULT_RECIPE)

        if self._is_conversation_molecule(molecule):
            recipe.insert(2, AtomContentType.DIALOGUE)

        return [{"type": atom_type} for atom_type in recipe]

    # === IMPLÉMENTATION OBLIGATOIRE N°2 ===
    def _build_atom_content(
        self,
        atom_type: AtomContentType,
        molecule: Molecule,
        context_atoms: List[Atom],
        difficulty: str | None = None,
    ) -> Dict[str, Any] | None:
        """
        "Usine" de fabrication du contenu pour chaque type d'atome de langue.
        """
        assets = self._assets_for(molecule)

        builders = {
            AtomContentType.LESSON: self._build_lesson_atom,
            AtomContentType.VOCABULARY: self._build_vocabulary_atom,
            AtomContentType.FLASHCARDS: self._build_flashcards_atom,
            AtomContentType.MATCHING: self._build_matching_atom,
            AtomContentType.TRANSLATION: self._build_translation_atom,
            AtomContentType.DIALOGUE: self._build_dialogue_atom,
            AtomContentType.DIALOGUE_PRACTICE: self._build_dialogue_practice_atom,
            AtomContentType.CHARACTER: self._build_character_atom,
        }

        builder = builders.get(atom_type)
        if builder:
            content = builder(molecule, assets, context_atoms=context_atoms, difficulty=difficulty)
            if content:
                self._save_atom_to_vector_store(
                    self.db,
                    self.capsule,
                    molecule,
                    atom_type.value,
                    content,
                )
            return content

        if self.atom_service:
            generated = self.atom_service.create_atom_content(
                atom_type,
                molecule,
                context_atoms,
                difficulty=difficulty,
            )
            if generated:
                return generated

        logger.warning("Aucun constructeur disponible pour l'atome %s", atom_type.name)
        return None

    def _call_openai_for_json(self, user_prompt: str, system_prompt: str) -> Dict[str, Any] | None:
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-5-mini-2025-08-07",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Erreur lors de l'appel OpenAI pour obtenir du JSON : {e}")
            return None
