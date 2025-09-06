import importlib
import logging
import json
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from openai import OpenAI
from typing import List
from app.models.capsule.atom_model import Atom
from app.services.services.capsules.languages.foreign_builder import ForeignBuilder


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
def _get_builder_for_capsule(db: Session, capsule: Capsule) -> BaseCapsuleBuilder:
    """
    Fonction "Dispatcher" qui sélectionne le bon builder en fonction du domaine de la capsule.
    """
    domain = capsule.domain
    logger.info(f"Sélection du builder pour le domaine : '{domain}'")

    if domain == "languages":
        # Assurez-vous que le nom de la classe ici correspond bien au nom dans votre fichier
        return ForeignBuilder(db=db, capsule=capsule) 
    
    # if domain == "philosophy":
    #     return PhilosophyBuilder(db=db, capsule=capsule)
    
    # Par défaut, on pourrait retourner un DefaultBuilder qui génère du contenu simple
    # return DefaultBuilder(db=db, capsule=capsule)
    
    # Pour l'instant, si aucun builder n'est trouvé, on lève une erreur.
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
        """
        Orchestre la création d'une capsule de manière robuste :
        1. Vérifie si une capsule similaire existe déjà.
        2. Si non, crée l'entité de base 'Capsule' en BDD.
        3. Démarre la tâche de fond pour la génération du plan.
        """
        logger.info("\n--- [SERVICE] Début du processus de création de capsule ---")
        
        main_skill = classification_result.get('main_skill')
        if not main_skill:
            raise ValueError("La classification n'a pas pu déterminer la compétence principale.")

        # === ÉTAPE 1: Vérifier si une capsule identique existe déjà ===
        existing_capsule = self.db.query(Capsule).filter(
            Capsule.main_skill == main_skill,
            Capsule.creator_id == self.user.id
        ).first()
        
        if existing_capsule:
            logger.info(f"--- [SERVICE] Une capsule pour '{main_skill}' existe déjà (ID: {existing_capsule.id}).")
            # Si le plan n'a pas été généré pour une raison X, on peut relancer la tâche
            if not existing_capsule.learning_plan_json and existing_capsule.generation_status != 'pending':
                logger.info("--- [SERVICE] Le plan est manquant, relance de la tâche de génération. ---")
                background_tasks.add_task(self.generate_and_save_plan, existing_capsule.id)
            return existing_capsule

        # === ÉTAPE 2: Créer l'objet Capsule de base ===
        # C'est la seule responsabilité de cette méthode : créer l'enregistrement initial.
        logger.info(f"--- [SERVICE] Aucune capsule existante pour '{main_skill}'. Création de l'entrée en BDD. ---")
        
        new_capsule = Capsule(
            title=main_skill.capitalize(), # On met une majuscule pour un titre propre
            main_skill=main_skill,
            domain=classification_result.get("domain", "others"),
            area=classification_result.get("area", "default"),
            creator_id=self.user.id
            # le statut par défaut est 'pending'
        )
        self.db.add(new_capsule)
        self.db.commit()
        self.db.refresh(new_capsule)
        
        logger.info(f"--- [SERVICE] Capsule ID {new_capsule.id} créée avec succès. ---")

        # === ÉTAPE 3: Lancer la génération du plan en arrière-plan ===
        # La tâche de fond est autonome, elle n'a besoin que de l'ID.
        background_tasks.add_task(self.generate_and_save_plan, new_capsule.id)
        
        logger.info("--- [SERVICE] Processus de création terminé, la génération du plan s'exécute en fond. ---")
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
    

    def generate_and_save_plan(self, capsule_id: int):
        """
        Tâche de fond robuste pour générer, sauvegarder et vectoriser un plan d'apprentissage.
        Cette méthode est autonome et gère sa propre session de base de données.
        """
        logger.info(f"\n--- [PLAN_GENERATOR] Tâche démarrée pour la capsule ID: {capsule_id} ---")
        db: Session = SessionLocal()
        
        # On déclare capsule ici pour qu'elle soit accessible dans le bloc 'except'
        capsule = None 
        try:
            # 1. Récupération et validation de la capsule
            capsule = db.query(Capsule).get(capsule_id)
            if not capsule:
                logger.warning(f"--- [PLAN_GENERATOR] Capsule ID {capsule_id} non trouvée. Arrêt.")
                return
            if capsule.learning_plan_json:
                logger.info(f"--- [PLAN_GENERATOR] La capsule '{capsule.title}' a déjà un plan. Arrêt. ---")
                return

            # 2. Sélection du Builder approprié
            # Cette étape est cruciale car elle charge la logique spécifique au domaine
            builder = get_builder_for_capsule(capsule.domain, capsule.area, db, capsule)

            # 3. Tentative de récupération du plan depuis le cache (VectorStore)
            logger.info(f"--- [PLAN_GENERATOR] Recherche du plan dans le cache pour '{capsule.main_skill}'...")
            generated_plan = builder._find_plan_in_vector_store(db, capsule.main_skill)
            
            # 4. Si non trouvé en cache, génération via le Builder spécialisé
            if not generated_plan:
                logger.info(f"--- [PLAN_GENERATOR] Plan non trouvé en cache. Lancement de la génération via {type(builder).__name__}...")
                generated_plan = builder.generate_learning_plan(db, capsule)

            # 5. Validation et sauvegarde du plan
            if not generated_plan:
                # Si la génération échoue, on lève une erreur pour passer au bloc 'except'
                raise ValueError("La génération du plan par le builder a échoué et n'a retourné aucun contenu.")

            capsule.learning_plan_json = generated_plan
            capsule.generation_status = GenerationStatus.COMPLETED
            db.commit()
            
            logger.info(f"-> ✅ SUCCÈS: Le plan pour '{capsule.title}' a été sauvegardé dans la capsule.")

            # 6. Vectorisation de la compétence pour le RAG futur
            # On s'assure que cette compétence est dans notre "mémoire" pour les prochaines générations
            self._vectorize_skill(db, capsule)
        
        except Exception as e:
            logger.error(f"-> ❌ ERREUR CRITIQUE lors de la génération du plan pour la capsule ID {capsule_id}: {e}", exc_info=True)
            if capsule: # On vérifie que la capsule a bien été chargée
                db.rollback() # Annuler les changements potentiels
                capsule.generation_status = GenerationStatus.FAILED
                db.commit()
        finally:
            logger.info(f"--- [PLAN_GENERATOR] Tâche terminée pour la capsule ID {capsule_id}. Fermeture de la session DB. ---")
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
    
    logger.info(f"--- [GET_BY_PATH] Capsule '{capsule.title}' trouvée et autorisée.")
    return capsule