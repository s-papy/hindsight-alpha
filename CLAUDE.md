# CLAUDE.md — hindsight-alpha

## Le garde-fou

`python3 garde_fou.py` avant toute publication (README, submission/*, un commit vers un dépôt public). Construit le 25/08/2026, volontairement petit — chaque contrôle vient d'une vraie erreur déjà trouvée dans ce projet, jamais d'une anticipation. Détail de chaque contrôle et de son origine : commentaires dans `garde_fou.py` lui-même. Un de ces contrôles surveille `requirements.txt` (alerte non bloquante à chaque changement, née d'une demande d'installer un dépôt GitHub externe non vérifié, refusée le 25/08). *Ce paragraphe numérotait ce contrôle par un ordinal figé au 25/08, devenu faux depuis. L'ordinal est retiré plutôt que corrigé : un compte écrit à la main dans un document vieillit à chaque ajout, alors que `garde_fou.py` s'annonce lui-même à l'exécution. Un test refuse désormais tout compte de contrôles écrit à la main ici — et il a d'abord attrapé cette note-ci, qui reproduisait la formule périmée en la citant.*

**Règle non négociable, héritée d'un autre projet interne : on ne modifie jamais `garde_fou.py` pour faire taire une alerte — on corrige le dossier.** Si un contrôle bloque à tort (ça arrive — voir le commentaire sur "SPY, QQQ, IWM" dans le script, corrigé le jour même de sa création), on affine le contrôle avec une vraie raison écrite en commentaire, jamais en le supprimant pour effacer l'alerte.

**Active le hook automatique une fois par clone** — le vrai trou n'était pas un contrôle manquant, c'était que rien ne forçait `garde_fou.py` à tourner :

    git config core.hooksPath githooks

Après ça, chaque `git commit` relance `garde_fou.py` et refuse le commit si le verdict est 🔴 (contournable en connaissance de cause avec `git commit --no-verify`).

**Deuxième couche, sur GitHub même** (`.github/workflows/garde-fou.yml`, ajouté 25/08 : un contrôle local et un contrôle en CI, jamais l'un sans l'autre) : le hook local ne protège que les machines où il a été activé, et `--no-verify` le contourne volontairement. La CI tourne sur GitHub même à chaque push/PR vers `main`, aucune des deux échappatoires ne s'applique — coche verte/rouge visible directement sur le dépôt public.

**Troisième hook, `githooks/pre-push`** (ajouté 25/08) : bloque tout push non-fast-forward (donc un `--force` ou `--force-with-lease`) vers une branche qui existe déjà côté distant. Comble un vrai trou : « jamais de `git push --force` » est répété tout au long de ce fichier depuis le début du sprint, mais rien ne le faisait respecter mécaniquement avant ce hook. Contournable en connaissance de cause avec `git push --no-verify`, comme le hook de commit.

## Vérifier avant d'affirmer

**Déjà la pratique réelle de ce projet** — chaque correctif est reproduit par un témoin AVANT d'être déclaré bon — **maintenant écrite noir sur blanc plutôt que seulement pratiquée** :

**Aucune affirmation de succès sans preuve fraîche, obtenue dans le même message.** Avant de dire « ça marche », « le bug est corrigé », « les tests passent » : lancer la commande qui le prouve, lire sa sortie en entier, puis seulement affirmer — jamais l'inverse. « Ça devrait marcher », « je suis confiant », ou un rapport d'agent pris pour argent comptant ne comptent pas comme preuve.

## Contraintes non négociables du projet (répétées tout au long du sprint hackathon)

- **`.env.hackathon` et le compte Alpaca qu'il désigne : intouchables avant le kickoff du 28/08/2026**, même par accident.
- **Jamais `--live` au CLI, jamais `ALPACA_LIVE_TRADE=true`** — paper trading uniquement, `config.py` refuse de tourner sinon (vérifié par `garde_fou.py`).
- **Aucun seuil de risque modifié** (`MAX_RISK_PCT_PER_TRADE`, `MAX_TOTAL_RISK_PCT`, `MAX_SECTOR_EXPOSURE_PCT`, `WEEKLY_LOSS_LOCK_PCT`, `MAX_OPEN_POSITIONS`, `MAX_CONSECUTIVE_LOSSES`, `CHEAP_VOL_PERCENTILE`, `HEARTBEAT_SECONDS`) sans décision humaine explicite.
- **La stratégie live reste `vol_strategy.py`** — bascule vers `momentum_strategy.py` réservée à une décision humaine explicite, et l'argument « momentum est plus propre » NE LA SOUTIENT PAS — mesuré
  le 28/08, deux fois :
    - **4/4 contre 3/4 n'est pas distinguable du hasard.** Test exact de
      Fisher sur la table observée : *p = 1.000*. Si les deux stratégies
      étaient identiques, un écart d'au moins un symbole apparaîtrait
      encore 48 à 70 % du temps à n=4.
    - **Les deux ne décident pas sur la même information.** Mesuré par
      perturbation : `vol_strategy` saute un jour entre sa dernière
      information et son payoff, `momentum` non. Momentum décide donc sur
      une information plus fraîche d'un jour, ce qui l'avantage.
  L'observation reste publiée (README, STRATEGY_COMPARISON.md) avec ces deux
  réserves. La contrainte, elle, ne change pas : la bascule reste une
  décision humaine explicite.
- **Jamais de `git push --force`.**
- **Aucune publication sur les réseaux sociaux au nom de l'auteur** — les brouillons restent locaux, à poster lui-même.
