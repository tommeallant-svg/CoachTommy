# Application Entrainement

Ce projet est une application web moderne composée d'un backend FastAPI et d'un frontend Next.js.

## Structure du projet

- `backend/` : API Python avec FastAPI, SQLAlchemy et PostgreSQL.
- `frontend/` : Interface utilisateur avec Next.js (React), TypeScript et Tailwind CSS.
- `k8s/` : Manifestes Kubernetes pour le déploiement.
- `docker-compose.yml` : Configuration pour le développement local.

## Prérequis

- Docker et Docker Compose
- (Optionnel) Kubernetes (minikube, kind, etc.)

## Lancement en local

Avant le démarrage, configurez `JWT_SECRET_KEY` hors du dépôt avec une clé aléatoire d'au moins 32 caractères (par exemple `openssl rand -hex 32`). Conservez-la dans un gestionnaire de secrets et utilisez la même clé pour toutes les instances ; le backend refuse de démarrer sans cette configuration. Ne réutilisez pas l'ancienne clé publique. Le changement de clé invalide toutes les sessions existantes : les utilisateurs doivent se reconnecter, mais leurs comptes et connexions Strava restent inchangés. Toute rotation ultérieure invalide également les sessions.

```bash
docker-compose up --build
```

L'application sera accessible sur :
- Frontend : http://localhost:3000
- Backend API : http://localhost:8000
- Documentation API : http://localhost:8000/docs

## Mise à jour et Initialisation

Les tables Strava sont créées au démarrage sans supprimer les données existantes. Ne supprimez pas le volume pour appliquer cette migration.

Pour peupler la base de données avec les nouvelles séances de vélo et données de test, exécutez :

```bash
docker-compose exec backend python seed.py
```

Vous pouvez aussi lancer le backend avec la variable d'environnement `SEED_DB=true` pour automatiser cette étape.
Le seed ignore une base contenant déjà des données et ne les efface pas.

## Connexion Strava (étape 1)

Configurer hors du dépôt `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REDIRECT_URI` (URL HTTPS publique terminant par `/api/auth/strava/callback`) et `STRAVA_ENCRYPTION_KEY` (clé Fernet générée et stockée dans un gestionnaire de secrets). Conserver la clé : sa perte rend les jetons illisibles. Configurer le domaine OAuth correspondant dans l'application Strava. Les routes authentifiées sont `POST /api/auth/strava/authorize`, `GET /api/auth/strava/status` et `POST /api/auth/strava/disconnect`. Ouvrir l'URL retournée par authorize ; le callback consomme son état une seule fois. La déconnexion demande aussi la révocation auprès de Strava et peut échouer si le service est indisponible.

L'import, les webhooks et l'interface ne sont pas encore implémentés. Avant activation réelle, vérifier l'autorisation de l'application et les conditions Strava ; ne pas partager ses données avec les coachs. Éviter la journalisation des paramètres de requête du callback OAuth dans les serveurs et proxies.

Le serveur fourni désactive ses journaux d'accès, mais les proxies doivent également masquer les paramètres OAuth. Dans Kubernetes, créez préalablement le secret `application-entrainement-secrets` avec la clé `jwt-secret-key`, sans la stocker dans les manifestes.

## API pour une intégration IA

Cette API permet à un client externe d'accéder aux plans et séances d'un seul athlète ; elle ne fournit pas elle-même un assistant IA. Les routes et schémas complets sont disponibles dans `/docs` sur l'instance déployée. Le client doit rendre l'URL de base configurable et utiliser une URL HTTPS publique en production (terminaison TLS et certificat valide à configurer sur le déploiement). `http://localhost:8000` est réservé au développement local.

### Clé d'accès

Un athlète authentifié avec son JWT habituel peut appeler `GET /api/ai-access` pour obtenir `{"active": true}` ou `false`, `POST /api/ai-access` pour générer ou renouveler sa clé, et `DELETE /api/ai-access` pour la révoquer (204). Ces routes refusent les coachs (403). La clé `ct_ai_...` n'est retournée en clair qu'à la génération ; seul son hash est conservé. Une rotation invalide immédiatement l'ancienne clé. Stockez la nouvelle dans un gestionnaire de secrets, ne la mettez ni dans le dépôt, ni dans les journaux, ni dans une URL ; révoquez-la si elle est compromise.

Les routes `/api/ai/...` utilisent `Authorization: Bearer <clé IA>`, et non le JWT de connexion. Une clé absente, invalide ou révoquée renvoie 401. Exemple générique, après avoir configuré les variables localement sans enregistrer la clé dans un script :

```bash
curl --fail-with-body "$API_BASE_URL/api/ai/workouts?skip=0&limit=100" \
  -H "Authorization: Bearer $AI_ACCESS_KEY"
```

Ici `API_BASE_URL` désigne l'origine HTTPS de l'instance, sans `/api`, et `AI_ACCESS_KEY` la clé obtenue par l'athlète. Ne transmettez cette clé qu'à un client de confiance : elle autorise aussi des modifications et la suppression de plans.

### Routes et contrats

| Méthode et route | Résultat ou action |
| --- | --- |
| `GET /api/ai/plans/current` | Plan actif ou `null`. |
| `GET /api/ai/plans/history` | Liste paginée des plans archivés, par date de course puis identifiant décroissants. |
| `GET /api/ai/plans/{plan_id}` | Plan, actif ou archivé. |
| `GET /api/ai/plans/{plan_id}/weekly-stats` | Statistiques hebdomadaires des séances liées. |
| `POST /api/ai/plans` | Crée un plan et génère ses séances ; réponse 200. |
| `POST /api/ai/plans/{plan_id}/archive` | Archive le plan ; corps JSON avec `cancellation_comment` facultatif, par exemple `{}`. |
| `DELETE /api/ai/plans/{plan_id}` | Supprime définitivement le plan et toutes ses séances liées en cascade, même validées ; réponse 204. L'archivage, lui, conserve les séances. |
| `GET /api/ai/workouts` | Liste paginée des séances de l'athlète. |
| `GET /api/ai/workouts/{workout_id}` | Détail d'une séance. |
| `POST /api/ai/workouts` | Crée une séance indépendante ; réponse 201. |
| `PATCH /api/ai/workouts/{workout_id}` | Modifie partiellement une séance. |

La création d'un plan attend `race_name`, `race_date`, `race_distance` (km), `start_date`, `sessions_per_week`, `goal_type`, `training_days` et `estimated_vma` ; `race_estimated_time` est facultatif. Les dates sont des date-heures ISO 8601, le début doit être un lundi et la course ultérieure ; la distance et `estimated_vma` doivent être positives, et le nombre de séances compris entre 1 et 7. `estimated_vma` est une allure en minutes décimales par kilomètre : sa création met à jour la VMA du profil en km/h (`60 / estimated_vma`). `training_days` est une liste de jours (0 lundi à 6 dimanche) ou un objet associant jours et catégories ; les objectifs acceptés sont `plaisir`, `maintien`, `mixte`, `intensité` et `trail`. Un plan actif existant entraîne une erreur 400.

Pour une séance, `workout_type`, `name`, `duration_minutes`, `difficulty_level` (1 à 10) et `date` sont obligatoires à la création ; `sport` vaut `running` par défaut. `category`, `distance_km`, `description` et `scheme` sont facultatifs. Le schéma est une liste de blocs `repetitions` (entier au moins égal à 1, défaut 1) et `intervals` ; chaque intervalle accepte `type`, `duration` en minutes, `distance` en mètres, `pace_min`, `pace_max` en min/km et `power_watt_min`/`power_watt_max`. Chaque intervalle doit avoir une durée ou une distance avec allure. Un schéma non vide recalcule durée et distance en tenant compte des répétitions ; la distance totale peut être `null` si elle est indéterminable. La charge estimée est calculée par le serveur.

Les corps IA refusent les champs supplémentaires, notamment `athlete_id`, `plan_id`, les champs de validation et commentaires athlète ; ils ne permettent ni de choisir un autre destinataire, ni de valider ou supprimer directement une séance. Les identifiants hors du périmètre de l'athlète renvoient 404. Les entrées invalides renvoient 422 ; les méthodes non disponibles peuvent renvoyer 405. Les routes de plans refusent également les paramètres de requête inconnus.

### Pagination et confidentialité

Les listes `history` et `workouts` prennent `skip` (défaut 0, minimum 0) et `limit` (défaut 100, de 1 à 500). Parcourez les pages jusqu'à obtenir moins de `limit` résultats. Les séances sont triées par date puis identifiant croissants ; `date_from` est inclusif et `date_to` exclusif. Une plage inversée renvoie 422. Par défaut, `include_archived=true` inclut les séances des plans archivés. Avec `include_archived=false`, les séances sans plan et celles des plans actifs restent visibles, ainsi que les séances validées ou passées des plans archivés ; seules leurs séances futures non validées sont exclues.

L'accès IA est limité aux plans et séances de l'athlète associé à la clé, pas aux autres athlètes ni aux routes Strava. Ne transmettez pas de données Strava à un service IA ou à un coach sans vérifier les autorisations et conditions applicables. L'intégration externe doit être développée et vérifiée pour le client choisi : aucune compatibilité universelle, configuration automatique ou intégration native à un assistant particulier n'est garantie ; le frontend actuel ne fournit pas de gestion de clé IA.

## Notifications web-push

Les utilisateurs activent les notifications et enregistrent chaque appareil depuis Profil. Les rappels des séances non validées sont prévus à 8 h et 21 h en heure de Paris ; le coach associé est averti lorsqu'un athlète valide sa séance. L'autorisation du navigateur et une connexion HTTPS sont nécessaires (localhost est généralement accepté pour le développement). Sur iPhone, ajouter l'application à l'écran d'accueil et l'ouvrir depuis celui-ci avant de demander l'autorisation. Le navigateur et le système peuvent retarder ou bloquer la livraison.

Générer une paire VAPID P-256 dédiée et conserver la clé privée hors du dépôt. Configurer `VAPID_PRIVATE_KEY` avec les 32 octets de la clé privée encodés en base64url sans remplissage et `VAPID_SUBJECT` avec une adresse de contact `mailto:...` ou une URL HTTPS. Configurer `NEXT_PUBLIC_VAPID_PUBLIC_KEY` avec la clé publique non compressée de 65 octets encodée en base64url sans remplissage ; elle est publique et intégrée lors de la construction du frontend. Une rotation de la paire peut nécessiter la réinscription des appareils.

Docker Compose lance `notification-worker` séparément, avec la même base que l'API. Sur Railway ou Kubernetes, créer un service de travail distinct à partir de l'image backend, exécutant `python -m app.notification_worker`, avec `DATABASE_URL`, `JWT_SECRET_KEY`, `VAPID_PRIVATE_KEY` et `VAPID_SUBJECT` configurés dans le gestionnaire de secrets ; reconstruire le frontend avec la clé publique. Les tables sont ajoutées sans supprimer les données. Protéger la base et ses sauvegardes : les endpoints et clés d'abonnement y sont conservés.

Les livraisons échouées sont réessayées et les abonnements expirés retirés. Après une panne, un fournisseur ayant accepté un message avant l'enregistrement du résultat peut recevoir un doublon. Les données de notification sont limitées au type et à l'identifiant de séance ; aucune donnée Strava n'est envoyée. L'activation et la livraison réelles dépendent du fournisseur push, du navigateur et de la configuration de déploiement.

## Déploiement Kubernetes

```bash
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/deployment.yaml
```
