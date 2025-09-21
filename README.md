# Documentation de l'API Nanshe V2

Voici la liste des endpoints actuellement disponibles.

---

### Users (`/api/v2/users`)

| Méthode | Route                       | Description                               | Données en entrée (Body)         | Réponse en cas de succès (2xx)   |
| :------ | :-------------------------- | :---------------------------------------- | :------------------------------- | :------------------------------- |
| `POST`  | `/`                         | Crée un nouvel utilisateur.               | `user_schema.UserCreate`         | `user_schema.User`               |
| `POST`  | `/login`                    | Connecte un utilisateur et retourne un JWT. | `OAuth2PasswordRequestForm`      | `token_schema.Token`             |
| `GET`   | `/me`                       | Récupère les infos de l'utilisateur connecté. | _Aucune_ (Token dans l'en-tête)  | `user_schema.User`               |

---

### Capsules (`/api/v2/capsules`)

| Méthode | Route                                                | Description                                                         | Données en entrée (Body)                     | Réponse en cas de succès (2xx)   |
| :------ | :--------------------------------------------------- | :------------------------------------------------------------------ | :------------------------------------------- | :------------------------------- |
| `GET`   | `/me`                                                | Liste les capsules auxquelles l'utilisateur est inscrit.            | _Aucune_                                     | `List[capsule_schema.CapsuleRead]` |
| `GET`   | `/public`                                            | Liste les capsules publiques disponibles à l'inscription.           | _Aucune_                                     | `List[capsule_schema.CapsuleRead]` |
| `GET`   | `/{domain}/{area}/{capsule_id}`                      | Récupère les détails complets d'une capsule.                        | _Aucune_                                     | `capsule_schema.CapsuleRead`     |
| `POST`  | `/`                                                  | Génère une capsule à partir d'une classification.                   | `capsule_schema.CapsuleCreateRequest`        | `capsule_schema.CapsuleRead`     |
| `POST`  | `/{capsule_id}/granule/{granule_order}/molecule/{molecule_order}` | Génère/récupère le contenu d'une leçon (molécule).                   | _Aucune_                                     | `List[capsule_schema.AtomRead]`   |

---

## Espace d'administration

Une interface graphique est disponible sur `http://localhost:8000/admin` (base URL configurable). Elle repose sur **SQLAdmin** et offre un CRUD complet sur les principales tables :

- **Utilisateurs & Paiements** : utilisateurs (statut d'abonnement, vérification e‑mail, client Stripe), inscriptions, progression, notifications, jetons d'e-mail.
- **Contenus** : capsules, granules, molécules et atomes, avec aperçus JSON formatés pour les contenus générés.
- **Apprentissage** : feedbacks, réponses et journaux d'activité.
- **Gamification & Tech** : badges, attribution de badges, logs d'utilisation de l'IA.

### Connexion

1. Créez (ou mettez à jour) un utilisateur avec `is_superuser = true` et un mot de passe connu.
2. Authentifiez-vous depuis le formulaire `/admin/login` avec `username` + `password` de ce super-utilisateur.

> Les sessions sont gérées par cookie sécurisé via `SessionMiddleware`. En cas de perte d'accès, videz la session ou reconnectez-vous.
