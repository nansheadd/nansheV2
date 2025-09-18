# Fichier: backend/app/api/v2/endpoints/capsule_router.py

"""
================================================================================
SECTION 1: IMPORTS & CONFIGURATION
================================================================================
"""
import logging
import json
import re
import unicodedata
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import OpenAI

from app.core.config import settings
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user import user_model
from app.models.user.user_model import User
from app.models.capsule import capsule_model, granule_model, atom_model, utility_models, molecule_model
from app.models.analytics.vector_store_model import VectorStore
from app.schemas.capsule import capsule_schema
from app.services.services.capsule_service import CapsuleService
from app.services.services.capsule_service import get_capsule_by_path
from app.services.classification_service import db_classifier
from app.services.capsule_addon.exercices.exercices_generator import ExerciseGeneratorService
from app.models.progress.user_atomic_progress import UserAtomProgress
from app.services.rag_utils import get_embedding
from app.services.services.capsule_service import CapsuleService
from app.schemas.capsule import capsule_schema # Votre fichier de schémas
from app.api.v2 import dependencies



from app.crud import roadmap_crud
from app.services.services.capsules.languages.foreign_builder import ForeignBuilder
from app.schemas.capsule.capsule_schema import CapsuleReadWithRoadmap # Le nouveau schéma
from app.crud import badge_crud



# --- Configuration du Logger et du Routeur ---
logger = logging.getLogger(__name__)
router = APIRouter()

# --- Initialisation du client OpenAI ---
try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    logger.info("✅ Client OpenAI configuré.")
except Exception as e:
    openai_client = None
    logger.error(f"❌ Erreur de configuration pour OpenAI: {e}")


"""
================================================================================
SECTION 2: MODÈLES DE DONNÉES (PYDANTIC)
================================================================================
"""
class ClassifyRequest(BaseModel):
    text: str


"""
================================================================================
SECTION 3: UTILITAIRES DE TRAITEMENT DE TEXTE
================================================================================
"""
_STOP_PATTERNS = re.compile(
    r"\b("
    r"je\s*(voudrais|voudrai|veux|vx)\b"
    r"|est[-\s]*ce\s*possible\b"
    r"|apprendre\b"
    r"|étudier\b|etudier\b"
    r"|comprendre\b"
    r"|cours\s+sur\b"
    r"|les?\s+bases\s+de\b"
    r"|introduction\s+à\b|introduction\s+a\b"
    r"|comment\s+(ma[iî]triser|fonctionne|apprendre)\b"
    r"|exercices?\s+sur\b"
    r")",
    flags=re.IGNORECASE
)

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def clean_user_query(q: str) -> str:
    q_norm = q.strip()
    q_noacc = _strip_accents(q_norm)
    cleaned_noacc = _STOP_PATTERNS.sub(" ", q_noacc)
    cleaned = _STOP_PATTERNS.sub(" ", q_norm)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned if cleaned else q.strip()


"""
================================================================================
SECTION 4: GESTION DES CAPSULES (CRUD)
================================================================================
"""
@router.post(
    "/", 
    response_model=capsule_schema.CapsuleRead, # Utilise votre schéma CapsuleRead existant
    status_code=status.HTTP_201_CREATED
)
def create_generic_capsule(
    request: capsule_schema.CapsuleCreateRequest, # Utilise le schéma de requête que nous avons ajouté
    db: Session = Depends(dependencies.get_db),
    current_user: User = Depends(dependencies.get_current_user),
):
    """
    Crée une nouvelle capsule générique à partir d'un sujet.
    Génère le plan complet et le contenu de la première molécule.
    """
    # 3. Instanciation du service
    # On crée une instance du service en lui passant la session db et l'utilisateur
    # qui viennent des dépendances.
    service = CapsuleService(db=db, user=current_user)
    
    # On appelle la nouvelle méthode que nous avons ajoutée au service.
    capsule = service.create_capsule_from_classification(
        classification_data=request.dict()
    )
    
    if not capsule:
        raise HTTPException(status_code=500, detail="La création de la capsule a échoué.")
    
    return capsule


# --- Endpoint de progression (JIT) ---
@router.post(
    "/molecules/{molecule_id}/complete",
    response_model=List[capsule_schema.AtomRead] # Renvoie la liste des nouveaux atomes
)
def complete_molecule_and_get_next(
    molecule_id: int,
    db: Session = Depends(dependencies.get_db),
    current_user: User = Depends(dependencies.get_current_user),
):
    """
    Valide la fin d'une molécule et génère/renvoie le contenu de la suivante.
    """
    # On instancie le service de la même manière
    service = CapsuleService(db=db, user=current_user)
    
    # On appelle la méthode de génération JIT
    next_atoms = service.generate_next_molecule_content(
        completed_molecule_id=molecule_id
    )
    
    # Si la liste est vide, c'est qu'il n'y a pas de molécule suivante
    if not next_atoms:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="La molécule suivante n'a pas été trouvée ou la capsule est terminée."
        )
        
    return next_atoms


@router.get(
    "/molecules/{molecule_id}/atoms",
    response_model=List[capsule_schema.AtomRead],
    summary="Récupérer ou générer les atomes pour une molécule"
)
def get_atoms_for_molecule(
    molecule_id: int,
    db: Session = Depends(dependencies.get_db),
    current_user: User = Depends(dependencies.get_current_user),
):
    """
    Récupère la liste des atomes pour une molécule spécifique.
    Si les atomes n'ont pas encore été générés, cette route déclenche
    leur création par le builder approprié.
    """
    service = CapsuleService(db=db, user=current_user)
    atoms = service.get_or_generate_atoms_for_molecule(molecule_id=molecule_id)
    
    if not atoms:
        # Cela peut arriver si la génération échoue ou si la recette est vide.
        # Le frontend peut afficher un message approprié.
        return []
        
    return atoms

def log_all_capsules(db: Session):
    capsules = db.query(capsule_model.Capsule).all()
    for cap in capsules:
        logger.info(f"[DB] Capsule: {cap.__dict__}")

@router.get(
    "/{domain}/{area}/{capsule_id}",
    response_model=capsule_schema.CapsuleReadWithRoadmap # ou CapsuleRead si vous n'avez pas de roadmap pour tout
)
def get_capsule(
    domain: str,
    area: str,
    capsule_id: int,
    db: Session = Depends(dependencies.get_db),
    current_user: User = Depends(dependencies.get_current_user)
):
    """
    Récupère les détails d'une capsule, quelle que soit sa catégorie.
    """
    logger.info(f"--- [API] Requête pour récupérer la capsule ID: {capsule_id} via {domain}/{area} ---")
    
    capsule = get_capsule_by_path(
        db=db, 
        user=current_user, 
        domain=domain, 
        area=area, 
        capsule_id=capsule_id
    )

    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule non trouvée ou accès refusé.")

    # Pour les capsules de langue, on attache la roadmap si elle existe.
    # Pour les autres, ce sera simplement None.
    if capsule.domain == "languages":
        capsule.language_roadmap = roadmap_crud.get_roadmap_by_user_and_capsule(
            db, user_id=current_user.id, capsule_id=capsule.id
        )

    service = CapsuleService(db=db, user=current_user)
    capsule = service.annotate_capsule(capsule)

    logger.info(f"--- [API] Capsule trouvée, renvoi des données. <💊Capsule(id={capsule.id})>")
    return capsule


"""
================================================================================
SECTION 5: GESTION DES INSCRIPTIONS UTILISATEUR
================================================================================
"""
@router.get("/me", response_model=List[capsule_schema.CapsuleRead], summary="Lister les capsules de l'utilisateur")
def get_my_capsules(
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user)
):
    """Récupère la liste des capsules auxquelles l'utilisateur actuel est inscrit."""
    enrollments = db.query(utility_models.UserCapsuleEnrollment).filter(utility_models.UserCapsuleEnrollment.user_id == current_user.id).all()
    return [enrollment.capsule for enrollment in enrollments]

@router.get("/public", response_model=List[capsule_schema.CapsuleRead], summary="Lister les capsules publiques disponibles")
def get_public_capsules(
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user)
):
    """Récupère les capsules publiques auxquelles l'utilisateur N'EST PAS encore inscrit."""
    enrolled_capsule_ids = {e.capsule_id for e in current_user.enrollments}
    
    public_capsules = db.query(capsule_model.Capsule).filter(
        capsule_model.Capsule.is_public == True,
        ~capsule_model.Capsule.id.in_(enrolled_capsule_ids)
    ).all()
    
    return public_capsules

@router.post("/{capsule_id}/enroll", response_model=capsule_schema.CapsuleRead, summary="S'inscrire à une capsule")
def enroll_in_capsule(
    capsule_id: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user)
):
    """Inscrit l'utilisateur à une capsule publique."""
    capsule = db.query(capsule_model.Capsule).get(capsule_id)
    if not capsule or not capsule.is_public:
        raise HTTPException(status_code=404, detail="Capsule non trouvée ou non publique.")

    existing = db.query(utility_models.UserCapsuleEnrollment).filter_by(user_id=current_user.id, capsule_id=capsule_id).first()
    if existing:
        return capsule

    new_enrollment = utility_models.UserCapsuleEnrollment(user_id=current_user.id, capsule_id=capsule_id)
    db.add(new_enrollment)
    db.commit()
    # Badges d'inscription: première inscription à une capsule
    try:
        enroll_count = db.query(utility_models.UserCapsuleEnrollment).filter_by(user_id=current_user.id).count()
        if enroll_count == 1:
            badge_crud.award_badge(db, current_user.id, "apprenant-premiere-inscription-capsule")
    except Exception:
        pass
    return capsule

@router.post("/{capsule_id}/unenroll", response_model=capsule_schema.CapsuleRead, summary="Se désinscrire d'une capsule")
def unenroll_from_capsule(
    capsule_id: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user)
):
    """Désinscrit l'utilisateur d'une capsule."""
    enrollment = db.query(utility_models.UserCapsuleEnrollment).filter_by(user_id=current_user.id, capsule_id=capsule_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Inscription non trouvée.")
        
    capsule = enrollment.capsule
    db.delete(enrollment)
    db.commit()
    return capsule


"""
================================================================================
SECTION 6: APPRENTISSAGE & GÉNÉRATION DE CONTENU
================================================================================
"""
@router.post("/classify-topic/", summary="Classifier un sujet de capsule")
def classify_topic(
    request: ClassifyRequest,
    db: Session = Depends(get_db)
):
    """Endpoint utilitaire pour tester la classification d'un texte."""
    logger.info(f"\n--- [CLASSIFY] Démarrage pour le texte: '{request.text}' ---")
    text_input = clean_user_query(request.text)

    if not text_input.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide.")

    predictions = db_classifier.classify(text_input, db, top_k=1)
    
    if not predictions:
        logger.error(f"--- [CLASSIFY] Aucune prédiction trouvée pour '{text_input}'")
        return {"input_text": text_input, "domain": "others", "area": "unknown", "confidence": 0}

    best_prediction = predictions[0]
    category_info = best_prediction.get("category", {})
    
    result = {
        "input_text": text_input,
        "main_skill": category_info.get("name", "unknown"),
        "domain": category_info.get("domain", "others"),
        "area": category_info.get("area", "default"),
        "confidence": best_prediction.get("confidence", 0)
    }
    
    logger.info(f"--- [CLASSIFY] Résultat: {json.dumps(result, indent=2, ensure_ascii=False)}")
    return result


@router.post("/{capsule_id}/level/{level_order}/session", summary="Préparer et récupérer une session d'apprentissage")
def prepare_learning_session(
    capsule_id: int,
    level_order: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user)
):
    """
    Point d'entrée principal pour démarrer l'apprentissage.
    1. Trouve la capsule.
    2. Appelle le service qui, via le bon builder, va:
        a. Créer la structure (Granule, Molecules) si elle n'existe pas.
        b. Générer le contenu pédagogique (Atoms) si nécessaire.
    3. Retourne le contenu complet de la session.
    """
    logger.info(f"--- [API] Préparation de la session pour Capsule ID: {capsule_id}, Level: {level_order} ---")
    
    capsule = db.query(capsule_model.Capsule).get(capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule non trouvée.")

    # On délègue toute la logique complexe au service
    capsule_service = CapsuleService(db, current_user)
    try:
        session_data = capsule_service.prepare_session_for_level(capsule, level_order)
        return session_data
    except Exception as e:
        logger.error(f"Erreur lors de la préparation de la session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Impossible de préparer la session d'apprentissage.")



@router.post("/{capsuleId}/level/{levelOrder}/molecule/{moleculeOrder}", summary="Générer le contenu d'une leçon (molécule)")
def create_molecule_content(
    capsuleId: int,
    levelOrder: int,
    moleculeOrder: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user),
):
    """Génère le contenu d'une leçon si elle n'existe pas déjà."""
    capsule = db.query(capsule_model.Capsule).get(capsuleId)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule introuvable.")
    
    try:
        plan = capsule.learning_plan_json or {}
        level_data = plan.get("levels", [])[levelOrder - 1]
        molecule_data = level_data.get("chapters", [])[moleculeOrder -1] # Correction d'index
        molecule_title = molecule_data.get("chapter_title")
    except IndexError:
        raise HTTPException(status_code=404, detail="Niveau ou chapitre introuvable dans le plan JSON.")

    # Get-or-Create la hiérarchie en base de données
    granule = db.query(granule_model.Granule).filter_by(capsule_id=capsuleId, order=levelOrder).first()
    if not granule:
        granule = granule_model.Granule(capsule_id=capsuleId, order=levelOrder, title=level_data.get("level_title"))
        db.add(granule)
        db.flush()

    molecule = db.query(molecule_model.Molecule).filter_by(granule_id=granule.id, order=moleculeOrder).first()
    if not molecule:
        molecule = molecule_model.Molecule(granule_id=granule.id, order=moleculeOrder, title=molecule_title)
        db.add(molecule)
        db.flush()

    service = CapsuleService(db=db, user=current_user)
    service.assert_molecule_unlocked(molecule)

    # Vérifier si le contenu de la leçon (Atom) existe déjà
    existing_atom = db.query(atom_model.Atom).filter_by(molecule_id=molecule.id, content_type=atom_model.AtomContentType.LESSON).first()
    if existing_atom:
        return {"status": "exists", "lesson": existing_atom.content}

    # Génération du contenu via OpenAI
    logger.info(f"Génération de contenu pour la molécule '{molecule.title}'")
    system_msg = "Tu es un assistant pédagogique. Réponds STRICTEMENT au format JSON. Structure attendue : {\"lesson_text\": \"...markdown...\"}."
    user_msg = f"Génère une leçon complète et structurée pour la leçon « {molecule.title} » dans le contexte du cours « {capsule.title} »."
    
    try:
        response = openai_client.chat.completions.create(model="gpt-5-mini-2025-08-07", messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}], response_format={"type": "json_object"})
        lesson_payload = json.loads(response.choices[0].message.content or "{}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur de génération OpenAI: {e}")

    if "lesson_text" not in lesson_payload:
        raise HTTPException(status_code=500, detail="La réponse d'OpenAI est invalide.")
        
    # Sauvegarde du nouvel Atom et de son vecteur
    new_atom = atom_model.Atom(
        title="Leçon", order=1, content_type=atom_model.AtomContentType.LESSON,
        content=lesson_payload, molecule_id=molecule.id
    )
    db.add(new_atom)
    
    # Création du vecteur associé
    lesson_text = lesson_payload["lesson_text"]
    new_vector = VectorStore(
        chunk_text=lesson_text, embedding=get_embedding(lesson_text),
        domain=capsule.domain, area=capsule.area, skill=granule.title
    )
    db.add(new_vector)

    db.commit()
    logger.info(f"Molécule '{molecule.title}' et son contenu sauvegardés.")
    
    return {"status": "created", "lesson": lesson_payload}


@router.get(
    "/{capsule_id}/granule/{granule_order}/molecule/{molecule_order}",
    # response_model=List[capsule_schema.AtomRead], # Adaptez le schéma de réponse
    summary="Récupérer ou générer le contenu d'une leçon (Molécule)"
)
def get_or_create_molecule_content(
    capsule_id: int,
    granule_order: int,
    molecule_order: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user)
):
    """
    Point d'entrée principal pour l'apprentissage.
    Récupère le contenu d'une leçon. S'il n'a jamais été généré,
    le service le crée à la volée (Just-In-Time).
    """
    capsule = db.query(capsule_model.Capsule).get(capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule non trouvée.")

    # On délègue toute la logique complexe au service
    service = CapsuleService(db, current_user)
    try:
        # Note: j'ai simplifié le nom de la méthode dans le service
        atoms = service.prepare_session_for_level(capsule, granule_order, molecule_order)
        return atoms # Retourne la liste des objets Atom
    except Exception as e:
        logger.error(f"Erreur lors de la préparation de la session : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# NOUVELLE ROUTE : Pour marquer un atome comme terminé
@router.post(
    "/atom/{atom_id}/complete",
    summary="Marquer un atome comme terminé par l'utilisateur"
)
def complete_atom(
    atom_id: int,
    # On pourrait recevoir un body avec le score, etc.
    # class AtomCompletionRequest(BaseModel):
    #     score: float
    # request: AtomCompletionRequest,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(get_current_user)
):
    """
    Met à jour la progression de l'utilisateur pour un atome spécifique.
    """
    atom = db.query(atom_model.Atom).get(atom_id)
    if not atom:
        raise HTTPException(status_code=404, detail="Atome non trouvé.")

    progress = db.query(UserAtomProgress).filter_by(user_id=current_user.id, atom_id=atom_id).first()
    
    if not progress:
        progress = UserAtomProgress(user_id=current_user.id, atom_id=atom_id)
        db.add(progress)

    # Logique simple : on le marque comme complété avec 100%
    progress.status = 'completed'
    progress.strength = 1.0 
    
    db.commit()
    db.refresh(progress)
    
    return {"status": "success", "progress": progress}
