# app/services/atom_service.py

import json
import logging
from textwrap import dedent
from sqlalchemy.orm import Session
from app.core import ai_service
from app.models.user.user_model import User
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from typing import Dict, Any, Optional, List
from app.models.capsule.atom_model import Atom, AtomContentType

logger = logging.getLogger(__name__)

class AtomService:
    """
    Service dédié à la création et à la gestion des Atomes.
    Contient la logique spécifique pour chaque type d'atome.
    """
    def __init__(
        self,
        db: Session,
        user: User,
        capsule: Capsule,
        *,
        source_material: Optional[dict] = None,
    ):
        self.db = db
        self.user = user
        self.capsule = capsule
        self.source_material: Dict[str, Any] | None = source_material or None

    def create_atom_content(self, atom_type: AtomContentType, molecule: Molecule, context_atoms: list[Atom], difficulty: Optional[str] = None) -> Dict[str, Any] | None:
        """Aiguille vers la bonne méthode de création en fonction du type d'atome."""
        if atom_type == AtomContentType.LESSON:
            return self._create_lesson_content(molecule)
        if atom_type == AtomContentType.QUIZ:
            return self._create_quiz_content(molecule, context_atoms, difficulty)
        if atom_type == AtomContentType.CODE_EXAMPLE:
            return self._create_code_example_content(molecule, context_atoms)
        if atom_type == AtomContentType.CODE_CHALLENGE:
            return self._create_code_challenge_content(molecule, context_atoms)
        if atom_type == AtomContentType.LIVE_CODE_EXECUTOR:
            return self._create_live_code_executor_content(molecule, context_atoms)
        if atom_type == AtomContentType.CODE_SANDBOX_SETUP:
            return self._create_code_sandbox_setup_content(molecule, difficulty)
        if atom_type == AtomContentType.CODE_PROJECT_BRIEF:
            return self._create_code_project_brief_content(molecule, context_atoms, difficulty)
        if atom_type == AtomContentType.FILL_IN_THE_BLANK:
            return self._create_fill_in_blank_content(molecule, context_atoms)
        if atom_type == AtomContentType.FLASHCARDS:
            return self._create_flashcards_content(molecule, context_atoms)
        if atom_type == AtomContentType.SHORT_ANSWER:
            return self._create_short_answer_content(molecule, context_atoms)
        if atom_type == AtomContentType.TRUE_FALSE:
            return self._create_true_false_content(molecule, context_atoms)
        if atom_type == AtomContentType.MATCHING:
            return self._create_matching_content(molecule, context_atoms)
        if atom_type == AtomContentType.ORDERING:
            return self._create_ordering_content(molecule, context_atoms)
        if atom_type == AtomContentType.CATEGORIZATION:
            return self._create_categorization_content(molecule, context_atoms)
        if atom_type == AtomContentType.DIAGRAM_COMPLETION:
            return self._create_diagram_completion_content(molecule, context_atoms)
        # Ajoutez d'autres types d'atomes ici à l'avenir
        # if atom_type == AtomContentType.CODE_CHALLENGE:
        #     return self._create_code_challenge_content(molecule)
        return None

    def _create_lesson_content(self, molecule: Molecule) -> Dict[str, Any]:
        """
        Crée le contenu pour un atome de type Leçon en reconstruisant
        le contexte du plan depuis la base de données.
        """
        
        # --- CORRECTION : Reconstruire le contexte du plan ---
        # Au lieu de lire un champ JSON, nous créons un dictionnaire
        # à partir des relations SQLAlchemy déjà chargées.
        plan_dict = {
            "overview": {
                "title": self.capsule.title,
                "domain": self.capsule.domain,
                "main_skill": self.capsule.main_skill,
            },
            "granules": [
                {
                    "title": granule.title,
                    "order": granule.order,
                    "molecules": [
                        {"title": m.title, "order": m.order}
                        for m in sorted(granule.molecules, key=lambda x: x.order)
                    ]
                }
                for granule in sorted(self.capsule.granules, key=lambda x: x.order)
            ]
        }
        plan_context = json.dumps(plan_dict, indent=2, ensure_ascii=False)
        reference_text = self._build_reference_context(molecule)
        # --- FIN DE LA CORRECTION ---

        if self.capsule.domain == 'programming':
            language = self._language_from_capsule()
            return ai_service.generate_programming_lesson(
                course_plan_context=plan_context,
                lesson_title=molecule.title,
                language=language,
                model_choice="gpt-5-mini-2025-08-07",
                reference_text=reference_text,
            )

        app_rules_context = """
        - Structure: Le cours est divisé en chapitres (granules) et leçons (molécules).
        - Calendrier: L'apprentissage est auto-rythmé (self-paced).
        - Évaluations: Chaque leçon est typiquement suivie d'un quiz simple (QCM).
        """
        
        # Le reste de la fonction est maintenant correct
        return ai_service.generate_contextual_lesson(
            course_plan_context=plan_context,
            app_rules_context=app_rules_context,
            target_lesson_title=molecule.title,
            model_choice="gpt-5-mini-2025-08-07",
            reference_text=reference_text,
        )

    def _create_quiz_content(self, molecule: Molecule, context_atoms: list[Atom], difficulty: Optional[str]) -> Dict[str, Any] | None:
        """
        Crée le contenu pour un atome de type Quiz en utilisant la nouvelle
        fonction de génération contextualisée.
        """
        lesson_text = ""
        for atom in context_atoms:
            if atom.content_type == AtomContentType.LESSON:
                lesson_text = atom.content.get("text", "")
                break
        
        if not lesson_text:
            print(f"Impossible de créer un quiz pour '{molecule.title}' car le contenu de la leçon est manquant.")
            return None

        # --- On appelle la NOUVELLE fonction de l'ai_service ---
        reference_text = self._build_reference_context(molecule)
        exercise_content = ai_service.generate_contextual_exercises(
            lesson_text=lesson_text,
            lesson_title=molecule.title,
            course_type="generic",
            difficulty=difficulty, # <-- On le passe à l'IA
            model_choice="gpt-5-mini-2025-08-07",
            reference_text=reference_text,
        )
        
        # La nouvelle fonction renvoie directement le bon format JSON,
        # donc on peut le retourner tel quel.
        if exercise_content:
            return exercise_content
            
        return None

    # =========================
    # PROGRAMMING CONTENT HELPERS
    # =========================

    def _extract_lesson_text(self, context_atoms: list[Atom]) -> str:
        for atom in context_atoms:
            if atom.content_type == AtomContentType.LESSON:
                return atom.content.get("text", "")
        return ""

    def _language_from_capsule(self) -> str:
        fields = [
            (self.capsule.area or ""),
            (self.capsule.main_skill or ""),
            getattr(self.capsule, "description", "") or "",
        ]
        text = " ".join(fields).lower()

        candidates = [
            (['python', 'py'], 'python'),
            (['javascript', 'typescript', 'node', 'js', 'react'], 'javascript'),
            (['sql', 'postgres', 'mysql', 'sqlite'], 'sql'),
            (['java '], 'java'),
            (['swift'], 'swift'),
            (['kotlin'], 'java'),
            (['go '], 'go'),
            (['rust'], 'rust'),
            (['c#'], 'csharp'),
            (['c++'], 'cpp'),
            (['php'], 'php'),
        ]

        for keywords, lang in candidates:
            for keyword in keywords:
                if keyword in text:
                    return lang

        return 'python'

    def compute_progression_stage(self, molecule: Molecule) -> Dict[str, Any]:
        """Évalue la position de la molécule dans le parcours pour ajuster les projets."""
        granules = sorted(self.capsule.granules, key=lambda g: g.order or 0)
        sequence: List[Molecule] = []
        for granule in granules:
            sequence.extend(sorted(granule.molecules, key=lambda m: m.order or 0))

        total = len(sequence) or 1
        index = 0
        for idx, existing in enumerate(sequence):
            if existing.id == molecule.id:
                index = idx
                break

        denominator = max(total - 1, 1)
        ratio = index / denominator if total > 1 else 0.0

        stage_definitions = [
            {"slug": "foundation", "label": "Phase découverte", "difficulty": "débutant"},
            {"slug": "consolidation", "label": "Phase consolidation", "difficulty": "intermédiaire"},
            {"slug": "application", "label": "Phase application", "difficulty": "avancé"},
            {"slug": "mastery", "label": "Phase maîtrise", "difficulty": "expert"},
        ]

        if total <= 1:
            stage_idx = 0
        elif ratio < 0.25:
            stage_idx = 0
        elif ratio < 0.5:
            stage_idx = 1
        elif ratio < 0.75:
            stage_idx = 2
        else:
            stage_idx = 3

        stage = stage_definitions[stage_idx]
        return {
            "position": index + 1,
            "total_molecules": total,
            "ratio": ratio if total > 1 else 0.0,
            **stage,
        }

    def _build_reference_context(self, molecule: Molecule) -> Optional[str]:
        """Construit un contexte textuel basé sur le plan et la ressource fournie."""
        segments: List[str] = []
        chapter_meta = self._get_chapter_metadata(molecule)
        if isinstance(chapter_meta, dict):
            summary = chapter_meta.get("chapter_summary") or chapter_meta.get("summary")
            if summary:
                segments.append(f"Résumé ciblé:\n{summary.strip()}")
            key_points = chapter_meta.get("key_points") or chapter_meta.get("learning_objectives")
            if key_points:
                formatted_points = "\n".join(
                    f"- {point}" for point in key_points if isinstance(point, str) and point.strip()
                )
                if formatted_points:
                    segments.append(f"Points clés issus du document:\n{formatted_points}")
            references = chapter_meta.get("source_excerpt") or chapter_meta.get("source_passages")
            if isinstance(references, list):
                excerpt_text = "\n".join(filter(None, [ref.strip() for ref in references if isinstance(ref, str)]))
            elif isinstance(references, str):
                excerpt_text = references.strip()
            else:
                excerpt_text = ""
            if excerpt_text:
                segments.append(f"Extraits du support:\n{excerpt_text}")

        source_excerpt = self._get_source_excerpt()
        if source_excerpt:
            segments.append(f"Sélection de passages bruts:\n{source_excerpt}")

        if not segments:
            return None
        return "\n\n".join(segments)

    def _get_chapter_metadata(self, molecule: Molecule) -> Optional[Dict[str, Any]]:
        plan = self.capsule.learning_plan_json or {}
        levels = plan.get("levels")
        if not isinstance(levels, list):
            return None
        try:
            level = levels[molecule.granule.order - 1]
            chapters = level.get("chapters") if isinstance(level, dict) else None
            if not isinstance(chapters, list):
                return None
            return chapters[molecule.order - 1]
        except (IndexError, AttributeError, TypeError):
            return None

    def _get_source_excerpt(self, max_chars: int = 4000) -> Optional[str]:
        if not self.source_material:
            return None
        text = self.source_material.get("text")
        if not isinstance(text, str):
            return None
        snippet = text.strip()[:max_chars]
        return snippet or None

    def _create_code_example_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any] | None:
        lesson_text = self._extract_lesson_text(context_atoms)
        language = self._language_from_capsule()
        content = ai_service.generate_code_example(
            lesson_text=lesson_text,
            lesson_title=molecule.title,
            language=language,
            model_choice="gpt-5-mini-2025-08-07",
        )
        return content or {
            "description": "Exemple de code non disponible.",
            "language": language,
            "code": "",
            "explanation": "",
        }

    def _create_code_challenge_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any] | None:
        lesson_text = self._extract_lesson_text(context_atoms)
        language = self._language_from_capsule()
        content = ai_service.generate_code_challenge(
            lesson_text=lesson_text,
            lesson_title=molecule.title,
            language=language,
            model_choice="gpt-5-mini-2025-08-07",
        )
        return self._prepare_code_challenge_content(
            candidate=content,
            language=language,
            lesson_title=molecule.title,
        )

    def _create_live_code_executor_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any] | None:
        challenge_atom = next(
            (atom for atom in context_atoms if atom.content_type == AtomContentType.CODE_CHALLENGE),
            None,
        )
        challenge_content = dict(challenge_atom.content) if challenge_atom else {}
        lesson_text = self._extract_lesson_text(context_atoms)
        language = self._language_from_capsule()
        content = ai_service.generate_live_code_session(
            lesson_text=lesson_text,
            lesson_title=molecule.title,
            language=language,
            challenge=challenge_content,
            model_choice="gpt-5-mini-2025-08-07",
        )
        if content:
            content.setdefault("language", language)
            content.setdefault("starter_code", challenge_content.get("starter_code", ""))
            content.setdefault("hints", challenge_content.get("hints", []))
            if not content.get("instructions"):
                description = challenge_content.get("description") or "Applique le concept de la leçon dans le code ci-dessous."
                content["instructions"] = (
                    f"{description}\n\nExécute le code, observe la sortie dans la zone Résultat et ajuste jusqu'à ce qu'elle corresponde aux tests d'exemple."
                )
            return content
        fallback_challenge = self._prepare_code_challenge_content(
            candidate=None,
            language=language,
            lesson_title=molecule.title,
        )
        return {
            "language": language,
            "instructions": (
                f"{fallback_challenge['description']}\n\nModifie la fonction fournie, clique sur Exécuter pour vérifier la sortie,"
                " puis lance le challenge pour valider les tests."
            ),
            "starter_code": fallback_challenge.get("starter_code", ""),
            "hints": fallback_challenge.get("hints", []),
            "suggested_experiments": [
                "Teste plusieurs jeux de données pour valider le comportement.",
                "Ajoute une gestion d'erreurs en cas d'entrée invalide.",
            ],
        }

    def _create_code_sandbox_setup_content(self, molecule: Molecule, difficulty: Optional[str]) -> Dict[str, Any]:
        language = self._language_from_capsule()
        stage = self.compute_progression_stage(molecule)
        target_difficulty = difficulty or stage.get("difficulty")

        content = ai_service.generate_code_sandbox_setup(
            lesson_title=molecule.title,
            language=language,
            stage=stage,
            model_choice="gpt-5-mini-2025-08-07",
        )

        if content:
            content.setdefault("title", f"Espace de pratique sécurisé — {molecule.title}")
            content.setdefault("language", language)
            content.setdefault("difficulty", target_difficulty)
            content.setdefault("progression_stage", stage)
            security = content.setdefault("security", {})
            security.setdefault("code_submission_allowed", False)
            security.setdefault("sandbox_mode", "client_isolated")
            guidelines = security.setdefault("safe_usage_guidelines", [])
            reminder = "Ne colle jamais ton code dans la plateforme : exécute-le uniquement dans l'IDE sécurisé."
            if reminder not in guidelines:
                guidelines.append(reminder)
            checklist = content.setdefault("checklist", [])
            if not checklist:
                checklist.extend([
                    "IDE sécurisé lancé",
                    "Commandes de test exécutées",
                    "Sauvegarde locale effectuée",
                ])
            return content

        command_library = {
            "python": ["python --version", "pip --version"],
            "javascript": ["node --version", "npm --version"],
            "typescript": ["npx tsc --version"],
            "sql": ["psql --version"],
            "java": ["java --version"],
            "go": ["go version"],
            "rust": ["rustc --version"],
        }
        commands = command_library.get(language, ["echo 'Sandbox opérationnelle'"])

        return {
            "title": f"Espace de pratique sécurisé — {molecule.title}",
            "language": language,
            "difficulty": target_difficulty,
            "progression_stage": stage,
            "workspace": {
                "recommended_mode": "terminal+éditeur intégré",
                "setup_steps": [
                    "Lance le terminal sécurisé depuis l'interface d'apprentissage.",
                    "Vérifie que l'environnement isolé est bien chargé avant d'écrire du code.",
                    "Teste le fonctionnement avec une commande simple avant de commencer le projet.",
                ],
                "commands_to_try": commands,
            },
            "security": {
                "code_submission_allowed": False,
                "sandbox_mode": "client_isolated",
                "safe_usage_guidelines": [
                    "Le code s'exécute uniquement dans un bac à sable local et temporaire.",
                    "Ne partage ni ton code ni tes fichiers via le chat ou des formulaires.",
                    "Réinitialise l'environnement à la fin de la session ou en cas de doute.",
                ],
            },
            "checklist": [
                "Sandbox démarrée",
                "Commandes de vérification exécutées",
                "Notes de session sauvegardées localement",
            ],
        }

    # ------------------------------------------------------------------
    # Normalisation & fallbacks pour les challenges de code
    # ------------------------------------------------------------------

    def _prepare_code_challenge_content(
        self,
        candidate: Optional[Dict[str, Any]],
        language: str,
        lesson_title: str,
    ) -> Dict[str, Any]:
        fallback = self._fallback_code_challenge(language, lesson_title)
        base = candidate or {}

        normalized = {
            "title": base.get("title") or fallback["title"],
            "description": base.get("description") or fallback["description"],
            "language": language,
            "starter_code": dedent(base.get("starter_code") or fallback["starter_code"]).strip("\n"),
            "sample_tests": self._normalize_sample_tests(base.get("sample_tests"), fallback["sample_tests"]),
            "hints": self._normalize_string_list(base.get("hints"), fallback["hints"]),
        }

        if not normalized["sample_tests"]:
            normalized["sample_tests"] = fallback["sample_tests"]
        if not normalized["hints"]:
            normalized["hints"] = fallback["hints"]

        return normalized

    def _normalize_sample_tests(
        self,
        raw_tests: Any,
        default: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        if isinstance(raw_tests, dict):
            if "tests" in raw_tests and isinstance(raw_tests["tests"], list):
                raw_tests = raw_tests["tests"]
            elif "samples" in raw_tests and isinstance(raw_tests["samples"], list):
                raw_tests = raw_tests["samples"]
            else:
                raw_tests = list(raw_tests.values())

        normalized: list[dict[str, str]] = []
        if isinstance(raw_tests, list):
            for entry in raw_tests:
                if isinstance(entry, dict):
                    input_value = entry.get("input") if "input" in entry else entry.get("stdin")
                    output_value = (
                        entry.get("output")
                        if "output" in entry
                        else entry.get("expected")
                    )
                elif isinstance(entry, (tuple, list)) and len(entry) >= 2:
                    input_value, output_value = entry[0], entry[1]
                else:
                    continue

                input_str = self._stringify_test_field(input_value)
                output_str = self._stringify_test_field(output_value)

                if input_str is None or output_str is None:
                    continue

                normalized.append({"input": input_str, "output": output_str})

        if normalized:
            return normalized
        return [dict(item) for item in default]

    def _normalize_string_list(self, value: Any, default: list[str]) -> list[str]:
        items: list[str] = []
        if isinstance(value, list):
            for entry in value:
                if entry is None:
                    continue
                text = entry if isinstance(entry, str) else str(entry)
                text = text.strip()
                if text:
                    items.append(text)
        if items:
            return items
        return list(default)

    def _stringify_test_field(self, value: Any) -> str | None:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip("\n")
        if isinstance(value, (int, float, bool)):
            return str(value)
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return str(value)

    def _fallback_code_challenge(self, language: str, lesson_title: str) -> Dict[str, Any]:
        language = (language or "python").lower()
        if language != "python":
            return {
                "title": f"Mini-projet — {lesson_title}",
                "description": (
                    "Propose un petit script dans le langage ciblé pour mettre en pratique la leçon. "
                    "Concentre-toi sur un exemple concret inspiré du chapitre et prépare un mini-sujet à montrer à ton pair."
                ),
                "language": language,
                "starter_code": "// Début de ton script\n",
                "sample_tests": [],
                "hints": [
                    "Commence par décrire ce que ton programme reçoit et ce qu'il doit retourner.",
                    "Découpe le problème en fonctions simples et teste-les individuellement.",
                ],
            }

        templates = [
            {
                "title": "Analyse de séries numériques — {lesson}",
                "description": (
                    "Écris un programme qui lit une liste d'entiers depuis l'entrée standard et retourne la somme des "
                    "nombres pairs. Utilise cette base pour t'assurer que tu maîtrises les boucles et les conditions."
                ),
                "starter_code": dedent(
                    """
                    from typing import List

                    def solve(numbers: List[int]) -> int:
                        # Additionne uniquement les nombres pairs
                        # TODO: implémente la logique ici
                        return 0

                    def parse_input(raw: str) -> List[int]:
                        if not raw.strip():
                            return []
                        return [int(part) for part in raw.split()]

                    if __name__ == "__main__":
                        import sys

                        data = parse_input(sys.stdin.read())
                        print(solve(data))
                    """
                ).strip("\n"),
                "sample_tests": [
                    {"input": "1 2 3 4 5", "output": "6"},
                    {"input": "10 11 12", "output": "22"},
                ],
                "hints": [
                    "Commence par transformer la chaîne d'entrée en liste d'entiers.",
                    "Utilise une compréhension de liste ou une boucle pour filtrer les valeurs paires.",
                ],
            },
            {
                "title": "Nettoyage de texte — {lesson}",
                "description": (
                    "Construit une fonction qui normalise une phrase: suppression des espaces superflus, passage en minuscules, "
                    "et remplacement des caractères accentués par leur équivalent sans accent. Affiche le résultat final."
                ),
                "starter_code": dedent(
                    """
                    import sys
                    import unicodedata

                    def normalize(text: str) -> str:
                        # Retourne un slug lisible depuis une phrase
                        # TODO: compléter la fonction
                        return text

                    if __name__ == "__main__":
                        raw = sys.stdin.read()
                        print(normalize(raw))
                    """
                ).strip("\n"),
                "sample_tests": [
                    {
                        "input": "Bonjour    Monde!",
                        "output": "bonjour monde!",
                    },
                    {
                        "input": "Énergie  propre",
                        "output": "energie propre",
                    },
                ],
                "hints": [
                    "Utilise `unicodedata.normalize` pour gérer les accents.",
                    "Pense à la méthode `split()` pour réduire les espaces multiples.",
                ],
            },
            {
                "title": "Tableau de fréquences — {lesson}",
                "description": (
                    "À partir d'un flux JSON contenant des mots, calcule combien de fois chaque mot apparaît et affiche le "
                    "résultat au format JSON trié par fréquence décroissante."
                ),
                "starter_code": dedent(
                    """
                    import json
                    import sys
                    from collections import Counter

                    def solve(words: list[str]) -> dict[str, int]:
                        # TODO: implémente la logique de comptage
                        return {}

                    if __name__ == "__main__":
                        raw = sys.stdin.read().strip() or "[]"
                        words = json.loads(raw)
                        result = solve(words)
                        print(json.dumps(result, ensure_ascii=False))
                    """
                ).strip("\n"),
                "sample_tests": [
                    {
                        "input": "[\"python\", \"ai\", \"python\"]",
                        "output": "{\"python\": 2, \"ai\": 1}",
                    },
                    {
                        "input": "[\"data\", \"data\", \"lab\"]",
                        "output": "{\"data\": 2, \"lab\": 1}",
                    },
                ],
                "hints": [
                    "`collections.Counter` peut t'éviter beaucoup de code.",
                    "N'oublie pas de convertir le Counter en dictionnaire standard avant l'affichage.",
                ],
            },
            {
                "title": "Planificateur de tâches — {lesson}",
                "description": (
                    "Reçois en entrée un JSON représentant des tâches avec une priorité et une durée. "
                    "Affiche la durée totale et la prochaine tâche la plus prioritaire."
                ),
                "starter_code": dedent(
                    """
                    import json
                    import sys

                    def planify(tasks: list[dict]) -> dict:
                        # TODO: calcule la durée totale et la tâche prioritaire
                        return {"total_duration": 0, "next_task": None}

                    if __name__ == "__main__":
                        raw = sys.stdin.read().strip() or "[]"
                        tasks = json.loads(raw)
                        result = planify(tasks)
                        print(json.dumps(result, ensure_ascii=False))
                    """
                ).strip("\n"),
                "sample_tests": [
                    {
                        "input": "[{\"name\": \"setup env\", \"priority\": 2, \"duration\": 15}, {\"name\": \"write tests\", \"priority\": 1, \"duration\": 30}]",
                        "output": "{\"total_duration\": 45, \"next_task\": \"write tests\"}",
                    },
                    {
                        "input": "[{\"name\": \"refactor\", \"priority\": 3, \"duration\": 40}]",
                        "output": "{\"total_duration\": 40, \"next_task\": \"refactor\"}",
                    },
                ],
                "hints": [
                    "Utilise `sorted` avec la clé `priority` pour identifier la tâche urgente.",
                    "Additionne les durées avec une compréhension ou `sum`.",
                ],
            },
        ]

        index = sum(ord(c) for c in lesson_title.lower()) % len(templates) if lesson_title else 0
        template = templates[index]
        return {
            "title": template["title"].format(lesson=lesson_title),
            "description": template["description"],
            "language": "python",
            "starter_code": template["starter_code"],
            "sample_tests": template["sample_tests"],
            "hints": template["hints"],
        }

    def _create_code_project_brief_content(self, molecule: Molecule, context_atoms: list[Atom], difficulty: Optional[str]) -> Dict[str, Any]:
        lesson_text = self._extract_lesson_text(context_atoms)
        language = self._language_from_capsule()
        stage = self.compute_progression_stage(molecule)
        target_difficulty = difficulty or stage.get("difficulty")

        content = ai_service.generate_code_project_brief(
            lesson_text=lesson_text,
            lesson_title=molecule.title,
            language=language,
            stage=stage,
            model_choice="gpt-5-mini-2025-08-07",
        )

        if content:
            content.setdefault("title", f"Projet de validation — {molecule.title}")
            content.setdefault("language", language)
            content.setdefault("difficulty", target_difficulty)
            content.setdefault("progression_stage", stage)
            security = content.setdefault("security", {})
            security.setdefault("code_submission_allowed", False)
            security.setdefault("reminders", [
                "Ne partage pas ton code dans le chat : valide-le dans le bac à sable sécurisé.",
                "Conserve une copie locale de ton travail plutôt que de l'uploader.",
            ])
            return content

        fallback_objectives = [
            "Appliquer le concept central de la leçon dans un cas réel.",
            "Structurer ton code avec des fonctions/classe clairement identifiées.",
            "Rédiger une courte documentation d'exécution.",
        ]
        fallback_milestones = [
            {
                "label": "Conception",
                "steps": [
                    "Liste les fonctionnalités indispensables et optionnelles.",
                    "Définis les entrées/sorties de chaque fonction principale.",
                ],
            },
            {
                "label": "Implémentation",
                "steps": [
                    "Code la solution dans l'IDE sécurisé.",
                    "Ajoute des tests ou commandes de vérification automatiques.",
                ],
            },
            {
                "label": "Vérifications finales",
                "steps": [
                    "Relis ton code et élimine les répétitions inutiles.",
                    "Documente comment lancer ton projet depuis le terminal intégré.",
                ],
            },
        ]

        return {
            "title": f"Projet de validation — {molecule.title}",
            "summary": "Réalise un mini-projet pour valider les acquis de cette leçon.",
            "language": language,
            "difficulty": target_difficulty,
            "progression_stage": stage,
            "objectives": fallback_objectives,
            "milestones": fallback_milestones,
            "deliverables": [
                "Code fonctionnel dans la sandbox sécurisée.",
                "README ou notes expliquant l'exécution et les tests.",
                "Synthèse de trois points d'amélioration envisagés.",
            ],
            "validation": {
                "self_checklist": [
                    "Toutes les commandes de test passent dans l'environnement sécurisé.",
                    "Le code respecte les conventions du langage utilisé.",
                    "La documentation décrit clairement comment lancer et vérifier le projet.",
                ],
                "suggested_tests": [
                    "Tester différents cas limites dans la sandbox.",
                    "Expliquer la solution à voix haute ou à un pair pour valider la compréhension.",
                ],
            },
            "security": {
                "code_submission_allowed": False,
                "reminders": [
                    "Garde ton code et tes fichiers dans l'IDE sécurisé, ne les colle pas dans le chat.",
                    "Réinitialise la sandbox après usage et supprime les fichiers sensibles.",
                ],
            },
            "extension_ideas": [
                "Ajoute une fonctionnalité bonus pour aller plus loin.",
                "Prépare une suite de tests automatisés supplémentaires.",
            ],
        }

    def _create_fill_in_blank_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any]:
        lesson_text = self._extract_lesson_text(context_atoms)
        if lesson_text:
            try:
                candidate = ai_service.generate_fill_in_blank_exercise(
                    lesson_text=lesson_text,
                    topic=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                )
                if isinstance(candidate, dict) and candidate.get("text"):
                    return candidate
            except Exception as exc:  # pragma: no cover
                logger.warning("Fill-in IA failure for %s: %s", molecule.title, exc)
        return {
            "prompt": f"Complète les éléments essentiels du concept {molecule.title}.",
            "text": f"{molecule.title} implique {{1}} fondamentales et nécessite {{2}} pour être vérifié expérimentalement.",
            "blanks": [
                {"answers": ["des lois", "des principes"]},
                {"answers": ["des mesures", "des observations"]},
            ],
        }

    def _create_flashcards_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any]:
        lesson_text = self._extract_lesson_text(context_atoms)
        if lesson_text:
            try:
                candidate = ai_service.generate_flashcards(
                    lesson_text=lesson_text,
                    topic=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                )
                if isinstance(candidate, dict) and candidate.get("cards"):
                    return candidate
            except Exception as exc:  # pragma: no cover
                logger.warning("Flashcards IA failure for %s: %s", molecule.title, exc)
        return {
            "prompt": f"Notions clés à retenir pour {molecule.title}",
            "cards": [
                {"front": molecule.title, "back": "Définition concise."},
                {"front": "Application", "back": "Exemple tiré de la leçon."},
                {"front": "Attention", "back": "Piège ou erreur fréquente."},
            ],
        }

    def _create_short_answer_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any]:
        lesson_text = self._extract_lesson_text(context_atoms)
        if lesson_text:
            try:
                candidate = ai_service.generate_short_answer_exercise(
                    lesson_text=lesson_text,
                    topic=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                )
                if isinstance(candidate, dict) and candidate.get("prompt"):
                    return candidate
            except Exception as exc:  # pragma: no cover
                logger.warning("Short-answer IA failure for %s: %s", molecule.title, exc)
        return {
            "prompt": f"Résume en une phrase l'idée clé de {molecule.title}.",
            "acceptable_answers": [molecule.title],
            "explanation": "Mentionner la propriété principale étudiée.",
        }

    def _create_true_false_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any]:
        lesson_text = self._extract_lesson_text(context_atoms)
        if lesson_text:
            try:
                candidate = ai_service.generate_true_false_exercise(
                    lesson_text=lesson_text,
                    topic=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                )
                if isinstance(candidate, dict) and "correct_answer" in candidate:
                    return candidate
            except Exception as exc:  # pragma: no cover
                logger.warning("True/False IA failure for %s: %s", molecule.title, exc)
        return {
            "statement": f"{molecule.title} ne fait appel qu'à l'observation et jamais à la modélisation.",
            "correct_answer": False,
            "explanation": "Les sciences combinent observation, modélisation et expérimentation.",
        }

    def _create_matching_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any]:
        lesson_text = self._extract_lesson_text(context_atoms)
        if lesson_text:
            try:
                candidate = ai_service.generate_matching_exercise(
                    lesson_text=lesson_text,
                    topic=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                )
                if isinstance(candidate, dict) and candidate.get("pairs"):
                    return candidate
            except Exception as exc:  # pragma: no cover
                logger.warning("Matching IA failure for %s: %s", molecule.title, exc)
        return {
            "prompt": f"Associe chaque notion liée à {molecule.title} à la bonne description.",
            "pairs": [
                {"left": "Grandeur mesurée", "right": "Valeur déterminée lors d'une expérience"},
                {"left": "Modèle", "right": "Représentation simplifiée d'un phénomène"},
            ],
        }

    def _create_ordering_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any]:
        lesson_text = self._extract_lesson_text(context_atoms)
        if lesson_text:
            try:
                candidate = ai_service.generate_ordering_exercise(
                    lesson_text=lesson_text,
                    topic=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                )
                if isinstance(candidate, dict) and candidate.get("items"):
                    return candidate
            except Exception as exc:  # pragma: no cover
                logger.warning("Ordering IA failure for %s: %s", molecule.title, exc)
        return {
            "prompt": f"Classe les étapes du raisonnement scientifique associé à {molecule.title}.",
            "items": [
                "Observer le phénomène",
                "Formuler une hypothèse",
                "Mettre en place l'expérience",
                "Interpréter les résultats",
            ],
        }

    def _create_categorization_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any]:
        lesson_text = self._extract_lesson_text(context_atoms)
        if lesson_text:
            try:
                candidate = ai_service.generate_categorization_exercise(
                    lesson_text=lesson_text,
                    topic=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                )
                if isinstance(candidate, dict) and candidate.get("categories"):
                    return candidate
            except Exception as exc:  # pragma: no cover
                logger.warning("Categorization IA failure for %s: %s", molecule.title, exc)
        return {
            "prompt": f"Classe chaque élément selon qu'il est directement lié à {molecule.title}.",
            "categories": [
                {"id": "relie", "label": "Lié"},
                {"id": "non_relie", "label": "Non lié"},
            ],
            "items": [
                {"id": "item1", "label": molecule.title, "correct_category": "relie"},
                {"id": "item2", "label": "Bruit expérimental", "correct_category": "non_relie"},
            ],
        }

    def _create_diagram_completion_content(self, molecule: Molecule, context_atoms: list[Atom]) -> Dict[str, Any]:
        lesson_text = self._extract_lesson_text(context_atoms)
        if lesson_text:
            try:
                candidate = ai_service.generate_diagram_completion(
                    lesson_text=lesson_text,
                    topic=molecule.title,
                    model_choice="gpt-5-mini-2025-08-07",
                )
                if isinstance(candidate, dict) and candidate.get("slots"):
                    return candidate
            except Exception as exc:  # pragma: no cover
                logger.warning("Diagram IA failure for %s: %s", molecule.title, exc)
        return {
            "title": f"Complète le schéma simplifié de {molecule.title}",
            "slots": [
                {
                    "id": "slot1",
                    "label": "Élément central",
                    "options": [
                        {"value": molecule.title, "label": molecule.title},
                        {"value": "Inconnu", "label": "Inconnu"},
                    ],
                    "correct_option": molecule.title,
                }
            ],
        }
