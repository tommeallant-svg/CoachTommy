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

```bash
docker-compose up --build
```

L'application sera accessible sur :
- Frontend : http://localhost:3000
- Backend API : http://localhost:8000
- Documentation API : http://localhost:8000/docs

## Mise à jour et Initialisation

Si vous avez mis à jour l'application et que de nouveaux champs ont été ajoutés à la base de données, vous devrez peut-être réinitialiser le volume de la base de données :

```bash
docker-compose down -v
docker-compose up --build
```

Pour peupler la base de données avec les nouvelles séances de vélo et données de test, exécutez :

```bash
docker-compose exec backend python seed.py
```

Vous pouvez aussi lancer le backend avec la variable d'environnement `SEED_DB=true` pour automatiser cette étape.

## Déploiement Kubernetes

```bash
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/deployment.yaml
```
