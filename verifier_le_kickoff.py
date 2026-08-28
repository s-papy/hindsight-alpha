#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.
"""Une seule commande qui dit CE QUI RESTE A FAIRE avant la seance.

Pourquoi ce fichier existe : au matin du kickoff, la liste des gestes
manuels tenait sur cinq points -- declarer le compte, recharger deux
LaunchAgents, pousser, poser un tag signe, basculer les identifiants. Cinq
choses a se rappeler, un soir de kickoff, est une de trop.

Ce script ne REFAIT rien : il DELEGUE aux controles qui existent deja
(garde_fou.py, test_connection.py) et n'ajoute que ce que personne ne
verifiait -- les plists charges contre ceux du depot, les commits pousses,
le tag signe. Ecrire une regle ici alors qu'elle vit deja ailleurs serait
la faute que ce depot passe son temps a debusquer.

    python3 verifier_le_kickoff.py            # sans reseau
    python3 verifier_le_kickoff.py --reseau   # + verifie le compte Alpaca

Ne modifie RIEN. Il lit, il compare, il dit.
"""

from __future__ import annotations

import argparse
import filecmp
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).parent
AGENTS = Path.home() / "Library" / "LaunchAgents"

VERT, JAUNE, ROUGE = "🟢", "🟡", "🔴"


def _dire(etat: str, titre: str, detail: str = "") -> None:
    print("  %s %-38s %s" % (etat, titre, detail))


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=RACINE, capture_output=True,
                           text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def compte_declare() -> bool:
    """Delegue la regle a config, qui la possede."""
    sys.path.insert(0, str(RACINE))
    try:
        import config
    except Exception as e:
        _dire(ROUGE, "compte declare", "config illisible (%s)" % type(e).__name__)
        return False
    if config.compte_est_declare():
        _dire(VERT, "compte declare", "les trois gardes sont actifs")
        return True
    _dire(ROUGE, "compte declare",
          "ALPACA_ACCOUNT_ID absent : entrees, sorties et publication ne "
          "verifient RIEN")
    return False


def plists_a_jour() -> bool:
    """Les LaunchAgents charges sont-ils bien ceux du depot ?

    Personne ne verifiait ca : un plist corrige dans le depot reste sans
    effet tant qu'il n'est pas recopie ET recharge. C'est arrive le 28/08
    avec la fenetre de veille.
    """
    livres = sorted(RACINE.joinpath("launchagents").glob("*.plist"))
    if not livres:
        _dire(JAUNE, "LaunchAgents", "aucun plist livre")
        return True
    perimes = []
    for source in livres:
        actif = AGENTS / source.name
        if not actif.exists():
            perimes.append(source.name + " (absent)")
        elif not filecmp.cmp(source, actif, shallow=False):
            perimes.append(source.name + " (different)")
    if perimes:
        _dire(ROUGE, "LaunchAgents charges",
              "a recopier + recharger : %s" % ", ".join(perimes))
        return False
    _dire(VERT, "LaunchAgents charges", "%d identiques au depot" % len(livres))
    return True


def travail_pousse() -> bool:
    en_attente = _git("rev-list", "--count", "origin/main..HEAD")
    if en_attente and en_attente != "0":
        _dire(ROUGE, "travail pousse",
              "%s commit(s) locaux : une anteriorite non poussee ne prouve "
              "rien publiquement" % en_attente)
        return False
    _dire(VERT, "travail pousse", "rien en attente")
    return True


def tag_signe() -> bool:
    """Le dernier tag signe couvre-t-il l'etat ACTUEL ?

    Corrige juste apres la premiere execution de ce script : il prenait
    `tags[-1]`, c'est-a-dire le dernier par ordre ALPHABETIQUE, et se
    contentait de dire « verifie ». Il annoncait donc en vert un tag pose la
    veille, avec 33 commits apres lui -- une signature valide sur un etat
    perime, ce qui est precisement la fausse assurance qu'on cherche a
    eviter. Le tri est desormais chronologique, et la distance a HEAD est
    dite.
    """
    tags = [t for t in _git("tag", "--sort=-creatordate").splitlines()
            if t.strip()]
    if not tags:
        _dire(JAUNE, "tag signe", "aucun tag : rien n'est signe a ce jour")
        return False
    dernier = tags[0]
    sortie = subprocess.run(["git", "tag", "-v", dernier], cwd=RACINE,
                            capture_output=True, text=True, timeout=30)
    texte = sortie.stdout + sortie.stderr
    valide = "Good" in texte and "signature" in texte
    apres = _git("rev-list", "--count", "%s..HEAD" % dernier) or "?"

    if not valide:
        # DISTINGUER LES DEUX CAUSES, ajoute le 28/08/2026 apres avoir
        # reproduit le piege : `git tag -s` rend le code de sortie 0 et cree
        # un tag SANS SIGNATURE quand la phrase secrete de la cle n'a pas pu
        # etre saisie. Mesure sur cette machine :
        #
        #   git tag -s essai2-claude -m "essai"   -> code 0
        #   git cat-file tag essai2-claude        -> aucun bloc SSH SIGNATURE
        #
        # Un tel tag se pousse sans broncher et ne prouve RIEN. Un
        # enchainement `git tag -s ... && git push ...` le publierait en
        # silence, puisque le && ne voit qu'un succes.
        #
        # « pas verifiee ici » couvrait les deux cas et laissait croire au
        # moins grave. Un fichier de signataires incomplet se repare en une
        # ligne ; un tag non signe doit etre refait.
        objet = subprocess.run(["git", "cat-file", "tag", dernier], cwd=RACINE,
                               capture_output=True, text=True, timeout=20)
        non_signe = ("SSH SIGNATURE" not in objet.stdout
                     and "PGP SIGNATURE" not in objet.stdout)
        if non_signe:
            _dire(ROUGE, "tag signe",
                  "%s N'EST PAS SIGNE — l'objet ne contient aucune signature. "
                  "Il ne prouve rien : refais-le en saisissant la phrase "
                  "secrete de la cle." % dernier)
        else:
            _dire(JAUNE, "tag signe",
                  "%s porte bien une signature, mais elle ne se verifie pas "
                  "ici (fichier des signataires autorises ?)" % dernier)
        return False
    if apres != "0":
        _dire(JAUNE, "tag signe",
              "%s valide, mais %s commit(s) APRES lui : l'etat actuel n'est "
              "pas signe" % (dernier, apres))
        return False
    _dire(VERT, "tag signe", "%s couvre l'etat actuel" % dernier)
    return True


def garde_fou() -> bool:
    # Borne de temps OBLIGATOIRE : un test de ce depot refuse tout
    # sous-processus non borne, et il a attrape ces trois appels-ci a la
    # premiere execution de la suite. garde_fou tourne en 0.63 s (mesure),
    # donc 60 s est large sans jamais figer la verification.
    r = subprocess.run([sys.executable, str(RACINE / "garde_fou.py")],
                       cwd=RACINE, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        _dire(ROUGE, "garde-fou", "verdict BLOQUANT — lance-le pour le detail")
        return False
    jaunes = r.stdout.count("\n   ") if "REGARDER" in r.stdout else 0
    _dire(VERT if jaunes == 0 else JAUNE, "garde-fou",
          "aucun point" if jaunes == 0 else "%d point(s) a regarder" % jaunes)
    return True


def compte_reel() -> bool:
    """Delegue entierement a test_connection.py, qui possede cette regle."""
    # Celui-ci sort sur le RESEAU : sans borne, une API muette figerait la
    # verification pour toujours -- exactement ce que ce garde interdit.
    r = subprocess.run([sys.executable, str(RACINE / "test_connection.py")],
                       cwd=RACINE, capture_output=True, text=True, timeout=120)
    sortie = r.stdout + r.stderr
    if "MAUVAIS COMPTE" in sortie:
        _dire(ROUGE, "compte Alpaca", "MAUVAIS COMPTE — ne lance pas agent.py")
        return False
    if "All good" in sortie or r.returncode == 0:
        ligne = next((l.strip() for l in sortie.splitlines()
                      if "All good" in l or "confirmed" in l), "connexion OK")
        _dire(VERT, "compte Alpaca", ligne[:44])
        return True

    # NE PAS DEPENDRE D'UNE PHRASE. Corrige le 28/08/2026 a 20h35, sur un vrai
    # mauvais compte, une heure avant le premier passage de l'agent.
    #
    # Ce controle cherchait « MAUVAIS COMPTE » dans la sortie. Or
    # test_connection.py n'imprimait PAS cette chaine -- elle vivait seulement
    # dans une variable interne, et le texte affiche etait « STOP: ... ». Le
    # cas le PLUS dangereux tombait donc dans le dernier `return False`, avec
    # le message le plus doux du script : « non verifie ».
    #
    # La chaine est corrigee cote test_connection.py, mais un couplage par
    # PHRASE derive tot ou tard -- c'est exactement ce qui vient d'arriver, et
    # c'est le meme defaut que coherence.py corrige cet apres-midi. On ajoute
    # donc une regle qui ne depend d'aucun texte : test_connection.py sort en
    # ZERO quand tout va bien. Un code NON NUL est une anomalie, et une
    # anomalie sur l'identite du compte se traite en ROUGE, pas en jaune.
    _dire(ROUGE, "compte Alpaca",
          "test_connection.py a rendu le code %d — anomalie non identifiee, "
          "traitee comme bloquante. Lance-le a la main pour la raison exacte."
          % r.returncode)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reseau", action="store_true",
                        help="verifie aussi le compte Alpaca (appel API)")
    args = parser.parse_args()

    print("\n  PRET POUR LA SEANCE ?\n")
    resultats = [compte_declare(), plists_a_jour(), travail_pousse(),
                 tag_signe(), garde_fou()]
    if args.reseau:
        resultats.append(compte_reel())
    else:
        _dire(JAUNE, "compte Alpaca", "non verifie (relance avec --reseau)")

    print()
    if all(resultats):
        print("  Tout est en place.\n")
    else:
        print("  %d point(s) a traiter ci-dessus.\n"
              % sum(1 for r in resultats if not r))
    sys.exit(0)


if __name__ == "__main__":
    main()
