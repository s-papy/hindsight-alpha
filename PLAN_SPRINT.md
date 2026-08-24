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
