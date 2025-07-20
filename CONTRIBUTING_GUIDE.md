# Guide de Style et de Nomenclature - Nanshe Backend V2

Ce document est la charte de développement pour le backend du projet Nanshe. Son respect par tous les contributeurs garantit un code lisible, cohérent et maintenable sur le long terme.

---

## 1. Structure des Dossiers

Le projet suit une structure logique pour séparer les différentes couches de l'application :

/app
├── api/          # Endpoints et logique API
│   └── v2/
├── core/         # Configuration, sécurité
├── crud/         # Fonctions d'interaction avec la BDD (Create, Read, Update, Delete)
├── db/           # Configuration de la BDD, session, Base model
├── models/       # Définitions des tables de la BDD (SQLAlchemy)
└── schemas/      # Validation des données API (Pydantic)


---

## 2. Nomenclature des Fichiers

La nomenclature suit la convention `snake_case` de Python (PEP 8) avec un suffixe descriptif.

* **Modèles de Données (SQLAlchemy)**: `[nom_entité]_model.py`
* **Schémas de Validation (Pydantic)**: `[nom_entité]_schema.py`
* **Logique Métier (CRUD)**: `[nom_entité]_crud.py`
* **Endpoints / Routeurs API (FastAPI)**: `[nom_entité]_router.py`

---

## 3. Conventions de Code (Python)

* **Style de Code :** Suivre la **PEP 8**. L'utilisation d'un formateur comme **Black** est recommandée.
* **Syntaxe SQLAlchemy :** Utiliser la syntaxe moderne de **SQLAlchemy 2.0** (`Mapped`, `mapped_column`).
* **Typage :** Tout le code doit être **typé**.
* **Documentation :** Chaque fonction et classe doit avoir une **docstring**.

---

## 4. Conventions API

* **Principes RESTful :** L'API doit être conçue en suivant les principes REST.
* **Versionnement :** Tous les endpoints seront préfixés par `/api/v2/`.
* **Nommage des Ressources :** Les noms des ressources dans les URLs doivent être au **pluriel**.
* **Méthodes HTTP :** Utilisation sémantique des verbes HTTP (`GET`, `POST`, `PUT`, `DELETE`).

---

## 5. Messages de Commit (Git)

Les messages de commit doivent suivre la convention **Conventional Commits**.

* **Format :** `<type>(<scope>): <description>`
* **Types principaux :** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.