# BRIEF — session terminal : la recherche concurrence/règles est déjà faite, ne pas la refaire

*À coller dans une session terminal lancée depuis `~/hindsight-alpha`. Fait suite à `BRIEF_COMMIT_4_CORRECTIFS_ET_NETTOYAGE.md` — son verdict (commits `afaef46`, `4aae387`, `4b7a708`, tous poussés) : les 4 correctifs "cherche encore" vérifiés et committés, `alpaca_client.py` retiré, les 3 fichiers bloqués supprimés (confirmant que c'était bien une restriction du bac à sable Cowork, pas une vraie corruption). Ce brief est différent des précédents : ce n'est pas une demande de vérifier du code, c'est une note pour économiser du temps — Spap a demandé "cherche la concurrence, les éditions passées, les axes non couverts" à Cowork, et Cowork a déjà fait cette recherche avec un accès web réel (WebSearch + Chrome). Le but ici est que tu partes de ces résultats plutôt que de refaire les mêmes recherches.*

---

## Contexte, honnêtement

`git status` actuel : `PLAN_SPRINT.md` et `submission/Hindsight_Alpha_Writeup.docx` modifiés, `SOCIAL_POSTS_DRAFT.md` nouveau, untracked. `HEAD` local == `origin/main` == `4b7a708`, donc tout ce qui suit part de cette base propre. Rien de tout ça n'est du code — pas de `py_compile` à relancer pour cette partie-là.

## Ce que la recherche a déjà établi (ne pas refaire)

**Page officielle du hackathon (lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon), lue intégralement le 25/08** :
- **Un seul track** : "Options Alpha Agents" — exactement ce que fait ce projet, pas de dispersion à arbitrer.
- **Exigence de compte jamais vue avant aujourd'hui, textuelle** : *"Competition account starting balance must be set to $100,000"* et *"create a brand-new Alpaca paper trading account dedicated to this hackathon... Projects run on an existing or reused account will not be eligible for judging."* Détail opérationnel trouvé en même temps : un reset de compte paper Alpaca **invalide l'ancienne clé API** (il faut en régénérer une et mettre `.env.hackathon` à jour) — donc si le solde n'est pas bon le 28, ce n'est pas juste "changer un chiffre". Action précise déjà écrite dans `PLAN_SPRINT.md` (section "exigence trouvée en lisant la page officielle du hackathon") : `alpaca account get --quiet` en tout premier le 28/08, avant tout autre appel.
- **5 critères de jugement officiels, textuels** : P&L Performance · Technology Implementation · Creativity & Originality · Presentation & Execution · **Social engagement** (jusqu'à 5 posts X/LinkedIn, taguant @lablabai et @AlpacaHQ — **c'est un critère du classement principal, pas juste le prix "Build in Public" séparé à $500/équipe**). `PLAN_SPRINT.md` le sous-estimait ("bonus optionnel") avant cette recherche — corrigé.
- Prix : $2500 / $1500 / $1000 (1er/2e/3e), + 2 équipes gagnantes du volet social à $500 chacune + 1 mois Algo Trader Plus par membre.

**Concurrence, vue via Chrome (page live + pages d'équipes)** : hackathon pas commencé (démarre 28/08), 2245+ inscrits, 546 équipes en formation, aucune soumission réelle encore. Les pitchs visibles (AgentAlpha, Bagholders, quasar, Jetpack, Atleast) sont tous génériques — aucun ne nomme une stratégie précise ou un mécanisme d'auto-vérification. Pas d'édition précédente de CE hackathon à étudier (première édition).

**Recherche complémentaire (alpaca.markets/learn, "Weekly Roundup #1")** : ce qu'Alpaca met en avant dans sa communauté — documentation publique du raisonnement en temps réel, visualisation du risque au-delà d'une recommandation brute, outillage réutilisable. Une piste concrète en est ressortie : des ordres **bracket/OCO côté broker** (take-profit/stop-loss posés directement chez Alpaca, pas seulement surveillés par polling local) — **non implémentée**, parce que Cowork n'a pas d'accès réseau réel pour vérifier si Alpaca supporte ça sur les OPTIONS (confirmé seulement pour les actions dans ce qui a été trouvé). C'est le seul point de cette recherche qui a vraiment besoin d'une session terminal — voir la demande ci-dessous.

**Analyse chiffrée déjà faite** (section "regarder en face" dans `PLAN_SPRINT.md`) : fenêtre de marché réelle sur la semaine jugée ≈ 4 jours pleins (31/08→3/09, calculé jour par jour — pas de Labor Day dans la fenêtre, il tombe le 7/09), fréquence de trade mesurée ≈ 17,9 % en moyenne sur les 3 symboles valides aujourd'hui (XLK recalé par `hindsight_guard`) → **environ 2 trades espérés sur toute la semaine**. Pas une raison de toucher aux seuils — une raison d'investir sur les 4 autres critères. Décision d'élargir l'univers (`DEFAULT_UNIVERSE`) explicitement laissée à Spap, pas prise ici.

**Tout ce détail est déjà écrit, avec les citations exactes et les calculs, dans `PLAN_SPRINT.md`** (chercher les 5 sections datées du 25/08 après celle sur `alpaca_client.py`) — pas la peine de relire la page lablab.ai ou de refaire les recherches web, juste lire ces sections.

## Ce qu'on te demande

1. `git status` et `git diff --stat` — confirme que `PLAN_SPRINT.md`, `submission/Hindsight_Alpha_Writeup.docx` et `SOCIAL_POSTS_DRAFT.md` (nouveau) sont les seuls changements.
2. Ouvre `submission/Hindsight_Alpha_Writeup.docx` (ou convertis en PDF pour vérifier visuellement) — confirme que le rendu est propre sur une seule page, comme exigé par le règlement ("one-page write-up"), et que les chiffres correspondent bien à `BACKTEST_RESULTS.md` actuel.
3. **La seule vraie tâche technique de ce brief** : vérifie si Alpaca supporte les ordres bracket/OCO sur les OPTIONS (pas juste les actions).
   - `alpaca order submit --help` — les flags `--order-class`, `--take-profit-limit-price`, `--stop-loss-stop-price` (ou noms équivalents) existent-ils ?
   - Si oui, teste en paper sur le compte de **dev** (`.env`, pas `.env.hackathon`) : soumets un bracket order réel sur un symbole d'option OCC valide, puis `alpaca order list` pour confirmer que le take-profit et le stop-loss existent bien comme des ordres actifs côté Alpaca, pas juste acceptés silencieusement puis ignorés.
   - **N'implémente rien dans le code sur cette base** — c'est une vérification factuelle à rapporter, pas une décision à prendre. Si ça marche, note-le dans `PLAN_SPRINT.md` comme une option pour Spap, avec ce qui a été vérifié exactement.
4. Si tout est propre : `git add`, un commit qui regroupe ces 3 fichiers (recherche + write-up corrigé + brouillons de posts), `git push`.
5. Mets à jour `PLAN_SPRINT.md` avec le résultat réel de la vérification bracket/OCO (nouvelle section datée, à la suite de celles déjà écrites).

## Hors périmètre

- **Ne touche pas à `.env.hackathon` ni au compte `PA3K8MP3MF0U` avant le kickoff du 28/08** — la vérification du solde $100k et la régénération de clé si besoin, c'est un geste du 28, pas d'aujourd'hui.
- **Ne poste rien sur X/LinkedIn** — les brouillons dans `SOCIAL_POSTS_DRAFT.md` sont pour Spap, à personnaliser et poster lui-même.
- **N'implémente pas de bracket/OCO order dans `risk_gates.py`/`alpaca_cli.py`** même si le test au point 3 marche — c'est un changement de comportement de soumission d'ordre, la décision revient à Spap, pas une action à prendre silencieusement ici.
- **Ne modifie aucun seuil de risque** ni `DEFAULT_UNIVERSE`.
- **Ne bascule pas la stratégie sur `momentum_strategy.py`.**
- **Pas de `git push --force`.**
- **Ne touche à aucun autre dossier de CERVEAU.**

## En fin de séance

Verdict net, point par point :
- **Write-up vérifié** (rendu propre, une page, chiffres à jour) : oui ou pas.
- **Bracket/OCO sur options** : supporté ou pas, avec la preuve exacte (sortie de commande) — ou pas eu l'occasion de tester, et pourquoi.
- **Commit poussé** (hash) ou rien à pousser.

Mets à jour `PLAN_SPRINT.md` avant de terminer.

---

**Compte paper trading uniquement — zéro fonds réel engagé.**
