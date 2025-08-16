# Fichier : nanshe/backend/app/services/language_course_generator.py (VERSION REFACTORISÉE)
import json
import logging
from sqlalchemy.orm import Session

# On utilise les nouveaux chemins d'importation
from app.models.user.user_model import User
from app.models.course import (
    course_model, level_model, chapter_model, character_model
)
from app.models.progress import user_course_progress_model
from app.core import ai_service, prompt_manager # <-- IMPORT DU PROMPT_MANAGER
from app.schemas.course import course_schema
from typing import Tuple, Optional, Dict, Any

_PRON_KEYS = (
    "pronunciation", "romanization", "transliteration", "reading",
    "ipa", "pinyin", "romaji", "jyutping", "wylie", "buckwalter",
    "phonetic", "phonetics", "pron"
)

logger = logging.getLogger(__name__)


def _extras_without(skip: set, src: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(src, dict):
        return {}
    return {k: v for k, v in src.items() if k not in skip}

def _normalize_character_entry(entry: Any) -> Tuple[str, str, Dict[str, Any]]:
    """
    Accepte soit une string, soit un dict.
    Retourne (symbol, pronunciation, extras_metadata)
    - symbol: jamais vide si possible (sinon on ignore l'entrée)
    - pronunciation: jamais None (fallback "")
    """
    if isinstance(entry, str):
        symbol = entry.strip()
        if not symbol:
            return "", "", {}
        # si ASCII (ex: alphabets latins), on peut réutiliser le symbole
        pron = symbol if symbol.isascii() else ""
        return symbol, pron, {}

    if isinstance(entry, dict):
        symbol = str(entry.get("symbol") or entry.get("character") or "").strip()
        if not symbol:
            return "", "", {}

        # cherche la meilleure clé pour la prononciation
        pron = ""
        for key in _PRON_KEYS:
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                pron = val.strip()
                break
            # parfois l'IA renvoie une liste/dict (on prend le premier string qu'on trouve)
            if isinstance(val, (list, tuple)) and val:
                first = val[0]
                if isinstance(first, str) and first.strip():
                    pron = first.strip()
                    break
            if isinstance(val, dict):
                # ex: {"value": "..."} / {"text": "..."}
                for cand in ("value", "text"):
                    v2 = val.get(cand)
                    if isinstance(v2, str) and v2.strip():
                        pron = v2.strip()
                        break
                if pron:
                    break

        extras = _extras_without(set(["symbol", "character", *list(_PRON_KEYS)]), entry)
        return symbol, pron or "", extras

    # entrée illisible
    return "", "", {}


def _split_title_and_meta(chapter_entry: Any, fallback_title: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Accepte soit une string, soit un dict chapitre.
    Retourne (title_str, meta_dict_ou_None).
    """
    if isinstance(chapter_entry, dict):
        title = chapter_entry.get("title") or chapter_entry.get("chapter_title") or fallback_title
        meta = {k: v for k, v in chapter_entry.items() if k not in ("title", "chapter_title")}
        return str(title), meta
    return str(chapter_entry), None

def _level_meta(level_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait les champs utiles d'un niveau (hors titre/chapitres) pour metadata_json.
    """
    exclude = {"level_title", "chapters"}
    return {k: v for k, v in level_data.items() if k not in exclude}

class LanguageCourseGenerator:
    """
    Orchestre la création de l'échafaudage complet et structuré d'un cours de langue.
    """
    def __init__(self, db: Session, db_course: course_model.Course, creator: User):
        self.db = db
        self.db_course = db_course  # On reçoit le cours existant
        self.course_in = course_schema.CourseCreate(title=db_course.title, model_choice=db_course.model_choice)
        self.model_choice = db_course.model_choice
        self.creator = creator

    def generate_full_course_scaffold(self):
        """
        Méthode principale qui génère l'ÉCHAFAUDAGE du cours.
        """
        try:
            logger.info(f"Génération de l'échafaudage pour le cours de langue '{self.db_course.title}' (ID: {self.db_course.id})")
            
            # On ne crée plus d'entrée, on la met à jour
            self.db_course.generation_status = "generating"
            self.db.commit()

            # Les étapes de génération restent les mêmes
            course_plan = self._generate_full_course_plan()
            self._apply_full_course_plan(course_plan)
            
            character_sets = self._generate_character_sets()
            self._save_character_sets(character_sets)

            # Finalisation
            self.db_course.generation_status = "completed"
            self.db.commit()
            
            self._enroll_creator()
            self.db.commit()

            logger.info(f"Échafaudage généré et créateur inscrit pour le cours ID {self.db_course.id}")
            return self.db_course

        except Exception as e:
            logger.error(f"Erreur majeure lors de la génération de l'échafaudage : {e}", exc_info=True)
            if self.db_course:
                self.db.rollback()
                self.db_course.generation_status = "failed"
                self.db.commit()
            return None
    
    # --- MÉTHODES PRIVÉES DE LA PIPELINE ---

    def _create_initial_course_entry(self):
        """Crée l'enregistrement de base pour le cours."""
        logger.info("  Étape 1: Création de l'entrée en base de données.")
        self.db_course = course_model.Course(
            title=self.course_in.title,
            model_choice=self.model_choice,
            generation_status="generating",
            course_type="langue"
        )
        self.db.add(self.db_course)
        self.db.commit()
        self.db.refresh(self.db_course)

    def _generate_full_course_plan(self) -> Dict[str, Any]:
        """Appelle l'IA pour générer le plan complet du cours via le prompt manager (JSON garanti)."""
        logger.info(" Étape 2: Génération du plan de cours complet par l'IA.")
        system_prompt = prompt_manager.get_prompt("language_generation.full_course_plan", ensure_json=True)
        user_prompt = f"Langue à apprendre : {self.course_in.title}"
        # ⬇️ on utilise la variante JSON robuste
        plan = ai_service._call_ai_model_json(user_prompt, self.model_choice, system_prompt=system_prompt)
        return plan or {}
    
    def _apply_full_course_plan(self, plan: Dict[str, Any]):
        """Sauvegarde le plan de cours (niveaux et chapitres) en BDD, compatible string/dict."""
        if not plan:
            raise ValueError("Le plan de cours généré est vide.")

        # Description + metadata côté cours
        self.db_course.description = plan.get("overview", f"Un cours fascinant sur {self.db_course.title}")
        course_meta = plan.get("metadata")
        if course_meta and hasattr(self.db_course, "metadata_json"):
            try:
                self.db_course.metadata_json = course_meta  # JSONB si présent
            except Exception:
                logger.debug("metadata_json non assignable sur Course; ignoré.")

        levels = plan.get("levels", [])
        for i, level_data in enumerate(levels):
            level_title = level_data.get("level_title") or f"Niveau {i+1}"

            db_level = level_model.Level(
                course_id=self.db_course.id,
                title=str(level_title),
                level_order=i,
                are_chapters_generated=True
            )
            # Metadata niveau (cefr, can_dos, outcomes, etc.)
            meta = _level_meta(level_data)
            if meta and hasattr(db_level, "metadata_json"):
                try:
                    db_level.metadata_json = meta
                except Exception:
                    logger.debug("metadata_json non assignable sur Level; ignoré.")

            self.db.add(db_level)
            self.db.flush()  # pour récupérer db_level.id

            chapters = level_data.get("chapters", [])
            for j, ch in enumerate(chapters):
                ch_title, ch_meta = _split_title_and_meta(ch, fallback_title=f"Chapitre {j+1}")

                db_chapter = chapter_model.Chapter(
                    level_id=db_level.id,
                    title=ch_title,                  # ⚠️ toujours une string ici
                    chapter_order=j,
                    lesson_status="pending",
                    exercises_status="pending"
                )
                # Metadata chapitre (objectives, targets, etc.) si colonne dispo
                if ch_meta and hasattr(db_chapter, "metadata_json"):
                    try:
                        db_chapter.metadata_json = ch_meta
                    except Exception:
                        logger.debug("metadata_json non assignable sur Chapter; ignoré.")

                self.db.add(db_chapter)

    def _generate_character_sets(self) -> Dict[str, Any]:
        """Appelle l'IA pour générer les alphabets/syllabaires via le prompt manager (JSON garanti)."""
        logger.info(" Étape 3: Génération des jeux de caractères par l'IA.")
        system_prompt = prompt_manager.get_prompt("language_generation.character_sets", ensure_json=True)
        user_prompt = f"Langue : {self.course_in.title}"
        return ai_service._call_ai_model_json(user_prompt, self.model_choice, system_prompt=system_prompt) or {}

    def _save_character_sets(self, data: Dict[str, Any]):
        """Sauvegarde les jeux de caractères en BDD, de manière générique et sûre (NOT NULL)."""
        for set_data in (data or {}).get("character_sets", []):
            set_name = str(set_data.get("name") or "Character Set")

            db_set = character_model.CharacterSet(
                course_id=self.db_course.id,
                name=set_name
            )
            # stocker notes/ordre/etc. si disponible
            if hasattr(db_set, "metadata_json"):
                extras = _extras_without({"name", "characters"}, set_data)
                if extras:
                    try:
                        db_set.metadata_json = extras
                    except Exception:
                        pass

            self.db.add(db_set)
            self.db.flush()  # récupère db_set.id

            chars = set_data.get("characters", [])
            for entry in chars:
                symbol, pronunciation, extras = _normalize_character_entry(entry)
                if not symbol:
                    continue  # on ignore les lignes vides/malformées

                # ⚠️ 'pronunciation' est NOT NULL en DB → fallback déjà "" si rien
                db_char = character_model.Character(
                    character_set_id=db_set.id,
                    symbol=symbol,
                    pronunciation=pronunciation
                )
                if hasattr(db_char, "metadata_json") and extras:
                    try:
                        db_char.metadata_json = extras
                    except Exception:
                        pass

                self.db.add(db_char)

    def _enroll_creator(self):
        """Inscrit le créateur au cours."""
        logger.info("  Étape finale: Inscription du créateur au cours.")
        progress = user_course_progress_model.UserCourseProgress(
            user_id=self.creator.id, 
            course_id=self.db_course.id, 
            current_level_order=0,
            current_chapter_order=0
        )
        self.db.add(progress)