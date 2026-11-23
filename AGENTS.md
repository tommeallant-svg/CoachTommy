# Recommandations de développement pour les agents

Pour chaque nouveau développement, effectuer les opérations suivantes dans l'ordre :

1. Créer une branche Git dédiée à la fonctionnalité avant de commencer les modifications.
2. Construire les images Docker du projet avec `docker compose build` et vérifier que la construction réussit.
3. Si la base de données a été modifiée, adapter `backend/seed.py` pour permettre sa reconstruction et fournir le code mis à jour dans le compte rendu. Ne pas supprimer de volume ou de données existantes sans autorisation explicite.
4. Tester les fonctionnalités développées au moyen d'appels API, en vérifiant les réponses et les cas d'erreur pertinents. L'API est accessible sur `http://localhost:8000` et sa documentation sur `http://localhost:8000/docs` lorsque les services sont démarrés.
5. Toujours effectuer un commit des modifications sur la branche créée, sauf si les tests API échouent. Si la construction ou une vérification est impossible, le signaler dans le compte rendu sans empêcher le commit.

Pour chaque développement, consigner dans le compte rendu les erreurs rencontrées, leur contexte et leur résolution ou leur état si elles ne sont pas résolues. Si des informations utiles pour faciliter les futurs déploiements ont été apprises, les ajouter à ce fichier avant le commit, sans y inscrire de secrets.

## Apprentissages : plans et séances des athlètes

- Un coach doit sélectionner explicitement le destinataire d'un plan ; la VMA du plan doit modifier celle de cet athlète, pas celle du coach. Tester aussi le refus d'une création sans destinataire.
- Pour une séance issue du catalogue, utiliser la VMA ou la FTP du destinataire sélectionné et actualiser ces statistiques en cas de changement d'athlète. Une VMA s'exprime en km/h, et non en min/km ; ne pas convertir une séance si la statistique nécessaire est indisponible.
- Pour recalculer la durée et la distance d'une séance structurée, tenir compte des répétitions et des unités des intervalles ; distinguer les distances en mètres des distances totales en kilomètres.
- Les tests API isolés ne remplacent pas la vérification du parcours authentifié dans l'interface : préciser explicitement lorsqu'il n'a pas été testé. Des conteneurs de test séparés peuvent utiliser d'autres ports ; vérifier leur rôle avant de les arrêter.
- Après modification du backend ou du frontend, reconstruire et redémarrer les services concernés pour que les changements soient effectivement servis. `docker compose up -d` conserve les volumes existants ; vérifier l'état de PostgreSQL, les journaux et les réponses HTTP sans supprimer de données.
- Si les dépendances Python locales sont absentes, privilégier les tests dans un environnement adapté, notamment l'image Docker, et signaler toute vérification impossible. La disponibilité de `/docs` et du frontend ne prouve pas le bon fonctionnement d'un parcours authentifié.
- Au démarrage, PostgreSQL peut signaler que la colonne `garmin_workout_id` existe déjà lors d'une tentative d'ajout ; vérifier les journaux du backend et les réponses HTTP pour distinguer cette erreur d'un échec de démarrage.
- Configurer `JWT_SECRET_KEY` avec une clé aléatoire conservée hors dépôt avant de redémarrer le backend ; sa rotation invalide les sessions et exige une reconnexion, sans supprimer les comptes. Ne jamais réutiliser l'ancienne clé JWT publique.