# Fichier à créer : nanshe/backend/app/core/prompt_manager.py

import os
from functools import lru_cache

# Détermine le chemin de base du projet pour trouver le dossier 'prompts'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS_DIR = os.path.join(BASE_DIR, 'prompts')

@lru_cache(maxsize=128)
def get_prompt_template(path: str) -> str:
    """
    Charge un modèle de prompt depuis un fichier .md.
    Utilise un cache pour éviter de lire le même fichier plusieurs fois.
    """
    # Sépare le chemin en dossier et nom de fichier (ex: "course_planning.classify_topic")
    parts = path.split('.')
    file_name = f"{parts[-1]}.md"
    full_path = os.path.join(PROMPTS_DIR, *parts[:-1], file_name)

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # Gérer le cas où le prompt n'est pas trouvé
        return f"Erreur: Prompt non trouvé à l'emplacement {full_path}"

def get_prompt(path: str, **kwargs) -> str:
    """
    Charge un modèle de prompt et y injecte les variables fournies,
    uniquement si des variables sont passées.
    """
    template = get_prompt_template(path)
    # On n'exécute le formatage que si des arguments sont réellement fournis
    if kwargs:
        return template.format(**kwargs)
    return template