# Hindsight Alpha — script vidéo de démo

*Cible : **~4:30**, démo HALT exclue. Chiffre MESURÉ, pas estimé : **601 mots prononcés** (les didascalies entre crochets sont exclues — elles ne se disent pas), soit 4:08 à 145 mots/min, plus ~21 s de manipulations à l'écran. Le compte annoncé ici était 623 : irreproductible par aucune convention claire, donc remplacé par un chiffre que l'on peut re-dériver — compter les mots des lignes commençant par « > », didascalies retirées. Contrainte officielle confirmée le 25/08 (page lablab "Submission Guidelines") : **maximum 5 minutes, format MP4**, structure attendue "introduction → discuter la présentation PDF → montrer les fonctionnalités". Structure suivie du guide officiel lablab ("how to win an AI hackathon") : démo tôt, problème énoncé en moins de 30 secondes, ne pas cacher la rigueur derrière une prose ronflante. Le texte ci-dessous est un brouillon à dire avec tes mots, pas un texte à lire mot pour mot — adapte le ton, garde les chiffres exacts.*

---

## 0:00–0:34 — Accroche (montrer le tableau de bord public)

**À l'écran :** le tableau de bord public (`s-papy.github.io/hindsight-alpha`) ouvert dans le navigateur, la section "Recent decisions" visible.

**À dire :**

> "La plupart des agents de trading testent des paramètres sur l'historique, gardent le meilleur score, et tradent dessus. Mais si ce score a été calculé sur des données que l'agent ne pouvait pas encore connaître, il triche — sans que rien dans le code n'ait l'air cassé. C'est une fuite de hindsight, et Hindsight Alpha est construit pour l'attraper avant de trader, pas après. Tout est détaillé dans le write-up d'une page joint à la soumission."

## 0:34–1:12 — L'idée en une image concrète

**À l'écran :** basculer sur le code ou un schéma simple (2 barres : "score plein historique" vs "score en n'utilisant que ce qui était connu avant"), ou simplement le terminal.

**À dire :**

> "Concrètement : à chaque cycle, l'agent teste 5 fenêtres de volatilité historique candidates — 10, 20, 30, 60, 90 jours. Il calcule un score deux fois pour chacune : une fois sur tout l'historique, une fois en cachant les 20 derniers jours, comme si c'était 'aujourd'hui'. Si la fenêtre gagnante change entre les deux — ou si aucune ne dépasse le seuil de Sharpe en n'utilisant que l'information disponible — l'agent refuse de trader. Ce refus, c'est le vrai produit, pas un cas d'erreur."

## 1:12–2:31 — Démo en direct

**À l'écran :** terminal, lancer `python agent.py --dry-run` (ou sans `--dry-run` si un vrai trade a eu lieu cette semaine — préférer le vrai trade si disponible). Montrer la sortie qui affiche, pour chaque symbole (SPY, GLD, XLK, XLV), le verdict `hindsight_guard` et la raison. Puis ouvrir `decision_log.jsonl` (ou le tableau de bord) et montrer l'entrée correspondante.

**À dire :**

> "Voici un run réel. Pour chaque symbole de l'univers — SPY, GLD, XLK, XLV, volontairement choisis dans des secteurs non corrélés — l'agent affiche son verdict et pourquoi. [pointer un cas TRADEABLE, ex. SPY ou XLV] Ici, la fenêtre gagne sur tout l'historique ET sur la version cachée : pas de fuite, la volatilité est bon marché aujourd'hui, l'agent est prêt à trader. [pointer XLK — refusé de façon systématique, pas un cas rare à espérer pendant le tournage] Ici en revanche, XLK est refusé : sur tout l'historique, la fenêtre de 90 jours gagne ; mais en ne regardant que ce qui était connu avant, c'est la fenêtre de 10 jours qui gagne. Les deux ne sont pas d'accord, sur de vraies données — donc l'agent refuse XLK, à chaque run, jusqu'à ce que ça change. Chaque décision, y compris les refus, est journalisée dans `decision_log.jsonl` — c'est ce fichier-là qui alimente le tableau de bord public, republié toutes les 30 minutes en séance, tout au long de la semaine du hackathon."

## 2:31–3:07 — Les garde-fous de risque

**À l'écran :** ouvrir `risk_gates.py` brièvement (juste les constantes en haut : `MAX_RISK_PCT_PER_TRADE`, `MAX_TOTAL_RISK_PCT`, `MAX_SECTOR_EXPOSURE_PCT`, `MAX_OPEN_POSITIONS`), puis — **seulement si l'on a coupé ailleurs, voir les notes de tournage : cette démo coûte 35 secondes et fait dépasser les 5 minutes** — créer le fichier `HALT` en direct dans le terminal et relancer l'agent pour montrer qu'il refuse d'ouvrir une nouvelle position.

**À dire :**

> "Le code ne se contente pas de décider quoi trader — il limite combien. 1% de l'équité par trade, 3% au total sur toutes les positions ouvertes en même temps, 1,5% par secteur, jamais deux positions sur le même sous-jacent, jamais plus de 4 positions à la fois, et un verrou automatique si le compte perd 3% depuis son équité de départ — mesuré depuis cette référence, sans remise à zéro chaque semaine. [si démo HALT] Et si je dois mettre l'agent en pause en pleine semaine — un incident, un doute — je crée juste un fichier nommé HALT, comme ça [le créer]. Relance : [relancer l'agent] — il refuse toute nouvelle position, mais continue de gérer celles déjà ouvertes. Pas besoin de toucher au code ni aux identifiants."

## 3:07–4:10 — Résultat honnête du backtest

**À l'écran :** le tableau `BACKTEST_RESULTS.md` ou la capture du tableau à l'écran (montrer les 5 fenêtres, les 3 symboles, les chiffres négatifs bien visibles).

**À dire :**

> "Et voici la partie que la plupart des pitchs de hackathon évitent : le vrai résultat du backtest, sans retoucher aucun seuil après coup. Sur les quatre symboles de l'univers actuel, l'edge tient sur trois — SPY, GLD, XLV — mais 68,5 à 82,6% du gain de chacun vient d'une poignée de journées sur 52 à 102 trades, avec un taux de succès entre 45 et 57%. Le quatrième, XLK, c'est celui que vous venez de voir refusé. Et ce test se trompe 23% du temps sur des séries saines — mesuré, publié. Le refus de XLK ne prouve donc pas que les trois autres ont un edge. C'est la nuance que ce projet existe pour forcer : 'ce backtest ne triche pas' et 'cette stratégie gagne de l'argent' ne sont pas la même chose, et confondre les deux est exactement l'erreur que beaucoup d'agents commettent silencieusement."

## 4:10–4:31 — Clôture

**À l'écran :** revenir au tableau de bord, ou une slide de fin simple avec les liens.

**À dire :**

> "Hindsight Alpha, c'est un pari sur l'agent, pas sur la stratégie : le mécanisme qui refuse une fausse victoire compte plus que n'importe quel chiffre de performance sur une seule semaine de marché. Projet solo, code source public, tableau de bord public, licence MIT. Merci d'avoir regardé."

---

## Notes de tournage

- **Durée : ~4:30 sans la démo HALT, ~5:06 avec — et 5:06 DÉPASSE la limite.** Les bornes de section ci-dessus sont calculées, pas devinées : nombre de mots réel de chaque bloc « à dire », à 145 mots/min, plus une allocation pour les manipulations à l'écran (15 s pour la démo, 6 s pour ouvrir `risk_gates.py`, 35 s de plus si l'on crée le fichier HALT et qu'on relance l'agent). Le script annonçait « ~2:45 » alors que sa propre dernière section finissait à 3:05 : le chiffre était faux dans les deux sens, trop court en façade et trop long en réalité. **Décision : la démo HALT n'est pas tournée**, sauf à couper ailleurs — c'est elle, à elle seule, qui fait passer au-dessus de 5:00.
- **Le débit change tout, donc chronométrer une répétition avant de tourner.** Tout ce qui suit se re-dérive de 601 mots + 21 s d'écran, rien n'est recopié : à 145 mots/min → **4:29**. À 165 (soutenu) → **3:59**. À 130 (lent, très articulé) → **4:58, soit 2 secondes de marge**. En dessous de ~129 mots/min le script dépasse les 5 minutes réglementaires : si la première répétition sort au-delà de 4:45, couper un bloc plutôt que d'accélérer le débit. *(Corrigé le 29/08 : deux des trois durées annoncées ici ne dérivaient pas du compte de mots — 4:09 au lieu de 3:59 à 165, et surtout **4:48 au lieu de 4:58** à 130, ce qui annonçait douze secondes de marge là où il y en a deux.)* Le guide lablab insiste aussi sur "démo tôt" — ici le tableau de bord est à l'écran dès la première seconde, et le premier run réel à 1:12.
- **La structure officielle attendue est "introduction → discuter la présentation PDF → montrer les fonctionnalités".** ✅ Couvert : l'accroche se termine désormais sur "tout est détaillé dans le write-up d'une page joint à la soumission". Cette note demandait la phrase ; elle y est.
- **Ne pas dire "ROI garanti" ou "+X% de gains"** nulle part — le backtest dit l'inverse, et le mentir en vidéo contredirait tout le reste de la soumission.
- Si aucun trade réel n'a encore eu lieu au moment de l'enregistrement, dire clairement "voici un dry-run" plutôt que de laisser croire à un ordre réel.
- Si le compte dédié (`.env.hackathon`) est déjà branché et a un vrai historique cette semaine-là, remplacer la section 1:12–2:31 par un vrai run sur ce compte — plus fort qu'un dry-run.
- Sous-titres recommandés si l'anglais du narrateur n'est pas fluide à l'oral — beaucoup de juges lisent plus vite qu'ils n'écoutent.
- **Cover image de la soumission** (exigence trouvée 25/08, distincte de la vidéo) : PNG ou JPG, ratio 16:9 recommandé — à préparer séparément, pas couvert par ce script.
- **Réponse prête si un juge demande "est-ce que ça existe déjà" (recherché 25/08)** : le mécanisme s'apparente à la Probability of Backtest Overfitting / walk-forward optimization de la littérature quant (López de Prado et al.), mais validées une fois à la conception — la vraie différence de ce projet, c'est que le test tourne à CHAQUE décision live, pas une seule fois. Détail complet dans le README ("Where this sits in the existing literature"), pas la peine de le réciter dans la vidéo elle-même — juste avoir la réponse prête pour un Q&A.
