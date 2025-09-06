import logging
import random
import json
from sqlalchemy.orm import Session
from app.models.analytics.vector_store_model import VectorStore
from app.models.progress.user_atomic_progress import UserCharacterProgress
from app.models.capsule.capsule_model import Capsule


logger = logging.getLogger(__name__)

class ExerciseGeneratorService:
    def __init__(self, db: Session, user_id: int, capsule: Capsule):
        self.db = db
        self.user_id = user_id
        self.capsule = capsule
        logger.info(f"--- [EXERCISE_GEN] Initialisé pour User ID: {user_id}, Capsule: '{capsule.title}' ---")

    def create_session_for_level(self, level_order: int):
        """
        Point d'entrée principal pour générer une session pour un niveau donné.
        """
        logger.info(f"[EXERCISE_GEN] Début de la création de session pour le Level {level_order}")
        if level_order == 0 and self.capsule.area == "langues_etrangeres":
            return self._create_alphabet_introduction_session()
        else:
            logger.warning(f"[EXERCISE_GEN] La logique pour le Level {level_order} n'est pas encore implémentée.")
            return {"title": f"Leçon non disponible", "blocs": []}

    def _create_alphabet_introduction_session(self):
        """
        Crée une session d'apprentissage pour le niveau 0 d'une langue étrangère.
        """
        logger.info("[EXERCISE_GEN] -> Étape 1: Sélection des atomes de caractères...")
        
        # --- 👇 CORRECTION : ON CHERCHE TOUS LES TYPES DE CARACTÈRES 👇 ---
        # On définit les skills qui correspondent à un alphabet pour cette langue
        alphabet_skills = ["hiragana", "katakana"] # Plus tard, on pourra rendre ça dynamique
        print("TESTIOOOO ::: ", alphabet_skills)
        
        all_character_atoms = self.db.query(VectorStore).filter(
            VectorStore.area == self.capsule.main_skill,
            VectorStore.skill.in_(alphabet_skills) # On utilise 'in_' pour chercher plusieurs skills
        ).all()


        # -----------------------------------------------------------------
        
        if not all_character_atoms:
            logger.error(f"Aucun atome de caractère trouvé pour '{self.capsule.main_skill}'.")
            return {"title": "Contenu non disponible", "blocs": []}

        # La suite de la logique reste la même et fonctionnera maintenant correctement
        progress_data = self.db.query(UserCharacterProgress).filter(
            UserCharacterProgress.user_id == self.user_id,
            UserCharacterProgress.character_atom_id.in_([atom.id for atom in all_character_atoms])
        ).all()
        
        seen_character_ids = {p.character_atom_id for p in progress_data}
        unseen_atoms = [atom for atom in all_character_atoms if atom.id not in seen_character_ids]
        
        new_atoms_to_learn = random.sample(unseen_atoms, min(len(unseen_atoms), 5))
        
        logger.info(f"[EXERCISE_GEN] -> Sélectionné {len(new_atoms_to_learn)} nouveaux caractères à apprendre.")
        
        
        # On récupère TOUS les atomes de l'alphabet pour cette langue
        all_character_atoms = self.db.query(VectorStore).filter(
            VectorStore.area == self.capsule.main_skill,
            VectorStore.skill == "alphabet"
        ).all()
        
        # On récupère la progression de l'utilisateur sur ces caractères
        progress_data = self.db.query(UserCharacterProgress).filter(
            UserCharacterProgress.user_id == self.user_id,
            UserCharacterProgress.character_atom_id.in_([atom.id for atom in all_character_atoms])

        ).all()
        
        # On sépare les caractères vus des non-vus
        seen_character_ids = {p.character_id for p in progress_data}
        unseen_atoms = [atom for atom in all_character_atoms if atom.id not in seen_character_ids]
        
        # On sélectionne 5 nouveaux caractères à apprendre
        new_atoms_to_learn = random.sample(unseen_atoms, min(len(unseen_atoms), 5))
        
        logger.info(f"[EXERCISE_GEN] -> Sélectionné {len(new_atoms_to_learn)} nouveaux caractères à apprendre.")
        
        # --- Étape 2: Assemblage des Blocs de la Session ---
        logger.info("[EXERCISE_GEN] -> Étape 2: Assemblage des blocs de la session...")
        session_blocs = []

        # 2.1 - On commence par une leçon théorique générée par l'IA
        session_blocs.append(self._generate_theory_block_with_ia(
            topic=f"Introduction aux 5 prochains caractères en {self.capsule.main_skill}",
            atoms_context=[json.loads(atom.chunk_text) for atom in new_atoms_to_learn]
        ))

        lecon_blocs = []
        lecon_blocs.append(self._generate_theory_block_with_ia(
            topic=f"Introduction aux prochains caractères en {self.capsule.main_skill}",
            atoms_context=[json.loads(atom.chunk_text) for atom in new_atoms_to_learn]
        ))
        # 2.2 - Pour chaque nouveau caractère, on crée un cycle : Leçon -> Exercice
        for atom in new_atoms_to_learn:
            atom_data = json.loads(atom.chunk_text)
            session_blocs.append({"order": len(session_blocs), "block_type": "lecon_caractere", "content": atom_data})
            session_blocs.append(self._create_character_qcm(atom_data, all_character_atoms))
        
        session_granule = {
            "granule_title": "Leçon du Jour : Vos Premiers Caractères",
            "order": 1,
            "blocs": lecon_blocs # On met notre liste de blocs ici
        }

        logger.info(f"[EXERCISE_GEN] -> Session assemblée avec {len(lecon_blocs)} blocs dans 1 granule.")
        
        # On retourne la structure que le frontend attend : une liste de granules
        return {
            "title": "Session d'Apprentissage",
            "blocs": [session_granule] 
        }

    # --- PARTIE HAUTE (Logique Backend) ---
    def _create_character_qcm(self, correct_atom_data: dict, all_atoms: list):
        """
        Crée un exercice de QCM pour un caractère donné.
        """
        options = {correct_atom_data['romaji']}
        while len(options) < 4:
            random_atom = random.choice(all_atoms)
            options.add(json.loads(random_atom.chunk_text)['romaji'])
        
        return {
            "order": 99, # L'ordre sera défini lors de l'assemblage final
            "block_type": "exercice_qcm_caractere",
            "content": {
                "question": "Quel est la lecture de ce caractère ?",
                "character": correct_atom_data['caractere'],
                "options": sorted(list(options)),
                "reponse": correct_atom_data['romaji']
            }
        }

    # --- PARTIE BASSE (Génération IA) ---
    def _generate_theory_block_with_ia(self, topic: str, atoms_context: list):
        """
        Utilise le LLM local pour générer un bloc de théorie enrichi.
        """
        logger.info(f"  [IA_GEN] Génération d'un bloc de théorie pour '{topic}'...")
        
        prompt = f"""
        Tu es un professeur de langue expert. Rédige une leçon d'introduction simple et encourageante sur le sujet suivant : "{topic}".
        Voici les caractères spécifiques qui seront abordés dans cette leçon, utilise-les comme exemples :
        {json.dumps(atoms_context, ensure_ascii=False, indent=2)}
        Ta réponse doit être un JSON contenant une clé "title" et une clé "text".
        """
        
        # response_json = local_llm_service.generate_json_with_local_llm(prompt)
        # Pour le test, on retourne une valeur par défaut
        response_json = {
            "title": topic,
            "text": "Le LLM local générerait ici une leçon complète et engageante sur les caractères à venir..."
        }
        
        return {"order": 0, "block_type": "theorie", "content": response_json}