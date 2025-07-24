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

### Courses (`/api/v2/courses`)

| Méthode | Route                       | Description                               | Données en entrée (Body)         | Réponse en cas de succès (2xx)   |
| :------ | :-------------------------- | :---------------------------------------- | :------------------------------- | :------------------------------- |
| `POST`  | `/`                         | Crée un nouveau cours (plan généré par IA). | `course_schema.CourseCreate`     | `course_schema.Course`           |
| `GET`   | `/`                         | Récupère la liste de tous les cours.      | _Aucune_                         | `List[course_schema.Course]`     |
| `GET`   | `/{course_id}`              | Récupère les détails d'un cours spécifique. | _Aucune_                         | `course_schema.Course`           |