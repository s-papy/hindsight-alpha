# CLAUDE.md — hindsight-alpha

## Le garde-fou

`python3 garde_fou.py` avant toute publication (README, submission/*, un commit vers un dépôt public). Construit le 25/08/2026 avec le skill `garde-fou-generique`, volontairement petit — chaque contrôle vient d'une vraie erreur déjà trouvée dans ce projet, jamais d'une anticipation. Détail de chaque contrôle et de son origine : commentaires dans `garde_fou.py` lui-même. Depuis le 25/08, un 6e contrôle surveille aussi `requirements.txt` (alerte non bloquante à chaque changement, née d'une demande d'installer un dépôt GitHub externe non vérifié, refusée ce soir-là).

**Règle non négociable, héritée d'un autre projet interne : on ne modifie jamais `garde_fou.py` pour faire taire une alerte — on corrige le dossier.** Si un contrôle bloque à tort (ça arrive — voir le commentaire sur "SPY, QQQ, IWM" dans le script, corrigé le jour même de sa création), on affine le contrôle avec une vraie raison écrite en commentaire, jamais en le supprimant pour effacer l'alerte.

**Active le hook automatique une fois par clone** (comparé le 25/08 à pre-commit.com / gitleaks / danger-js — le vrai trou n'était pas un contrôle manquant, c'était que rien ne forçait `garde_fou.py` à tourner) :

    git config core.hooksPath githooks

Après ça, chaque `git commit` relance `garde_fou.py` et refuse le commit si le verdict est 🔴 (contournable en connaissance de cause avec `git commit --no-verify`).

**Deuxième couche, sur GitHub même** (`.github/workflows/garde-fou.yml`, ajouté 25/08 — comparé au vrai déploiement de gitleaks, qui documente explicitement pre-commit local + CI comme un "programme en couches", jamais l'un sans l'autre) : le hook local ne protège que les machines où il a été activé, et `--no-verify` le contourne volontairement. La CI tourne sur GitHub même à chaque push/PR vers `main`, aucune des deux échappatoires ne s'applique — coche verte/rouge visible directement sur le dépôt public.

**Troisième hook, `githooks/pre-push`** (ajouté 25/08, en adaptant — pas en copiant — le principe `/careful` de gstack, lu en référence) : bloque tout push non-fast-forward (donc un `--force` ou `--force-with-lease`) vers une branche qui existe déjà côté distant. Comble un vrai trou : « jamais de `git push --force` » est répété tout au long de ce fichier depuis le début du sprint, mais rien ne le faisait respecter mécaniquement avant ce hook. Contournable en connaissance de cause avec `git push --no-verify`, comme le hook de commit.

## Vérifier avant d'affirmer

**Règle empruntée à `verification-before-completion` (skill `superpowers`, obra/superpowers, lu en référence)** — déjà la pratique réelle de ce projet (chaque correctif est reproduit par un témoin AVANT d'être déclaré bon), maintenant écrite noir sur blanc plutôt que seulement pratiquée :

**Aucune affirmation de succès sans preuve fraîche, obtenue dans le même message.** Avant de dire « ça marche », « le bug est corrigé », « les tests passent » : lancer la commande qui le prouve, lire sa sortie en entier, puis seulement affirmer — jamais l'inverse. « Ça devrait marcher », « je suis confiant », ou un rapport d'agent pris pour argent comptant ne comptent pas comme preuve.

## Contraintes non négociables du projet (répétées tout au long du sprint hackathon)

- **`.env.hackathon` et le compte Alpaca qu'il désigne : intouchables avant le kickoff du 28/08/2026**, même par accident.
- **Jamais `--live` au CLI, jamais `ALPACA_LIVE_TRADE=true`** — paper trading uniquement, `config.py` refuse de tourner sinon (vérifié par `garde_fou.py`).
- **Aucun seuil de risque modifié** (`MAX_RISK_PCT_PER_TRADE`, `MAX_TOTAL_RISK_PCT`, `MAX_SECTOR_EXPOSURE_PCT`, `WEEKLY_LOSS_LOCK_PCT`, `MAX_OPEN_POSITIONS`, `MAX_CONSECUTIVE_LOSSES`, `CHEAP_VOL_PERCENTILE`, `HEARTBEAT_SECONDS`) sans décision humaine explicite.
- **La stratégie live reste `vol_strategy.py`** — bascule vers `momentum_strategy.py` réservée à une décision humaine explicite, même si `momentum_strategy` passe `hindsight_guard` plus proprement (4/4 vs 3/4, observation honnête déjà documentée, pas une invitation à changer).
- **Jamais de `git push --force`.**
- **Aucune publication sur les réseaux sociaux au nom de l'auteur** — les brouillons restent locaux, à poster lui-même.
