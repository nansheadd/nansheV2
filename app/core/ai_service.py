# Fichier: nanshe/backend/app/core/ai_service.py
import google.generativeai as genai
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    logger.info("✅ Service IA configuré avec succès.")
except Exception as e:
    logger.error(f"❌ Erreur lors de la configuration du service IA: {e}")
    model = None

def classify_course_topic(title: str) -> str:
    """Appelle l'IA pour classifier un sujet de cours."""
    if not model:
        logger.warning("⚠️ Modèle IA non disponible. Classification par défaut.")
        return "general"

    prompt = f"""
    Tu es un expert en classification. Pour le sujet suivant : '{title}', choisis la catégorie la plus pertinente
    parmi cette liste : ['histoire', 'science', 'philosophie', 'langue', 'programmation', 'art', 'stratégie', 'économie', 'psychologie'].
    Réponds uniquement avec le mot de la catégorie en minuscule.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip().lower()
    except Exception as e:
        logger.error(f"Erreur lors de la classification IA : {e}")
        return "general"

def generate_learning_plan(title: str, course_type: str) -> dict:
    """Appelle l'IA pour générer le plan d'apprentissage d'un cours."""
    if not model:
        logger.warning("⚠️ Modèle IA non disponible. Plan de cours par défaut.")
        return {}

    prompt = f"""
    Tu es un ingénieur pédagogique expert. Pour le sujet "{title}", qui est de type "{course_type}",
    génère un plan d'apprentissage au format JSON.
    Le JSON doit avoir 3 clés : "overview" (une phrase d'accroche), "rpg_stats_schema" (un objet avec 3 statistiques pertinentes pour ce sujet, initialisées à 0),
    et "levels" (une liste de 3 à 5 objets, où chaque objet a une clé "level_title" et une clé "category").
    Assure-toi que le JSON soit valide et ne contienne aucun commentaire.
    Exemple pour "Les volcans": {{"overview": "Découvrez les forces cachées de la Terre.", "rpg_stats_schema": {{"Géologie": 0, "Chimie": 0, "Vulcanologie": 0}}, "levels": [{{"level_title": "Qu'est-ce qu'un volcan ?", "category": "Fondamentaux"}}]}}
    """
    try:
        response = model.generate_content(prompt)
        # Nettoyer la réponse pour s'assurer qu'elle est un JSON valide
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Erreur lors de la génération du plan IA : {e}")
        return {"error": "Failed to generate learning plan"}
    

def generate_level_content(level_title: str, course_type: str) -> list[dict]:
    """Appelle l'IA pour générer le contenu détaillé d'un niveau."""
    if not model:
        logger.warning("⚠️ Modèle IA non disponible. Contenu de niveau par défaut.")
        return []

    # Ce prompt est crucial. On lui demande de générer plusieurs types d'exercices.
    prompt = f"""
    Tu es un ingénieur pédagogique expert. Pour le niveau "{level_title}" d'un cours de type "{course_type}",
    génère une liste de 3 à 5 "briques de savoir" au format JSON.
    Chaque brique dans la liste doit être un objet JSON avec les clés suivantes :
    - "title": un titre court et précis pour le concept (ex: "Le biais de confirmation").
    - "category": une catégorie RPG pertinente (ex: "Psychologie Cognitive").
    - "component_type": le type d'exercice parmi ['lesson', 'qcm', 'fill_in_the_blank'].
    - "bloom_level": le niveau de taxonomie de Bloom ('remember', 'understand').
    - "content_json": un objet contenant les données de l'exercice.
        - Pour une "lesson", il doit contenir une clé "text".
        - Pour un "qcm", il doit contenir "question", "options" (une liste de strings), et "correct_option_index" (un nombre).
        - Pour un "fill_in_the_blank", il doit contenir "text_with_blanks" (avec des ___ ) et "answers" (une liste des mots manquants).

    Assure-toi que la sortie soit une liste JSON valide, sans texte avant ou après.
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Erreur lors de la génération du contenu de niveau : {e}")
        return [{"error": "Failed to generate level content"}]