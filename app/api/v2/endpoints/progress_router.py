# Fichier: backend/app/api/v2/endpoints/progress_router.py (FINAL)
from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.schemas.progress import progress_schema
from app.crud.course import chapter_crud
from app.crud import progress_crud
from app.api.v2 import dependencies
from app.api.v2.dependencies import get_db, get_current_user
from app.models.progress import user_answer_log_model
from app.models.course import knowledge_component_model, knowledge_graph_model
from app.schemas.progress.progress_schema import AnswerCreate, AnswerResult, AnswerLogCreate
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.user.user_model import User
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Any

router = APIRouter()

# --- NOUVEAUX SCHÉMAS POUR LE CHAT ---
class ChatMessage(BaseModel):
    author: str
    message: str

class ContinueDiscussionRequest(BaseModel):
    history: List[ChatMessage]
    user_message: str
# ------------------------------------


from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User
from app.services.progress_service import ProgressService
from app.schemas.capsule.capsule_schema import CapsuleProgressRead # Créez ce schéma Pydantic

router = APIRouter()


@router.post("/activity/start", response_model=dict, summary="Démarrer le suivi d'une activité")
def start_user_activity(
    data: dict, # ex: {"capsule_id": 1, "atom_id": 1}
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProgressService(db, current_user.id)
    log_id = service.start_activity(data.get("capsule_id"), data.get("atom_id"))
    return {"log_id": log_id}

@router.post("/activity/end", response_model=dict, summary="Arrêter le suivi d'une activité")
def end_user_activity(
    data: dict, # ex: {"log_id": 123}
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProgressService(db, current_user.id)
    service.end_activity(data.get("log_id"))
    return {"status": "success"}

@router.get("/stats", response_model=dict, summary="Récupérer les stats de l'utilisateur")
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProgressService(db, current_user.id)
    return service.get_user_stats()

@router.post("/atom/{atom_id}/complete", response_model=CapsuleProgressRead, summary="Marquer un atome comme terminé")
def complete_atom(
    atom_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Appelé par le frontend quand un utilisateur termine une activité (atome).
    Met à jour l'XP et retourne la nouvelle progression.
    """
    progress_service = ProgressService(db=db, user_id=current_user.id)
    updated_progress = progress_service.record_atom_completion(atom_id)
    return updated_progress


@router.post("/log-answer", status_code=201)
def log_user_answer(
    answer_data: AnswerLogCreate,
    db: Session = Depends(dependencies.get_db),
    current_user: User = Depends(dependencies.get_current_user),
):
    """Enregistre la réponse d'un utilisateur à un exercice."""
    answer_log = UserAnswerLog(
        user_id=current_user.id,
        atom_id=answer_data.atom_id,
        is_correct=answer_data.is_correct,
        user_answer_json=answer_data.user_answer
    )
    db.add(answer_log)
    db.commit()
    return {"message": "Answer logged successfully"}

def _is_qcm_correct(correct_option: Any, user_answer: Any) -> bool:
    """
    Compare intelligemment la réponse d'un QCM, que les entrées soient
    des lettres (a, b, c...), des index (0, 1, 2...), ou le texte complet.
    """
    if correct_option is None or user_answer is None:
        return False

    # Dictionnaire de mapping pour la conversion lettre <-> index
    letter_to_index = {'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4, 'f': 5}
    index_to_letter = {v: k for k, v in letter_to_index.items()}

    try:
        # 1. Normaliser la bonne réponse (la convertir en index numérique)
        correct_index = -1
        correct_str = str(correct_option).strip().lower()
        if correct_str in letter_to_index:
            correct_index = letter_to_index[correct_str]
        elif correct_str.isdigit():
            correct_index = int(correct_str)

        # 2. Normaliser la réponse de l'utilisateur (la convertir en index numérique)
        user_index = -1
        user_str = str(user_answer).strip().lower()
        
        # Cas 1: L'utilisateur envoie l'index directement (ex: 0)
        if user_str.isdigit():
            user_index = int(user_str)
        # Cas 2: L'utilisateur envoie le texte complet (ex: "a) Croyance...")
        else:
            first_char = user_str.split(')')[0].strip()
            if first_char in letter_to_index:
                user_index = letter_to_index[first_char]

        # 3. Comparer les index normalisés
        if correct_index != -1 and user_index != -1:
            return correct_index == user_index

    except Exception:
        return False
        
    return False


@router.post("/answer", response_model=AnswerResult)
def submit_answer(
    payload: AnswerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Traite la réponse d'un utilisateur à un exercice, avec une logique de validation QCM robuste.
    """
    component = None
    exercise_type = None
    print("HEEERE :::: ",payload )
    lang_component = db.get(knowledge_component_model.KnowledgeComponent, payload.component_id)
    if lang_component:
        component = lang_component
        exercise_type = "language"
    
    if not component:
        philo_exercise = db.get(knowledge_graph_model.NodeExercise, payload.component_id)
        if philo_exercise:
            component = philo_exercise
            exercise_type = "philosophy"

    if not component:
        return AnswerResult(
            status="error",
            feedback="Composant d'exercice non trouvé.",
            is_correct=False
        )

    is_correct = False
    feedback_text = "Votre réponse a été enregistrée."

    # --- NOUVELLE LOGIQUE DE VALIDATION QCM AMÉLIORÉE ---
    if component.component_type == 'qcm':
        correct_answer = component.content_json.get("correct_option")
        user_answer = payload.user_answer_json.get("selected_option")
        
        if _is_qcm_correct(correct_answer, user_answer):
            is_correct = True
            feedback_text = "Bonne réponse !"
        else:
            feedback_text = "Ce n'est pas la bonne réponse. Essayez encore !"
    
    elif component.component_type in ['writing', 'essay']:
        is_correct = True 
        feedback_text = "Votre réponse a été soumise pour analyse."

    # --- Le reste de la fonction est correct ---
    log_entry = user_answer_log_model.UserAnswerLog(
        user_id=current_user.id,
        component_id=payload.component_id if exercise_type == "language" else None,
        node_exercise_id=payload.component_id if exercise_type == "philosophy" else None,
        status="correct" if is_correct else "incorrect",
        user_answer_json=payload.user_answer_json,
        ai_feedback={"text": feedback_text}
    )
    db.add(log_entry)
    db.commit()

    return AnswerResult(
        status="success",
        feedback=feedback_text,
        is_correct=is_correct
    )


@router.post("/discussion/{answer_log_id}/continue", response_model=Dict)
def continue_discussion(
    answer_log_id: int,
    request: ContinueDiscussionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Endpoint pour continuer une conversation avec l'IA."""
    updated_log = progress_crud.add_message_to_discussion(
        db=db, 
        answer_log_id=answer_log_id, 
        user=current_user,
        history=request.dict().get('history', []),
        user_message=request.user_message
    )
    if not updated_log:
        raise HTTPException(status_code=404, detail="Discussion non trouvée ou accès refusé.")
    
    # On renvoie le feedback complet qui contient le nouvel historique
    return updated_log.ai_feedback

@router.post("/reset/chapter/{chapter_id}", status_code=status.HTTP_200_OK)
def reset_chapter_answers(
    chapter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Réinitialise toutes les réponses d'un utilisateur pour un chapitre donné."""
    return progress_crud.reset_user_answers_for_chapter(db=db, user_id=current_user.id, chapter_id=chapter_id)

@router.post("/chapter/{chapter_id}/complete", status_code=status.HTTP_200_OK)
def mark_chapter_as_complete(
    chapter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marque un chapitre comme terminé et fait avancer la progression de l'utilisateur.
    Idéal pour les chapitres théoriques ou pour confirmer la fin d'un chapitre pratique.
    """
    chapter = chapter_crud.get_chapter_details(db, chapter_id=chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # On appelle la fonction existante qui gère la logique d'avancement
    progress_crud.advance_progress(db, user=current_user, chapter=chapter)
    
    return {"message": "Progress advanced successfully."}


@router.post("/nodes/{node_id}/complete", status_code=201)
def complete_knowledge_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Marque un nœud de connaissance comme terminé pour l'utilisateur actuel."""
    progress = progress_crud.mark_node_as_completed(db, user_id=current_user.id, node_id=node_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Impossible de trouver le nœud ou l'utilisateur.")
    return {"message": "Node marked as completed successfully."}


@router.post("/component/{component_id}/force-complete", status_code=200)
def force_complete_component(
    component_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    log_entry = None
    
    lang_component = db.get(knowledge_component_model.KnowledgeComponent, component_id)
    if lang_component:
        log_entry = user_answer_log_model.UserAnswerLog(
            user_id=current_user.id,
            component_id=component_id,
            status="incorrect",
            user_answer_json={"action": "force_complete_by_feedback"},
            # LA CORRECTION EST ICI
            ai_feedback={"text": "Exercice passé suite à un feedback."}
        )
    else:
        philo_exercise = db.get(knowledge_graph_model.NodeExercise, component_id)
        if philo_exercise:
            log_entry = user_answer_log_model.UserAnswerLog(
                user_id=current_user.id,
                node_exercise_id=component_id,
                status="incorrect",
                user_answer_json={"action": "force_complete_by_feedback"},
                # ET ICI
                ai_feedback={"text": "Exercice passé suite à un feedback."}
            )

    if not log_entry:
        raise HTTPException(status_code=404, detail="Composant d'exercice non trouvé (ni en langue, ni en philosophie).")

    db.add(log_entry)
    db.commit()
    return {"message": "Composant marqué comme complété."}