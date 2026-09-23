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

## Initialisation de la base de données (Seeding)

Pour peupler la base de données PostgreSQL avec des données de test, exécutez la commande suivante :

```bash
docker exec application-entrainement-backend-1 python seed.py
```

## Déploiement Kubernetes

```bash
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/deployment.yaml
```
