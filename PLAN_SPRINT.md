# 🔎 Reconnaissance concurrence (24/08, avant kickoff)

Vérifié directement sur lablab.ai (pages publiques, aucun compte requis) :
- **1 802 inscrits, 442 équipes** en formation sur ce hackathon au moment du contrôle. Un seul track : "Options Alpha Agents".
- Les pages publiques `/alpaca-ai-trading-agents-hackathon/<nom-équipe>` affichent le pitch ("Team Idea") de chaque équipe avant même la soumission finale — c'est une vraie fenêtre légale sur ce que les autres visent, pas une supposition. Équipe "AgentAlpha" trouvée avec un pitch générique : "autonomous AI trading agent that analyzes markets, generates strategies, and executes paper trades" — aucune mention d'options, aucun angle de risque, aucune originalité affichée. Notre propre page (`.../hindsight-alpha`) a déjà un pitch spécifique et déjà en ligne.
- Un hackathon lablab précédent sur le même thème ("AI Trading Agents", mars-avril 2026, sponsor Kraken) a un vrai historique de soumissions terminées. Exemple type (équipe XIV Trading, "AlphaTrader") : ensemble pondéré RSI+Bollinger (50%) / momentum (30%) / retour à la moyenne (20%), vote pondéré, stop-loss -5%/take-profit +10%/perte quotidienne -10%, journal SQLite, dashboard Streamlit, objectif affiché "+15-20% ROI, Sharpe >1.5". C'est le gabarit "compétent standard" auquel on doit se comparer : plusieurs indicateurs classiques combinés + chiffres de performance annoncés avec confiance.

Ce que ça confirme et ce que ça corrige :
- Notre angle (audit de fuite de hindsight sur la sélection de paramètre, pas juste "un signal de plus") est réellement rare dans ce type de soumission — à mettre en avant explicitement dans le write-up et la vidéo, pas en note de bas de page.
- Risque réel identifié : notre honnêteté ("aucune preuve que la thèse gagne, seule la mécanique est vérifiée") peut paraître faible à côté d'un "+15-20% ROI" affiché avec assurance par d'autres équipes, même si ce chiffre-là n'est souvent qu'une estimation non vérifiée. Correctif de présentation : ouvrir sur ce qu'on empêche (un agent qui se trompe lui-même sans le savoir), pas sur ce qu'on ne sait pas — le désaveu honnête reste présent, mais en second plan, pas en titre.

**Complément du 24/08, deuxième passe — taux réel de finition et un concurrent proche de notre angle :**
- Sur le hackathon précédent du même organisateur (même thème, sponsor différent) : **2 752 inscrits, 631 équipes formées, mais seulement 107 soumissions finales** — environ 17% des équipes vont jusqu'au bout. Le nombre "442 équipes" qui semble intimidant sur le hackathon Alpaca ne représente probablement pas 442 concurrents réels au moment du jugement.
- Le classement "vote communautaire" du hackathon précédent n'est pas forcément le classement des gagnants officiels ("Winners announced" existe comme onglet séparé, jamais consulté) — à ne pas confondre les deux si on regarde encore ce hackathon pour s'inspirer.
- Trouvé une soumission avec un angle voisin du nôtre : "TrustTrade AI" (équipe HackGPT, 3e au vote communautaire) — vérification on-chain (ERC-8004) + couche d'explicabilité (raisons "pourquoi/pourquoi pas", scores de confiance) pour rendre chaque décision de trade auditable. Bien reçu par un relecteur ("paradigm shift", "industry-leading"). Différence réelle avec nous : leur "confiance" vient d'un LLM qui explique sa propre décision (donc invérifiable, potentiellement halluciné) ; la nôtre vient d'un test statistique falsifiable (la fenêtre gagnante doit aussi gagner sans les données les plus récentes, sinon refus). À dire explicitement dans le write-up — c'est une vraie distinction, pas juste du vocabulaire différent.
- Le projet le plus voté ("TradeAgents", 38 votes) est techniquement basique (juste une liste de fonctionnalités, pas de détail de stratégie) — le vote communautaire semble récompenser la présentation/vidéo autant que la profondeur technique. Ne pas sous-investir la vidéo et le pitch en pensant que la rigueur du code parle d'elle-même.

**Rentabilité exigée ou juste construire l'agent ?** Cherché dans les pages publiques du hackathon : aucun seuil de rentabilité minimum publié, "P&L Performance" est un des 5 critères nommés sans poids numérique ni plancher trouvé nulle part. Un plancher de rentabilité obligatoire sur une seule semaine de marché serait de toute façon irréaliste à garantir (aléa de marché) — probablement jugé en relatif, pas en pass/fail. Pas une certitude à 100%, à confirmer sur le Discord du hackathon si on veut lever le doute complètement.

**Troisième passe "cherche encore" (24/08) — le guide officiel lablab, pas juste la page de l'event :**
- `lablab.ai/guide/how-to-win-an-ai-hackathon` (guide officiel, générique à tous leurs hackathons) donne un vrai signal concret : **"judges check your repo; an empty repo with one final push raises red flags"** et **"real commits spread across the event window"**. Notre historique actuel = 5 commits, tous faits le 24/08 avant le kickoff. C'est légitime (dev autorisé avant le 28/08), mais il faut continuer à committer réellement pendant la semaine du 28/08 au 04/09 (dashboard quotidien via `--git-push`, résultats du backtest, etc.) — pas juste une rafale avant le début puis plus rien. Déjà prévu à l'étape 10 du plan jour-par-jour, maintenant confirmé par une vraie source, pas une supposition.
- Ce guide donne aussi le rubric générique lablab (Présentation, Business Value, Application de la techno, Originalité) — **différent** des 5 critères propres à CE hackathon (P&L Performance, Technology Implementation, Creativity & Originality, Presentation & Execution, Social engagement). Pas la peine de construire un slide TAM/revenue model — ça ne fait pas partie de ce qui nous juge réellement ici. Le rubric générique sert surtout pour la structure vidéo (démo tôt, problème en 30s) et le rappel "Application of Technology = le repo est réel, la démo est déployée, l'IA fait quelque chose de non-trivial" — déjà couvert par nous.
- Point honnête à ne pas cacher à Spap : le même guide dit que "teams of 3-4 regularly outperform solos in the finals" sur ces événements. On est une équipe solo. Pas un problème qu'on peut corriger maintenant (kickoff dans 4 jours), mais ça justifie de compenser par la rigueur/l'originalité plutôt que par le volume de features.
- Les pages officielles "Hackathon Rule Book" et "Submission Guidelines" (liens directs depuis le guide) ne se sont pas chargées correctement depuis Cowork (rendu vide, probablement une page Notion imbriquée que l'outil de fetch ne sait pas restituer) — **la pondération numérique exacte des 5 critères et un éventuel seuil de rentabilité minimum restent non trouvés**, malgré plusieurs tentatives. Pas grave en soi (aucun hackathon lablab ne semble publier de seuil pass/fail sur le P&L), mais à lever au Discord/kickoff stream du 28/08 si Spap veut une certitude à 100%.
- Recompté : le nombre réel de jours de bourse pendant la semaine du hackathon est petit — kickoff vendredi 28/08 (marché encore ouvert quelques heures), week-end 29-30/08 mort, puis 5 jours pleins (31/08 au 04/09, la deadline du 04/09 tombe avant la clôture du marché ce jour-là). Environ 5-6 jours de bourse réels, pas 7 — un point de contexte honnête à mettre dans le write-up pour cadrer les attentes sur un seul P&L hebdomadaire forcément bruité.

**Quatrième passe "cherche encore" (24/08) — un concurrent réel du hackathon précédent, très proche de notre angle, avec un résultat live honnêtement publié :**
- Trouvé sur GitHub (`JudyaiLab/hackathon-trading-agent`, hackathon Kraken précédent) : un agent avec validation "Walk-Forward Optimization" (8 fenêtres glissantes, in-sample 90j/out-of-sample 30j, critère de passage : taux de réussite OOS ≥ 65%, écart IS-OOS < 15%) — **82,2% de taux de réussite en backtest out-of-sample**. Méthodologiquement proche de nous dans l'esprit (se protéger d'un résultat qui ne tient que grâce aux données d'entraînement), mais implémenté différemment : eux valident une fois à la conception (rolling windows historiques), nous on revérifie à **chaque décision de trade en live**, pas juste une fois au design — vraie différence à expliciter dans le write-up, pas juste du vocabulaire voisin.
- **Le plus utile pour nous** : leur résultat live pendant la semaine réelle du hackathon a été 40% de réussite et un P&L négatif (-376,91 $ sur 24 trades), très loin du 82,2% de backtest — à cause d'un régime de marché différent (marché plat/choppy) pendant leur semaine de hackathon vs. leurs fenêtres d'entraînement. Le drawdown est resté contenu à -0,4% grâce à leur système de risque à 7 couches. Ils l'ont publié honnêtement (tableau backtest vs live côte à côte) plutôt que de le cacher, et ont recadré leur pitch sur "la préservation du capital compte plus que le taux de réussite brut".
- Ce que ça confirme pour nous, concrètement : **même une validation rigoureuse ne protège pas contre un résultat décevant sur une seule semaine réelle** — le régime de marché pendant le 28/08-04/09 est un facteur qu'aucune rigueur de conception ne contrôle. Notre discours doit déjà intégrer ça (pas une découverte de dernière minute, cohérent avec notre honnêteté déjà affichée), et si notre P&L live déçoit aussi, le bon réflexe — déjà dans notre philosophie, maintenant confirmé par un vrai précédent — est de mettre en avant ce que les garde-fous (`risk_gates.py`) ont empêché, pas de cacher le chiffre brut.

**Cinquième passe "cherche encore" (24/08) — un vrai bug de code trouvé et corrigé, pas juste de la recherche externe :**

Relu `risk_gates.py` ligne par ligne en pensant spécifiquement au changement de compte prévu au kickoff (dev → compte dédié `.env.hackathon`). Trouvé : `state.json` n'a jamais été conscient de *quel compte* il décrit — juste `starting_equity` et `locked`, aucun `account_id`. Si `state.json` n'est pas effacé manuellement au moment exact du changement de compte, le verrou de -3% (ou le calcul de drawdown) du compte de **dev** continue de s'appliquer tel quel au compte **dédié** — deux soldes complètement différents comparés entre eux. Testé pour de vrai (pas juste raisonné) : sans le correctif, un compte dédié fraîchement démarré à 100 000 $ héritait du verrou déclenché la veille sur le compte de dev à 50 000 $, et refusait de trader dès le premier run réel, silencieusement.

**Corrigé** : `_record_starting_equity` compare maintenant `account_id` (lu depuis `alpaca account get`) à celui déjà enregistré dans `state.json`. Si ça ne correspond pas (ou rien n'est encore enregistré), l'équité de départ et le verrou sont réinitialisés automatiquement — plus besoin de se souvenir de vider `state.json` à la main au bon moment le 28/08. Revérifié avec un test qui simule exactement ce scénario (dev verrouillé à -4%, puis bascule vers le compte dédié) : `state after switching accounts: {'account_id': 'PA3K8MP3MF0U', 'starting_equity': 100000.0, 'locked': False, ...}` — le compte dédié démarre bien propre.

**Sixième passe "cherche encore" (24/08) — deux identifiants de compte différents chez Alpaca, on n'affichait pas le bon :**

Vérifié dans la doc Alpaca : `GET /v2/account` renvoie **deux champs différents** pour "identifier ce compte" — `id` (un UUID interne, ex. `523f7f05-1d67-4219-a96e-e65276f1dcf3`, déjà vu dans notre `data.json`) et `account_number` (le numéro visible côté utilisateur, format `PA...`, ex. `PA3K8MP3MF0U` — exactement ce qui est déjà dans `.env.hackathon`). Le champ "Alpaca account ID" demandé par le formulaire de soumission du hackathon est presque certainement le second (le seul qu'un juge peut visuellement croiser), pas le premier.

Or `publish_dashboard.py` ne capturait que `id` (l'UUID) dans `docs/data.json`, et la carte "Account ID" qu'on venait d'ajouter au dashboard (passe précédente) l'aurait donc affiché sous une forme différente de celle déclarée dans le formulaire de soumission — rendant le contrôle croisé qu'on venait d'ajouter confus au lieu de rassurant. Corrigé : `publish_dashboard.py` capture maintenant aussi `account_number`, et le dashboard l'affiche en priorité (repli sur `id` si absent). **Non vérifié contre le vrai CLI** — à confirmer à la prochaine session terminal que `alpaca account get --quiet` renvoie bien un champ `account_number` (probable, vu que le CLI reprend systématiquement les noms de champs de l'API REST partout ailleurs, mais jamais testé directement pour celui-ci).

**Septième passe "cherche encore" (24/08) — même confusion id/account_number, trouvée une deuxième fois dans un fichier jamais relu ce soir-là :**

Fichiers jamais relus cette session (`config.py`, `decision_log.py`, `.env.example`, `requirements.txt`, `test_connection.py`) passés en revue pour de vrai, pas juste supposés bons parce que déjà écrits. `test_connection.py` comparait `config.ACCOUNT_ID` (le `PA...` de `.env.hackathon`, format `account_number`) contre `account.get("id")` (l'UUID interne) — exactement la même confusion trouvée juste avant dans `publish_dashboard.py`, mais cette fois dans le tout premier script que la session terminal doit lancer. Comme les deux formats ne peuvent jamais être égaux par construction, ce script aurait affiché un faux "WARNING: ne correspond pas" à **chaque run correctement configuré**, y compris le premier test avec le compte dédié le 28/08 — un signal d'alarme trompeur au pire moment. Corrigé pour comparer contre `account_number`, avec repli honnête si ce champ est absent de la sortie CLI (plutôt que de fausse alerte). `config.py`, `decision_log.py`, `.env.example`, `requirements.txt` relus, rien trouvé d'autre.

**Backtest réel lancé** : `backtest.py` créé — rejoue la stratégie HV-rank du projet (pas une réimplémentation séparée) contre l'historique réel de prix via `alpaca_cli`, calcule le payoff proxy cumulé, le taux de succès sur les jours tradés, le max drawdown, et rejoue le verdict `hindsight_guard` pour chaque symbole. Testé mécaniquement en local avec des données synthétiques (aucune fuite, pas de crash) — **jamais lancé contre les vraies données**, bloqué par le même mur réseau que d'habitude (essayé stooq.com et Yahoo Finance directement depuis Cowork en plus d'Alpaca : les trois bloqués). À lancer en terminal réel — voir `BRIEF_BACKTEST_REEL.md`. Rappel important déjà écrit dans le script : le payoff calculé est un proxy (abs du rendement du lendemain moins un coût lié au niveau de vol), pas une vraie simulation de prime d'option — à ne jamais présenter comme un vrai P&L sans cette nuance.

---

# 🔗 URLS DE SOUMISSION — requises par le formulaire du hackathon

| champ du formulaire | valeur |
|---|---|
| **Public GitHub repository** | **https://github.com/s-papy/hindsight-alpha** |
| **Application URL** | **https://s-papy.github.io/hindsight-alpha/** |

*Dépôt créé et poussé le 24/08/2026. Visibilité **PUBLIC** vérifiée par l'API. Licence détectée par GitHub : **MIT** (exigence « Submissions must be original and MIT-compliant »). Pages servi depuis `main` → `/docs`, statut `built`, HTTP 200 sur la page ET sur `data.json`.*

*Vérification visuelle réelle sur l'URL publique : les 3 sections s'affichent, **zéro message console**, et les chiffres correspondent exactement au `data.json` servi (equity 99 875,90 · 0 position → « No open positions right now. » · 1 décision « dry-run: would trade », SPY bearish (put), verdicts SPY/QQQ/IWM).*

🔴 **Reste à faire pour la soumission : rebrancher le compte dédié.** Tout ce qui précède tourne sur le compte de DEV (`.env`). Le compte de soumission (`.env.hackathon`) n'a **toujours jamais été touché** — à activer au kickoff du 28/08, pas avant.

---

# Plan de sprint — Hindsight Alpha (Alpaca AI Trading Agents Hackathon)

*Rédigé le 24/08/2026. Kickoff : ven 28/08 15:00 UTC (17:00 CEST). Fin des soumissions : ven 04/09 15:00 UTC (17:00 CEST). Déjà fait : équipe créée, enregistrement confirmé ("Enrolled"), Discord rejoint.*

## Ce que la page officielle exige, en un coup d'œil

- Agent autonome utilisant le Trading API **et** (MCP server **ou** CLI) — un seul des deux suffit, mais un des deux est obligatoire.
- Stratégie qui inclut du trading d'options.
- Compte paper **neuf, jamais réutilisé**, dédié à cette soumission, soldé à 100 000 $.
- Le P&L jugé porte sur l'activité réelle du compte pendant la semaine du hackathon — pas une démo ponctuelle.
- Soumission : dépôt GitHub public + appli hébergée avec URL publique + ID du compte Alpaca + vidéo + deck de slides + write-up d'une page (logique IA, garde-fous de risque, implémentation infra).
- Bonus optionnel : jusqu'à 5 posts X/LinkedIn taguant @lablabai et @AlpacaHQ.

## Réalisme du calendrier

Le vrai obstacle n'est pas le code (déjà en grande partie écrit et testé hors-ligne) — c'est le fait que le P&L jugé demande que l'agent **tourne pendant 7 jours d'affilée** sans supervision constante, et qu'il faut une **appli hébergée** avec une URL publique. Les deux sont faisables dans le temps disponible, mais aucun des deux n'est instantané. Verdict honnête : tenable si on avance dès maintenant sur ce qui ne dépend pas du kickoff, pas tenable si on attend le 28 pour commencer.

## Jour par jour

**Aujourd'hui → 27/08 (avant le kickoff) — tout ce qui ne dépend pas du compte officiel**
0. ~~Construire le tableau de bord hébergé~~ **Fait (code)** — `docs/index.html` (page statique, aucune dépendance externe) + `publish_dashboard.py` (génère `docs/data.json` depuis le compte réel + `decision_log.jsonl`) + `decision_log.py` (journal des décisions de chaque run, maintenant câblé dans `agent.py`). Choix d'hébergement : GitHub Pages sur ce même dépôt (`docs/`), même schéma que le tableau de bord D31 de SNIPER — la page publique ne voit jamais les clés API, seulement un instantané JSON régénéré localement. Vérifié sans navigateur réel (le bac à sable ne peut pas ouvrir de fichier local dans Chrome) : HTML bien formé, JS syntaxiquement valide, chaque champ lu par le JS confirmé correspondre exactement à ce que `publish_dashboard.py`/`agent.py` produisent réellement. **Reste à faire en terminal réel** : premier `python publish_dashboard.py`, activer GitHub Pages sur `/docs`, et un coup d'œil visuel avant la vidéo de démo.
1. ~~Corriger le code : brancher le CLI Alpaca~~ **Fait** — `alpaca_cli.py` remplace l'appel direct au SDK `alpaca-py`, `hindsight_guard` + `vol_strategy` intacts. Reste incertain et à vérifier en terminal réel (voir `BRIEF_TEST_AGENT_TERMINAL.md`) : la forme exacte du JSON retourné par `alpaca data bars` — codée défensivement contre les deux formes connues de l'API REST, mais jamais testée contre le vrai binaire (pas installable dans le bac à sable Cowork).
2. Construire l'appli hébergée : un tableau de bord web minimal (sweep du jour, verdict hindsight_guard, dernier trade, P&L cumulé lu en direct depuis le compte Alpaca) — c'est aussi ce qu'on montrera dans la vidéo.
3. Décider où ça tourne pendant la semaine (ton Mac avec une tâche planifiée, ou un hébergeur gratuit type Render/Railway/Fly.io — l'appli hébergée doit de toute façon vivre quelque part avec une URL publique, donc ce choix répond aux deux besoins à la fois).
4. Tester tout le pipeline de bout en bout contre le compte de test déjà créé (autorisé pendant le développement — la page le dit explicitement : "Use any paper account you like during development").
5. Préparer les brouillons : script de vidéo, structure du deck, structure du write-up d'une page — contenu à finaliser une fois qu'il y a du vrai P&L à montrer.

**28/08, kickoff (17:00 CEST)**
6. Suivre le kickoff pour d'éventuelles précisions de dernière minute sur les règles.
7. Créer le compte Alpaca **neuf et dédié**, solde à 100 000 $ (voir choix à trancher juste après ce plan).
8. Brancher l'agent corrigé sur ce nouveau compte, vérifier qu'il tourne, démarrer le programme (planifié quotidien, ou en continu selon ce qui est choisi à l'étape 3).

**29/08 → 03/08 (en réalité 29/08 → 03/09) — la semaine de trading**
9. Laisser l'agent tourner et trader selon son cycle. Vérifier chaque jour que le check `hindsight_guard` s'exécute correctement et que le tableau de bord reflète l'activité réelle.
10. Publier au fil de l'eau sur X/LinkedIn (jusqu'à 5 posts, piste bonus) — montrer le raisonnement, pas juste le résultat.
11. Ajuster si quelque chose casse (contrat introuvable, ordre rejeté, etc.) — journaliser chaque incident, ça nourrit le write-up et la vidéo ("comment l'agent gère l'imprévu" est un bon angle de présentation).

**03/09 → 04/09, 17:00 CEST — finalisation**
12. Arrêter l'agent, figer le P&L final.
13. Enregistrer la vidéo de démo (agent en action + explication du raisonnement hindsight_guard).
14. Finaliser le deck de slides et le write-up d'une page.
15. Nettoyer et pousser le dépôt GitHub public (README à jour, `.env` bien exclu).
16. Soumettre : dépôt, URL de l'appli, ID du compte Alpaca, vidéo, deck, write-up, liens des posts sociaux.

## Piste déposée, pas maintenant : TradingView comme confirmation secondaire

Spap a un vrai accès TradingView (BeeHive) et il existe des ponts MCP communautaires (`tradingview-mcp`, ~3500 étoiles GitHub, aucun n'est officiel). Avantage réel possible côté critère "originalité" — personne d'autre au hackathon n'aura cette expérience Pine Script en plus. Risques réels aussi : outil tiers non audité, temps qui manque déjà pour le cœur du pipeline. Décidé le 24/08 : on ne touche pas à ça avant que le CLI soit vérifié en vrai et que le tableau de bord tourne. Si le temps le permet après le 28, ajouter en confirmation secondaire *optionnelle* — jamais un point de défaillance dur pour la décision de trade.

## Angle mort corrigé le 24/08 : risque de semaine à zéro trade, et le fuseau horaire

Avec trois refus indépendants empilés (fuite hindsight_guard, régime de volatilité, garde-fous de risque) sur un seul symbole plutôt calme (SPY), il était tout à fait possible que l'agent ne trade jamais de toute la semaine — honnête, mais un des 5 critères de jugement est "P&L Performance", et un agent muet n'a rien à montrer là-dessus ni dans la vidéo. Corrigé : l'agent évalue maintenant un petit univers (`SPY,QQQ,IWM` par défaut, `--symbols` pour changer) et trade le premier qui passe tous les gates — même logique honnête, juste appliquée plusieurs fois. Testé hors-ligne avec des régimes de volatilité différents par symbole : fonctionne (le bon symbole est retenu, les autres refusés avec la vraie raison affichée).

**Fuseau horaire, à ne pas oublier au moment de planifier le job quotidien** : les marchés US ouvrent 9h30-16h00 heure de New York, soit **15h30-22h00 heure suisse (CEST)**. Un job planifié le matin côté Suisse tombera systématiquement sur "marché fermé" (l'agent le détecte et sort proprement, mais ne fera jamais rien). Prévoir de lancer le job en fin d'après-midi/soirée suisse, par exemple vers 16h00-17h00 CEST.

## Bug réel trouvé et corrigé le 24/08 : le sweep affamait 3 candidats sur 5

Avec le réglage d'historique par défaut (≈250 jours de bourse), les fenêtres 60 et 90 jours du sweep `hindsight_guard` recevaient **zéro échantillon exploitable** (vérifié par calcul, pas supposé), et la fenêtre 30 jours seulement 8 points — contre 18-28 pour les fenêtres 10 et 20. Le sweep "sur 5 candidats" n'en comparait donc réellement que 2, silencieusement. Corrigé : l'historique récupéré par défaut passe à ~600 jours de bourse (`vol_strategy.MIN_TRADING_DAYS_FOR_SWEEP`, calculé à partir des vrais besoins du calcul — pas un chiffre rond arbitraire comme l'ancien 250). Revérifié par simulation : les 5 fenêtres reçoivent maintenant chacune plusieurs centaines de points, le pipeline complet tourne correctement de bout en bout.

## Angle mort corrigé le 24/08 : aucune sortie de position

Les garde-fous ajoutés plus tôt ne couvraient que l'entrée (position déjà ouverte, plafond par trade, verrou hebdo) — rien ne fermait jamais une position une fois ouverte. Sur 7 jours avec des échéances à 7-21 jours, tout serait resté en P&L latent jusqu'à la fin du jugement, et le write-up doit couvrir les "risk gates" en entier, pas juste la moitié. Ajouté : `risk_gates.manage_exits()`, appelé en tout premier à chaque run (avant même d'évaluer une nouvelle entrée) — ferme la position à +50% (prise de profit) ou -50% (coupe la perte) sur le P&L latent en % de la prime payée. Testé hors-ligne avec des positions simulées : prend la bonne décision dans les 3 cas (ferme sur profit, ferme sur perte, garde si entre les deux), et le mode `--dry-run` rapporte sans jamais fermer réellement.

## Deux derniers points corrigés le 24/08

- **Licence manquante** — la page de règles exige explicitement "Submissions must be original and MIT-compliant". `hindsight-guard` avait déjà sa licence MIT, `hindsight-alpha` n'en avait aucune (donc "tous droits réservés" par défaut, non conforme). Ajouté : `LICENSE` (MIT, même modèle).
- **Flag `--quiet` jamais utilisé dans `alpaca_cli.py`** — le CLI est documenté "Alpha Preview", donc susceptible d'imprimer un bandeau ou un message avant le JSON attendu. Sans `--quiet` (flag réel et documenté, "suppress non-essential output"), n'importe quel texte en plus aurait cassé le parsing JSON de chaque appel. Corrigé : `run()` l'ajoute désormais systématiquement, vérifié par test.

## Double contrôle du 24/08 : pipeline complet rejoué en une fois

Test de bout en bout (clôture de position + sweep multi-symboles + garde-fous + ordre) avec toutes les corrections de la journée combinées. Résultat correct dans l'ensemble, un point réel identifié : juste après que `manage_exits()` ferme une position gagnante, le check "position déjà ouverte" peut encore la voir comme ouverte le temps que l'ordre de clôture se remplisse côté Alpaca — l'agent refuse alors une nouvelle entrée ce jour-là. Vérifié que c'est un échec du bon côté (abstention plutôt qu'empilement de positions), cohérent avec la philosophie du projet. Pas de correctif nécessaire, juste à savoir.

Confirmé avec `git check-ignore` (l'outil réel) : `.env`, `.env.hackathon`, `state.json` bien exclus, `.env.example` bien suivi. Confirmé qu'aucun import actif ne pointe vers le code mort (`alpaca_client.py`, `momentum_strategy.py`) — seules des mentions en commentaire, volontaires.

## 🟢 24/08 — session terminal n°2 : nettoyage git + dashboard vérifié visuellement

**Fait et vérifié :**
- `test-gitignore-check/` **supprimé** (ne contenait que son `.git`, zéro fichier utile).
- `.git` **reconstruit propre** sur `main` (l'ancien avait `index.lock`, `th02JRu`, 10 `tmp_obj_*`, zéro commit). `fsck` clean.
- **Secrets vérifiés AVANT le premier commit** : `git check-ignore -v` confirme `.env` (règle `.env`), `.env.hackathon` (règle `.env.*`), `state.json` — les trois ignorés ; `.env.example` bien suivable et **vérifié sans vraie clé** (placeholders `your_..._here`, et différent du vrai `.env`). Scan du contenu de tout l'historique : **0 occurrence** de clé.
- `.DS_Store` retiré de l'index et ajouté au `.gitignore` (il partait dans un dépôt public).
- Commits : `68c778d` (initial, 21 fichiers) puis `c7f1376` (fix close + snapshot réel).
- **Dashboard vérifié VISUELLEMENT pour la première fois** (serveur local + navigateur) : les 3 sections s'affichent, **zéro erreur console**, chiffres conformes à `docs/data.json` (equity 99 887,95 · 1 position · 1 décision). Le `PLACEHOLDER` fictif a disparu.
- `decision_log.jsonl` **créé au premier run** — il était vide simplement parce qu'`agent.py` n'avait plus tourné depuis le câblage de `decision_log`.

**🔴 5ᵉ écart code/API trouvé — le plus grave, dans le système de risque :**
`alpaca position close --symbol` → `unknown flag`. La vraie signature est **`--symbol-or-asset-id`**. **`manage_exits()` aurait donc levé une exception à CHAQUE take-profit ou stop-loss réel** — la branche que les mocks ne pouvaient pas attraper. Corrigé et **prouvé en direct** : position `SPY260831P00763000` réellement fermée (ordre `37275e32-6dc4-4b98-9b0a-28ab60289d39`, sell 2), positions à 0. Les deux branches de `manage_exits()` ont désormais une confirmation live.

**🔴 BLOQUÉ — ne dépend pas de moi :** dépôt GitHub, push et Pages (étapes 5, 7, 8) sont impossibles depuis ce Mac : **aucune authentification GitHub n'existe** (ni `gh`, ni token, ni clé SSH, ni credential helper, ni trousseau). Le commit est prêt et propre ; il attend une voie d'authentification décidée par Spap.

## 🟢 24/08 — Premier test réel réussi (session terminal, compte de dev)

Pipeline complet vérifié de bout en bout contre l'API Alpaca réelle via le CLI officiel (installé depuis le binaire GitHub `alpacahq/cli` v0.0.13, empreinte SHA-256 vérifiée — ni `brew` ni `go` n'étaient disponibles sur ce Mac). Ordre paper confirmé : `id=e896888f-7c58-418a-aefc-3d5034cfaef9`, 2 puts `SPY260831P00763000` à 4,88 $, coût 976 $ sous le plafond de 1 000 $.

Quatre écarts entre le code écrit hors-ligne et la réalité, tous corrigés :
1. `data bars` — conforme au premier essai, rien à corriger. Confirme au passage que le plan gratuit Alpaca rend bien assez d'historique (657 barres pour 592 exigées).
2. `position list` — noms de champs corrects mais tous les champs numériques sont typés **string** par le CLI, pas number. Le check `isinstance(plpc, (int, float))` ne pouvait jamais matcher — ça marchait par accident via le repli de calcul. Corrigé pour accepter aussi la forme chaîne.
3. `data option snapshot` — flag `--symbols` (pluriel), pas `--symbol` ; la forme singulière échouait silencieusement (erreur en JSON valide). Et le vrai chemin du prix ask est `latestQuote.ap` — la seule combinaison absente de la liste de repli. Corrigés.
4. **Le plus grave, jamais anticipé** : `/v2/options/contracts` pagine à 100 résultats triés par strike croissant. Sans borne, la première page pour SPY revenait en strikes 420-675 alors que le spot était à 763 — le spot n'était même pas dans la page reçue. Le code prenait donc la strike la plus proche *disponible dans la page*, 88 points dans la monnaie, prime ~8 926 $. Avec le plafond de 1% (1 000 $), ça donne qty=0 — **l'agent aurait refusé de trader indéfiniment, en donnant l'impression de fonctionner**. Corrigé en bornant la recherche à ±5% du spot (`alpaca_cli.STRIKE_BAND_PCT`).

Ce dernier point est exactement le genre d'échec que ce projet existe pour attraper ailleurs — un mécanisme qui a l'air de marcher (aucune erreur, aucun crash) mais qui ne fait pas ce qu'il prétend faire. Il a fallu de vraies données pour le voir ; invisible avec des mocks.

## Passe du 24/08 après le test réel : un point écarté, un confirmé, un vraiment ouvert

- Écarté : une option achetée le jour du kickoff (7 jours min) pourrait expirer pile le jour de la deadline (04/09) — vérifié que la deadline (15h00 UTC = 11h00 ET) tombe avant la clôture du marché ce jour-là (~16h00 ET), donc la position serait encore ouverte, pas réglée, au moment de la soumission. Pas un problème.
- Confirmé : le dimensionnement recalculé à la main sur les vrais chiffres du trade (ask 4,88 $, plafond 1 000 $) retombe exactement sur qty=2, coût 976 $ — la logique de sizing est juste en pratique, pas seulement en simulation.
- **Encore ouvert** : `alpaca position close` (la fermeture réelle d'une position à ±50%) n'a jamais été exercée contre l'API réelle — la position de test n'a jamais franchi ce seuil (plpc lu à -1,64%, dans la fourchette). Seule la branche "garder" a une confirmation live ; la branche "fermer" ne repose encore que sur des mocks. À vérifier dans une prochaine session terminal — éventuellement en fermant la position de test manuellement pour confirmer que l'appel CLI et sa réponse ont la forme attendue.

## Choix à trancher avant le 28 : où l'agent tourne pendant la semaine

- **Ton Mac, tâche planifiée locale** — gratuit, simple, mais le Mac doit rester allumé et connecté tous les jours de la semaine du hackathon.
- **Hébergeur gratuit (Render/Railway/Fly.io)** — tourne sans dépendre de ton Mac, héberge aussi le tableau de bord (répond aux deux exigences en un seul endroit), mais demande un peu de configuration en plus.

On tranchera ça au moment de construire le tableau de bord (étape 2), pas maintenant.

## Pourquoi CLI plutôt que MCP server pour satisfaire l'exigence technique

La doc Alpaca elle-même le dit sur la page du hackathon : *"Alpaca CLI — the same trading functions from a terminal command, with structured JSON output. Built for long-running agent sessions, cron jobs and CI, where MCP is heavier than needed."* Le MCP server est pensé pour qu'un assistant IA interactif (Claude Desktop, Cursor) discute avec Alpaca pendant qu'un humain pilote — pas pour un agent autonome qui tourne seul sur un calendrier pendant 7 jours. Le CLI colle exactement à notre cas d'usage, et Alpaca le dit noir sur blanc.
