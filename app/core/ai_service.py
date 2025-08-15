# Fichier: nanshe/backend/app/core/ai_service.py (VERSION REFACTORISÉE)

import json
import logging
import requests
import openai
from openai import OpenAI
import google.generativeai as genai

from app.core.config import settings
from app.core import prompt_manager
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# --- Configuration des Clients API (inchangée) ---
try:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-pro-latest')
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
# Fonctions Privées d'Appel aux IA (inchangées)
# ==============================================================================
def _call_gemini(prompt: str) -> str:
    """Fonction privée pour appeler l'API Gemini."""
    if not gemini_model:
        raise ConnectionError("Le modèle Gemini n'est pas disponible.")
    try:
        response = gemini_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
        )
        return response.text
    except Exception as e:
        logger.error(f"Erreur lors de l'appel à l'API Gemini : {e}")
        raise

def _call_openai_llm(user_prompt: str, system_prompt: str = "") -> str:
    """Fonction privée pour appeler l'API OpenAI avec une extraction JSON robuste."""
    if not openai_client:
        raise ConnectionError("Le client OpenAI n'est pas configuré. Vérifiez votre clé API.")

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    try:
        logger.info(f"Appel à l'API OpenAI avec le modèle gpt-4o-mini")
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except openai.APIError as e:
        logger.error(f"Une erreur API est survenue avec OpenAI : {e}")
        raise

def _call_local_llm(user_prompt: str, system_prompt: str = "") -> str:
    """Fonction privée pour appeler le LLM local via Ollama."""
    if not settings.LOCAL_LLM_URL:
        raise ConnectionError("L'URL du LLM local (Ollama) n'est pas configurée.")
    
    full_url = f"{settings.LOCAL_LLM_URL.rstrip('/')}/api/chat"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    payload = {"model": "llama3:8b", "messages": messages, "format": "json", "stream": False}
    
    try:
        response = requests.post(full_url, json=payload, timeout=120)
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        if content and content.strip() not in ['{}', '[]']:
            return content
        raise ValueError("Ollama a renvoyé une réponse vide ou malformée.")
    except requests.exceptions.RequestException as e:
        logger.error(f"ERREUR CRITIQUE lors de l'appel à Ollama : {e}")
        raise

def _call_ai_model(user_prompt: str, model_choice: str, system_prompt: str = "") -> str:
    """Chef d'orchestre : choisit quel modèle appeler."""
    logger.info(f"Appel à l'IA avec le modèle : {model_choice}")
    if model_choice == 'local':
        return _call_local_llm(user_prompt=user_prompt, system_prompt=system_prompt)
    elif model_choice.startswith('openai_'):
        return _call_openai_llm(user_prompt=user_prompt, system_prompt=system_prompt)
    else: # Gemini par défaut
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        return _call_gemini(full_prompt)

# ==============================================================================
# Fonctions de Planification et Génération de Cours
# ==============================================================================

def classify_course_topic(title: str, model_choice: str) -> str:
    system_prompt = prompt_manager.get_prompt("course_planning.classify_topic")
    try:
        response_str = _call_ai_model(title, model_choice, system_prompt=system_prompt)
        return json.loads(response_str).get("category", "general")
    except Exception as e:
        logger.error(f"Erreur de classification pour '{title}': {e}")
        return "general"

def generate_learning_plan(title: str, course_type: str, model_choice: str) -> dict:
    system_prompt = prompt_manager.get_prompt("course_planning.generic_plan")
    user_prompt = f"Sujet du cours : {title}. Catégorie : {course_type}."
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur de plan de cours pour '{title}': {e}")
        return {}

def generate_adaptive_learning_plan(title: str, personalization_details: Dict[str, Any], model_choice: str) -> dict:
    user_context = json.dumps(personalization_details, ensure_ascii=False)
    system_prompt = prompt_manager.get_prompt(
        "course_planning.adaptive_plan",
        user_context=user_context
    )
    try:
        response_str = _call_ai_model(title, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur de plan de cours adapté pour '{title}': {e}")
        return {}

def generate_personalization_questions(title: str, model_choice: str) -> Dict[str, Any]:
    logger.info(f"IA - Génération des questions de personnalisation pour '{title}'")
    system_prompt = prompt_manager.get_prompt(
        "course_planning.personalization_questions",
        title=title
    )
    user_prompt = f"Génère les questions de personnalisation pour un cours sur : {title}"
    try:
        # ... (la logique de correction automatique reste ici, elle est très utile)
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        data = json.loads(response_str)
        if "fields" in data:
            for field in data["fields"]:
                if field.get("type") == "select" and "options" in field:
                    corrected_options = [
                        opt if isinstance(opt, dict) else {
                            "value": str(opt).lower().replace(" ", "_"), "label": str(opt)
                        } for opt in field["options"]
                    ]
                    field["options"] = corrected_options
        if "fields" in data and isinstance(data["fields"], list): return data
        for key, value in data.items():
            if isinstance(value, list): return {"fields": value}
        raise ValueError("La réponse de l'IA ne contient aucune liste de champs valide.")
    except Exception as e:
        logger.error(f"Erreur de génération du formulaire pour '{title}': {e}", exc_info=True)
        return {"fields": []}

# ==============================================================================
# Fonctions de Génération de Contenu Générique
# ==============================================================================

def generate_chapter_plan_for_level(level_title: str, model_choice: str) -> List[str]:
    system_prompt = prompt_manager.get_prompt("generic_content.chapter_plan")
    try:
        response_str = _call_ai_model(level_title, model_choice, system_prompt=system_prompt)
        return json.loads(response_str).get("chapters", [])
    except Exception as e:
        logger.error(f"Erreur de plan de chapitre pour '{level_title}': {e}")
        return []

def generate_lesson_for_chapter(chapter_title: str, model_choice: str) -> str:
    system_prompt = prompt_manager.get_prompt("generic_content.lesson")
    try:
        response_str = _call_ai_model(chapter_title, model_choice, system_prompt=system_prompt)
        return json.loads(response_str).get("lesson_text", "")
    except Exception as e:
        logger.error(f"Erreur de génération de leçon pour '{chapter_title}': {e}")
        return ""

def generate_exercises_for_lesson(lesson_text: str, chapter_title: str, course_type: str, model_choice: str) -> List[Dict[str, Any]]:
    logger.info(f"Génération des exercices pour le chapitre '{chapter_title}' (Type: {course_type})")
    exercise_types = ["qcm", "fill_in_the_blank", "discussion"]
    if course_type == 'langue':
        exercise_types.extend(["character_recognition", "association_drag_drop", "sentence_construction"])
    
    system_prompt = prompt_manager.get_prompt(
        "generic_content.exercises",
        course_type=course_type,
        chapter_title=chapter_title,
        exercise_types=json.dumps(exercise_types)
    )
    try:
        response_str = _call_ai_model(lesson_text, model_choice, system_prompt=system_prompt)
        data = json.loads(response_str)
        exercises = data.get("exercises", [])
        return [ex for ex in exercises if ex.get("content_json")]
    except Exception as e:
        logger.error(f"Erreur de génération d'exercices pour '{chapter_title}': {e}", exc_info=True)
        return []

# ==============================================================================
# Fonctions Pédagogiques Spécifiques aux Langues
# ==============================================================================

def generate_language_pedagogical_content(course_title: str, chapter_title: str, model_choice: str) -> Dict[str, Any]:
    logger.info(f"IA Service: Génération du contenu pédagogique pour '{chapter_title}' (Cours: {course_title})")
    system_prompt = prompt_manager.get_prompt(
        "language_generation.pedagogical_content",
        course_title=course_title,
        chapter_title=chapter_title
    )
    user_prompt = f"Génère le contenu pour le chapitre '{chapter_title}' du cours '{course_title}'."
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur de génération de contenu pédagogique pour '{chapter_title}': {e}")
        return {"vocabulary": [], "grammar": []}

def generate_language_dialogue(course_title: str, chapter_title: str, vocabulary: list, grammar: list, model_choice: str) -> str:
    logger.info(f"IA Service: Génération du dialogue pour '{chapter_title}' (Cours: {course_title})")
    vocab_str = ", ".join([f"'{item['term']}' ({item['translation']})" for item in vocabulary])
    grammar_str = " et ".join([f"'{rule['rule_name']}'" for rule in grammar])
    system_prompt = prompt_manager.get_prompt(
        "language_generation.dialogue",
        course_title=course_title,
        chapter_title=chapter_title,
        vocab_str=vocab_str,
        grammar_str=grammar_str
    )
    try:
        response_str = _call_ai_model("Écris le dialogue maintenant.", model_choice, system_prompt=system_prompt)
        return json.loads(response_str).get("dialogue", "Erreur: Le dialogue n'a pas pu être généré.")
    except Exception as e:
        logger.error(f"Erreur de génération de dialogue pour '{chapter_title}': {e}")
        return "Le dialogue n'a pas pu être généré en raison d'une erreur technique."

# ==============================================================================
# Fonctions d'Analyse des Réponses Complexes
# ==============================================================================

def analyze_user_essay(prompt: str, guidelines: str, user_essay: str, model_choice: str) -> Dict[str, Any]:
    system_prompt = prompt_manager.get_prompt(
        "analysis.analyze_essay",
        prompt=prompt,
        guidelines=guidelines
    )
    user_prompt = f"Voici l'essai : \"{user_essay}\""
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de l'essai: {e}")
        return {"evaluation": "L'analyse a échoué.", "is_validated": False}

def start_ai_discussion(prompt: str, user_first_post: str, model_choice: str) -> Dict[str, Any]:
    system_prompt = prompt_manager.get_prompt("analysis.start_discussion", prompt=prompt)
    user_prompt = f"Première intervention de l'utilisateur : \"{user_first_post}\""
    try:
        # ... (la logique pour initialiser l'historique reste ici)
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        response_data = json.loads(response_str)
        response_data['history'] = [
            {"author": "user", "message": user_first_post},
            {"author": "ia", "message": response_data.get("response_text")}
        ]
        response_data["is_validated"] = False
        return response_data
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la discussion: {e}")
        return {"response_text": "Je n'ai pas bien compris. Pouvez-vous reformuler ?", "is_validated": False}

def continue_ai_discussion(prompt: str, history: List[Dict[str, str]], user_message: str, model_choice: str) -> Dict[str, Any]:
    history_str = "\n".join([f"{msg['author']}: {msg['message']}" for msg in history])
    system_prompt = prompt_manager.get_prompt(
        "analysis.continue_discussion",
        prompt=prompt,
        history_str=history_str
    )
    user_prompt = f"Nouveau message de l'utilisateur : \"{user_message}\""
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur lors de la continuation de la discussion: {e}")
        return {"response_text": "Je rencontre un problème technique.", "is_complete": False}