# Fichier: nanshe/backend/app/core/ai_service.py (VERSION REFACTORISÉE)

import json
import logging
import requests
import openai
import tiktoken 
import google.generativeai as genai
from sqlalchemy.orm import Session
from app.models.user.user_model import User
from app.models.analytics.ai_token_log_model import AITokenLog
from openai import OpenAI



from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core import prompt_manager
from app.utils.json_utils import safe_json_loads  # <-- util JSON robuste

logger = logging.getLogger(__name__)

MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # Ajoutez les autres modèles ici
}

try:
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
except Exception:
    encoding = tiktoken.get_encoding("cl100k_base")


def call_ai_and_log(
    db: Session,
    user: User,
    model_choice: str,
    system_prompt: str,
    user_prompt: str,
    feature_name: str
) -> Dict[str, Any]:
    """
    Wrapper qui appelle l'IA, compte les tokens, loggue les coûts, et retourne la réponse.
    """
    # Compter les tokens du prompt
    prompt_tokens = len(encoding.encode(system_prompt + user_prompt))
    
    # Appel à l'IA (en utilisant notre fonction existante)
    response_data = _call_ai_model_json(
        user_prompt=user_prompt,
        model_choice=model_choice,
        system_prompt=system_prompt
    )
    
    response_text = json.dumps(response_data)
    completion_tokens = len(encoding.encode(response_text))
    
    # Calculer le coût
    cost = 0.0
    if model_choice in MODEL_PRICING:
        prices = MODEL_PRICING[model_choice]
        cost = ((prompt_tokens / 1_000_000) * prices["input"]) + \
               ((completion_tokens / 1_000_000) * prices["output"])

    # Enregistrer dans la base de données
    log_entry = AITokenLog(
        user_id=user.id,
        feature=feature_name,
        model_name=model_choice,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost
    )
    db.add(log_entry)
    db.commit()
    
    return response_data

def _summarize_text_for_prompt(
    db: Session,
    user: User,
    text_to_summarize: str,
    prompt_name: str # ex: "toolbox.summarize_history"
) -> str:
    """
    Utilise un prompt spécifique pour résumer un texte et loggue l'appel.
    Retourne le résumé textuel.
    """
    system_prompt = prompt_manager.get_prompt(
        prompt_name,
        text_to_summarize=text_to_summarize,
        ensure_json=True
    )
    
    try:
        # On utilise call_ai_and_log pour le suivi des coûts
        response_data = call_ai_and_log(
            db=db,
            user=user,
            model_choice="openai_gpt4o-mini", # On utilise un modèle rapide
            system_prompt=system_prompt,
            user_prompt="Effectue la tâche de résumé demandée.",
            feature_name=f"summarizer_{prompt_name}"
        )
        return response_data.get("summary", text_to_summarize) # Fallback: retourne le texte original en cas d'erreur
    except Exception as e:
        logger.error(f"Échec de la summarisation avec le prompt {prompt_name}: {e}")

        
# ==============================================================================
# Configuration des Clients API
# ==============================================================================
try:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-pro-latest")
    logger.info("✅ Service IA Gemini (1.5 Pro) configuré.")
except Exception as e:
    gemini_model = None
    logger.error(f"❌ Erreur de configuration pour Gemini: {e}")

try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    logger.info("✅ Client OpenAI configuré.")
except Exception as e:
    openai_client = None
    logger.error(f"❌ Erreur de configuration pour OpenAI: {e}")



# ==============================================================================
# Fonctions Privées d'Appel aux IA
# ==============================================================================

def _call_gemini(prompt: str, temperature: Optional[float] = None) -> str:
    """Appel Gemini en JSON (mime type). Renvoie une STR (attendue JSON)."""
    if not gemini_model:
        raise ConnectionError("Le modèle Gemini n'est pas disponible.")
    try:
        gen_cfg = genai.types.GenerationConfig(
            response_mime_type="application/json",
            **({"temperature": temperature} if temperature is not None else {})
        )
        response = gemini_model.generate_content(prompt, generation_config=gen_cfg)
        return response.text
    except Exception as e:
        logger.error(f"Erreur lors de l'appel à l'API Gemini : {e}")
        raise

def _call_openai_llm(user_prompt: str, system_prompt: str = "", temperature: Optional[float] = None) -> str:
    """Appel OpenAI (JSON strict). Renvoie une STR (attendue JSON)."""
    if not openai_client:
        raise ConnectionError("Le client OpenAI n'est pas configuré. Vérifiez votre clé API.")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        logger.info("Appel à l'API OpenAI avec le modèle gpt-4o-mini")
        response = openai_client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=messages,
            response_format={"type": "json_object"},
            **({"temperature": temperature} if temperature is not None else {})
        )
        return response.choices[0].message.content
    except openai.APIError as e:
        logger.error(f"Une erreur API est survenue avec OpenAI : {e}")
        raise

def _call_local_llm(user_prompt: str, system_prompt: str = "", temperature: Optional[float] = None) -> str:
    """Appel LLM local via Ollama (format JSON). Renvoie une STR (attendue JSON)."""
    if not settings.LOCAL_LLM_URL:
        raise ConnectionError("L'URL du LLM local (Ollama) n'est pas configurée.")

    full_url = f"{settings.LOCAL_LLM_URL.rstrip('/')}/api/chat"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    payload: Dict[str, Any] = {
        "model": "llama3:8b",
        "messages": messages,
        "format": "json",
        "stream": False,
    }
    if temperature is not None:
        payload["options"] = {"temperature": temperature}

    try:
        response = requests.post(full_url, json=payload, timeout=120)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        if content and content.strip() not in ["{}", "[]"]:
            return content
        raise ValueError("Ollama a renvoyé une réponse vide ou malformée.")
    except requests.exceptions.RequestException as e:
        logger.error(f"ERREUR CRITIQUE lors de l'appel à Ollama : {e}")
        raise

# ==============================================================================
# Orchestrateur & Variante JSON avec retries
# ==============================================================================

def _call_ai_model(user_prompt: str, model_choice: str, system_prompt: str = "") -> str:
    """
    Chef d'orchestre de bas niveau : renvoie une STR (qui devrait être du JSON),
    pour compatibilité ascendante.
    """
    logger.info(f"Appel à l'IA avec le modèle : {model_choice}")
    if model_choice == "local":
        return _call_local_llm(user_prompt=user_prompt, system_prompt=system_prompt)
    elif model_choice.startswith("openai_"):
        return _call_openai_llm(user_prompt=user_prompt, system_prompt=system_prompt)
    else:  # Gemini par défaut
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        return _call_gemini(full_prompt)

def _call_ai_model_json(
    user_prompt: str,
    model_choice: str,
    system_prompt: str = "",
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Appelle _call_ai_model puis parse en JSON avec safe_json_loads.
    En cas d'échec, réessaye avec un 'repair hint' et une température abaissée.
    """
    last_exc: Optional[Exception] = None
    sys_base = system_prompt or ""
    repair = (
        "\n\n[CONTRAINTE DE SORTIE]\n"
        "- Ta réponse précédente n'était pas un JSON valide.\n"
        "- Réponds STRICTEMENT avec un unique objet JSON valide.\n"
        "- Pas de backticks, pas de commentaires, pas de texte hors JSON."
    )

    for attempt in range(max_retries + 1):
        temp = 0.2 if attempt > 0 else None
        sys_used = sys_base if attempt == 0 else (sys_base + repair)
        try:
            if model_choice == "local":
                raw = _call_local_llm(user_prompt=user_prompt, system_prompt=sys_used, temperature=temp)
            elif model_choice.startswith("openai_"):
                raw = _call_openai_llm(user_prompt=user_prompt, system_prompt=sys_used, temperature=temp)
            else:
                full_prompt = f"{sys_used}\n\n{user_prompt}"
                raw = _call_gemini(full_prompt, temperature=temp)

            return safe_json_loads(raw)
        except Exception as e:
            last_exc = e
            logger.warning(f"Tentative JSON {attempt+1}/{max_retries+1} échouée: {e}")

    raise last_exc if last_exc else RuntimeError("Échec d'appel JSON sans exception d'origine.")

# ==============================================================================
# Fonctions de Planification et Génération de Cours
# ==============================================================================

def classify_course_topic(title: str, model_choice: str) -> str:
    system_prompt = prompt_manager.get_prompt("course_planning.classify_topic", ensure_json=True)
    try:
        data = _call_ai_model_json(title, model_choice, system_prompt=system_prompt)
        return data.get("category", "general")
    except Exception as e:
        logger.error(f"Erreur de classification pour '{title}': {e}")
        return "general"

def generate_learning_plan(title: str, course_type: str, model_choice: str) -> dict:
    system_prompt = prompt_manager.get_prompt("course_planning.generic_plan", ensure_json=True)
    user_prompt = f"Sujet du cours : {title}. Catégorie : {course_type}."
    try:
        return _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"Erreur de plan de cours pour '{title}': {e}")
        return {}

def generate_adaptive_learning_plan(title: str, personalization_details: Dict[str, Any], model_choice: str) -> dict:
    user_context = json.dumps(personalization_details, ensure_ascii=False)
    system_prompt = prompt_manager.get_prompt(
        "course_planning.adaptive_plan",
        user_context=user_context,
        ensure_json=True
    )
    try:
        return _call_ai_model_json(title, model_choice, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"Erreur de plan de cours adapté pour '{title}': {e}")
        return {}

def generate_personalization_questions(title: str, model_choice: str) -> Dict[str, Any]:
    logger.info(f"IA - Génération des questions de personnalisation pour '{title}'")
    system_prompt = prompt_manager.get_prompt(
        "course_planning.personalization_questions",
        title=title,
        ensure_json=True
    )
    user_prompt = f"Génère les questions de personnalisation pour un cours sur : {title}"
    try:
        data = _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)

        # Normalisation des options de select
        if "fields" in data:
            for field in data["fields"]:
                if field.get("type") == "select" and "options" in field:
                    corrected = []
                    for opt in field["options"]:
                        if isinstance(opt, dict):
                            corrected.append(opt)
                        else:
                            corrected.append({"value": str(opt).lower().replace(" ", "_"), "label": str(opt)})
                    field["options"] = corrected

        if "fields" in data and isinstance(data["fields"], list):
            return data

        # fallback si la racine n'est pas conforme
        for key, value in data.items():
            if isinstance(value, list):
                return {"fields": value}

        raise ValueError("La réponse de l'IA ne contient aucune liste de champs valide.")
    except Exception as e:
        logger.error(f"Erreur de génération du formulaire pour '{title}': {e}", exc_info=True)
        return {"fields": []}

# ==============================================================================
# Fonctions de Génération de Contenu Générique
# ==============================================================================

def generate_chapter_plan_for_level(
    level_title: str,
    model_choice: str,
    user_context: Optional[str] = None,
) -> List[str]:
    system_prompt = prompt_manager.get_prompt(
        "generic_content.chapter_plan",
        user_context=user_context,
        ensure_json=True,
    )
    try:
        data = _call_ai_model_json(level_title, model_choice, system_prompt=system_prompt)
        return data.get("chapters", []) or []
    except Exception as e:
        logger.error(f"Erreur de plan de chapitre pour '{level_title}': {e}")
        return []

def generate_lesson_for_chapter(chapter_title: str, model_choice: str) -> str:
    system_prompt = prompt_manager.get_prompt("generic_content.lesson", ensure_json=True)
    try:
        data = _call_ai_model_json(chapter_title, model_choice, system_prompt=system_prompt)
        return data.get("lesson_text", "") or ""
    except Exception as e:
        logger.error(f"Erreur de génération de leçon pour '{chapter_title}': {e}")
        return ""

def generate_exercises_for_lesson(
    lesson_text: str,
    chapter_title: str,
    course_type: str,
    model_choice: str
) -> List[Dict[str, Any]]:
    logger.info(f"Génération des exercices pour le chapitre '{chapter_title}' (Type: {course_type})")
    exercise_types = ["qcm", "fill_in_the_blank", "discussion"]
    if course_type == "langue":
        exercise_types.extend(["character_recognition", "association_drag_drop", "sentence_construction"])

    system_prompt = prompt_manager.get_prompt(
        "generic_content.exercises",
        course_type=course_type,
        chapter_title=chapter_title,
        exercise_types=json.dumps(exercise_types, ensure_ascii=False),
        ensure_json=True
    )
    try:
        data = _call_ai_model_json(lesson_text, model_choice, system_prompt=system_prompt)
        exercises = data.get("exercises", []) or []
        return [ex for ex in exercises if ex.get("content_json")]
    except Exception as e:
        logger.error(f"Erreur de génération d'exercices pour '{chapter_title}': {e}", exc_info=True)
        return []

# ==============================================================================
# Fonctions Pédagogiques Spécifiques aux Langues
# ==============================================================================

def generate_language_pedagogical_content(
    course_title: str,
    chapter_title: str,
    model_choice: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Retourne un dict avec clés: 'vocabulary', 'grammar', (évent. 'phrases'...).
    """
    logger.info(f"IA Service: Génération du contenu pédagogique pour '{chapter_title}' (Cours: {course_title})")
    system_prompt = prompt_manager.get_prompt(
        "language_generation.pedagogical_content",
        course_title=course_title,
        chapter_title=chapter_title,
        ensure_json=True,
        **kwargs  # ex: lang_code="ja", items_per_chapter=12, etc.
    )
    user_prompt = f"Génère le contenu pour le chapitre '{chapter_title}' du cours '{course_title}'."
    try:
        data = _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
        # garde-fous
        data["vocabulary"] = data.get("vocabulary") or []
        data["grammar"] = data.get("grammar") or []
        return data
    except Exception as e:
        logger.error(f"Erreur de génération de contenu pédagogique pour '{chapter_title}': {e}")
        return {"vocabulary": [], "grammar": []}

def generate_language_dialogue(
    course_title: str,
    chapter_title: str,
    vocabulary: list,
    grammar: list,
    model_choice: str,
    **kwargs
) -> str:
    """
    Retourne une STRING JSON (le contenu de la clé 'dialogue' sérialisé) pour
    stockage dans un champ texte. Si besoin tu peux json.loads côté lecture.
    """
    logger.info(f"IA Service: Génération du dialogue pour '{chapter_title}' (Cours: {course_title})")
    # On passe seulement ce qui est utile (id/term/rule_name) pour éviter les prompts géants
    vocab_refs = ", ".join([f"{it.get('id','') or it.get('term','')}" for it in vocabulary])
    grammar_refs = ", ".join([f"{gr.get('id','') or gr.get('rule_name','')}" for gr in grammar])

    system_prompt = prompt_manager.get_prompt(
        "language_generation.dialogue",
        course_title=course_title,
        chapter_title=chapter_title,
        target_cefr=kwargs.get("target_cefr", "A1"),
        max_turns=kwargs.get("max_turns", 8),
        include_transliteration=kwargs.get("include_transliteration"),
        include_french_gloss=kwargs.get("include_french_gloss"),
        vocab_refs=vocab_refs,
        grammar_refs=grammar_refs,
        ensure_json=True
    )

    try:
        data = _call_ai_model_json("Écris le dialogue maintenant.", model_choice, system_prompt=system_prompt)
        dlg = data.get("dialogue")
        # On renvoie une STRING JSON (pour stockage dans un champ texte)
        if dlg is None:
            return "Erreur: Le dialogue n'a pas pu être généré."
        return json.dumps(dlg, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erreur de génération de dialogue pour '{chapter_title}': {e}")
        return "Le dialogue n'a pas pu être généré en raison d'une erreur technique."


def generate_writing_system_lesson(
    course_title: str,
    chapter_title: str,
    model_choice: str,
    **kwargs
) -> str:
    """
    Génère une leçon textuelle explicative pour un chapitre théorique (ex: alphabet).
    """
    logger.info(f"IA Service: Génération de la leçon théorique pour '{chapter_title}'")
    system_prompt = prompt_manager.get_prompt(
        "language_generation.writing_system_lesson",
        course_title=course_title,
        chapter_title=chapter_title,
        ensure_json=True,
        **kwargs
    )
    user_prompt = "Rédige la leçon pour ce chapitre théorique."
    try:
        data = _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
        return data.get("lesson_text", "") or ""
    except Exception as e:
        logger.error(f"Erreur de génération de leçon théorique pour '{chapter_title}': {e}")
        return "Erreur lors de la génération de cette leçon."


# ==============================================================================
# Fonctions d'Analyse des Réponses Complexes
# ==============================================================================

def analyze_user_essay(prompt: str, guidelines: str, user_essay: str, model_choice: str) -> Dict[str, Any]:
    system_prompt = prompt_manager.get_prompt(
        "analysis.analyze_essay",
        prompt=prompt,
        guidelines=guidelines,
        ensure_json=True
    )
    user_prompt = f"Voici l'essai : \"{user_essay}\""
    try:
        return _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de l'essai: {e}")
        return {"evaluation": "L'analyse a échoué.", "is_validated": False}

def start_ai_discussion(prompt: str, user_first_post: str, model_choice: str) -> Dict[str, Any]:
    system_prompt = prompt_manager.get_prompt("analysis.start_discussion", prompt=prompt, ensure_json=True)
    user_prompt = f"Première intervention de l'utilisateur : \"{user_first_post}\""
    try:
        data = _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
        data["history"] = [
            {"author": "user", "message": user_first_post},
            {"author": "ia", "message": data.get("response_text")}
        ]
        data["is_validated"] = False
        return data
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la discussion: {e}")
        return {"response_text": "Je n'ai pas bien compris. Pouvez-vous reformuler ?", "is_validated": False}

def continue_ai_discussion(prompt: str, history: List[Dict[str, str]], user_message: str, model_choice: str) -> Dict[str, Any]:
    history_str = "\n".join([f"{msg['author']}: {msg['message']}" for msg in history])
    system_prompt = prompt_manager.get_prompt(
        "analysis.continue_discussion",
        prompt=prompt,
        history_str=history_str,
        ensure_json=True
    )
    user_prompt = f"Nouveau message de l'utilisateur : \"{user_message}\""
    try:
        return _call_ai_model_json(user_prompt, model_choice, system_prompt=system_prompt)
    except Exception as e:
        logger.error(f"Erreur lors de la continuation de la discussion: {e}")
        return {"response_text": "Je rencontre un problème technique.", "is_complete": False}
