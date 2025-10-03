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

## Déploiement sur Fly.io

Cette application FastAPI peut maintenant être déployée sur [Fly.io](https://fly.io/) grâce au `Dockerfile` et au `fly.toml` fournis.

1. **Installer la CLI Fly** et se connecter :
   ```bash
   curl -L https://fly.io/install.sh | sh
   fly auth login
   ```
2. **Configurer l'application** : mettez à jour la valeur `app` dans `fly.toml` avec le nom de votre application Fly, puis initialisez le projet (sans déploiement automatique) :
   ```bash
   fly launch --no-deploy
   ```
3. **Créer et attacher une base PostgreSQL** (requis en production) :
   ```bash
   fly postgres create --name <nom-bdd> --region cdg
   fly postgres attach --app <nom-app> <nom-bdd>
   ```
   L'attachement configure automatiquement le secret `DATABASE_URL`.
4. **Définir les secrets obligatoires** :
   ```bash
   fly secrets set \
  SECRET_KEY="<secret JWT>" \
  RESEND_API_KEY="<token Resend>" \
  FRONTEND_BASE_URL="https://<votre-front>" \
  BACKEND_BASE_URL="https://<votre-domaine>" \
  EMAIL_FROM="support@<votredomaine>"
   ```
   Ajoutez également les clés facultatives nécessaires (`OPENAI_API_KEY`, `SUPABASE_URL`, etc.).
5. **Déployer** :
   ```bash
   fly deploy
   ```
6. **Suivre les logs et l'état** :
   ```bash
   fly status
   fly logs
   ```

Le service écoute sur le port `8080` (configuré dans `fly.toml`) et expose la racine `/` pour les vérifications de santé.
