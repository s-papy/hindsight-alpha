# BRIEF — session terminal : tester le re-calibrage de compte pour de vrai, avec un compte paper jetable

*À coller dans une session terminal lancée depuis `~/hindsight-alpha`. Fait suite au sixième bug trouvé et corrigé (commit `49e3c8f`) — ton propre verdict à ce moment-là : "le chemin critique est solide... ce qui reste vraiment ouvert avant le 28, c'est la bascule vers le compte dédié, et le fait que le re-calibrage sur changement de compte n'a jamais été exercé qu'en mocks." Ce brief ferme précisément ce point, sans toucher au compte dédié.*

---

## Contexte, honnêtement

**État du dépôt** : dernier commit `49e3c8f` ("fix: dedup bookkeeping could kill the exit monitor..."), le sixième bug de la journée, même famille que les cinq précédents (une action protégée avec soin, sa trace traitée comme un détail) — trouvé cette fois en chassant spécifiquement le code écrit par Cowork dans les trois passes précédentes, jamais chassé jusque-là.

**Un reste trouvé par Cowork en relisant ce commit** : un commentaire orphelin (deux lignes qui appartenaient à l'appel `_save_dedup_state(...)` d'origine, laissées accrochées à la branche `except` après le déplacement du code, où elles affirment maintenant l'inverse de ce que fait cette branche). Corrigé, **non committé** — cosmétique, zéro impact fonctionnel, `py_compile` propre. `git status` actuel : seul `monitor_exits.py` modifié.

**Le point vraiment ouvert** : `risk_gates._record_starting_equity()` détecte un changement d'`account_id` et réinitialise `starting_equity`, `locked`, `traded_today`, `consecutive_losses` — confirmé par LECTURE du code (voir `PLAN_SPRINT.md`, réponse au brief `BRIEF_DEBLOQUER_MONITOR_ET_KICKOFF.md`) et par des tests en mocks, **jamais exercé contre l'API réelle**. Spap a choisi explicitement de fermer ce point maintenant, avec un troisième compte paper jetable — pas le compte de dev, pas `PA3K8MP3MF0U` — plutôt que d'attendre le 28/08 pour le découvrir sous pression.

**Le même trou déjà documenté s'applique ici** : `config.py` charge `.env` en dur (`load_dotenv(Path(__file__).parent / ".env")`), aucun mécanisme pour pointer vers un autre fichier. La procédure de bascule sûre déjà écrite dans `PLAN_SPRINT.md` (sauvegarde → copie → test → restauration) est directement réutilisable ici — c'est même l'occasion de la valider en vrai avant de s'en servir pour de bon le 28.

## Ce qu'on te demande

1. **Créer un troisième compte paper** sur le tableau de bord Alpaca (alpaca.markets, sélecteur de compte paper → nouveau compte) — étape manuelle, nécessite un navigateur authentifié, hors de portée de Cowork. Générer une nouvelle paire de clés API pour ce compte.
2. Créer `.env.test2` à la racine du dépôt (déjà couvert par `.env.*` dans `.gitignore`, rien à ajouter) avec ces nouvelles clés, sur le modèle de `.env.example`.
3. **Avant de basculer**, note le contenu actuel de `state.json` (compte de dev) — pour comparaison, pas pour restauration exacte : `locked` et `consecutive_losses` sont déjà à leurs valeurs de repos d'après le dernier état connu, donc rien de précieux à perdre, mais autant vérifier avant qu'après.
4. Bascule : `cp .env .env.dev.bak` puis `cp .env.test2 .env`.
5. `python test_connection.py` — attendu : connexion réussie, `account_number` différent à la fois de celui du compte de dev et de `PA3K8MP3MF0U`.
6. `python agent.py --dry-run` — un seul run. Lire `state.json` juste après et confirmer les **quatre champs** re-calibrés pour de vrai : `account_id` a changé (vers l'UUID du nouveau compte), `starting_equity` reflète l'équité réelle du nouveau compte (pas un report de l'ancien), `locked: false`, `traded_today` vide, `consecutive_losses: 0`.
7. **Bascule retour, qui teste la même mécanique une deuxième fois, dans l'autre sens** : `cp .env.dev.bak .env`, `python test_connection.py` (confirme le retour sur dev), `python agent.py --dry-run` à nouveau, relire `state.json` — confirme que le re-calibrage se déclenche aussi correctement au retour (les quatre champs se réinitialisent encore une fois, cette fois vers l'équité réelle du compte de dev). C'est attendu et sans conséquence réelle : rien de précieux n'était stocké dans l'ancien état du compte de dev (voir point 3).
8. Nettoyage : `rm -f .env.dev.bak .env.test2`. Le troisième compte paper lui-même peut rester ou être fermé sur le tableau de bord Alpaca, au choix de Spap — aucune conséquence côté code.
9. Mets à jour `PLAN_SPRINT.md` avec le résultat réel (nouvelle section datée, à la suite de celles déjà écrites) : les 4 champs confirmés en vrai dans les deux sens, ou ce qui a coincé exactement.
10. Si tout est propre : commit du petit correctif cosmétique de Cowork sur `monitor_exits.py` laissé en attente, et push.

## Hors périmètre

- **Ne touche pas à `.env.hackathon` ni au compte `PA3K8MP3MF0U`** — ce test utilise un troisième compte, jamais celui-là, avant comme après le kickoff du 28/08.
- **`--dry-run` obligatoire à chaque étape 6 et 7** — aucun ordre réel n'a besoin d'être soumis pour vérifier le re-calibrage ; `check_gates()` lit l'équité réelle du compte que `--dry-run` n'empêche pas.
- **Ne modifie aucun seuil de risque** ni `HEARTBEAT_SECONDS`.
- **Ne ferme pas la position de test** (`SPY260831P00764000`, compte de dev) sauf raison nouvelle.
- **Ne bascule pas la stratégie sur `momentum_strategy.py`.**
- **Pas de `git push --force`.**
- **Ne touche à aucun autre dossier de CERVEAU.**

## En fin de séance

Verdict net, point par point :
- **Compte jetable créé** : oui (numéro de compte, pas les clés) — ou bloqué, pourquoi.
- **Les 4 champs re-calibrés, aller** (dev → jetable) : confirmés en vrai, avec les valeurs observées — ou pas.
- **Les 4 champs re-calibrés, retour** (jetable → dev) : confirmés en vrai — ou pas.
- **Nettoyage fait** : `.env.dev.bak` et `.env.test2` supprimés, confirmé par `ls`.
- **Commit poussé** (hash) ou rien à pousser.

Mets à jour `PLAN_SPRINT.md` avant de terminer.

---

**Compte paper trading uniquement — zéro fonds réel engagé.**
