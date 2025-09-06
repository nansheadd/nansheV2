import logging
import json
from openai import OpenAI
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client
try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    logger.info("✅ Client OpenAI configuré avec succès.")
except Exception as e:
    openai_client = None
    logger.error(f"❌ Erreur lors de la configuration du client OpenAI: {e}")

def generate_json_with_gpt(prompt: str, model: str = "gpt-5-mini-2025-08-07") -> dict | None:
    """
    Génère un plan de cours structuré en JSON en utilisant un modèle OpenAI (GPT).

    Args:
        prompt: Le prompt détaillé pour la génération.
        model: Le modèle OpenAI à utiliser (par défaut "gpt-5-mini-2025-08-07").

    Returns:
        Un dictionnaire Python représentant le plan de cours, ou None en cas d'erreur.
    """
    if not openai_client:
        logger.error("Le client OpenAI n'est pas initialisé. Impossible de continuer.")
        return None

    logger.info(f"Début de la génération de texte avec le modèle OpenAI: {model}")
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Tu es un assistant expert en conception pédagogique. Tu génères uniquement des réponses au format JSON valide."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
        )
        
        response_text = response.choices[0].message.content
        logger.info("Réponse brute de l'API OpenAI reçue.")
        
        return json.loads(response_text)

    except json.JSONDecodeError as e:
        logger.error(f"Erreur de parsing JSON de la réponse OpenAI: {e}\nRéponse reçue:\n{response_text}")
        return None
    except Exception as e:
        logger.error(f"Une erreur inattendue est survenue lors de l'appel à l'API OpenAI: {e}", exc_info=True)
        return None