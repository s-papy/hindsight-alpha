# BRIEF — session terminal : authentification GitHub, push, activation de Pages

*À coller dans une session terminal lancée depuis `~/Desktop/CERVEAU/hindsight-alpha/`. Fait suite à `BRIEF_GIT_DASHBOARD_PUBLICATION.md` — ce brief avait 8 points sur 10 validés (git reconstruit propre, secrets vérifiés, dashboard publié et vérifié visuellement en local, 5ᵉ bug réel trouvé et corrigé — `alpaca position close` exige `--symbol-or-asset-id`, pas `--symbol`, testé en fermant réellement une position live). Seuls les points 5/7/8 (dépôt GitHub, push, Pages) sont restés bloqués, faute d'authentification GitHub sur ce Mac.*

---

## Contexte, honnêtement

**État git actuel, vérifié depuis Cowork juste avant ce brief** : 3 commits locaux propres sur `main` — `68c778d` (commit initial, 21 fichiers), `c7f1376` (fix `close_position` + premier snapshot dashboard réel), `5811586` (mise à jour de `PLAN_SPRINT.md` avec les résultats de la session précédente). `git remote -v` est vide : aucun remote configuré, donc rien n'a encore été poussé nulle part.

**Mon propre problème à corriger en premier** : en vérifiant l'état du dépôt depuis Cowork (`git status`), ça a laissé un `.git/index.lock` orphelin que le bac à sable Cowork ne peut pas supprimer (permission refusée — même restriction que pour `test-gitignore-check/` dans une session précédente). Ce lock bloquera toute vraie commande git tant qu'il traîne. À supprimer en tout premier, avant quoi que ce soit d'autre.

**Ce qui bloquait la dernière fois** : ni `gh`, ni token, ni clé SSH, ni credential helper, ni trousseau configuré pour GitHub sur ce Mac. Spap a peut-être déjà lancé `gh auth login` de son côté — à vérifier en premier, pas à supposer.

## Ce qu'on te demande

1. `rm -f .git/index.lock` (mon verrou orphelin, sans danger à supprimer — zéro commit en cours).
2. Vérifier l'état réel : `git status` (doit être propre, rien en attente), `git log --oneline` (doit montrer les 3 commits ci-dessus), `git fsck` (doit être propre, les "dangling blob" déjà vus sont normaux — résidus du retrait de `.DS_Store`, pas un souci).
3. Vérifier l'authentification GitHub : `gh auth status`. Si pas connecté, `gh auth login` (GitHub.com → HTTPS → connexion via navigateur). Si `gh` n'est toujours pas installé, `brew install gh` d'abord.
4. Créer le dépôt public : `gh repo create hindsight-alpha --public --source=. --remote=origin` (ou, si tu préfères le faire à la main sur github.com puis `git remote add origin <url>` — dis-moi le nom choisi avant si tu changes de nom de dépôt).
5. **Avant tout push**, un dernier coup d'œil : `git show --stat HEAD~2` (le commit initial) pour confirmer qu'aucun fichier surprenant n'y figure — la liste doit correspondre aux fichiers `.py`, `docs/`, `README.md`, `LICENSE`, `.gitignore`, `.env.example`, `PLAN_SPRINT.md`, `BRIEF_*.md`. Si tu vois `.env`, `.env.hackathon`, ou `state.json` dans cette liste, **arrête-toi et dis-le moi** — ne pousse pas.
6. `git push -u origin main`.
7. Activer GitHub Pages : Settings du dépôt → Pages → Deploy from branch → `main` → `/docs` → Save. Note l'URL générée (`https://<user>.github.io/hindsight-alpha/`).
8. **Vérification visuelle réelle sur l'URL publique** (attends quelques minutes que le déploiement Pages se termine) : les 3 sections (Account, Open Positions, Recent Decisions) doivent s'afficher sans erreur console, avec les mêmes chiffres que `docs/data.json` (equity, la position `SPY260831P00763000` si elle est encore ouverte à ce moment, ou vide si elle a été fermée entre-temps). Dis-moi précisément ce qui s'affiche, pas juste "ça marche".
9. Note quelque part de facilement retrouvable (dans `PLAN_SPRINT.md`) : l'URL du dépôt GitHub public et l'URL Pages — ce sont deux des champs requis à la soumission finale du hackathon ("Public GitHub repository", "Application URL").

## Hors périmètre

- Ne jamais toucher au compte dédié "Spap" (`.env.hackathon`) avant le kickoff du 28/08.
- Ne jamais passer `--live` au CLI ni définir `ALPACA_LIVE_TRADE=true`.
- Ne jamais committer `.env`, `.env.hackathon`, ni coller de clé API dans un message de commit, un commit, ou ce brief.
- Pas de `git push --force` à quelque étape que ce soit.
- Le dépôt doit être **public**, mais vérifie l'absence de secrets (étape 5) avant de le rendre public, pas après — plus facile de ne rien pousser que de purger un historique public.
- Ne modifie pas les seuils de `risk_gates.py` sans en parler d'abord.
- Ne touche à aucun autre dossier de CERVEAU pendant cette session.

## En fin de séance

Verdict net : `.git/index.lock` supprimé (oui/non), `gh auth status` (connecté ou non, et comment résolu si ça bloquait), dépôt GitHub créé et poussé (URL exacte), Pages activé et vérifié visuellement (URL exacte + ce qui s'affiche vraiment). Si un point coince, dis lequel et l'erreur exacte plutôt que de sauter au suivant en silence. Mets à jour `PLAN_SPRINT.md` avec les deux URLs avant de terminer — elles seront nécessaires pour la soumission finale.

---

**Compte paper trading uniquement — zéro fonds réel engagé.**
