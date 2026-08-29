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
import os
import plistlib
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).parent
AGENTS = Path.home() / "Library" / "LaunchAgents"

VERT, JAUNE, ROUGE = "🟢", "🟡", "🔴"


# CE QUI A ETE AFFICHE. Le verdict final se calcule sur CETTE liste, et non
# sur un decompte parallele -- deux comptes du meme etat finissent toujours
# par diverger, et celui-ci avait deja diverge (voir main()).
_AFFICHES: list = []


def _dire(etat: str, titre: str, detail: str = "") -> None:
    _AFFICHES.append(etat)
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


def _intervalles_charges(label: str) -> "list | None":
    """Les horaires que launchd a REELLEMENT charges pour ce job, ou None si
    on n'a pas pu les lire.

    `launchctl print` expose les declencheurs calendaires tels qu'ils ont ete
    charges -- ce qui n'est pas la meme chose que le contenu du fichier sur le
    disque, puisqu'un plist recopie sans rechargement laisse launchd sur
    l'ancienne version. C'est exactement l'ecart que ce controle existait pour
    fermer, et qu'il ne fermait qu'a moitie.

    Rend None, jamais [], quand la lecture echoue : une liste vide voudrait
    dire « aucun horaire charge », et ce n'est pas ce qu'on a mesure."""
    try:
        r = subprocess.run(
            ["launchctl", "print", "gui/%d/%s" % (os.getuid(), label)],
            capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    out = []
    for bloc in re.findall(r"descriptor = \{(.*?)\}", r.stdout, re.S):
        d = {c: int(v) for c, v in re.findall(r'"(\w+)" => (\d+)', bloc)}
        if d:
            out.append(tuple(sorted(d.items())))
    return sorted(out)


def _intervalles_du_fichier(chemin: Path) -> "list | None":
    try:
        with open(chemin, "rb") as fh:
            d = plistlib.load(fh)
    except Exception:
        return None
    iv = d.get("StartCalendarInterval") or []
    if isinstance(iv, dict):
        iv = [iv]
    try:
        return sorted(tuple(sorted(e.items())) for e in iv)
    except Exception:
        return None


def plists_a_jour() -> bool:
    """Les LaunchAgents charges sont-ils bien ceux du depot ?

    Personne ne verifiait ca : un plist corrige dans le depot reste sans
    effet tant qu'il n'est pas recopie ET recharge. C'est arrive le 28/08
    avec la fenetre de veille.

    IL N'EN VERIFIAIT QUE LA MOITIE, corrige le 29/08/2026. Il comparait les
    FICHIERS -- depot contre ~/Library/LaunchAgents -- et titrait la ligne
    « LaunchAgents charges ». Or « recopie » n'est pas « recharge » : un
    operateur qui copie sans faire `launchctl unload/load` obtenait un 🟢
    pendant que launchd continuait sur l'ancien horaire. Le mot « charges »
    nommait precisement ce que le controle ne mesurait pas.

    `launchctl print` donne les declencheurs calendaires TELS QUE CHARGES.
    Mesure du 29/08 : les quatre jobs concordent, 5, 5, 140 et 75
    declencheurs, identiques au depot -- donc ce controle ne change aucun
    verdict aujourd'hui ; il ferme la moitie qui manquait."""
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

    # Les fichiers concordent. Reste la question que le titre posait sans y
    # repondre : est-ce bien ca que launchd fait tourner ?
    illisibles, divergents = [], []
    for source in livres:
        label = source.name[:-len(".plist")]
        charges = _intervalles_charges(label)
        attendus = _intervalles_du_fichier(source)
        if charges is None or attendus is None:
            illisibles.append(label)
        elif charges != attendus:
            divergents.append(label)
    if divergents:
        _dire(ROUGE, "LaunchAgents charges",
              "fichiers a jour mais launchd tourne sur un AUTRE horaire "
              "(%s) — `launchctl unload` puis `load`" % ", ".join(divergents))
        return False
    if illisibles:
        # NI VERT NI ROUGE. Les fichiers sont bons ; l'etat charge n'a pas pu
        # etre lu. Dire « charges » ici serait reprendre exactement le mot
        # qu'on vient de cesser d'affirmer sans mesure.
        _dire(JAUNE, "LaunchAgents",
              "%d fichiers identiques au depot, mais l'etat CHARGE n'a pas pu "
              "etre lu pour : %s" % (len(livres), ", ".join(illisibles)))
        return True
    _dire(VERT, "LaunchAgents charges",
          "%d identiques au depot ET charges avec ces horaires" % len(livres))
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
    # ON LIT LE NOMBRE QUE LE GARDE-FOU ANNONCE, on ne recompte pas sa prose.
    #
    # C'etait `r.stdout.count("\\n   ")`, soit « toute ligne commencant par
    # trois espaces ». Mesure le 29/08/2026, garde-fou a UN seul point :
    #
    #     count("\\n   ") = 2
    #       "   submission/Hindsight_Alpha_Deck.pptx  cite un nombre..."
    #       "     pas le fond. Un dossier qu'il approuve peut encore..."
    #
    # La seconde est la deuxieme ligne de l'avertissement PERMANENT du
    # garde-fou, present a chaque execution -- et cinq espaces contiennent
    # trois espaces. Le compte etait donc toujours +1 des qu'il y avait au
    # moins un point, et une entree qui passe a la ligne en aurait ajoute
    # d'autres. Deux controles du meme dossier annoncaient des chiffres
    # differents pour la meme chose.
    #
    # Le garde-fou imprime deja le nombre : « 🟡 A REGARDER : 1 ». C'est lui
    # qui fait autorite. Le relire est plus juste que le recompter.
    annonce = re.search(r"REGARDER\s*:\s*(\d+)", r.stdout)
    if annonce is None:
        if "REGARDER" in r.stdout:
            # FERMETURE : verdict jaune dont on n'a pas su lire le compte.
            # Rendre 0 dirait « aucun point » -- « je n'ai pas compris »
            # n'est pas « il n'y a rien ».
            _dire(JAUNE, "garde-fou",
                  "des points a regarder, mais leur NOMBRE n'a pas pu etre lu "
                  "— lance `python3 garde_fou.py`")
            return True
        jaunes = 0
    else:
        jaunes = int(annonce.group(1))
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
    # Les valeurs de retour ne sont plus collectees : le verdict se lit sur
    # _AFFICHES, rempli par _dire. Garder une seconde liste en parallele
    # etait justement ce qui permettait aux deux de diverger.
    compte_declare()
    plists_a_jour()
    travail_pousse()
    tag_signe()
    garde_fou()
    if args.reseau:
        compte_reel()
    else:
        _dire(JAUNE, "compte Alpaca", "non verifie (relance avec --reseau)")

    print()
    # LE VERDICT SE LIT SUR CE QUI EST AFFICHE. Corrige le 29/08/2026.
    #
    # C'etait `all(resultats)` puis un compte des False. Deux ecarts mesures
    # sur la sortie reelle :
    #
    #   . `garde_fou()` rend True meme quand il affiche 🟡, et la branche
    #     sans --reseau AFFICHE « compte Alpaca : non verifie » sans rien
    #     ajouter a `resultats`. Avec tout le reste au vert, le script
    #     imprimait donc DEUX lignes jaunes puis « Tout est en place. » --
    #     dont « je n'ai pas verifie sur quel compte tu es », la panne exacte
    #     du 28/08 ;
    #   . et quand il y avait bien des False, « 2 point(s) a traiter »
    #     s'affichait sous QUATRE lignes non vertes. Un lecteur qui compte
    #     les couleurs trouvait autre chose que le resume.
    #
    # Le verdict vient de _AFFICHES, la meme source que les lignes ci-dessus.
    # Un resume ne peut plus contredire le detail qu'il resume.
    rouges = _AFFICHES.count(ROUGE)
    jaunes = _AFFICHES.count(JAUNE)
    if not rouges and not jaunes:
        print("  Tout est en place.\n")
    elif rouges:
        print("  %d bloquant(s) et %d point(s) a regarder ci-dessus.\n"
              % (rouges, jaunes))
    else:
        print("  %d point(s) a regarder ci-dessus — rien de bloquant.\n"
              % jaunes)
    sys.exit(0)


if __name__ == "__main__":
    main()
