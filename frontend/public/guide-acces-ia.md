# CoachTommy — Accès IA : guide d'intégration pour agents

> **Document à ingérer par tout agent IA autorisé via la fonctionnalité « Accès IA ».** Il décrit l'API mise à votre disposition pour gérer les plans d'entraînement et les séances d'**un seul athlète** : celui qui vous a fourni sa clé d'accès. Après lecture, vous devez être capable de créer un plan, créer une séance et modifier une séance sans assistance humaine.

## 1. Votre rôle et votre périmètre

Vous êtes un agent IA externe agissant pour le compte d'un athlète. L'API vous donne un accès **en lecture, création et modification** à ses plans et séances d'entraînement.

**Vous pouvez :**
- Consulter le plan actif, l'historique des plans, leurs statistiques hebdomadaires ;
- Créer un plan d'entraînement (les séances sont alors **générées automatiquement par le serveur**) ;
- Archiver ou supprimer un plan ;
- Lister, consulter, créer et modifier des séances (y compris celles issues d'un plan).

**Vous ne pouvez pas :**
- Accéder aux données d'un autre athlète (404 sur tout identifiant hors périmètre) ;
- Valider une séance, saisir le ressenti ou les commentaires de l'athlète (champs refusés en 422) ;
- Choisir le destinataire d'une création (`athlete_id`, `plan_id` interdits dans les corps de requête) ;
- Supprimer une séance, ni accéder aux routes Strava, coachs ou communauté ;
- Gérer la clé d'accès elle-même (génération/rotation/révocation : l'athlète le fait dans l'application).

## 2. Configuration requise

| Élément | Valeur |
|---|---|
| `API_BASE_URL` | `https://coachtommyback-production.up.railway.app/api` (base des routes ; ajouter `/ai/...` sans répéter `/api`). En développement local uniquement : `http://localhost:8000/api`. |
| `AI_ACCESS_KEY` | Clé d'accès IA fournie par l'athlète, préfixe `ct_ai_`. |

Authentification : **toutes** les routes `POST/GET/PATCH/DELETE /api/ai/...` exigent l'en-tête :

```
Authorization: Bearer <AI_ACCESS_KEY>
```

La clé est **secrète et personnelle** : ne l'écrivez jamais dans un dépôt, un log, une URL ou un message visible ; ne la rediffusez pas. Une clé absente, invalide ou révoquée renvoie **401** : dans ce cas, demandez à l'athlète de régénérer sa clé dans l'application (une rotation invalide immédiatement l'ancienne clé).

## 3. Catalogue des routes

| Méthode et route | Action | Réponse |
|---|---|---|
| `GET /api/ai/plans/current` | Plan actif ou `null` | 200 |
| `GET /api/ai/plans/history` | Plans archivés, paginé, triés par date de course puis id décroissants | 200 |
| `GET /api/ai/plans/{plan_id}` | Détail d'un plan (actif ou archivé) | 200 / 404 |
| `GET /api/ai/plans/{plan_id}/weekly-stats` | Statistiques hebdomadaires des séances du plan | 200 / 404 |
| `POST /api/ai/plans` | Crée un plan **et génère ses séances** | 200 / 400 / 422 |
| `POST /api/ai/plans/{plan_id}/archive` | Archive le plan (les séances sont conservées) | 200 / 404 |
| `DELETE /api/ai/plans/{plan_id}` | Supprime **définitivement** le plan et ses séances en cascade | 204 / 404 |
| `GET /api/ai/workouts` | Liste paginée des séances | 200 |
| `GET /api/ai/workouts/{workout_id}` | Détail d'une séance | 200 / 404 |
| `POST /api/ai/workouts` | Crée une séance indépendante | 201 / 422 |
| `PATCH /api/ai/workouts/{workout_id}` | Modification partielle d'une séance | 200 / 404 / 422 |

> Les routes de plans **refusent les paramètres de requête inconnus (422)** : n'envoyez que `skip`/`limit` sur `history`, rien ailleurs. Les schémas d'OpenAPI complets sont sur `/docs` de l'instance.

## 4. Créer un plan d'entraînement

`POST /api/ai/plans` — le serveur génère l'intégralité des séances (phases, volumes, allures basées sur la VMA). Vous ne choisissez pas le contenu des séances : vous fournissez le cadre, le moteur de génération fait le reste.

**Corps de requête** (tous les champs sont obligatoires sauf `race_estimated_time`) :

```json
{
  "race_name": "Semi de Paris",
  "race_date": "2026-03-15T08:00:00",
  "race_distance": 21.1,
  "race_estimated_time": "1h45",
  "start_date": "2026-01-05T00:00:00",
  "sessions_per_week": 3,
  "goal_type": "mixte",
  "training_days": [1, 3, 5],
  "estimated_vma": 5.5
}
```

**Règles de validation (422 si violation) :**
- Toutes les dates sont des **date-heures ISO 8601** ;
- `start_date` **doit être un lundi** (ex. 2026-01-05) ;
- `race_date` doit être **postérieure** à `start_date` ;
- `race_distance` en km, strictement positive ;
- `sessions_per_week` : entier de **1 à 7** ;
- `goal_type` : `plaisir`, `maintien`, `mixte`, `intensité` ou `trail` (accents et casse tolérés) ;
- `training_days` : soit une **liste de jours** (`0`=lundi … `6`=dimanche, ex. `[1, 3, 5]`), soit un **objet jour → catégorie** (ex. `{"1": "Endurance", "5": "Sortie longue"}`). En forme liste, le serveur attribue lui-même les catégories selon l'objectif. En forme objet, les catégories usuelles sont `Libre`, `Endurance`, `Fractionné`, `Sortie longue`, `Trail` ;
- `estimated_vma` : **allure en minutes décimales par km**, strictement positive, malgré son nom. Ex. `5.5` = 5:30/km. Effet de bord : cette valeur met à jour la VMA du profil athlète en km/h (`60 / estimated_vma`).

**Réponses :**
- **200** : plan créé. La réponse contient le plan (`id`, `is_archived: false`, etc.). Les séances générées se consultent via `GET /api/ai/workouts` (elles référencent `plan_id`).
- **400** : un plan actif existe déjà pour cet athlète → archivez-le (avec l'accord de l'athlète) avant d'en créer un nouveau.
- **422** : validation en échec ; `detail` explique la règle violée.

## 5. Créer une séance indépendante

`POST /api/ai/workouts` — crée une séance **hors plan** (le serveur ne la rattache à aucun plan et `plan_id` est interdit dans le corps).

**Corps de requête** :

```json
{
  "sport": "running",
  "workout_type": "Fractionné",
  "category": "Fractionné",
  "name": "8x400m",
  "duration_minutes": 60,
  "distance_km": 9.5,
  "difficulty_level": 7,
  "description": "8x400m à allure 5 km, récup 1'30",
  "scheme": [
    { "repetitions": 1, "intervals": [ { "type": "Echauffement", "duration": 15 } ] },
    { "repetitions": 8, "intervals": [ { "type": "Vite", "distance": 400, "pace_min": "4:30", "pace_max": "4:45" } ] }
  ],
  "date": "2026-02-12T18:30:00"
}
```

**Champs obligatoires** : `workout_type` (texte libre ; valeurs usuelles : `Endurance`, `Libre`, `Fractionné`, `Sortie longue`, `Trail`, `Course`), `name`, `duration_minutes` (≥ 0), `difficulty_level` (entier **1 à 10**), `date` (ISO 8601).
**Facultatifs** : `sport` (`running` par défaut), `category`, `distance_km`, `description`, `scheme`.
**Réponse 201** : la séance créée (`id` à conserver pour les modifications ultérieures).

**Interdits dans le corps (422)** : `athlete_id`, `plan_id`, `estimated_load` (calculé serveur), `is_validated`, `perceived_difficulty`, `athlete_comment`, et tout champ inconnu.

### Le schéma d'intervals (`scheme`)

Liste de blocs de répétitions ; si `scheme` est fourni non vide, **le serveur recalcule `duration_minutes` et `distance_km`** en tenant compte des répétitions (vos valeurs saisies sont écrasées) :

- Bloc : `{ "repetitions": <entier ≥ 1, défaut 1>, "intervals": [...] }` ;
- Intervalle : `type` (étiquette libre), `duration` (**minutes**), `distance` (**mètres** !), `pace_min` / `pace_max` (**allures "min:ss" par km**, ex. `"5:30"`), `power_watt_min` / `power_watt_max` (watts) ;
- **Chaque intervalle doit avoir soit une `duration`, soit une `distance` accompagnée d'une allure** — sinon 422 ; la valeur manquante est déduite de l'allure ;
- La distance totale peut renvoyer `null` si elle est indéterminable (par ex. intervalle timed sans allure).

Gardez la cohérence des unités : `duration` en minutes à l'intérieur des intervals, `distance` en mètres dans les intervals, mais `distance_km` en kilomètres au niveau de la séance.

## 6. Modifier une séance

`PATCH /api/ai/workouts/{workout_id}` — **modification partielle** : n'envoyez que les champs à changer.

```json
{ "date": "2026-02-14T18:00:00", "difficulty_level": 6 }
```

**Règles :**
- Les champs obligatoires (`sport`, `workout_type`, `name`, `duration_minutes`, `difficulty_level`, `date`) **ne peuvent pas être mis à `null`** (422) ;
- Modifier `scheme`, `duration_minutes` ou `distance_km` redéclenche le recalcul des volumes ; modifier `scheme`, `duration_minutes`, `distance_km` ou `difficulty_level` recalcule la charge estimée ;
- L'identifiant doit appartenir à l'athlète (sinon 404) ;
- Les champs `is_validated`, `perceived_difficulty`, `athlete_comment`, `athlete_id`, `plan_id` sont **refusés** (422) : la validation est réservée à l'athlète dans l'application.

**Recette courante** (« reporte ma séance de mardi à jeudi ») :
1. `GET /api/ai/workouts?date_from=...&date_to=...` pour identifier l'id ;
2. `PATCH /api/ai/workouts/{id}` avec la nouvelle `date`.

## 7. Lister les séances

`GET /api/ai/workouts` accepte :
- `skip` (≥ 0, défaut 0) et `limit` (1 à 500, défaut 100) : **parcourez les pages jusqu'à recevoir moins de `limit` résultats** ; tri par date puis id croissants ;
- `include_archived` (défaut `true`) : avec `false`, restent visibles les séances sans plan, celles des plans actifs, et les séances passées ou validées des plans archivés ; seules les **séances futures non validées** des plans archivés sont exclues ;
- `date_from` ( inclusif) et `date_to` (exclusif), date-heures ISO 8601 ; plage inversée → 422.

`GET /api/ai/plans/history` accepte `skip`/`limit` aux mêmes règles.

## 8. Erreurs standardisées

| Code | Signification | Réaction attendue |
|---|---|---|
| 401 | Clé absente, invalide ou révoquée | Demander à l'athlète de régénérer sa clé dans l'application ; ne pas réessayer en boucle |
| 404 | Ressource inexistante **ou hors du périmètre de l'athlète** | Ne pas deviner un autre id ; re-lister si besoin |
| 400 | Un plan actif existe déjà | Proposer l'archivage explicite avant nouvelle création |
| 405 | Méthode non disponible sur cette route | Corriger l'appel |
| 422 | Entrée invalide (champ inconnu, règle de validation violée, paramètre de requête inconnu) | Lire `detail`, corriger le corps et renvoyer |

## 9. Bonnes pratiques pour l'agent

1. **Avant toute création de plan**, appelez `GET /api/ai/plans/current` : s'il existe déjà un plan actif, proposez à l'athlète de l'archiver (`POST .../archive`, corps `{}`, commentaire facultatif via `cancellation_comment`) plutôt que de subir un 400.
2. **Destruction irréversible** : `DELETE /api/ai/plans/{id}` supprime le plan et toutes ses séances, même validées. Demandez toujours une confirmation explicite de l'athlète. L'archivage est l'alternative non destructive privilégiée.
3. **N'inventez pas de routes** : le périmètre est strictement celui du tableau de la section 3. En cas de doute sur un schéma, consultez `/docs` de l'instance.
4. **Renseignez l'athlète** : après création de plan, présentez un résumé (objectif, nombre de semaines, séances/semaine) et proposez `GET /api/ai/plans/{id}/weekly-stats` pour visualiser la répartition.
5. Ne transmettez à aucun tiers les données lues via cette API ; l'accès est limité aux plans et séances de l'athlète concerné.
6. Les dates et heures sont toujours ISO 8601 ; explicitez le fuseau avec l'athlète avant d'écrire une heure de séance.