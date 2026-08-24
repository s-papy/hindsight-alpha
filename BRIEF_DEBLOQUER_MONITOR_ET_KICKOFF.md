# BRIEF — session terminal : débloquer `monitor_exits`, puis préparer le kickoff du 28/08

*À coller dans une session terminal lancée depuis `~/Desktop/CERVEAU/hindsight-alpha`. Fait suite à `BRIEF_VERIFICATION_FINALE_ET_COMMIT.md` et aux passes « cherche encore » qui ont suivi — leur verdict : le pipeline tourne de bout en bout contre l'API réelle, mais **la surveillance des sorties ne tourne pas**, et c'est le seul vrai trou avant le hackathon.*

---

## Contexte, honnêtement

**Ce qui marche, vérifié contre l'API réelle le 24/08** (pas en mocks) : pipeline complet, ordre paper `2e7ba582-3784-4c80-8abb-d1e4eb0a79eb` (2 puts `SPY260831P00764000`, rempli à 4,69 $) ; dépôt public `github.com/s-papy/hindsight-alpha` poussé ; GitHub Pages en ligne sur `https://s-papy.github.io/hindsight-alpha/`, vérifié visuellement, zéro erreur console ; l'interrupteur `HALT` bloque les entrées sans bloquer les sorties ; l'anti-double-soumission se déclenche pour de vrai ; `hindsight_guard` a réellement rejeté XLK en direct.

**Cinq bugs réels trouvés et corrigés dans les passes « cherche encore » du 24/08**, chacun reproduit par un test avant d'être déclaré. Tous de la même famille : *le code protège soigneusement l'action, puis traite sa trace comme un détail*. Détail complet dans `PLAN_SPRINT.md` (sections « cherche encore », de la plus récente à la plus ancienne). Dernier commit : `e20502349bcdb842a2d25b9b9ac78aebce94ac9b`.

🔴 **Et trois FAUX positifs, produits par moi, à savoir avant de me relire** : deux venaient de mes propres montages de test (mauvaise signature d'appel de `check_gates`, exception levée dans une lambda qui cassait la chaîne `__context__`), un venait d'un raisonnement algébrique que le test numérique a démenti. **Si tu relis mes conclusions, vérifie-les — j'ai eu autant de tort que de raison sur les deux dernières passes.**

### 🔴 Le blocage réel : `monitor_exits.py` ne tourne pas

`monitor_exits.py` existe, fonctionne à la main (`--dry-run` testé), et **doit** tourner toutes les 15 minutes : sans lui, `manage_exits()` ne s'exécute qu'au lancement quotidien d'`agent.py`, donc une position qui franchit son stop-loss à -50 % une heure après reste ouverte jusqu'au lendemain. Tout le travail sur les sorties ne sert à rien tant que ce point n'est pas réglé.

Deux problèmes trouvés, **un corrigé, un ouvert** :

1. 🟢 **Corrigé** : le cron documenté dans le docstring (`*/15 9-16`) est en heure **locale**, pas ET. Sur ce Mac (CEST, 6 h d'écart) il tournerait de 03h00 à 10h00 ET — 30 minutes utiles sur une séance de 6h30. Les bons créneaux locaux sont **15h30–22h00**.

2. 🔴 **Ouvert** : une tâche `launchd` a été écrite avec les bons créneaux (140, lun-ven, toutes les 15 min) **et un `PATH` incluant `~/.local/bin`** (sinon le binaire `alpaca` est introuvable — piège déjà payé). Elle est **installée et chargée**, mais elle échoue :

```
/usr/bin/python3: can't open file '.../hindsight-alpha/monitor_exits.py': [Errno 1] Operation not permitted
```

**Diagnostic prouvé par sonde contrôlée, pas supposé** : un process lancé par launchd lit `~/.zshenv` sans problème mais se voit **refuser tout accès à `~/Desktop/…`**. C'est la protection **TCC de macOS sur le Bureau**, ni un chemin, ni un droit de fichier, ni le `PATH`.

---

## Ce qu'on te demande

### A. Débloquer la surveillance des sorties (prioritaire)

1. Choisir **une** des deux issues, et le dire à Spap avant d'agir :
   - **① Accorder l'Accès complet au disque à `/usr/bin/python3`** dans Réglages Système → Confidentialité et sécurité → Accès complet au disque. **C'est Spap qui doit le faire** (mot de passe requis) — ne tente pas de modifier des réglages de sécurité toi-même.
   - **② Déplacer le dépôt hors de `~/Desktop`** (par ex. `~/hindsight-alpha`). Plus lourd : le chemin change dans le `.plist`, et il faut revérifier que git, le remote et Pages suivent.
2. Une fois l'issue choisie et appliquée, **vérifier que ça tourne vraiment** :
   `launchctl kickstart gui/$(id -u)/com.hindsightalpha.monitor-exits`, puis lire `monitor_exits.log`. **Le succès, c'est la ligne `Checking open positions for take-profit / stop-loss...` dans le log — pas l'absence d'erreur.**
3. Confirmer que le `.plist` chargé porte bien les créneaux **15h–21h45 locale** et le `PATH` avec `~/.local/bin`.

### B. Préparer la bascule du 28/08 — **sans y toucher aujourd'hui**

4. Vérifier que la procédure de bascule est écrite noir sur blanc dans `PLAN_SPRINT.md` (compte dédié `PA3K8MP3MF0U`, clés dans `.env.hackathon`). Si elle n'y est pas sous forme de liste d'étapes exécutable, l'écrire.
5. **Relire** (sans l'exécuter) le chemin de re-calibrage automatique : `risk_gates._record_starting_equity()` détecte un changement d'`account_id` et remet à zéro `starting_equity`, `locked`, `traded_today` et `consecutive_losses`. **Testé en mocks uniquement, jamais en direct.** Confirme par lecture que les quatre champs sont bien couverts.
6. Décider ce qu'on fait de la position de test ouverte sur le compte de **dev** (`SPY260831P00764000`, échéance 31/08) : la laisser vivre, ou la fermer. Elle n'affecte pas la soumission (mauvais compte), mais elle fausse le dashboard si celui-ci reste pointé sur le compte de dev.

### C. Si et seulement si A et B sont réglés

7. `python agent.py --dry-run` et `python monitor_exits.py --dry-run` pour confirmer qu'aucune régression n'a été introduite.
8. Commit + push des éventuelles corrections, et mise à jour de `PLAN_SPRINT.md`.

---

## Hors périmètre

- **Ne touche pas à `.env.hackathon` ni au compte `PA3K8MP3MF0U` avant le kickoff du 28/08** — zéro trade, zéro test, zéro `publish_dashboard` dessus, même par erreur. C'est le compte de la soumission finale ; un compte réutilisé disqualifie.
- **Ne passe jamais `--live` au CLI, ne définis jamais `ALPACA_LIVE_TRADE=true`.**
- **Ne modifie aucun seuil de risque** (`MAX_RISK_PCT_PER_TRADE`, `MAX_TOTAL_RISK_PCT`, `MAX_SECTOR_EXPOSURE_PCT`, `WEEKLY_LOSS_LOCK_PCT`, `MAX_OPEN_POSITIONS`, `MAX_CONSECUTIVE_LOSSES`, `CHEAP_VOL_PERCENTILE`) — ce sont des choix arrêtés, pas des curseurs.
- **Ne bascule pas la stratégie sur `momentum_strategy.py`** : `compare_strategies.py` montre `vol_strategy` devant sur le Sharpe in-sample des 4 symboles, mais `momentum` plus propre côté garde-fou (4/4 contre 3/4). C'est une décision de méthode, elle appartient à Spap.
- **Ne modifie pas les réglages système de sécurité toi-même** — l'Accès complet au disque se donne par Spap, dans l'interface, avec son mot de passe.
- **Pas de `git push --force`.** Pas de vidéo, de deck ni de write-up d'une page — session à part, explicitement.
- **Ne touche à aucun autre dossier de CERVEAU.**

---

## En fin de séance

Verdict net, sans entre-deux, point par point :

- **`monitor_exits` planifié et vérifié en vrai** : oui (avec l'extrait de `monitor_exits.log` qui le prouve) — ou bloqué, avec l'issue choisie et ce qui manque exactement.
- **Procédure de bascule du 28/08** : écrite dans `PLAN_SPRINT.md` (oui/non), et les quatre champs de re-calibrage confirmés par lecture.
- **Position de test** : laissée ouverte ou fermée, et pourquoi.
- **Commit poussé** (hash) ou rien à pousser.

Mets à jour `PLAN_SPRINT.md` avec le résultat réel avant de terminer — une nouvelle section datée, dans la continuité de celles déjà écrites, pas un rapport séparé.

---

**Compte paper trading uniquement — zéro fonds réel engagé.**
