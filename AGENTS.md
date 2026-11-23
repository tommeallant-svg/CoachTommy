# Recommandations de développement pour les agents

Pour chaque nouveau développement, effectuer les opérations suivantes dans l'ordre :

1. Créer une branche Git dédiée à la fonctionnalité avant de commencer les modifications.
2. Construire les images Docker du projet avec `docker compose build` et vérifier que la construction réussit.
3. Si la base de données a été modifiée, adapter `backend/seed.py` pour permettre sa reconstruction et fournir le code mis à jour dans le compte rendu. Ne pas supprimer de volume ou de données existantes sans autorisation explicite.
4. Tester les fonctionnalités développées au moyen d'appels API, en vérifiant les réponses et les cas d'erreur pertinents. L'API est accessible sur `http://localhost:8000` et sa documentation sur `http://localhost:8000/docs` lorsque les services sont démarrés.
5. Toujours effectuer un commit des modifications sur la branche créée, sauf si les tests API échouent. Si la construction ou une vérification est impossible, le signaler dans le compte rendu sans empêcher le commit.

Pour chaque développement, consigner dans le compte rendu les erreurs rencontrées, leur contexte et leur résolution ou leur état si elles ne sont pas résolues. Si des informations utiles pour faciliter les futurs déploiements ont été apprises, les ajouter à ce fichier avant le commit, sans y inscrire de secrets.