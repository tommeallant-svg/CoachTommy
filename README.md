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

## Déploiement Kubernetes

```bash
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/deployment.yaml
```
