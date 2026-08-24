# BRIEF — session terminal : backtest réel de la stratégie HV-rank

*À coller dans une session terminal lancée depuis `~/Desktop/CERVEAU/hindsight-alpha/`. Fait suite à `BRIEF_PUSH_GITHUB_PAGES.md` (dépôt public poussé, dashboard vérifié, `.git/index.lock` réglé) — le pipeline live tourne, mais personne n'a encore vérifié si la thèse elle-même (acheter de l'optionalité quand la volatilité réalisée est bon marché) a un edge historique. Ce brief répond exactement à cette question.*

---

## Contexte, honnêtement

Spap a posé la question directe : est-ce que le but est juste de construire un agent, ou est-ce qu'il doit être rentable, et de combien ? Réponse cherchée dans les pages publiques du hackathon : aucun seuil de rentabilité minimum publié nulle part, "P&L Performance" est un des 5 critères nommés sans poids ni plancher trouvé — probablement jugé en relatif (comme les autres équipes), pas en pass/fail, mais ce n'est pas une certitude à 100%. Dans tous les cas, la question "est-ce que cette stratégie a un edge historique" mérite une vraie réponse indépendamment du hackathon — c'est un vrai backtest, pas une supposition.

`backtest.py` a été écrit pour ça : il rejoue la stratégie du projet (`vol_strategy._vol_strategy_returns`, `hindsight_guard.check_selection_leakage`) contre l'historique réel de prix, sans réimplémenter la logique séparément — donc le résultat du backtest correspond exactement à ce que l'agent live ferait, pas à une variante optimiste. Vérifié mécaniquement depuis Cowork avec des données synthétiques (aucune erreur, pas de NaN, pipeline complet fonctionne) — **jamais lancé contre les vraies données**. Trois tentatives depuis Cowork pour récupérer de l'historique de prix réel ont toutes échoué : Alpaca directement (bloqué, déjà connu), stooq.com (bloqué), Yahoo Finance (bloqué) — le bac à sable Cowork bloque l'accès réseau à tous les fournisseurs de données financières, pas seulement Alpaca.

**Important à lire avant de croire ou de citer un chiffre de ce backtest** : le payoff calculé est un **proxy**, pas une vraie simulation de prime d'option. C'est la valeur absolue du rendement du lendemain moins un coût lié au niveau de volatilité — documenté explicitement dans `vol_strategy.py` et rappelé dans `backtest.py`. Ça répond à "est-ce que le timing du régime de volatilité a un edge", pas à "combien de dollars réels ça aurait rapporté avec une vraie prime, un vrai spread, une vraie décote temporelle". Les deux nombres (positif ou négatif) sont informatifs, mais ne jamais les présenter comme un vrai P&L sans cette nuance — dans le write-up comme à l'oral.

## Ce qu'on te demande

1. `python backtest.py` (compte de dev, `.env` — aucune écriture, aucun ordre, lecture seule de l'historique de prix). Ça va chercher ~600+ jours de bourse pour SPY, QQQ, IWM et écrire `BACKTEST_RESULTS.md`.
2. Lis le résultat honnêtement : pour chaque symbole, regarde si le payoff cumulé est positif ou négatif sur les 5 fenêtres candidates, le taux de succès sur les jours réellement tradés, le max drawdown, et si `hindsight_guard` dit "agrees" ou "LEAK DETECTED" pour ce symbole sur l'historique complet.
3. Si le résultat est mitigé ou négatif sur certaines fenêtres/symboles, **ne pas chercher à l'améliorer en changeant les seuils** (`CHEAP_VOL_PERCENTILE`, `RANK_LOOKBACK_DAYS`, etc. dans `vol_strategy.py`) après coup pour "faire mieux" — ce serait exactement le biais de sélection après-coup que `hindsight_guard` existe pour attraper. Rapporte le résultat tel quel, même s'il n'est pas flatteur.
4. Commit `BACKTEST_RESULTS.md` (`git add BACKTEST_RESULTS.md && git commit -m "backtest: real historical results" && git push`) — ce fichier doit être public, c'est une preuve d'honnêteté utile pour le write-up, pas quelque chose à cacher si le résultat est mauvais.
5. Résume en une phrase par symbole ce que ça dit pour le narratif du write-up : "l'edge de timing de volatilité existe/n'existe pas historiquement sur ce symbole, avec telle réserve sur le proxy".

## Hors périmètre

- Ne modifie aucun seuil de `vol_strategy.py` ou `risk_gates.py` pour améliorer le résultat du backtest après l'avoir vu.
- Aucun ordre réel, aucun `--live`, ne touche pas à `.env.hackathon`.
- Ne touche à aucun autre dossier de CERVEAU pendant cette session.
- Pas de `git push --force`.

## Bonus si tu as 2 minutes, pas bloquant

`publish_dashboard.py` capture maintenant `account.get("account_number")` en plus de `id` (deux identifiants différents chez Alpaca — voir `PLAN_SPRINT.md`, passe du 24/08). Jamais vérifié contre le vrai CLI : lance `alpaca account get --quiet` et confirme que le JSON contient bien une clé `account_number` au format `PA...`. Si le champ s'appelle autrement dans la vraie sortie, corrige le nom dans `publish_dashboard.py` (une ligne) et republie le dashboard.

## En fin de séance

Verdict net : le backtest a tourné (oui/non, erreur exacte sinon), le résumé honnête par symbole (edge présent ou pas, sur quelles fenêtres), `BACKTEST_RESULTS.md` poussé sur le dépôt public. Mets à jour `PLAN_SPRINT.md` avec le résultat réel avant de terminer — ce chiffre sert directement le write-up d'une page à venir.

---

**Compte paper trading uniquement — zéro fonds réel engagé.**
