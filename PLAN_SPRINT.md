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

**Huitième passe "cherche encore" (24/08) — une affirmation technique du projet était trop absolue, corrigée avant qu'un juge ne la reprenne :**

Vérifié directement dans la doc Alpaca (`docs.alpaca.markets/us/docs/historical-option-data`), pas supposé : Alpaca **offre bien des données historiques d'options** (bars/trades/quotes) depuis février 2024 — `vol_strategy.py` disait auparavant que les barres actions étaient "the same reliable, historically-available data source used everywhere else", ce qui laissait entendre qu'aucune donnée d'options historique n'existait du tout. C'est faux. Ce qui reste vrai (et c'était déjà bien écrit) : l'**IV historique** (volatilité implicite calculée) n'est pas un champ servi directement — il faudrait la reconstruire soi-même depuis des prix d'options historiques via un modèle. Deux vraies limites sur ces données d'options, pas des raisons de les ignorer : seulement ~2,5 ans d'historique (depuis février 2024, contre plusieurs années pour les actions), et le flux gratuit "Indicative" n'est pas le vrai OPRA consolidé (dérivé, trades retardés de 15 min — le vrai OPRA est payant).

Corrigé dans `vol_strategy.py` : le proxy stock-only reste le choix fait, mais documenté maintenant comme un vrai compromis (portée d'historique, simplicité) plutôt que comme la seule option possible. Un backtest plus rigoureux basé sur les vrais prix d'options historiques (au lieu du proxy) est un axe légitime pour après le hackathon, pas un oubli par ignorance — à formuler ainsi dans le write-up, pas "la donnée n'existe pas". Pourquoi ça compte : notre argument central au jugement est l'honnêteté technique — une affirmation trop absolue, relevée par un juge qui connaît bien l'API Alpaca (pas improbable, Alpaca est cosponsor), aurait fait plus de mal à la crédibilité du projet que n'importe quel autre bug trouvé ce soir.

**Neuvième passe "cherche encore" (24/08) — le compte dédié aura-t-il vraiment les options activées, et un risque opérationnel trouvé sur le forum Alpaca :**

Bonne nouvelle vérifiée dans la doc officielle : en environnement paper, le trading d'options est **activé par défaut au niveau 3** (le plus haut, spreads inclus) — "there's nothing you need to do". Pas d'étape d'activation manquée pour le compte dédié créé le 24/08, contrairement à ce qu'on aurait pu craindre.

Mais en cherchant plus loin (forum communautaire Alpaca, pas juste la doc), trouvé un fil très récent (**30 juillet 2026**, moins d'un mois avant notre kickoff) où plusieurs utilisateurs rapportent perdre l'accès aux options **sur un compte paper qui tradait des options la veille sans problème** — un membre de l'équipe Alpaca répond activement dessus, donc un problème connu/suivi, pas ignoré, mais pas non plus totalement résolu au moment du fil. Pas un bug de notre code — rien à corriger — mais un vrai risque opérationnel à connaître : si `order submit` échoue pendant la semaine du hackathon avec une erreur d'autorisation, ne pas supposer automatiquement une régression du code avant d'avoir vérifié le statut du compte sur le tableau de bord Alpaca et le forum communautaire.

**Backtest réel lancé** : `backtest.py` créé — rejoue la stratégie HV-rank du projet (pas une réimplémentation séparée) contre l'historique réel de prix via `alpaca_cli`, calcule le payoff proxy cumulé, le taux de succès sur les jours tradés, le max drawdown, et rejoue le verdict `hindsight_guard` pour chaque symbole. Testé mécaniquement en local avec des données synthétiques (aucune fuite, pas de crash) — **jamais lancé contre les vraies données**, bloqué par le même mur réseau que d'habitude (essayé stooq.com et Yahoo Finance directement depuis Cowork en plus d'Alpaca : les trois bloqués). À lancer en terminal réel — voir `BRIEF_BACKTEST_REEL.md`. Rappel important déjà écrit dans le script : le payoff calculé est un proxy (abs du rendement du lendemain moins un coût lié au niveau de vol), pas une vraie simulation de prime d'option — à ne jamais présenter comme un vrai P&L sans cette nuance.

---

## 🟢 24/08 (nuit, 5e « cherche encore ») — l'arithmétique des décisions : AUCUN bug, et un faux positif évité de justesse

**Zone jamais auditée jusqu'ici, et la plus lourde de conséquences : les maths qui décident les trades** (`vol_strategy.py`). Un décalage d'indice y serait du look-ahead — dans un projet dont c'est précisément le sujet.

**Résultat honnête : aucun bug.** Mais la vérification valait d'être faite, et elle a failli produire une fausse alerte publique.

### Ce que j'ai cru trouver, et pourquoi c'était faux

`hv[k]` est calculé sur `returns[k : window+k]`, donc son **dernier rendement observé est `returns[window+k-1]`**. Le « lendemain » naturel serait `returns[window+k]`. Or le backtest consomme **`returns[window+k+1]`** — un jour est sauté. J'allais conclure : *« le backtest mesure une règle différente de celle que l'agent trade »* — une affirmation grave, sur des chiffres déjà **publics** (`BACKTEST_RESULTS.md`, `STRATEGY_COMPARISON.md`).

**Vérifié numériquement plutôt qu'algébriquement : c'était faux.** `_hv_series` n'utilise **jamais** le dernier rendement, donc le chemin EN DIRECT porte exactement le même retard : `today_regime` décide sur `hv[-1]` (dernière info `returns[-2]`) et achète pour capter le mouvement suivant — **saut de 1 jour, des deux côtés, mesuré côte à côte**. Le backtest modélise donc fidèlement la règle vécue, staleness comprise. **Les chiffres publiés tiennent.**

### Ce qui reste vrai et méritait d'être écrit

L'estimation de volatilité est **stale d'un jour par construction**, en direct comme en backtest. Ce n'est pas un défaut (aucune information future n'entre dans la décision, et la correspondance est exacte) mais c'était **totalement non documenté** — et une « correction » future de `_hv_series` en `range(window, len(returns)+1)` casserait la correspondance **d'un seul côté**, avec des chiffres qui resteraient plausibles. **Invariant désormais écrit dans le code**, avec la façon de le revérifier.

**Deux autres points vérifiés, cohérents** : la fenêtre d'historique du rang est la même tranche des deux côtés ; `_percentile_rank` utilise `<=`, ce qui gonfle légèrement le rang et produit donc **moins** de trades — conservateur, pas un biais favorable.

---

## 🔴 24/08 (nuit, 4e « cherche encore ») — la piste que la passe précédente avait nommée

**Cette passe a suivi la piste écrite en clair à la fin de la précédente** (« le prochain endroit où regarder, c'est le `finally` d'`agent.py` : que se passe-t-il si `log_run` échoue après un ordre réellement passé ? »). Elle était juste.

### ⑧ Un ordre passé pouvait ne laisser AUCUNE trace dans le journal de décision

`main()` appelle `decision_log.log_run(record)` dans un `finally`, sans protection. **Mesuré :** ordre réellement soumis + `log_run` qui échoue → **le run entier sort en erreur et `decision_log.jsonl` ne reçoit rien**. L'ordre existe chez Alpaca ; le journal de l'agent, et donc le dashboard public, n'en ont aucune trace.

*Atténuation partielle qui existait déjà* : `record_order_submitted()` écrit `state.json` de façon synchrone juste après la soumission (isolé plus tôt dans la journée), donc `traded_today` garde le symbole. La trace n'est pas nulle — mais elle est absente de là où un juge regarde.

**🔴 Et une correction de ma propre analyse, faite en cours de route.** J'avais d'abord conclu qu'une vraie panne d'`_run` était **perdue** quand `log_run` échouait aussi. **C'était faux** : l'erreur d'origine est bien conservée dans `__context__`. Le premier test le montrait « perdue » à cause de **la façon dont MON test levait l'exception** (`(_ for _ in ()).throw(...)` dans une lambda), pas à cause du code. Refait avec une vraie fonction : la chaîne Python est intacte. **Le défaut réel est donc plus étroit que je ne l'ai cru une minute : masquage cosmétique, pas perte de données.** Écrit ici parce qu'une analyse corrigée en silence ne vaut rien.

**Corrigé, dans `agent.py` ET `monitor_exits.py`** : le `log_run` du `finally` est enveloppé ; en cas d'échec, un avertissement s'affiche **et le record complet est dompé en JSON sur stdout** — donc la trace survit là où va stdout (log launchd, terminal, CI) au lieu de nulle part. Et comme le `finally` ne relève plus, **une vraie panne d'`_run` remonte désormais telle quelle** au lieu d'être déplacée par l'erreur de journalisation. Vérifié sur les trois cas, plus le témoin.

---

## 🔴 24/08 (nuit, 3e « cherche encore ») — la chasse au MOTIF, plutôt qu'aux bugs isolés

**Point de départ : les trois bugs de la passe précédente étaient du même genre — *une action réelle dont la trace se perd parce que la comptabilité qui la suit échoue*. Trois occurrences, ce n'est plus une coïncidence.** Cette passe recense donc systématiquement tout ce qui produit un effet irréversible (ordre soumis, position fermée, fichier écrit) et vérifie, pour chacun, si sa trace peut disparaître. **Le motif a livré un quatrième bug.**

### ⑦ Un échec de fermeture n'était PAS journalisé — le pire événement possible, silencieux

`monitor_exits.py` décidait quoi journaliser en cherchant les chaînes `"CLOSED"` / `"WOULD CLOSE"` dans les lignes rendues par `manage_exits()`. **Mais `manage_exits()` produit aussi deux lignes d'ÉCHEC qui ne contiennent ni l'une ni l'autre :**

    <sym>: ERROR managing this position (...) -- left open, check manually
    <sym>: could not read unrealized P&L% -- leaving position open

et dans les deux cas `record["outcome"]` vaut `"checked"`, pas `"error"` — parce que `manage_exits` rattrape les exceptions par position **à dessein**, pour qu'une position défaillante n'en bloque pas d'autres.

**Reproduit :** une position ayant touché son stop-loss et **n'ayant pas pu être fermée** était classée non-événement, **rien n'était écrit dans `decision_log.jsonl`**, et le programme affichait *« nothing closed »* — activement faux. Sous launchd cet affichage part dans `monitor_exits.log`, ignoré par git et jamais lu. **Un agent sans surveillance pouvait donc laisser une position perdante ouverte indéfiniment, sans aucune trace durable ni rien sur le dashboard public.** L'événement le plus important que ce script existe pour attraper était précisément celui sur lequel il se taisait.

**Corrigé en INVERSANT le test** : on identifie désormais la seule ligne réellement routinière (`": holding ("`) et **tout le reste est journalisé par défaut**. Une chaîne d'action ajoutée plus tard à `manage_exits()` sera tracée sauf classement délibéré en routine — au lieu d'être silencieusement perdue faute de figurer dans une liste blanche que personne n'a pensé à mettre à jour. **9 cas de test, dont les mélanges** (une gardée + un échec → journalisé ; deux gardées → non).

### Tracé et ÉCARTÉ, sans correctif inutile

- **`publish_dashboard.py` écrit `docs/data.json` avec `write_text` non atomique** — même forme que ④, mais l'exposition est bien moindre : le script **n'est pas planifié** (seul `monitor_exits` l'est), écriture et commit sont dans le même processus, et le run suivant réécrit le fichier. **Signalé, pas corrigé.**
- **« commit réussi, push échoué »** dans `git_publish()` : semble laisser un commit orphelin jamais poussé. **Vérifié : se rattrape tout seul** — `generated_at` change à chaque run, donc le run suivant recommite et `git push` envoie aussi le commit précédent. **Pas un bug.**
- **`git add` avec `check=True` sur `decision_log.jsonl`** lèverait une exception si le fichier n'existait pas. Il existe ; latent seulement sur un clone neuf. **Noté.**

---

## 🔴 24/08 (nuit, 2e « cherche encore ») — l'écriture d'état n'était pas atomique

**Un bug de plus, démontré en deux temps plutôt qu'affirmé. Deux autres candidats examinés et innocentés.**

### ④ `_save_state()` tronquait le fichier avant d'écrire — et l'architecture du jour a multiplié l'exposition

**Le mécanisme, prouvé** : `Path.write_text()` ouvre en mode `"w"`, ce qui **tronque le fichier à 0 octet AVANT d'écrire le moindre octet** (sondé directement : 77 → 0 dès l'`open`, contenu seulement ensuite). Puis, en tuant un processus dans cette fenêtre : le fichier reste `{"account_id": "abc", "start` — **exactement l'état `_corrupted`**.

**Pourquoi ça compte plus ce soir que ce matin**, et c'est le vrai point :
- La gestion de corruption ajoutée dans la passe précédente rend un `state.json` cassé **collant, volontairement** : toutes les entrées sont refusées jusqu'à intervention humaine. Sûr — mais une écriture déchirée n'est plus un désagrément passager, **elle arrête l'agent pour le reste d'une semaine sans surveillance**.
- `monitor_exits.py` est désormais planifié **toutes les 15 minutes** (launchd) : un **second** processus appelle cette fonction bien plus souvent que le run quotidien d'`agent.py`, et les deux peuvent se chevaucher.

**Autrement dit : les deux décisions prises aujourd'hui ont, ensemble, transformé un risque théorique en risque d'indisponibilité réel.** Aucune des deux n'était fausse isolément.

**Corrigé** : écriture dans un fichier temporaire du même répertoire, `fsync`, puis `os.replace()` — atomique sur POSIX. **Vérifié en rejouant le même scénario de mise à mort : `state.json` intact, complet, encore valide.** Non-régression : écriture normale OK, aucun résidu `.tmp`.

### ⑤ `hindsight_guard.py` — audité pour la première fois, **innocenté**

La revendication centrale du projet n'avait jamais été relue. Hypothèse testée : `max(scores, key=...)` retourne le **premier** élément en présence d'un `NaN` (toute comparaison avec NaN est fausse), et `_sharpe()` rend bien `NaN` si un rendement est `NaN`/`inf` — un score corrompu pourrait donc gagner le sweep en silence.

**Testé : non.** Le `NaN` gagne bien le `max`, **mais `NaN > seuil` est faux**, donc `in_sample_clears_bar` le rejette et `agrees` reste `False`. **Le garde-fou échoue du bon côté.** *(Seul résidu : une liste de candidats vide lève `ValueError` au lieu de refuser proprement — inatteignable, `CANDIDATE_HV_WINDOWS` est une constante.)*

### ⑥ `decision_log.read_log()` — **innocenté** aussi

Deux processus écrivent ce fichier en append. Testé avec une ligne volontairement tronquée : la lecture **avertit, saute la ligne, et continue** — le dashboard public ne casse pas. Aucun correctif nécessaire.

---

## 🔴 24/08 (nuit) — « cherche encore » : deux bugs de plus, reproduits avant d'être déclarés

**Deux vrais défauts trouvés dans le code écrit quelques heures plus tôt, chacun reproduit par un test AVANT correction.** Un troisième candidat examiné et **innocenté**.

### ① Un ordre réellement passé pouvait disparaître des accumulateurs — côté DANGEREUX

`agent.py` soumettait l'ordre, **puis** mettait à jour `committed_this_run_by_underlying` / `opened_this_run_underlyings`. Entre les deux : `record_order_submitted()`, qui écrit `state.json` — donc exactement le scénario de crash-en-écriture pour lequel la gestion de corruption a été écrite. En cas d'échec, le `except` de la boucle avalait tout et passait au symbole suivant **sans jamais enregistrer que la position existait**.

**Reproduit :** témoin sain → `check_gates(GLD)` reçoit `committed={'SPY': 950.0}, open={'SPY'}`. Avec l'échec → **les deux ordres partent quand même**, mais GLD est évalué avec `committed={}, open=set()`. La position SPY devient invisible pour le garde-fou suivant, précisément dans la fenêtre de latence API que ces accumulateurs existent pour couvrir → `MAX_TOTAL_RISK_PCT`, `MAX_SECTOR_EXPOSURE_PCT` et `MAX_OPEN_POSITIONS` franchissables en agrégat.

**Même forme que le correctif `manage_exits` de la passe précédente** (« une position réellement fermée ne doit pas être rapportée comme laissée ouverte parce que le compteur a échoué après ») — mais sur le chemin d'**entrée**, et contrairement à la plupart des trous d'isolation trouvés aujourd'hui, celui-ci échouait **du mauvais côté** : sur-exposition, pas un trade refusé pour rien.

**Corrigé** : les accumulateurs bougent **en premier**, juste après la soumission ; `record_order_submitted` est isolé dans son propre `try/except`, avec avertissement affiché et trace dans le journal de décision. Vérifié : l'ordre est désormais rapporté `order_submitted` (plus « error ») et la position reste visible.

### ② Le chemin de SORTIE écrasait un `state.json` corrompu

`_load_state()` promet dans sa propre docstring qu'un fichier corrompu est « laissé intact jusqu'à intervention humaine ». `check_gates()` respecte scrupuleusement cette promesse. **Mais le chemin de sortie ne passe pas par `check_gates`** — par conception, les sorties doivent tourner sous verrou — donc `manage_exits() → _record_exit_outcome()` atteignait `_load_state()` + `_save_state()` **sans aucun contrôle de corruption**.

**Reproduit, sur un fichier corrompu qui cachait `locked: true`** : après un stop-loss, le fichier est écrasé par `{"_corrupted": true, "consecutive_losses": 1}` — **`starting_equity` et `locked: true` perdus**.

⚠️ **Gravité, dite précisément : ça n'ouvrait PAS de trou de trading.** Le drapeau `_corrupted` survit au passage, donc `check_gates` continue de refuser toute entrée. Ce qui était détruit, c'est la **preuve** — les octets dont un humain a besoin pour savoir si un verrou était actif avant le crash — alors que le module affirmait le contraire.

**Corrigé au point de passage unique** (`_save_state`) plutôt que dans chaque appelant : ça couvre aussi `record_order_submitted` (même forme latente, seulement inatteignable parce que `check_gates` refuse d'abord) et tout écrivain ajouté plus tard. Non-régression vérifiée : l'écriture normale fonctionne toujours.

### ③ Contrôle de qualité des données — examiné, **innocenté**

Le `raise DataQualityError` est imbriqué dans un `try/except ValueError` : si `DataQualityError` héritait de `ValueError`, le contrôle de fraîcheur serait avalé par son propre `except`. **Testé : il hérite d'`Exception`, il s'échappe correctement.** Les deux seuils mordent pour de vrai (barre de 30 j > limite 5 j ; saut de 80 % > limite 50 %) et un horodatage illisible est signalé, pas sauté en silence. **Aucun bug — vérifié plutôt que supposé.**

**Non-régression contre l'API réelle** après les deux correctifs : pipeline complet OK, l'anti-double-soumission bloque correctement le second passage sur SPY (`already submitted an order for SPY today`), `monitor_exits` sain, `state.json` intact.

---

## 🟢 24/08 (soir) — session terminal : TOUT le code du jour vérifié contre l'API réelle

**Verdict : le pipeline tourne de bout en bout avec tous les correctifs en place.** Ordre paper `id=2e7ba582-3784-4c80-8abb-d1e4eb0a79eb`, **qty=2** sur `SPY260831P00764000`, rempli à 4,69 $. Univers passé à SPY/GLD/XLK/XLV (redesign multi-positions).

**Les deux bugs de sécurité du jour ont été observés en conditions réelles, pas seulement en mocks :**
- 🟢 **Corruption de `state.json`** — testé en vrai (sauvegarde → troncature → appel → restauration) : le code **refuse toute nouvelle entrée**, affiche l'avertissement, et surtout **ne réécrit pas le fichier**. Le verrou ne tombe plus en silence.
- 🟢 **Isolation de `manage_exits()`** — a tourné sur une vraie position ouverte (« holding (-0,4 %) »). La branche « échec de fermeture » n'a pas eu d'occasion naturelle de se déclencher ; seule la branche nominale est confirmée en direct.
- 🟢 **Bonus non cherché : l'anti-double-soumission s'est déclenché pour de vrai** — un second appel à `check_gates('SPY', …)` le même jour répond *« already submitted an order for SPY today (local record, state.json) »*.
- 🟢 **`HALT` fait exactement ce qu'il promet** : les sorties tournent d'abord (`[0.5] Managing existing positions`), puis l'entrée est bloquée — le message le dit lui-même.

**🔴 `hindsight_guard` a refusé un symbole en direct, et c'est la meilleure démonstration du projet.** XLK : sa fenêtre 90 jours affiche **+0,416 de payoff cumulé, le meilleur chiffre de tout le backtest, 3× tout le reste** — et c'est précisément celle que le garde-fou rejette (gagnant 90 sur l'historique complet, 10 en in-sample). **Sans le garde-fou, c'est exactement la fenêtre qu'on aurait choisie.**

**`compare_strategies.py`, lancé pour la première fois** (rapport : `STRATEGY_COMPARISON.md`) : sur le Sharpe in-sample du paramètre vetté — le seul chiffre comparable — **`vol_strategy` gagne sur les 4 symboles** (SPY 1,598 vs 0,630 · GLD 1,956 vs 1,407 · XLV 1,442 vs 0,812 · XLK vol disqualifié pour fuite). 🔴 **Mais `momentum` est plus propre : garde-fou 4/4 contre 3/4.** ⚠️ Les rendements cumulés des deux familles **ne sont pas commensurables** (momentum est en permanence dans le marché) — ne jamais les classer. **Aucune bascule décidée : c'est un choix de méthode qui appartient à Spap.**

**🔴 Point bloqué, avec sa cause exacte : `monitor_exits.py` ne peut pas être planifié tant que `~/Desktop` reste le dossier du projet.**
- Le cron documenté dans son docstring (`*/15 9-16`) est en heure **locale**, pas ET : sur ce Mac (CEST, 6 h d'écart) il tournerait **03h00–10h00 ET**, soit 30 minutes utiles sur 6h30. Les bonnes heures locales sont **15h30–22h00**.
- Une tâche `launchd` a été écrite avec les bons créneaux (140, lun-ven, toutes les 15 min) **et le PATH incluant `~/.local/bin`** — installée et chargée. Mais elle échoue : `Operation not permitted`. **Diagnostic prouvé** par une sonde contrôlée : un process lancé par launchd lit `~/.zshenv` mais se voit **refuser `~/Desktop/…`** — c'est la protection TCC de macOS sur le Bureau, pas un problème de chemin ni de droits.
- **Deux issues, au choix de Spap** : ① accorder l'Accès complet au disque à `/usr/bin/python3` dans Réglages Système → Confidentialité (action manuelle, mot de passe requis) ; ② déplacer le dépôt hors de `~/Desktop`. La tâche est laissée installée : elle fonctionnera dès l'autorisation accordée, sans rien d'autre à faire.

---

## 🟠 24/08 — LE BACKTEST RÉEL A TOURNÉ. Résultat : edge fragile, pas prouvé.

**Premier passage de la stratégie contre de vraies barres historiques** (657 par symbole, via le CLI). Rapport complet : `BACKTEST_RESULTS.md`.

| | SPY | QQQ | IWM |
|---|---|---|---|
| **fenêtre 10 j** (la seule positive) | +0,1071 | +0,1771 | +0,2090 |
| les 4 autres fenêtres (20/30/60/90) | 🔴 négatives | 🔴 négatives | 🔴 négatives (sauf 30 j ≈ 0) |
| taux de succès du 10 j | 45,1 % | 43,9 % | 54,4 % |
| **gain restant si on retire les 5 meilleurs jours** | **0,1070 → 0,0177** | **0,1767 → 0,0402** | 0,2088 → 0,0989 |
| `hindsight_guard` | 🟢 propre | 🟢 propre | 🟢 propre |

**Trois lectures, honnêtement :**
- 🔴 **4 des 5 fenêtres candidates perdent de l'argent** sur les trois symboles. L'edge tient à une seule.
- 🔴 **83 % du gain de SPY vient de 5 jours sur 102** (77 % QQQ, 53 % IWM). C'est la signature *attendue* d'une stratégie d'optionalité longue — mais sur ~110 trades, ça ne distingue pas un edge d'une chance.
- ⚠️ **Le payoff est un proxy** qui ignore le spread et le theta — exactement les coûts qui frappent les ~70 % de trades perdants. Un coût réel mangerait d'abord ce qui reste après les 5 meilleurs jours.
- 🟢 **Aucune fuite de sélection** : la fenêtre gagnante gagne aussi sans information future, sur les trois symboles.

**🔒 Aucun seuil retouché après avoir vu ces chiffres** — c'est précisément le biais que ce projet existe pour attraper.

**Correctifs de la même session, vérifiés contre le vrai CLI** (commit `d23341a`) : isolation par symbole dans `agent.py` · `state.json` désormais gardé par `account_id` (une bascule de compte re-calibre et lève le verrou automatiquement) · **`account_number` confirmé présent dans la sortie CLI** (`PA3I2OIKF5F4` pour le dev, distinct de l'UUID) et le faux WARNING de `test_connection.py` est mort — vérifié dans les 3 cas (bon numéro → silence, UUID → alerte, mauvais numéro → alerte). Le dashboard affiche maintenant ce même `account_number`.

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
- **"Social engagement" n'est PAS qu'un bonus** — corrigé 25/08 après avoir relu la page officielle lablab.ai ligne par ligne : c'est un des **5 critères de jugement officiels** du classement principal (P&L Performance, Technology Implementation, Creativity & Originality, Presentation & Execution, **Social engagement**), en plus d'être un prix séparé ($500/équipe + 1 mois Algo Trader Plus par membre, 2 équipes gagnantes). Jusqu'à 5 posts X/LinkedIn taguant @lablabai et @AlpacaHQ, comptés dans la soumission finale. Brouillons prêts dans `SOCIAL_POSTS_DRAFT.md`.

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
10. Publier au fil de l'eau sur X/LinkedIn (jusqu'à 5 posts — **critère de jugement officiel, pas juste une piste bonus**, voir plus bas) — montrer le raisonnement, pas juste le résultat. Brouillons prêts dans `SOCIAL_POSTS_DRAFT.md`, à personnaliser et poster soi-même.
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

## 🟢 24/08 — Positions multiples, secteurs non corrélés, comparaison de stratégies, plan licence

Directive explicite de Spap (verbatim) : *"plusieurs position en meme temp s'il y a 2 positions ouvertes en même temps, il faut redéfinir si le plafond de 1% s'applique par trade (donc jusqu'à 2% d'exposition simultanée) ou sur le total, et vérifier que le verrou de -3% mesure bien le drawdown combiné, pas juste une position isolée — rien de tout ça n'est câblé aujourd'hui. go plusieur symbole différents 1 sur la matiere premiere 2 sur les technologie 3 sur la phramacetique ect jamais tout les meme oeuf dans le meme panier"* — plus deux directives complémentaires (comparer les stratégies honnêtement, documenter le plan licence/confidentialité).

**1. Positions multiples (`risk_gates.py`, `alpaca_cli.py`).** `MAX_OPEN_POSITIONS` passe de 1 à 4. Nouveau plafond `MAX_TOTAL_RISK_PCT = 0.03` (3% de l'équité) sur la somme des primes engagées sur TOUTES les positions ouvertes à la fois, en plus du plafond par trade `MAX_RISK_PCT_PER_TRADE = 0.01` déjà existant — donc une 2e ou 3e position réduit le budget restant, elle ne reçoit pas chacune son propre 1% frais. Blocage explicite si deux positions tentaient d'ouvrir sur le même sous-jacent en même temps (`alpaca_cli.option_underlying()` compare le sous-jacent de chaque position ouverte). Le verrou hebdomadaire à -3% (`WEEKLY_LOSS_LOCK_PCT`) n'a **pas eu besoin d'être modifié** : il compare déjà l'équité totale du compte (qui reflète nécessairement toutes les positions combinées) à l'équité de départ enregistrée — c'était déjà un drawdown combiné, pas une position isolée. Vérifié par compilation (`py_compile`) et un test simulé à 6 cas : deux sous-jacents différents peuvent ouvrir en même temps, un doublon sur le même sous-jacent est bloqué, le plafond de 4 positions bloque une 5e tentative, et le plafond total à 3% réduit correctement le dimensionnement d'un trade avant de le bloquer complètement une fois épuisé — les 6 cas passent.

**2. Univers étendu à des secteurs non corrélés (`agent.py`).** `DEFAULT_UNIVERSE` passe de `["SPY", "QQQ", "IWM"]` (trois ETF large marché très corrélés entre eux — même moteur macro, souvent chers/bon marché en volatilité les mêmes jours) à `["SPY", "GLD", "XLK", "XLV"]` : SPY (ancrage marché large), GLD (matières premières/or), XLK (technologie), XLV (pharma/santé) — tous des ETF liquides et optionables, choisis plutôt que des actions individuelles pour des spreads plus serrés pendant une semaine de hackathon en direct. `_run()` dans `agent.py` a été restructuré : au lieu de ne trader que le premier symbole tradeable trouvé (`next(...)`), la boucle tente maintenant une entrée pour **chaque** symbole qui a passé les gates 2-5, et laisse `risk_gates.check_gates()` bloquer naturellement une fois le plafond de positions ou d'exposition totale atteint.

**3. Comparaison honnête momentum vs HV-rank (`compare_strategies.py`, nouveau fichier).** Directive de Spap : *"si tu veux vraiment la meilleure stratégie, pas juste celle qui raconte la meilleure histoire aux juges."* Script qui fait tourner `momentum_strategy.py` (TSMOM, jusque-là jamais backtesté contre de vraies données, seulement écrit comme deuxième démonstration du même schéma hindsight_guard) contre les mêmes barres réelles que `vol_strategy.py`, avec le même test de fuite hindsight_guard sur les deux familles. **Mise en garde explicite dans le script** : les deux payoffs ne sont pas la même unité (proxy d'options pour vol_strategy, qui est plat la plupart des jours ; rendement réel d'action pour momentum, qui est toujours en position) — la colonne comparable honnêtement est le Sharpe in-sample du gagnant vetté par chaque famille, pas le rendement cumulé brut. Le script écrit `STRATEGY_COMPARISON.md` avec un verdict à remplir **après** l'avoir fait tourner sur de vraies données, pas une conclusion pré-écrite. Reste à exécuter depuis un vrai terminal (même contrainte réseau que `backtest.py`) — pas encore fait à ce stade.

**4. Plan licence/confidentialité documenté (`README.md`).** Nouvelle section "License and privacy" : le dépôt est public MIT parce que le hackathon l'exige (règle non négociable, "Submissions must be original and MIT-compliant"), ce qui signifie concrètement que n'importe qui — y compris une entreprise — peut copier, modifier et même vendre ce code sans payer ni demander la permission, la seule obligation étant de garder la notice de copyright. Impossible de soumettre à ce hackathon et de garder le code privé — les deux s'excluent par construction. Plan confirmé avec Spap : après le hackathon, il continue de faire tourner sa propre copie privée (un clone séparé, pas le dépôt public) même si l'historique du dépôt public reste public pour toujours et ne peut pas être rendu privé rétroactivement. Toute vraie amélioration développée après coup qu'il voudrait protéger va dans un nouveau dépôt séparé, non public — pas dans celui-ci, qui reste figé comme "la soumission du hackathon".

**Reste à faire, pas encore fait à ce stade** : committer ces changements depuis un vrai terminal, tester le comportement multi-positions contre l'API réelle, exécuter `compare_strategies.py` pour de vrai et rapporter le résultat honnêtement (même s'il contredit le choix de vol_strategy comme stratégie principale), et revérifier la liquidité des chaînes d'options pour GLD/XLK/XLV via `find_near_the_money_contract` contre de vraies données — le prochain brief terminal doit couvrir tout ça.

**Septième passe "cherche encore" (24/08) — un vrai bug introduit par mes propres changements du jour, trouvé en relisant le tableau de bord :**

En relisant `docs/index.html` après avoir restructuré `agent.py` pour attendre plusieurs symboles par run, j'ai trouvé que le JS du tableau de bord lisait encore `d.order_id`, `d.chosen_symbol`, `d.direction`, `d.qty` directement sur chaque enregistrement de décision — exactement les champs que la réécriture d'`agent.py` a déplacés dans une nouvelle liste `record["trades"]` (un par symbole tenté). `publish_dashboard.py` republie les enregistrements de `decision_log.py` sans les transformer, donc sans correctif, **toutes les prochaines journées de trading, même avec de vrais ordres soumis, se seraient affichées comme "—" (aucun trade)** sur le tableau de bord public — silencieusement, sans erreur visible. Un vrai régression que j'ai moi-même introduite en début de journée, pas un bug préexistant.

**Corrigé** : `renderTrade(d)` dans `docs/index.html` gère maintenant les trois formes possibles d'un enregistrement — `d.trades` (liste, la nouvelle forme, un ordre par symbole tenté), `d.tradeable_symbols` (nouvelle forme des runs `--dry-run`), et les anciens champs plats `d.chosen_symbol`/`d.order_id`/`d.qty`/`d.direction` (les entrées déjà écrites dans `decision_log.jsonl` avant aujourd'hui, qui restent dans ce fichier pour toujours puisqu'il est committé, pas ignoré). Au passage, corrigé aussi le badge d'outcome agrégé dans `agent.py` : au lieu de toujours retomber sur "risk_gate_blocked" quand aucun ordre n'est soumis (même si la vraie raison était "aucun contrat trouvé" sur tous les symboles), il reprend maintenant la raison réelle quand elle est la même pour toutes les tentatives. Vérifié : `py_compile` propre sur `agent.py`, `node --check` propre sur le JS extrait, et un script Python avec `html.parser` confirme zéro tag non fermé dans `docs/index.html` après l'édition.

Cette découverte confirme une nouvelle fois le schéma déjà vu ce sprint (bug de pagination des strikes le 24/08) : un changement qui compile et qui "a l'air de marcher" peut casser silencieusement une autre partie du système qui dépendait de l'ancienne forme des données — la relecture systématique après un changement structurel n'est pas optionnelle.

**Huitième passe "cherche encore" (24/08) — un deuxième bug réel, cette fois dans la logique même de `risk_gates.py` du jour, pas dans le tableau de bord :**

En repensant au chemin "plusieurs symboles dans le même run" ajouté aujourd'hui, une question s'est posée : `agent.py` boucle sur chaque symbole tradeable et appelle `risk_gates.check_gates()` une fois par symbole — mais chaque appel relit `alpaca_cli.list_open_option_positions()` **depuis l'API en direct**. Rien ne garantit qu'un ordre tout juste soumis (`order submit` renvoie dès l'acceptation, pas nécessairement à l'exécution) apparaisse instantanément dans cette liste. Concrètement : si le run traite SPY puis GLD dans la même exécution, et que la position SPY n'est pas encore visible côté API au moment de vérifier GLD, `check_gates()` pour GLD calculerait son budget comme si SPY n'avait jamais été tenté — pouvant dépasser silencieusement le plafond total de 3% ou le plafond de 4 positions en agrégé sur un seul run, exactement ce que Spap a demandé de vérifier ("le verrou... mesure bien le drawdown combiné").

**Corrigé** : `check_gates()` accepte maintenant deux paramètres optionnels, `already_committed_this_run` et `already_open_this_run`. `agent.py` les accumule en mémoire au fil de sa boucle (`committed_this_run`, `opened_this_run`), incrémentés après chaque ordre réellement soumis en utilisant le nouveau champ `RiskDecision.committed_dollars` (le coût réel du trade, pas juste ré-estimé) — pas besoin de refaire l'appel API entre deux itérations. Le blocage sur sous-jacent en double n'avait pas besoin du même correctif : la boucle ne visite chaque symbole de l'univers qu'une seule fois par run, donc un doublon dans le même run est déjà impossible par construction. Vérifié par un nouveau test simulé à 3 cas : un scénario où l'API "en retard" montre zéro position ouverte alors que 2 900 $ ont déjà été engagés plus tôt dans le même run bloque bien le 3e trade (au lieu de le laisser passer comme avant le correctif), un scénario équivalent pour le plafond de 4 positions, et un cas neutre (premier trade du run, rien de changé) — les 3 cas passent. `py_compile` propre sur `agent.py` et `risk_gates.py`.

**Neuvième passe "cherche encore" (24/08) — vérification externe (pas de code) de la liquidité des 3 nouveaux symboles, avec de vraies données trouvées, mais une limite honnête à signaler :**

Question restée ouverte depuis l'ajout de GLD/XLK/XLV : est-ce que ces trois ETF ont vraiment des chaînes d'options assez profondes pour que `find_near_the_money_contract` (bande ±5% autour du spot, 7-21 jours à l'échéance) trouve un contrat exploitable tous les jours ? Les sites spécialisés en liquidité d'options (OptionCharts, MarketChameleon) se sont révélés payants/verrouillés derrière un login, comme pour Alpaca — pas d'accès direct depuis Cowork. Mais `stockanalysis.com` a donné de vrais chiffres à jour (24/08/2026, sources CBOE/S&P Global) : **GLD** — 154,24 Md$ d'actifs sous gestion, ~13,45M d'actions échangées ce jour-là, coté depuis nov. 2004 ; **XLK** — 119,63 Md$ d'actifs, ~4,0M d'actions échangées, coté depuis déc. 1998 ; **XLV** — 45,21 Md$ d'actifs, ~3,8M d'actions échangées, coté depuis déc. 1998, avec un signal concret trouvé dans un article CNBC (juin 2026) : ~5 300 calls échangés en une seule séance contre ~1 000 puts. Les trois sont des Select Sector SPDR / le plus gros ETF or au monde — pas des tickers obscurs.

**Limite honnête, à ne pas dépasser dans le pitch** : un gros volume sur l'action sous-jacente et un gros encours sont un **indicateur indirect fort**, pas une preuve directe, de profondeur d'options — ils ne disent rien sur le spread bid-ask réel ni sur la disponibilité de strikes dans la bande ±5% précisément sur les échéances 7-21 jours que l'agent utilise. Cette vérification-là ne peut se faire qu'avec l'endpoint réel `/v2/options/contracts` d'Alpaca, bloqué depuis Cowork comme tout le reste de l'API — reste dans le brief terminal, pas résolue ici. Ce que cette passe apporte concrètement : la probabilité que ces trois symboles posent un vrai problème de liquidité d'options est basse (ce sont parmi les ETF sectoriels les plus échangés du marché américain), donc le risque à vérifier en priorité au kickoff n'est plus "est-ce que ces tickers ont des options du tout" mais bien le détail fin (strikes précis disponibles, spread) — déjà ce que le brief demandait, maintenant avec un vrai contexte chiffré derrière au lieu d'une inconnue totale.

**Dixième passe "cherche encore" (24/08) — `compare_strategies.py` n'avait jamais été exécuté, seulement compilé : vérifié pour de vrai avec des données synthétiques :**

Écrit hier mais jamais lancé — `py_compile` prouve que la syntaxe est valide, pas que le pipeline tourne. Point de risque identifié en le relisant : `momentum_strategy.py` a sa propre classe `Bar` (dataclass séparée de celle de `vol_strategy.py`), et `alpaca_cli.get_daily_bars()` renvoie des instances de `vol_strategy.Bar` — `compare_strategies.py` passe ces objets directement aux fonctions de `momentum_strategy.py` sans conversion, en comptant sur le duck typing Python (les deux classes n'ont qu'un champ `close`, donc `isinstance` échoue mais l'accès aux attributs marche). Jamais vérifié pour de vrai jusqu'à cette passe.

**Vérifié avec des données synthétiques** (marche aléatoire, seed fixée, ~597 barres par symbole — la vraie forme de barres qu'Alpaca renverrait, juste avec des prix inventés puisque Cowork ne peut pas atteindre l'API) : `momentum_strategy.current_signal()` et `score_lookback()` tournent sans erreur sur des objets `vol_strategy.Bar`, `compare_strategies.compare_symbol()` tourne de bout en bout sur 4 symboles (SPY/GLD/XLK/XLV) sans exception, et `format_report()` produit un tableau markdown propre et lisible (confirmé en l'affichant). Le pipeline entier — pas juste la syntaxe — fonctionne. Reste un vrai inconnu que seules de vraies données peuvent trancher : les VALEURS de sortie (quelle fenêtre/lookback gagne, quel Sharpe) n'ont aucune signification sur des prix aléatoires — seule la mécanique est vérifiée ici, pas le résultat, exactement la même distinction que ce projet applique déjà à tout le reste.

**Onzième passe "cherche encore" (24/08), demandée explicitement comme double contrôle final avant d'arrêter pour aujourd'hui :**

Relecture systématique de tout ce qui a changé aujourd'hui, pas une nouvelle fonctionnalité :
- `grep` sur `QQQ|IWM` dans tout le code : deux mentions restantes dans `risk_gates.py` et `agent.py` sont volontaires (elles expliquent pourquoi l'ANCIEN univers ne convenait pas au multi-positions, contexte historique correct). Une troisième, dans `backtest.py`, ne l'était pas : la docstring disait déjà "univers par défaut SPY,GLD,XLK,XLV", mais le `--symbols` par défaut d'`argparse` était resté à `"SPY,QQQ,IWM"` — un `python backtest.py` sans argument aurait donc contredit sa propre documentation. **Corrigé.**
- Vérifié qu'aucun appelant ne reste sur l'ancienne fonction `alpaca_cli.has_open_option_position()` (gardée volontairement pour compatibilité, mais plus jamais appelée nulle part dans le code — confirmé par recherche).
- Revérifié à la main l'ordre des arguments positionnels/nommés de `RiskDecision(True, reason, qty, committed_dollars=actual_cost)` contre la définition du dataclass (`allowed, reason, qty=0, committed_dollars=0.0`) — correct, pas de décalage.
- Relancé les 6 cas de test multi-positions ET les 3 cas de test "décalage même run" **ensemble, dans un seul passage** (au lieu de deux scripts séparés comme précédemment) pour vérifier qu'aucun des deux correctifs ne casse l'autre : 9/9 passent.
- `BRIEF_MULTI_POSITION_ET_COMPARAISON.md` mis à jour pour rester synchrone avec l'état réel du code : le chiffre "6 cas" était devenu obsolète (9 maintenant), `backtest.py` manquait de la liste des fichiers modifiés à vérifier en session terminal, et la vérification réelle de `compare_strategies.py` (passe précédente) n'y était pas encore mentionnée.
- `py_compile` relancé sur l'ensemble des fichiers `.py` du projet une dernière fois : propre.

Rien de cassé trouvé dans cette dernière passe, seulement une incohérence de documentation (`backtest.py`) et des références obsolètes dans le brief — mais utile de l'avoir fait : c'est exactement le genre d'écart silencieux (le code dit une chose, la doc en dit une autre) que ce projet existe pour détecter ailleurs, donc pas défendable de le laisser traîner chez soi.

**Douzième passe "cherche encore" (24/08) — recentrée sur Spap : l'agent, pas la stratégie. Une vraie source externe trouvée, publiée par Alpaca lui-même :**

Question de Spap : on vient de passer la journée à améliorer la STRATÉGIE (HV-rank, comparaison momentum) et les contrôles de risque, mais le vrai livrable du hackathon c'est l'AGENT. Cherché sur ce terrain précis, y compris dans les concours passés.

Trouvé un article officiel Alpaca ("Learn", mai 2026, tag "Agentic Trading") : *"Building a Multi-Agent AI Trading System on Alpaca"*, écrit par un CPO d'une plateforme d'investissement réglementée (CUSP Wealth, Dubaï), documentant une vraie architecture multi-agents tournée sur un compte paper Alpaca 100K$. Pas un pitch de hackathon — un vrai retour d'expérience publié directement par Alpaca, donc potentiellement lu par des gens proches des juges. Quatre axes concrets pour AMÉLIORER L'AGENT (pas la stratégie), trouvés en le comparant à notre code actuel :

1. **Le plus important, un vrai trou trouvé chez nous** : leur "position monitor" tourne toutes les 15 minutes, indépendamment du cycle de décision d'entrée. Chez nous, `risk_gates.manage_exits()` (take-profit/stop-loss) ne tourne QU'au tout début de chaque exécution d'`agent.py` — si l'agent est planifié une fois par jour (option encore ouverte dans "Choix à trancher avant le 28"), une position qui explose son stop-loss de -50% en pleine journée reste ouverte jusqu'au lendemain. C'est un vrai trou de discipline de sortie, pas une amélioration cosmétique.
2. Leur `risk_guard` code en dur un plafond de **concentration sectorielle** (30% max par secteur), en plus du plafond par position. Chez nous, la diversification sectorielle (SPY/GLD/XLK/XLV) est une politique de choix d'univers, pas un contrôle codé — exactement le genre d'écart entre "politique en prose" et "contrôle appliqué en code" que le docstring de `risk_gates.py` dénonce déjà comme le trou que ce projet existe pour attraper ailleurs.
3. Leçon qu'ils tirent eux-mêmes explicitement ("ce que je changerais") : surveiller la fraîcheur/qualité des données dès le départ, pas après un problème en pleine séance sous pression. Chez nous, rien ne vérifie qu'une barre fraîchement récupérée n'est pas périmée ou aberrante avant de calculer un signal dessus.
4. Ils gardent une porte humaine (APPROVE/REJECT/REVISE) même si le système pourrait tourner en autonomie complète, en argumentant que l'intégrité du processus l'exige en finance régulée — pas forcément applicable pendant la semaine du hackathon (l'autonomie est probablement attendue), mais directement pertinent pour l'usage long terme que Spap envisage après coup : un interrupteur manuel simple (`paused` dans `state.json` ou fichier `HALT`) que l'agent vérifie avant de trader, pour pouvoir le mettre en pause sans toucher aux identifiants ni au code en pleine semaine.

**Rien de tout ça n'est encore implémenté** — trouvé et documenté seulement, présenté à Spap pour arbitrage vu le temps restant avant le 28/08.

**Spap a répondu : les 4 axes, plus "cherche encore si il en a d'autre" avant d'implémenter.** Deuxième source trouvée, cette fois un guide d'architecture détaillé ("AI Trading Agent Development: 2026 Architecture Guide", ampcome.com, 10 août 2026) — contenu marketing d'agence mais avec une checklist de modes de panne concrète et vérifiable contre notre propre code, pas juste des généralités. Deux axes vraiment nouveaux (pas déjà couverts par les 4 ci-dessus), trouvés dans leur liste "Failure modes" :

5. **Protection contre la double-soumission d'ordre** ("idempotency keys on every order... a retry after a timeout sends the order twice"). Chez nous : si `agent.py` plante ou est relancé après avoir déjà soumis un ordre mais avant de finir d'écrire `decision_log.jsonl` (coupure réseau, relance manuelle par erreur), rien n'empêche de soumettre le même trade deux fois. Jamais considéré avant cette recherche.
6. **Coupe-circuit sur pertes consécutives**, distinct du verrou de -3% déjà en place : leur liste de déclencheurs d'escalade inclut "consecutive_losses: 3" comme signal séparé du drawdown en %. Une série de pertes rapprochées peut être un signal d'alerte avant même d'atteindre -3% de drawdown total — un filet complémentaire, pas redondant.

Les deux corroborent aussi les axes déjà validés : leur `guardrails` d'exemple inclut explicitement `max_sector_exposure_pct: 30` (axe 2) et `data_staleness_seconds_above` comme déclencheur d'escalade (axe 3) — deux sources indépendantes convergent sur les mêmes idées, bon signe que ce ne sont pas des lubies isolées.

**Décision : les 4 axes validés + ces 2 nouveaux sont tous implémentés maintenant** (Spap a autorisé à agir sur ce qui est trouvé, pas juste à le rapporter). Détail de chaque implémentation ci-dessous.

## 🟢 24/08 — Les 6 contrôles niveau AGENT implémentés et testés

Les 6 axes (4 validés par Spap + 2 trouvés en cherchant encore) sont tous codés dans `risk_gates.py` (sauf le dernier, `monitor_exits.py`), chacun avec un test simulé dédié qui passe :

1. **Plafond de concentration sectorielle** (`MAX_SECTOR_EXPOSURE_PCT = 0.015`, `SECTOR_MAP`, `sector_of()`) — no-op aujourd'hui (un seul symbole par secteur, déjà couvert par le blocage anti-doublon), mais devient actif dès que l'univers grandit au-delà d'un symbole par secteur. Tracking "même run" ajouté aussi (`already_committed_this_run_by_sector`), même raison que pour le plafond total. 5/5 cas de test passent.
2. **Contrôle de fraîcheur/qualité des données** (`alpaca_cli._check_bar_quality`, `DataQualityError`) — refuse de trader sur des barres périmées (>5 jours) ou un saut de prix implausible (>50% d'un jour à l'autre). Vérifié qu'un vrai jour de krach historique (-12%, pire journée SPY du COVID) ne déclenche PAS de faux positif — le seuil est généreux exprès. 5/5 cas passent, y compris ce cas négatif important.
3. **Interrupteur manuel** (`risk_gates.is_halted()`, fichier `HALT` gitignoré) — bloque les nouvelles entrées, jamais les sorties (même asymétrie que le verrou hebdo). **Incident trouvé en le testant** : Cowork peut créer le fichier `HALT` mais pas le supprimer (même limitation connue que `.git/index.lock`) — un fichier `HALT` vide traîne réellement dans le dépôt en ce moment, ce qui bloquerait un vrai run de l'agent tel quel. **À supprimer en priorité absolue dans la prochaine session terminal** (`rm -f HALT`), avant tout test d'entrée. 3/3 cas passent.
4. **Protection contre la double-soumission** (`risk_gates.already_traded_today()`, `record_order_submitted()`) — enregistrement local dans `state.json`, vérifié EN PREMIER dans `check_gates()` avant tout appel API, pour survivre à un crash+relance d'`agent.py` sans dépendre du délai de l'API. 6/6 cas passent, y compris la preuve que l'appel API n'est jamais atteint quand le blocage local suffit.
5. **Coupe-circuit sur pertes consécutives** (`MAX_CONSECUTIVE_LOSSES = 3`, `_record_exit_outcome()`) — distinct du verrou de -3% de drawdown, alimenté par les propres sorties stop-loss/take-profit de l'agent (pas un suivi P&L exhaustif du compte — limite dite honnêtement dans le docstring). Collant comme le verrou hebdo, ne se réinitialise pas tout seul une fois déclenché (logique : un agent bloqué ne peut jamais produire le gain qui le débloquerait — c'est le but, pas un oubli). 4/4 cas passent.
6. **Moniteur de sortie indépendant** (`monitor_exits.py`, nouveau fichier) — appelle uniquement `risk_gates.manage_exits()`, pensé pour tourner toutes les 15-30 min pendant les heures de marché, séparément du cycle quotidien complet d'`agent.py`. Ne vérifie PAS `is_halted()` (une pause bloque les nouvelles entrées, pas la gestion des positions déjà ouvertes). Cowork ne peut pas planifier de vraie tâche cron/launchd sur le Mac de Spap — instructions de mise en place documentées dans le docstring du fichier, à exécuter en session terminal réelle. Testé avec des mocks (1/1 cas, bout en bout).

`README.md` mis à jour avec une nouvelle section "Agent-level controls (not strategy tweaks)". `py_compile` propre sur les 14 fichiers `.py` du projet. **Rien de tout ça n'a encore tourné contre l'API réelle** — même mise en garde que d'habitude.

**Treizième passe "cherche encore" (24/08) — un vrai bug de récidive, même famille que le tout premier bug corrigé aujourd'hui :**

En relisant les 2 nouveaux champs de `state.json` ajoutés cette après-midi (`traded_today`, `consecutive_losses`) à la lumière de la logique de changement de compte déjà existante, trouvé exactement le même bug que celui corrigé en tout début de journée (compte dev → compte dédié) — mais réapparu dans du code écrit APRÈS ce premier correctif. `_record_starting_equity()` réinitialise `starting_equity`/`locked`/`lock_reason` quand `account_id` change, mais `traded_today` et `consecutive_losses` n'avaient jamais été ajoutés à cette liste de réinitialisation. Concrètement : passer du compte dev au compte dédié le 28/08 aurait fait croire à l'agent qu'un symbole "a déjà été tradé aujourd'hui" sur le NOUVEAU compte alors qu'il n'a jamais rien tradé, et qu'une série de pertes de l'ANCIEN compte s'applique encore — pouvant déclencher le coupe-circuit sur pertes consécutives dès le premier run réel sur un compte qui n'a subi aucune perte. **Prouvé avec un test qui reproduit le bug avant correctif** (le blocage apparaissait bien), pas juste supposé.

Deuxième problème trouvé en creusant : le contrôle `already_traded_today()` était placé AVANT l'appel à `_record_starting_equity()` dans `check_gates()` (optimisation pour éviter un appel API dans le cas courant) — ce qui veut dire que même en corrigeant la réinitialisation, le contrôle aurait continué à lire l'ancien état avant que la réinitialisation n'ait eu lieu. Réordonné : la détection de changement de compte tourne maintenant AVANT `already_traded_today()`.

**Corrigé** : `_record_starting_equity()` réinitialise maintenant aussi `traded_today` et `consecutive_losses` quand le compte change, et l'ordre des vérifications dans `check_gates()` a été inversé pour que ça marche réellement. Revérifié avec le test qui avait prouvé le bug (passe maintenant), plus une vérification de non-régression que le MÊME compte (pas de changement) ne réinitialise PAS ces champs à tort, plus les 8 cas de test déjà écrits ce sprint (positions multiples, décalage même-run, pertes consécutives, plafond sectoriel) relancés ensemble pour confirmer que le réordonnancement n'a rien cassé ailleurs — 3+8 = 11/11 passent.

Ce n'est pas la première fois aujourd'hui qu'une même famille de bug réapparaît dans du nouveau code après avoir été corrigée ailleurs (voir aussi : le tableau de bord qui lisait encore l'ancien format après la réécriture d'`agent.py`) — signe qu'il vaut la peine, la prochaine fois qu'un nouveau champ est ajouté à `state.json`, de vérifier systématiquement s'il doit rejoindre la liste de réinitialisation au changement de compte, plutôt que de le redécouvrir à chaque fois après coup.

**Quatorzième passe "cherche encore" (24/08) — un vrai bug trouvé dans `monitor_exits.py`, le fichier qu'on venait tout juste de créer dans la passe précédente :**

En relisant `monitor_exits.py` (contrôle #6 des axes agent, écrit cette après-midi) avec un œil neuf : le `finally` appelait `decision_log.log_run(record)` sans condition, à CHAQUE exécution — y compris les runs où il n'y a rien à fermer, le cas le plus fréquent de loin. Le docstring du fichier lui-même recommande de le planifier toutes les 15 minutes pendant les heures de marché US (9h30-16h00 ET, ~6,5h), soit jusqu'à ~26 exécutions par jour de bourse. `publish_dashboard.py` (via `decision_log.read_log(limit=30)`) n'affiche que les 30 décisions les plus récentes sur le tableau de bord public. Avec ~26 entrées "rien à fermer" par jour, en un peu plus d'une journée de bourse, ces entrées de routine auraient entièrement évincé la vraie décision quotidienne d'`agent.py` (celle qui trade ou explique pourquoi pas) de la section "recent decisions" du tableau de bord — exactement ce qu'un juge consulterait. Le journal `decision_log.jsonl` lui-même resterait complet et honnête (rien de caché), seul l'AFFICHAGE public en serait dégradé.

**Corrigé** : le `finally` de `monitor_exits.py` ne journalise plus que quand c'est utile — une fermeture réelle ou simulée (`"CLOSED"` ou `"WOULD CLOSE"` dans `exit_actions`) ou une erreur (`outcome == "error"`). Un run de routine sans rien à fermer imprime une ligne en console mais n'écrit rien dans `decision_log.jsonl`. Vérifié : `py_compile` propre, et un test simulé à 5 cas reproduisant exactement la logique du `finally` — (a) routine sans rien à fermer → pas de log, (b) fermeture réelle → log, (c) fermeture simulée en `--dry-run` → log, (d) erreur sans même de clé `exit_actions` → log, (e) marché fermé sans `exit_actions` → pas de log — les 5 passent.

Comme pour les passes 7 et 13 aujourd'hui, ce bug était dans du code écrit dans la MÊME session, pas hérité d'avant — confirme qu'une relecture après coup reste nécessaire même sur ce qu'on vient d'écrire, pas seulement sur le code ancien.

**Quinzième passe "cherche encore" (24/08) — le correctif de la passe précédente rendait un trou encore plus visible : `exit_actions` n'était jamais affiché nulle part sur le tableau de bord :**

En vérifiant si le correctif de journalisation de `monitor_exits.py` (passe 14) produirait vraiment quelque chose d'utile pour un juge une fois affiché, remonté toute la chaîne jusqu'au rendu réel : `publish_dashboard.py` republie bien chaque enregistrement brut de `decision_log.jsonl` (donc `exit_actions` est bien présent dans `data.json`), mais `docs/index.html` — le fichier qui construit le tableau HTML — ne lisait `d.exit_actions` **nulle part**. Ni `renderTrade()`, ni `renderDecisions()`, ni aucune autre fonction. Conséquence concrète à deux niveaux :
1. Un enregistrement `monitor_exits.py` (qui, depuis la passe 14, n'est journalisé QUE quand quelque chose de notable s'est passé) tombait dans tous les cas de repli de `renderTrade()` sans jamais les satisfaire (pas de `d.trades`, pas de `d.tradeable_symbols`, pas de `d.order_id`, pas de `d.chosen_symbol`) → affichait `—` dans la colonne Trade, verdicts vides, et un badge générique gris "checked" (absent de la table `outcomeBadge`). Une ligne du tableau de bord qui ne dit littéralement rien sur ce qui a fermé.
2. Même les vraies clôtures de `agent.py` lui-même (`risk_gates.manage_exits()` appelé en tout début de chaque run quotidien) écrivent dans `exit_actions` — et n'ont **jamais** été visibles sur le tableau de bord public depuis leur ajout plus tôt aujourd'hui, pas seulement pour `monitor_exits.py`.

Le correctif de la passe 14 rendait ce trou encore plus important : tout l'intérêt de ne journaliser que les runs notables de `monitor_exits.py` est que le juge voie la clôture sur le tableau de bord — sans ce correctif-ci, la donnée existait dans `data.json` mais restait invisible à l'écran.

**Corrigé** : `renderTrade(d)` préfixe maintenant chaque ligne de `d.exit_actions` (marquée `↩`) avant les lignes de trade habituelles — fonctionne pour un enregistrement `monitor_exits.py` (seulement des sorties) comme pour un enregistrement `agent.py` (sorties ET nouvelles tentatives d'entrée dans le même run). `outcomeBadge()` prend maintenant l'enregistrement complet (pas juste la chaîne `outcome`) pour distinguer un vrai `checked` de `monitor_exits.py` d'un badge vert "position closed" (ou jaune "would close (dry-run)" si `d.dry_run` est vrai) — plus besoin du badge générique gris "checked" qui ne disait rien. Vérifié avec un test Node qui charge le JS réel extrait du fichier (pas une réécriture séparée) et vérifie 7 cas : clôture réelle par `monitor_exits.py`, clôture simulée en dry-run, un run `agent.py` combinant une sortie ET une nouvelle entrée dans le même enregistrement, un jour "no_edge" sans rien à afficher, et un ancien enregistrement à plat (pré-24/08) toujours rendu correctement — les 7 passent. Revérifié aussi `node --check` (syntaxe propre) et l'équilibrage des balises HTML (zéro tag non fermé).

**Seizième passe "cherche encore" (24/08) — un vrai bug de robustesse trouvé dans `agent.py`, distinct des deux précédents (affichage), cette fois dans la boucle d'entrée elle-même :**

En comparant `evaluate_symbol()` (qui a son propre `try/except` explicite, avec un docstring qui explique précisément pourquoi : *"a single flaky symbol should cost that one symbol's chance today, not the whole day's chance across all three"*) à la boucle d'entrée juste en dessous (celle qui appelle `find_near_the_money_contract()`, `check_gates()`, `submit_paper_option_order()` pour chaque symbole tradeable) : cette deuxième boucle n'avait **aucune** protection équivalente. Or `find_near_the_money_contract()` appelle `get_last_price()` → `get_daily_bars()`, qui peut lever exactement le même genre d'exception que `evaluate_symbol()` protège déjà — y compris `DataQualityError`, ajouté PLUS TÔT dans cette même session (contrôle #63) comme nouvelle source d'exception sur cette fonction. Le principe avait déjà été écrit et justifié une fois dans le code, mais pas appliqué au deuxième endroit qui utilise la même fonction sous-jacente.

Conséquence concrète, si un seul symbole sur 2-4 déclenchait une erreur (data périmée, hoquet réseau CLI) en tentant l'entrée : l'exception remontait hors de `_run()`, n'était attrapée que par le `try/except` global de `main()`, qui (1) empêchait tout symbole restant dans la boucle d'être seulement tenté, même sains, et (2) — le plus grave — empêchait `record["trades"] = trades` de s'exécuter, donc **même les ordres déjà soumis avec succès plus tôt dans le même run auraient disparu de `decision_log.jsonl`**, pas juste mal étiquetés. Jamais déclenché en vrai (trouvé en relisant, pas en observant un crash), mais un vrai trou de résilience directement lié à un contrôle ajouté plus tôt aujourd'hui dans cette même session.

**Corrigé** : chaque itération de la boucle d'entrée est maintenant enveloppée dans son propre `try/except`, qui transforme n'importe quelle exception en `trade_record["outcome"] = "error"` (avec le détail de l'exception) et passe au symbole suivant — même philosophie que `evaluate_symbol()`, appliquée cohéremment aux deux endroits qui appellent la même fonction sous-jacente. `docs/index.html` mis à jour en même temps pour afficher le détail de l'erreur (`t.error`) au lieu du seul mot "error" nu dans la colonne Trade. Vérifié par `py_compile` sur les 12 fichiers `.py` du projet, et par un test simulé à 5 cas qui appelle réellement `agent.main()` (pas une réécriture séparée de la logique) avec deux symboles, le premier configuré pour lever une `DataQualityError` : (a) `main()` se termine sans lever, (b) le résultat agrégé reste `order_submitted` malgré l'échec du premier symbole, (c) `record["trades"]` contient bien les DEUX symboles, (d) le symbole en échec affiche `outcome="error"` avec le détail de l'exception, (e) le symbole suivant dans la boucle a bien été évalué et tradé normalement — les 5 cas passent.

**Dix-septième passe "cherche encore" (24/08) — même famille de principe (« un enregistrement cassé ne doit pas tout faire tomber »), trouvée cette fois dans `decision_log.py` :**

En pensant directement au scénario de crash que la passe précédente venait de creuser (un kill du process pile au mauvais moment) : `log_run()` écrit chaque enregistrement avec un seul `f.write(json.dumps(record) + "\n")`, mais ça reste deux étapes au niveau OS (écrire les octets, puis flush/close) — un crash exactement à ce moment-là peut laisser une dernière ligne tronquée, non parseable, dans `decision_log.jsonl`. Or `read_log()` faisait `[json.loads(line) for line in lines ...]` sans aucune protection : UNE SEULE ligne cassée aurait fait planter `read_log()` avec une `json.JSONDecodeError`, non rattrapée nulle part — et `publish_dashboard.py` l'appelle directement, sans son propre `try/except`. Résultat concret : une seule ligne corrompue (par exemple pile après un crash au moment même où l'idempotency guard de tout à l'heure a été conçu pour survivre) aurait bloqué la génération du tableau de bord public **pour tout le reste de la semaine du hackathon**, pas juste perdu cette seule entrée — jusqu'à ce que quelqu'un trouve et corrige la ligne à la main.

C'est exactement le même principe que ce projet applique déjà ailleurs (`evaluate_symbol()` isole chaque symbole, la boucle d'entrée d'`agent.py` isole maintenant chaque tentative depuis la passe précédente, `_total_committed` compte un `cost_basis` illisible comme 0\$ plutôt que de bloquer tout le calcul) — juste jamais appliqué à cet endroit précis, qui est pourtant le seul point où UNE ligne cassée pouvait geler TOUT le tableau de bord public, pas juste une décision.

**Corrigé** : `read_log()` parse maintenant chaque ligne dans son propre `try/except`, saute (avec un avertissement imprimé) toute ligne non parseable au lieu de laisser l'exception remonter, et continue avec les lignes suivantes. Vérifié par `py_compile` et un test à 4 cas : aucun fichier (liste vide, pas de crash), lignes bien formées (ordre le plus récent en premier respecté), une ligne corrompue au milieu de deux lignes valides (les deux valides ressortent, la corrompue est sautée avec un avertissement), et la limite (`limit=N`) toujours respectée même après avoir sauté une ligne cassée — les 4 cas passent.

**Dix-huitième passe "cherche encore" (24/08) — le même trou (pas de try/except par symbole autour de `get_daily_bars`), retrouvé cette fois dans les deux scripts d'analyse hors-ligne, pas dans l'agent live :**

Après avoir corrigé la boucle d'entrée d'`agent.py` (16e passe) contre exactement ce défaut, vérifié si le même défaut existait ailleurs dans le code — et oui : `backtest.py` et `compare_strategies.py` ont chacun leur propre boucle `for symbol in symbols: ... bars = alpaca_cli.get_daily_bars(symbol) ...` dans `main()`, **sans aucun `try/except`**. Une `DataQualityError` ou une `AlpacaCLIError` sur UN SEUL symbole (sur 4 dans l'univers par défaut) aurait fait planter le script entier — perdant les résultats déjà calculés pour tous les symboles précédents dans la boucle, et **le fichier de rapport (`BACKTEST_RESULTS.md` / `STRATEGY_COMPARISON.md`) n'aurait jamais été écrit du tout**, pas même partiellement. Ces deux scripts sont justement ceux que le brief terminal demande d'exécuter pour de vrai cette semaine contre les données réelles — un vrai risque, pas théorique.

**Corrigé** : même correctif que pour `agent.py`, appliqué aux deux scripts — chaque itération de la boucle est dans son propre `try/except`, un symbole en échec est sauté avec un message d'erreur imprimé, et le rapport est quand même écrit avec les symboles qui ont réussi (avec un message explicite si AUCUN symbole n'a réussi, plutôt qu'un rapport vide silencieux). Vérifié par `py_compile` et un test qui appelle réellement `backtest.main()` et `compare_strategies.main()` avec deux symboles (le premier configuré pour lever une `DataQualityError`), en interceptant `Path.write_text` pour capturer le contenu sans toucher au vrai fichier : les deux scripts se terminent sans lever, le rapport contient bien le symbole qui a réussi, et ne contient PAS le symbole en échec — vérifié pour les deux scripts. Fichiers réels du dépôt (`BACKTEST_RESULTS.md`) revérifiés après coup : intacts, contenu réel de SPY/QQQ/IWM du premier backtest de ce matin, non écrasés par le test.

**Dix-neuvième passe "cherche encore" (24/08) — cette fois pas du code, mais le document que les juges liront en premier : `README.md` lui-même était devenu faux, et structurellement cassé à un endroit :**

En relisant `README.md` de bout en bout (jamais fait dans son intégralité depuis les tout premiers correctifs de la journée) : deux problèmes réels, distincts.

1. **La section "## Status" mentait par obsolescence** : elle disait encore *"Not yet run end-to-end (blocked on both network access and CLI install...)"* — alors que `PLAN_SPRINT.md` documente depuis plusieurs heures un vrai run de bout en bout réussi (ordre paper réellement soumis et fermé, dashboard vérifié dans un vrai navigateur), plus quatre vrais écarts code/API trouvés et corrigés au passage. Un juge qui lit uniquement le README (le document qu'on attend qu'il lise, contrairement à `PLAN_SPRINT.md` qui est un journal de travail interne) en aurait conclu à tort que rien n'a jamais tourné pour de vrai. La section pointait aussi vers `BRIEF_TEST_AGENT_TERMINAL.md` (17h25) comme LE brief à suivre, alors que six briefs différents existent maintenant dans le dépôt et que `BRIEF_MULTI_POSITION_ET_COMPARAISON.md` est le seul tenu à jour en continu toute la journée.
2. **Un vrai bug de structure Markdown, préexistant, jamais remarqué** : la section "## Files" listait une partie des fichiers (`hindsight_guard.py` → `docs/index.html`), puis la section "## Hosted dashboard" s'intercalait, et à la toute fin de CETTE section — sans nouveau titre, juste après un paragraphe sur la vérification du navigateur — une deuxième liste de fichiers (`test_connection.py`, `config.py`, `backtest.py`, `momentum_strategy.py`, `compare_strategies.py`, `alpaca_client.py`) apparaissait, orpheline, comme si elle appartenait au tableau de bord. Un rendu Markdown normal aurait affiché un bloc de puces incohérent collé à un paragraphe sur un tout autre sujet — pas juste inélégant, franchement déroutant pour quiconque essaie de comprendre l'organisation du dépôt.

**Corrigé** : les deux moitiés de la liste de fichiers sont maintenant fusionnées sous "## Files", dans l'ordre. La section "## Status" dit maintenant honnêtement ce qui a vraiment tourné (compte dev, ordre réel soumis et fermé, dashboard vérifié en vrai) et ce qui reste vraiment à faire (le compte dédié jamais branché ; tous les contrôles ajoutés dans l'après-midi du 24/08 — multi-positions, plafond sectoriel, qualité des données, HALT, anti-doublon, coupe-circuit, `monitor_exits.py`, et tous les correctifs de robustesse trouvés dans les passes "cherche encore" suivantes — testés seulement avec des mocks, jamais contre l'API réelle). Les références au brief pointent maintenant vers `BRIEF_MULTI_POSITION_ET_COMPARAISON.md`, avec la liste des autres briefs devenus des instantanés dépassés. Un petit mot honnête laissé dans la section elle-même : ce README qui documente un projet anti-décalage-code/doc avait lui-même un décalage doc/réalité — cohérent avec le principe du projet appliqué à sa propre documentation, pas seulement à son code.

**Vingtième passe "cherche encore" (24/08) — un vrai défaut de logique trouvé dans le tout premier correctif de la journée (le "même-run API lag"), pas juste un bug de robustesse : un risque de double comptage, qui échoue du bon côté mais coûte quand même de vraies opportunités de trade :**

En repensant précisément à l'hypothèse posée par le tout premier correctif "même-run API lag" de ce matin (`already_committed_this_run` / `already_open_this_run`, qui suppose que l'API Alpaca est TOUJOURS en retard sur un ordre tout juste soumis, dans la même exécution) : rien ne garantit ça. Un ordre paper peut très bien se remplir et devenir visible dans `list_open_option_positions()` avant que le symbole suivant de la boucle d'`agent.py` ne soit vérifié — surtout avec seulement 2-3 appels API entre deux soumissions. Si ça arrive, la position déjà visible côté API se retrouvait comptée DEUX FOIS dans `check_gates()` : une fois via `open_positions` (l'API l'a rattrapée), une fois via l'ajout systématique et inconditionnel de `already_committed_this_run` (qui ne savait pas que l'API avait rattrapé). Le budget restant calculé pouvait donc paraître plus épuisé qu'il ne l'était réellement.

**Direction du bug, importante à préciser honnêtement** : ce double comptage échoue du BON côté — plus conservateur, jamais moins. Il ne pouvait jamais faire dépasser un plafond de risque réel (le sens dangereux), seulement refuser à tort un trade qui aurait été parfaitement sûr (le sens prudent). Mais "prudent" ne veut pas dire "gratuit" : sur une semaine jugée sur le P&L, refuser un vrai trade sûr pour une raison fantôme coûte quand même quelque chose, sans jamais s'expliquer dans les logs.

**Corrigé, pas juste documenté comme limite connue** : `check_gates()` prend maintenant `already_committed_this_run_by_underlying` (un dict `{underlying: dollars}`) et `already_open_this_run_underlyings` (un set) au lieu d'un total/compteur brut. À l'intérieur, chaque contribution de ce run n'est comptée QUE si son sous-jacent n'apparaît PAS déjà dans `open_positions` (donc si l'API ne l'a pas encore rattrapée) — si elle y apparaît, elle est déjà comptée via `open_positions` et l'ajout du montant "ce run" serait un doublon. Ce changement a aussi simplifié l'interface : `already_committed_this_run_by_sector` n'existe plus comme paramètre séparé — le total par secteur se dérive maintenant directement du même dict filtré, via `sector_of()`, à l'intérieur de `check_gates()`. `agent.py` a été mis à jour pour accumuler des dicts/sets par sous-jacent au lieu de compteurs plats.

**Vérifié en trois temps** : (1) un test qui reproduit précisément le scénario ORIGINAL que le premier correctif visait (API en retard, position pas encore visible) — toujours bloqué correctement, budget restant toujours réduit du bon montant, preuve que la protection d'origine n'a pas régressé ; (2) un test qui reproduit le NOUVEAU scénario (API déjà rattrapée, la même position visible ET encore présente dans le dict "ce run") — le budget restant est maintenant calculé correctement une seule fois (100 \$, pas -2800 \$/doublé), la branche de blocage "dur" (cap déjà atteint) n'est plus déclenchée à tort ; (3) un cas où le comptage correct (une seule fois) permet un trade qu'un double comptage aurait empêché à tort — le dimensionnement (`qty=2`) est vérifié précisément. Ensuite, la suite de régression complète du sprint (10 cas couvrant positions multiples, doublon de sous-jacent, plafond de positions, plafond total, plafond sectoriel, HALT, anti-doublon d'ordre, coupe-circuit, changement de compte) rejouée contre la nouvelle signature — tout passe. Et le test d'isolation d'exception de la 16e passe (`agent.main()` avec un symbole qui plante) revérifié aussi avec les nouveaux noms de paramètres — toujours correct. `py_compile` propre sur les 12 fichiers `.py`.

**Vingt-et-unième passe "cherche encore" (24/08) — le premier vrai bug de la journée qui échoue du MAUVAIS côté (dangereux, pas juste prudent), trouvé en relisant `_load_state()` avec un œil critique sur sa propre justification :**

`_load_state()` a son propre docstring qui dit : *"a process killed mid-write... is a real enough scenario that the whole agent shouldn't go down over it"* — et sur `state.json` corrompu (pas manquant, corrompu — un fichier existant mais illisible en JSON, exactement le genre de séquelle qu'un crash pile pendant l'écriture peut laisser), la fonction retournait simplement `{}`, comme pour un premier lancement jamais vu. Le problème : `_record_starting_equity()` traite "`starting_equity` absent de `state`" (ce qu'un fichier corrompu produit AUSSI) exactement comme "ce compte n'a jamais été vu" — et réinitialise automatiquement `starting_equity`, **`locked`**, et `consecutive_losses` à zéro/faux. Concrètement : si le verrou hebdomadaire de -3% était déjà déclenché (`locked: true`) et qu'un crash survient PLUS TARD dans la semaine pendant une autre écriture de `state.json` (par exemple juste après une clôture de position), le fichier corrompu résultant aurait fait croire à l'agent, au prochain run, que le compte n'a jamais eu de verrou du tout — **levant silencieusement une protection de sécurité active**, exactement le contraire de ce que "fail-safe" veut dire. Tous les autres bugs trouvés aujourd'hui (le double comptage de la 20e passe compris) échouaient du bon côté — trop prudent, jamais dangereux. Celui-ci est le premier à échouer du mauvais côté.

**Corrigé** : `_load_state()` distingue maintenant "fichier absent" (`{}`, vraiment un premier lancement, comportement inchangé) de "fichier présent mais corrompu" (retourne un sentinel `{"_corrupted": True}`). `check_gates()` vérifie ce sentinel EN PREMIER, juste après avoir chargé l'état et AVANT tout appel à `_record_starting_equity()` — s'il est présent, refuse immédiatement toute nouvelle entrée avec une raison explicite, sans jamais réécrire `state.json` (le fichier reste corrompu sur disque, intact, jusqu'à ce qu'un humain le supprime ou le répare à la main — pas de "réparation" silencieuse). `manage_exits()` reste volontairement non affecté (les sorties continuent, même asymétrie que le HALT et le verrou hebdo — une corruption de l'état ne doit jamais empêcher de fermer une position déjà ouverte).

**Vérifié à 6 cas** : (A) un `state.json` qui avait `locked: true` puis se corrompt — refuse bien les nouvelles entrées, avec "corrupted" dans la raison ; (A2) le fichier sur disque reste inchangé, jamais silencieusement réécrit ; (B) `manage_exits()` tourne normalement malgré la corruption ; (C) un `state.json` réellement ABSENT (premier lancement, pas corrompu) démarre toujours frais normalement — aucune régression ; (D) un humain qui supprime le fichier corrompu à la main permet bien un nouveau départ propre au run suivant. Puis toute la suite de régression du sprint (11 cas, positions multiples + double comptage + HALT + idempotency + coupe-circuit + changement de compte) rejouée avec ce correctif en place — tout passe encore.

**Vingt-deuxième passe "cherche encore" (24/08) — trouvé immédiatement en relisant `manage_exits()` juste après avoir corrigé `check_gates()` pour la même famille de trou : celui-ci est probablement le plus important de toute la journée, parce qu'il est dans la fonction qui ferme réellement les positions perdantes :**

Même schéma que toute la journée (isolation d'exception par élément d'une boucle, déjà appliquée à `evaluate_symbol()`, la boucle d'entrée d'`agent.py`, `backtest.py`, `compare_strategies.py`) — mais cette fois-ci **manquante dans `manage_exits()`**, la fonction qui parcourt CHAQUE position ouverte (jusqu'à `MAX_OPEN_POSITIONS` = 4 depuis le passage au multi-positions) et appelle `alpaca_cli.close_position(symbol)` sans aucun `try/except` autour. Si la fermeture d'UNE position échoue (hoquet réseau transitoire, appel CLI qui échoue, une position déjà fermée par ailleurs à cause d'une course avec une fermeture manuelle) — l'exception remonte immédiatement hors de `manage_exits()`, **et toute position suivante dans la même boucle n'est jamais vérifiée ni fermée ce run-là**, même si elle a elle aussi franchi son seuil de +50%/-50%.

**C'est le premier bug de la journée, avec la corruption de `state.json`, à échouer du mauvais côté** — pas "refuse un trade sûr par excès de prudence" (comme le double comptage), mais littéralement "une vraie position perdante peut rester ouverte, non gérée, à cause d'un problème sur une AUTRE position complètement indépendante fermée juste avant dans la même boucle." C'est exactement le trou que `monitor_exits.py` a été construit pour combler (voir son propre docstring : *"a position that blows past its -50% stop-loss... would sit open, unmanaged"*) — sauf que la fonction qu'il appelle avait elle-même ce trou, invisible jusqu'à cette relecture.

**Corrigé** : chaque tentative de fermeture est maintenant dans son propre `try/except` à l'intérieur de la boucle de `manage_exits()` — une position en échec produit une ligne `"ERROR managing this position (...) — left open, check manually"` et la boucle continue avec la position suivante, qui reçoit sa vraie chance d'être vérifiée et fermée. Vérifié avec un test qui reproduit exactement le scénario dangereux : deux positions ouvertes, la première (-60%, doit fermer sur stop-loss) configurée pour faire planter `close_position()`, la seconde (+55%, doit fermer sur take-profit) juste après dans la boucle — les 3 assertions passent : les deux tentatives de fermeture sont bien appelées (pas d'arrêt après l'échec de la première), l'erreur de la première est rapportée clairement, et **la seconde position se ferme quand même correctement sur son propre take-profit** malgré l'échec de la première. Puis toute la suite de régression du sprint (13 cas au total maintenant, avec ce nouveau cas et celui de la corruption de `state.json` inclus) rejouée — tout passe. `py_compile` propre.

**Vingt-troisième passe "cherche encore" (24/08) — un vrai défaut trouvé dans MON PROPRE correctif de la passe précédente, quelques minutes plus tôt seulement : le principe "chasse-récidive" appliqué à mon propre travail, pas seulement au code écrit hier :**

En relisant le `try/except` tout juste ajouté à `manage_exits()` (22e passe) avec un œil critique : à l'intérieur du bloc `try`, `alpaca_cli.close_position(symbol)` (l'ordre de fermeture réel) et `_record_exit_outcome(is_win=...)` (juste la mise à jour du compteur de pertes consécutives dans `state.json`) étaient dans le MÊME bloc `try`. Si `close_position()` réussissait pour de vrai (la position EST fermée) mais que `_record_exit_outcome()` échouait ensuite (par exemple un problème d'écriture disque sur `state.json`, ou le même genre de corruption traité à la passe 21) — le `except` que je venais d'ajouter aurait rapporté `"ERROR managing this position ... — left open, check manually"`, **alors que la position était réellement déjà fermée**. Sur le seul événement que ce projet tient le plus à rapporter honnêtement (un stop-loss réel qui se déclenche), ça aurait été non seulement inutile mais activement trompeur — Spap aurait pu croire qu'un stop-loss n'a pas fonctionné alors qu'il a parfaitement fonctionné, ou intervenir manuellement sur une position déjà soldée.

**Corrigé** : `_record_exit_outcome()` est maintenant dans son propre `try/except` INTERNE, séparé de celui qui protège `close_position()`. Si la fermeture elle-même échoue, le comportement de la 22e passe reste inchangé ("left open, check manually"). Si la fermeture réussit mais que seule la mise à jour du compteur échoue, l'action rapportée reste `"CLOSED — ..."` avec une note honnête ajoutée ("consecutive-loss count NOT updated: ...") au lieu d'être noyée dans un message d'erreur générique qui prétend à tort que rien n'a été fermé. Vérifié à 2 cas : (1) fermeture réussie + bookkeeping en échec → toujours rapporté "CLOSED", jamais "left open", avec la note honnête sur le compteur non mis à jour ; (2) la fermeture elle-même en échec (scénario d'origine de la 22e passe) → toujours rapporté "left open, check manually" comme avant, la distinction n'a pas régressé. Puis la suite de régression complète du sprint (14 cas) rejouée avec ce correctif en place — tout passe.

Cette passe ne vient pas d'une relecture de code déjà "ancien" (écrit plus tôt dans la journée) mais d'une relecture immédiate de mon propre changement, minutes après l'avoir écrit — cohérent avec la discipline déjà établie ce sprint (revérifier après tout changement structurel, pas seulement faire confiance parce que ça vient d'être écrit et que ça "a l'air" correct).

---

## 🟢 24/08 (Cowork, en réponse à `BRIEF_DEBLOQUER_MONITOR_ET_KICKOFF.md`) — points B4 et B5 traités par lecture, README resynchronisé

*Cowork n'a pas d'accès terminal fiable ni aux réglages système du Mac — le blocage réel du brief (TCC de macOS sur `~/Desktop`, point A) reste entièrement pour la prochaine session terminal. Ce qui suit couvre seulement ce qui est faisable par simple lecture/écriture de fichiers.*

**Point B5 (relire le chemin de re-calibrage, sans l'exécuter) — confirmé par lecture directe de `risk_gates.py`, lignes 258-270** : `_record_starting_equity()` déclenche sur `state.get("account_id") != account_id or "starting_equity" not in state`, et réinitialise bien les **quatre** champs demandés dans le même bloc : `state["starting_equity"]` (ligne 266), `state["locked"] = False` (267), `state["traded_today"] = {...}` (269), `state["consecutive_losses"] = 0` (270). Les quatre sont couverts, dans la même transaction logique — pas de champ oublié. `account_id` comparé ici est l'UUID interne (`account.get("id")`, ligne 607), pas l'`account_number` `PA...` — sans importance pour la détection du changement de compte (un UUID différent suffit à déclencher le reset), seulement pour l'affichage, déjà traité séparément (6e/7e passe).

**Point B4 (procédure de bascule écrite comme liste d'étapes exécutable) — elle ne l'était pas, et un vrai trou trouvé en la rédigeant** : `config.py` charge `.env` en dur (`load_dotenv(Path(__file__).parent / ".env")`, ligne 18) — **il n'existe aucun mécanisme dans le code pour charger `.env.hackathon` à la place**. Rien dans `PLAN_SPRINT.md` ni ailleurs ne documentait donc concrètement *comment* basculer, seulement *qu'il faudra* basculer. Sous la pression du kickoff, un remplacement de fichier improvisé sans sauvegarde écraserait silencieusement les clés du compte de dev. Procédure écrite maintenant, vérifiée compatible avec `.gitignore` (`.env.*` couvre bien un fichier de sauvegarde nommé `.env.dev.bak`) :

1. `cd ~/Desktop/CERVEAU/hindsight-alpha` (ou le chemin réel une fois l'issue TCC du point A réglée).
2. `cp .env .env.dev.bak` — sauvegarde le compte de dev avant tout, jamais committé (couvert par la règle `.env.*`).
3. `cp .env.hackathon .env` — bascule effective.
4. `python test_connection.py` — attendu : `account_number` affiche `PA3K8MP3MF0U`, plus l'UUID ou le numéro du compte de dev.
5. `python agent.py --dry-run` — un seul run, et lire `state.json` juste après : `account_id` doit avoir changé, `starting_equity` re-basé sur l'équité réelle du compte dédié, `locked: false`, `traded_today` vide, `consecutive_losses: 0` — exactement les quatre champs confirmés au point B5 ci-dessus. Ne pas passer en mode réel avant d'avoir vu ces quatre valeurs correctes.
6. Seulement alors, retirer `--dry-run` pour le premier vrai run de la semaine du hackathon.
7. Rollback si besoin, à tout moment : `cp .env.dev.bak .env` restaure le compte de dev sans rien perdre — `.env.hackathon` et la sauvegarde restent tous deux intacts quoi qu'il arrive.

**README.md resynchronisé au passage** : la section "## Status" citait encore l'ancien brief (`BRIEF_MULTI_POSITION_ET_COMPARAISON.md`) comme handoff courant et disait "not yet run against the live API" pour des contrôles qui, d'après ce brief, ont depuis tourné pour de vrai (ordre rempli, HALT vérifié en direct, anti-doublon déclenché, `hindsight_guard` ayant rejeté XLK en direct, cinq bugs de plus trouvés contre l'API réelle). Même famille d'écart doc/réalité que la 19e passe, retrouvée une deuxième fois au même endroit précis. Corrigé : statut à jour, pointeur vers `BRIEF_DEBLOQUER_MONITOR_ET_KICKOFF.md` comme brief courant, liste des huit briefs maintenant tous nommés (les sept précédents marqués dépassés).

**Non traité ici, explicitement hors de portée de Cowork** : point A (déblocage TCC/launchd — nécessite Réglages Système, main humaine) et point B6 (garder ou fermer la position de test `SPY260831P00764000` sur le compte de dev — décision de Spap, et de toute façon une fermeture réelle nécessite le vrai CLI). Les deux restent tels quels dans `BRIEF_DEBLOQUER_MONITOR_ET_KICKOFF.md`, prêts pour la prochaine session terminal.

---

# 🏁 CLÔTURE DU 24/08 — l'état réel en fin de journée

*Ajoutée en fin de fichier, exprès : les sections « cherche encore » ci-dessus ont été insérées au fil de l'eau, certaines en haut, d'autres au milieu, et ne se lisent plus dans l'ordre. Celle-ci ne remplace rien — c'est la synthèse à lire en premier pour savoir où on en est.*

## 🔴 Le dépôt a changé d'emplacement

**`~/Desktop/CERVEAU/hindsight-alpha` → `~/hindsight-alpha`.** Décidé par Spap le 24/08 au soir pour lever le blocage TCC. Le dépôt GitHub, la remote et Pages ne changent pas. Si un chemin en dur traîne quelque part, c'est celui-là qu'il faut corriger.

## Ce qui a tourné contre l'API RÉELLE (pas en mocks)

Pipeline complet de bout en bout · ordre paper **`2e7ba582-3784-4c80-8abb-d1e4eb0a79eb`** (2 puts `SPY260831P00764000`, rempli à 4,69 $) · `hindsight_guard` a réellement **rejeté XLK** en direct · l'interrupteur `HALT` bloque les entrées sans bloquer les sorties · l'anti-double-soumission se déclenche · dépôt public et GitHub Pages en ligne et vérifiés visuellement · backtest et `compare_strategies` exécutés sur données réelles.

## Bugs : 5 trouvés et corrigés, tous de la même famille

*Chacun reproduit par un test AVANT d'être déclaré. Racine commune : **le code protège soigneusement l'action, puis traite sa trace comme un détail**.*

| # | défaut | direction |
|---|---|---|
| ① | accumulateurs perdus si la comptabilité échoue après soumission | 🔴 sur-exposition |
| ② | écrasement d'un `state.json` corrompu par le chemin de sortie | 🟠 forensique |
| ③ | `_save_state` non atomique (tronque avant d'écrire) | 🔴 indisponibilité |
| ④ | échec de fermeture jamais journalisé | 🔴 angle mort |
| ⑤ | trace d'ordre perdue si `log_run` échoue | 🟠 angle mort |

**Audités et déclarés sains** *(vérifiés, pas supposés)* : contrôle de qualité des données · `hindsight_guard` · `decision_log.read_log` · `publish_dashboard` · le chemin « commit ok, push échoué » · et l'alignement d'indices de `vol_strategy` (invariant désormais écrit dans le code).

⚠️ **Et 3 FAUX positifs de mon propre fait**, tous nés de mes montages de test ou d'un raisonnement algébrique, jamais du code. **Le prochain lecteur doit vérifier mes conclusions, pas les reprendre.**

## 🟢 `monitor_exits` : DÉBLOQUÉ

**Cause, prouvée par sonde contrôlée** : macOS (TCC) refusait à tout process lancé par launchd l'accès à `~/Desktop`. Ni un chemin, ni un droit de fichier, ni le `PATH`.

**Résolu par le déplacement du dépôt.** La même sonde qui renvoyait `REFUSE` depuis `~/Desktop` renvoie **`LISIBLE`** depuis `~/hindsight-alpha`, et la tâche launchd exécute réellement le script (zéro `Operation not permitted` dans `monitor_exits.log`, le script produit sa propre sortie). Tâche chargée : **140 créneaux, lun-ven, 15h–21h45 locale** = les heures de marché US, avec le `PATH` incluant `~/.local/bin`.

⚠️ *Piège déjà payé, à ne pas réintroduire : le cron documenté à l'origine (`*/15 9-16`) était en heure **locale**, pas ET — il aurait tourné 03h–10h ET, soit 30 minutes utiles sur 6h30.*

## Position de test : GARDÉE, délibérément

**Une seule position ouverte** sur le compte de dev : `SPY260831P00764000`, qty 2, coût 938 $, ~+3 %. *(Le `traded_today: ["SPY"]` de `state.json` correspond à ce même ordre, pas à un second run — vérifié.)*

**Gardée exprès** : elle donne au moniteur fraîchement débloqué quelque chose de réel à surveiller pendant les 3 jours avant le kickoff. C'est la seule façon de vérifier le chemin de sortie en conditions réelles avant que ça compte. Échéance 31/08, sans effet sur la soumission (mauvais compte).

## `StateNotPersisted` : pas de rattrapage nommé, et c'est testé

Les deux points de levée ont été **reproduits**. Le message n'est pas noyé : côté entrée il atterrit sous une **clé dédiée** (`record_order_submitted_failed`), côté sortie il est **accolé à la ligne d'action** (« CLOSED — stop-loss hit (-60,0 %) (consecutive-loss count NOT updated: StateNotPersisted: …) »). Un `except` nommé dupliquerait le traitement sans rien apporter. Raisonnement écrit dans la docstring de la classe.

## Ce qui reste ouvert pour le 28

🔴 **Basculer sur le compte dédié `PA3K8MP3MF0U`** (`.env.hackathon`) — **jamais touché à ce jour, et à ne pas toucher avant le kickoff**. Le re-calibrage automatique sur changement d'`account_id` couvre `starting_equity`, `locked`, `traded_today` et `consecutive_losses` ; testé en mocks uniquement.

⬜ **Décision de méthode qui appartient à Spap** : `vol_strategy` devance `momentum` sur le Sharpe in-sample des 4 symboles, mais `momentum` est plus propre côté garde-fou (4/4 contre 3/4). Aucune bascule décidée.

⬜ **Deux améliorations identifiées, non faites** *(changements de comportement, pas du nettoyage)* : dédoublonner les échecs persistants dans le journal (une panne structurelle serait journalisée ~26×/jour et évincerait le dashboard public en ~1,2 jour), et remplacer le `List[str]` de `manage_exits` par un type structuré — **c'est le dernier endroit du code où une chaîne lisible par un humain décide du flux de contrôle**.

---

## 🟢 24/08 (Cowork) — les deux améliorations laissées ouvertes, faites : type structuré + dédoublonnage

*Fait depuis Cowork sur `~/hindsight-alpha` (accès reconnecté après le déplacement) pendant qu'une session terminal semblait avoir déjà tourné dessus (`ad8609e`, arbre propre au moment de commencer) — code et tests uniquement, aucune commande git lancée ici, comme d'habitude.*

**`risk_gates.manage_exits()` retourne maintenant `List[ExitAction]`**, un dataclass (`symbol`, `kind: ExitKind`, `pnl_pct`, `label`, `consecutive_losses`, `bookkeeping_error`, `error`) au lieu de chaînes brutes. `ExitKind` est un `str, Enum` (`holding` / `closed` / `would_close` / `unreadable` / `error`) — comparer `action.kind == "holding"` marche sans importer la classe. `str(action)` reproduit **byte pour byte** les cinq formats de phrase d'origine (vérifié par test, pas par relecture) — `monitor_exits.log` et l'affichage terminal ne changent pas de forme. `to_dict()` produit un dict JSON-sérialisable avec un champ `text` (la même phrase) plus les champs structurés — c'est ça qui part dans `decision_log.jsonl`, jamais l'objet lui-même. `agent.py` et `monitor_exits.py` mis à jour pour appeler `.to_dict()` avant d'assigner à `record["exit_actions"]`. `docs/index.html` mis à jour pour accepter les deux formes (`typeof a === "string" ? a : a.text`) — `decision_log.jsonl` est committé, jamais réécrit, donc les entrées d'avant ce changement restent des chaînes brutes pour toujours.

**Dédoublonnage des échecs persistants, dans `monitor_exits.py`** : `_filter_for_logging()` compare la signature de chaque échec (`symbol`, `kind`, `error`) contre un nouveau fichier `monitor_exits_dedup.json` (gitignored, séparé de `state.json` — délibérément, pour ne pas mélanger cette bookkeeping cosmétique avec l'état risque qui, lui, refuse toute écriture une fois corrompu). Une fermeture (`CLOSED`/`WOULD_CLOSE`) est toujours journalisée — elle ne peut pas se répéter par construction. Un échec est journalisé la première fois, puis au plus une fois par heure (`HEARTBEAT_SECONDS = 3600`) tant qu'il persiste inchangé ; s'il disparaît, sa signature est purgée, donc une récidive plus tard est traitée comme neuve, pas silencieusement supprimée pour toujours.

**Vérifié, pas juste écrit** : suite de tests (supprimée après coup, comme d'habitude) reproduisant le scénario concret cité dans le brief précédent — 26 checks simulés sur ~6h30 de séance avec le même échec `unreadable` à chaque fois. Sans filtre : 26 écritures. Avec : **7**, à la fréquence attendue (1re fois immédiatement, puis toutes les heures). Testé aussi : une fermeture jamais dédoublonnée même répétée immédiatement ; une signature purgée quand l'échec disparaît puis re-déclenchée immédiatement dès qu'il revient ; `manage_exits()` rejoué pour de vrai (pas réimplémenté) contre des positions mockées confirme que `close_position()` n'est appelé que sur la position qui dépasse vraiment son seuil et que les 7 formats de phrase (dont les deux variantes de `CLOSED`, gain et perte, bookkeeping réussi ou en échec) matchent exactement l'original ; `agent.py`, exécuté réellement avec `manage_exits()` mocké au niveau `alpaca_cli`, confirme que `record["exit_actions"]` sérialise en JSON sans erreur ; `docs/index.html` (le vrai `<script>` extrait, pas une réécriture) confirme qu'une ancienne entrée en chaîne brute ET une nouvelle entrée en dict s'affichent toutes les deux correctement, sans jamais produire `[object Object]`. `state.json`, `HALT` et le nouveau `monitor_exits_dedup.json` du vrai projet vérifiés intacts après coup. `py_compile` propre sur les 9 fichiers `.py` du dépôt.

**Non fait ici, comme toujours** : aucun `git add`/`commit`/`push` — les fichiers modifiés (`risk_gates.py`, `monitor_exits.py`, `agent.py`, `docs/index.html`, `.gitignore`) restent tels quels sur disque pour la prochaine session terminal.

---

## 🔴 24/08 (Cowork) — cherche encore : un vrai bug trouvé dans MON PROPRE code, minutes après l'avoir écrit

**`ExitAction.failure_signature()` (juste ajoutée pour le dédoublonnage ci-dessus) utilisait le texte brut de l'exception comme identité de signature — `self.error` en entier.** Tous mes tests passaient parce qu'ils utilisaient des messages d'erreur statiques, inventés à la main. En relisant `alpaca_cli.py` pour vérifier honnêtement à quoi ressemble une vraie erreur (`_run_cli`, ligne ~101) : `AlpacaCLIError` est construit avec `result.stderr.strip() or result.stdout.strip()` — pour une vraie panne réseau/API, ce texte contient presque toujours du contenu qui varie d'un appel à l'autre (timing de connexion, détail de socket) **même quand c'est exactement le même problème qui persiste**.

**Reproduit avant de corriger** : deux `ExitAction` construites avec deux messages représentant la MÊME panne réseau sous-jacente, différant seulement par le timing exact (`"...timeout after 30.001s"` vs `"...timeout after 30.014s"`) — `failure_signature()` renvoyait deux tuples différents. Conséquence concrète : contre une vraie panne persistante, le dédoublonnage tout juste écrit (voir passe précédente) **ne se serait jamais déclenché** — chaque vérification à 15 minutes d'intervalle aurait semblé être une "nouvelle" panne, et le problème de saturation du journal que ce dédoublonnage existe pour corriger serait resté entier, silencieusement, malgré un code qui a l'air correct et une suite de tests entièrement verte.

**Corrigé** : la signature n'utilise plus que le préfixe avant le premier `": "` du message d'erreur (le nom de la classe d'exception, `type(e).__name__`, format que tous les points de levée du dépôt suivent déjà — vérifié par `grep`, pas supposé), pas le message entier. `AlpacaCLIError: dial tcp ...: timeout after 30.001s` et `AlpacaCLIError: dial tcp ...: timeout after 30.014s` partagent maintenant la même signature ; `AlpacaCLIError` et `DataQualityError` restent bien distincts ; le message fixe et sans deux-points d'`UNREADABLE` n'est pas affecté.

**Vérifié** : le cas reproduit ci-dessus donne maintenant la même signature pour les deux occurrences ; deux classes d'exception différentes restent différenciées ; deux symboles différents ne collisionnent jamais ; le scénario complet de la passe précédente (26 checks simulés sur ~6h30) rejoué avec un message d'erreur qui **change à chaque appel** (comme en vrai) — toujours seulement 7 écritures sur 26, à la cadence attendue, au lieu de 26 si le bug n'avait pas été trouvé. `py_compile` propre.

Même famille que les bugs trouvés plus tôt aujourd'hui dans du code écrit par d'autres passes — cette fois trouvé par relecture immédiate de mon propre travail, dans la continuité de la 23e passe du matin.

---

## 🟢 24/08 (Cowork, sur demande explicite) — `publish_dashboard.py` écrit `docs/data.json` de façon atomique

**Revisite une décision déjà prise et journalisée** (3e passe "cherche encore" du matin : "même forme que le bug `state.json` (④), mais exposition bien moindre — signalé, pas corrigé"). Ce raisonnement portait sur la PROBABILITÉ d'une écriture tronquée ici, pas sur la CONSÉQUENCE si elle survient — et la conséquence est réelle : contrairement à `state.json` (du code que ce projet exécute lui-même, protégé par le sentinel `_corrupted`), `docs/data.json` est du contenu qu'un navigateur de juge parse avec `JSON.parse()` via GitHub Pages. Un fichier tronqué ici casse le dashboard public pour tout visiteur jusqu'au prochain run réussi — pas une histoire de forensique interne.

**Même mécanisme que le bug `state.json`, reprouvé sur ce fichier précis** : `Path.write_text()` ouvre en mode `"w"`, qui tronque à 0 octet avant d'écrire quoi que ce soit — sondé directement sur `docs/data.json` (40 octets → 0 dès l'`open()`, avant tout `write()`).

**Corrigé avec le même correctif que `_save_state()`** (`risk_gates.py`) : écriture dans un fichier temporaire du même répertoire (`docs/data.json.tmp`, ajouté au `.gitignore`), `fsync`, puis `os.replace()` — atomique sur POSIX, un lecteur ne voit jamais qu'un ancien snapshot complet ou un nouveau snapshot complet, jamais un fichier à moitié écrit.

**Vérifié en reproduisant le crash, pas en relisant le code** : une écriture normale reste un JSON valide, sans résidu `.tmp` ; un crash simulé pendant l'écriture (`os.fsync` patché pour lever une exception, au milieu de la fenêtre dangereuse) laisse `docs/data.json` **strictement inchangé** — toujours l'ancien snapshot valide, encore parseable, sans fichier `.tmp` orphelin. `main()` avec `--git-push` non demandé rejoué de bout en bout contre des mocks (`alpaca_cli.get_account/list_positions`, `decision_log.read_log`) confirme que le snapshot réel contient bien `account_number`. Le vrai `docs/data.json` du dépôt vérifié intact après coup (`git status --short` ne le montre pas modifié). `py_compile` propre.

---

## 🟢 24/08 (nuit, session terminal) — les trois passes Cowork vérifiées contre l'API réelle

*Tout ce qui suit n'avait tourné qu'en mocks. Vérifié ici en conditions réelles, sur le compte de dev, depuis le nouveau chemin `~/hindsight-alpha`.*

**① Type structuré `ExitAction` — les 5 formats de phrase reproduits AU CARACTÈRE PRÈS.** Testés un par un contre les chaînes d'origine : `HOLDING`, `CLOSED`, `WOULD_CLOSE`, `UNREADABLE`, `ERROR`, plus la variante « fermeture + échec de comptabilité ». Confirmé en direct sur la vraie position ouverte : `SPY260831P00764000: holding (+2.8%, thresholds are +50%/-50%)` — **identique à la sortie relevée avant le refactor**. `to_dict()` sérialisable, et le journal contient bien **les deux formes en même temps** (7 anciennes chaînes brutes, 1 nouveau dict) : le JS du dashboard accepte les deux, vérifié visuellement, **zéro erreur console**.

**② Dédoublonnage — et surtout, le bug de signature vraiment corrigé.** Testé avec deux messages `AlpacaCLIError` réalistes ne différant que par le timing réseau (`i/o timeout after 30.114s` vs `29.887s`) — le cas exact où l'ancienne version n'aurait jamais dédoublonné. **Signature obtenue : `('SPY260831P00764000', 'error', 'AlpacaCLIError')` — identique pour les deux.** Battement horaire vérifié sur une horloge simulée : journalisé à t=0, **muet à 15 et 45 min**, re-journalisé à 61 min. Une panne d'une **autre** classe (`DataQualityError`) reste journalisée ; une ligne `holding` routinière ne l'est jamais ; une vraie fermeture l'est toujours.

⚠️ **Le dédoublonnage n'a PAS été observé sur une panne réelle** — aucune n'est survenue pendant la séance, et `monitor_exits_dedup.json` est resté à `{}`, ce qui est correct : il ne vise que les échecs persistants, et une position en `holding` n'est de toute façon jamais journalisée. Mécanisme prouvé sur des données réalistes, pas sur une panne vécue.

**③ Écriture atomique de `docs/data.json`** — `temp + fsync + os.replace`, comme `state.json`. Régénéré, JSON valide, aucun résidu `.tmp`. *Ce correctif avait été écarté dans une passe précédente au motif que l'exposition était faible ; l'argument portait sur la **probabilité**, pas sur la **conséquence** — un fichier tronqué ici casse le dashboard public pour tout visiteur, alors que `state.json` est protégé par le sentinel `_corrupted`. Reconsidéré à raison.*

**Non-régression :** `agent.py --dry-run` (évaluation forcée, marché fermé) rend exactement les mêmes verdicts qu'avant — SPY tradeable, GLD et XLV écartés pour volatilité non bon marché, **XLK toujours rejeté par `hindsight_guard`**. `monitor_exits --dry-run` propre. 14 fichiers compilent.

**Position de test :** toujours ouverte, `SPY260831P00764000`, qty 2, ~+2,8 %. Gardée, inchangé.

⚠️ **Et une note sur ma propre fiabilité :** quatre fois dans cette séance, un « 🔴 » affiché venait de **mon montage de test** (mauvais noms d'enum, mauvais noms de champ `plpc`/`pnl_pct`, mauvaise signature d'appel), jamais du code. À chaque fois relu et refait avant de conclure. **Le lecteur suivant doit vérifier mes verdicts plutôt que les reprendre.**

---

## 🔴 24/08 (nuit, « cherche encore » sur le code Cowork) — 6ᵉ bug, même famille que les cinq autres

*Les trois passes Cowork avaient été **vérifiées conformes** plus tôt dans la séance — pas **chassées**. ~347 lignes neuves, écrites en mocks. Une passe dédiée les a auditées.*

### ⑥ La comptabilité de dédoublonnage pouvait tuer le moniteur — et emporter l'échec qu'elle était en train d'évaluer

`_filter_for_logging()` garde `except ValueError` sur `datetime.fromisoformat(...)`, commenté *« unparseable timestamp -- don't get stuck silent »*. L'intention est claire : **jamais laisser un mauvais horodatage casser ça**. Mais un horodatage **naïf** (sans fuseau) soustrait d'un `now` *aware* lève un **`TypeError`**, pas un `ValueError` — non attrapé.

**Reproduit :** avec un horodatage naïf dans `monitor_exits_dedup.json`, **le run entier meurt**, et **l'échec de fermeture en cours d'évaluation n'est jamais journalisé**. Le tout depuis le `finally`, donc en masquant aussi le vrai résultat.

⚠️ **Atteignabilité honnête : le code actuel n'écrit que des horodatages *aware*.** Le chemin exige un fichier écrit par une autre version ou édité à la main. **C'est un trou de robustesse latent, pas un bug vivant** — je ne le présente pas comme plus grave qu'il n'est.

**Corrigé à deux niveaux, pas un :**
1. Le garde local accepte `(ValueError, TypeError)` — les deux formes de mauvais horodatage retombent sur « traiter comme dû ».
2. **Surtout** : tout le bloc de dédoublonnage est enveloppé. Cette comptabilité est **explicitement non critique** (sa propre docstring dit qu'une mauvaise lecture coûte au pire une ligne de log en trop) — et pourtant elle siégeait dans le `finally` du seul job dont la raison d'être est la discipline de sortie. En cas de panne, elle dégrade désormais vers *« journaliser tout ce qui n'est pas routinier »* : plus bruyant, **jamais muet**.

**Vérifié sur 7 états du fichier** : naïf, illisible, JSON corrompu, absent, aware récent *(throttle actif — non-régression)*, aware vieux *(battement dû)*, et une panne d'écriture *(l'enveloppe externe se déclenche, avertit, et journalise quand même — elle n'est pas du code mort)*.

### 🟢 Audité et innocenté dans la même passe

**L'écriture non atomique de `monitor_exits_dedup.json`** — mon hypothèse de départ, et elle était fausse pour une bonne raison : le code **justifie explicitement** le choix. Un fichier corrompu retombe sur `{}` (non collant, contrairement à `state.json`), donc au pire une ligne de log en trop, et le run suivant le réécrit. Raisonné, pas oublié.

*Note : le « 🔴 avertissement non émis » de mon premier test était correct — le cas naïf est désormais traité par le garde **local**, donc n'atteint jamais l'enveloppe externe. Mon test cherchait au mauvais endroit.*

---

## 🟢 24/08 (nuit) — le re-calibrage de compte, PROUVÉ contre l'API réelle

*Le dernier point vraiment ouvert avant le 28. Fermé — mais pas par la procédure prévue.*

### 🔴 D'abord : la procédure du brief n'aurait rien testé

Le brief supposait que `python agent.py --dry-run` suffisait à exercer le re-calibrage (« `check_gates()` lit l'équité réelle que `--dry-run` n'empêche pas »). **Vérifié : c'est faux.** En `--dry-run`, l'agent s'arrête à *« not looking up contracts or submitting orders »* — **`check_gates()` n'est jamais appelé, donc `_record_starting_equity()` non plus**. Testé en forçant un `account_id` bidon dans `state.json` puis en lançant un dry-run : le fichier est resté **inchangé**.

**Conséquence : même avec un troisième compte paper créé, les étapes 6 et 7 auraient montré un `state.json` figé** — et on en aurait conclu soit que le re-calibrage est cassé, soit, pire, qu'il fonctionne alors qu'on ne l'avait pas exercé.

### Ce qui a été fait à la place — et qui prouve davantage

**Aucun compte supplémentaire n'était nécessaire.** Le re-calibrage se déclenche sur un **changement d'`account_id`**, pas sur un changement de clés : il suffit d'un `account_id` différent dans `state.json` et d'un appel **réel** à `check_gates()`, qui lit l'équité **live** via l'API. *(Créer un compte et générer des clés API sont par ailleurs des actions que Claude ne fait pas.)*

**① Aller — état hérité d'un « autre compte », avec un verrou ACTIF et 3 pertes d'affilée** *(plus sévère que le brief : un compte neuf n'aurait rien eu à effacer)* :

| champ | avant | après | |
|---|---|---|---|
| `account_id` | `11111111-…-555555555555` | `523f7f05-…` *(UUID réel)* | 🟢 |
| `starting_equity` | 12 345,0 | **99 901,84** *(équité LIVE, pas un report)* | 🟢 |
| `locked` | **true** | false *(+ `lock_reason` effacé)* | 🟢 |
| `traded_today` | `[SPY, GLD, XLK]` | `[]` | 🟢 |
| `consecutive_losses` | **3** | 0 | 🟢 |

La NOTE de re-calibrage est bien émise, nommant les deux comptes.

**② La moitié que le brief ne couvrait pas — MÊME compte, verrou LÉGITIME** : les cinq champs sont **conservés**, aucune NOTE émise, et `check_gates` refuse correctement (*« weekly loss lock already active »*). **Le re-calibrage ne se déclenche donc pas à tort — sinon il effacerait un verrou hebdomadaire à chaque run.**

**③ Retour** — un second changement d'`account_id` re-déclenche le mécanisme, dans l'autre sens. 🟢

### État après le test

`state.json` **restauré à l'identique**, y compris `traded_today: ["SPY"]` — c'est la garde anti-doublon du jour, la perdre aurait rouvert une porte. `.env` intact, `.env.hackathon` toujours à sa date de création, jamais touché. Aucun `.env.test2` ni `.env.dev.bak` n'a été créé. Non-régression propre.

**Ce qui reste non prouvé, dit honnêtement :** que *l'échange des fichiers `.env`* désigne bien le bon compte. Ce n'est pas le mécanisme risqué — c'est une copie de fichier, et `test_connection.py` vérifie déjà l'`account_number` obtenu. **Le code qui pouvait mal se comporter est celui qui vient d'être exercé.**

---

## 🟢 24/08 (nuit) — la garantie « paper uniquement » prouvée, et une politique en prose transformée en contrôle

*Deux zones jamais auditées : `config.py` — qui porte la contrainte la plus dure du projet — et le risque de dérive du CLI.*

### `config.py` : aucun bug, et c'est désormais démontré et non plus supposé

**Structurellement** : un seul point du dépôt lance le CLI Alpaca (`alpaca_cli.py`), et il passe `env=config.cli_env()`. Les quatre autres sous-processus sont `git`. **Aucun chemin ne peut atteindre le CLI avec l'environnement ambiant.**

**Empiriquement, sur trois couches** :
- `require_credentials()` refuse `true / TRUE / True / 1 / yes / YES / " true "` — et autorise `"" / false / no / 0 / off`. Aucune graphie vraie ne passe.
- `cli_env()` retire le drapeau de l'environnement transmis **même quand il est réellement présent** dans `os.environ`.
- Et si **`.env` lui-même** contenait `ALPACA_LIVE_TRADE=true` : refus à la couche 1, environnement propre à la couche 2. *(Testé en l'ajoutant réellement au fichier, puis restauré — 0 occurrence après.)*

**« Zéro fonds réel engagé » n'est plus une phrase de pied de page : c'est vérifié.**

### 🟠 Le contrôle ajouté : la version du CLI n'était garantie que par des commentaires

Trois endroits d'`alpaca_cli.py` portent *« VERIFIED 24/08 against CLI v0.0.13 »*. **Rien ne le vérifiait à l'exécution** — une politique écrite en prose que rien n'applique, exactement le reproche que ce projet adresse au travail des autres.

**Et le risque est mesuré, pas théorique : la dérive de flag a coûté DEUX bugs le 24/08** (`data option snapshot --symbol` → `--symbols`, `position close --symbol` → `--symbol-or-asset-id`). **Les deux échouaient en silence** : le premier rend `None` et le trade est écarté « faute de prix », le second laisse une position stop-lossée **ouverte**.

**Ajouté** : `_check_cli_version()`, une fois par processus, **avertit sans bloquer** *(refuser de trader sur une chaîne de version serait pire que la dérive qu'on veut attraper)*. Vérifié : silence quand la version correspond · **un seul** avertissement sur 3 appels quand elle diffère · **un seul sous-processus en plus par processus**, pas par appel.

*Contexte du jour : v0.0.13 installée = dernière publiée, et `alpaca update` est manuel. Aucune dérive possible aujourd'hui — le contrôle est là pour la semaine à venir.*

---

## 🔴 24/08 (nuit) — un chiffre PUBLIC corrigé : le classement des deux stratégies s'inverse selon la statistique

*Passe sur les outils de rapport, annoncée comme à faible enjeu. Elle ne l'était pas : ces fichiers produisent les chiffres de la soumission, et j'y avais écrit un verdict.*

### Ce qui est symétrique, vérifié d'abord

`compare_strategies.py` traite bien les deux familles à égalité : **même garde-fou** (`check_selection_leakage`), **même seuil** (0.0), **même holdout** (`IN_SAMPLE_HOLDOUT_DAYS = 20` dans les deux modules), **même nombre de candidats** (5), **même `_sharpe`**. Aucun biais de traitement. 🟢

### 🔴 Mais « même statistique » était un abus, et je l'avais écrit

Les deux Sharpe partagent une **formule**, pas une **quantité** :
- `vol_strategy` : payoff bâti sur `abs(rendement)` — **non négatif par construction**, et **~25 % moins variable** que le rendement signé (mesuré : écart-type 0,00742 contre 0,00994) — et **à plat ~3 jours sur 4**, ce qui réduit encore l'écart-type.
- `momentum` : rendement **signé**, en marché quasiment tous les jours.

**Mesuré sur les 4 symboles :**

| | vol_strategy | momentum |
|---|---|---|
| Sharpe le plus haut | **4 / 4** | — |
| **moyenne quotidienne la plus haute** | — | **3 / 4** |
| `hindsight_guard` propre | 3 / 4 | **4 / 4** |

Sur SPY : `momentum` gagne la moyenne (+0,00045 contre +0,00027) et **perd quand même le Sharpe**, parce que son écart-type est **3,7× plus grand**. **L'avantage de `vol_strategy` au Sharpe est structurel — une variance plus faible — pas un rendement supérieur.**

### Corrigé dans le SCRIPT, pas à la main

La mise en garde est désormais **générée** par `compare_strategies.py` (une correction écrite à la main aurait été écrasée au run suivant — elle l'avait d'ailleurs été), et les colonnes **moyenne/jour et écart-type/jour** sont calculées et affichées pour les deux familles, **pour que l'affirmation soit vérifiable au lieu d'être crue**. Le verdict de `STRATEGY_COMPARISON.md` est réécrit : il donne les **trois** chiffres qui tirent dans des sens différents, au lieu d'un seul qui tranche à la place de Spap.

**Aucune bascule de stratégie décidée** — hors périmètre, et c'est précisément le genre de décision que ce document ne doit pas préempter.

---

## 🔴 24/08 (nuit) — `BACKTEST_RESULTS.md` : deux cadrages trompeurs, et une analyse que j'avais silencieusement perdue

*Suite de la passe sur les outils de rapport. Même famille que la correction de `STRATEGY_COMPARISON.md` : le code sait, le rapport ne le dit pas.*

### ① Le buy-and-hold était juxtaposé au payoff, sans un mot

L'en-tête de chaque symbole affichait `## SPY (657 bars used, buy-and-hold over the period: 60.2%)` **immédiatement au-dessus** d'une colonne `cum. proxy payoff` valant `0.108`. **Aucune mise en garde** — un lecteur, ou un juge, lit mécaniquement « le buy-and-hold écrase la stratégie ». **Les deux ne sont pas comparables** : l'un est un rendement composé sur *tous* les jours, l'autre une **somme** de payoffs `abs(rendement) − coût` sur la minorité de jours où la règle était en position. Le buy-and-hold est maintenant sur sa propre ligne, avec l'avertissement.

### ② « max drawdown » n'est pas un drawdown de compte

Le champ interne s'appelle honnêtement `max_drawdown_proxy` — **mais l'en-tête de colonne laissait tomber le qualificatif**, seul endroit où un lecteur rencontre le chiffre. Il porte sur une **somme cumulée de payoffs**, pas sur une courbe d'équité : il ne peut pas se lire « le compte a chuté de X % ». Colonne renommée, et la fonction documente désormais ce qu'elle mesure vraiment.

### 🔴 ③ Et surtout : mon analyse de concentration avait disparu du document public

L'analyse mesurée hier (**83 % du gain de SPY venant de 5 jours sur 102**) avait été écrite **à la main** dans un fichier **généré**. Elle a été écrasée à la régénération suivante — **et j'avais commité la version amputée sans le voir** : vérifié, elle était déjà absente de `HEAD`. **Troisième fois que je commets cette erreur** (après `STRATEGY_COMPARISON.md`, deux fois).

**Corrigé pour de bon : la concentration est désormais CALCULÉE ET PUBLIÉE PAR LE SCRIPT** (`_top_n_share`), donc elle survit à toute régénération. Recoupée avec ma mesure manuelle : **SPY 82,6 %** contre 83 % mesuré à la main. 🟢

**Découverte au passage :** plusieurs symboles dépassent **100 %** (XLV 20 j : **282,5 %**). Ce n'est pas une erreur — **les 5 meilleurs jours rapportent plus que le résultat net entier, donc tous les autres jours de trade réunis perdent de l'argent**. C'est plus parlant que le chiffre de SPY, et c'est maintenant expliqué dans le rapport plutôt que laissé passer pour un bug.

### 🟢 Ce que la journée a démontré au passage

En insérant ce calcul, je me suis trompé de nom de variable (`trade_rets` au lieu de `trade_days`). **L'isolation par symbole ajoutée ce matin a fait exactement son travail** : elle a attrapé le `NameError` sur chaque symbole et poursuivi proprement, au lieu de faire tomber le run. *(J'avais aussi masqué la sortie avec `>/dev/null` — sans quoi je l'aurais vu tout de suite. Contrôler en aveugle ne contrôle rien.)*

---

## 🔴 25/08 (Cowork) — cherche encore : `publish_dashboard.py --git-push` pouvait committer et pousser un fichier qui n'avait rien à voir avec le dashboard

*Nouveau bug, jamais signalé avant (relu la ligne 591 de ce fichier : `publish_dashboard` avait déjà été « audité et déclaré sain » — mais sur la résilience de lecture, jamais sur ce chemin git). Famille différente des six précédents : pas une trace perdue, une PORTÉE mal posée — le contrôle censé décider « y a-t-il quelque chose à publier » ne regardait pas ce qu'il croyait regarder.*

**Le code, avant correction :**
```python
subprocess.run(["git", "add", "docs/data.json", "decision_log.jsonl"], check=True)
result = subprocess.run(["git", "diff", "--cached", "--quiet"])
if result.returncode == 0:
    print("Nothing changed since last publish — skipping commit.")
    return
subprocess.run(["git", "commit", "-m", f"dashboard: snapshot ..."], check=True)
subprocess.run(["git", "push"], check=True)
```

`git diff --cached --quiet` **sans pathspec** regarde tout l'index, pas seulement les deux fichiers venant d'être ajoutés. Et `git commit` sans pathspec committe tout l'index aussi. **Reproduit dans un dépôt jetable** : un fichier sans rapport (`unrelated.py`) déjà `git add`é, `docs/data.json`/`decision_log.jsonl` strictement inchangés → le diff non scopé rend quand même "changé" (code 1), et un `git commit` non scopé aurait embarqué `unrelated.py` dans un commit qui se prétend juste « dashboard: snapshot ... » — poussé au dépôt public sous une étiquette fausse.

Ce n'est pas hypothétique pour CE dépôt précisément : toute la journée, la session terminal a fait des `git add`/relectures multi-fichiers en cours de séance, exactement le genre d'état où un fichier peut rester indexé au moment où `publish_dashboard.py --git-push` tourne (le `README.md` documente cet enchaînement comme le geste de fin de journée).

**Corrigé** : les deux appels sont maintenant scopés au pathspec (`git diff --cached --quiet -- <paths>` et `git commit -m ... -- <paths>`). Testé dans un dépôt jetable avec un vrai remote local, deux scénarios : (a) fichier étranger indexé + dashboard inchangé → commit sauté, le fichier étranger reste indexé intact ; (b) fichier étranger indexé + dashboard changé pour de vrai → commit contient EXCLUSIVEMENT les 2 fichiers du dashboard (`git show --stat` vérifié), poussé avec succès, le fichier étranger reste indexé et intact après coup. `py_compile` propre. Non committé — pour la prochaine session terminal, comme d'habitude.

---

## 🔴 25/08 (Cowork) — cherche encore : `manage_exits()` mutait `consecutive_losses` sans jamais vérifier à quel compte `state.json` appartenait vraiment

*Même famille que les six précédents (un contrôle construit avec soin pour UN chemin, silencieusement supposé protéger un AUTRE chemin qui ne passe jamais par lui) mais jamais repérée jusqu'ici. Trouvée en relisant `risk_gates.py` avec un œil neuf plutôt qu'en repartant du dernier diff.*

**Le fait établi** : `check_gates()` est le SEUL endroit qui compare l'`account_id` sauvegardé dans `state.json` avec celui du compte réellement actif, et re-baseline (`_record_starting_equity`) si ça ne correspond pas — locked, traded_today, ET consecutive_losses remis à zéro. `manage_exits()` (donc `monitor_exits.py`) ne passe JAMAIS par `check_gates()`, par construction (les sorties doivent continuer à tourner même sous un lock). Résultat : `_record_exit_outcome()` incrémentait/remettait à zéro `consecutive_losses` dans `state.json` sans jamais vérifier si ce fichier appartenait au compte qui venait réellement de subir la perte ou le gain.

**Pas hypothétique pour CE projet précisément** : `monitor_exits.py` est planifié via launchd, sans surveillance, toutes les 15 minutes — et cette même session a swappé `.env` à la main des dizaines de fois aujourd'hui pour tester. Si ce job planifié se déclenche pendant une fenêtre de swap manuel, et que `.env` est reswappé vers le bon compte AVANT qu'un `check_gates()` tourne sur le compte visité entre-temps (ce qui ne déclenche la détection que dans le sens compte→state.json, pas l'inverse), le vrai compte hérite silencieusement d'un historique de gains/pertes qui n'était pas le sien — sans aucun avertissement nulle part.

**Reproduit** : `state.json` semé pour le compte "A" (`consecutive_losses: 1`), `alpaca_cli.get_account()` mocké pour renvoyer le compte "B", une position perdante fermée via `manage_exits()`. Résultat avant correctif : `consecutive_losses` passe à 2, toujours étiqueté `account_id: "A"` — rien n'enregistre que cette perte était en fait celle de B.

**Corrigé** : `_record_exit_outcome()` accepte maintenant `account_id`/`equity` (optionnels, défaut `None` — dégrade vers l'ancien comportement aveugle si absents, jamais une nouvelle façon d'échouer) et réconcilie via `_record_starting_equity()`, la même fonction déjà testée que `check_gates()` utilise — no-op quand le compte correspond déjà (le cas courant à chaque tick de 15 minutes), reset complet sinon. `manage_exits()` récupère le compte SEULEMENT quand une clôture réelle se produit (pas à chaque tick, pas sur les positions "holding" — même logique de coût que le contrôle de version du CLI), et cet appel est lui-même protégé par son propre `try/except` : un échec de `get_account()` à ce moment précis ne bloque JAMAIS la clôture déjà effectuée, il dégrade simplement vers l'ancien comportement aveugle au compte.

**4 scénarios testés, tous passent** : ① compte différent → re-baseline avant d'appliquer la perte, l'ancien compte de A n'est pas hérité ; ② même compte, perte normale → incrément 1→2 comme avant, aucun re-baseline parasite ; ③ même compte, gain → reset à 0 comme avant ; ④ `get_account()` échoue pendant la réconciliation → la clôture reste effective, comptabilité en mode aveugle (ancien comportement), rien de cassé. `py_compile` propre sur tout le périmètre touché aujourd'hui. Non committé — pour la prochaine session terminal.

---

## 🔴 25/08 (Cowork) — cherche encore : le correctif du badge résumé mentait encore, exactement dans le cas qu'il prétendait avoir corrigé

*Trouvé dans `agent.py`, à l'intérieur même du bloc dont le commentaire affirme déjà avoir réglé « le badge résumé ne doit pas mentir ». Pas une nouvelle famille — la même récidive que ce bloc était censé fermer, laissée ouverte dans le cas qu'il ne testait pas.*

**Le code, avant correction** :
```python
trade_outcomes = {t["outcome"] for t in trades}
record["outcome"] = trade_outcomes.pop() if len(trade_outcomes) == 1 else "risk_gate_blocked"
```
Le commentaire au-dessus explique avoir corrigé le cas où TOUS les symboles partagent la même issue (`len == 1`) — mais dès que deux symboles ont des issues DIFFÉRENTES (`len > 1`), le code retombe sur `"risk_gate_blocked"` en dur, **qu'un risk gate ait ou non jamais été atteint**.

**Reproduit** : `trades = [{"outcome": "no_contract_found"}, {"outcome": "error"}]` (zéro symbole bloqué par un risk gate) → `record["outcome"]` valait quand même `"risk_gate_blocked"`. `docs/index.html`'s `outcomeBadge()` aurait affiché **« blocked by risk gate »** en jaune sur le tableau de bord public, un jour où aucun risk gate n'a jamais été atteint par quoi que ce soit — exactement le mensonge que ce bloc affirme empêcher, juste dans le cas jamais testé (plusieurs raisons différentes, aucune n'étant `risk_gate_blocked`).

**Corrigé** : un jeu d'issues hétérogène produit maintenant `"mixed"` plutôt que de choisir arbitrairement l'une des raisons réelles (n'importe quel choix unique parmi N raisons différentes serait tout aussi trompeur). `docs/index.html` reçoit une entrée dédiée dans la table des badges (`mixed: muted, "mixed outcomes — see trades below"`) plutôt que de tomber sur le badge générique — le détail par symbole reste correct et visible juste en dessous (`renderTrade()`, inchangé). 4 cas testés (mêmes issues répétées, issues différentes, un seul symbole, mélange incluant `risk_gate_blocked`) — tous passent. `node --check` sur le JS extrait du dashboard, propre. `py_compile` propre. Non committé — pour la prochaine session terminal.

---

## 🟡 25/08 (Cowork) — cherche encore : rien de conséquent, un seul import manquant, honnêtement mineur

*Par honnêteté envers le rituel : cette passe n'a PAS trouvé de bug fonctionnel. Un seul défaut réel, mais sans conséquence à l'exécution — signalé quand même plutôt que de forcer quelque chose de plus gros pour avoir quelque chose à écrire ici.*

`backtest.py` importe `from typing import List` mais utilise `Optional[float]` comme annotation de retour de `_top_n_share()` (ajoutée par la session terminal, commit `1ae7b7c`) sans jamais importer `Optional`. Ça ne plante PAS à l'exécution — `from __future__ import annotations` (déjà présent en haut du fichier) rend toutes les annotations paresseuses (de simples chaînes, jamais évaluées), vérifié en appelant la fonction pour de vrai (`_top_n_share([0.1, 0.2, -0.05], 5)` → `100.0`, aucune `NameError`). Ça casserait uniquement un outil qui évalue les annotations activement (`typing.get_type_hints()`, un `mypy`) — rien de tel ne tourne dans ce projet aujourd'hui. Corrigé quand même (une ligne, `from typing import List, Optional`), `py_compile` propre, `get_type_hints()` résout proprement après coup. Aussi consulté : `vol_strategy.py`, `momentum_strategy.py`, `hindsight_guard.py`, `alpaca_cli.py` (parsing des snapshots, sélection de contrat, comptage des positions) relus sans trouver de nouveau problème réel — y compris une piste creusée sérieusement (`hindsight_guard.check_selection_leakage`'s `max(scores, key=...)` avec un score `NaN` produirait un résultat instable en Python) puis abandonnée après avoir confirmé que `vol_strategy._sharpe`/`_realized_vol` ne peuvent jamais renvoyer NaN sur des données réelles (retour `0.0` garanti dans tous les cas dégénérés) — piste non reproductible, donc pas publiée comme un bug.

---

## 🟢 25/08 (Cowork) — audit demandé explicitement : compilation + rangement, tout le dépôt

*Spap a demandé un passage général, pas un "cherche encore" ciblé : compiler tout, vérifier le rangement, confirmer que rien n'est cassé. Résultat rangé en trois blocs.*

### 🟢 Tout est vert

- `python3 -m py_compile *.py` (les 16 fichiers Python à la racine) : propre, y compris avec `-W error::SyntaxWarning`.
- `docs/data.json`, `decision_log.jsonl` (16 lignes), `state.json`, `monitor_exits_dedup.json` : JSON valide, vérifié en les parsant réellement, pas en supposant.
- `submission/Hindsight_Alpha_Deck.pptx` et `.docx` : archives zip valides, non corrompues (`zipfile.testzip()`).
- `requirements.txt` : recoupé contre les imports RÉELS de tout le code actif (AST, pas grep) — `python-dotenv` est bien la seule dépendance externe utilisée, rien de manquant, rien de mort listé.
- `.gitignore` : `.env`, `.env.*`, `__pycache__/`, `*.pyc`, `state.json`, `HALT`, `.DS_Store`, les fichiers `.tmp`, `monitor_exits.log`, `monitor_exits_dedup.json` — tous correctement ignorés, confirmé via `git status --ignored`, aucun n'est suivi.
- **Aucun secret jamais committé** : `git log --all --full-history` sur `.env`/`.env.hackathon`/etc. est vide sur tout l'historique, et aucune clé API en dur trouvée dans les fichiers suivis (`git grep`).
- Aucun `.pyc`/`__pycache__`/`.DS_Store` suivi par git.

### 🟡 Un fichier mal rangé, déjà documenté mais jamais nettoyé

`alpaca_client.py` — brouillon abandonné (SDK `alpaca-py` direct, remplacé par `alpaca_cli.py` pour respecter l'exigence "MCP or CLI" du hackathon). **Committé depuis le tout premier commit** (`68c778d`), jamais importé nulle part (vérifié par grep sur tout le dépôt), et son import `from alpaca.trading.client import TradingClient` échouerait immédiatement si quelqu'un l'exécutait (le paquet `alpaca-py` n'est même pas dans `requirements.txt`). README.md le documente déjà honnêtement ligne 256-259 : *"dead code... nothing imports it. Safe to delete by hand."* — donc déjà repéré, jamais exécuté par erreur, mais toujours présent, avec un nom qui ressemble dangereusement à `alpaca_cli.py` (le vrai fichier actif) pour quiconque parcourt le dépôt en diagonale, juge du hackathon inclus.

**Testé, pas supposé : Cowork ne peut PAS le supprimer.** `rm` sur ce dossier (`/Users/s-pap/hindsight-alpha`, monté séparément de `~/Desktop/CERVEAU`) échoue avec `Operation not permitted` — même restriction que celle déjà documentée dans README.md pour ce fichier précis. **À supprimer à la main, ou via la prochaine session terminal** : `git rm alpaca_client.py`.

### 🟡 Deux fichiers laissés par cette session elle-même, à nettoyer

- **`__TEST_DELETE_PERMISSION__.tmp`** (0 octet, racine) — créé par Cowork pour vérifier la permission de suppression ci-dessus, confirmé non supprimable par Cowork. **Untracked** (`??` dans `git status`, aucun risque d'être committé par accident), mais à supprimer à la main : `rm __TEST_DELETE_PERMISSION__.tmp`.
- **`.git/index.lock`** (0 octet, horodaté de cette session) — le warning déjà observé plusieurs fois aujourd'hui ("unable to unlink .git/index.lock: Operation not permitted") vient de ce fichier fantôme, lui aussi non supprimable par Cowork. **N'a bloqué aucune opération git testée aujourd'hui** (status, log, diff, et même les scénarios de test avec un vrai remote local ont tous fonctionné) — vraisemblablement un artefact du montage réseau de ce dossier côté Cowork, pas une vraie corruption de l'index git réel sur le Mac. À vérifier/supprimer côté terminal si une vraie opération git bloque un jour (`rm .git/index.lock`), mais rien d'urgent constaté.

**Verdict global : le code est vert, rien de cassé. Le seul vrai rangement en attente (`alpaca_client.py`) était déjà connu et documenté — ce passage l'a juste re-confirmé avec des tests plutôt que de le supposer, et a trouvé les deux fichiers de service que cette session elle-même a laissés traîner.**

---

## ✅ 25/08 (Terminal) — les 4 correctifs Cowork vérifiés puis committés, et les 3 fichiers nettoyés — avec une réserve honnête sur les dry-runs

*Session terminal faisant suite au brief `BRIEF_COMMIT_4_CORRECTIFS_ET_NETTOYAGE.md`. Point de départ vérifié : `HEAD` == `origin/main` == `1ae7b7c`, rien entre les deux. Résultat : commits `afaef46` (les 4 correctifs) et `4aae387` (suppression du code mort), **poussés** — `git ls-remote` confirme `refs/heads/main` == `4aae387`.*

### 🟡 La réserve, d'abord : les deux dry-runs n'ont rien prouvé

`python agent.py --dry-run` et `python monitor_exits.py --dry-run` tournent tous les deux **proprement** (`monitor_exits` sort en code 0), mais tous les deux sortent sur **« Market is closed »** avant d'atteindre la moindre ligne modifiée par les 4 correctifs. Le test de non-régression demandé au brief est donc **inerte** : il confirme que rien ne plante au démarrage, rien de plus. Écrit ici plutôt que rapporté comme un « dry-run propre » qui aurait laissé croire que les chemins corrigés avaient été traversés.

**Compensé par des tests ciblés sur les chemins réellement changés**, tous exécutés pour de vrai :

- **`publish_dashboard.git_publish()`** — dépôt jetable avec un vrai remote local, deux scénarios. (a) fichier étranger indexé + dashboard inchangé → commit correctement sauté, `HEAD` immobile, le fichier étranger reste indexé et son contenu intact ; (b) fichier étranger indexé + dashboard vraiment modifié → `git show --name-only` confirme que le commit contient **exclusivement** `docs/data.json`, message conforme, push effectif, et le fichier étranger toujours indexé et intact après coup.
- **`risk_gates._record_exit_outcome()`** — 4 scénarios, avec `STATE_FILE` redirigé vers un fichier temporaire. Compte différent → re-baseline (compteur à 1 et non 2, `starting_equity` suit le nouveau compte, `traded_today` de A non hérité par B) avec un `NOTE:` visible en sortie, pas un changement silencieux ; même compte perte → 1→2 sans re-baseline parasite, `traded_today` préservé ; même compte gain → reset à 0 ; `account_id` absent → ancien comportement aveugle, aucune exception. **Le vrai `state.json` a été relu après coup et est intact** (`account_id`, `consecutive_losses`, `starting_equity` inchangés).
- **Agrégation d'outcome (`agent.py`)** — 5 combinaisons, dont le cas du bug (`no_contract_found` + `error`, zéro risk gate atteint → `"mixed"`) et le cas non-régressé (tous `risk_gate_blocked` → inchangé).
- **`docs/index.html`** — entrée `mixed` présente ligne 282, classe `badge-muted` bien définie dans la feuille de style ligne 113 (le badge n'aurait pas été stylé sinon), `node --check` propre sur le JS extrait.
- **`backtest.py`** — `get_type_hints()` résout maintenant les deux fonctions annotées.
- **`ExitAction.__str__`** — vérifié intact, comme demandé : le seul hunk de `risk_gates.py` dans cette zone est à la ligne 720, `__str__` est à la 580.

### 🟢 Deux pistes creusées, toutes deux écartées après vérification

1. **`risk_gates.py` utilise `Optional[...]` dans la nouvelle signature** — soupçon immédiat d'avoir réintroduit exactement le défaut que le correctif n°4 corrigeait dans `backtest.py`. **Faux** : `Optional` est bien importé ligne 74, et l'import réel du module le confirme. Vérifié avant de committer plutôt que supposé d'après la ressemblance.
2. **`trades` vide → `"mixed"`** — le nouveau `else` attrape aussi `len(trade_outcomes) == 0`, ce qui afficherait « mixed outcomes — see trades below » sans aucun trade en dessous. **Inatteignable** : `agent.py` fait un `return` anticipé quand `tradeable_verdicts` est vide (`outcome = "no_edge"`, ligne 264) et un autre pour `--dry-run`, et chaque branche de la boucle fait un `append`. Le correctif n'a donc pas ouvert ce trou — vérifié en lisant les gardes réelles, pas en le supposant.

### 🔵 Le contraste mesuré sur les suppressions

**`rm` fonctionne sans problème depuis le terminal réel**, sur les deux fichiers que Cowork avait confirmé ne pas pouvoir supprimer (`Operation not permitted`) :

- `__TEST_DELETE_PERMISSION__.tmp` — supprimé.
- `.git/index.lock` — supprimé. Vérifié d'abord qu'**aucun processus git ne tournait** (le lock avait 34 minutes et 0 octet — orphelin, pas actif) : supprimer un lock détenu par un vrai processus aurait corrompu l'index. `git status` fonctionne normalement après coup.

C'est bien la restriction du bac à sable Cowork qui était en cause, pas une permission du Mac ni une corruption de l'index — l'hypothèse que Cowork avait formulée est confirmée.

- `alpaca_client.py` — retiré par `git rm`. Avant suppression, **re-vérifié qu'aucun `.py` ne l'importe** : le premier `grep --include=*.py` avait échoué silencieusement sur le glob zsh et renvoyé un « aucun import » qui était un **faux négatif** — refait proprement, les seules occurrences dans tout le dépôt sont de la prose dans `README.md`, `PLAN_SPRINT.md` et les briefs. La puce du `README.md` qui le documentait est retirée dans le **même commit**, pour ne pas laisser la liste de fichiers pointer vers un fichier disparu. Les 13 `.py` restants compilent et s'importent proprement après coup.

### 📋 Deux écarts avec le brief, signalés

- Un **second fichier untracked** non listé au brief : `BRIEF_COMMIT_4_CORRECTIFS_ET_NETTOYAGE.md`, le brief lui-même. Committé, conformément à la convention du dépôt (11 briefs déjà suivis par git).
- **`decision_log.jsonl` a gagné une ligne** du fait de mes propres dry-runs (`outcome: "market_closed"`, correctement étiquetée `dry_run: true`). Conservée et committée : le log est append-only par convention, et c'est la trace honnête d'une exécution réelle.

### 🔒 Périmètre respecté

`.env.hackathon` et le compte du kickoff jamais touchés — vérifié avant tout appel que `.env` pointe bien vers le compte de dev (`523f7f05-…`, préfixe de clé `PKLVR2` vs `PKXKP3` pour le hackathon). Aucun `--live`, aucun seuil de risque modifié, position de test non fermée, stratégie non basculée, aucun `--force`.

---

## 🔴 25/08 (Cowork) — exigence trouvée en lisant la page officielle du hackathon, jamais vérifiable avant le 28 : solde de départ à $100 000 EXACT

*Demandé explicitement par Spap : chercher la concurrence, les éditions passées, les axes non couverts. Ceci vient de la lecture de la page officielle lablab.ai elle-même (onglet "Account Requirements"), jamais lue ligne à ligne avant aujourd'hui.*

**Citation exacte, section "ADDITIONAL REQUIREMENTS" :** *"Competition account starting balance must be set to $100,000."* Et section "REQUIRED FOR JUDGING" : *"For your final submission, create a brand-new Alpaca paper trading account dedicated to this hackathon. Projects run on an existing or reused account will not be eligible for judging."*

**Le compte dédié (`PA3K8MP3MF0U` / `.env.hackathon`) n'a jamais été touché — donc son solde réel n'a JAMAIS été vérifié**, seulement simulé en mocks (`starting_equity: 100000.0` dans un test, voir plus haut dans ce fichier). Recherché : un compte paper Alpaca fraîchement créé démarre à $100k par défaut, donc si `PA3K8MP3MF0U` a été créé par le flux normal d'inscription sans jamais être "reset" vers un autre montant, il devrait déjà être conforme. **Mais ça reste une supposition tant que personne n'a lancé `alpaca account get` dessus.**

**Piège opérationnel trouvé en même temps, à ne pas découvrir le 28 au pire moment** : sur Alpaca, remettre à zéro un compte paper (bouton "reset", avec un solde de départ choisi) **invalide l'ancienne clé API** — il faut en régénérer une nouvelle et mettre `.env.hackathon` à jour. Donc SI le solde n'est pas exactement $100k et qu'un reset est nécessaire, ça entraîne automatiquement une régénération de clé, pas juste un changement de chiffre.

**Action concrète pour le kickoff (28/08), en tout premier, avant toute autre chose** :
1. `alpaca account get --quiet` sur le compte dédié — confirmer `cash`/`equity`/`portfolio_value` == 100000.00 exactement.
2. Si ce n'est pas le cas : reset avec $100 000 explicitement demandé dans le dashboard Alpaca, **puis régénérer la clé API et mettre à jour `.env.hackathon`** avant tout autre appel.
3. Ne lancer `agent.py` qu'après cette confirmation — sinon le premier run pourrait re-baseliner `state.json` sur un solde de départ qui n'est pas le bon, ce qui fausserait tout calcul de drawdown hebdomadaire (`WEEKLY_LOSS_LOCK_PCT`) pour le reste de la semaine jugée.

Non actionnable avant le 28 par construction (interdiction de toucher ce compte) — noté ici pour que ce ne soit pas oublié dans l'excitation du kickoff.

---

## 🟡 25/08 (Cowork) — regarder en face : la fréquence de trade réelle sur la semaine jugée est probablement très basse

*Demandé explicitement par Spap. Pas un bug, pas une recommandation de toucher aux seuils — un chiffre qu'il vaut mieux connaître avant le 28 que découvrir pendant.*

**La fenêtre réelle de marché ouvert, calculée jour par jour (pas supposée)** : kickoff vendredi 28/08 à 15h00 UTC, clôture des soumissions vendredi 4/09 à 15h00 UTC.
- 28/08 (ven) : partiel, après le kickoff — peu de marge pour trader le jour même, entre la bascule de compte et la mise en route.
- 29-30/08 : marché fermé (week-end).
- 31/08 (lun), 1er/09 (mar), 2/09 (mer), 3/09 (jeu) : **4 jours pleins**.
- 4/09 (ven) : la deadline (15h UTC) tombe à peu près à l'heure d'ouverture du marché US — quasiment aucune fenêtre de trading avant la clôture des soumissions.
- **Pas de Labor Day dans la fenêtre** — vérifié par calcul de date, pas supposé : Labor Day US 2026 tombe le lundi **7 septembre**, après la deadline. Une inquiétude que j'ai eue puis écartée en calculant, pas en devinant.

**Fréquence de trade réelle mesurée** (`BACKTEST_RESULTS.md`, fenêtre vettée par symbole) : SPY 26,0 % · GLD 14,6 % · XLV 13,2 % (XLK actuellement recalé par `hindsight_guard`, donc 3 symboles réellement disponibles aujourd'hui). Moyenne ≈ **17,9 %**.

**Estimation grossière** (fréquence historique moyenne traitée comme une probabilité par jour et par symbole — approximation, PAS une prévision : les régimes de vol cheap sont autocorrélés dans la réalité, pas indépendants jour à jour) : 4 jours × 3 symboles × 17,9 % ≈ **2 trades espérés sur toute la semaine jugée**.

**Ce que ça veut dire pour le critère #1 ("P&L Performance")** : avec 1 à 3 trades sur la semaine, le résultat sera dominé par la chance sur ce petit nombre de trades, pas une démonstration robuste d'edge — que le trade gagne ou perde. Ce n'est pas un défaut caché : le write-up le dit déjà explicitement ("53–83 % du gain vient des 5 meilleurs jours"). Mais ça veut dire concrètement que les 4 autres critères (Technology Implementation, Creativity & Originality, Presentation & Execution, Social engagement) pèseront probablement plus lourd que le P&L brut dans le classement final — raison de plus d'y investir à fond (voir `SOCIAL_POSTS_DRAFT.md`, le write-up mis à jour).

**Un levier existe, mais c'est la décision de Spap, pas la mienne** : élargir `DEFAULT_UNIVERSE` (aujourd'hui 4 symboles, `SPY/GLD/XLK/XLV`) à d'autres secteurs non corrélés augmenterait le nombre de tentatives par jour sans toucher un seul seuil de risque nommé (`MAX_RISK_PCT_PER_TRADE`, `CHEAP_VOL_PERCENTILE`, etc. — `risk_gates.SECTOR_MAP` est déjà conçu pour être étendu). Pas fait ici : ça change le comportement de trading réel, même sans toucher un seuil, et c'est exactement le genre de décision ("élargir l'univers" a déjà été fait une fois aujourd'hui "à la direction explicite de Spap") qui doit rester la sienne.

---

## 🟡 25/08 (Cowork) — piste trouvée dans la communauté Alpaca, à VÉRIFIER avant d'y toucher : ordres bracket/OCO côté serveur

*Demandé explicitement par Spap ("cherche les axes non couverts"). Trouvé en lisant "The Weekly Roundup #1" d'Alpaca (alpaca.markets/learn) : un billet communautaire de Rudraksh Mishra décrit l'usage d'ordres bracket Alpaca pour gérer le risque "when local trading bot processes stop running" — exactement le point faible structurel non couvert ici.*

**Le point faible, nommé précisément** : aujourd'hui, le take-profit/stop-loss de ce projet est appliqué exclusivement par **polling côté client** — `agent.py` (une fois par jour) et `monitor_exits.py` (toutes les 15 min via launchd) interrogent les positions et ferment celles qui dépassent leur seuil. **Si les deux processus sont down en même temps** (crash machine, launchd mort, coupure réseau prolongée), rien ne protège une position ouverte — aucun ordre stop-loss n'existe côté broker. C'est exactement le scénario "policies not enforced in code are worthless" que ce projet dénonce ailleurs, appliqué cette fois à son propre mécanisme d'enforcement.

**Ce qui existe chez Alpaca** (vérifié par recherche, pas supposé) : les ordres **bracket** (OTOCO — entrée + take-profit + stop-loss soumis ensemble) et **OCO** (les deux ordres de sortie soumis après coup sur une position déjà ouverte) sont bien documentés côté **actions**. **Non confirmé pour les OPTIONS spécifiquement** — la documentation trouvée ne mentionne pas explicitement ce cas, et les options sont un ajout plus récent à l'API Alpaca que les actions.

**Pourquoi ce n'est PAS implémenté aujourd'hui** : ça nécessite un accès réseau réel à l'API Alpaca pour vérifier la vraie capacité, ce que le bac à sable Cowork n'a pas. Et même si c'est supporté, ajouter un ordre bracket/OCO est un changement de comportement de soumission d'ordre — pas un seuil de risque au sens strict, mais assez proche pour mériter la décision de Spap plutôt qu'être fait silencieusement.

**À vérifier lors d'une prochaine session terminal** (pas urgent avant le 28, mais à garder sous le coude) :
1. `alpaca order submit --help` — les flags `--order-class`, `--take-profit-limit-price`, `--stop-loss-stop-price` (ou équivalents) existent-ils, et fonctionnent-ils sur un symbole OCC (option) ?
2. Si oui, tester en dry/paper sur le compte de dev : soumettre un bracket order réel sur une option, confirmer que le take-profit et le stop-loss apparaissent bien comme des ordres actifs côté Alpaca (visibles via `alpaca order list`), pas juste acceptés silencieusement puis ignorés.
3. Si ça marche : ce serait un ÉLÉMENT DE PLUS pour "Technology Implementation" (critère de jugement) et une vraie amélioration de résilience — mais **implémenter en PLUS du polling existant, jamais à sa place** (le polling gère aussi la comptabilité interne — `consecutive_losses`, `decision_log.jsonl` — qu'un ordre bracket côté broker ne fait pas).
4. Si ce n'est pas supporté sur les options : le documenter honnêtement comme une limite connue plutôt que de laisser le sujet ouvert sans réponse.

---

## ✅ 25/08 (Terminal) — bracket/OCO sur options : **NON supporté par Alpaca**, la question est close, mesurée contre l'API réelle

*Réponse à la seule vraie tâche technique du brief `BRIEF_RECHERCHE_HACKATHON_DEJA_FAITE.md`. Testé sur le compte de **dev** (`523f7f05-…`, `.env`), marché ouvert, `options_trading_level: 3`. `.env.hackathon` jamais touché.*

### La réponse, avec la preuve exacte

```
POST https://paper-api.alpaca.markets/v2/orders  ->  HTTP 422
{"code": 42210000, "error": "complex orders not supported for options trading"}
```

Obtenu sur `GLD260901C00430000` (call proche de la monnaie, bid 3,82), avec `--order-class bracket`, `--take-profit '{"limit_price":"6.00"}'`, `--stop-loss '{"stop_price":"1.00"}'`. **Identique pour `--order-class oco` et `--order-class oto`** (même code 42210000). Ce n'est donc pas une particularité de `bracket` : c'est toute la famille des ordres complexes qui est fermée aux options chez Alpaca.

### Le contrôle qui rend ce verdict solide

Un rejet seul ne prouve rien — il pouvait venir de mes paramètres, du symbole ou du compte. **Le même ordre, mêmes symbole / qty / prix limite / time-in-force, sans `--order-class`, est ACCEPTÉ** (`id=7f26c102-…`, `order_class: simple`, `status: pending_new`). Le seul facteur qui change entre l'accepté et le rejeté est la classe d'ordre. Le rejet porte bien sur elle.

**À ne pas confondre avec un test concluant : `alpaca order submit --dry-run` accepte parfaitement le bracket sur une option** et imprime un corps de requête impeccable (`order_class: bracket` avec ses deux jambes). Ce flag n'imprime que la requête locale, il ne l'envoie jamais. S'être arrêté là aurait produit la conclusion exactement inverse de la vérité.

### Nettoyage — le compte est rendu tel qu'il a été trouvé

L'ordre de contrôle accepté a été **annulé** : `status: canceled`, `filled_qty: 0`, plus aucun ordre ouvert. La position de test `SPY260831P00764000` (qty 2) est intacte, et aucune position n'a été créée — le prix limite était volontairement placé très en dessous du marché (2,00 $ contre un bid à 3,82 $) précisément pour qu'aucun test ne puisse remplir.

### Ce que ça implique pour le projet

**Rien à changer.** `manage_exits()` par polling n'est pas un pis-aller en attendant mieux : c'est le **seul** mécanisme disponible pour des sorties automatiques sur options chez Alpaca. La piste « bracket côté broker » issue de la recherche communautaire est fermée pour ce projet, et le point 3 du brief (« implémenter en plus du polling ») est sans objet. Conformément au brief, **aucun code n'a été modifié** sur cette base.

C'est aussi une limite qui mérite d'être **dite** plutôt que tue : un juge qui se demande pourquoi les sorties sont surveillées par un cron toutes les 15 minutes au lieu d'être posées chez le broker a maintenant une réponse mesurée, avec le code d'erreur de l'API à l'appui.

### 📄 Write-up vérifié au passage

`submission/Hindsight_Alpha_Writeup.docx` — géométrie réelle lue dans le XML : **Letter 8,5×11", marges 0,43"/0,5", zéro saut de page explicite**, corps en 9–9,5 pt, 673 mots. Rendu à cette géométrie exacte via Chrome headless : **1 page**, remplie à environ la moitié de la hauteur — la contrainte « one-page write-up » du règlement est tenue avec de la marge. *(Réserve : ce rendu passe par `textutil`→HTML, donc il est fidèle sur la longueur, pas sur la typographie finale de Word.)*

**Chiffres recoupés un par un contre les fichiers sources, tous justes** : concentration « 68,5–82,6 % » = GLD 20d 68,5 % et SPY 10d 82,6 % (`BACKTEST_RESULTS.md`) ; « 52–102 trades » = XLV 10d 52 et SPY 10d 102 ; « win rate 45,1–57,1 % » = SPY 45,1 % et GLD 57,1 % ; désaccord XLK (90d plein / 10d in-sample) exact ; Sharpe 1,60 / 1,96 / 1,44 = 1,598 / 1,956 / 1,442 arrondis (`STRATEGY_COMPARISON.md`).

🟡 **Une imprécision de vocabulaire, signalée sans être corrigée** (le write-up est un livrable de Spap) : il écrit « Sharpe 1.60 » là où la source dit « **in-sample** Sharpe », et `STRATEGY_COMPARISON.md` porte un avertissement explicite disant de ne pas lire cette colonne comme un verdict isolé — le classement s'inverse selon la statistique choisie. Le write-up reste honnête par ailleurs (il assume la concentration et le refus sur XLK), mais ajouter « in-sample » coûterait deux mots et fermerait la seule prise possible sur ce paragraphe.

---

## 🔴 25/08 (Terminal) — trouvé par accident, et c'est le point le plus grave de la journée : **le moniteur de sorties n'a pas tourné une seule fois aujourd'hui**

*Pas cherché : repéré parce que `git status` montrait `decision_log.jsonl` modifié alors que je n'y avais rien écrit. Le fichier contenait **11 échecs consécutifs** du job launchd, de 13:13 à 17:45 UTC, tous identiques.*

### Le symptôme

```
AlpacaCLIError: alpaca clock failed (exit 1):
"could not reach https://paper-api.alpaca.markets/v2/clock:
 dial tcp: lookup paper-api.alpaca.markets: no such host"
```

`monitor_exits.py` meurt à la toute première ligne utile (`alpaca_cli.get_clock()`, ligne 176), avant d'avoir regardé la moindre position. **Onze fois de suite.** Le dernier échec datait de quelques minutes quand je l'ai trouvé.

### Ce que ce n'est PAS — éliminé par test, pas par raisonnement

- **Pas le `PATH`** : le binaire `alpaca` est bien dans `/Users/s-pap/.local/bin`, qui est explicitement sur le `PATH` du plist.
- **Pas l'environnement minimal de launchd** : rejoué `alpaca clock get` avec exactement `PATH`+`HOME`+les deux clés, et même **sans** `HOME` — **les trois réussissent**.
- **Pas une mauvaise config du job** : `launchctl kickstart -k` déclenché à la main → **succès, code 0**, position lue correctement (`SPY260831P00764000: holding (-20.0%)`).

### La cause, prouvée par recoupement horaire

`pmset -g log` montre que le Mac a dormi toute la journée sur batterie, ne se réveillant qu'en **DarkWake** (réveil de maintenance) 2 à 6 secondes à la fois. En convertissant les horodatages d'échec (UTC) en heure locale, **chacun tombe à la seconde près sur un DarkWake** :

| échec du job (local) | DarkWake `pmset` | écart |
|---|---|---|
| 17:33:29 | 17:33:28 | 1 s |
| 18:00:10 | 18:00:10 | 0 s |
| 18:34:06 | 18:34:06 | 0 s |
| 18:45:17 | 18:45:12 | 5 s |
| 19:17:25 | 19:17:22 | 3 s |
| 19:45:41 | 19:45:40 | 1 s |

launchd honore `StartCalendarInterval` pendant ces réveils de maintenance, mais le Wi-Fi n'est pas réassocié à ce moment-là : le DNS échoue, le job meurt, et la machine se rendort 2 à 6 secondes plus tard. Le test manuel réussit uniquement parce que le Mac était réveillé pour de bon (`Wake ... lid/UserActivity` à 19:46).

C'est aussi ce qui explique les horodatages **hors grille** (13:13, 13:42, 14:35, 16:45, 17:17…) alors que le job est planifié aux :00/:15/:30/:45 — ce ne sont pas les créneaux prévus, ce sont les réveils.

### Pourquoi c'est grave pour le 31/08 → 3/09

**Les sorties automatiques sont le seul mécanisme de protection des positions de ce projet** — et la section précédente vient d'établir qu'Alpaca **refuse les ordres bracket/OCO sur les options**, donc il n'existe aucun filet côté broker pour prendre le relais. Les deux faits se combinent : si le Mac dort pendant la semaine jugée, une position peut dépasser −50 % sans que rien ne la ferme, et sans qu'aucune alerte ne parte. Les 11 échecs d'aujourd'hui sont passés totalement inaperçus — ils n'ont été vus que parce que `git status` a signalé un fichier modifié.

### Pistes, à trancher par Spap — rien n'a été implémenté ici

1. **Le plus simple et le plus sûr** : Mac branché sur secteur et empêché de dormir pendant les heures de marché de la semaine jugée (`caffeinate -dimsu` lancé le matin, ou Réglages → Batterie → empêcher la veille sur adaptateur). Ne touche à aucun code.
2. **Rendre le job résilient** : une reprise sur échec DNS dans `monitor_exits.py` (quelques tentatives espacées) — mais inutile si la machine se rendort en 2 secondes, le réveil est trop court pour attendre le Wi-Fi.
3. **Rendre l'échec visible** : aujourd'hui un job mort n'alerte personne. Le tableau de bord ne distingue pas « rien à faire » de « n'a jamais tourné ».

*Conformément au brief, aucun code, aucun plist et aucun seuil n'ont été modifiés sur cette base — c'est un constat mesuré, pas une décision prise.*

---

## 🟢 25/08 (Cowork) — piste 3 du terminal (« rendre l'échec visible ») construite : indicateur de santé du moniteur de sortie sur le dashboard

*Suite directe de la trouvaille DarkWake ci-dessus. Spap a validé explicitement (« Oui, construis-la maintenant ») la piste 3 listée par le terminal : aujourd'hui le dashboard ne distingue pas « rien à faire » de « n'a jamais tourné » — les 11 échecs du jour n'ont été vus que par accident via `git status`, pas via la page publique que les juges regardent.*

### Ce qui a été ajouté — `docs/index.html` uniquement, lecture seule, aucun changement de comportement de trading

Une bannière calculée **entièrement côté client**, à partir de `data.json.recent_decisions` (déjà publié par `publish_dashboard.py` via `decision_log.read_log(limit=30)`, déjà newest-first) :

- Filtre les entrées `run_type === 'exit_monitor'`, prend la plus récente.
- Âge calculé contre `Date.now()` du **visiteur**, pas contre l'heure de génération de `data.json` — reste juste même si la page n'est pas régénérée entre deux visites.
- Compte les échecs consécutifs en partant de la plus récente entrée `exit_monitor` et en s'arrêtant au premier `outcome !== 'error'`.
- Quatre paliers : ⚪ muted si aucune entrée `exit_monitor` n'existe encore ; 🔴 rouge si ≥3 échecs consécutifs ; 🟡 jaune si pas de série d'échecs mais dernier passage il y a plus de 45 min (3× le cycle de 15 min, pour tolérer un raté isolé sans fausse alerte) ; 🟢 vert sinon.

### Vérifié avant d'être laissé sur disque

Extrait la fonction du fichier réel (`docs/index.html` → `/tmp/dash.js`) avec un faux `document.getElementById` en Node, **10 scénarios** testés : aucune donnée, cas sain récent, exactement 3 échecs consécutifs, 11 échecs consécutifs (forme exacte de l'incident réel du jour), stale sans série d'échecs, frontière exacte 45 min (doit rester vert), 46 min (doit passer jaune), 2 échecs seulement — sous le seuil rouge, doit rester vert, entrée `run_type` non-`exit_monitor` plus récente qui ne doit pas fausser le tri, timestamp manquant. **Les 10 passent.**

Rejoué ensuite contre le **vrai** `decision_log.jsonl` (les 28 lignes réelles, dont les 11 échecs du DarkWake) : résultat `🔴 Exit monitor: 11 consecutive failures, last check 1h 14m ago` — correspond exactement à l'incident documenté ci-dessus, pas une donnée synthétique inventée pour faire joli.

Syntaxe JS validée (`new Function(...)` sans exception) et HTML re-parsé sans erreur après l'édition.

### Pas fait ici

Aucun commit — comme toujours depuis Cowork, le fichier reste modifié sur disque pour une session terminal. Rien dans `publish_dashboard.py` ou `decision_log.py` n'a été touché : la bannière ne consomme que des données déjà publiées.

---

## 🔴🟢 25/08 (Cowork) — grande passe "cherche encore" demandée explicitement par Spap : un vrai bug trouvé en confrontant la bannière aux données réelles, 3 agents dispatchés en parallèle, et une série de correctifs de présentation

*Spap a demandé, en une seule fois : chercher encore ce qui a pu être oublié, chercher de nouveaux axes, chercher des règles ratées, explorer le dossier ligne par ligne, mobiliser tous les outils disponibles, contrôler et double-contrôler, et revenir avec une solution plutôt qu'un problème — avec l'objectif explicite de viser la première place, pas un top 10.*

### Le vrai bug, trouvé en vérifiant la bannière de santé (construite plus tôt le même jour) contre les VRAIES données du disque, pas contre des scénarios synthétiques

En relisant `monitor_exits.log` et `decision_log.jsonl` pour préparer le brief terminal suivant, découverte que **le moniteur a réellement récupéré depuis 17:55** (confirmé par le log réel : contrôles réussis toutes les 15 min de 17:55 à au moins 19:15) — mais `decision_log.jsonl` ne contient toujours QUE les 11 échecs comme dernières entrées `exit_monitor`, parce que `monitor_exits.py` n'écrit jamais dans ce fichier pour un contrôle routinier réussi (`noteworthy = outcome=="error" or bool(surfaced)` — voir son propre commentaire, déjà présent avant aujourd'hui, jamais remis en question jusqu'à ce que la bannière construite ce matin en dépende directement).

**Conséquence concrète, non hypothétique** : la bannière construite plus tôt aujourd'hui, basée uniquement sur `decision_log.jsonl`, afficherait **"🔴 11 consecutive failures" indéfiniment**, potentiellement pour le reste de la semaine jugée, même des heures après que le problème soit résolu — une fausse alerte qui ne se corrige jamais toute seule, pire que l'absence d'indicateur.

**Corrigé par un mécanisme séparé, pas en modifiant `decision_log.jsonl`** (son filtre "noteworthy only" reste intentionnellement intact — c'est la bonne conception pour SON rôle, un journal curé, pas pour la santé instantanée) :
- `monitor_exits.py` : nouveau fichier `monitor_last_run.json` (gitignored, même catégorie que `state.json`/`monitor_exits_dedup.json`), écrit **à chaque run, sans condition**, via `_write_last_run_status()` appelée dans le `finally` — résiste à toute exception (capture large, jamais autorisé à interférer avec la vraie logique de protection des positions).
- `publish_dashboard.py` : lit ce fichier (best-effort, `None` si absent/corrompu) et le republie dans `data.json` sous `monitor_status`.
- `docs/index.html` : `renderMonitorHealth()` réécrite pour utiliser `monitor_status` comme signal primaire (le vrai dernier run, succès ou non), avec repli automatique sur l'ancienne logique `decision_log`-seule si `monitor_status` est absent (compatibilité avec un `data.json` généré avant ce correctif).
- **Ajout non prévu au départ, trouvé en réfléchissant à la staleness** : un contrôle d'heures de marché côté client (`isUsMarketHoursNow()`, via `Intl` + fuseau `America/New_York`, DST géré automatiquement) — sans ça, la bannière passerait au jaune "stale" **toutes les nuits et tous les week-ends**, puisque le moniteur est censé être silencieux des heures durant en dehors du marché. Un indicateur qui crie au loup chaque soir se fait ignorer exactement quand une vraie coupure pendant les heures de marché compte.

**Vérifié, pas juste écrit** : 3 scénarios Python isolés sur `_write_last_run_status`/`_read_monitor_status` (écriture normale, écrasement sur erreur, résilience sur chemin non-inscriptible) ; 10 scénarios JS sur `renderMonitorHealth` (dont le cas exact de l'incident réel — 11 échecs + récupération — qui DOIT rester vert, pas rouge) ; 6 scénarios sur `isUsMarketHoursNow` avec des timestamps UTC fixes (mercredi en séance, avant l'ouverture, exactement à la clôture, juste avant clôture, samedi, dimanche) — tous corrects, DST inclus (août = EDT). `py_compile` + `pyflakes` propres sur tout `*.py` après coup, HTML re-parsé sans erreur.

### 3 agents dispatchés en parallèle pour l'audit "ligne par ligne" demandé

**Agent 1 — audit code + fichiers du repo** : verdict global, le code est déjà exceptionnellement propre (aucun bug fonctionnel neuf après relecture complète des 13 `.py` racine). Trouvé : 2 imports morts (`json` dans `agent.py`, `json` + `daily_returns` dans `backtest.py` — confirmés par `pyflakes`, **corrigés**), et trois incohérences documentaires à fort impact (README daté, script vidéo citant un chiffre de l'ancien univers abandonné, dashboard public déjà en ligne périmé).

**Agent 2 — re-vérification du règlement officiel lablab/Alpaca** : confirme tout ce qui était déjà su, et trouve du **neuf et important** :
- Soumission finale doit inclure l'**Alpaca paper trading account ID** ("this allows the judging team to identify your trading activity and evaluate your P&L performance") — déjà anticipé par construction dans `publish_dashboard.py` (commentaire explicite déjà présent avant cette recherche), rien à changer.
- Write-up d'une page doit couvrir "AI logic, risk gates, and Alpaca infrastructure implementation" — déjà le cas.
- Vidéo : **maximum 5 minutes, format MP4**, structure "introduction → discuter la présentation PDF → montrer les fonctionnalités" — script vidéo mis à jour en conséquence (voir plus bas).
- Cover image de soumission : **PNG/JPG, ratio 16:9 recommandé** — **pas encore préparée, action restante**.
- Clause "Submissions must be original and MIT-compliant" — **déjà respecté**, `LICENSE` déjà en MIT pur (vérifié en le relisant intégralement).
- "Social engagement" noté sur la qualité ET l'engagement généré (likes/commentaires/partages), pas juste sur le fait de poster — renforce l'importance de vraiment poster les brouillons de `SOCIAL_POSTS_DRAFT.md`, pas de les laisser en brouillon.
- Concurrence : correction par rapport à la recherche du 25/08 matin — plusieurs équipes ont maintenant des pitchs très aboutis (garde-fous déterministes, multi-agents, stat-arb). **Point rassurant confirmé malgré ça** : aucune équipe repérée ne mentionne le concept de "hindsight leakage"/"look-ahead bias" avec un mécanisme de comparaison fenêtre-pleine vs in-sample — la différenciation du projet tient toujours.

**Agent 3 — audit des livrables Presentation & Execution** : trouve 2 erreurs factuelles dans `Video_Script.md` (le script affirmait "aucune fuite" alors que `hindsight_guard` détecte un vrai leak sur XLK — la meilleure preuve du concept était occultée plutôt que montrée ; "trois symboles" au lieu de quatre) et un manque critique dans `README.md` : **le lien du dashboard public n'apparaissait nulle part dans le fichier**, alors que le règlement exige une "Application URL" visible.

### Correctifs appliqués suite à ces trois audits

- **`Video_Script.md`** : les deux erreurs factuelles corrigées (le cas XLK refusé devient la preuve centrale de la section démo, plus un "s'il y en a un" hypothétique ; les vrais chiffres du write-up — 68,5–82,6% de concentration, 52–102 trades, 45–57% de réussite — remplacent le "53 à 83%" périmé de l'ancien univers SPY/QQQ/IWM) ; durée cible unifiée à ~2:45 (au lieu de deux chiffres contradictoires) ; nouvelles contraintes officielles ajoutées aux notes de tournage (5 min max, MP4, mentionner le write-up PDF, cover image 16:9 à préparer).
- **`README.md`** : lien du dashboard ajouté dès la 3e ligne utile ; TL;DR de 5 phrases ajouté avant la prose longue ; tableau condensé des résultats de backtest ajouté (4 lignes, référence vers `BACKTEST_RESULTS.md` pour le détail) ; le fait honnête que `momentum_strategy` passe `hindsight_guard` proprement sur 4/4 symboles contre 3/4 pour la stratégie réellement tradée, auparavant seulement dans `STRATEGY_COMPARISON.md`, maintenant visible dans le README ; section "Status" réécrite pour refléter la réalité du jour — le blocage TCC/Full Disk Access est résolu (le moniteur tourne réellement), la trouvaille DarkWake et sa parade (bannière) sont documentées, l'exigence de solde $100k et son risque de régénération de clé API sont rappelés avant le kickoff.
- **`agent.py`, `backtest.py`** : imports morts retirés, `pyflakes` propre sur tout le repo Python.

### Ce qui reste, honnêtement, pas caché

- **Cover image PNG/JPG 16:9** : pas préparée. Nécessite un vrai choix visuel, pas juste du code — à faire par Spap ou à discuter avant qu'un visuel générique soit produit à sa place.
- **Glossaire/tooltips pour le jargon du dashboard** (HV rank, in-sample, hindsight_guard) et un vrai test dans un navigateur mobile réel : identifiés par l'agent 3 comme améliorations utiles mais de moindre impact que ce qui a été corrigé ici — pas faits, pour rester concentré sur ce qui avait le plus d'impact avant la deadline.
- **Le dashboard public en ligne reste périmé tant qu'une session terminal n'a pas republié** `docs/data.json` (avec `monitor_status`) et poussé `docs/index.html`, `README.md`, `Video_Script.md`, `monitor_exits.py`, `publish_dashboard.py`, `agent.py`, `backtest.py`, `.gitignore` — voir le brief terminal mis à jour.

---

## 🔴🟢 25/08 (Cowork) — cherche encore, sur mon propre travail de ce soir : un vrai bug de rendu Markdown trouvé et corrigé, le reste vérifié plus profondément et confirmé propre

*Cette passe s'est concentrée délibérément sur le code écrit CE SOIR (`monitor_exits.py`, `publish_dashboard.py`, `docs/index.html`, `README.md`) — le même réflexe que plusieurs passes précédentes du 24/08 (13e, 14e, 22e→23e) : le code le plus récent est celui le moins relu, donc le plus probable à cacher un défaut.*

### 🔴 Trouvé : le nouveau titre "TL;DR" du README cassait le rendu Markdown, prouvé en le rendant pour de vrai, pas en le relisant

Le titre `### TL;DR (...)` ajouté plus tôt ce soir contenait un retour à la ligne brut au milieu de la parenthèse explicative. En Markdown, un titre ATX (`###`) ne prend que la première ligne — le reste (*"summary were both missing before, and a judge with 5 minutes is exactly who that hurts)"*) devenait un paragraphe orphelin, commençant en pleine phrase, juste avant le vrai contenu du TL;DR. **Reproduit en rendant le fichier avec un vrai moteur Markdown** (`python-markdown` + extension `tables`) plutôt qu'en le relisant à l'œil : le `<h3>` réel ne contenait que *"TL;DR (added 25/08, "cherche encore" pass — the link above and this"*, tronqué, suivi d'un `<p>` qui commence par *"summary were both..."*. Exactement le genre de changement qui "a l'air correct" en relisant le texte source mais casse une fois rendu — même famille que le bug de liste Markdown orpheline trouvé dans ce même README le 24/08 (19e passe).

**Corrigé** : titre réduit à `### TL;DR` seul, l'explication déplacée en italique juste en dessous (même style que l'intro de la section "Backtest, at a glance" ajoutée à côté). Revérifié en rendant à nouveau : `<h3>` propre (`"TL;DR"`), plus aucun paragraphe orphelin.

**Balayage complet fait dans la foulée**, pas juste ce seul titre : script qui détecte toute ligne `#`/`##`/`###` suivie immédiatement (sans ligne vide) d'une ligne non-titre — a remonté d'autres cas, tous **faux positifs vérifiés** (des blocs de code bash après `## Setup`, légitimes en Markdown). Un premier passage avait aussi semblé montrer des `<h1>` fantômes à l'intérieur des blocs de code bash (des commentaires `#` interprétés comme des titres) — **faux positif de mon propre outil de test**, pas du fichier : l'extension `fenced_code` manquait dans mon appel à la librairie Markdown. Refait avec l'extension correcte : un seul vrai `<h1>` (`"Hindsight Alpha"`), tous les autres titres propres. `submission/Video_Script.md` passé au même test : 8 titres, tous corrects, rien à corriger.

### 🟢 Vérifié plus profondément, rien de cassé : le nouveau code de `monitor_exits.py` rejoué via son vrai `main()`, pas juste la fonction isolée

Les tests de ce soir sur `_write_last_run_status()` appelaient la fonction directement, en isolation — jamais le vrai `main()` de bout en bout. Rejoué avec `alpaca_cli.get_clock`/`risk_gates.manage_exits` mockés (pas réécrits) sur 4 cas réels : run normal réussi, marché fermé, `manage_exits()` qui lève une exception en cours de route. Les 4 cas écrivent `monitor_last_run.json` avec le bon `outcome`/`market_open` dans tous les cas, y compris quand `main()` propage bien l'exception (le comportement voulu, pas un régression) — `record.get("market_open")` reste `None` proprement plutôt que de lever une `KeyError` quand `get_clock()` échoue avant d'avoir pu le renseigner (exactement le scénario DarkWake du jour). Import de `publish_dashboard.py` (qui importe maintenant `monitor_exits` pour partager `MONITOR_STATUS_FILE`) revérifié sans effet de bord ni import circulaire.

Rien d'autre trouvé cette passe — le reste du nouveau code de ce soir (bannière de santé, surlignage des refus XLK, heures de marché) tient face à une relecture adversariale supplémentaire.

### 🟡 Erreur commise EN VÉRIFIANT, corrigée immédiatement : mon propre test a pollué `decision_log.jsonl` pour de vrai

Le test end-to-end ci-dessus mockait `alpaca_cli.get_clock` et `risk_gates.manage_exits`, mais **pas** `decision_log.log_run_or_dump` — le cas "manage_exits lève une exception" a donc un `outcome="error"` que le code juge à raison "noteworthy", et a réellement écrit une ligne bidon (`"error": "RuntimeError: boom"`) dans le vrai `decision_log.jsonl` du dépôt. Repéré immédiatement par `git status` (même réflexe que celui qui avait révélé l'incident DarkWake ce matin — surveiller les fichiers qui ne devraient pas bouger). **Corrigé** : ligne retirée, fichier revérifié `git diff` vide (identique à `HEAD`). Aucune trace committée — l'erreur n'a existé que sur le disque local, quelques minutes.

Vaut la peine d'être écrit tel quel plutôt que discrètement réparé sans le dire : c'est exactement le principe que ce projet applique au reste du code (une trace fausse est un vrai défaut, même auto-infligé) appliqué à ma propre séance de vérification.

---

## 🟢 25/08 (Cowork) — cherche encore, sur demande explicite : audit complet du mécanisme hindsight_guard + recherche de littérature/concurrence "à contre-courant"

*Spap a demandé deux choses précisément : chercher d'autres stratégies "à contre-courant" comme la nôtre, et vérifier partout le mécanisme de détection de fuite pour voir si quelque chose avait été raté.*

### Audit interne — rien de cassé, un point mineur purement théorique noté

`grep` exhaustif de tout usage réel de `check_selection_leakage` dans le dépôt : 4 sites d'appel (`agent.py` en live, `backtest.py`, `compare_strategies.py` ×2 pour vol_strategy et momentum_strategy) — cohérents entre eux, même `IN_SAMPLE_HOLDOUT_DAYS = 20` dans `vol_strategy.py` ET `momentum_strategy.py` (dupliqué en constante séparée dans chaque module plutôt que partagé, mais vérifié identique dans les deux — pas un bug). Les deux seules mentions dans `monitor_exits.py`/`risk_gates.py` sont des commentaires expliquant pourquoi le chemin de SORTIE ne passe délibérément jamais par le garde-fou (les sorties gèrent des positions déjà ouvertes, pas une nouvelle sélection de paramètre) — conforme au design, pas un oubli. Seul point relevé, purement théorique : `max(scores, key=...)` départage une égalité exacte de score par l'ordre d'insertion des candidats, pas par une règle de bris d'égalité explicite — sans risque pratique avec des scores réels en virgule flottante calculés sur des données de marché (une égalité exacte n'arrive jamais en pratique), donc noté et pas corrigé.

### Recherche externe — le vrai résultat de cette passe : `hindsight_guard` n'est pas une invention isolée, et c'est une bonne nouvelle une fois dit honnêtement

Recherché la littérature quant établie sur exactement ce problème (sélection de paramètre biaisée par des données non disponibles au moment de la décision). Trouvé une vraie parenté, avec ce qui est repris et ce qui ne l'est pas :

- **Probability of Backtest Overfitting / combinatorially symmetric cross-validation** (Bailey, Borwein, López de Prado & Zhu, 2015) — la parenté la plus directe : comparer un gagnant in-sample contre son rang out-of-sample.
- **Walk-forward optimization** (Pardo) — revalider qu'un paramètre optimal reste optimal en avançant dans le temps.
- **Deflated Sharpe Ratio** (Bailey & López de Prado, 2014) — l'esprit ("ne pas faire confiance à un Sharpe non corrigé du nombre d'essais"), sans en reprendre la formule.

**Ce qui N'EST PAS repris**, dit honnêtement : aucune correction formelle de multiple-testing sur les 5 fenêtres candidates, pas de partitions combinatoires, pas de bootstrap — `hindsight_guard` est une version dégradée à deux partitions (historique complet vs historique moins 20 jours), pas l'appareil statistique complet de ces méthodes.

**La vraie différence, et l'argument à mettre en avant** : ces méthodes valident une stratégie **une fois, à la conception**, puis déploient. Ce projet refait le même test de désaccord **avant chaque décision live**, avec refus catégorique possible n'importe quel jour — un paramètre validé hier peut être refusé aujourd'hui. C'est la réponse prête si un juge connaissant cette littérature demande "n'est-ce pas juste du walk-forward validation ?"

**Concurrence** : toujours aucun projet trouvé (dans le hackathon Alpaca ou l'écosystème lablab.ai plus large) combinant un test de désaccord de sélection ET un refus par décision individuelle en production. Une équipe de plus repérée avec un angle voisin en esprit (`Dawn Of The Trading Agents` — débat interne bull/bear/risk avant chaque trade, mécanisme qualitatif d'auto-contestation, pas un test statistique) — pas un concurrent direct sur le mécanisme, mais le seul autre projet du pool actuel qui met en avant l'auto-contestation plutôt que la performance brute. `JudyAI WaveRider` (déjà connu du 24/08) confirme que "l'honnêteté méthodologique comme argument central" n'est pas un angle inédit dans ce type de hackathon, mais valide sa stratégie une fois au design (walk-forward sur 8 fenêtres), pas à chaque décision — même distinction que ci-dessus.

**Corrigé/ajouté** : nouvelle sous-section dans `README.md` ("Where this sits in the existing literature — not invented from nothing"), qui cite les trois techniques ci-dessus, dit honnêtement ce qui est repris et ce qui ne l'est pas, et formule l'argument du "à chaque décision, pas une fois" — vérifié en rendant le Markdown (pas juste relu) après l'édition, aucun titre cassé. Ajout d'une ligne courte dans les "Notes de tournage" de `Video_Script.md` pour que Spap ait la réponse prête en Q&A sans l'ajouter au script minuté lui-même.

---

## 🔴 25/08 (Cowork) — cherche encore : `submission/Hindsight_Alpha_Deck.pptx` n'avait jamais été relu cette session, et il mentait sur le point le plus important du projet

*Quatrième "cherche encore" de la soirée. Le write-up, le README et le script vidéo avaient tous déjà reçu les chiffres corrigés (univers SPY/GLD/XLK/XLV, leak XLK confirmé) lors de passes précédentes — mais personne n'avait pensé à relire le deck de slides lui-même. Trouvé via `markitdown submission/Hindsight_Alpha_Deck.pptx`, texte de tous les slides d'un coup.*

**Le plus grave, de loin** : le slide 8 ("HONEST RESULTS — NOT A HEADLINE NUMBER") affichait encore **"0 leaks"** comme statistique vedette — alors que c'est désormais l'argument central du projet, répété partout ailleurs, que `hindsight_guard` A détecté un vrai désaccord sur XLK (gagnant plein historique = 90j, gagnant in-sample = 10j) et le refuse en live à chaque run. Un juge qui aurait comparé le deck au write-up ou à la vidéo aurait vu une contradiction directe sur le point que ce projet existe pour prouver.

**Autres chiffres périmés trouvés sur le même slide** : "53–83%" → chiffre réel actuel 68,5–82,6% (concentration du gain sur les 5 meilleurs jours) ; "43–54%" → 45,1–57,1% (taux de succès) ; "~110 trades" → en réalité 52 à 102 trades selon le symbole ; la légende affirmait "all three symbols tested (SPY, QQQ, IWM)" — ancien univers abandonné, remplacé depuis par SPY/GLD/XLK/XLV. Le graphique natif (`chart1.xml` + son classeur Excel intégré) avait aussi une valeur légèrement périmée pour la fenêtre 10j de SPY (0,1071 vs 0,108 actuel dans `BACKTEST_RESULTS.md` — petit écart de précision entre deux runs de backtest, pas un changement d'univers). Slide 3 : nombre d'équipes inscrites encore à 442, mis à jour à 546 (dernier chiffre vérifié ce soir). Slides 6/7 (garde-fous de risque : 1%/3%/1,5%/3%/4 positions/3 pertes consécutives/30e percentile) recroisés contre les constantes réelles de `risk_gates.py`/`vol_strategy.py` — toujours exacts, rien à corriger là.

**Corrigé** : 7 remplacements de texte exact-match (vérifiés uniques avant chaque remplacement) sur `slide8.xml`, dont la phrase "0 leaks" → "1 leak caught" avec la vraie explication XLK ; la légende du graphique recadrée pour ne parler que de SPY plutôt que de prétendre à tort une uniformité sur 3 symboles ; `chart1.xml` ET son classeur Excel intégré (`ppt/embeddings/Microsoft_Excel_Worksheet1.xlsx`) patchés en cohérence (0,1071 → 0,108) pour que le graphique affiché et sa source "Edit Data" restent synchronisés ; `slide3.xml` mis à jour (442 → 546). Décision prise consciemment : ne pas reconstruire le graphique pour montrer les 4 symboles actuels (SPY/GLD/XLK/XLV) plutôt que SPY seul — gardé comme illustration ciblée SPY avec une légende honnêtement recadrée, compromis temps/risque plutôt qu'un vrai manque.

**Vérifié par le rendu, pas juste par le texte XML** : `validate.py --original` propre, conversion PDF + rasterisation des slides 3 et 8, inspection visuelle des deux images — aucun débordement de texte malgré des chaînes plus longues ("68,5–82,6%" vs "53–83%", la nouvelle phrase XLK nettement plus longue que l'originale), aucun chevauchement, mise en page intacte. `markitdown` relancé sur le fichier final : plus aucune trace de "442", "53–83", "43–54", "0 leaks", ou "SPY, QQQ, IWM" ; "546", "68.5–82.6%", "45.1–57.1%", "1 leak caught" et la phrase XLK bien présents.

`submission/Hindsight_Alpha_Deck.pptx` devient donc un nouveau fichier modifié dans `git status` — à ajouter à la liste de `BRIEF_COMMIT_INDICATEUR_SANTE_ET_WRITEUP.md`, qui n'a toujours pas été traité par une session terminal (`origin/main` toujours à `0fe900f` au dernier contrôle).

---

## 🟡 25/08 (Cowork) — cinquième "cherche encore" de la soirée : rien de nouveau, sweep systématique du même motif d'erreur sur tout le dépôt

*Après avoir trouvé le même genre de staleness deux fois de suite (write-up/README/vidéo, puis le deck), plutôt que de deviner un prochain fichier au hasard, recherche systématique (`grep`) des mêmes motifs périmés exacts — "442", "0 leaks", "53–83", "43–54", "~110 trades", "SPY, QQQ, IWM" — sur TOUT le dépôt, pas juste les livrables déjà connus.*

**Résultat honnête : aucune occurrence vivante de plus.** Les seuls résultats trouvés sont dans `PLAN_SPRINT.md` lui-même (journal historique daté, où l'ancien chiffre EST le sujet de l'entrée) et dans des `BRIEF_*.md` déjà traités/archivés (contexte historique légitime, pas une affirmation "en direct"). `agent.py:52` mentionne encore "SPY, QQQ, IWM" mais c'est volontaire — déjà noté le 24/08 comme référence à l'ANCIEN univers pour expliquer pourquoi il ne convenait pas au multi-positions.

**Trois vérifications ciblées en plus, pour être sûr** :
- `submission/Hindsight_Alpha_Writeup.docx` — jamais relu par `markitdown` cette session (le paquet `markitdown[docx]` n'était pas installé dans ce bac à sable ; installé et relancé pour de vrai, pas supposé propre). Texte extrait entièrement vérifié : univers SPY/GLD/XLK/XLV correct, 68,5–82,6%/45,1–57,1%/52–102 trades tous exacts, XLK explicitement documenté comme refusé par `hindsight_guard` — cohérent avec tout le reste. Aucune mention de "442"/"0 leaks" (le docx ne cite même pas de chiffre d'équipes inscrites, donc pas de risque de péremption sur ce point-là).
- `SOCIAL_POSTS_DRAFT.md` — jamais relu cette session. Tous les chiffres concrets (P&L, symbole tradé, nombre de refus) sont volontairement des `[placeholders]` à remplir pendant la vraie semaine de trading, pas des valeurs codées en dur — donc structurellement à l'abri de la péremption trouvée ailleurs. Rien à corriger.
- `.gitignore` — diff relu contre `origin/main` : un seul ajout (`monitor_last_run.json`), cohérent avec le correctif de bannière de santé déjà documenté plus haut. Rien de nouveau.

Pas de bug, pas de correctif cette fois — juste la confirmation, par une recherche exhaustive plutôt qu'une supposition, que la même famille d'erreur ne traîne pas ailleurs.

---

## 🟢 25/08 (Cowork) — Spap a remarqué qu'aucun garde-fou ne tournait sur ce projet : `garde_fou.py` posé, avec le skill `garde-fou-generique`

*hindsight-alpha n'a jamais eu son propre `garde_fou.py`, contrairement à SNIPER/JEU BLOCKCHAIN/OUTILS_CONTROLE_GARDE_FOU. Construit volontairement PETIT (méthode du skill : un contrôle naît d'une erreur réelle déjà commise, jamais par anticipation), avec 4 contrôles :*

1. **Journal** (forme minimale recommandée par le skill) : `PLAN_SPRINT.md` existe, aucune section datée dans le futur.
2. **`.env.hackathon` scellé** : jamais suivi par git, toujours couvert par `.gitignore` — née de la contrainte répétée des dizaines de fois cette session ("intouchable avant le 28/08"), équivalent d'un fichier `*SCELLE*.md` chez SNIPER.
3. **Refus live-trading toujours actif dans `config.py`** — vérifie mécaniquement une affirmation du write-up ("hard-enforced in config.py"), pas juste supposée vraie.
4. **Chiffres périmés** : liste noire des chaînes exactes déjà trouvées fausses dans le deck ce soir (442, "0 leaks", 53–83%, 43–54%, ~110 trades, ancien univers SPY/QQQ/IWM), recherchées dans README.md, `submission/Video_Script.md`, le docx et le pptx (extraction XML brute, bibliothèque standard uniquement — pas de dépendance externe, même philosophie que `hindsight_guard.py`).

**Testé pour de vrai, pas supposé propre — et ça a immédiatement trouvé un vrai bug dans le script lui-même** : le tout premier run a bloqué à tort sur slide 5 du deck, qui affiche honnêtement "PREVIOUS UNIVERSE: SPY, QQQ, IWM" à côté de "NOW: SPY, GLD, XLK, XLV" — un contexte légitime, pas une erreur. Même piège que "PERIME vs PERIMETRE" chez SNIPER. **Corrigé dans la minute** : chaque motif de la liste noire porte désormais une exemption de contexte optionnelle (regex cherchée dans les ~40 caractères précédents). Deuxième bug trouvé au même moment, plus subtil : l'alerte non-bloquante sur le nombre d'équipes (`\b\d{2,4}\s*teams\b`) ne se déclenchait jamais sur le pptx réel, parce que l'extraction brute des runs XML concatène le texte SANS espace entre les cases ("546teams" collé) — aucune frontière `\b` entre un chiffre et le mot précédent tous deux collés à un autre mot. Corrigé avec `(?<!\d)` à la place d'un `\b` strict. Un témoin synthétique confirme que le contrôle attrape encore un vrai cas après le correctif.

**État actuel, vérifié sur le vrai dépôt** : verdict 🟡 — une seule alerte non bloquante (le deck cite bien "546 teams", rappel qu'il faudra revérifier ce chiffre à la main avant la soumission finale, ce script ne peut pas savoir s'il a encore bougé). Aucun blocage.

**`CLAUDE.md` créé** (n'existait pas) — règle non négociable du garde-fou (on corrige le dossier, jamais le script) + rappel condensé des contraintes non négociables du sprint (compte hackathon, live trading, seuils de risque, stratégie live, force-push, réseaux sociaux) déjà répétées des dizaines de fois dans ce fichier mais jamais centralisées ailleurs.

`garde_fou.py` et `CLAUDE.md` sont deux nouveaux fichiers untracked — à ajouter au prochain commit terminal.

---

## 🟢 25/08 (Cowork) — Spap : « garde en mémoire qu'à chaque nouveau projet il faut un garde-fou » + amélioration comparée contre le modèle mature d'OUTILS_CONTROLE_GARDE_FOU

**Mémoire mise à jour, pas juste dans ce fichier** : le skill `garde-fou-generique` (celui qui pose un garde-fou dans un nouveau projet) a été réécrit via `save_skill` pour devenir PROACTIF — il se déclenchera désormais dès qu'un nouveau dossier de projet prend forme, sans attendre que Spap le demande explicitement. La description du skill cite littéralement le retard pris sur hindsight-alpha (plusieurs "cherche encore" à répétition pour rattraper des chiffres périmés qu'un garde-fou aurait attrapés du premier coup) comme leçon.

**Comparaison demandée contre le garde-fou mature d'OUTILS_CONTROLE_GARDE_FOU (1131 lignes, 22 contrôles)** — ce qui manquait au nôtre (4 contrôles, posé il y a quelques minutes) :
1. **Fichier scellé vérifié par hash, pas juste par git** — le nôtre ne vérifiait que "pas suivi par git" pour `.env.hackathon`, ce qui protège contre une fuite poussée mais rien contre une modification purement locale. `verifier_scelles.py` chez SNIPER hash le contenu. **Corrigé** : nouveau registre local `.garde_fou_scelles.json` (gitignored — ajouté à `.gitignore`), empreinte SHA-256 enregistrée à la première lecture, comparée ensuite ; tout changement bloque avec message explicite.
2. **Rappel "même vert, ceci n'est pas une preuve"** affiché à chaque run — présent chez SNIPER, absent du nôtre. **Ajouté**, adapté à l'échelle réelle de notre script (4 contrôles, pas 22).
3. Non ajoutés, délibérément, et pourquoi : l'escalade à 48h avec registre persistant des alertes (utile si des alertes traînent longtemps sans être vues, mais notre garde-fou se relance à la demande dans une session active, le risque d'alerte qui pourrit en silence est bien moindre qu'avec les rythmes de SNIPER) ; l'auto-test par mutation intégré au script (fait manuellement pendant la construction, pas automatisé — pourrait être ajouté si un futur contrôle s'avère fragile) ; les ~18 sous-contrôles spécifiques au sujet de SNIPER (jugement, propositions, statuts périmés...) qui n'ont pas d'équivalent dans hindsight-alpha aujourd'hui, exactement comme le skill le recommande ("ne pas importer aveuglément").

**Testé pour de vrai avant de déclarer fini, comme d'habitude** : témoin sur un dossier temporaire — première lecture du fichier scellé enregistre l'empreinte sans bloquer (🟡, "première lecture") ; une deuxième lecture sans changement reste silencieuse ; une modification simulée du fichier scellé bloque bien (🔴, message explicite). `.garde_fou_scelles.json` confirmé ignoré par git (`git check-ignore -v`).

**État réel du dépôt après ces ajouts** : verdict 🟡 inchangé (toujours la seule alerte sur le nombre d'équipes du deck), plus l'empreinte de `.env.hackathon` maintenant enregistrée pour de bon.

---

## 🟢 25/08 (Cowork) — Spap : « compare aux bons garde-fous déjà créés sur GitHub » : recherche externe réelle, deux vrais projets open source comparés, deux ajouts, un bug trouvé et corrigé dans le hook lui-même

*Clarifié avec Spap : les garde-fous SNIPER/JEU BLOCKCHAIN/OUTILS_CONTROLE_GARDE_FOU ne sont PAS sur GitHub (vérifié : aucun n'a de `.git`) — la demande portait sur de vrais projets publics. Recherche web faite, pas supposée.*

**Trois projets réels trouvés et comparés** :
- **gitleaks** (27 700+ étoiles, MIT) — le scanner de secrets de référence. Scanne l'**historique complet** du dépôt, pas juste son état actuel.
- **pre-commit** (framework standard pour wirer des hooks git) et **danger-js** (~5 500 étoiles) — codifient des règles propres à une équipe, tournent automatiquement à chaque commit/PR, pas sur demande.
- **doc-drift / DriftGuard** (détection de dérive documentaire en CI) — régénère les chiffres depuis la source et compare, plutôt que de connaître à l'avance les chaînes déjà fausses.

**Deux gaps corrigés ce soir** :
1. Notre contrôle `.env.hackathon` ne regardait que `git ls-files` (l'état ACTUEL de l'index) — un fichier ajouté par erreur puis retiré avec `git rm --cached` disparaît de cette liste mais reste dans l'historique, récupérable par quiconque clone. **Ajouté** : `git log --all --full-history -- .env.hackathon`, bloque si le fichier a jamais existé dans un commit, même ancien.
2. Le vrai trou le plus profond n'était pas un contrôle manquant : rien ne forçait `garde_fou.py` à tourner. **Ajouté** : `githooks/pre-commit`, un hook versionné (activable via `git config core.hooksPath githooks`, documenté dans `CLAUDE.md`) qui relance `garde_fou.py` à chaque commit et refuse si 🔴.

**Bug trouvé en testant le hook pour de vrai, corrigé dans la minute** : `set -e` en tête du script tuait le hook dès que `python3 garde_fou.py` sortait en erreur — AVANT que la ligne `code=$?` ne s'exécute. Le commit était bien bloqué (par accident, via le code de sortie brut du sous-processus), mais le message personnalisé "COMMIT REFUSÉ..." ne s'affichait jamais. Retiré `set -e`, témoin relancé : message affiché correctement.

**Un troisième gap identifié, PAS corrigé ce soir, délibérément** : le pattern doc-drift (régénérer les chiffres sources et comparer) serait strictement plus robuste que notre liste noire `MOTIFS_PERIMES` actuelle — la liste noire ne rattrape que la RÉCIDIVE d'une erreur déjà vue, pas une NOUVELLE staleness jamais rencontrée. Non implémenté ce soir : demanderait de définir mécaniquement "la source de vérité" pour chaque chiffre cité (BACKTEST_RESULTS.md pour les stats, une vraie requête lablab.ai pour le nombre d'équipes) et un vrai régénérateur — trop de travail pour la fin de cette session, mais c'est la prochaine amélioration la plus honnête à faire, notée ici pour ne pas se perdre.

**Testé pour de vrai, comme toujours** : témoin sur un dépôt git jetable — un commit avec un dossier rouge est bien refusé (`your current branch does not have any commits yet` confirmé), un commit propre passe. Vérifié sur le vrai dépôt : `.env.hackathon` absent de tout l'historique git réel (silence confirmé), verdict 🟡 inchangé.

---

## 🟢 25/08 (Cowork) — Spap : « fait le travail jusqu'à la fin » : la source de vérité mécanique (contrôle 5) implémentée, testée, trois bugs trouvés et corrigés en la testant

**Ce que le contrôle 4 (liste noire) ne pouvait structurellement pas faire** : rattraper une staleness qu'on n'a encore JAMAIS vue — seulement la récidive d'une erreur déjà connue. Le contrôle 5 comble ça pour les 4 catégories de chiffres qui ont une vraie source mécanique dans ce dépôt :

1. **Plages taux de succès / concentration / nombre de trades** — calculées à l'instant depuis `BACKTEST_RESULTS.md` : pour chaque symbole "propre" (non fuité selon le verdict `hindsight_guard` du fichier), on prend sa fenêtre "vettée" (le gagnant plein historique) et on lit son taux de succès, sa concentration et son nombre de trades À CETTE fenêtre précise — pas la meilleure ligne du tableau, la ligne que l'agent traderait réellement aujourd'hui. Min/max sur les symboles propres → la plage attendue.
2. **Nombre de leaks** — compté directement dans le même fichier.
3. **Univers actuel** — lu depuis `DEFAULT_UNIVERSE` dans `agent.py`, pas recopié à la main.
4. **Seuils de risque** — extraits de `risk_gates.py`/`vol_strategy.py` là où le nom de la constante est cité entre backticks juste avant le chiffre.
5. **Sharpe vetté** — comparé à la liste des vraies valeurs dans `STRATEGY_COMPARISON.md`.

Toutes ces valeurs source sont recalculées À CHAQUE run, jamais mémorisées — si `BACKTEST_RESULTS.md` change demain (nouveau backtest), le contrôle change de cible tout seul, sans qu'on ait besoin d'éditer `garde_fou.py`.

**Trois bugs trouvés en le testant pour de vrai contre les 4 vrais livrables, tous corrigés dans la foulée** :
1. Une fenêtre de proximité de 40 caractères après `` `MAX_OPEN_POSITIONS` `` attrapait le "1" d'une phrase suivante sans rapport ("...positions (`MAX_OPEN_POSITIONS`), a 1%-of-equity per-trade cap...") et le comparait à tort à cette constante (qui vaut 4). Resserré : le chiffre doit suivre IMMÉDIATEMENT le nom (virgule ou parenthèse), pas n'importe où dans une fenêtre large.
2. Un `elif` sur une seule fenêtre "texte avant le nombre" faisait retomber une plage de taux de succès déjà validée sur le contrôle concentration, parce que la phrase réelle mentionne les deux stats à la fois dans un rayon de 80 caractères. Corrigé en prenant l'ancre la plus proche, pas la première trouvée.
3. Plus subtil, propre au pptx : sa structure est "chiffre d'abord, légende ensuite" dans les encarts (contrairement au README/docx, en prose, légende avant le chiffre) — mon fix n°2 ne regardait que le texte AVANT le nombre, donc ratait "45.1–57.1%win rate on..." où l'ancre suit le nombre. Corrigé en cherchant des deux côtés (avant ET après), distance minimale l'emporte.
4. Un faux positif à part, pas un bug de logique mais de jugement : README dit délibérément "~50-100 trades" (approximation arrondie, marquée par le "~") — bloquer ça punirait une honnêteté volontaire. Exemption ajoutée pour "~"/"environ"/"about"/"roughly" juste avant une plage.

**Testé dans les deux sens, comme toujours** : un témoin avec des chiffres délibérément faux dans les 7 catégories (taux de succès, concentration, trades, leaks, univers, seuil de risque, Sharpe) — tout bloque, avec le bon message et le bon chiffre attendu à chaque fois. Le même témoin avec les chiffres corrects — verdict 🟢 propre. Revérifié sur le vrai dépôt après les 3 correctifs : verdict 🟡 inchangé (toujours la seule alerte sur le nombre d'équipes, qui reste — honnêtement — hors de portée de ce contrôle : aucune source mécanique possible pour un chiffre qui vit sur lablab.ai).

`garde_fou.py` compte maintenant 5 contrôles, pas 4 — mis à jour partout où ce chiffre était cité (le rappel de fin de script inclus).

---

## 🟢 25/08 (Cowork) — « cherche encore sur GitHub » : le vrai trou restant était la couche CI, pas un 6e contrôle de contenu

**Deux projets réels trouvés, un adopté, un délibérément pas** :

- **mutmut** (`boxed/mutmut`, 1,4k étoiles, actif — dernière mise à jour le 09/08/2026) : mutation testing pour Python, automatise exactement ce que j'ai fait à la main ce soir (fabriquer un cas connu-mauvais et vérifier qu'il est attrapé). **Pas adopté** : SNIPER fait déjà ça pour certains de ses contrôles ("auto-testé par mutation à chaque lancement"), déjà noté comme piste dans une passe précédente de ce soir — pas une découverte nouvelle, juste reconfirmée.
- **semgrep** (15 555 étoiles, actif) : pattern-matching structurel pour du code, alternative réelle aux regex fragiles qui ont produit 3 bugs ce soir dans le contrôle 5. **Délibérément pas adopté** : `garde_fou.py` et `hindsight_guard.py` partagent la même philosophie affichée noir sur blanc ("Standard library only") — ajouter une dépendance externe pour un script de cette taille contredirait un choix déjà écrit, pas une amélioration gratuite. Noté ici au cas où le script grossirait assez pour que le compromis change.

**Le vrai trou trouvé, confirmé par la propre documentation de gitleaks** : un "programme de scan en couches" cite explicitement pre-commit LOCAL **et** CI comme les deux couches, jamais l'une sans l'autre. Notre hook (`githooks/pre-commit`, ajouté plus tôt ce soir) a deux angles morts documentés : il ne protège que les machines où quelqu'un a pensé à l'activer, et `git commit --no-verify` le contourne par construction. Aucune des deux limites n'est un défaut du hook — ce sont des trous STRUCTURELS qu'un hook local ne peut, par nature, jamais combler seul.

**Ajouté** : `.github/workflows/garde-fou.yml` — lance `python3 garde_fou.py` sur GitHub même à chaque push/PR vers `main`. `fetch-depth: 0` explicitement nécessaire (pas le défaut) : le contrôle 2 (`.env.hackathon` scellé) lit l'historique git complet, et un clone superficiel l'aurait rendu aveugle sans le signaler.

**Testé pour de vrai** : YAML validé (`pyyaml`, parse propre). Simulé un vrai clone frais (`git clone` du dépôt local, pas juste `cp`) pour reproduire ce que ferait `actions/checkout` — a immédiatement révélé quelque chose d'utile plutôt qu'un bug : le clone reflète l'état COMMITÉ, qui a encore l'ancien "442" (le correctif du deck n'est encore que dans l'arbre de travail, jamais poussé) — verdict 🔴 dans le clone. **Ce n'est pas un défaut** : c'est la CI qui fait exactement son travail, elle aurait bloqué un push réel tant que les correctifs en attente ne sont pas commités. Confirme au passage, une fois de plus, que `garde_fou.py`, `CLAUDE.md`, `githooks/` et maintenant `.github/workflows/garde-fou.yml` doivent tous partir dans le même commit terminal.

---

## 🟢 25/08 (Cowork) — un 6e contrôle né d'un quasi-incident réel de ce soir, pas d'une anticipation

**Ce qui s'est passé** : Spap a demandé d'installer un dépôt GitHub externe, `affaan-m/ecc` — un "harnais d'agent" qui prétend "212K+ étoiles, le toolkit agent le plus starré de GitHub" et qui modifie explicitement les hooks/rules/conventions MCP de plusieurs agents de code (Claude Code, Codex, Cursor, Gemini...). Vérifications faites avant toute décision : le `package.json` réel (105 Ko de README, lui-même un signal) liste des centaines de skills et un script `postinstall`-style qui mentionne déjà un "sponsor compute" et une commande soumettant une "RFQ authentifiée live" — pas juste un kit de skills passif. Le chiffre d'étoiles n'a pas pu être confirmé via l'API GitHub (réponse vide au moment du test). **Refusé** : télécharger/exécuter depuis une source non vérifiée est une règle de cet environnement qui ne se contourne pas, même sur demande explicite.

**Ce que ça révèle pour CE dépôt, concrètement** : rien dans `garde_fou.py` n'aurait signalé l'ajout d'une dépendance si la demande avait visé `requirements.txt` directement (un `pip install` planqué dans un futur commit) plutôt qu'une installation manuelle passée par ce chat. `requirements.txt` ne contient qu'une ligne (`python-dotenv>=1.0.0`) depuis le commit initial — jamais surveillé jusqu'ici.

**Ajouté, contrôle 6 (`controle_dependances_scellees`)** : même mécanique de scellé que le contrôle 2 (hash SHA-256, registre `.garde_fou_scelles.json` déjà existant, réutilisé) — mais volontairement **non bloquant** : une dépendance légitime est censée changer de temps en temps, contrairement à `.env.hackathon`. Alerte 🟡 une seule fois au moment du changement (le registre se re-scelle tout seul juste après l'avoir signalé), pour forcer une relecture consciente de la provenance (nom exact sur PyPI, pas de typosquat, mainteneur actif) plutôt qu'un ajout qui passe inaperçu — jamais un nag permanent.

**Testé pour de vrai, les 4 branches, dans un dossier jetable (`/tmp/temoin_deps`)** : première lecture → alerte 🆕 + empreinte enregistrée ; relance sans changement → silence ; `requirements.txt` modifié → alerte "A CHANGÉ" avec les deux empreintes tronquées, ET re-scellé dans le même passage ; relance après re-scellement → silence à nouveau. Revérifié sur le vrai dépôt : verdict 🟡 inchangé (toujours l'alerte sur le nombre d'équipes, plus maintenant la première empreinte de `requirements.txt`), rien de cassé.

`garde_fou.py` compte maintenant 6 contrôles — mis à jour partout où ce chiffre était cité (rappel de fin de script inclus). **Reste à faire en terminal** : ce fichier fait partie du même commit en attente que `garde_fou.py`, `CLAUDE.md`, `githooks/` et `.github/workflows/garde-fou.yml` — rien de nouveau côté périmètre du brief.

**Correction publique, pas silencieuse** : Spap a redemandé « cherche encore » sur `affaan-m/ecc` spécifiquement pour vérifier le chiffre d'étoiles laissé "invérifiable" ci-dessus. `api.github.com` restait vide depuis cet environnement (bloqué ou mal formé, cause non identifiée), mais un miroir tiers indépendant et légitime de l'API GitHub (`ungh.cc`, projet unjs, sans lien avec l'auteur d'ecc) a répondu avec des données structurées réelles : **242 948 étoiles, 36 767 forks, dernier push il y a quelques heures (25/08 02:12 UTC)** — donc le chiffre "212K+" n'était pas gonflé, il est maintenant dépassé par la croissance organique. Confirmé aussi côté npm : **4 788 téléchargements/semaine, 16 790/mois** (API officielle `api.npmjs.org`), cohérent avec un usage réel, pas un chiffre de façade. **Le doute sur la popularité est levé — c'est un vrai projet, massivement utilisé, activement maintenu.**

Ce que ça ne change PAS : la décision de ne pas l'installer depuis Cowork tient toujours, mais pour une raison différente et plus honnête que "signal de crédibilité gonflée" (qui était une inférence, pas une observation — corrigée ici). La vraie raison, indépendante de sa popularité : il modifie explicitement les hooks/rules/conventions MCP de plusieurs harnais d'agent (Claude Code inclus) à travers des centaines de fichiers — une popularité réelle ne réduit pas la surface de confiance que ça engage, et une revue manuelle complète avant install n'est pas faisable en une passe, encore moins en plein sprint hackathon avec `.env.hackathon` en jeu. Root cause du "empty" retourné par `api.github.com` non identifiée — noté sans être creusé davantage, hors périmètre de ce projet.

---

## 🟢 25/08 (Cowork) — première adaptation réelle des références externes : `githooks/pre-push` + « vérifier avant d'affirmer »

Suite de la tâche #94 (« adapter gstack/superpowers/plugins Anthropic à chaque projet, jamais un import en masse »). Premier projet traité : hindsight-alpha lui-même.

**Ce qui a été lu avant d'adapter quoi que ce soit** : `gstack/guard/SKILL.md` et `gstack/investigate/SKILL.md` en entier — verdict honnête, ce ne sont PAS des fichiers portables. Chacun dépend d'une dizaine de binaires gstack propres (`gstack-config`, `gstack-telemetry-log`, `gstack-brain-sync`, `gstack-slug`...), d'un état persistant (`~/.gstack/`), et d'une télémétrie/synchronisation vers un dépôt distant — tout l'inverse de la philosophie « standard library only » de ce projet. Copier ces fichiers tels quels dans `githooks/` n'aurait rien fait fonctionner. **Décision : extraire le PRINCIPE, jamais le fichier.**

**1. `githooks/pre-push` (nouveau)** — principe emprunté à `/careful` de gstack (avertir/bloquer avant une commande destructrice), réimplémenté en ~30 lignes de `sh` pur, zéro dépendance externe. Détecte un push non-fast-forward en comparant si le SHA distant est un ancêtre du SHA local (`git merge-base --is-ancestor`) — couvre `--force` ET `--force-with-lease` sans avoir à lire les flags (que les hooks pre-push ne voient de toute façon pas). Raison précise d'exister : « jamais de `git push --force` » est répété dans CLAUDE.md et ce fichier depuis le début du sprint, mais rien ne le vérifiait mécaniquement — même trou que `.env.hackathon` et `ALPACA_LIVE_TRADE` avant que `garde_fou.py` existe.

**Testé pour de vrai, 7 scénarios, sur un dépôt jetable (`/tmp/temoin_push`, remote bare + local avec le hook installé)** :
1. Push normal (nouvelle branche) → passe.
2. Deuxième push fast-forward → passe.
3. Push non-FF sans `--force` → refusé par git lui-même (comportement normal, rien à voir avec notre hook).
4. Push `--force` → **bloqué par notre hook**, message clair avec les deux SHA et le rappel de la règle CLAUDE.md.
5. Push `--force --no-verify` → contourne le hook (échappatoire documentée, cohérente avec `pre-commit`).
6. Nouvelle branche → passe.
7. Suppression de branche distante → passe (pas confondu avec un force-push).
Bug de méthode trouvé en testant le témoin lui-même (pas le hook) : `set -e` dans le SCRIPT DE TEST arrêtait la suite après le test 4 qui sort en erreur volontairement — même piège que celui déjà documenté dans `githooks/pre-commit`, cette fois côté témoin. Retiré, suite rejouée, tout confirmé.

**2. Section « Vérifier avant d'affirmer » ajoutée à CLAUDE.md** — principe emprunté à `verification-before-completion` (skill `superpowers`, obra/superpowers). Pas un nouvel outil : une règle déjà PRATIQUÉE tout au long de ce fichier (chaque correctif de ce journal est démontré par un témoin avant d'être déclaré bon), simplement jamais écrite noir sur blanc jusqu'ici. Adaptée en une version courte, en français, dans le style du reste du fichier — pas copiée-collée depuis superpowers.

**Reste hors périmètre ce soir, noté pour la suite** : le pattern `/code-review` officiel Anthropic (4 agents parallèles : 2× conformité CLAUDE.md, 1× détecteur de bugs, 1× historien git blame, score de confiance ≥80 avant de remonter un point) serait directement applicable au gros lot de fichiers en attente de commit (`garde_fou.py`, `CLAUDE.md`, `githooks/`, workflow CI...) — pas lancé ce soir, à proposer avant le prochain commit terminal si Spap veut une revue croisée avant de pousser.

**Reste à faire en terminal** : `githooks/pre-push` et la mise à jour de `CLAUDE.md` rejoignent le même lot en attente de commit que le reste.

---

## 🟢 25/08 (Cowork) — la revue croisée `/code-review` proposée, lancée pour de vrai : deux vrais bugs trouvés, un avant qu'il parte en soumission

Spap a dit « go » sur la proposition laissée en suspens. 4 agents lancés en parallèle sur le lot entier en attente de commit, chacun avec un mandat distinct (calqué sur le vrai plugin officiel Anthropic `plugins/code-review`, cloné en référence dans `CERVEAU/OUTILS_CONTROLE_GARDE_FOU/5_REFERENCES_EXTERNES/claude-code-plugins/`) : deux audits indépendants de conformité à CLAUDE.md, un scan de bugs concrets (avec exécution réelle du code, pas juste lecture — `py_compile`, `garde_fou.py` relancé pour de vrai, YAML parsé), et un audit croisé contre l'historique du projet (`PLAN_SPRINT.md` entier relu par l'agent, pour repérer une erreur de la même famille qu'une déjà corrigée).

**Le vrai résultat, trouvé indépendamment par DEUX agents différents (bug scan ET audit historique), confiance 85 les deux fois** : le nouveau tableau "Backtest, at a glance" de `README.md` affichait **181.6%** pour la concentration de XLK, alors que XLK est jugé sur sa fenêtre **90 jours** (verdict `hindsight_guard` : fuite, gagnant plein historique = 90j) et que 181.6% est la concentration de sa fenêtre **10 jours** — la mauvaise fenêtre collée à la bonne ligne. Vérifié directement dans `BACKTEST_RESULTS.md` (`10d: 181.6% · 90d: 136.7%`) avant de corriger : le vrai chiffre pour la ligne XLK (fenêtre 90j, 76 trades, 36,8% de réussite — ces deux-là étaient corrects) est **136.7%**. Corrigé dans `README.md`.

**Ce qui rend cette trouvaille plus intéressante qu'un simple chiffre faux** : l'agent d'audit historique a explicitement rapproché ça des TROIS bugs de proximité regex déjà trouvés et corrigés en construisant le contrôle 5 le même soir (mauvaise fenêtre associée au mauvais chiffre) — même famille d'erreur, récidive humaine cette fois, pas dans le code. Et surtout : **`garde_fou.py` ne pouvait structurellement pas l'attraper**. Le contrôle 5 (`controle_source_de_verite`) exclut par construction les symboles en fuite de ses plages mécaniques (`propres = {s: d for s, d in backtest.items() if not d["leaked"]}`) — XLK, le seul symbole en fuite, celui-là même que le projet met en avant comme sa meilleure démonstration, n'est validé par AUCUN contrôle mécanique aujourd'hui. Documenté en commentaire dans `garde_fou.py` (pas corrigé ce soir — construire un vrai vérificateur par-fenêtre-par-symbole pour les symboles en fuite est un vrai chantier, pas une ligne, et le tester correctement prendrait le temps que les 3 bugs du contrôle 5 ont déjà pris ce soir-là ; noté ici pour ne pas se perdre, pas oublié).

**Deuxième trouvaille, confirmée indépendamment par les deux agents de conformité CLAUDE.md, confiance 80-85** : le commentaire de fin de `garde_fou.py` disait encore « seuls 4 contrôles existent aujourd'hui » alors que le code en compte 6 depuis les ajouts plus tôt ce soir — contradiction directe avec la ligne imprimée juste en dessous (« 6 formes d'erreur »). Corrigé, en profitant du même passage pour documenter l'angle mort XLK trouvé ci-dessus directement dans le commentaire.

**Trois autres pistes remontées, notées mais pas toutes corrigées ce soir** :
- `MOTIFS_PERIMES` (contrôle 4) matchait "442" en sous-chaîne, pas en nombre isolé — un futur "4420" quelconque aurait déclenché à tort (confiance 50, mine dormante jamais atteinte pour de vrai). **Corrigé** : même idiome `(?<!\d)...(?!\d)` que le contrôle du nombre d'équipes juste en dessous dans le même fichier. Témoin testé : "4420 participants" ne déclenche plus, "442 équipes" déclenche toujours.
- `SEUILS_RISQUE` (contrôle 5) ne couvre que 7 des 8 constantes listées dans CLAUDE.md — `HEARTBEAT_SECONDS` (qui vit dans `monitor_exits.py`, pas `risk_gates.py`/`vol_strategy.py`) n'est jamais vérifié (confiance 70). **Pas corrigé ce soir** — noté, pas urgent (aucun livrable ne cite ce chiffre précis aujourd'hui).
- `BRIEF_COMMIT_INDICATEUR_SANTE_ET_WRITEUP.md` avait un inventaire de fichiers périmé, sans `githooks/pre-push` ni le contrôle 6 (confiance 55). **Corrigé** : note "sixième fois" ajoutée.

**Après tous ces correctifs, revérifié pour de vrai (pas supposé)** : `python3 -m py_compile garde_fou.py` propre, `python3 garde_fou.py` toujours 🟡, toujours la seule alerte sur le nombre d'équipes — aucun correctif n'a cassé quoi que ce soit d'autre.

---

## 🟢 25/08 (Cowork) — l'angle mort XLK comblé : contrôle 5 étendu aux tableaux symbole-par-symbole, fuite ou pas

Suite immédiate de la revue croisée ci-dessus, sur demande de Spap (« continue »). L'angle mort documenté en commentaire (XLK non couvert par `propres`) est maintenant fermé — pas en construisant le vérificateur général par-fenêtre-pour-toute-prose (trop de risque de reproduire les 3 bugs de proximité regex du contrôle 5 original), mais avec une portée honnêtement plus étroite : les TABLEAUX markdown, la forme exacte où le vrai bug XLK est apparu.

**`_lignes_tableau_symboles()`** repère un tableau par sa ligne d'en-tête (colonnes "win rate" et "concentration"/"best 5 days"/"gain from best"), saute la ligne de séparation markdown, puis lit chaque ligne de données : ticker en première colonne, valeur des colonnes win-rate et concentration. Câblé dans `controle_source_de_verite()` — pour CHAQUE symbole trouvé dans `BACKTEST_RESULTS.md` (via `backtest`, qui contient déjà tous les symboles, fuite ou pas — juste jamais utilisé pour les fuites jusqu'ici), compare directement contre SA fenêtre vettée à lui, pas contre une plage agrégée des seuls symboles propres.

**Testé pour de vrai, 4 scénarios, contre le vrai `README.md`** :
1. État réel actuel (déjà corrigé plus tôt) → verdict inchangé, 🟡, rien de nouveau ne bloque.
2. XLK recassé à la main à 181.6% (l'erreur réelle trouvée) → **bloque**, message exact : "CONCENTRATION « 181.6% » pour XLK (tableau) ne correspond pas à sa fenêtre vettée (90j) — devrait être 136.7%."
3. SPY (symbole propre, pas en fuite) cassé à 99.9% de taux de réussite → **bloque aussi**, confirme que les symboles propres restent couverts en plus des symboles en fuite, pas un remplacement du contrôle existant.
4. Restauration du vrai contenu → 🟡 à nouveau, propre.

Un fichier `README.md.bak` oublié par `sed` pendant le test 2 a été supprimé après coup (permission de suppression demandée sur le dossier hindsight-alpha, comme pour CERVEAU plus tôt ce soir — les deux dossiers connectés refusent la suppression directe sans cette étape).

`garde_fou.py` reste à 6 contrôles nommés (celui-ci est une extension du contrôle 5, pas un 7e) — revérifié après coup : compile propre, verdict 🟡 inchangé sur le vrai dépôt.

---

## 🟢 25/08 (Cowork) — dernière piste de la revue croisée comblée : `HEARTBEAT_SECONDS` rejoint `SEUILS_RISQUE`

Suite directe (« continue »). CLAUDE.md liste HUIT constantes non négociables ; `SEUILS_RISQUE` du contrôle 5 n'en couvrait que sept — `HEARTBEAT_SECONDS` manquait parce qu'elle vit dans `monitor_exits.py`, pas `risk_gates.py`/`vol_strategy.py` comme les sept autres. Trouvé en confiance 70 par la revue croisée, volontairement pas corrigé sur le coup ("pas urgent, aucun livrable ne la cite aujourd'hui") — comblé maintenant que le reste de la liste est traité.

**Correctif d'une ligne** : `("HEARTBEAT_SECONDS", "monitor_exits.py")` ajouté à `SEUILS_RISQUE`. `_parse_seuils_risque()` ne faisait déjà aucune hypothèse sur le fichier source, donc rien d'autre à changer.

**Testé pour de vrai, 3 temps, sur le vrai `README.md`** :
1. État réel avant témoin → 🟡 inchangé, HEARTBEAT_SECONDS n'est cité nulle part aujourd'hui donc rien ne devait changer.
2. Ligne témoin ajoutée avec la mauvaise valeur (`` `HEARTBEAT_SECONDS`, 900 ``, la vraie valeur étant 3600) → **bloque**, message exact : "cité comme 900 juste après le nom, mais vaut réellement 3600 dans monitor_exits.py."
3. Même ligne avec la bonne valeur (3600) → passe, silence.
Témoin nettoyé, `README.md` restauré, `.bak` supprimé (permission déjà accordée sur ce dossier plus tôt ce soir).

**Les 4 pistes de la revue croisée à 4 agents sont maintenant toutes traitées** : XLK (structurel, comblé), commentaire "4 contrôles" (corrigé), motif "442" en sous-chaîne (corrigé), `HEARTBEAT_SECONDS` (comblé). Seule la note sur `BRIEF_COMMIT_INDICATEUR_SANTE_ET_WRITEUP.md` restait déjà réglée dans la même passe. Revérifié une dernière fois : `garde_fou.py` compile, tourne, verdict 🟡 inchangé.

---

## 🔴 26/08 (Cowork) — vetting des 4 derniers outils cités dans la deuxième vidéo TikTok (OmniRoute, Headroom, Claude Code Setup, Task Observer)

Suite directe de la demande explicite « vérifie les 4 autres ». Même méthodologie que le premier lot de 7 : jamais le nombre d'étoiles seul, toujours une lecture de contenu (README/package.json) pour chercher le même type de signal qui avait fait tomber `claude-mem` (token crypto embarqué) — recoupé avec `ungh.cc` pour des données indépendantes de GitHub.

**OmniRoute (`diegosouzapw/OmniRoute`) — REFUSÉ, ne pas installer.** 54 204 étoiles pour un dépôt créé le 13/02/2026 (~194 jours) = ~280 étoiles/jour soutenu sur 6 mois, un rythme extrême. Le README lui-même porte les signaux de growth-hacking déjà documentés par l'étude StarScout (CMU, 6M fausses étoiles recensées) : bandeau "⭐ Star the repo if...", liens WhatsApp/Telegram/Discord multiples, traduction en 34 langues pour un outil dev de niche. Plus grave que les étoiles : c'est une gateway qui route tout le trafic IA (Claude Code, Cursor, etc.) à travers un point central en agrégeant les "free tiers" de 43 fournisseurs, et le README admet lui-même que **15 de ces fournisseurs sont "ToS-flagged"** — l'outil encourage explicitement à contourner les CGU de tiers. Même famille de refus que `claude-mem` (contenu révèle le vrai problème, pas les étoiles).

**Headroom — à surveiller, pas refusé net, mais pas installé tel quel non plus.** Deux entités, pas une usurpation : `headroomlabs-ai/headroom` et `chopratejas/headroom` sont le **même** dépôt (`ungh.cc` résout les deux identifiants vers le même repo — probablement un renommage d'org/utilisateur suivi par GitHub, pas un fork trompeur). 67 577 étoiles sur ~231 jours (~290/jour) — un rythme tout aussi extrême qu'OmniRoute en valeur absolue, mais **aucun signal de growth-hacking dans le contenu** : pas de bandeau "star me", pas de liens WhatsApp, présentation technique sobre, CI réelle (GitHub Actions + Codecov), publié sur PyPI/npm sous des noms cohérents, licence Apache 2.0, modèle HuggingFace public. Fonctionnellement plus risqué qu'OmniRoute sur un point (mode "proxy" qui intercepte tout le trafic API, y compris vers Anthropic, pour le compresser) mais tourne en local ("your data stays here") au lieu de router vers des fournisseurs externes. Rythme d'étoiles noté comme un signal à ne pas ignorer, sans preuve suffisante pour un refus net comme OmniRoute. `gglucass/headroom-desktop` (509 étoiles, app payante) est modeste et crédible, non revérifié en détail.

**Claude Code Setup — fiable, déjà confirmé officiel.** `anthropics/claude-plugins-official`, listé sur `claude.com/plugins/claude-code-setup`. Aucune vérification supplémentaire nécessaire.

**Task Observer (`rebelytics/one-skill-to-rule-them-all`) — le seul des 4 à considérer, en adaptation (jamais tel quel).** 2 019 étoiles sur ~192 jours (~10/jour) — rythme cohérent avec une adoption organique réelle, contraste net avec OmniRoute/Headroom. Auteur nommé et identifiable (Eoghan Henn, `rebelytics.com`, méthodologie publique "Augmented Expertise"), recommandations tierces vérifiables (comptes X/LinkedIn/Instagram nommés, pas anonymes), badge d'audit de sécurité tiers (oathe.ai). C'est un pur bundle de fichiers markdown (`SKILL.md` + `references/`), aucune exécution de code, aucun appel réseau documenté — écrit ses observations localement. Même s'il est vetted propre, la doctrine du soir reste "extraire le principe, jamais le fichier tel quel" : s'il est repris un jour, ce sera une version adaptée du principe (un skill qui observe les sessions et propose des améliorations de skills) dans `5_REFERENCES_EXTERNES/`, pas une installation brute — pas fait ce soir, aucune demande explicite de Spap en ce sens.

**Verdict global communiqué à Spap** : n'installer aucun des 4 ce soir. OmniRoute refusé (CGU tiers contournées, signal d'étoiles gonflées). Headroom à surveiller (contenu propre mais rythme d'étoiles à ne pas ignorer). Claude Code Setup déjà fiable, rien à faire. Task Observer est le seul candidat plausible pour une adaptation future, sur demande explicite.

---

## 🟢 26/08 (session terminal) — l'indicateur de santé vérifié sur l'incident RÉEL

**La bannière rend l'état attendu, et c'est la démonstration du correctif sur données vécues, pas sur un scénario inventé.**

À l'instant du contrôle : `decision_log.jsonl` s'arrête sur une **erreur à 17:45:41 UTC** (la dernière panne DarkWake), tandis que `monitor_last_run.json` — la nouvelle source écrite à chaque run — dit **`checked` à 19:45:07 UTC, marché ouvert**. La bannière affiche **🟢 vert** : *« Exit monitor: last check 3h 3m ago, healthy »*.

> **C'est exactement le bug corrigé** : sans `monitor_status`, la bannière serait restée sur « 🔴 11 consecutive failures » alors que le moniteur tourne sainement depuis deux heures — potentiellement toute la semaine jugée.

Et le contrôle d'heures de marché fait son travail : il est 22:48 UTC, le marché a fermé à 20:00 UTC, **3 h sans contrôle ne déclenchent donc pas le jaune « stale »**.

**Les deux autres bandeaux, confirmés visuellement** : 🛡️ *« Hindsight leaks caught so far (last 28 logged runs): 12 »*, et les refus XLK surlignés dans le tableau.

⚠️ **Une erreur de lecture de ma part, notée pour la suite** : j'ai d'abord cru voir deux échecs récents à « 19:45 » et « 19:17 » dans le tableau. **Le dashboard affiche en heure LOCALE (CEST)** — c'était 17:45 et 17:17 UTC, les pannes déjà connues. Le log brut a tranché. *À se rappeler en lisant ce dashboard : le tableau est en heure locale, les logs en UTC.*

### État du moniteur et de la position

Sain depuis 17:55 UTC, contrôles réussis toutes les 15 min jusqu'à 19:45 UTC au moins, puis arrêt normal à la fermeture du marché. 🔴 **La position de test a nettement bougé : `SPY260831P00764000` à ~−23 % (−26,9 % sur la lecture la plus fraîche), contre +2,8 % hier.** Toujours dans la bande ±50 %, donc aucune sortie déclenchée — mais elle s'en rapproche, et c'est le moniteur qui la surveillera.

### Ce que je n'ai PAS pu faire

🟠 **La conversion PDF du write-up est impossible sur ce Mac : LibreOffice n'est pas installé.** J'ai vérifié le **contenu** du `.docx` à la place — `XLK` et `leak` présents, `0 leaks`, `442` et `QQQ` absents, univers `SPY, GLD, XLK, XLV` correct — mais **pas la pagination**. La vérification « tient sur une page » reste celle faite côté Cowork.

### Contrôles de la séance

`garde_fou.py` lancé en vrai depuis le terminal : **🟡, une seule alerte** (nombre d'équipes du deck), conforme. Hook activé (`core.hooksPath = githooks`), `pre-commit` et `pre-push` exécutables.

**Vérification non demandée que j'ai faite quand même** : le deck passait de 273 Ko à 57 Ko (−79 %), ce qui pouvait signaler une perte d'images. **Vérifié : rien de perdu** — 11 slides des deux côtés, le seul « média » disparu est une entrée de dossier vide, et le texte a *augmenté* (8 269 → 8 390 caractères), « 0 leaks » et « 442 » bien disparus.
