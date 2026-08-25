# Hindsight Alpha — script vidéo de démo

*Cible : ~2:45. Contrainte officielle confirmée le 25/08 (page lablab "Submission Guidelines") : **maximum 5 minutes, format MP4**, structure attendue "introduction → discuter la présentation PDF → montrer les fonctionnalités". 2:45 laisse une vraie marge sous la limite dure. Structure suivie du guide officiel lablab ("how to win an AI hackathon") : démo tôt, problème énoncé en moins de 30 secondes, ne pas cacher la rigueur derrière une prose ronflante. Le texte ci-dessous est un brouillon à dire avec tes mots, pas un texte à lire mot pour mot — adapte le ton, garde les chiffres exacts.*

---

## 0:00–0:20 — Accroche (montrer le tableau de bord en direct)

**À l'écran :** le tableau de bord public (`s-papy.github.io/hindsight-alpha`) ouvert dans le navigateur, la section "Recent decisions" visible.

**À dire :**

> "La plupart des agents de trading IA font la même chose : ils testent plusieurs paramètres sur des données historiques, gardent celui qui a le meilleur score, et tradent dessus. Le problème, c'est que si la fenêtre de test contenait des données que l'agent n'aurait pas encore pu connaître au moment de la décision, ce 'meilleur score' n'est pas réel — il triche sans que rien dans le code n'ait l'air cassé. C'est ce que j'appelle une fuite de hindsight. Hindsight Alpha est construit pour l'attraper avant de trader, pas après."

## 0:20–0:55 — L'idée en une image concrète

**À l'écran :** basculer sur le code ou un schéma simple (2 barres : "score plein historique" vs "score en n'utilisant que ce qui était connu avant"), ou simplement le terminal.

**À dire :**

> "Concrètement : à chaque cycle, l'agent teste 5 fenêtres de volatilité historique candidates — 10, 20, 30, 60, 90 jours. Il calcule un score deux fois pour chacune : une fois sur tout l'historique, une fois en cachant les 20 derniers jours, comme si c'était 'aujourd'hui'. Si la fenêtre gagnante change entre les deux — ou si aucune ne dépasse le seuil de Sharpe en n'utilisant que l'information disponible — l'agent refuse de trader. Ce refus, c'est le vrai produit, pas un cas d'erreur."

## 0:55–1:40 — Démo en direct

**À l'écran :** terminal, lancer `python agent.py --dry-run` (ou sans `--dry-run` si un vrai trade a eu lieu cette semaine — préférer le vrai trade si disponible). Montrer la sortie qui affiche, pour chaque symbole (SPY, GLD, XLK, XLV), le verdict `hindsight_guard` et la raison. Puis ouvrir `decision_log.jsonl` (ou le tableau de bord) et montrer l'entrée correspondante.

**À dire :**

> "Voici un run réel. Pour chaque symbole de l'univers — SPY, GLD, XLK, XLV, volontairement choisis dans des secteurs non corrélés — l'agent affiche son verdict et pourquoi. [pointer un cas TRADEABLE, ex. SPY ou XLV] Ici, la fenêtre gagne sur tout l'historique ET sur la version cachée : pas de fuite, la volatilité est bon marché aujourd'hui, l'agent est prêt à trader. [pointer XLK — refusé de façon systématique, pas un cas rare à espérer pendant le tournage] Ici en revanche, XLK est refusé : sur tout l'historique, la fenêtre de 90 jours gagne ; mais en ne regardant que ce qui était connu avant, c'est la fenêtre de 10 jours qui gagne. Les deux ne sont pas d'accord — un vrai désaccord détecté sur de vraies données, pas un cas hypothétique — donc l'agent refuse XLK, à chaque run, jusqu'à ce que ça change. Chaque décision, y compris les refus, est journalisée dans `decision_log.jsonl` — c'est ce fichier-là qui alimente le tableau de bord public, en temps réel, tout au long de la semaine du hackathon."

## 1:40–2:15 — Les garde-fous de risque

**À l'écran :** ouvrir `risk_gates.py` brièvement (juste les constantes en haut : `MAX_RISK_PCT_PER_TRADE`, `MAX_TOTAL_RISK_PCT`, `MAX_SECTOR_EXPOSURE_PCT`, `MAX_OPEN_POSITIONS`), puis (si le temps le permet) créer le fichier `HALT` en direct dans le terminal et relancer l'agent pour montrer qu'il refuse d'ouvrir une nouvelle position.

**À dire :**

> "Le code ne se contente pas de décider quoi trader — il limite combien. 1% de l'équité par trade, 3% au total sur toutes les positions ouvertes en même temps, 1,5% par secteur, jamais deux positions sur le même sous-jacent, jamais plus de 4 positions à la fois, et un verrou automatique si le compte perd 3% sur la semaine. [si démo HALT] Et si je dois mettre l'agent en pause en pleine semaine — un incident, un doute — je crée juste un fichier nommé HALT, comme ça [le créer]. Relance : [relancer l'agent] — il refuse toute nouvelle position, mais continue de gérer celles déjà ouvertes. Pas besoin de toucher au code ni aux identifiants."

## 2:15–2:45 — Résultat honnête du backtest

**À l'écran :** le tableau `BACKTEST_RESULTS.md` ou la capture du tableau à l'écran (montrer les 5 fenêtres, les 3 symboles, les chiffres négatifs bien visibles).

**À dire :**

> "Et voici la partie que la plupart des pitchs de hackathon évitent : le vrai résultat du backtest, sans retoucher aucun seuil après coup. Sur les quatre symboles de l'univers actuel, l'edge tient sur trois — SPY, GLD, XLV — mais 68,5 à 82,6% du gain de chacun vient d'une poignée de journées sur 52 à 102 trades, avec un taux de succès entre 45 et 57%. Et le quatrième, XLK, c'est justement celui que vous venez de voir refusé : `hindsight_guard` a détecté un vrai désaccord entre la fenêtre gagnante sur tout l'historique et la fenêtre gagnante en in-sample — l'agent le sait, et refuse de trader dessus plutôt que de cacher le problème. Ce refus ne prouve pas que les trois autres symboles ont un edge réel — juste qu'ils n'ont pas ce problème précis. C'est la nuance que ce projet existe pour forcer : distinguer 'ce backtest ne triche pas' de 'cette stratégie gagne de l'argent'. Les deux ne sont pas la même chose, et confondre les deux est exactement l'erreur que beaucoup d'agents commettent silencieusement."

## 2:45–3:05 — Clôture

**À l'écran :** revenir au tableau de bord, ou une slide de fin simple avec les liens.

**À dire :**

> "Hindsight Alpha, c'est un pari sur l'agent, pas sur la stratégie : le mécanisme qui refuse une fausse victoire compte plus que n'importe quel chiffre de performance sur une seule semaine de marché. Projet solo, code source public, dashboard en direct, licence MIT. Merci d'avoir regardé."

---

## Notes de tournage

- **Durée cible réelle : ~2:45, un seul chiffre, pas une fourchette.** Contrainte officielle (page lablab "Submission Guidelines", vérifiée 25/08) : **maximum 5 minutes, format MP4** — 2:45 laisse une vraie marge, pas besoin de viser la limite. Le guide lablab insiste aussi sur "démo tôt" — ne pas dépasser 25-30 secondes avant de montrer quelque chose à l'écran qui tourne vraiment.
- **La structure officielle attendue est "introduction → discuter la présentation PDF → montrer les fonctionnalités".** Ce script fait déjà l'intro + la démo, mais ne mentionne jamais explicitement le write-up d'une page — ajouter une phrase courte dans l'accroche (0:00–0:20) du type "tout ça est aussi détaillé dans le write-up d'une page joint à la soumission" pour couvrir ce point sans réécrire toute la structure.
- **Ne pas dire "ROI garanti" ou "+X% de gains"** nulle part — le backtest dit l'inverse, et le mentir en vidéo contredirait tout le reste de la soumission.
- Si aucun trade réel n'a encore eu lieu au moment de l'enregistrement, dire clairement "voici un dry-run" plutôt que de laisser croire à un ordre réel.
- Si le compte dédié (`.env.hackathon`) est déjà branché et a un vrai historique cette semaine-là, remplacer la section 0:55–1:40 par un vrai run sur ce compte — plus fort qu'un dry-run.
- Sous-titres recommandés si l'anglais du narrateur n'est pas fluide à l'oral — beaucoup de juges lisent plus vite qu'ils n'écoutent.
- **Cover image de la soumission** (exigence trouvée 25/08, distincte de la vidéo) : PNG ou JPG, ratio 16:9 recommandé — à préparer séparément, pas couvert par ce script.
- **Réponse prête si un juge demande "est-ce que ça existe déjà" (recherché 25/08)** : le mécanisme s'apparente à la Probability of Backtest Overfitting / walk-forward optimization de la littérature quant (López de Prado et al.), mais validées une fois à la conception — la vraie différence de ce projet, c'est que le test tourne à CHAQUE décision live, pas une seule fois. Détail complet dans le README ("Where this sits in the existing literature"), pas la peine de le réciter dans la vidéo elle-même — juste avoir la réponse prête pour un Q&A.
