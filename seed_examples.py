# -*- coding: utf-8 -*-

import sys
import json
import logging

# Pour que les imports 'app....' fonctionnent si on lance depuis la racine
sys.path.append('.')
from app.db import base as _base

from app.db.session import SessionLocal
from app.core.ai_service import get_text_embedding
from app.models.analytics.golden_examples_model import GoldenExample

# Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_golden_examples")

# -----------------------------------------------------------------
# ⚠️ IMPORTANT : N'insère PAS de triple guillemets """ à l'intérieur du JSON.
# Si tu dois mettre du code ou du SQL, encode-les comme chaînes JSON avec \n.
# -----------------------------------------------------------------

EXAMPLES_JSON_STRINGS = [
r"""{
  "schema_version": "1.0",
  "example_type": "exercise_mcq",
  "subject": "Français (FLÉ)",
  "topic": "Subjonctif vs indicatif",
  "language": "fr",
  "difficulty": "moyen",
  "cefr_level": "B2",
  "tags": ["grammaire", "conjugaison", "QCM"],
  "instructions": "Choisissez la forme verbale correcte pour compléter chaque phrase.",
  "items": [
    {
      "id": "q1",
      "stem": "Il faut que tu ___ (faire) attention.",
      "choices": [
        {"id": "A", "text": "fais", "is_correct": false, "rationale": "Indicatif présent — on attend le subjonctif après 'il faut que'."},
        {"id": "B", "text": "fasses", "is_correct": true,  "rationale": "Après 'il faut que', on emploie le subjonctif: 'tu fasses'."},
        {"id": "C", "text": "feras", "is_correct": false, "rationale": "Futur simple inadapté ici."},
        {"id": "D", "text": "ferais", "is_correct": false, "rationale": "Conditionnel inadapté ici."}
      ]
    },
    {
      "id": "q2",
      "stem": "Je pense qu'il ___ (venir) demain.",
      "choices": [
        {"id": "A", "text": "vient", "is_correct": true,  "rationale": "Avec 'penser que' affirmatif, on emploie généralement l'indicatif."},
        {"id": "B", "text": "vienne", "is_correct": false, "rationale": "Le subjonctif s'emploie plutôt avec la négation ou le doute."},
        {"id": "C", "text": "viendra", "is_correct": false, "rationale": "Futur possible mais le contexte privilégie l'indicatif présent."},
        {"id": "D", "text": "viendrait", "is_correct": false, "rationale": "Conditionnel marque l'hypothèse, non demandé ici."}
      ]
    },
    {
      "id": "q3",
      "stem": "Bien que ce ___ (être) difficile, ils ont réussi.",
      "choices": [
        {"id": "A", "text": "est", "is_correct": false, "rationale": "Après 'bien que', on emploie le subjonctif."},
        {"id": "B", "text": "soit", "is_correct": true,  "rationale": "Subjonctif requis après 'bien que'."},
        {"id": "C", "text": "sera", "is_correct": false, "rationale": "Futur inadapté."},
        {"id": "D", "text": "serait", "is_correct": false, "rationale": "Conditionnel inadapté."}
      ]
    }
  ],
  "solutions": { "short": {"q1": "B", "q2": "A", "q3": "B"} },
  "rubric": { "criteria": [{"name": "Exactitude", "weight": 1}], "passing_threshold": 0.7 },
  "validation": { "auto_gradable": true },
  "style_guidelines": "Explications brèves, ton bienveillant, exemples authentiques."
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_cloze",
  "subject": "Français (FLÉ)",
  "topic": "Vocabulaire du travail à distance",
  "language": "fr",
  "difficulty": "moyen",
  "cefr_level": "B1",
  "tags": ["lexique", "contexte", "texte à trous"],
  "instructions": "Complétez le texte avec les mots de la banque. Un mot n'est pas utilisé.",
  "materials": {
    "passage": "Depuis la généralisation du travail à distance, les équipes doivent \\ncoordonner leurs tâches via des outils de [1] en ligne. Les réunions \\nse tiennent souvent en [2], et il est essentiel de définir des [3] clairs \\npour éviter les malentendus. Grâce aux [4] partagés, chacun suit l'avancement \\ndes projets."
  },
  "word_bank": ["objectifs", "tableaux", "messagerie", "visioconférence", "agenda"],
  "blanks": [
    {"id": 1, "answer": "messagerie", "alternatives": ["chat"], "explanation": "Outils de communication écrite."},
    {"id": 2, "answer": "visioconférence", "alternatives": ["video-conférence", "conférence vidéo"], "explanation": "Réunions à distance."},
    {"id": 3, "answer": "objectifs", "alternatives": ["objectifs clairs"], "explanation": "Cibles à atteindre."},
    {"id": 4, "answer": "tableaux", "alternatives": ["tableaux partagés", "tableaux de bord"], "explanation": "Supports collaboratifs (kanban, etc.)."}
  ],
  "solutions": { "short": {"1": "messagerie", "2": "visioconférence", "3": "objectifs", "4": "tableaux"} },
  "rubric": { "criteria": [{"name": "Précision lexicale", "weight": 1}] },
  "validation": { "auto_gradable": true },
  "style_guidelines": "Texte authentique, vocabulaire métier moderne."
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_listening_mcq",
  "subject": "Français (FLÉ)",
  "topic": "Annonce de service client",
  "language": "fr",
  "difficulty": "facile",
  "cefr_level": "A2",
  "tags": ["écoute", "compréhension", "A2"],
  "instructions": "Écoutez l'extrait audio et répondez aux questions.",
  "materials": {
    "audio_url": "https://example.com/audio/annonce_service_client.mp3",
    "transcript": "Bonjour, vous avez appelé le service client de Luminex. Nos \\nhoraires sont du lundi au vendredi, de 9 h à 18 h. Pour le suivi \\ndes commandes, tapez 1 ; pour l'assistance technique, tapez 2."
  },
  "items": [
    {
      "id": "q1",
      "stem": "Quels sont les horaires du service ?",
      "choices": [
        {"id": "A", "text": "7 j/7, 8 h – 20 h", "is_correct": false, "rationale": "Ce n'est pas mentionné."},
        {"id": "B", "text": "Du lundi au vendredi, 9 h – 18 h", "is_correct": true,  "rationale": "Cité explicitement."},
        {"id": "C", "text": "Week-end uniquement", "is_correct": false, "rationale": "Faux."}
      ]
    },
    {
      "id": "q2",
      "stem": "Quel numéro faut-il taper pour l'assistance technique ?",
      "choices": [
        {"id": "A", "text": "1", "is_correct": false, "rationale": "1 = suivi des commandes."},
        {"id": "B", "text": "2", "is_correct": true,  "rationale": "2 = assistance technique."},
        {"id": "C", "text": "3", "is_correct": false, "rationale": "Option non proposée."}
      ]
    }
  ],
  "solutions": { "short": {"q1": "B", "q2": "B"} },
  "rubric": { "criteria": [{"name": "Compréhension d'informations factuelles", "weight": 1}] },
  "validation": { "auto_gradable": true }
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_speaking_prompt",
  "subject": "Français (FLÉ)",
  "topic": "Présenter un projet en 90 secondes",
  "language": "fr",
  "difficulty": "moyen",
  "cefr_level": "B2",
  "tags": ["production orale", "présentation", "B2"],
  "instructions": "Enregistrez une présentation de 60–90 s décrivant un projet passé. Indiquez l'objectif, les étapes clés, le résultat et une leçon apprise.",
  "expected_answer": {
    "duration_seconds": {"min": 60, "max": 90},
    "key_points": ["objectif", "rôle personnel", "résultat mesurable", "leçon apprise"]
  },
  "rubric": {
    "criteria": [
      {"name": "Fluidité et cohérence", "weight": 0.35, "levels": [{"label": "Excellent", "descriptor": "Discours continu, connecteurs variés"}]},
      {"name": "Richesse lexicale", "weight": 0.25},
      {"name": "Correction grammaticale", "weight": 0.25},
      {"name": "Prononciation", "weight": 0.15}
    ],
    "passing_threshold": 0.7
  },
  "validation": { "auto_gradable": false },
  "style_guidelines": "Encourager un ton clair et structuré, éviter la lecture mot-à-mot."
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_reading_short_answer",
  "subject": "Français (FLÉ)",
  "topic": "Article de blog – Télétravail et productivité",
  "language": "fr",
  "difficulty": "moyen",
  "cefr_level": "B1",
  "tags": ["compréhension écrite", "réponses courtes"],
  "instructions": "Lisez le passage puis répondez en 1–2 phrases.",
  "materials": {
    "passage": "De nombreuses études indiquent que le télétravail peut accroître la productivité quand les objectifs sont clairement définis et que l'équipement est adéquat. Toutefois, l'isolement et la surcharge informationnelle constituent des risques à surveiller."
  },
  "items": [
    {"id": "q1", "prompt": "Dans quelles conditions le télétravail améliore-t-il la productivité ?", "expected_keywords": ["objectifs clairs", "équipement adéquat"]},
    {"id": "q2", "prompt": "Citez un risque lié au télétravail mentionné dans le texte.", "expected_keywords": ["isolement", "surcharge informationnelle"]}
  ],
  "solutions": {"short": {"q1": "Quand les objectifs sont clairs et que l'équipement est adéquat.", "q2": "L'isolement ou la surcharge informationnelle."}},
  "rubric": {"criteria": [{"name": "Pertinence des informations", "weight": 1}], "passing_threshold": 0.7},
  "validation": {"auto_gradable": true, "tests": [{"type": "keyword_match", "min_keywords": 1}]}
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_code_fix",
  "subject": "Programmation",
  "topic": "JavaScript – Correction de fonction asynchrone",
  "language": "fr",
  "difficulty": "moyen",
  "cefr_level": "n/a",
  "tags": ["javascript", "async", "tests"],
  "instructions": "Corrigez la fonction pour qu'elle renvoie un tableau d'utilisateurs actifs. N'utilisez pas de librairies externes.",
  "materials": {
    "code": "async function getActiveUsers(api) {\\n  const res = api.fetch('/users'); // BUG: manque await\\n  if (!res.ok) throw new Error('Network');\\n  const users = await res.json();\\n  return users.filter(u => u.active = true); // BUG: affectation au lieu de comparaison\\n}"
  },
  "validation": {
    "auto_gradable": true,
    "tests": [
      {"name": "calls api once", "input": [], "assert": "api.fetch called once with '/users'"},
      {"name": "filters active", "input": [], "assert": "only users with active===true returned"}
    ]
  },
  "solutions": {
    "short": "Utiliser await sur fetch et remplacer l'affectation par une comparaison stricte.",
    "detailed": "async function getActiveUsers(api) {\\n  const res = await api.fetch('/users');\\n  if (!res.ok) throw new Error('Network');\\n  const users = await res.json();\\n  return users.filter(u => u.active === true);\\n}"
  },
  "style_guidelines": "Clarté, gestion d'erreur minimale, comparaison stricte."
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_sql",
  "subject": "Bases de données",
  "topic": "SQL – Ventes mensuelles par catégorie",
  "language": "fr",
  "difficulty": "moyen",
  "tags": ["sql", "group by", "agrégation"],
  "instructions": "Écrivez une requête qui retourne, pour le mois de mars 2024, le total des ventes par catégorie (category_name) classé du plus élevé au plus faible.",
  "materials": {
    "schema": {
      "tables": {
        "orders": ["id", "order_date", "customer_id"],
        "order_items": ["order_id", "product_id", "quantity", "unit_price"],
        "products": ["id", "category_id", "name"],
        "categories": ["id", "category_name"]
      }
    }
  },
  "expected_answer": "SELECT c.category_name,\\n       SUM(oi.quantity * oi.unit_price) AS total_sales\\nFROM orders o\\nJOIN order_items oi ON oi.order_id = o.id\\nJOIN products p ON p.id = oi.product_id\\nJOIN categories c ON c.id = p.category_id\\nWHERE o.order_date >= DATE '2024-03-01'\\n  AND o.order_date <  DATE '2024-04-01'\\nGROUP BY c.category_name\\nORDER BY total_sales DESC;",
  "validation": {"auto_gradable": false},
  "solutions": {"short": "Agréger quantity*unit_price par catégorie avec filtre sur mars 2024."}
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_mcq",
  "subject": "Informatique",
  "topic": "Complexité – Recherche binaire",
  "language": "fr",
  "difficulty": "facile",
  "tags": ["algorithmes", "complexité", "QCM"],
  "instructions": "Choisissez la bonne réponse.",
  "items": [
    {
      "id": "q1",
      "stem": "La complexité temporelle moyenne de la recherche binaire est…",
      "choices": [
        {"id": "A", "text": "O(1)", "is_correct": false, "rationale": "Constante — incorrect."},
        {"id": "B", "text": "O(log n)", "is_correct": true,  "rationale": "Division par 2 à chaque étape."},
        {"id": "C", "text": "O(n)", "is_correct": false, "rationale": "Linéaire — c'est la recherche séquentielle."}
      ]
    }
  ],
  "solutions": {"short": {"q1": "B"}},
  "rubric": {"criteria": [{"name": "Exactitude", "weight": 1}]}
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_short_answer",
  "subject": "Histoire",
  "topic": "Restauration Meiji (Japon)",
  "language": "fr",
  "difficulty": "moyen",
  "tags": ["Japon", "XIXe siècle", "cause-conséquence"],
  "instructions": "Répondez en 2–3 phrases.",
  "materials": {
    "passage": "La Restauration Meiji (1868) met fin au shogunat Tokugawa et ouvre une période d'industrialisation rapide, de réformes politiques et d'occidentalisation partielle du Japon."
  },
  "items": [
    {"id": "q1", "prompt": "Citez une cause majeure de la Restauration Meiji."},
    {"id": "q2", "prompt": "Indiquez une conséquence économique directe dans les décennies suivantes."}
  ],
  "solutions": {
    "short": {
      "q1": "La contestation du shogunat face aux pressions occidentales et l'ouverture forcée des ports (traités inégaux).",
      "q2": "Industrialisation rapide et développement d'infrastructures (chemins de fer, usines)."
    }
  },
  "rubric": {"criteria": [{"name": "Exactitude historique", "weight": 0.6}, {"name": "Clarté", "weight": 0.4}], "passing_threshold": 0.7},
  "validation": {"auto_gradable": false}
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_matching",
  "subject": "Culture générale",
  "topic": "Inventions et inventeurs",
  "language": "fr",
  "difficulty": "facile",
  "tags": ["matching", "mémoire"],
  "instructions": "Associez chaque invention à son inventeur.",
  "pairs": {
    "left": ["Électricité alternée", "Téléphone", "Pénicilline", "Imprimerie à caractères mobiles"],
    "right": ["Gutenberg", "Bell", "Fleming", "Tesla"]
  },
  "solution_map": {
    "Électricité alternée": "Tesla",
    "Téléphone": "Bell",
    "Pénicilline": "Fleming",
    "Imprimerie à caractères mobiles": "Gutenberg"
  },
  "rubric": {"criteria": [{"name": "Exactitude", "weight": 1}]},
  "validation": {"auto_gradable": true}
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_guided_problem",
  "subject": "Mathématiques",
  "topic": "Système de deux équations",
  "language": "fr",
  "difficulty": "moyen",
  "tags": ["algèbre", "système", "résolution"],
  "instructions": "Résolvez le système suivant: { 2x + 3y = 13 ; x - y = 1 }.",
  "expected_answer": {"x": 4, "y": 3},
  "solutions": {
    "short": "x = 4, y = 3",
    "detailed": "Soustrayez: de x - y = 1, on a x = y + 1. Substituez dans 2x + 3y = 13 ⇒ 2(y+1) + 3y = 13 ⇒ 5y + 2 = 13 ⇒ y = 3 ⇒ x = 4."
  },
  "rubric": {"criteria": [{"name": "Résultat", "weight": 0.6}, {"name": "Méthode", "weight": 0.4}], "passing_threshold": 0.7},
  "validation": {"auto_gradable": true, "tests": [{"type": "equals", "field": "x", "value": 4}, {"type": "equals", "field": "y", "value": 3}]}
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_balancing",
  "subject": "Chimie",
  "topic": "Équilibrer une combustion d'hydrocarbure",
  "language": "fr",
  "difficulty": "moyen",
  "tags": ["stoéchiométrie", "équilibrage"],
  "instructions": "Équilibrez l'équation suivante: C3H8 + O2 → CO2 + H2O",
  "expected_answer": "C3H8 + 5 O2 → 3 CO2 + 4 H2O",
  "solutions": {"short": "1, 5, 3, 4", "detailed": "Balancez C (3) ⇒ 3 CO2 ; H (8) ⇒ 4 H2O ; O total à droite = 3*2 + 4 = 10 ⇒ 5 O2."},
  "rubric": {"criteria": [{"name": "Conservation des atomes", "weight": 1}]},
  "validation": {"auto_gradable": true}
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_essay_rubric",
  "subject": "Rédaction académique",
  "topic": "Argumentation courte (250–300 mots)",
  "language": "fr",
  "difficulty": "moyen",
  "tags": ["rédaction", "rubrique", "évaluation"],
  "instructions": "Rédigez un essai argumentatif de 250–300 mots répondant à la question: 'Faut-il généraliser la semaine de 4 jours ?'",
  "rubric": {
    "criteria": [
      {"name": "Thèse et structure", "weight": 0.25, "levels": [{"label": "Excellent", "descriptor": "Thèse claire, progression logique"}]},
      {"name": "Arguments et preuves", "weight": 0.35},
      {"name": "Cohésion et connecteurs", "weight": 0.15},
      {"name": "Langue (grammaire/lexique)", "weight": 0.15},
      {"name": "Conclusion et ouverture", "weight": 0.10}
    ],
    "passing_threshold": 0.7
  },
  "anchor_responses": {
    "high": "L'essai présente une thèse nette, deux arguments étayés par des données ou exemples pertinents, contre-argument traité et réfuté, conclusion qui synthétise et ouvre.",
    "medium": "Thèse identifiable, arguments présents mais inégaux, articulation parfois faible.",
    "low": "Thèse floue, arguments insuffisants, cohérence fragile."
  },
  "validation": {"auto_gradable": false},
  "style_guidelines": "Encourager exemples concrets, éviter les généralisations vagues."
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_error_diagnosis",
  "subject": "Français (FLÉ)",
  "topic": "Accord du participe passé avec 'être'",
  "language": "fr",
  "difficulty": "moyen",
  "cefr_level": "B1",
  "tags": ["grammaire", "diagnostic", "feedback"],
  "instructions": "Identifiez l'erreur et proposez une correction.",
  "items": [
    {
      "id": "s1",
      "learner_sentence": "Elles sont arrivé hier soir.",
      "error_type": "accord participe passé",
      "expected_correction": "Elles sont arrivées hier soir.",
      "explanation": "Avec l'auxiliaire 'être', le participe passé s'accorde en genre et en nombre avec le sujet."
    }
  ],
  "solutions": {"short": {"s1": "arrivées"}},
  "rubric": {"criteria": [{"name": "Identification de l'erreur", "weight": 0.5}, {"name": "Correction appropriée", "weight": 0.5}]},
  "validation": {"auto_gradable": true}
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_design_prompt",
  "subject": "Architecture logicielle",
  "topic": "Concevoir une API REST pour une Todo List",
  "language": "fr",
  "difficulty": "moyen",
  "tags": ["design", "api", "rest"],
  "instructions": "Proposez la conception d'une API REST pour gérer des tâches (todos): endpoints, schémas JSON, statuts HTTP, règles d'authentification.",
  "expected_answer": {
    "endpoints_min": ["GET /todos", "POST /todos", "GET /todos/{id}", "PATCH /todos/{id}", "DELETE /todos/{id}"],
    "auth": "Bearer JWT",
    "schemas": {"Todo": {"id": "uuid", "title": "string", "completed": "boolean"}}
  },
  "rubric": {
    "criteria": [
      {"name": "Couverture des cas d'usage", "weight": 0.4},
      {"name": "Clarté et cohérence", "weight": 0.3},
      {"name": "Respect des conventions REST", "weight": 0.3}
    ],
    "passing_threshold": 0.7
  },
  "validation": {"auto_gradable": false},
  "style_guidelines": "Utiliser des verbes HTTP idempotents quand approprié, statuts explicites."
}""",

# 13, 14, 15 sont déjà ci-dessus — on complète avec 2 supplémentaires pour atteindre 15 solides :

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_mcq",
  "subject": "Français (FLÉ)",
  "topic": "Pronoms relatifs (qui, que, dont, où)",
  "language": "fr",
  "difficulty": "moyen",
  "cefr_level": "B1",
  "tags": ["grammaire", "pronoms", "QCM"],
  "instructions": "Choisissez le pronom relatif correct.",
  "items": [
    {
      "id": "q1",
      "stem": "La ville ___ je suis né est au bord de la mer.",
      "choices": [
        {"id": "A", "text": "qui", "is_correct": false, "rationale": "'qui' serait sujet du verbe suivant, ici il faut un complément de lieu."},
        {"id": "B", "text": "où", "is_correct": true,  "rationale": "Complément de lieu: 'la ville où je suis né'."},
        {"id": "C", "text": "dont", "is_correct": false, "rationale": "S'emploie avec 'de'."},
        {"id": "D", "text": "que", "is_correct": false, "rationale": "COD, non pertinent ici."}
      ]
    },
    {
      "id": "q2",
      "stem": "C'est un sujet ___ je me passionne depuis des années.",
      "choices": [
        {"id": "A", "text": "qui", "is_correct": false, "rationale": "Sujet mal placé."},
        {"id": "B", "text": "que", "is_correct": false, "rationale": "Manque la préposition 'de'."},
        {"id": "C", "text": "dont", "is_correct": true,  "rationale": "Verbe 'se passionner de' → 'dont'."},
        {"id": "D", "text": "où", "is_correct": false, "rationale": "Pas un lieu."}
      ]
    }
  ],
  "solutions": { "short": {"q1": "B", "q2": "C"} },
  "rubric": { "criteria": [{"name": "Exactitude", "weight": 1}], "passing_threshold": 0.7 },
  "validation": { "auto_gradable": true }
}""",

r"""{
  "schema_version": "1.0",
  "example_type": "exercise_cloze",
  "subject": "Français (FLÉ)",
  "topic": "Connecteurs logiques (cause, opposition, concession)",
  "language": "fr",
  "difficulty": "moyen",
  "cefr_level": "B2",
  "tags": ["cohésion", "discours", "texte à trous"],
  "instructions": "Complétez avec: 'bien que', 'car', 'tandis que'.",
  "materials": {
    "passage": "[1] le budget soit limité, l'équipe a livré à l'heure, [2] elle avait planifié des marges, [3] d'autres projets prenaient du retard."
  },
  "blanks": [
    {"id": 1, "answer": "Bien que", "alternatives": ["bien que"], "explanation": "Concession → subjonctif."},
    {"id": 2, "answer": "car", "alternatives": ["parce que"], "explanation": "Cause."},
    {"id": 3, "answer": "tandis que", "alternatives": [], "explanation": "Opposition simultanée."}
  ],
  "solutions": { "short": {"1": "Bien que", "2": "car", "3": "tandis que"} },
  "rubric": { "criteria": [{"name": "Cohérence logique", "weight": 1}] },
  "validation": { "auto_gradable": true }
}"""
]
# -----------------------------------------------------------------


def _text_for_embedding(data: dict) -> str:
    """
    Concatène des champs pertinents pour une meilleure recherche sémantique.
    """
    parts = [
        f"Type: {data.get('example_type', '')}",
        f"Sujet: {data.get('subject', '')}",
        f"Thème: {data.get('topic', '')}",
        f"Langue: {data.get('language', '')}",
        f"Difficulty: {data.get('difficulty', '')}",
        "Tags: " + ", ".join(data.get("tags", [])),
        f"Instructions: {data.get('instructions', '')}",
    ]
    mats = data.get("materials") or {}
    for key in ("passage", "transcript", "code"):
        if key in mats and mats[key]:
            parts.append(f"{key}: {mats[key]}")
    # Ajouter solutions courtes si présentes
    sols = data.get("solutions")
    if isinstance(sols, dict) and "short" in sols and sols["short"]:
        parts.append(f"Solutions: {sols['short']}")
    return "\n".join(parts)


def seed_database():
    """
    Parser, vectoriser et insérer les exemples dans la DB.
    """
    db = SessionLocal()
    logger.info("Démarrage du peuplement de la base de données avec les exemples de qualité...")

    try:
        examples_to_add = []

        for i, json_str in enumerate(EXAMPLES_JSON_STRINGS, start=1):
            logger.info(f"Traitement de l'exemple N°{i}...")

            # 1) Parser le JSON
            try:
                data = json.loads(json_str)
            except Exception as e:
                logger.error(f"  -> JSON invalide à l'index {i}: {e}")
                continue

            # 2) Préparer le texte pour l'embedding
            text_for_embedding = _text_for_embedding(data)

            # 3) Générer l'embedding
            embedding = get_text_embedding(text_for_embedding)
            if not embedding:
                logger.warning(f"  -> Embedding vide pour l'exemple {i}, on saute.")
                continue

            # 4) Objet SQLAlchemy
            example_type = data.get('example_type', 'unknown')
            golden_example = GoldenExample(
                example_type=example_type,
                content=json_str,  # Stockage du JSON brut
                embedding=embedding
            )
            examples_to_add.append(golden_example)

        # 5) Nettoyer et insérer
        logger.info("Nettoyage des anciens exemples...")
        db.query(GoldenExample).delete(synchronize_session=False)

        logger.info(f"Insertion de {len(examples_to_add)} nouveaux exemples...")
        db.add_all(examples_to_add)
        db.commit()

        logger.info(f"✅ Succès ! {len(examples_to_add)} exemples ont été indexés dans la base de données vectorielle.")

    except Exception as e:
        logger.exception(f"❌ Une erreur est survenue : {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
