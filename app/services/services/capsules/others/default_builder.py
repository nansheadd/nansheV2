import logging
import json
from sqlalchemy.orm import Session
from app.models.capsule.capsule_model import Capsule
from app.services.services.capsules.base_builder import BaseCapsuleBuilder
from openai import OpenAI

from app.core.config import settings



logger = logging.getLogger(__name__)


try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    openai_client = None
    logger.error(f"❌ Erreur de configuration pour OpenAI: {e}")

class DefaultBuilder(BaseCapsuleBuilder):
    """
    Builder spécialisé pour les langues. Utilise la logique de cache/RAG du parent
    mais avec un prompt spécialisé pour une meilleure qualité.
    """
    def generate_learning_plan(self, db: Session, capsule: Capsule) -> dict | None:
        """
        Surcharge la génération de plan pour utiliser un prompt spécialisé pour les langues.
        La logique de cache/RAG est toujours gérée par le parent.
        """
        print("==========================================================")
        print("====== ✅ GÉNÉRATION DE PLAN DANS LE Default BUILDER ! ✅ ==")
        print("==========================================================")
        
        # On peut réutiliser la logique du parent, mais en surchargeant le prompt
        # (Pour cet exemple, je réécris la logique pour plus de clarté)

        # ÉTAPE 1: Chercher un plan existant dans la base vectorielle (logique héritée)
        existing_plan = self._find_plan_in_vector_store(db, capsule.main_skill)
        if existing_plan:
            logger.info(f"--> [CACHE] ✅ Plan de langue trouvé dans VectorStore pour '{capsule.main_skill}'.")
            return existing_plan

        # ÉTAPE 2: Générer avec un prompt spécialisé si non trouvé
        logger.info(f"--> [CACHE] ❌ Aucun plan de langue trouvé. Génération avec prompt spécialisé.")
        inspirational_examples = self._find_inspirational_examples(db, capsule.domain, capsule.area)
        
        if not openai_client: return None
        
        language = capsule.main_skill
        
        system_prompt = (
            "Tu es un polyglotte et un ingénieur pédagogique. Crée un plan d'apprentissage JSON pour une langue étrangère. "
            "Le plan doit être complet, progressif (A1 à C1), et contenir entre 16 et 25 'levels' (compétences majeures). "
            "Chaque 'level' contient des 'chapters' (leçons spécifiques)."
        )
        user_prompt = f"Crée un plan de cours exceptionnel pour apprendre le {language}."

        if inspirational_examples:
            # On construit une chaîne de caractères contenant tous les exemples.
            examples_str = "\n\n---\n\n".join(
                f"Exemple de plan pour '{ex['main_skill']}':\n{json.dumps(ex['plan'], indent=2, ensure_ascii=False)}"
                for ex in inspirational_examples
            )
            
            # On ajoute les exemples formatés au prompt de l'utilisateur.
            user_prompt += (
                "\n\nPour t'aider, inspire-toi de la structure et de la qualité de ces excellents plans. "
                "NE COPIE PAS le contenu, mais utilise-les comme modèle de qualité pour créer un plan "
                f"entièrement nouveau et adapté pour le {language}.\n\n{examples_str}"
            )

        try:
            response = openai_client.chat.completions.create(
                model="gpt-5-mini-2025-08-07",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"}
            )
            new_plan = json.loads(response.choices[0].message.content)
            
            # ÉTAPE 3: Sauvegarder le nouveau plan (logique héritée)
            self._save_plan_to_vector_store(db, capsule, new_plan)
            
            return new_plan
        except Exception as e:
            logger.error(f"Erreur API OpenAI dans ForeignBuilder : {e}")
            return None