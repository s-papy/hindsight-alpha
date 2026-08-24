# BRIEF — session terminal : premier test réel de l'agent Hindsight Alpha (hackathon Alpaca)

*À coller dans une session terminal lancée depuis `~/Desktop/CERVEAU/hindsight-alpha/`. Réécrit en entier le 24/08 pour consolider une série de corrections trouvées lors de plusieurs passes de relecture — les versions précédentes de ce brief étaient correctes mais patchées au fil de l'eau, celle-ci est la version propre et à jour. Voir aussi `PLAN_SPRINT.md` pour le plan complet jour par jour.*

---

## Contexte, honnêtement

Ce dossier a été écrit entièrement depuis Cowork (bac à sable Linux), pour l'équipe **Hindsight Alpha** au hackathon **Alpaca AI Trading Agents** (lablab.ai, kickoff 28/08 15:00 UTC, deadline 04/09 15:00 UTC). Page officielle lue en entier, pas juste résumée. Critères de jugement réels : P&L Performance, Technology Implementation, Creativity & Originality, Presentation & Execution, Social engagement. Exigences dures confirmées : agent autonome sur le Trading API **et** (MCP server **ou** CLI), stratégie incluant du trading d'options, **compte paper neuf et dédié** pour la soumission finale (un compte réutilisé disqualifie), solde de départ à 100 000 $, licence MIT.

**Deux comptes Alpaca existent, ne pas les confondre** :
- Compte de dev (`.env`) — utilisé pour tous les tests, autorisé pour le développement selon les règles du hackathon.
- Compte dédié "Spap" (`PA3K8MP3MF0U`, clés dans `.env.hackathon`) — créé le 24/08, jamais touché, **à ne PAS utiliser avant le kickoff du 28/08**. Ce sera le compte de la soumission finale.

**La stratégie** : sweep de 5 fenêtres candidates de volatilité réalisée (10/20/30/60/90 jours) sur un petit univers de symboles (`SPY,QQQ,IWM` par défaut) pour une règle "achète de l'optionalité (call ou put) quand la volatilité réalisée est bon marché par rapport à son propre historique sur 1 an, sinon reste à l'écart". Le premier symbole qui passe tous les filtres est tradé. Voir `vol_strategy.py` pour la documentation honnête de la simplification (rang de volatilité *réalisée*, pas *implicite* — Alpaca n'expose pas d'historique d'IV à balayer ; payoff de backtest approximatif, pas un vrai modèle Black-Scholes). **Aucune preuve que la thèse elle-même soit gagnante** — seule la mécanique a été vérifiée, pas l'edge réel.

**Accès Alpaca : le CLI officiel, pas le SDK.** L'exigence du hackathon est explicitement "MCP or CLI", pas juste "Trading API" — un premier brouillon appelait `alpaca-py` en direct, corrigé après lecture complète des règles. Le CLI (`github.com/alpacahq/cli`) a été préféré au MCP server parce que la doc Alpaca elle-même le recommande pour ce cas précis (agent autonome/cron, une commande puis sortie — pas une session IA pilotée par un humain). Tout passe par `alpaca_cli.py`, qui ajoute systématiquement `--quiet` à chaque appel (sinon un bandeau du CLI, documenté "Alpha Preview", pourrait casser le parsing JSON).

**Pipeline complet, dans l'ordre réel d'exécution** :
1. Vérifie que le marché est ouvert (`alpaca clock`) — sort proprement sinon, pas de crash.
2. `risk_gates.manage_exits()` — ferme toute position ouverte à +50% (profit) ou -50% (perte) de P&L latent, avant même d'évaluer une nouvelle entrée.
3. Pour chaque symbole de l'univers : sweep des 5 fenêtres HV, vérifié par `hindsight_guard` (la fenêtre gagnante sur tout l'historique doit aussi gagner en ne scorant que ce qui aurait été connu avant les 20 derniers jours — sinon refus, fuite détectée). Si le check passe et que la volatilité est bon marché aujourd'hui, ce symbole est candidat.
4. Le premier symbole candidat est tradé : recherche d'un contrat proche de la monnaie via `alpaca api GET /v2/options/contracts`, puis `risk_gates.check_gates()` (position déjà ouverte ? plafond de 1% de l'équité par trade, dimensionné sur le prix ask réel ? verrou de -3% de perte hebdo actif dans `state.json` ?), puis `alpaca order submit` si tout passe.

**Ce qui a été vérifié depuis Cowork** (mécanique uniquement, jamais contre de vraies données) :
- Les 7 fichiers `.py` compilent sans erreur.
- Pipeline complet rejoué en une fois avec des mocks (fermeture de position + sweep multi-symboles + garde-fous + ordre) — comportement correct.
- Bug réel trouvé et corrigé : avec l'historique par défaut d'avant (~250 jours), les fenêtres 60 et 90 jours du sweep recevaient **zéro échantillon exploitable** (vérifié par calcul), 30 jours seulement 8 points — le sweep "5 candidats" n'en comparait réellement que 2. Corrigé, historique porté à ~600 jours de bourse (`vol_strategy.MIN_TRADING_DAYS_FOR_SWEEP`, calculé, pas arbitraire). Revérifié : les 5 fenêtres reçoivent chacune plusieurs centaines de points désormais.
- `.gitignore` vérifié avec le vrai `git check-ignore` (pas une simulation) : `.env`, `.env.hackathon`, `state.json` bien exclus, `.env.example` bien suivi.
- Aucun import actif ne pointe vers le code mort (`alpaca_client.py` — ancienne version SDK, `momentum_strategy.py` — ancienne stratégie momentum). Ces deux fichiers traînent dans le dossier (Cowork n'a pas pu les supprimer, restriction du bac à sable) mais rien ne les importe — supprimables à la main si tu veux nettoyer.
- Licence MIT ajoutée (`LICENSE`) — la page de règles exige explicitement "Submissions must be original and MIT-compliant", et ce dossier n'en avait aucune contrairement à `../hindsight-guard/`.

**Ce qui n'a jamais été testé, et c'est le blocage réel** : le binaire `alpaca` n'est pas installable dans le bac à sable Cowork (pas de réseau vers les domaines Alpaca — `403 Forbidden`, `X-Proxy-Error: blocked-by-allowlist` déjà confirmé pour l'API REST directe). **Points les plus incertains du code**, tous documentés en commentaires dans `alpaca_cli.py`/`risk_gates.py`, à vérifier en premier avec `--schema` (flag réel du CLI) avant de faire confiance au reste :
- `alpaca data bars` — noms de champs (essaie `c`/`close`, imbriqué par symbole ou non).
- `alpaca position list` — comment identifier une position "option" (cherche `asset_class` contenant "option", sinon un symbole au format OCC) et le nom du champ de P&L latent (essaie `unrealized_plpc`, sinon calcule depuis `unrealized_pl`/`cost_basis`).
- `alpaca data option snapshot` — où se trouve le prix ask (essaie plusieurs chemins de clés plausibles).
- Que le plan de données Alpaca gratuit fournit bien ~2-3 ans de barres journalières sans restriction — supposé, jamais confirmé.

**Nouveau depuis le premier test réel : tableau de bord hébergé + nettoyage git.** `docs/index.html` (page statique) + `publish_dashboard.py` (génère `docs/data.json` depuis le compte réel) + `decision_log.py` (journal des décisions, câblé dans `agent.py` — chaque run écrit maintenant une ligne dans `decision_log.jsonl`). Choix d'hébergement : GitHub Pages sur ce dépôt, même schéma que le tableau de bord D31 de SNIPER. Vérifié sans navigateur réel (HTML bien formé, JS valide, champs cross-vérifiés contre ce que le code produit) mais **jamais vu s'afficher pour de vrai** — à vérifier visuellement. `docs/data.json` contient actuellement un exemple explicitement fictif (`"PLACEHOLDER"`, daté 2026-01-01) — sera remplacé au premier vrai `publish_dashboard.py`.

Aussi en attente depuis la dernière session : `test-gitignore-check/` (créé par erreur pendant un contrôle Cowork, le bac à sable ne peut pas le supprimer) et le `.git` existant (fichiers indexés, zéro commit — reliquat d'une tentative avortée).

## Ce qu'on te demande

1. Installer le CLI : `brew install alpacahq/tap/cli` (ou `go install github.com/alpacahq/cli/cmd/alpaca@latest`), puis `alpaca doctor` pour vérifier.
2. `cd ~/Desktop/CERVEAU/hindsight-alpha/` puis `pip install -r requirements.txt` (juste `python-dotenv`).
3. Vérifier que `.env` existe et contient les clés du **compte de dev** (`cat .env` — ne les partage nulle part). Ne touche pas à `.env.hackathon`. Vérifier que `state.json` contient bien `{}` (remis à zéro après les tests Cowork).
4. `python test_connection.py` — doit afficher le statut du compte via le CLI. Si ça échoue, colle-moi l'erreur exacte (sans les clés).
5. **Avant tout le reste**, vérifier les schemas réels un par un et comparer à ce que le code attend (section ci-dessus) :
   - `alpaca data bars --symbol SPY --start 2026-01-01 --timeframe 1Day`
   - `alpaca position list` (peut être vide si aucune position — normal)
   - `alpaca data option snapshot --symbol <un vrai symbole d'option>` (prends-en un dans la sortie de `alpaca option contracts --underlying-symbol SPY` si besoin)
   Si un format ne colle pas, dis-le moi avec un extrait du JSON réel — corrections rapides et ciblées dans `alpaca_cli.py`.
6. Si les schemas collent : `python agent.py --dry-run` — doit vérifier le marché ouvert, gérer les sorties (rien à fermer normalement), dérouler le sweep sur les 3 symboles, afficher le verdict `hindsight_guard` et le symbole retenu si un est vetté. Aucun ordre n'est passé en `--dry-run`.
7. Si le dry-run est propre et qu'on est prêts à tester un vrai ordre (toujours sur le compte de dev) : `python agent.py` une fois. Vérifie que le message "[3] Checking risk gates..." s'affiche et que la quantité affichée est cohérente (pas forcément 1 — elle est maintenant calculée depuis le prix réel de l'option et le plafond de 1% de l'équité, pas fixée en dur).
8. Note tout ce qui a coincé, même corrigé — le vrai état compte plus que "ça marche" à la fin.

## Hors périmètre

- Ne jamais toucher au compte dédié "Spap" (`.env.hackathon`) avant le 28/08 — zéro trade, zéro test dessus.
- Ne jamais passer `--live` au CLI ni définir `ALPACA_LIVE_TRADE=true` — le compte paper existe précisément pour zéro risque financier réel.
- Ne pas committer `.env` ni `.env.hackathon` ni coller de clés API dans un message, un commit, ou ce brief.
- Pas de `git push` sans mon accord explicite au moment voulu (le repo GitHub n'est pas encore créé).
- Ne pas modifier les seuils de `risk_gates.py` (MAX_RISK_PCT_PER_TRADE, WEEKLY_LOSS_LOCK_PCT, TAKE_PROFIT_PCT, STOP_LOSS_PCT) sans en parler d'abord — ce sont des choix déjà réfléchis, pas des valeurs à ajuster pour "voir ce qui se passe".
- Ne touche à aucun autre dossier de CERVEAU pendant cette session.

## En fin de séance

Verdict net : soit "le pipeline tourne de bout en bout contre l'API réelle via le CLI, ordre paper confirmé, id=`<id>`, quantité=`<n>`" soit "bloqué à l'étape X, erreur : `<erreur exacte>`". Précise pour chacun des 3 schemas vérifiés à l'étape 5 s'il correspondait à ce que le code attendait ou s'il a fallu corriger, et quoi exactement. Rapporte le résultat directement à Spap.

---

**Compte paper trading uniquement — zéro fonds réel engagé.**
