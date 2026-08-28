# Provenance et authenticité — Hindsight Alpha

Ce dépôt est publié sous licence **MIT**, comme l'exige le règlement du
hackathon. N'importe qui peut donc légalement copier, modifier et
redistribuer ce code — **à une seule condition : conserver l'avis de
copyright**, présent en tête de chaque fichier source.

Ce document ne cherche pas à empêcher la copie. Il rend l'**antériorité**
et l'**authenticité** vérifiables par quiconque, sans avoir à croire
l'auteur sur parole.

## Ce qui est revendiqué

| | |
|---|---|
| Auteur | Spap |
| Premier commit | `68c778db272217d56ebaad1c430a90bf8d8454a6 2026-08-24 17:35:59 +0200` |
| Dépôt d'origine | https://github.com/s-papy/hindsight-alpha |
| Licence | MIT (`LICENSE`) |

## Vérifier une version signée

Les **tags** de ce dépôt sont signés avec une clé SSH. La clé **publique**
correspondante est committée ici — c'est ce qui rend la vérification
possible ailleurs que sur GitHub, et à n'importe quelle date future :

    provenance/hindsight-alpha-signing-key.pub
    empreinte : SHA256:NcF2m5Ck6hUYtSI1bQ2uTD6CiP05fstUJBOH8D9gfTc

Pour vérifier un tag depuis un clone :

    printf '%s %s\n' "<email de l'auteur>" \
      "$(cat provenance/hindsight-alpha-signing-key.pub)" > /tmp/signers
    git -c gpg.ssh.allowedSignersFile=/tmp/signers tag -v <nom-du-tag>

Une signature valide affiche `Good "git" signature`.

## Ce que cela prouve, et ce que cela ne prouve pas

**Prouve** : que le contenu du tag a été signé par le détenteur de cette
clé, et que l'historique public existe depuis la date ci-dessus. Une copie
antidatée est impossible : les horodatages et les empreintes de commit
sont chaînés.

**Ne prouve pas**, et il faut le dire : que l'idée est originale. Personne
ne peut revendiquer « vérifier une sélection de paramètre contre une
fenêtre cachée » — c'est une pratique connue de la littérature quantitative
(voir la section « Where this sits in the existing literature » du README,
qui dit ce qui est emprunté et ce qui ne l'est pas). Ce qui est daté et
signé ici, c'est **cette implémentation**, pas le concept.

## Limites assumées

- **Les 177 premiers commits ne sont pas signés.** Les signer aurait exigé
  de réécrire l'historique, ce qui change tous les identifiants de commit —
  donc détruit précisément la preuve d'antériorité qu'on cherche à
  protéger. La signature porte sur les **tags**, qui couvrent l'état
  complet de l'arbre à une date donnée sans toucher au passé.
- **Une clé publique committée dans le dépôt qu'elle signe** n'est pas une
  autorité de certification : quelqu'un qui forke peut y mettre la sienne.
  Ce qu'elle apporte, c'est la continuité — cette clé est présente dans
  l'historique public depuis ce commit-ci, avant tout litige.
- Le badge *Verified* de GitHub dépend en plus que la clé soit enregistrée
  comme **Signing Key** sur le compte de l'auteur.

## Marques distinctives

Au-delà de la cryptographie, ce dépôt porte des traits qu'une copie ne
peut pas reproduire de façon crédible : les commentaires de code sont
rédigés en français, datés, et expliquent la **mesure** qui a motivé
chaque correctif (« mesuré le 27/08 : … »). Les messages de commit
contiennent les chiffres relevés avant et après. Un dépôt qui affiche ces
raisonnements sans l'historique qui les a produits se signale de lui-même.
