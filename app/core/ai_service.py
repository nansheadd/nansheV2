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
    gemini_model = genai.GenerativeModel('gemini-1.5-pro-latest')
    logger.info("✅ Service IA Gemini (1.5 Pro) configuré.")
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


# ==============================================================================
# Fonctions Privées d'Appel aux IA
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
    system_prompt = "Tu es un service de classification. Ton rôle est de classer un sujet de cours dans une catégorie parmi : ['histoire', 'science', 'philosophie', 'langue', 'programmation', 'art', 'stratégie', 'économie', 'psychologie', 'politique']. Tu DOIS répondre avec un JSON contenant une seule clé 'category'."
    user_prompt = title
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str).get("category", "general")
    except Exception as e:
        logger.error(f"Erreur de classification pour '{title}': {e}")
        return "general"

def generate_learning_plan(title: str, course_type: str, model_choice: str) -> dict:
    system_prompt = "Tu es un ingénieur pédagogique. Crée un plan de cours. Tu DOIS répondre avec un JSON ayant la structure : { \"overview\": \"string\", \"levels\": [ { \"level_title\": \"string\" } ] }."
    user_prompt = f"Sujet du cours : {title}. Catégorie : {course_type}."
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur de plan de cours pour '{title}': {e}")
        return {}

def generate_adaptive_learning_plan(title: str, course_type: str, model_choice: str, personalization_details: Dict[str, Any]) -> dict:
    user_context = f"Le cours doit être adapté pour un utilisateur avec le profil suivant : {json.dumps(personalization_details, ensure_ascii=False)}."
    system_prompt = f"Tu es un ingénieur pédagogique expert. Crée un plan d'apprentissage HAUTEMENT PERSONNALISÉ. Prends en compte le sujet du cours, mais SURTOUT le profil de l'utilisateur. {user_context} Tu DOIS répondre avec un JSON avec la structure : {{'overview': '...', 'levels': [{{'level_title': '...'}}]}}."
    user_prompt = title
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur de plan de cours adapté pour '{title}': {e}")
        return {}
    
def generate_personalization_questions(title: str, category: str, model_choice: str) -> Dict[str, Any]:
    """
    Génère un schéma de formulaire avec un prompt très strict pour garantir le format des options.
    """
    logger.info(f"IA - Génération des questions de personnalisation pour '{title}'")

    # --- NOUVEAU PROMPT AMÉLIORÉ ---
    system_prompt = f"""
    Tu es un tuteur expert. Ta tâche est de créer un formulaire de questions pour un utilisateur souhaitant apprendre sur le sujet : '{title}'.
    
    Tu DOIS répondre avec un objet JSON. La sortie NE DOIT contenir aucun texte en dehors de l'objet JSON.
    L'objet JSON doit contenir une clé "fields", dont la valeur est une liste de 2 à 3 objets de question.

    Chaque objet question DOIT avoir les clés suivantes :
    1. "name": une chaîne courte en snake_case (ex: "current_level").
    2. "label": la question pour l'utilisateur (ex: "Quel est votre niveau actuel ?").
    3. "type": une chaîne (choisir entre "select", "text", "textarea").

    Si, et SEULEMENT si, le "type" est "select", tu DOIS ajouter une clé "options".
    La valeur de "options" DOIT être une liste d'OBJETS. C'est obligatoire.
    Chaque objet dans la liste "options" DOIT avoir DEUX clés :
    - "value": une chaîne courte en minuscules, sans espaces (ex: "debutant").
    - "label": le texte affiché à l'utilisateur (ex: "Débutant (A1)").

    EXEMPLE DE SORTIE PARFAITE :
    {{
      "fields": [
        {{
          "name": "spinoza_knowledge",
          "label": "Comment évaluez-vous votre connaissance de Spinoza ?",
          "type": "select",
          "options": [
            {{ "value": "none", "label": "Je ne connais que le nom" }},
            {{ "value": "beginner", "label": "J'ai lu quelques résumés" }},
            {{ "value": "intermediate", "label": "J'ai déjà lu 'L'Éthique'" }}
          ]
        }},
        {{
          "name": "learning_goal",
          "label": "Quel concept clé souhaitez-vous approfondir en priorité ?",
          "type": "textarea"
        }}
      ]
    }}
    NE GÉNÈRE PAS une liste de chaînes pour les options. GÉNÈRE une liste d'objets.
    """
    user_prompt = f"Génère les questions de personnalisation pour un cours sur : {title}"

    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        data = json.loads(response_str)

        # Vérification et auto-correction simple au cas où l'IA se tromperait encore
        if "fields" in data:
            for field in data["fields"]:
                if field.get("type") == "select" and "options" in field:
                    # Si une option n'est pas un dictionnaire, on la transforme
                    corrected_options = []
                    for option in field["options"]:
                        if not isinstance(option, dict):
                            logger.warning(f"Correction auto: L'option '{option}' n'est pas un objet. Transformation...")
                            corrected_options.append({
                                "value": str(option).lower().replace(" ", "_"),
                                "label": str(option)
                            })
                        else:
                            corrected_options.append(option)
                    field["options"] = corrected_options
        
        # Logique pour trouver la liste de champs même si la clé n'est pas "fields"
        if "fields" in data and isinstance(data["fields"], list): return data
        for key, value in data.items():
            if isinstance(value, list): return {"fields": value}
        
        raise ValueError("La réponse de l'IA ne contient aucune liste de champs valide.")

    except Exception as e:
        logger.error(f"Erreur de génération du formulaire pour '{title}': {e}", exc_info=True)
        return {"fields": []}
    

def generate_chapter_plan_for_level(level_title: str, model_choice: str) -> List[str]:
    system_prompt = "Tu es un ingénieur pédagogique. Décompose le titre de niveau en 3 à 5 titres de chapitres. Tu DOIS répondre avec un JSON contenant une clé 'chapters', qui est une liste de chaînes de caractères."
    user_prompt = level_title
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        data = json.loads(response_str)
        return data.get("chapters", [])
    except Exception as e:
        logger.error(f"Erreur de plan de chapitre pour '{level_title}': {e}")
        return []

def generate_lesson_for_chapter(chapter_title: str, model_choice: str) -> str:
    system_prompt = "Tu es un professeur expert. Rédige une leçon de 300-500 mots sur le sujet donné. Tu DOIS répondre avec un JSON contenant une seule clé 'lesson_text'."
    user_prompt = chapter_title
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        data = json.loads(response_str)
        return data.get("lesson_text", "")
    except Exception as e:
        logger.error(f"Erreur de génération de leçon pour '{chapter_title}': {e}")
        return ""

def generate_exercises_for_lesson(lesson_text: str, chapter_title: str, model_choice: str) -> List[Dict[str, Any]]:
    """
    Génère des exercices avec un prompt très strict pour garantir le formatage du content_json.
    """
    logger.info(f"Génération des exercices pour le chapitre '{chapter_title}'")
    
    # --- PROMPT SYSTÈME AMÉLIORÉ ET ULTRA-PRÉCIS ---
    system_prompt = f"""
    Tu es un créateur d'exercices pédagogiques expert. Crée 3 exercices variés et pertinents basés UNIQUEMENT sur le texte de la leçon fourni.
    Tu DOIS répondre avec un objet JSON contenant une seule clé "exercises", qui est une liste de 3 objets.

    Chaque objet exercice dans la liste DOIT avoir la structure suivante :
    1. "title": un titre clair et concis.
    2. "category": la valeur DOIT être exactement: "{chapter_title}".
    3. "component_type": DOIT être choisi parmi ["qcm", "fill_in_the_blank", "discussion"].
    4. "bloom_level": une valeur comme "remember", "apply", "evaluate".
    5. "content_json": un objet JSON qui DOIT être rempli selon le `component_type`. C'est obligatoire.

    Voici les formats obligatoires pour `content_json` pour chaque type :
    
    - Si `component_type` est "qcm":
      {{
        "question": "Le texte de la question ici.",
        "options": ["Option 1", "Option 2", "Option 3"],
        "correct_option_index": 2 
      }}

    - Si `component_type` est "fill_in_the_blank":
      {{
        "sentence": "Le marxisme est une théorie ___ développée au XIXe siècle.",
        "answers": ["sociale, économique et politique"]
      }}

    - Si `component_type` est "discussion":
      {{
        "prompt": "Comment la théorie de la plus-value explique-t-elle l'exploitation dans le système capitaliste selon Marx ?",
        "guidelines": "Pensez à la différence entre la valeur du travail et le salaire."
      }}
      
    Assure-toi que chaque `content_json` est complet et non vide.
    """
    user_prompt = lesson_text
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        data = json.loads(response_str)
        exercises = data.get("exercises", [])
        
        # Sécurité : on filtre les exercices au contenu vide
        valid_exercises = [ex for ex in exercises if ex.get("content_json")]
        if len(valid_exercises) != len(exercises):
            logger.warning("Certains exercices générés avaient un content_json vide et ont été filtrés.")
            
        return valid_exercises
    except Exception as e:
        logger.error(f"Erreur de génération d'exercices pour '{chapter_title}': {e}", exc_info=True)
        return []
    
# ==============================================================================
# Fonctions d'Analyse des Réponses Complexes
# ==============================================================================

def analyze_user_essay(prompt: str, guidelines: str, user_essay: str, model_choice: str) -> Dict[str, Any]:
    logger.info("IA Service: Démarrage de l'analyse d'un essai.")
    system_prompt = f"""
    Tu es un professeur expert. Analyse l'essai d'un étudiant sur le sujet "{prompt}" avec les consignes "{guidelines}".
    Tu DOIS répondre avec un JSON ayant la structure suivante : {{ "evaluation": "...", "strengths": ["..."], "areas_for_improvement": ["..."], "grade": "...", "is_validated": true/false }}.
    """
    user_prompt = f"Voici l'essai : \"{user_essay}\""
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de l'essai: {e}")
        return {"evaluation": "L'analyse a échoué.", "is_validated": False}

def start_ai_discussion(prompt: str, user_first_post: str, model_choice: str) -> Dict[str, Any]:
    logger.info("IA Service: Démarrage d'une discussion.")
    system_prompt = f"""
    Tu es un tuteur et un animateur de discussion. Le sujet est : "{prompt}"
    L'utilisateur a posté sa première réponse. Réponds-lui pour approfondir la conversation en posant une question ouverte.
    Tu DOIS répondre avec un JSON ayant la structure : {{ "initial_analysis": "...", "response_text": "...", "history": [...] }}.
    """
    user_prompt = f"Première intervention de l'utilisateur : \"{user_first_post}\""
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        response_data = json.loads(response_str)
        # On initialise l'historique de la conversation
        response_data['history'] = [
            {"author": "user", "message": user_first_post},
            {"author": "ia", "message": response_data.get("response_text")}
        ]
        response_data["is_validated"] = False # La discussion ne fait que commencer
        return response_data
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la discussion: {e}")
        return {"response_text": "Je n'ai pas bien compris. Pouvez-vous reformuler ?", "is_validated": False}

def continue_ai_discussion(prompt: str, history: List[Dict[str, str]], user_message: str, model_choice: str) -> Dict[str, Any]:
    """
    Continue une discussion existante en se basant sur l'historique.
    """
    logger.info("IA Service: Continuation d'une discussion.")
    history_str = "\n".join([f"{msg['author']}: {msg['message']}" for msg in history])
    system_prompt = f"""
    Tu es un tuteur engageant. Le sujet initial est : "{prompt}".
    Voici l'historique de la conversation :
    {history_str}

    L'utilisateur vient d'envoyer un nouveau message. Réponds de manière à approfondir la discussion.
    Si tu estimes que l'utilisateur a bien exploré le sujet, conclus la conversation et valide sa compréhension.
    Tu DOIS répondre avec un JSON ayant la structure : {{ "response_text": "...", "is_complete": true/false }}.
    """
    user_prompt = f"Nouveau message de l'utilisateur : \"{user_message}\""
    try:
        response_str = _call_ai_model(user_prompt, model_choice, system_prompt=system_prompt)
        return json.loads(response_str)
    except Exception as e:
        logger.error(f"Erreur lors de la continuation de la discussion: {e}")
        return {"response_text": "Je rencontre un problème technique.", "is_complete": False}
