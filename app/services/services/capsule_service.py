import importlib
import logging
import json
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from openai import OpenAI
from typing import List
from app.models.capsule.atom_model import Atom
from app.models.capsule.language_roadmap_model import LanguageRoadmap, LanguageRoadmapLevel, LevelSkillTarget, LevelFocus
from app.services.services.capsules.languages.foreign_builder import ForeignBuilder
from app.services.services.capsules.others.default_builder import DefaultBuilder
from app.models.capsule.capsule_model import Capsule, GenerationStatus
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.atom_model import Atom 
from app.models.progress.user_course_progress_model import UserCourseProgress



from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user.user_model import User
from app.models.capsule.capsule_model import Capsule, GenerationStatus
from app.models.analytics.vector_store_model import VectorStore
from app.services.rag_utils import get_embedding

# --- Builders ---
from app.services.services.capsules.base_builder import BaseCapsuleBuilder


# --- Configuration ---
logger = logging.getLogger(__name__)

try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    openai_client = None
    logger.error(f"❌ Erreur de configuration pour OpenAI: {e}")

# ==============================================================================
# SECTION 1: FONCTION D'AIGUILLAGE (Dispatcher)
# ==============================================================================
def _get_builder_for_capsule(db: Session, capsule: Capsule, user: User) -> BaseCapsuleBuilder: # Ajoutez user ici
    domain = capsule.domain
    logger.info(f"Sélection du builder pour le domaine : '{domain}'")

    if domain == "languages":
        return ForeignBuilder(db=db, capsule=capsule, user=user) # Passez user

    elif domain != "languages":
        return DefaultBuilder(db=db, capsule=capsule, user=user) # Passez user

    raise NotImplementedError(f"Aucun builder n'est implémenté pour le domaine '{domain}'")


def get_builder_for_capsule(domain: str, area: str, db: Session, capsule: Capsule) -> BaseCapsuleBuilder:
    """
    Fonction "Dispatcher" qui sélectionne et INSTANCIE le bon builder.
    """
    logger.info(f"Sélection du builder pour le domaine : '{domain}'")

    if domain == "languages":
        # --- MODIFICATION 2 : On passe les arguments à l'instanciation ---
        return ForeignBuilder(db=db, capsule=capsule)
    
    raise NotImplementedError(f"Aucun builder n'est implémenté pour le domaine '{domain}'")


# ==============================================================================
# SECTION 2: CLASSE DE SERVICE PRINCIPALE
# ==============================================================================

class CapsuleService:
    """
    Service principal pour orchestrer les opérations liées aux capsules.
    Il utilise un système de "Builders" pour déléguer la logique spécifique à chaque type de capsule.
    """
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def create_capsule(self, background_tasks: BackgroundTasks, classification_result: dict) -> Capsule:
        logger.info("\n--- [SERVICE] Début du processus de création de capsule ---")
        main_skill = classification_result.get('main_skill')
        if not main_skill:
            raise ValueError("La classification n'a pas pu déterminer la compétence principale.")

        existing_capsule = self.db.query(Capsule).filter(
            Capsule.main_skill == main_skill,
            Capsule.creator_id == self.user.id
        ).first()
        
        if existing_capsule:
            logger.info(f"--- [SERVICE] Une capsule pour '{main_skill}' existe déjà (ID: {existing_capsule.id}).")
            existing_roadmap = self.db.query(LanguageRoadmap).filter_by(capsule_id=existing_capsule.id, user_id=self.user.id).first()
            if not existing_roadmap and existing_capsule.generation_status != 'pending':
                logger.info("--- [SERVICE] La roadmap est manquante, relance de la tâche de génération. ---")
                background_tasks.add_task(self.generate_and_save_plan, existing_capsule.id, self.user.id)
            return existing_capsule

        logger.info(f"--- [SERVICE] Aucune capsule existante pour '{main_skill}'. Création...")
        new_capsule = Capsule(
            title=main_skill.capitalize(),
            main_skill=main_skill,
            domain=classification_result.get("domain", "others"),
            area=classification_result.get("area", "default"),
            creator_id=self.user.id
        )
        self.db.add(new_capsule)
        self.db.commit()
        self.db.refresh(new_capsule)
        
        logger.info(f"--- [SERVICE] Capsule ID {new_capsule.id} créée. Lancement de la génération du plan en fond. ---")
        background_tasks.add_task(self.generate_and_save_plan, new_capsule.id, self.user.id)
        return new_capsule
    

    def prepare_session_for_level(self, capsule: Capsule, granule_order: int, molecule_order: int) -> List[Atom]:
        """
        Prépare et génère le contenu d'une molécule (leçon) spécifique si nécessaire.
        """
        # On utilise le dispatcher pour obtenir le bon builder
        builder = get_builder_for_capsule(capsule.domain, capsule.area, self.db, capsule)
        
        # 1. S'assurer que la hiérarchie DB (Granule -> Molecule) existe
        molecule = builder.get_or_create_hierarchy(granule_order, molecule_order)

        # 2. Construire le contenu (atomes) en utilisant la logique de recette du builder.
        # Cette méthode est intelligente : elle ne génère que si les atomes n'existent pas.
        atoms = builder.build_molecule_content(molecule)
        
        return atoms
    

    def create_capsule_from_classification(self, classification_data: dict) -> Capsule:
        """
        Version corrigée qui utilise la méthode generate_learning_plan du builder
        et crée la hiérarchie de la capsule.
        """
        topic = classification_data.get("main_skill", "Sujet inconnu")
        logger.info(f"\n--- [SERVICE] Création de capsule à partir de la classification pour: '{topic}' ---")
        
        new_capsule = Capsule(
            title=topic.capitalize(),
            main_skill=topic,
            domain=classification_data.get("domain", "others"),
            area=classification_data.get("area", "generic"),
            creator_id=self.user.id,
            generation_status=GenerationStatus.PENDING
        )
        self.db.add(new_capsule)
        self.db.commit()
        self.db.refresh(new_capsule)
        logger.info(f"--- [SERVICE] Capsule ID {new_capsule.id} créée. ---")

        enrollment = UserCourseProgress(user_id=self.user.id, capsule_id=new_capsule.id)
        self.db.add(enrollment)
        self.db.commit()
        logger.info(f"--- [SERVICE] Utilisateur {self.user.id} inscrit à la capsule {new_capsule.id}. ---")

        builder = _get_builder_for_capsule(self.db, new_capsule, self.user)
        
        # --- CORRECTION 1 : Appeler la bonne méthode ---
        # On appelle la méthode de la classe de base qui génère le plan JSON.
        logger.info(f"--- [SERVICE] Lancement de generate_learning_plan() pour la capsule {new_capsule.id}. ---")
        plan_json = builder.generate_learning_plan(db=self.db, capsule=new_capsule)

        if not plan_json:
            new_capsule.generation_status = GenerationStatus.FAILED
            self.db.commit()
            logger.error(f"--- [SERVICE] Échec de la génération du plan pour la capsule {new_capsule.id}.")
            # Vous pourriez vouloir retourner une erreur ici, mais pour l'instant on continue.
            return new_capsule

        # --- CORRECTION 2 : Sauvegarder le plan et créer la structure ---
        # On sauvegarde le plan JSON dans l'objet capsule.
        new_capsule.learning_plan_json = plan_json
        
        # On parcourt le plan pour créer les "coquilles vides" des Granules et Molécules.
        for g_order, level_data in enumerate(plan_json.get("levels", [])):
            new_granule = Granule(
                title=level_data.get("level_title", f"Niveau {g_order + 1}"),
                order=g_order + 1,
                capsule_id=new_capsule.id
            )
            self.db.add(new_granule)
            self.db.flush() # Nécessaire pour obtenir l'ID du granule

            for m_order, chapter_data in enumerate(level_data.get("chapters", [])):
                new_molecule = Molecule(
                    title=chapter_data.get("chapter_title", f"Leçon {m_order + 1}"),
                    order=m_order + 1,
                    granule_id=new_granule.id
                )
                self.db.add(new_molecule)
                
        new_capsule.generation_status = GenerationStatus.COMPLETED
        self.db.commit()
        self.db.refresh(new_capsule)

        # --- CORRECTION 3 : La logique de génération du contenu initial reste la même ---
        logger.info(f"--- [SERVICE] Génération du contenu initial pour la première molécule. ---")
        first_molecule = self.db.query(Molecule).join(Granule).filter(
            Granule.capsule_id == new_capsule.id
        ).order_by(Granule.order, Molecule.order).first()
        
        if first_molecule:
            builder.build_molecule_content(first_molecule)
            self.db.commit()
        else:
            logger.warning(f"--- [SERVICE] Le plan généré pour la capsule {new_capsule.id} est vide.")

        return new_capsule
    

    def generate_next_molecule_content(self, completed_molecule_id: int) -> List[Atom]:
        """
        Génère le contenu pour la molécule suivante et le retourne (logique JIT),
        SANS utiliser de module CRUD.
        """
        logger.info(f"--- [SERVICE] Requête JIT pour la molécule suivant {completed_molecule_id}. ---")
        
        completed_molecule = self.db.query(Molecule).get(completed_molecule_id)
        if not completed_molecule:
            return []

        # === CORRECTION : Requête directe pour trouver la molécule suivante ===
        next_molecule = self.db.query(Molecule).filter(
            Molecule.granule_id == completed_molecule.granule_id,
            Molecule.order == completed_molecule.order + 1
        ).first()

        if not next_molecule:
            logger.info("--- [SERVICE] Fin du granule ou de la capsule, pas de molécule suivante. ---")
            return []

        if next_molecule.atoms:
            logger.info(f"--- [SERVICE] Les atomes pour la molécule {next_molecule.id} existent déjà. On les retourne. ---")
            return next_molecule.atoms

        builder = _get_builder_for_capsule(self.db, next_molecule.granule.capsule, self.user)
        
        logger.info(f"--- [SERVICE] Génération des atomes pour la molécule {next_molecule.id}... ---")
        atoms = builder.build_molecule_content(next_molecule)
        self.db.commit() # On sauvegarde les atomes créés par le builder
        
        return atoms
    

    def get_or_generate_atoms_for_molecule(self, molecule_id: int) -> List[Atom]:
        """
        Récupère les atomes d'une molécule. S'ils n'existent pas, les génère.
        """
        logger.info(f"--- [SERVICE] Demande d'atomes pour la molécule ID: {molecule_id} ---")
        
        molecule = self.db.query(Molecule).get(molecule_id)
        if not molecule:
            logger.error(f"--- [SERVICE] Molécule ID {molecule_id} non trouvée.")
            return [] # Ou lever une HTTPException

        # 1. Vérifier si les atomes existent déjà (cache BDD)
        if molecule.atoms:
            logger.info(f"--- [SERVICE] Atomes trouvés en BDD pour la molécule '{molecule.title}'. Retour direct.")
            return molecule.atoms

        # 2. Si non, on les génère
        logger.info(f"--- [SERVICE] Aucun atome trouvé. Lancement de la génération pour '{molecule.title}'.")
        capsule = molecule.granule.capsule
        
        # On utilise votre dispatcher existant pour obtenir le bon builder
        builder = _get_builder_for_capsule(self.db, capsule, self.user)
        
        # On appelle la méthode du builder qui contient la logique de génération
        atoms = builder.build_molecule_content(molecule)
        
        # La méthode du builder doit faire le commit, mais on s'assure de rafraîchir
        self.db.refresh(molecule)
        
        return molecule.atoms
    
    def generate_and_save_plan(self, capsule_id: int, user_id: int):
        """
        Tâche de fond qui crée une roadmap personnelle pour un utilisateur en
        se basant sur la roadmap "modèle" de l'utilisateur système.
        """
        logger.info(f"\n--- [PLAN_GENERATOR] Tâche démarrée pour capsule ID: {capsule_id} et user ID: {user_id} ---")
        db: Session = SessionLocal()
        try:
            capsule = db.query(Capsule).get(capsule_id)
            user = db.query(User).get(user_id)
            if not capsule or not user:
                logger.error("Capsule ou Utilisateur non trouvé.")
                return

            # On vérifie si une roadmap existe déjà pour CET utilisateur
            if db.query(LanguageRoadmap).filter_by(capsule_id=capsule.id, user_id=user.id).first():
                logger.info("Une roadmap existe déjà pour cet utilisateur. Arrêt.")
                return

            # --- LOGIQUE DE COPIE CORRIGÉE ---
            # 1. Trouver l'utilisateur système et sa roadmap modèle
            system_user = db.query(User).filter(User.email == "system@nanshe.ai").first()
            if not system_user:
                raise ValueError("Utilisateur système 'system@nanshe.ai' introuvable.")

            template_roadmap = db.query(LanguageRoadmap).join(Capsule).filter(
                Capsule.main_skill == capsule.main_skill,
                LanguageRoadmap.user_id == system_user.id
            ).first()

            if not template_roadmap or not template_roadmap.roadmap_data:
                raise ValueError(f"Aucune roadmap modèle trouvée pour '{capsule.main_skill}'.")

            # 2. Créer la nouvelle roadmap pour l'utilisateur en copiant les données du modèle
            logger.info(f"Copie de la roadmap modèle pour l'utilisateur {user.id}...")
            new_roadmap = LanguageRoadmap(
                user_id=user.id,
                capsule_id=capsule.id,
                roadmap_data=template_roadmap.roadmap_data # On copie le plan JSON
            )
            db.add(new_roadmap)
            db.flush() # Pour obtenir l'ID de la nouvelle roadmap

            # 3. (Optionnel) Si vous voulez dénormaliser les niveaux, faites-le ici
            # C'est souvent plus simple de juste utiliser le JSON `roadmap_data` dans le frontend
            
            capsule.generation_status = GenerationStatus.COMPLETED
            db.commit()
            logger.info(f"-> ✅ SUCCÈS: Roadmap pour '{capsule.title}' créée pour l'utilisateur {user.id}.")
        
        except Exception as e:
            logger.error(f"-> ❌ ERREUR CRITIQUE lors de la génération du plan pour la capsule ID {capsule_id}: {e}", exc_info=True)
            if db.query(Capsule).get(capsule_id):
                db.rollback()
                capsule.generation_status = GenerationStatus.FAILED
                db.commit()
        finally:
            db.close()


    def _vectorize_skill(self, db: Session, capsule: Capsule):
        """Ajoute la compétence principale au VectorStore si elle n'y est pas déjà."""
        vector_exists = db.query(VectorStore).filter(VectorStore.skill == capsule.main_skill).first()
        if not vector_exists:
            logger.info(f"--- [VECTORIZER] Ajout de la compétence '{capsule.main_skill}' au VectorStore. ---")
            db.add(VectorStore(
                chunk_text=capsule.main_skill, 
                embedding=get_embedding(capsule.main_skill),
                domain=capsule.domain, 
                area=capsule.area, 
                skill=capsule.main_skill
            ))
            db.commit()

# ==============================================================================
# SECTION 3: FONCTIONS AUTONOMES (si nécessaire)
# ==============================================================================
# Cette fonction est maintenant indépendante de la classe, car elle est utilisée
# par le routeur pour la récupération de capsules.
def get_capsule_by_path(db: Session, user: User, domain: str, area: str, capsule_id: int) -> Capsule | None:
    """
    Récupère une capsule par son chemin et son ID, en vérifiant les permissions.
    """
    logger.info(f"--- [GET_BY_PATH] Recherche de la capsule ID:{capsule_id} via {domain}/{area} ---")
    
    capsule = db.query(Capsule).filter(
        Capsule.id == capsule_id,
        Capsule.domain == domain,
        # On pourrait aussi vérifier 'area' si c'est une contrainte stricte
        # Capsule.area == area 
    ).first()

    if not capsule:
        logger.warning(f"--- [GET_BY_PATH] Capsule ID {capsule_id} non trouvée.")
        return None

    # === LA CORRECTION EST ICI ===
    # L'appel au builder n'était pas nécessaire pour simplement afficher la capsule.
    # On le supprime. La fonction devient beaucoup plus simple.
    
    # Vérification des permissions : l'utilisateur peut-il voir cette capsule ?
    # (Ex: est-elle publique ou est-il le créateur ?)
    # Pour l'instant on la retourne si elle est publique.
    if not capsule.is_public and capsule.creator_id != user.id:
        logger.warning(f"--- [GET_BY_PATH] Accès refusé pour l'utilisateur {user.id} à la capsule {capsule_id}.")
        return None
    
    print("DIGIMON :: ", capsule)
    logger.info(f"--- [GET_BY_PATH] Capsule '{capsule.title}' trouvée et autorisée.")
    return capsule