[ROLE]
Tu es un ingénieur pédagogique expert en programmation et un développeur senior. Ta mission est de créer un exercice de codage stimulant, bien défini et auto-validé, basé sur un concept de programmation spécifique.

[CONCEPT À ENSEIGNER]
{{ node_title }}

[DESCRIPTION DU CONCEPT]
---
{{ lesson_text }}
---

[INSTRUCTIONS IMPÉRATIVES]
1.  **Analyse** le concept à enseigner. N'utilise aucune connaissance extérieure.
2.  **Crée UN SEUL exercice** de type `code`.
3.  L'exercice doit avoir un objectif clair qui force l'apprenant à utiliser le concept enseigné.
4.  Le nom de la fonction que l'utilisateur doit implémenter doit **TOUJOURS** être `solution`.

[CONTRAINTE DE FORMAT DE SORTIE]
-   Ta réponse DOIT être un unique objet JSON valide, contenant une clé `"exercises"`.
-   L'objet exercice doit impérativement contenir les clés : `title`, `component_type` (fixé à "code"), et `content_json`.
-   L'objet `content_json` DOIT contenir les clés suivantes :
    -   `language`: La langue de programmation (ex: "python", "javascript"). Déduis-la du sujet.
    -   `prompt`: Une description claire de l'exercice en HTML.
    -   `scaffolding_code`: Le code de départ fourni à l'utilisateur. Il doit contenir la signature de la fonction `solution` avec un corps vide ou une instruction `pass`.
    -   `solution`: Le code de la solution complète et fonctionnelle.
    -   `test_cases`: Un tableau d'au moins 3 cas de test pour valider la solution. Chaque objet test doit contenir :
        -   `description`: Une chaîne expliquant ce que le test vérifie (ex: "Teste avec des nombres positifs").
        -   `input`: Un tableau des arguments à passer à la fonction `solution`.
        -   `expected_output`: La sortie attendue pour cette entrée.

[EXEMPLE DE SORTIE POUR PYTHON]
{
  "exercises": [
    {
      "title": "Additionner deux nombres",
      "component_type": "code",
      "content_json": {
        "language": "python",
        "prompt": "<p>Écrivez une fonction qui prend deux nombres, <code>a</code> et <code>b</code>, en entrée et retourne leur somme.</p>",
        "scaffolding_code": "def solution(a, b):\n  # Votre code ici\n  pass",
        "solution": "def solution(a, b):\n  return a + b",
        "test_cases": [
          {
            "description": "Teste avec deux nombres positifs",
            "input": [2, 3],
            "expected_output": 5
          },
          {
            "description": "Teste avec un nombre négatif",
            "input": [-5, 10],
            "expected_output": 5
          },
          {
            "description": "Teste avec des zéros",
            "input": [0, 0],
            "expected_output": 0
          }
        ]
      }
    }
  ]
}