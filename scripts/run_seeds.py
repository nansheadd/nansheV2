# Fichier: backend/scripts/run_seeds.py (CORRIGÉ)

import json
import logging
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func

# --- Configuration du chemin et des imports ---
sys.path.append(str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # noqa: F401 - Crucial pour charger tous les modèles
from app.db.session import SessionLocal, sync_engine
from sqlalchemy import text
from app.core.security import get_password_hash
from app.models.capsule.capsule_model import Capsule, GenerationStatus
from app.models.analytics.vector_store_model import VectorStore
from app.models.user.user_model import User
from app.models.capsule.language_roadmap_model import (
    LanguageRoadmap, # <-- NOUVEL IMPORT
    Skill, LanguageRoadmapLevel, LevelSkillTarget, LevelFocus,
    LevelCheckpoint, LevelReward, CEFRBand, FocusType, SkillType, Unit,
    TargetMeasurement, CheckType, RewardType
)
from app.services.rag_utils import get_embedding
from app.models.user.badge_model import Badge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Chemins vers les fichiers de données ---
CLASSIFIER_TRAINING_FILE = Path(__file__).resolve().parent.parent / "app" / "data" / "training_data.jsonl"
PLANS_FILE = Path(__file__).resolve().parent.parent / "app" / "data" / "tree.jsonl"


def get_or_create_default_user(db: Session) -> User:
    """Récupère ou crée un utilisateur système pour être le créateur des capsules modèles."""
    system_user = db.query(User).filter(User.email == "system@nanshe.ai").first()
    if not system_user:
        logger.info("Création de l'utilisateur système 'system@nanshe.ai'")
        system_user = User(
            username="system", email="system@nanshe.ai",
            hashed_password=get_password_hash("system"),
            is_active=True,
            is_superuser=True,
        )
        db.add(system_user)
        db.commit(); db.refresh(system_user)
    return system_user

def seed_classifier_examples(db: Session):
    """Charge les exemples de phrases d'entraînement dans la VectorStore."""
    logger.info("--- Phase 1: Seeding des exemples du classifieur ---")
    if not CLASSIFIER_TRAINING_FILE.exists():
        logger.error(f"❌ Fichier d'entraînement non trouvé : {CLASSIFIER_TRAINING_FILE}")
        return

    count = 0
    with open(CLASSIFIER_TRAINING_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                text = data.get("text")
                main_skill = data.get("main_skill") or data.get("label")

                if not text or not main_skill: continue

                exists = db.query(VectorStore).filter(VectorStore.chunk_text == text).first()
                if not exists:
                    new_vector = VectorStore(
                        chunk_text=text, embedding=get_embedding(text),
                        domain=data.get("domain", "unknown"),
                        area=data.get("area", "unknown"),
                        skill=main_skill
                    )
                    db.add(new_vector)
                    count += 1
            except json.JSONDecodeError:
                continue
    db.commit()
    logger.info(f"✅ Phase 1 terminée: {count} nouveaux exemples d'entraînement ajoutés.")


def seed_skills(db: Session):
    """Crée le référentiel de compétences de base dans la table 'skills'."""
    logger.info("--- Phase 2: Seeding de la taxonomie des compétences (Skills) ---")
    skills_taxonomy = [
        {"code": "vocabulary", "name": "Vocabulaire", "unit": Unit.items, "type": SkillType.core},
        {"code": "grammar", "name": "Grammaire", "unit": Unit.rules, "type": SkillType.core},
        {"code": "verbs", "name": "Verbes", "unit": Unit.verbs, "type": SkillType.core},
        {"code": "characters", "name": "Caractères/Écriture", "unit": Unit.chars, "type": SkillType.core},
        {"code": "pronunciation", "name": "Prononciation", "unit": Unit.accuracy, "type": SkillType.subskill},
        {"code": "mechanics", "name": "Mécaniques de langue", "unit": Unit.rules, "type": SkillType.subskill},
        {"code": "connectors", "name": "Connecteurs logiques", "unit": Unit.items, "type": SkillType.subskill},
        {"code": "idioms", "name": "Expressions idiomatiques", "unit": Unit.items, "type": SkillType.subskill},
        {"code": "register", "name": "Registre de langue", "unit": Unit.rubric, "type": SkillType.extra_data},
        {"code": "listening", "name": "Compréhension orale", "unit": Unit.minutes, "type": SkillType.core},
        {"code": "speaking", "name": "Expression orale", "unit": Unit.minutes, "type": SkillType.core},
        {"code": "reading", "name": "Compréhension écrite", "unit": Unit.tasks, "type": SkillType.core},
        {"code": "writing", "name": "Expression écrite", "unit": Unit.tasks, "type": SkillType.core},
    ]

    count = 0
    for skill_data in skills_taxonomy:
        exists = db.query(Skill).filter(Skill.code == skill_data["code"]).first()
        if not exists:
            db.add(Skill(**skill_data))
            count += 1
    
    db.commit()
    logger.info(f"✅ Phase 2 terminée: {count} nouvelles compétences ajoutées.")


def seed_badges(db: Session):
    logger.info("--- Phase 2b: Seeding des badges ---")
    badge_defs = [
        # Découverte / Initiation (système)
        {
            "name": "Premier pas",
            "slug": "initiation-inscription",
            "description": "Inscription terminée. Bienvenue à bord !",
            "icon": "rocket",
            "category": "Initiation",
            "points": 5,
        },
        {
            "name": "Profil complet",
            "slug": "initiation-profil-complet",
            "description": "Tu as complété ton profil.",
            "icon": "starter",
            "category": "Initiation",
            "points": 10,
        },
        {
            "name": "Pionnier",
            "slug": "voyageur-premiere-connexion",
            "description": "Première connexion réussie.",
            "icon": "starter",
            "category": "Initiation",
            "points": 5,
        },
        {
            "name": "Abonné Premium",
            "slug": "premium-subscriber",
            "description": "Un abonnement premium est actif sur ce compte.",
            "icon": "crown",
            "category": "Premium",
            "points": 50,
        },
        {
            "name": "Artisan en herbe",
            "slug": "artisan-premiere-capsule",
            "description": "Première capsule générée",
            "icon": "creator",
            "category": "Artisan",
            "points": 15,
        },
        {
            "name": "Explorateur",
            "slug": "explorateur-premiere-lecon",
            "description": "Vous avez terminé votre première leçon.",
            "icon": "explorer",
            "category": "Exploration",
            "points": 10,
        },
        {
            "name": "Architecte",
            "slug": "artisan-cinq-capsules",
            "description": "Cinq capsules créées",
            "icon": "architect",
            "category": "Artisan",
            "points": 30,
        },
        {
            "name": "Voyageur aguerri",
            "slug": "explorateur-dix-lecons",
            "description": "Dix leçons terminées",
            "icon": "adventurer",
            "category": "Exploration",
            "points": 40,
        },
        {
            "name": "Marathonien",
            "slug": "explorateur-cinquante-lecons",
            "description": "Cinquante leçons terminées",
            "icon": "marathon",
            "category": "Exploration",
            "points": 80,
        },
        {
            "name": "Porteur de flambeau",
            "slug": "initiation-premiere-notification",
            "description": "Vous avez ouvert votre première notification.",
            "icon": "torch",
            "category": "Initiation",
            "points": 5,
        },
        {
            "name": "Premier pas en capsule",
            "slug": "apprenant-premiere-inscription-capsule",
            "description": "Tu t'es inscrit(e) à une capsule pour la première fois.",
            "icon": "explorer",
            "category": "Exploration",
            "points": 10,
        },
        # Collection / Meta
        {
            "name": "Collectionneur",
            "slug": "collection-dix-badges",
            "description": "Dix badges débloqués",
            "icon": "collection",
            "category": "Collection",
            "points": 25,
        },
    ]

    count = 0
    for data in badge_defs:
        exists = db.query(Badge).filter(Badge.slug == data["slug"]).first()
        if not exists:
            db.add(Badge(**data))
            count += 1
        else:
            # Mise à jour légère si le badge existe déjà (nom/desc/catégorie/points/icon)
            exists.name = data["name"]
            exists.description = data["description"]
            exists.category = data["category"]
            exists.points = data["points"]
            exists.icon = data.get("icon", exists.icon)
    db.commit()
    logger.info(f"✅ Phase 2b terminée: {count} badges ajoutés ou mis à jour.")


def seed_language_roadmaps(db: Session, system_user: User):
    """Charge les roadmaps complètes à partir du JSONL et peuple les tables normalisées."""
    logger.info("--- Phase 3: Seeding des Roadmaps de langue ---")
    if not PLANS_FILE.exists():
        logger.error(f"❌ Fichier de plans non trouvé : {PLANS_FILE}")
        return

    skills_map = {skill.code: skill for skill in db.query(Skill).all()}
    if not skills_map:
        logger.error("❌ La table des compétences (skills) est vide. Exécutez d'abord seed_skills.")
        return

    count_added = 0
    count_updated = 0
    with open(PLANS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                main_skill = data.get("main_skill")
                if not main_skill: continue

                # --- 1. GESTION DE LA CAPSULE ---
                capsule = db.query(Capsule).filter(func.lower(Capsule.main_skill) == main_skill.lower()).first()
                if not capsule:
                    logger.info(f"Création de la capsule pour '{main_skill}'...")
                    capsule = Capsule(
                        title=f"Cours de {main_skill.capitalize()}", main_skill=main_skill,
                        domain=data.get("domain"), area=data.get("area"),
                        creator_id=system_user.id, generation_status=GenerationStatus.COMPLETED,
                        is_public=True
                    )
                    db.add(capsule)
                    db.flush() 
                    count_added += 1
                else:
                    logger.info(f"Mise à jour de la roadmap pour '{main_skill}'...")
                    count_updated += 1
                
                # --- 2. GESTION DE LA ROADMAP PARENTE ---
                # On supprime l'ancienne roadmap de l'utilisateur système pour la reconstruire
                db.query(LanguageRoadmap).filter(
                    LanguageRoadmap.capsule_id == capsule.id,
                    LanguageRoadmap.user_id == system_user.id
                ).delete()
                db.flush()

                # On crée la nouvelle roadmap parente
                new_roadmap = LanguageRoadmap(
                    user_id=system_user.id,
                    capsule_id=capsule.id,
                    roadmap_data=data 
                )
                db.add(new_roadmap)
                db.flush() # Pour obtenir l'ID de la roadmap

                # --- 3. GESTION DES NIVEAUX (LanguageRoadmapLevel) ---
                for level_data in data.get("levels", []):
                    new_level = LanguageRoadmapLevel(
                        roadmap_id=new_roadmap.id, # <-- CORRECTION CLÉ
                        level=level_data["level"],
                        cefr_level=CEFRBand(level_data["cefr_level"]),
                        xp_range_start=level_data["xp_range_start"],
                        xp_range_end=level_data["xp_range_end"]
                    )
                    db.add(new_level)
                    db.flush() 

                    # 4. Créer les objets liés (targets, focuses, etc.)
                    for target_data in level_data.get("skill_targets", []):
                        skill = skills_map.get(target_data["skill_code"])
                        if skill:
                            db.add(LevelSkillTarget(level_id=new_level.id, skill_id=skill.id, target_value=target_data["target_value"], measurement=TargetMeasurement(target_data["measurement"]), criteria=target_data.get("criteria", {})))
                    for focus_data in level_data.get("focuses", []):
                        db.add(LevelFocus(level_id=new_level.id, type=FocusType(focus_data["type"]), label=focus_data["label"]))
                    for checkpoint_data in level_data.get("checkpoints", []):
                        db.add(LevelCheckpoint(level_id=new_level.id, type=CheckType(checkpoint_data["type"]), title=checkpoint_data["title"], min_score=checkpoint_data["min_score"]))
                    for reward_data in level_data.get("rewards", []):
                        db.add(LevelReward(level_id=new_level.id, type=RewardType(reward_data["type"]), code=reward_data["code"], name=reward_data["name"], extra_data=reward_data.get("extra_data", {})))
                
                vector_exists = db.query(VectorStore).filter(func.lower(VectorStore.skill) == main_skill.lower()).first()
                if not vector_exists:
                     db.add(VectorStore(chunk_text=main_skill, embedding=get_embedding(main_skill), domain=data.get("domain"), area=data.get("area"), skill=main_skill))

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(f"Erreur de parsing sur une ligne du fichier de plans : {e}")
                continue
    db.commit()
    logger.info(f"✅ Phase 3 terminée: {count_added} roadmaps ajoutées, {count_updated} mises à jour.")



if __name__ == "__main__":
    db_session = SessionLocal()
    try:
        with sync_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=sync_engine)
        user = get_or_create_default_user(db_session)
        seed_classifier_examples(db_session)
        seed_skills(db_session)
        seed_badges(db_session)
        seed_language_roadmaps(db_session, user)
    finally:
        db_session.close()
