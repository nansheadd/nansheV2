# Fichier: backend/app/core/ai_service.py (REFONTE COMPLÈTE)
import google.generativeai as genai
import json
import logging
from app.core.config import settings
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# --- Configuration du Modèle ---
try:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-pro')
    logger.info("✅ Service IA configuré (Gemini 2.5 Pro).")
except Exception as e:
    logger.error(f"❌ Erreur config IA: {e}")
    model = None

# --- Fonction d'Appel Générique ---
def _call_gemini(prompt: str) -> str:
    if not model:
        raise ConnectionError("Le modèle IA n'est pas disponible.")
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json")
        )
        return response.text
    except Exception as e:
        logger.error(f"Erreur lors de l'appel à l'API Gemini : {e}")
        raise

# ==============================================================================
# == ÉTAPE 1 : GÉNÉRATION DU PLAN DE COURS (NIVEAUX)
# ==============================================================================
def generate_learning_plan(title: str, course_type: str) -> dict:
    """Génère le plan d'apprentissage global d'un cours (la liste des niveaux)."""
    logger.info(f"IA Étape 1 : Génération du plan de cours pour '{title}'...")
    prompt = f"""
    Tu es un ingénieur pédagogique expert. Pour le sujet "{title}", qui est de type "{course_type}",
    génère un plan d'apprentissage au format JSON.
    Le JSON doit avoir 3 clés : "overview" (une phrase d'accroche), "rpg_stats_schema" (un objet avec 3 statistiques pertinentes),
    et "levels" (une liste de 3 à 5 objets, où chaque objet a une clé "level_title").
    """
    try:
        return json.loads(_call_gemini(prompt))
    except Exception as e:
        logger.error(f"Erreur de génération de plan IA : {e}")
        return {"error": "Failed to generate learning plan"}

# ==============================================================================
# == ÉTAPE 2 : GÉNÉRATION DU PLAN DE NIVEAU (CHAPITRES)
# ==============================================================================
def generate_chapter_plan_for_level(level_title: str) -> List[str]:
    """Pour un niveau donné, génère la liste des titres de ses chapitres."""
    logger.info(f"IA Étape 2 : Génération du plan de chapitres pour '{level_title}'...")
    prompt = f"""
    Pour un niveau de cours intitulé '{level_title}', décompose-le en 3 à 5 chapitres logiques et spécifiques.
    Réponds au format JSON avec une seule clé "chapters" contenant une liste des titres de ces chapitres.
    Exemple: {{"chapters": ["Le Matérialisme Historique", "La Lutte des Classes", "L'Aliénation"]}}
    """
    try:
        response_str = _call_gemini(prompt)
        return json.loads(response_str).get("chapters", [])
    except Exception as e:
        logger.error(f"Erreur Etape 2 (chapitres) : {e}")
        return []

# ==============================================================================
# == ÉTAPE 3 : GÉNÉRATION DE LA LEÇON D'UN CHAPITRE
# ==============================================================================
def generate_lesson_for_chapter(chapter_title: str) -> str:
    """Pour un chapitre donné, génère le texte détaillé de la leçon."""
    logger.info(f"IA Étape 3 : Génération de la leçon pour '{chapter_title}'...")
    prompt = f"""
    Tu es un professeur expert. Rédige une leçon claire, détaillée et complète (environ 300-500 mots) 
    sur le sujet : "{chapter_title}". Inclus des définitions, des exemples concrets, et si possible une analogie.
    Réponds au format JSON avec une seule clé "lesson_text".
    """
    try:
        response_str = _call_gemini(prompt)
        return json.loads(response_str).get("lesson_text", "")
    except Exception as e:
        logger.error(f"Erreur Etape 3 (leçon) : {e}")
        return ""

# ==============================================================================
# == ÉTAPE 4 : GÉNÉRATION DES EXERCICES BASÉS SUR LA LEÇON
# ==============================================================================
def generate_exercises_for_lesson(lesson_text: str, chapter_title: str) -> List[Dict[str, Any]]:
    """En se basant sur une leçon, génère une liste d'exercices variés."""
    logger.info(f"IA Étape 4 : Génération des exercices pour '{chapter_title}'...")
    prompt = f"""
    En te basant UNIQUEMENT et STRICTEMENT sur le texte suivant:
    ---
    {lesson_text}
    ---
    Crée une liste de 3 à 4 exercices interactifs et variés au format JSON.
    Chaque exercice dans la liste doit être un objet JSON avec les clés suivantes :
    - "title": un titre court dérivé du concept testé.
    - "category": une catégorie RPG pertinente.
    - "component_type": choisi parmi ['qcm', 'fill_in_the_blank', 'reorder'].
    - "bloom_level": 'remember' ou 'understand'.
    - "content_json": un objet contenant les données de l'exercice, dont la réponse doit se trouver dans le texte fourni.
    """
    try:
        response_str = _call_gemini(prompt)
        exercises_data = json.loads(response_str)
        
        # On s'assure que chaque exercice a bien le texte de la leçon associé
        for exercise in exercises_data:
            if "content_json" in exercise:
                exercise["content_json"]["lesson_text"] = lesson_text
        return exercises_data

    except Exception as e:
        logger.error(f"Erreur Etape 4 (exercices) : {e}")
        return []