# Fichier: backend/app/core/ai_service.py (VERSION FINALE COMPLÈTE)
import google.generativeai as genai
import json
import logging
import requests
import openai
from openai import OpenAI
from app.core.config import settings
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# --- Configuration des Clients API ---
try:
    # Client Gemini
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-pro')
    logger.info("✅ Service IA Gemini (2.5 Pro) configuré.")
except Exception as e:
    gemini_model = None
    logger.error(f"❌ Erreur de configuration pour Gemini: {e}")

try:
    # Client OpenAI
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    logger.info("✅ Client OpenAI configuré.")
except Exception as e:
    openai_client = None
    logger.error(f"❌ Erreur de configuration pour OpenAI: {e}")


# --- Fonctions d'Appel aux IA ---

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

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    try:
        logger.info("Appel à l'API OpenAI avec le modèle gpt-4o-mini")
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"}
        )
        raw_content = response.choices[0].message.content
        logger.info(f"Réponse brute d'OpenAI reçue : {raw_content}")

        # On cherche le début '{' ou '[' et la fin '}' ou ']' pour extraire le JSON.
        json_start = raw_content.find('{')
        if json_start == -1: json_start = raw_content.find('[')
            
        json_end = raw_content.rfind('}') + 1
        if json_end == 0: json_end = raw_content.rfind(']') + 1

        if json_start != -1 and json_end != 0:
            json_str = raw_content[json_start:json_end]
            logger.info("JSON extrait avec succès de la réponse d'OpenAI.")
            return json_str

        raise ValueError("La sortie d'OpenAI ne contenait pas de JSON valide.")

    except openai.APIError as e:
        logger.error(f"Une erreur API est survenue avec OpenAI : {e}")
        raise

def _call_local_llm(user_prompt: str, system_prompt: str = "") -> str:
    """
    Fonction privée pour appeler le LLM local via Ollama.
    """
    if not settings.LOCAL_LLM_URL:
        raise ConnectionError("L'URL du LLM local (Ollama) n'est pas configurée.")
    
    base_url = settings.LOCAL_LLM_URL.rstrip('/')
    full_url = f"{base_url}/api/chat"
    model_name = "llama3:8b" # Utilisation du modèle fiable
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    payload = {"model": model_name, "messages": messages, "format": "json", "stream": False}
    
    try:
        response = requests.post(full_url, json=payload, timeout=120)
        response.raise_for_status()
        response_data = response.json()
        
        if "message" in response_data and "content" in response_data["message"]:
            content = response_data["message"]["content"]
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
    elif model_choice == 'openai_gpt4o_mini':
        return _call_openai_llm(user_prompt=user_prompt, system_prompt=system_prompt)
    else: # Gemini par défaut
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        return _call_gemini(full_prompt)

# --- Fonctions de Génération de Contenu ---

def classify_course_topic(title: str, model_choice: str) -> str:
    system_prompt = "Tu es un service de classification. Ton rôle est de prendre un sujet de cours et de le classifier dans une catégorie parmi la liste suivante : ['histoire', 'science', 'philosophie', 'langue', 'programmation', 'art', 'stratégie', 'économie', 'psychologie', 'politique']. Tu DOIS répondre avec un objet JSON contenant une seule clé 'category'."
    user_prompt = title
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str).get("category", "general")
    except Exception as e:
        logger.error(f"Erreur de classification pour '{title}': {e}")
        return "general"

def generate_learning_plan(title: str, course_type: str, model_choice: str) -> dict:
    system_prompt = "Tu es un service de génération de plans de cours. Tu DOIS répondre avec un objet JSON qui a la structure suivante : { \"overview\": \"string\", \"rpg_stats_schema\": { \"stat_1\": \"string\",... }, \"levels\": [ { \"level_title\": \"string\" }, ... ] }. Remplis cette structure avec du contenu pertinent."
    user_prompt = title
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur de plan de cours pour '{title}': {e}")
        return {}

def generate_personalization_questions(title: str, category: str, model_choice: str) -> Dict[str, Any]:
    """
    Génère un schéma de formulaire de personnalisation avec un prompt très strict.
    """
    logger.info(f"IA - Génération des questions de personnalisation pour le sujet '{title}' (catégorie: {category})")

    system_prompt = f"""
    Tu es un tuteur expert. Ta tâche est de créer un formulaire de questions pour un utilisateur souhaitant apprendre sur le sujet très spécifique : '{title}'.
    Tes questions doivent être DIRECTEMENT liées au sujet '{title}'.
    
    Tu DOIS répondre avec un objet JSON. La sortie NE DOIT contenir aucun texte en dehors de l'objet JSON.
    L'objet JSON doit contenir une clé (par exemple "fields" ou "questions") dont la valeur est une liste de 2 à 3 objets de question.

    Chaque objet question DOIT avoir les clés suivantes :
    1. "name": une chaîne courte en snake_case (ex: "current_level").
    2. "label": la question pour l'utilisateur (ex: "Quel est votre niveau actuel ?").
    3. "type": une chaîne (choisir entre "select", "text", "textarea").

    Si, et SEULEMENT si, le "type" est "select", tu DOIS ajouter une clé "options".
    La valeur de "options" DOIT être une liste d'OBJETS.
    Chaque objet dans la liste "options" DOIT avoir deux clés :
    - "value": une chaîne courte en minuscules (ex: "debutant").
    - "label": le texte affiché à l'utilisateur (ex: "Débutant (A1)").

    EXEMPLE DE SORTIE PARFAITE :
    {{
      "fields": [
        {{
          "name": "spinoza_knowledge",
          "label": "Comment évaluez-vous votre connaissance actuelle de la philosophie de Spinoza ?",
          "type": "select",
          "options": [
            {{ "value": "none", "label": "Je ne connais que le nom" }},
            {{ "value": "beginner", "label": "J'ai lu quelques articles ou résumés" }},
            {{ "value": "intermediate", "label": "J'ai déjà lu 'L'Éthique' mais j'ai besoin d'aide" }}
          ]
        }},
        {{
          "name": "learning_goal",
          "label": "Quel concept clé du spinozisme souhaitez-vous approfondir en priorité ?",
          "type": "textarea"
        }}
      ]
    }}
    """
    user_prompt = f"Génère les questions de personnalisation pour un cours sur : {title}"

    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        data = json.loads(response_str)

        if "fields" in data and isinstance(data["fields"], list):
            return data
        
        for key, value in data.items():
            if isinstance(value, list):
                logger.warning(f"La clé 'fields' n'a pas été trouvée. Utilisation de la clé alternative '{key}'.")
                return {"fields": value}

        raise ValueError("La réponse de l'IA ne contient aucune liste de champs valide.")
    except Exception as e:
        logger.error(f"Erreur de génération du formulaire pour '{title}': {e}")
        return {"fields": []}
    
def generate_adaptive_learning_plan(title: str, course_type: str, model_choice: str, personalization_details: Dict[str, Any]) -> dict:
    logger.info(f"IA - Étape 1 (Adapté) : Génération du plan de cours pour '{title}' avec les détails : {personalization_details}")
    user_context = f"Le cours doit être adapté pour un utilisateur avec le profil suivant : {json.dumps(personalization_details, ensure_ascii=False)}."
    system_prompt = f"Tu es un ingénieur pédagogique expert. Crée un plan d'apprentissage HAUTEMENT PERSONNALISÉ. Prends en compte le sujet du cours, mais SURTOUT le profil de l'utilisateur. {user_context} Tu DOIS répondre avec un objet JSON avec la structure : {{'overview': '...', 'rpg_stats_schema': {{...}}, 'levels': [{{'level_title': '...'}}]}}."
    user_prompt = title
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur de plan de cours adapté pour '{title}': {e}")
        return {}

def generate_chapter_plan_for_level(level_title: str, model_choice: str) -> List[str]:
    system_prompt = "Tu es un ingénieur pédagogique. Décompose le titre de niveau fourni en 3 à 5 titres de chapitres. Tu DOIS répondre avec un objet JSON contenant une clé 'chapters', qui est une liste de chaînes de caractères."
    user_prompt = level_title
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        data = json.loads(response_str)
        return data.get("chapters", []) if isinstance(data, dict) else []
    except Exception as e:
        logger.error(f"Erreur de plan de chapitre pour '{level_title}': {e}")
        return []

def generate_lesson_for_chapter(chapter_title: str, model_choice: str) -> str:
    system_prompt = "Tu es un professeur expert. Rédige une leçon de 300-500 mots sur le sujet donné. Tu DOIS répondre avec un objet JSON contenant une seule clé 'lesson_text'."
    user_prompt = chapter_title
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        data = json.loads(response_str)
        return data.get("lesson_text", "") if isinstance(data, dict) else ""
    except Exception as e:
        logger.error(f"Erreur de génération de leçon pour '{chapter_title}': {e}")
        return ""

def generate_exercises_for_lesson(lesson_text: str, chapter_title: str, model_choice: str) -> List[Dict[str, Any]]:
    system_prompt = f"Tu es un créateur d'exercices. Crée 3 exercices variés basés UNIQUEMENT sur le texte de leçon fourni. Tu DOIS répondre avec une liste JSON d'objets. Chaque objet doit avoir les clés 'title', 'category' (qui doit être '{chapter_title}'), 'component_type', 'bloom_level', et 'content_json'."
    user_prompt = lesson_text
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        exercises_data = json.loads(response_str)
        # On s'assure que c'est bien une liste, sinon on cherche une clé qui en contient une
        if isinstance(exercises_data, list):
            return exercises_data
        if isinstance(exercises_data, dict):
            for key, value in exercises_data.items():
                if isinstance(value, list):
                    return value
        return []
    except Exception as e:
        logger.error(f"Erreur de génération d'exercices pour '{chapter_title}': {e}")
        return []