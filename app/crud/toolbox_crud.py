"""Logique métier du coach IA, alignée sur le modèle Capsule."""

import json
import logging
import re
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import ai_service
from app.crud import coach_conversation_crud, coach_energy_crud
from app.models.capsule import capsule_model, granule_model, molecule_model, atom_model
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.user.user_model import User
from app.services.srs_service import SRSService

logger = logging.getLogger(__name__)


def _extract_capsule_id(context: dict) -> int | None:
    """Tente de retrouver un identifiant de capsule à partir du contexte frontend."""

    if not context:
        return None

    candidates = []
    for key in ("capsuleId", "capsule_id", "capsuleid", "id"):
        value = context.get(key)
        if value is not None:
            candidates.append(value)

    params = context.get("params")
    if isinstance(params, dict):
        for key in ("capsuleId", "capsule_id"):
            if key in params:
                candidates.append(params[key])

    for value in candidates:
        try:
            return int(value)
        except (TypeError, ValueError):
            continue

    path = context.get("path")
    if isinstance(path, str):
        match = re.search(r"/capsule/(?:[^/]+/){0,2}(\d+)", path)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    return None


def _extract_molecule_id(context: dict) -> int | None:
    """Essaye d'extraire un identifiant de molécule depuis le contexte frontend."""

    if not context:
        return None

    candidates = []
    for key in ("moleculeId", "molecule_id", "moleculeid"):
        value = context.get(key)
        if value is not None:
            candidates.append(value)

    molecule_context = context.get("molecule")
    if isinstance(molecule_context, dict):
        for key in ("id", "moleculeId", "molecule_id"):
            value = molecule_context.get(key)
            if value is not None:
                candidates.append(value)

    params = context.get("params")
    if isinstance(params, dict):
        for key in ("moleculeId", "molecule_id"):
            if key in params:
                candidates.append(params[key])

    for value in candidates:
        try:
            return int(value)
        except (TypeError, ValueError):
            continue

    path = context.get("path")
    if isinstance(path, str):
        match = re.search(r"molecule/(\d+)", path)
        if not match:
            match = re.search(r"moleculeId=(\d+)", path)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    return None


def _format_recent_errors(errors: list[UserAnswerLog]) -> str:
    if not errors:
        return "Aucune erreur récente détectée."

    rows = []
    for log in errors:
        atom_title = getattr(log.atom, "title", "Exercice")
        answer = json.dumps(log.user_answer_json, ensure_ascii=False)
        rows.append(f"- {atom_title} → réponse {answer}")
    return "\n".join(rows)


def ask_coach(
    db: Session,
    user: User,
    message: str,
    context: dict,
    history: list,
    quick_action: str | None = None,
    selection: dict | None = None,
) -> dict:
    """Produit une réponse contextualisée par capsule pour le coach IA."""

    energy_status = coach_energy_crud.consume_energy(db, user)

    capsule_id = _extract_capsule_id(context or {})
    capsule = db.get(capsule_model.Capsule, capsule_id) if capsule_id else None

    molecule_id = _extract_molecule_id(context or {})
    molecule = db.get(molecule_model.Molecule, molecule_id) if molecule_id else None
    if molecule and capsule is None:
        granule = getattr(molecule, "granule", None)
        capsule = getattr(granule, "capsule", None)

    weak_topics: list[str] = []
    recent_errors: list[UserAnswerLog] = []
    focus_description = ""
    srs_digest = {"reviews": "", "errors": ""}

    if capsule:
        # Identifier les molécules qui posent problème (basé sur les erreurs récentes)
        weak_topics_query = (
            db.query(molecule_model.Molecule.title, func.count(UserAnswerLog.id))
            .join(atom_model.Atom, molecule_model.Molecule.atoms)
            .join(UserAnswerLog, UserAnswerLog.atom_id == atom_model.Atom.id)
            .join(granule_model.Granule)
            .filter(
                UserAnswerLog.user_id == user.id,
                granule_model.Granule.capsule_id == capsule.id,
                UserAnswerLog.is_correct.is_(False),
            )
            .group_by(molecule_model.Molecule.title)
            .order_by(func.count(UserAnswerLog.id).desc())
            .limit(3)
            .all()
        )
        weak_topics = [f"{title} ({errors} erreurs)" for title, errors in weak_topics_query]

        # Récupérer les exercices récemment échoués
        recent_errors = (
            db.query(UserAnswerLog)
            .join(atom_model.Atom)
            .join(molecule_model.Molecule)
            .join(granule_model.Granule)
            .filter(
                UserAnswerLog.user_id == user.id,
                granule_model.Granule.capsule_id == capsule.id,
                UserAnswerLog.is_correct.is_(False),
            )
            .order_by(UserAnswerLog.created_at.desc())
            .limit(5)
            .all()
        )

        granule_order = context.get("granuleOrder") or context.get("levelOrder")
        molecule_order = context.get("moleculeOrder") or context.get("chapterIndex")
        if granule_order and molecule_order:
            try:
                granule = (
                    db.query(granule_model.Granule)
                    .filter_by(capsule_id=capsule.id, order=int(granule_order))
                    .first()
                )
                focus_molecule = (
                    db.query(molecule_model.Molecule)
                    .filter_by(granule_id=granule.id if granule else None, order=int(molecule_order))
                    .first()
                )
                if focus_molecule:
                    focus_description = f"Travail en cours sur la leçon '{focus_molecule.title}'."
            except (ValueError, TypeError):
                logger.debug("Impossible d'interpréter granule/molecule depuis le contexte: %s", context)

        srs_service = SRSService(db=db, user=user)
        srs_digest = srs_service.coach_digest(capsule_id=capsule.id)

    capsule_details = (
        f"Capsule : {capsule.title} — Domaine {capsule.domain} / Aire {capsule.area} — Compétence {capsule.main_skill}."
        if capsule
        else "Capsule non identifiée (mode générique)."
    )

    weak_topics_text = "\n".join(weak_topics) if weak_topics else "Aucun sujet faible identifié pour l'instant."
    recent_errors_text = _format_recent_errors(recent_errors)

    history_text = "\n".join(
        f"{msg.get('author', 'user')}: {msg.get('message', '')}"
        for msg in (history or [])
    )

    selection_text = ''
    if selection and selection.get('text'):
        text_snippet = selection['text'][:2000]
        selection_text = f"\nContenu sélectionné par l'utilisateur :\n{text_snippet}"

    quick_action_text = ''
    if quick_action:
        quick_action_text = f"\nAction rapide détectée : {quick_action}."

    system_prompt = f"""
Tu es un coach IA bienveillant aidant un apprenant sur la capsule suivante :
{capsule_details}
{focus_description}
{quick_action_text}
{selection_text}

Contexte sur l'historique de discussion :
{history_text or 'Aucun historique.'}

Points faibles détectés :
{weak_topics_text}

Erreurs récentes :
{recent_errors_text}

SRS à traiter :
{srs_digest['reviews']}

Carnet d'erreurs synthétique :
{srs_digest['errors']}

Donne des conseils courts, concrets et motivants.
Réponds exclusivement en JSON avec la structure suivante :
{{
  "response": "Texte principal (max 4 phrases)",
  "suggestions": ["Bullet point optionnel", "..."],
  "next_steps": ["Action concrète à réaliser", "..."]
}}
""".strip()

    location, location_capsule_id, location_molecule_id = coach_conversation_crud.determine_location(
        capsule=capsule,
        molecule=molecule,
    )
    thread = coach_conversation_crud.get_or_create_thread(
        db,
        user,
        location=location,
        capsule_id=location_capsule_id,
        molecule_id=location_molecule_id,
    )

    user_message_content = message.strip()
    if not user_message_content:
        user_message_content = message

    coach_conversation_crud.append_user_message(
        db,
        thread,
        content=user_message_content,
        payload={
            "context": context,
            "quick_action": quick_action,
            "selection": selection,
        },
    )

    try:
        response_data = ai_service.call_ai_and_log(
            db=db,
            user=user,
            model_choice="openai_gpt4o_mini",
            system_prompt=system_prompt,
            user_prompt=message,
            feature_name="coach_ia",
        )
        response_text = response_data.get("response", json.dumps(response_data, ensure_ascii=False))
        coach_conversation_crud.append_coach_message(
            db,
            thread,
            content=response_text,
            payload={"raw_response": response_data},
        )
        return {"response": response_text, "energy": energy_status, "thread_id": thread.id}
    except Exception as exc:
        logger.error("Coach IA indisponible: %s", exc, exc_info=True)
        fallback = "Désolé, je ne parviens pas à répondre pour le moment."
        coach_conversation_crud.append_coach_message(
            db,
            thread,
            content=fallback,
            payload={"error": str(exc)},
        )
        return {
            "response": fallback,
            "energy": energy_status,
            "thread_id": thread.id,
        }
