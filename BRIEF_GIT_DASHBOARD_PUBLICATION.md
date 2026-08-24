# BRIEF — session terminal : nettoyage git, dépôt public, publication du tableau de bord

*À coller dans une session terminal lancée depuis `~/Desktop/CERVEAU/hindsight-alpha/`. Fait suite à `BRIEF_TEST_AGENT_TERMINAL.md` — ce premier brief a confirmé que le pipeline tourne bout en bout contre l'API réelle (ordre paper `id=e896888f-7c58-418a-aefc-3d5034cfaef9`, 2 puts `SPY260831P00763000`) et a trouvé/corrigé 4 écarts réels entre le code et l'API (voir `PLAN_SPRINT.md`, section "🟢 24/08"). Ce brief-ci couvre ce qui restait explicitement reporté : le nettoyage git et la première publication du tableau de bord.*

---

## Contexte, honnêtement

**État git actuel, vérifié par `Glob` depuis Cowork (pas juste supposé)** :
- `.git/` existe déjà dans `hindsight-alpha/` mais est dans un état cassé : `index.lock` présent (verrou orphelin, un `git` précédent n'a pas terminé proprement), un fichier étrange `.git/th02JRu` à la racine du `.git` (ne devrait pas exister), et plusieurs objets `tmp_obj_*` non finalisés dans `.git/objects/`. Aucun commit n'a jamais été fait (pas de `.git/refs/heads/` ni de HEAD valide confirmé). Le bac à sable Cowork ne peut pas réparer ça de façon fiable (pas de `git` fonctionnel dans ce sandbox pour ce dossier).
- `test-gitignore-check/` : un sous-dossier avec son propre `.git/` complet, créé par erreur depuis Cowork (commande `git init` mal ciblée pendant un contrôle de `.gitignore` — mon erreur, pas la tienne). Cowork ne peut pas le supprimer (`rm` refuse dans ce dossier partagé). À supprimer à la main.
- `.gitignore` est correct et déjà vérifié avec le vrai `git check-ignore` : `.env`, `.env.hackathon`, `state.json` bien exclus, `.env.example` bien suivi. Donc une fois `.git` reconstruit proprement, un `git add -A` normal ne devrait pas embarquer de secret — mais à revérifier avant tout push, jamais en confiance aveugle sur ce point précis vu que le hackathon disqualifie en cas de compte réutilisé/exposé.

**Tableau de bord — construit et vérifié seulement à froid** : `docs/index.html` (page statique, aucune dépendance externe), `publish_dashboard.py` (génère `docs/data.json` depuis le compte réel + `decision_log.jsonl`), `decision_log.py` (câblé dans `agent.py`, chaque run écrit une ligne). Vérifié depuis Cowork : HTML bien formé, JS syntaxiquement valide (`node --check`), chaque champ lu par le JS confirmé correspondre à ce que `publish_dashboard.py` produit réellement. **Jamais vu s'afficher dans un vrai navigateur** — Cowork n'a pas pu ouvrir de fichier local dans Chrome pour vérifier visuellement. `docs/data.json` contient actuellement un exemple explicitement fictif (`"id": "PLACEHOLDER"`, daté `2026-01-01`) — sera remplacé par le premier vrai run de `publish_dashboard.py`.

**Point encore ouvert du premier test réel** : `alpaca position close` (fermeture d'une position à ±50%) n'a jamais été exercée contre l'API réelle — la position de test (`SPY260831P00763000`) n'a jamais franchi ce seuil (plpc lu à -1,64% lors du dernier test, dans la fourchette [-50%, +50%]). Seule la branche "garder" de `manage_exits()` a une confirmation live ; la branche "fermer" ne repose encore que sur des mocks Cowork.

## Ce qu'on te demande

1. **Nettoyer `test-gitignore-check/`** : `rm -rf test-gitignore-check/` depuis `hindsight-alpha/`. Confirme qu'il a bien disparu.
2. **Reconstruire `.git` proprement** : `rm -rf .git` (le `.git` cassé actuel, zéro commit dedans donc rien à perdre), puis `git init -b main`. Vérifie `git status` avant tout `add` pour voir exactement ce qui serait suivi.
3. **Vérifier l'absence de secrets avant le premier commit** : `git status` puis un coup d'œil sur la liste — `.env` et `.env.hackathon` ne doivent PAS apparaître comme "untracked to be added" une fois `.gitignore` actif (confirme avec `git check-ignore -v .env .env.hackathon state.json` — les trois doivent matcher une règle). Si l'un des trois n'est pas ignoré, arrête-toi et dis-le moi avant de committer quoi que ce soit.
4. **Premier commit** : `git add -A`, `git status` une dernière fois pour lire la liste complète des fichiers stagés, puis `git commit -m "initial commit: Hindsight Alpha agent + risk gates + dashboard"`.
5. **Créer le dépôt GitHub public** (requis par les règles du hackathon — "Public GitHub repository") : soit via `gh repo create hindsight-alpha --public --source=. --remote=origin` (si `gh` est installé et authentifié), soit manuellement sur github.com puis `git remote add origin <url>`. Pas de push avant de me confirmer le nom/l'URL choisie.
6. **Premier vrai `python publish_dashboard.py`** (sans `--git-push` d'abord, pour vérifier le fichier généré avant de le committer) — utilise le compte de dev (`.env`), pas `.env.hackathon`. Ouvre `docs/data.json` généré et vérifie que les champs ont l'air sains (equity, positions, decisions récentes).
7. **Push** : `git push -u origin main`, puis `git add docs/data.json decision_log.jsonl && git commit -m "dashboard: first real snapshot" && git push`.
8. **Activer GitHub Pages** : Settings → Pages → Deploy from branch → `main` → `/docs`. Note l'URL générée (`https://<user>.github.io/hindsight-alpha/`).
9. **Vérification visuelle réelle** : ouvre l'URL Pages dans un vrai navigateur une fois le déploiement terminé (peut prendre quelques minutes). Regarde si les 3 sections (Account, Open Positions, Recent Decisions) s'affichent sans erreur JS visible, et si les nombres correspondent à ce que tu vois dans `docs/data.json`. C'est la première vérification visuelle réelle de ce fichier — dis-moi précisément si quelque chose ne s'affiche pas comme attendu.
10. **Exercer la branche "fermer" jamais testée** : regarde l'état actuel de la position de test (`alpaca position list --quiet`). Si son `unrealized_plpc` a franchi ±50% naturellement depuis le dernier test, `python agent.py --dry-run` devrait le signaler sans la fermer réellement — confirme ce que ça affiche. Si tu veux aller plus loin et vraiment exercer le code (`risk_gates.manage_exits()` en dehors du dry-run, ou directement `alpaca position close --symbol SPY260831P00763000 --quiet`), c'est du paper trading donc zéro risque réel — à toi de voir si tu as le temps, sinon on le laissera pour la semaine du hackathon où ça se déclenchera naturellement.

## Hors périmètre

- Ne jamais toucher au compte dédié "Spap" (`.env.hackathon`) avant le kickoff du 28/08 — zéro trade, zéro test dessus, même pour le dashboard.
- Ne jamais passer `--live` au CLI ni définir `ALPACA_LIVE_TRADE=true`.
- Ne jamais committer `.env`, `.env.hackathon`, ni coller de clé API dans un message de commit, un commit, ou ce brief.
- Le dépôt GitHub doit être **public** (exigence du hackathon), pas privé — mais vérifie qu'aucun secret n'y va avant de le rendre public, pas après.
- Ne modifie pas les seuils de `risk_gates.py` (MAX_RISK_PCT_PER_TRADE, WEEKLY_LOSS_LOCK_PCT, TAKE_PROFIT_PCT, STOP_LOSS_PCT) sans en parler d'abord.
- Ne touche à aucun autre dossier de CERVEAU pendant cette session.
- Ne force pas un `git push --force` à quelque étape que ce soit — si quelque chose bloque, arrête-toi et dis-le.

## En fin de séance

Verdict net, un état par point : `test-gitignore-check/` supprimé (oui/non), `.git` reconstruit avec un premier commit propre (hash du commit), dépôt GitHub public créé et poussé (URL), GitHub Pages activé et vérifié visuellement (URL + ce qui s'affiche vraiment, capture d'écran ou description précise si quelque chose cloche), et l'état de la position de test / branche `close_position` (testée pour de vrai, ou encore en attente et pourquoi). Si un point a coincé, dis lequel et l'erreur exacte plutôt que de passer au suivant en silence. Mets à jour `PLAN_SPRINT.md` avec le résultat réel avant de terminer.

---

**Compte paper trading uniquement — zéro fonds réel engagé.**
