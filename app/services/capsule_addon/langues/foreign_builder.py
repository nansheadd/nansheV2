import logging
import json
from .base_language_builder import BaseLanguageBuilder

logger = logging.getLogger(__name__)

class ForeignBuilder(BaseLanguageBuilder):
    def build(self):
        logger.info(f"--- [BUILDER_ETRANGERES] Début de la construction du parcours pour '{self.main_skill}' ---")
        level_0_plan = self._build_alphabet_level()
        full_plan = {
            "overview": f"Un cours pour apprendre le {self.main_skill}, en commençant par les bases de son écriture.",
            "levels": [level_0_plan]
        }
        return full_plan

    def _build_alphabet_level(self):
        logger.info("[BUILDER_ETRANGERES] Construction du Level 0 : Alphabet...")
        
        # --- 👇 CORRECTION : ON CHERCHE LES BONS SKILLS 👇 ---
        hiragana_atoms = self._get_knowledge_atoms(skill="hiragana", content_type="data_caractere")
        print("HIARAGA. ::: ", hiragana_atoms)
        print('SANGOKU :::: ', self._get_knowledge_atoms(skill="hiragana", content_type="data_caractere"))
        katakana_atoms = self._get_knowledge_atoms(skill="katakana", content_type="data_caractere")
        
        granules = []
        
        if hiragana_atoms:
            hiragana_blocs = []
            for i, atom in enumerate(hiragana_atoms):
                # On parse le JSON contenu dans le champ chunk_text
                atom_content = json.loads(atom.chunk_text)
                # On crée un bloc de leçon pour ce caractère
                hiragana_blocs.append({
                    "order": i + 1,
                    "block_type": "lecon_caractere",
                    "content": atom_content
                })
            
            granules.append({
                "granule_title": "1. Apprendre les Hiragana",
                "order": 1,
                "blocs": hiragana_blocs # On insère les blocs créés
            })

        if katakana_atoms:
            katakana_blocs = []
            for i, atom in enumerate(katakana_atoms):
                atom_content = json.loads(atom.chunk_text)
                katakana_blocs.append({
                    "order": i + 1,
                    "block_type": "lecon_caractere",
                    "content": atom_content
                })
                print("KOOKOK :: ",katakana_blocs )

            granules.append({
                "granule_title": "2. Apprendre les Katakana",
                "order": 2,
                "blocs": katakana_blocs # On insère les blocs créés
            })
            
        level_plan = {
            "level_title": "Level 0 — Les Fondations : L'Écriture",
            "level_order": 0,
            "granules": granules
        }
        logger.info(f"[BUILDER_ETRANGERES] -> Assemblage du Level 0 terminé avec {len(granules)} granules remplis.")
        return level_plan