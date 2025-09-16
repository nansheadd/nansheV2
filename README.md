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
