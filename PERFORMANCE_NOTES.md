# Nanshe V2 — Baseline de performances

Ce document sert de mémo rapide pour mesurer l'état actuel de l'app et suivre les optimisations à venir.

## 1. Points de mesure disponibles
- **Logs SQL lents**: `SQLALCHEMY_SLOW_QUERY_THRESHOLD_MS` (env) déclenche un warning dès qu'une requête dépasse ce délai. Valeur par défaut: `300` ms.
- **Logs HTTP lents**: `REQUEST_SLOW_THRESHOLD_MS` (env) génère un warning quand une requête FastAPI est plus longue que ce délai. Valeur par défaut: `400` ms.
- **Profil ponctuel**: lancer `uvicorn app.main:app --reload --log-level debug` puis observer les warnings de lenteur (les deux hooks sont actifs même en dev).

## 2. Checklist de baseline
1. Démarrer l'API localement (`uvicorn app.main:app --reload`).
2. Définir temporairement `SQLALCHEMY_SLOW_QUERY_THRESHOLD_MS=50` et `REQUEST_SLOW_THRESHOLD_MS=100` pour forcer la journalisation.
3. Ouvrir les écrans critiques (dashboard, capsules, coach) et noter:
   - Latence backend visible dans les logs (méthode + path + durée).
   - Requêtes SQL mises en avant (SQL, durée, paramètres).
4. Remettre les seuils par défaut une fois la session terminée.

## 3. Pistes d'optimisation (backlog)
- [ ] Tracer les appels externes (LLM, Supabase) et mesurer leur latence moyenne.
- [ ] Ajouter des compteurs Prometheus/OTEL si l'infra le permet (requests/s, erreurs, histogrammes de latence).
- [ ] Mettre en cache les classifications NLP sur Vercel (Redis, Supabase, etc.).
- [ ] Vérifier les index manquants signalés par les requêtes lentes (ex: colonnes filtres/sorts).
- [ ] Tester les endpoints critiques sous charge (Locust/k6) pour définir une latence p95 cible.

## 4. Bonnes pratiques de suivi
- Maintenir les seuils suffisamment bas pour détecter les régressions, mais assez hauts pour éviter le bruit.
- Inclure un extrait de log de référence dans les revues de perf (avant/après modification) pour documenter les gains.
- Lors d'une optimisation, noter les commandes/params exacts utilisés pour les mesures afin de les rejouer plus tard.
