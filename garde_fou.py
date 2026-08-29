#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.
"""garde_fou.py — hindsight-alpha

    python3 garde_fou.py

POURQUOI IL EXISTE
===================
Né le 25/08/2026, après avoir remarqué qu'aucun garde-fou ne tournait
sur ce projet — contrairement à d'autres projets internes, qui en ont un
depuis longtemps. Ce script
démarre PETIT, volontairement : chaque contrôle ci-dessous vient soit de la
forme minimale retenue au départ (journal + horodatage), soit d'une vraie
erreur déjà commise et documentée dans CE projet, jamais d'une anticipation. Le détail de chaque incident cité
en commentaire est conservé dans le journal d'ingénierie du projet.

Règle non négociable, héritée d'un projet antérieur : ON NE MODIFIE JAMAIS
CE SCRIPT
POUR LE FAIRE TAIRE. Si un contrôle est trop bruyant ou faux, on corrige
le contrôle avec une vraie raison écrite ici — jamais en le supprimant
pour effacer une alerte gênante. Si un contrôle bloque à tort, dis-le à
l'opérateur plutôt que de le désactiver toi-même.

Standard library only — même philosophie que hindsight_guard.py.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import ast
import re
import subprocess
import sys
import zipfile
from datetime import date, timedelta, datetime

RACINE = os.path.dirname(os.path.abspath(__file__))

blocages: list[tuple[str, str]] = []
alertes: list[tuple[str, str]] = []


def bloque(fichier: str, message: str) -> None:
    blocages.append((fichier, message))


def alerte(fichier: str, message: str) -> None:
    alertes.append((fichier, message))


# ── CONTRÔLE 1 : LE JOURNAL EXISTE ET NE MENT PAS SUR LA DATE ──────────────
# La forme minimale retenue au départ, appliquée telle quelle :
# PLAN_SPRINT.md fait office de journal de bord de ce
# projet. Chaque section datée (「## ... JJ/MM ...」) est relue ; une
# date qui tombe dans le futur par rapport à `date` est bloquante — même
# piège qu'un défaut déjà trouvé et corrigé sur un projet antérieur les
# 07-08/08 (une ligne de journal datée d'un jour pas encore arrivé). Jamais reproduit ici, mais
# le contrôle est gratuit et le principe est le même journal.
def _journal_volontairement_local() -> bool:
    """True si PLAN_SPRINT.md est DÉCLARÉ dans .gitignore.

    AJOUTÉ le 26/08/2026, et il faut dire pourquoi, parce que ça ressemble de
    loin à « modifier le script pour le faire taire » — ce que ce projet
    s'interdit.

    Ce soir, PLAN_SPRINT.md a été retiré du suivi git (il reste sur le disque,
    l'historique n'a pas été réécrit). Le contrôle 1 a alors bloqué EN CI :
    dans un checkout propre, le fichier n'existe pas du tout. Croix rouge sur
    le dépôt public — celle-là même dont CLAUDE.md vante la visibilité.

    La prémisse du contrôle a changé, pas sa valeur. « Le journal manque » est
    un vrai défaut quand le journal EST censé être là ; c'est une situation
    ATTENDUE quand le fichier est explicitement déclaré local. On distingue
    donc les deux, plutôt que de relâcher le contrôle dans les deux cas.

    Le critère est .gitignore et pas une variable d'environnement `CI` : un
    verdict qui dépend de la machine est exactement le défaut corrigé au
    commit précédent (« the future-date check gave a different verdict per
    machine »). .gitignore est versionné, donc le critère est le même partout.

    FAIL-CLOSED : si .gitignore est illisible, on ne peut pas conclure, donc on
    ne relâche RIEN — le contrôle reste bloquant.
    """
    try:
        with open(os.path.join(RACINE, ".gitignore"), encoding="utf-8") as fh:
            return any(l.strip() == "PLAN_SPRINT.md" for l in fh)
    except OSError:
        return False


def controle_journal() -> None:
    chemin = os.path.join(RACINE, "PLAN_SPRINT.md")
    if not os.path.exists(chemin):
        if _journal_volontairement_local():
            # Surtout PAS un silence. Le contrôle n'a rien vérifié ici et doit
            # le dire : sans cette ligne, un 🟢 de CI laisserait croire que les
            # dates du journal ont été relues, alors que personne ne les a
            # regardées. Il reste pleinement effectif sur la machine où le
            # journal vit — c'est là qu'il est écrit, donc là qu'il peut mentir.
            alerte("PLAN_SPRINT.md",
                   "absent de ce clone, et c'est ATTENDU : déclaré dans .gitignore, "
                   "donc volontairement local. Ce contrôle n'a RIEN vérifié ici ; "
                   "il reste effectif là où le journal existe.")
        else:
            bloque("PLAN_SPRINT.md", "JOURNAL ABSENT — aucun journal de bord trouvé.")
        return
    aujourdhui = date.today()
    lignes = open(chemin, encoding="utf-8").read().split("\n")
    for i, l in enumerate(lignes, 1):
        if not l.startswith("## "):
            continue
        m = re.search(r"(\d{1,2})/(\d{1,2})", l)
        if not m:
            continue
        jj, mm = int(m.group(1)), int(m.group(2))
        if not (1 <= jj <= 31 and 1 <= mm <= 12):
            continue
        try:
            # Pas d'année dans les titres de PLAN_SPRINT.md — on suppose
            # l'année en cours. Limite honnête : autour du réveillon, une
            # entrée de janvier écrite fin décembre pourrait sembler
            # "future" à tort. Le projet se termine le 04/09/2026, donc
            # sans objet pour ce sprint précis.
            d = date(aujourdhui.year, mm, jj)
        except ValueError:
            bloque("PLAN_SPRINT.md", "ligne %d : date impossible (%s)" % (i, m.group(0)))
            continue
        # Tolérance d'un jour, et ce n'est pas du laxisme : sans elle ce
        # contrôle rend un verdict DIFFÉRENT selon la machine qui l'exécute.
        # Constaté pour de vrai le 26/08 — deux titres datés 26/08 passaient
        # en local (Mac en CEST, où c'était déjà le 26) et BLOQUAIENT la CI
        # GitHub (runner en UTC, où il était encore le 25 à 22h51), sur le
        # même commit. Les dates de PLAN_SPRINT.md sont écrites dans le
        # fuseau de l'opérateur (Europe/Zurich, UTC+1/+2), donc une entrée peut
        # légitimement être "demain" pour un runner UTC. Un jour d'avance est
        # normal ; deux ne le sont pas, et restent bloqués.
        if d > aujourdhui + timedelta(days=1):
            bloque(
                "PLAN_SPRINT.md",
                "ligne %d : DATE DANS LE FUTUR — « %s » (%s > %s)"
                % (i, l.strip()[:80], d, aujourdhui),
            )


# ── CONTRÔLE 2 : LE COMPTE HACKATHON EST UN FICHIER SCELLÉ AVANT LE KICKOFF ─
# Née de la contrainte répétée littéralement des dizaines de fois dans
# cette session : « ne jamais toucher .env.hackathon ni le compte
# qu'il désigne avant le kickoff du 28/08 ». C'est l'équivalent exact d'un
# fichier « scellé » sur un projet antérieur — sauf que la pire façon de le
# "modifier"
# ici serait de le committer par erreur (fuite de clé API), pas de changer
# son contenu. Donc le contrôle mécanique porte sur DEUX choses vérifiables
# sans jamais lire le fichier lui-même : (a) il ne doit JAMAIS être suivi
# par git, (b) .gitignore doit continuer à le couvrir.
def _message_premier_scelle(registre_existait: bool, empreinte: str) -> str:
    """Message de la branche « pas d'empreinte connue » d'un scellé.

    AJOUTE le 27/08/2026. Cette branche disait toujours « première lecture —
    empreinte enregistrée, sera comparée au prochain run ». Vrai sur la machine
    de travail. Faux, et trompeur, partout ailleurs.

    Mesure : le registre .garde_fou_scelles.json est dans .gitignore, donc
    ABSENT de tout clone frais. Chaque run de CI part d'un clone frais. Le
    scellé y prend donc systematiquement cette branche, ecrit un registre
    ephemere, et ne compare RIEN -- verifie en clonant ce depot et en lancant
    garde_fou.py : « premiere lecture » au premier passage, plus rien au
    second. Un scellé qui ne compare rien affichait le meme 🟡 rassurant qu'un
    scellé qui a compare et trouve le fichier intact.

    controle_journal() fait deja la bonne chose pour le journal absent d'un
    clone (« Ce controle n'a RIEN verifie ici »). Meme traitement ici.
    """
    if registre_existait:
        return ("🆕 première lecture de ce fichier — empreinte enregistrée (%s…). "
                "Sera comparée au prochain run." % empreinte[:12])
    return (
        "🆕 AUCUN REGISTRE D'EMPREINTES sur cette machine — les scellés sont un "
        "état LOCAL, jamais committé (.gitignore). Ce contrôle n'a donc RIEN "
        "vérifié ici : c'est le cas de chaque run de CI, qui part d'un clone "
        "neuf. Empreinte %s… enregistrée pour ce run, mais elle disparaîtra "
        "avec lui. Le scellé reste effectif sur la machine où garde_fou.py "
        "tourne régulièrement." % empreinte[:12]
    )


def controle_env_hackathon_scelle() -> None:
    motif_gitignore = os.path.join(RACINE, ".gitignore")
    if os.path.exists(motif_gitignore):
        contenu = open(motif_gitignore, encoding="utf-8").read()
        # .env.* couvre .env.hackathon ; une ligne explicite suffit aussi.
        if not re.search(r"^\.env(\.\*|\.hackathon)?\s*$", contenu, re.M):
            bloque(
                ".gitignore",
                "ne couvre plus .env.hackathon — un motif .env* ou "
                ".env.hackathon explicite a disparu.",
            )
    else:
        bloque(".gitignore", "ABSENT — .env.hackathon ne serait protégé par rien.")

    # AJOUTE le 27/08/2026 : dire quand on ne peut PAS conclure.
    #
    # Les deux appels git de ce controle ne regardaient que `.stdout`, jamais le
    # code de retour. Or `git ls-files` hors d'un depot sort en 128 avec un
    # stdout VIDE (mesure) -- soit exactement ce que rend un depot propre. Une
    # commande qui ECHOUE devenait donc « aucun fichier suivi, tout va bien ».
    #
    # Et `git log --all --full-history` sur un clone SUPERFICIEL ne voit qu'un
    # commit (mesure : 1 contre 66 sur ce depot). Un secret present dans
    # l'historique plus ancien ne serait pas trouve, sans un mot. Le workflow CI
    # fixe deja fetch-depth: 0 pour cette raison precise, et son propre
    # commentaire admet la limite -- « teste une fois avant de pousser, jamais
    # apres ». Rien ne verifiait que ce reglage reste. Maintenant si.
    #
    # Aucun des deux ne BLOQUE : ne pas pouvoir verifier n'est pas la preuve
    # d'une fuite. Mais c'est DIT, au lieu d'etre compte comme un succes.
    try:
        proc_suivis = subprocess.run(
            ["git", "ls-files"], cwd=RACINE, capture_output=True, text=True, timeout=15
        )
        suivis = proc_suivis.stdout.splitlines()
        if proc_suivis.returncode != 0:
            alerte(
                "git",
                "`git ls-files` a echoue (code %d : %s) -- impossible de verifier que "
                "le fichier scelle n'est pas suivi. Un stdout vide est indistinguable "
                "d'un depot propre, donc ce controle n'a rien prouve ici."
                % (proc_suivis.returncode, (proc_suivis.stderr or "").strip()[:120]),
            )
        superficiel = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=RACINE, capture_output=True, text=True, timeout=15,
        )
        if superficiel.stdout.strip() == "true":
            alerte(
                "git",
                "depot SUPERFICIEL (clone --depth) -- `git log --all --full-history` "
                "ne voit qu'une partie de l'historique, donc le controle "
                "« secret jamais commite » est AVEUGLE ici. En CI, actions/checkout "
                "doit garder fetch-depth: 0.",
            )
    except Exception as exc:
        alerte("git", "impossible de lister les fichiers suivis (%s)" % exc)
        return
    if any(f == ".env.hackathon" or f.endswith("/.env.hackathon") for f in suivis):
        bloque(
            ".env.hackathon",
            "🔴 TRACKÉ PAR GIT — fuite de clé API en puissance. "
            "git rm --cached .env.hackathon IMMÉDIATEMENT, ne pas pousser.",
        )

    # 🔴 AJOUTÉ le 25/08 : `git ls-files` ne voit que l'état ACTUEL de
    # l'index. Un fichier ajouté par erreur puis retiré avec
    # `git rm --cached` disparaît de `git ls-files` mais RESTE dans
    # l'historique — récupérable par quiconque clone le dépôt. C'est la
    # raison pour laquelle un scan de secrets doit lire l'historique
    # complet ; ce contrôle en fait la version minimale, pour un seul nom
    # de fichier connu et sans dépendance externe.
    try:
        historique = subprocess.run(
            ["git", "log", "--all", "--full-history", "--oneline", "--", ".env.hackathon"],
            cwd=RACINE, capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except Exception as exc:
        alerte("git", "impossible de relire l'historique (%s)" % exc)
        historique = ""
    if historique:
        bloque(
            ".env.hackathon",
            "🔴 PRÉSENT DANS L'HISTORIQUE GIT (même retiré depuis) — "
            "récupérable par quiconque clone le dépôt. Commit(s) concerné(s) : "
            "%s. Ne suffit pas de le retirer de l'index ; il faut réécrire "
            "l'historique (filter-repo) ou révoquer la clé si déjà poussé."
            % historique.replace("\n", " / "),
        )

    # 🔴 AJOUTÉ le 25/08 en comparant ce script à un autre, plus mature :
    # ne pas être suivi par git protège contre
    # une FUITE (poussée sur GitHub), mais ne dit RIEN sur une modification
    # purement locale, jamais commitée — exactement le trou qu'un contrôle par
    # hachage du contenu comble ailleurs. "Intouché
    # même par accident" veut dire intouché tout court, pas seulement "pas
    # poussé". Donc : hash au premier passage, comparaison ensuite.
    fichier_scelle = os.path.join(RACINE, ".env.hackathon")
    if os.path.exists(fichier_scelle):
        empreinte_actuelle = hashlib.sha256(open(fichier_scelle, "rb").read()).hexdigest()
        registre = os.path.join(RACINE, ".garde_fou_scelles.json")
        registre_existait = os.path.exists(registre)
        connues = {}
        if os.path.exists(registre):
            try:
                connues = json.loads(open(registre, encoding="utf-8").read())
            except Exception:
                alerte(".garde_fou_scelles.json", "illisible — registre des empreintes recréé.")
        empreinte_connue = connues.get(".env.hackathon")
        if empreinte_connue is None:
            connues[".env.hackathon"] = empreinte_actuelle
            # ECRITURE FERMEE EXPLICITEMENT. Corrige le 28/08/2026 au soir, en
            # lisant les ResourceWarning du journal de CI. Ces registres sont la
            # LIGNE DE BASE qui detecte l'alteration d'un fichier scelle. Une
            # ecriture non fermee compte sur le ramassage de CPython pour etre
            # videe sur le disque : ca marche presque toujours, et « presque » ne
            # convient pas pour la piece qui prouve qu'un fichier n'a pas bouge.
            # Un registre tronque se fait RECREER quelques lignes plus haut --
            # donc une alteration passerait pour un premier scellement.
            with open(registre, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(connues, indent=2))
            alerte(".env.hackathon", _message_premier_scelle(
                registre_existait, empreinte_actuelle))
        elif empreinte_connue != empreinte_actuelle:
            bloque(
                ".env.hackathon",
                "🔴 A CHANGÉ DEPUIS SA PREMIÈRE LECTURE — fichier scellé jusqu'au "
                "kickoff du 28/08. Si c'est toi qui l'as modifié volontairement "
                "(ex. rotation de clé), signale-le à l'opérateur ; sinon ne touche à rien "
                "de plus et préviens-le immédiatement.",
            )


# ── CONTRÔLE 3 : LE REFUS LIVE-TRADING EXISTE ENCORE DANS config.py ────────
# Le write-up (submission/Hindsight_Alpha_Writeup.docx) AFFIRME : "Paper
# trading only, hard-enforced in config.py — refuses to run if
# ALPACA_LIVE_TRADE is set truthy." Un juge peut vérifier cette phrase en
# lisant le code. Ce contrôle vérifie mécaniquement que l'affirmation reste
# vraie — pas que le code n'a jamais changé, juste que le refus existe
# encore sous une forme reconnaissable. Si tu as sciemment reformulé ce
# garde-fou dans config.py, adapte les motifs ci-dessous, ne les supprime
# pas pour faire taire l'alerte.
def controle_garde_live_trading() -> None:
    chemin = os.path.join(RACINE, "config.py")
    if not os.path.exists(chemin):
        bloque("config.py", "ABSENT — impossible de vérifier le refus live-trading.")
        return
    src = open(chemin, encoding="utf-8").read()
    if "ALPACA_LIVE_TRADE" not in src:
        bloque("config.py", "ne lit plus ALPACA_LIVE_TRADE — refus live-trading disparu ?")
        return
    if not re.search(r"sys\.exit\(", src):
        bloque(
            "config.py",
            "lit ALPACA_LIVE_TRADE mais aucun sys.exit(...) trouvé — "
            "le refus pourrait n'être plus qu'un avertissement.",
        )

    # ══ RENFORCÉ le 27/08/2026 — ce contrôle ne mordait PAS ═══════════════════
    #
    # Les deux vérifications ci-dessus cherchent des CHAÎNES DE CARACTÈRES :
    # « ALPACA_LIVE_TRADE » quelque part dans le fichier, et « sys.exit( »
    # quelque part dans le fichier. Mesuré ce jour-là, par mutation d'une copie
    # du dépôt :
    #
    #   - bloc `if not PAPER: sys.exit(...)` entièrement supprimé
    #       -> garde_fou.py : code de sortie 0, « rien de bloquant »
    #          (le sys.exit( du contrôle d'identifiants suffisait)
    #   - `env.pop("ALPACA_LIVE_TRADE", None)` supprimé de cli_env()
    #       -> garde_fou.py : code de sortie 0
    #
    # La seconde est la PROTECTION RÉELLE : le CLI ne peut pas voir une variable
    # absente de son environnement, quelle que soit sa graphie. Le refus de
    # démarrer n'est que le diagnostic. Ce contrôle ne vérifiait donc ni l'une
    # ni l'autre — il vérifiait que deux mots figuraient dans un fichier.
    #
    # La suite de tests, elle, attrapait les deux (15 et 6 échecs). Ce n'est pas
    # une raison de laisser ici un contrôle décoratif : c'est CE script que le
    # hook de commit et la CI lancent sous le nom « garde live-trading », et
    # CLAUDE.md le présente comme le mécanisme. Un contrôle qui n'attrape pas ce
    # qu'il annonce est pire qu'un contrôle absent — il rassure.
    #
    # On vérifie donc le COMPORTEMENT, dans un sous-processus, sans réseau :
    # des identifiants factices sont injectés parce que require_credentials()
    # sort sur des clés manquantes AVANT d'atteindre le test paper/live — en CI
    # il n'y a pas de .env, et sans cette injection le contrôle passerait pour
    # la mauvaise raison.
    env_test = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", RACINE),
        "ALPACA_API_KEY": "cle-factice-garde-fou",
        "ALPACA_SECRET_KEY": "secret-factice-garde-fou",
        "ALPACA_LIVE_TRADE": "true",
    }

    def _sonde(code: str):
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=RACINE, env=env_test, capture_output=True, text=True, timeout=30,
        )

    try:
        refus = _sonde("import config; config.require_credentials(); print('AUCUN REFUS')")
        fuite = _sonde(
            "import config; print('PRESENT' if 'ALPACA_LIVE_TRADE' in config.cli_env() "
            "else 'ABSENT')"
        )
    except Exception as exc:
        # Ne pas conclure « tout va bien » parce que la sonde n'a pas pu tourner.
        alerte(
            "config.py",
            "le refus live-trading n'a PAS pu être vérifié par comportement (%s: %s) — "
            "seules les vérifications textuelles, beaucoup plus faibles, ont tourné."
            % (type(exc).__name__, exc),
        )
        return

    if refus.returncode == 0 or "AUCUN REFUS" in refus.stdout:
        bloque(
            "config.py",
            "avec ALPACA_LIVE_TRADE=true, require_credentials() ne refuse PAS de "
            "démarrer — le garde paper-uniquement est tombé.",
        )
    if "ABSENT" not in fuite.stdout:
        bloque(
            "config.py",
            "cli_env() laisse ALPACA_LIVE_TRADE atteindre le CLI Alpaca "
            "(sortie: %r) — c'est la protection RÉELLE du paper-uniquement, pas "
            "le message de refus." % (fuite.stdout.strip() or fuite.stderr.strip()[:120]),
        )


# ── CONTRÔLE 4 : LES CHIFFRES SANS SOURCE MÉCANIQUE POSSIBLE ───────────────
# Née de la même soirée du 25/08 que le contrôle 5 ci-dessous, mais pour la
# SEULE valeur qui n'a structurellement AUCUNE source de vérité dans ce
# dépôt : le nombre d'équipes inscrites au hackathon vit sur lablab.ai, pas
# dans un fichier ici. Reste donc une liste noire — la seule chose qui a du
# sens pour une donnée que ce script ne peut, par construction, jamais
# recalculer lui-même.
MOTIFS_PERIMES = [
    ("442", "ancien nombre d'équipes inscrites (remplacé par 546 le 25/08, "
             "puis par 975 le 29/08 — voir l'alerte dédiée plus bas, aucune "
             "source mécanique possible pour ce chiffre précis)", None),
    # AJOUTÉ le 29/08/2026 après vérification à la main sur lablab.ai, quand
    # le deck citait encore un nombre d'équipes.
    #
    # CE N'EST PLUS LE CAS depuis le 29/08 au soir : la diapo qui situait le
    # projet parmi les autres soumissions a été retirée sur décision de Spap,
    # et PLUS AUCUN livrable ne cite de nombre d'équipes ni de concurrent.
    # Ces deux motifs restent donc comme fil-piège : ils ne bloquent rien
    # aujourd'hui, et bloqueront le jour où l'un de ces chiffres reviendrait
    # sans source.
    #
    # L'EXEMPTION reste elle aussi, avec sa raison d'être : un chiffre périmé
    # peut légitimement être cité comme REPÈRE HISTORIQUE, précédé de
    # « up from ». Le champ est exercé par test_agent.py sur un texte
    # fabriqué, pas sur une phrase du dossier — c'est ce qui lui permet de
    # survivre à la disparition de cette phrase.
    ("546", "nombre d'équipes inscrites au 25/08 — mesuré à ~975 le 29/08 "
             "sur le tableau de bord live de lablab.ai. Il ne peut plus être "
             "cité comme chiffre COURANT ; comme repère historique il doit "
             "être précédé de « up from ».", r"up from\s*$"),
]

FICHIERS_TEXTE_LIVRABLES = [
    "README.md",
    os.path.join("submission", "Video_Script.md"),
]
FICHIERS_DOCX_LIVRABLES = [os.path.join("submission", "Hindsight_Alpha_Writeup.docx")]
FICHIERS_PPTX_LIVRABLES = [os.path.join("submission", "Hindsight_Alpha_Deck.pptx")]


def _texte_docx(chemin: str) -> str:
    with zipfile.ZipFile(chemin) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    return re.sub(r"<[^>]+>", " ", xml)


def _texte_pptx(chemin: str) -> str:
    morceaux = []
    with zipfile.ZipFile(chemin) as z:
        for nom in z.namelist():
            if re.match(r"ppt/slides/slide\d+\.xml$", nom):
                xml = z.read(nom).decode("utf-8", errors="replace")
                morceaux.append("".join(re.findall(r"<a:t>(.*?)</a:t>", xml)))
    return " ".join(morceaux)


def _charger_textes_livrables() -> dict[str, str]:
    """Point d'entrée UNIQUE pour lire le texte des 4 livrables destinés au
    jury. Partagé entre le contrôle 4 (liste noire) et le contrôle 5
    (source de vérité mécanique) — un seul endroit qui sait comment
    extraire le texte d'un .md/.docx/.pptx, pas deux copies qui risquent
    de diverger."""
    textes: dict[str, str] = {}
    for rel in FICHIERS_TEXTE_LIVRABLES:
        chemin = os.path.join(RACINE, rel)
        if os.path.exists(chemin):
            textes[rel] = open(chemin, encoding="utf-8", errors="replace").read()
    for rel in FICHIERS_DOCX_LIVRABLES:
        chemin = os.path.join(RACINE, rel)
        if os.path.exists(chemin):
            try:
                textes[rel] = _texte_docx(chemin)
            except Exception as exc:
                alerte(rel, "illisible pour le contrôle (%s)" % exc)
    for rel in FICHIERS_PPTX_LIVRABLES:
        chemin = os.path.join(RACINE, rel)
        if os.path.exists(chemin):
            try:
                textes[rel] = _texte_pptx(chemin)
            except Exception as exc:
                alerte(rel, "illisible pour le contrôle (%s)" % exc)
    return textes


def controle_chiffres_perimes() -> None:
    # 🔴 CORRIGÉ le 25/08 en revue croisée multi-agents avant commit : ce
    # contrôle utilisait `texte.find(motif)`, un simple sous-chaîne — un
    # futur "4420 €" ou "44,2%" aurait déclenché à tort sur le motif "442"
    # (bug jamais atteint pour de vrai aujourd'hui, aucun de ces textes ne
    # contient un tel nombre, mais une vraie mine dormante). Même idiome que
    # le contrôle du nombre d'équipes plus bas : `(?<!\d)...(?!\d)` refuse de
    # matcher au milieu d'un AUTRE nombre, sans exiger un vrai espace.
    textes = _charger_textes_livrables()
    for rel, texte in textes.items():
        for motif, raison, exemption in MOTIFS_PERIMES:
            m = re.search(r"(?<!\d)" + re.escape(motif) + r"(?!\d)", texte)
            if not m:
                continue
            pos = m.start()
            contexte_avant = texte[max(0, pos - 40):pos]
            if exemption and re.search(exemption, contexte_avant, re.I):
                continue
            bloque(rel, "CHIFFRE PÉRIMÉ « %s » — %s" % (motif, raison))

    # Alerte non bloquante : rappelle qu'un chiffre "vivant" (nombre
    # d'équipes) ne peut pas être vérifié mécaniquement contre lablab.ai
    # depuis ce script.
    #
    # 🔴 CORRIGÉ dans la foulée, trouvé en testant ce script pour de vrai
    # (pas supposé bon) : `\b` avant `\d` échoue quand le chiffre est collé
    # au mot précédent SANS espace dans le XML source du pptx (callout box
    # séparé du texte qui suit, ex. "assumed546teams" une fois les runs
    # concaténés) — deux mots-caractères adjacents ("d" et "5") ne forment
    # jamais de frontière \b. `(?<!\d)` à la place : refuse seulement de
    # matcher au milieu d'un AUTRE nombre, sans exiger un vrai espace.
    for rel, texte in textes.items():
        if re.search(r"(?<!\d)\d{2,4}\s*(équipes|teams)\b", texte, re.I):
            alerte(
                rel,
                "cite un nombre d'équipes inscrites — vérifier à la main sur "
                "lablab.ai avant la soumission finale, ce script ne peut pas "
                "savoir si le chiffre a encore bougé.",
            )


# ── CONTRÔLE 5 : SOURCE DE VÉRITÉ MÉCANIQUE, PAS UNE LISTE NOIRE ──────────
# Demandé explicitement le 25/08 : une liste noire de chaînes déjà fausses
# (contrôle 4 ci-dessus) ne rattrape que la RÉCIDIVE d'une erreur déjà vue
# une fois. Elle ne dirait RIEN le jour où `BACKTEST_RESULTS.md` change
# (nouveau run de backtest, nouveau symbole vetté) et qu'un livrable n'est
# pas mis à jour en conséquence. Le point mort se comble en RÉGÉNÉRANT
# depuis la source et en comparant, plutôt qu'en mémorisant les erreurs
# passées.
#
# Ce contrôle fait ça pour les 4 catégories de chiffres qui ONT une vraie
# source mécanique dans ce dépôt :
#   1. plage de taux de succès / concentration / nombre de trades — calculée
#      à partir de BACKTEST_RESULTS.md (les symboles "propres", vetté =
#      la fenêtre gagnante rapportée par le verdict hindsight_guard)
#   2. nombre de leaks — compté dans le même fichier
#   3. univers actuel de symboles — lu depuis DEFAULT_UNIVERSE dans agent.py
#   4. seuils de risque cités avec leur nom de constante entre backticks
#      (`MAX_SECTOR_EXPOSURE_PCT`, etc.) — comparés à leur vraie valeur
#      dans risk_gates.py / vol_strategy.py
#
# Le nombre d'équipes inscrites (ci-dessus) reste volontairement hors de ce
# contrôle : aucune source mécanique n'existe pour lui dans ce dépôt.


def _parse_backtest_results() -> dict | None:
    """Relit BACKTEST_RESULTS.md et calcule, pour chaque symbole, sa fenêtre
    "vettée" (le gagnant plein historique rapporté par le verdict
    hindsight_guard) avec son taux de succès, sa concentration et son
    nombre de trades à CETTE fenêtre précise — pas la meilleure ligne du
    tableau, la ligne que l'agent tradrait réellement aujourd'hui."""
    chemin = os.path.join(RACINE, "BACKTEST_RESULTS.md")
    if not os.path.exists(chemin):
        return None
    texte = open(chemin, encoding="utf-8").read()
    sections = list(re.finditer(r"^## (\w+) \(", texte, re.M))
    resultat = {}
    for i, m in enumerate(sections):
        symbole = m.group(1)
        debut = m.end()
        fin = sections[i + 1].start() if i + 1 < len(sections) else len(texte)
        bloc = texte[debut:fin]

        verdict = re.search(
            # ELARGI le 27/08 : le rapport ecrit desormais TROIS verdicts et
            # non deux -- « NO EDGE » a ete separe de « LEAK DETECTED », parce
            # qu'un symbole ou rien ne franchit le seuil sur aucune des deux
            # fenetres n'a pas fui, il n'a simplement pas d'edge.
            r"hindsight_guard verdict.*?:\*\*\s*"
            r"(agrees|LEAK DETECTED|NO EDGE|CANNOT CONCLUDE).*?"
            r"full-window winner:\s*(\d+)\s*days"
            # AJOUTE le 27/08 : la fenetre IN-SAMPLE, jusque-la ignoree du
            # parseur alors que DEUX livrables la citent nommement.
            r"(?:,\s*in-sample winner:\s*(\d+)\s*days)?",
            bloc,
        )
        if not verdict:
            # CORRIGE le 27/08 : c'etait un `continue` NU. Une section de
            # symbole trouvee mais dont le verdict ne se lit pas sortait de
            # TOUS les recoupements de livrables -- plages de concentration,
            # nombres de trades, fenetres citees, statut de fuite -- sans une
            # ligne. Le garde-fou restait vert en ayant cesse de verifier ce
            # symbole.
            #
            # Le cas vient de se produire : elargir le rapport a trois
            # verdicts a casse ce motif. Il a ete rattrape parce qu'un test le
            # cherchait, pas parce que le script l'a dit.
            #
            # « Je n'ai pas compris » n'est pas « il n'y a rien » -- le meme
            # argument que list_positions() tient dans alpaca_cli.py.
            alerte("BACKTEST_RESULTS.md",
                   "section %s trouvee, mais son verdict hindsight_guard est "
                   "ILLISIBLE pour ce parseur. Ce symbole sort de TOUS les "
                   "recoupements de livrables (plages, nombres de trades, "
                   "fenetres citees, statut de fuite) : ni confirme, ni "
                   "infirme. Verifier le libelle du verdict dans le rapport."
                   % symbole)
            continue
        leaked = verdict.group(1) == "LEAK DETECTED"
        fenetre = int(verdict.group(2))
        fenetre_in_sample = int(verdict.group(3)) if verdict.group(3) else None

        ligne = re.search(
            r"\|\s*" + str(fenetre) + r"\s*\|\s*(\d+)/\d+\s*\|[^|]*\|[^|]*\|\s*([\d.]+)%\s*\|",
            bloc,
        )
        if not ligne:
            continue
        trade_days = int(ligne.group(1))
        win_rate = float(ligne.group(2))

        concentrations = dict(
            (int(d), float(v)) for d, v in re.findall(r"(\d+)d:\s*\*\*([\d.]+)%\*\*", bloc)
        )
        concentration = concentrations.get(fenetre)

        resultat[symbole] = {
            "leaked": leaked,
            # Le verdict COMPLET, ajoute le 27/08 : `leaked` est desormais
            # strictement « LEAK DETECTED », et il existe deux autres facons
            # de ne pas etre « agrees ». Collapser les trois en un booleen
            # est exactement la confusion corrigee dans hindsight_guard le
            # meme jour.
            "verdict": verdict.group(1),
            "fenetre": fenetre,
            "fenetre_in_sample": fenetre_in_sample,
            "trade_days": trade_days,
            "win_rate": win_rate,
            "concentration": concentration,
        }
    return resultat or None


def _parse_strategy_comparison() -> dict | None:
    """Relit STRATEGY_COMPARISON.md pour le Sharpe in-sample vetté de
    vol_strategy, symbole par symbole (colonne 4 du tableau principal)."""
    chemin = os.path.join(RACINE, "STRATEGY_COMPARISON.md")
    if not os.path.exists(chemin):
        return None
    texte = open(chemin, encoding="utf-8").read()
    resultat = {}
    # CORRIGE le 27/08/2026. Le motif etait `([\d.]+)`, qui ne peut matcher ni
    # un Sharpe NEGATIF ni un `nan`. Mesure sur quatre tableaux fabriques :
    #
    #     tous positifs      -> ['GLD', 'SPY']
    #     un Sharpe NEGATIF  -> ['GLD']   SPY disparu EN SILENCE
    #     un Sharpe NaN      -> ['GLD']   SPY disparu EN SILENCE
    #     tous negatifs      -> None      les deux disparus
    #
    # Un Sharpe in-sample negatif n'est pas une anomalie ici : c'est
    # L'HISTOIRE D'ORIGINE du projet -- « The in-sample score was negative for
    # every candidate » (hindsight_guard.py). Et depuis le correctif de _sharpe
    # du meme jour, `nan` est une valeur legitime du rapport.
    #
    # Les deux directions d'echec etaient silencieuses :
    #   - un symbole qui disparait -> son Sharpe n'est plus une reference
    #     connue, donc une citation LEGITIME de ce chiffre dans un livrable
    #     serait BLOQUEE comme inconnue (faux positif) ;
    #   - tous qui disparaissent -> `sharpes_valides` est vide et le controle
    #     du Sharpe est saute entierement (faux negatif).
    for m in re.finditer(
        # ELARGI le 27/08 : la cellule de verdict porte desormais QUATRE valeurs
        # et non deux. Sans cet elargissement, une ligne « no edge » ou
        # « unscored » disparaissait EN SILENCE -- la panne exacte decrite
        # ci-dessus pour la colonne Sharpe, une colonne plus loin.
        r"\|\s*(\w+)\s*\|\s*\d+d\s*\|\s*(yes|\*\*LEAK\*\*|no edge|unscored)\s*\|"
        r"\s*(-?[\d.]+|[Nn]a[Nn])\s*\|", texte
    ):
        symbole, agrees, brut = m.group(1), m.group(2), m.group(3)
        try:
            sharpe = float(brut)
        except ValueError:
            continue
        resultat[symbole] = {"leaked": agrees == "**LEAK**",
                             "verdict": agrees, "sharpe": sharpe}

    if not resultat:
        # Le fichier EXISTE mais rien n'en a ete tire : c'est un changement de
        # format, pas une absence. Le dire, au lieu de rendre None comme si le
        # fichier n'etait pas la.
        alerte(
            "STRATEGY_COMPARISON.md",
            "present mais AUCUNE ligne de tableau n'a pu etre lue -- le format a "
            "change ? Le controle du Sharpe cite dans les livrables est sans effet "
            "tant que ce fichier n'est pas relisible.",
        )
        return None
    return resultat


def _parse_univers_actuel() -> list | None:
    """Lit DEFAULT_UNIVERSE directement dans agent.py — la vraie liste de
    symboles que l'agent trade aujourd'hui, pas une chaîne recopiée à la
    main dans chaque livrable."""
    chemin = os.path.join(RACINE, "agent.py")
    if not os.path.exists(chemin):
        return None
    src = open(chemin, encoding="utf-8").read()
    m = re.search(r'DEFAULT_UNIVERSE\s*=\s*\[([^\]]+)\]', src)
    symboles = (re.findall(r'"(\w+)"', m.group(1)) or
                re.findall(r"'(\w+)'", m.group(1))) if m else []
    if not symboles:
        # AJOUTE le 27/08/2026 : c'etait `return None`, muet. Mesure -- ecrire
        # DEFAULT_UNIVERSE sous une forme que ce motif ne lit pas (par exemple
        # `list(map(str.upper, (...)))`, un refactor parfaitement legitime) fait
        # DISPARAITRE le croisement de l'univers dans les livrables : code de
        # sortie 0, pas un mot.
        #
        # Ne pas pouvoir lire la reference n'est pas la preuve que les livrables
        # sont justes. On le dit.
        alerte(
            "agent.py",
            "DEFAULT_UNIVERSE n'a pas pu etre lu (forme inattendue ?) -- le "
            "croisement de l'univers cite dans les livrables est SANS EFFET tant "
            "que cette liste n'est pas relisible.",
        )
        return None
    return symboles


SEUILS_RISQUE = [
    ("MAX_RISK_PCT_PER_TRADE", "risk_gates.py"),
    ("MAX_TOTAL_RISK_PCT", "risk_gates.py"),
    ("MAX_SECTOR_EXPOSURE_PCT", "risk_gates.py"),
    ("WEEKLY_LOSS_LOCK_PCT", "risk_gates.py"),
    ("MAX_OPEN_POSITIONS", "risk_gates.py"),
    ("MAX_CONSECUTIVE_LOSSES", "risk_gates.py"),
    ("CHEAP_VOL_PERCENTILE", "vol_strategy.py"),
    # 🔴 AJOUTÉ le 25/08, trouvé en revue croisée multi-agents (confiance 70,
    # pas corrigé sur le coup, comblé ici en suite directe) : les 7 seuils
    # ci-dessus sont les seuls jamais couverts, alors que CLAUDE.md liste
    # HUIT constantes non négociables — HEARTBEAT_SECONDS manquait parce
    # qu'elle vit dans monitor_exits.py, pas risk_gates.py/vol_strategy.py
    # comme les autres. Même mécanique de lecture (`_parse_seuils_risque`
    # ne fait aucune hypothèse sur le fichier), donc l'ajouter suffit.
    ("HEARTBEAT_SECONDS", "monitor_exits.py"),
]


def _parse_seuils_risque() -> dict:
    """Extrait la vraie valeur actuelle de chaque constante de risque
    directement depuis le code — jamais importé (risk_gates.py a des effets
    de bord au chargement), toujours par lecture de texte brute."""
    valeurs = {}
    illisibles = []
    for nom, fichier in SEUILS_RISQUE:
        chemin = os.path.join(RACINE, fichier)
        if not os.path.exists(chemin):
            illisibles.append("%s (%s absent)" % (nom, fichier))
            continue
        src = open(chemin, encoding="utf-8").read()
        # RESSERRE le 27/08/2026. Le motif etait `([\d.]+)` SANS ancre de fin :
        # il capturait le premier nombre venu et s'arretait la. Mesure sur cinq
        # formes plausibles :
        #
        #     MAX_TOTAL_RISK_PCT = 0.03    # commentaire  -> 0.03  correct
        #     MAX_TOTAL_RISK_PCT = 3 / 100               -> 3.0   au lieu de 0.03
        #     MAX_SECTOR_EXPOSURE_PCT = 1.5 / 100        -> 1.5   au lieu de 0.015
        #     MAX_CONSECUTIVE_LOSSES = 6 // 2            -> 6.0   au lieu de 3
        #
        # Ce n'est pas un saut silencieux, c'est une MAUVAISE LECTURE : le
        # controle valide ensuite les livrables contre une valeur de reference
        # fausse. Le chiffre VRAI serait signale comme erronne, et le chiffre
        # faux passerait.
        #
        # On exige donc que le nombre soit TOUTE la partie droite (un
        # commentaire de fin de ligne reste tolere, c'est la forme du fichier).
        # Toute autre forme est declaree illisible et nommee, plutot que
        # devinee.
        m = re.search(r"^%s\s*=\s*([\d.]+)\s*(?:#.*)?$" % re.escape(nom), src, re.M)
        if m:
            valeurs[nom] = float(m.group(1))
        else:
            illisibles.append("%s (dans %s)" % (nom, fichier))

    # AJOUTE le 27/08/2026 : les seuils introuvables etaient simplement SAUTES.
    # Mesure -- reecrire `MAX_TOTAL_RISK_PCT = 0.03` en `MAX_TOTAL_RISK_PCT =
    # 3 / 100`, un refactor parfaitement legitime que ce motif ne lit pas, fait
    # disparaitre ce seuil du controle des chiffres cites dans les livrables :
    # code de sortie 0, pas un mot. Le livrable pourrait alors annoncer
    # n'importe quoi pour ce seuil.
    #
    # On ne BLOQUE pas -- une valeur qu'on ne sait pas lire n'est pas une valeur
    # fausse -- mais on nomme precisement ce qui echappe au controle.
    if illisibles:
        alerte(
            "seuils de risque",
            "valeur(s) non lisible(s) depuis le code : %s. Les livrables ne sont "
            "PAS verifies contre ce(s) seuil(s) tant que la forme n'est pas "
            "`NOM = <nombre>` en debut de ligne." % ", ".join(illisibles),
        )
    return valeurs


def _fmt(x: float) -> str:
    """Une seule décimale, comme partout dans les livrables (68.5, pas
    68.50 ni 68.500000000001 issus d'un calcul flottant)."""
    return ("%.1f" % x).rstrip("0").rstrip(".") if x == int(x) else "%.1f" % x


# 🟢 AJOUTÉ le 25/08 en revue croisée avant commit : deux relectures
# indépendantes ont trouvé, chacune à confiance 85, que
# README.md citait 181.6% pour la concentration de XLK — le chiffre de sa
# fenêtre 10j, alors que XLK est jugé sur sa fenêtre 90j vettée (136.7%).
# Le reste du contrôle 5 ci-dessous ne pouvait PAS l'attraper : `propres`
# exclut par construction les symboles en fuite de ses plages mécaniques,
# et XLK — le seul symbole en fuite du projet, celui mis en avant comme
# meilleure démonstration — n'était donc validé par AUCUN contrôle.
#
# Ce correctif ne construit PAS un vérificateur général par-fenêtre pour
# n'importe quelle prose (ç'aurait été un vrai chantier, pas une ligne,
# risqué de reproduire les 3 bugs de proximité regex déjà trouvés en
# construisant le reste du contrôle 5). Portée volontairement plus étroite
# et honnête : les TABLEAUX markdown à la `| SYMBOLE | ... | win rate % |
# ... | concentration % |` (la forme exacte où le bug réel est apparu) —
# repérés par leur ligne d'en-tête (colonnes "win rate" et
# "concentration"/"best 5 days"), puis chaque ligne de données comparée au
# VRAI symbole correspondant, fenêtre vettée comprise, fuite ou pas.
def _lignes_tableau_symboles(texte: str) -> list[dict]:
    lignes = texte.split("\n")
    resultats = []
    i = 0
    while i < len(lignes):
        entete = lignes[i]
        si_entete_valide = (
            entete.strip().startswith("|")
            and re.search(r"win rate", entete, re.I)
            and re.search(r"concentration|best 5|gain from best", entete, re.I)
        )
        if not si_entete_valide:
            i += 1
            continue
        cellules_entete = [c.strip() for c in entete.strip().strip("|").split("|")]
        idx_wr = next((j for j, c in enumerate(cellules_entete) if re.search(r"win rate", c, re.I)), None)
        idx_conc = next(
            (j for j, c in enumerate(cellules_entete)
             if re.search(r"concentration|best 5|gain from best", c, re.I)),
            None,
        )
        # AJOUTE le 27/08 : la colonne du nombre de transactions, jamais
        # croisee jusque-la. En-tete reel : « Trades (of ~657 bars) ».
        idx_trades = next(
            (j for j, c in enumerate(cellules_entete)
             if re.search(r"\btrades?\b", c, re.I)),
            None,
        )
        # ligne suivante = séparateur markdown (---|---|---), on la saute.
        j = i + 2
        while j < len(lignes) and lignes[j].strip().startswith("|"):
            cellules = [c.strip() for c in lignes[j].strip().strip("|").split("|")]
            if len(cellules) > max(x for x in (idx_wr, idx_conc) if x is not None):
                ticker = re.match(r"\*{0,2}([A-Z]{2,5})\*{0,2}$", cellules[0])
                if ticker:
                    resultats.append({
                        "ligne_brute": lignes[j],
                        "symbole": ticker.group(1),
                        "trades_cell": (cellules[idx_trades]
                                        if idx_trades is not None
                                        and idx_trades < len(cellules) else ""),
                        "win_rate_cell": cellules[idx_wr] if idx_wr is not None else "",
                        "concentration_cell": cellules[idx_conc] if idx_conc is not None else "",
                    })
            j += 1
        i = j
    return resultats


def controle_source_de_verite() -> None:
    backtest = _parse_backtest_results()
    if backtest is None:
        alerte("BACKTEST_RESULTS.md", "introuvable ou illisible — contrôle 5 sans effet.")
        return

    # CORRIGE le 27/08. « propres » etait defini comme « pas une fuite », donc
    # un symbole NO EDGE ou CANNOT CONCLUDE y serait tombe et aurait ete
    # recoupe comme un symbole que l'agent trade. Il n'y a que « agrees » qui
    # veuille dire ca.
    propres = {s: d for s, d in backtest.items()
               if d.get("verdict", "agrees") == "agrees"}
    fuites = {s: d for s, d in backtest.items() if d["leaked"]}

    # Et le troisieme groupe, qui n'existait pas : ni propre, ni fuite. Le
    # nommer plutot que de le laisser tomber entre les deux -- c'est le motif
    # que cette journee a poursuivi partout ailleurs.
    for symbole, d in sorted(backtest.items()):
        if symbole not in propres and symbole not in fuites:
            alerte("BACKTEST_RESULTS.md",
                   "%s porte le verdict « %s » : ni « agrees » ni « LEAK "
                   "DETECTED ». Il est donc exclu des DEUX groupes de "
                   "recoupement -- ses chiffres ne sont ni confirmes ni "
                   "infirmes ici." % (symbole, d.get("verdict", "?")))
    if not propres:
        alerte("BACKTEST_RESULTS.md", "aucun symbole propre trouvé — contrôle 5 sans effet.")
        return

    plage_succes = (
        min(d["win_rate"] for d in propres.values()),
        max(d["win_rate"] for d in propres.values()),
    )
    concentrations_connues = [d["concentration"] for d in propres.values() if d["concentration"] is not None]
    plage_concentration = (min(concentrations_connues), max(concentrations_connues)) if concentrations_connues else None
    plage_trades = (
        min(d["trade_days"] for d in propres.values()),
        max(d["trade_days"] for d in propres.values()),
    )
    nb_leaks = len(fuites)

    comparaison = _parse_strategy_comparison() or {}
    # AJOUTE le 27/08 : un Sharpe NON FINI (nan) n'est pas une valeur de
    # reference -- on ne peut pas valider une citation contre un chiffre qui
    # n'a pas pu etre calcule. On l'exclut, et on le DIT plutot que de reduire
    # silencieusement l'ensemble de reference (ce qui ferait bloquer a tort une
    # citation legitime d'un AUTRE symbole).
    non_finis = sorted(s for s, d in comparaison.items()
                       if not d["leaked"] and not math.isfinite(d["sharpe"]))
    if non_finis:
        alerte(
            "STRATEGY_COMPARISON.md",
            "Sharpe non fini (nan) pour %s -- ces symboles sortent de l'ensemble "
            "de reference du controle des Sharpes cites. Regenere le fichier : un "
            "nan signale une fenetre que la strategie n'a pas pu noter."
            % ", ".join(non_finis),
        )
    sharpes_valides = {
        round(d["sharpe"], 2) for s, d in comparaison.items()
        if not d["leaked"] and math.isfinite(d["sharpe"])
    }

    univers_actuel = _parse_univers_actuel()
    seuils = _parse_seuils_risque()

    textes = _charger_textes_livrables()

    def plage_correspond(lo: float, hi: float, attendu: tuple) -> bool:
        if attendu is None:
            return True  # rien à comparer, ne pas faire échouer un contrôle sur une donnée absente
        a, b = sorted((round(lo, 1), round(hi, 1)))
        c, d = sorted((round(attendu[0], 1), round(attendu[1], 1)))
        return (a, b) == (c, d)

    RANGE_PCT = re.compile(r"(\d{1,3})[.,](\d)\s*[–\-]\s*(\d{1,3})[.,](\d)\s*%")
    RANGE_TRADES = re.compile(r"(\d{2,3})\s*(?:[–\-]|à|a|to)\s*(\d{2,3})\s*trades", re.I)
    LEAK_COUNT = re.compile(r"(?<!\d)(\d+)\s*leaks?\b", re.I)
    ANCRE_SUCCES = re.compile(r"win rate|taux de succ[eè]s|taux de r[ée]ussite", re.I)
    ANCRE_CONCENTRATION = re.compile(
        r"concentration|best 5|5 best days|5 meilleurs jours|meilleures journ[ée]es", re.I
    )

    for rel, texte in textes.items():
        for m in RANGE_PCT.finditer(texte):
            lo = float("%s.%s" % (m.group(1), m.group(2)))
            hi = float("%s.%s" % (m.group(3), m.group(4)))
            # 🔴 CORRIGÉ DEUX FOIS en testant ce contrôle pour de vrai.
            # D'abord : un `elif` sur une seule fenêtre "avant" faisait
            # retomber une plage déjà validée sur l'autre contrôle, parce
            # que la phrase réelle mentionne les deux stats à la fois.
            # Fixé une première fois en prenant l'ancre la plus PROCHE
            # (avant le nombre) plutôt que la première trouvée.
            # Puis, sur le pptx précisément : ce fix ne regardait QUE le
            # texte AVANT le nombre. Le pptx a une structure "chiffre
            # d'abord, légende ensuite" dans ses encarts (contrairement au
            # README/docx qui sont en prose, légende avant le chiffre) —
            # "45.1–57.1%win rate on..." avec l'ancre APRÈS, pas avant.
            # Cherche donc des deux côtés, distance minimale l'emporte.
            avant = texte[max(0, m.start() - 80):m.start()]
            apres = texte[m.end():m.end() + 60]

            def _distance_min(regex: re.Pattern) -> int:
                d = [len(avant) - x.end() for x in regex.finditer(avant)]
                d += [x.start() for x in regex.finditer(apres)]
                return min(d) if d else None

            d_succes = _distance_min(ANCRE_SUCCES)
            d_concentration = _distance_min(ANCRE_CONCENTRATION)

            if d_succes is None and d_concentration is None:
                continue
            if d_concentration is None or (d_succes is not None and d_succes < d_concentration):
                if not plage_correspond(lo, hi, plage_succes):
                    bloque(
                        rel,
                        "TAUX DE SUCCÈS « %s » ne correspond pas à BACKTEST_RESULTS.md "
                        "(devrait être %s–%s%%, calculé à l'instant sur les symboles propres)."
                        % (m.group(0).strip(), _fmt(plage_succes[0]), _fmt(plage_succes[1])),
                    )
            else:
                if not plage_correspond(lo, hi, plage_concentration):
                    bloque(
                        rel,
                        "CONCENTRATION « %s » ne correspond pas à BACKTEST_RESULTS.md "
                        "(devrait être %s–%s%%, calculé à l'instant sur les symboles propres)."
                        % (m.group(0).strip(), _fmt(plage_concentration[0]), _fmt(plage_concentration[1])),
                    )

        for m in RANGE_TRADES.finditer(texte):
            # 🔴 CORRIGÉ en testant pour de vrai : README dit délibérément
            # "~50-100 trades" (approximation arrondie, marquée par le "~"
            # — pas une citation exacte du 52–102 réel). Bloquer ça serait
            # punir une honnêteté volontaire ("environ", pas "exactement").
            # Exemption : un "~" ou "environ"/"about"/"roughly" juste avant
            # désactive la comparaison stricte pour CE match précis.
            avant = texte[max(0, m.start() - 12):m.start()]
            if re.search(r"~|environ|about|roughly", avant, re.I):
                continue
            lo, hi = int(m.group(1)), int(m.group(2))
            if not plage_correspond(lo, hi, plage_trades):
                bloque(
                    rel,
                    "NOMBRE DE TRADES « %s » ne correspond pas à BACKTEST_RESULTS.md "
                    "(devrait être %d–%d, calculé à l'instant)."
                    % (m.group(0).strip(), plage_trades[0], plage_trades[1]),
                )

        # AJOUTE le 27/08/2026. Deux livrables citent NOMMEMENT les deux
        # fenetres du verdict de fuite :
        #
        #   Writeup : « XLK currently fails hindsight_guard (full-window winner
        #              90d, in-sample winner 10d disagree) »
        #   Deck    : « XLK's full-history winner (90d) disagrees with its
        #              in-sample winner (10d) »
        #
        # Verifie a la main le 27/08 : les deux disent VRAI aujourd'hui (la
        # source donne bien 90 et 10). Mais ces nombres n'etaient relies a rien.
        # Regenerer le backtest et voir XLK basculer sur d'autres fenetres
        # rendrait les deux livrables faux, en silence -- sur la phrase meme qui
        # illustre la revendication centrale du projet.
        #
        # On cherche chaque symbole connu, puis les deux fenetres dans les 200
        # caracteres qui suivent. Les deux formes reelles sont couvertes : le
        # nombre colle au libelle (« winner 90d ») ou entre parentheses
        # (« winner (90d) »).
        # RESSERRE aussitot ecrit : la premiere version cherchait chaque
        # symbole puis les fenetres dans les 200 caracteres SUIVANTS. Elle a
        # produit un FAUX POSITIF sur le depot sain -- « FENETRE PLEINE 90d
        # citee pour XLV » -- parce que le writeup liste l'univers
        # « SPY, GLD, XLK, XLV » puis parle de XLK deux phrases plus loin. Le
        # 90d de XLK etait attribue a XLV.
        #
        # C'est exactement le piege de proximite que les commentaires de ce
        # fichier decrivent ailleurs, et j'y suis tombe. Le bon critere n'est
        # pas « un symbole dans les parages » mais LE SYMBOLE LE PLUS PROCHE
        # AVANT la phrase : c'est celui dont on parle.
        def _symbole_le_plus_proche_avant(position: int) -> str | None:
            avant = texte[max(0, position - 120):position]
            candidats = [
                (sm.start(), sym)
                for sym in backtest
                for sm in re.finditer(r"\b%s\b" % re.escape(sym), avant)
            ]
            return max(candidats)[1] if candidats else None

        for m_full in re.finditer(
                r"full[- ](?:window|history)\s+winner\s*\(?\s*(\d+)\s*d",
                texte, re.I):
            symbole = _symbole_le_plus_proche_avant(m_full.start())
            if symbole is None:
                continue
            attendu = backtest[symbole]
            if int(m_full.group(1)) != attendu["fenetre"]:
                bloque(
                    rel,
                    "FENETRE PLEINE « %sd » citee pour %s, alors que "
                    "BACKTEST_RESULTS.md donne %dd."
                    % (m_full.group(1), symbole, attendu["fenetre"]),
                )

        for m_in in re.finditer(
                r"in-sample\s+winner\s*\(?\s*(\d+)\s*d", texte, re.I):
            symbole = _symbole_le_plus_proche_avant(m_in.start())
            if symbole is None:
                continue
            attendu = backtest[symbole]
            if (attendu.get("fenetre_in_sample") is not None
                    and int(m_in.group(1)) != attendu["fenetre_in_sample"]):
                bloque(
                    rel,
                    "FENETRE IN-SAMPLE « %sd » citee pour %s, alors que "
                    "BACKTEST_RESULTS.md donne %dd."
                    % (m_in.group(1), symbole, attendu["fenetre_in_sample"]),
                )

        for m in LEAK_COUNT.finditer(texte):
            n = int(m.group(1))
            if n != nb_leaks:
                bloque(
                    rel,
                    "NOMBRE DE LEAKS « %s » ne correspond pas à BACKTEST_RESULTS.md "
                    "(%d leak(s) détecté(s) en réalité — %s)."
                    % (m.group(0).strip(), nb_leaks, ", ".join(sorted(fuites)) or "aucun"),
                )

        # Univers actuel : toute liste de 4 tickers séparés par des virgules,
        # sauf si "PREVIOUS" apparaît juste avant (même exemption que le
        # contrôle 4, née du même faux positif le 25/08 — sur la diapo
        # « THE STRATEGY », qui portait alors le rang 5).
        # GENERALISE le 27/08/2026. Ce bloc etait garde par
        # `len(univers_actuel) == 4` et cherchait un motif a exactement QUATRE
        # groupes. Mesure, en mutant DEFAULT_UNIVERSE dans une copie du depot :
        #
        #     4 symboles (differents) -> le controle proteste   🟢
        #     3 symboles              -> SILENCE                🔴
        #     5 symboles              -> SILENCE                🔴
        #
        # Le controle ne fonctionnait donc que pour la taille d'univers du jour.
        # Il disparaissait au moment precis ou il sert : quand l'univers change,
        # c'est-a-dire quand les livrables deviennent faux. Pire encore dans le
        # sens inverse -- code passe a cinq symboles, README en listant encore
        # quatre : le motif aurait cherche des quintuplets et n'aurait pas vu le
        # quadruplet perime.
        #
        # On cherche donc TOUTE suite de tickers separes par des virgules, de
        # deux a six, et on compare les ENSEMBLES. La liste `connus` inclut
        # l'univers courant, pour qu'un ticker nouvellement adopte ne fasse pas
        # sauter la verification en silence.
        if univers_actuel:
            connus = set(univers_actuel) | {"SPY", "GLD", "XLK", "XLV", "QQQ", "IWM"}
            for m in re.finditer(r"\b[A-Z]{2,5}(?:\s*,\s*[A-Z]{2,5}){1,5}\b", texte):
                voisinage = texte[max(0, m.start() - 40):m.start()]
                if re.search(r"PREVIOUS", voisinage, re.I):
                    continue
                trouve = [t.strip() for t in m.group(0).split(",")]
                # Tous doivent etre des tickers du projet : sinon c'est une
                # enumeration quelconque en majuscules, pas l'univers.
                if not all(t in connus for t in trouve):
                    continue
                # RESSERRE le 27/08, apres avoir mesure la premiere version :
                # comparer toute suite de tickers a l'univers produisait TROIS
                # FAUX POSITIFS sur le depot sain, parce que la prose mentionne
                # legitimement des sous-ensembles (« SPY, GLD and XLV pass
                # clean »). Un controle qui crie sur du texte correct est pire
                # que celui qui se taisait : on apprend a l'ignorer.
                #
                # Le signal reel n'est pas « cette liste differe de l'univers »,
                # c'est « cette liste cite un ticker qui N'EST PLUS dans
                # l'univers », ou « cette liste est aussi longue que l'univers
                # sans lui correspondre ». Une mention partielle de tickers tous
                # actuels reste du texte correct.
                perimes = [t for t in trouve if t not in univers_actuel]
                aussi_longue = len(trouve) >= len(univers_actuel)
                if not perimes and not aussi_longue:
                    continue
                if sorted(trouve) != sorted(univers_actuel):
                    bloque(
                        rel,
                        "UNIVERS « %s » ne correspond pas à DEFAULT_UNIVERSE dans agent.py "
                        "(univers actuel réel : %s)." % (", ".join(trouve), ", ".join(univers_actuel)),
                    )

        # Seuils de risque : uniquement là où le nom de la constante est cité
        # entre backticks ET immédiatement suivi (virgule ou parenthèse) par
        # un nombre — ancrage fort, faible risque de faux positif.
        #
        # 🔴 CORRIGÉ en testant pour de vrai : une fenêtre de 40 caractères
        # après le nom était trop large. `MAX_OPEN_POSITIONS` est mentionné
        # une fois SANS nombre juste après ("...positions (`MAX_OPEN_
        # POSITIONS`), a 1%-of-equity per-trade cap...") — la fenêtre de 40
        # caractères attrapait le "1" de la phrase suivante et le comparait
        # à tort à MAX_OPEN_POSITIONS (qui vaut 4). Resserré : le nombre doit
        # suivre IMMÉDIATEMENT le nom (virgule ou parenthèse, espace
        # optionnel), pas n'importe où dans une fenêtre large.
        for nom, valeur_reelle in seuils.items():
            for m in re.finditer(r"`%s`\s*[,(]\s*([\d.]+)" % re.escape(nom), texte):
                nombre = m
                cite = float(nombre.group(1))
                # les pourcentages sont stockés en fraction (0.01) mais cités
                # en % (1) dans la prose — normalise avant de comparer.
                attendu = valeur_reelle * 100 if valeur_reelle < 1 else valeur_reelle
                if abs(cite - attendu) > 0.01:
                    bloque(
                        rel,
                        "`%s` cité comme %s juste après le nom, mais vaut réellement "
                        "%s dans %s." % (nom, nombre.group(1), _fmt(attendu),
                                          dict(SEUILS_RISQUE).get(nom, "?")),
                    )

        # AJOUTE le 27/08 au soir. La regle ci-dessus n'attrape un seuil que
        # sous la forme `NOM`, 3 -- nom de constante entre backticks
        # IMMEDIATEMENT suivi d'un nombre. Mesure sur les livrables reels :
        #
        #     declenchements de cette regle : 3, toutes dans README.md
        #     (MAX_SECTOR_EXPOSURE_PCT, MAX_OPEN_POSITIONS, MAX_CONSECUTIVE_LOSSES)
        #
        #     les MEMES plafonds enonces en PROSE : 9 fois, dans les QUATRE
        #     livrables -- README, script video, write-up, deck
        #
        # Et les deux chiffres les plus mis en avant du dossier -- 1% par
        # trade, 3% au total -- n'etaient recoupes NULLE PART. Doubler
        # MAX_TOTAL_RISK_PCT dans le code ne produisait pas une alerte :
        # verifie sur un clone, memes trois alertes a 3% et a 6%.
        #
        # C'est la these du projet non gardee sur ses propres chiffres. Le
        # controle existait, mais dans une forme que les livrables n'emploient
        # presque jamais.
        #
        # Meme methode que les plages de concentration plus haut : un NOMBRE,
        # puis une ANCRE proche qui dit de quel plafond il s'agit. Sans ancre
        # on ne conclut rien -- un « 3% » isole peut parler d'autre chose.
        for nom_seuil, ancre in (
            ("MAX_RISK_PCT_PER_TRADE",
             r"per[- ]trade|par trade|per position|of equity per"),
            # Ancre RESSERREE : « total » seul attrapait « 82.6% of each clean
            # symbol's TOTAL came from its best 5 days » -- un chiffre de
            # concentration, pas un plafond. Les livrables disent toujours
            # « total premium » ou « total exposure », ou nomment les positions
            # ouvertes. « drawdown » est volontairement absent : le verrou
            # hebdomadaire vaut AUSSI 3% et se cite « 3% drawdown lock », mais
            # c'est une autre constante (WEEKLY_LOSS_LOCK_PCT).
            ("MAX_TOTAL_RISK_PCT",
             r"total\s*(premium|exposure)|au total sur toutes les positions"
             r"|across [Aa][Ll][Ll] open positions"),
            ("MAX_SECTOR_EXPOSURE_PCT", r"sector|secteur"),
            # ETENDU le 27/08 au soir, apres avoir mesure les contextes reels
            # dans les quatre livrables plutot que de deviner des ancres :
            #     « 3% drawdown », « 3% from its recorded starting equity »,
            #     « 3% depuis son equite de depart »
            # « drawdown » distingue ce verrou de MAX_TOTAL_RISK_PCT, qui vaut
            # AUSSI 3% mais se cite « total premium / total exposure ».
            ("WEEKLY_LOSS_LOCK_PCT",
             r"drawdown|starting equity|[ée]quit[ée] de d[ée]part"),
        ):
            valeur_reelle = seuils.get(nom_seuil)
            if valeur_reelle is None:
                continue
            attendu = valeur_reelle * 100 if valeur_reelle < 1 else valeur_reelle
            for m in re.finditer(r"(\d{1,2}(?:[.,]\d)?)\s*%", texte):
                # La fenetre s'arrete au PROCHAIN pourcentage. Mesure : une
                # fenetre fixe de 60 caracteres produisait 5 faux positifs sur
                # des livrables corrects, parce qu'une phrase comme « 1% of
                # equity per trade, 3% total » fait tomber le mot « total »,
                # qui appartient au SECOND chiffre, dans la fenetre du PREMIER.
                # Un plafond annonce juste devenait alors une alerte bloquante,
                # ce qui est la pire facon de rater : un controle qui refuse un
                # dossier correct se fait desactiver.
                suite = texte[m.end():]
                prochain = suite.find("%")
                fenetre = suite[:prochain] if 0 <= prochain < 40 else suite[:40]
                if not re.search(ancre, fenetre, re.I):
                    continue
                cite = float(m.group(1).replace(",", "."))
                if abs(cite - attendu) > 0.01:
                    bloque(
                        rel,
                        "« %s%% » suivi de « %s » ne correspond pas a %s, qui "
                        "vaut %s dans le code. Un livrable annonce un plafond "
                        "de risque que l'agent n'applique pas."
                        % (m.group(1), fenetre.strip()[:28], nom_seuil,
                           _fmt(attendu)),
                    )

        # SEUILS ENTIERS : TENTE PUIS RETIRE le 27/08 au soir, et la trace
        # reste ici parce que l'echec est instructif.
        #
        # MAX_OPEN_POSITIONS (4) et MAX_CONSECUTIVE_LOSSES (3) se citent sans
        # signe %, donc la boucle ci-dessus ne les voit pas. J'ai essaye de les
        # ancrer sur le mot qui suit le nombre. Mesure sur les livrables
        # CORRECTS : 5 bloquants, tous legitimes.
        #
        #     « 3rd concurrent position »        -> un ORDINAL, pas un plafond
        #     « 11 times in a row »              -> l'incident DNS du 25/08
        #     « 2 positions on the same underlying » -> une AUTRE regle
        #     « 2nd or 3rd position shrinks ... »-> encore des ordinaux
        #
        # Un pourcentage porte son unite avec lui ; un entier nu ne dit pas de
        # quoi il parle, et la prose d'un dossier technique est pleine de
        # petits nombres. Aucune ancre courte ne les separe proprement.
        #
        # Ces deux seuils restent couverts par la regle `NOM`, 4 quand le
        # livrable cite la constante entre backticks -- ce que le README fait
        # pour les deux. Le deck et le write-up ne les citent qu'en prose et
        # restent donc non recoupes : c'est une LIMITE CONNUE, ecrite ici
        # plutot que masquee par un controle qui crierait sur du juste.

        # AJOUTE le 27/08. La regle ci-dessus attrape un ticker PERIME cite dans
        # un livrable. Elle n'attrape pas le cas miroir : l'univers a GRANDI et
        # le livrable ne parle toujours que des anciens. Aucune liste n'y est
        # alors fausse -- il en manque une partie, ce qu'aucune comparaison de
        # listes ne peut voir. Un symbole de l'univers cite NULLE PART est le
        # signal exploitable. Alerte et non blocage : un script video n'a pas
        # vocation a nommer chaque symbole.
        if univers_actuel:
            absents = [t for t in univers_actuel
                       if not re.search(r"\b%s\b" % re.escape(t), texte)]
            if absents:
                alerte(
                    rel,
                    "ne mentionne nulle part %s, pourtant dans DEFAULT_UNIVERSE "
                    "(agent.py) — le livrable a-t-il suivi l'ajout ?"
                    % ", ".join(absents),
                )

        for m in re.finditer(r"Sharpe\s+([\d.]+)", texte, re.I):
            valeur = round(float(m.group(1)), 2)
            if sharpes_valides and valeur not in sharpes_valides:
                bloque(
                    rel,
                    "SHARPE « %.2f » ne correspond à aucun Sharpe vetté connu dans "
                    "STRATEGY_COMPARISON.md (valeurs actuelles : %s)."
                    % (valeur, ", ".join("%.2f" % v for v in sorted(sharpes_valides))),
                )

        # Tableaux symbole-par-symbole (win rate + concentration) : vérifiés
        # contre CHAQUE symbole individuellement, fuite ou pas — voir le
        # commentaire au-dessus de _lignes_tableau_symboles pour l'origine.
        for ligne in _lignes_tableau_symboles(texte):
            symbole = ligne["symbole"]
            if symbole not in backtest:
                continue
            attendu = backtest[symbole]
            m_wr = re.search(r"([\d.]+)\s*%", ligne["win_rate_cell"])
            if m_wr:
                cite = float(m_wr.group(1))
                if abs(cite - attendu["win_rate"]) > 0.05:
                    bloque(
                        rel,
                        "WIN RATE « %s%% » pour %s (tableau) ne correspond pas à sa "
                        "fenêtre vettée (%dj) dans BACKTEST_RESULTS.md (devrait être "
                        "%s%%)." % (m_wr.group(1), symbole, attendu["fenetre"], _fmt(attendu["win_rate"])),
                    )
            # AJOUTE le 27/08/2026. Ce bloc comparait le TAUX DE REUSSITE et la
            # CONCENTRATION, pas le STATUT DE FUITE. Mesure : remplacer dans le
            # README la ligne « XLK | 90d | 🛡️ **LEAK — refused live** » par
            # « XLK | 90d | ✅ clean » donnait un garde_fou a CODE 0.
            #
            # C'est la revendication centrale du projet -- « this check finds a
            # genuine disagreement on XLK and refuses it live, every run ». Un
            # livrable pouvait annoncer le contraire de ce que la source
            # mecanique dit, et le controle qui existe pour empecher exactement
            # ca ne regardait pas cette colonne.
            brute = ligne.get("ligne_brute", "")
            dit_fuite = bool(re.search(r"leak|refused", brute, re.I))
            dit_propre = bool(re.search(r"\bclean\b", brute, re.I))
            if attendu["leaked"] and dit_propre and not dit_fuite:
                bloque(
                    rel,
                    "%s est annonce PROPRE dans le tableau, alors que "
                    "BACKTEST_RESULTS.md le donne EN FUITE (fenetre vettee %dj). "
                    "C'est la revendication centrale du projet : elle doit dire "
                    "ce que la source mecanique dit."
                    % (symbole, attendu["fenetre"]),
                )
            elif not attendu["leaked"] and dit_fuite and not dit_propre:
                bloque(
                    rel,
                    "%s est annonce EN FUITE dans le tableau, alors que "
                    "BACKTEST_RESULTS.md le donne propre (fenetre vettee %dj)."
                    % (symbole, attendu["fenetre"]),
                )

            # AJOUTE le 27/08 : mesure, remplacer « 52 » par « 152 » pour XLV
            # dans le README donnait un garde_fou a CODE 0. Le premier entier de
            # la cellule est la valeur -- « 76 (not traded) » se lit bien 76.
            m_tr = re.search(r"(\d+)", ligne.get("trades_cell", ""))
            if m_tr and attendu.get("trade_days") is not None:
                cite_tr = int(m_tr.group(1))
                if cite_tr != attendu["trade_days"]:
                    bloque(
                        rel,
                        "NOMBRE DE TRANSACTIONS « %d » pour %s (tableau) ne "
                        "correspond pas a sa fenetre vettee (%dj) dans "
                        "BACKTEST_RESULTS.md (devrait etre %d)."
                        % (cite_tr, symbole, attendu["fenetre"], attendu["trade_days"]),
                    )

            m_conc = re.search(r"([\d.]+)\s*%", ligne["concentration_cell"])
            if m_conc and attendu["concentration"] is not None:
                cite = float(m_conc.group(1))
                if abs(cite - attendu["concentration"]) > 0.05:
                    bloque(
                        rel,
                        "CONCENTRATION « %s%% » pour %s (tableau) ne correspond pas à "
                        "sa fenêtre vettée (%dj) dans BACKTEST_RESULTS.md (devrait "
                        "être %s%%)." % (m_conc.group(1), symbole, attendu["fenetre"],
                                          _fmt(attendu["concentration"])),
                    )

        # 🔴 AJOUTÉ le 26/08/2026 — le dernier vrai trou de couverture connu
        # du contrôle 5. Le correctif du 25/08 ci-dessus (_lignes_tableau_
        # symboles) ne couvre que la forme TABLEAU markdown. Mais le bug
        # d'ORIGINE qui l'a motivé était une phrase en PROSE, pas un tableau :
        # README.md dit encore aujourd'hui « A concentration share above 100%
        # (XLK's 136.7%) » — une citation individuelle d'un symbole EN FUITE,
        # hors tableau. `plage_concentration`/`plage_succes` ne peuvent QUE
        # comparer une PLAGE construite sur les symboles `propres` : XLK, en
        # fuite, en est exclu par construction — la même exclusion que celle
        # déjà documentée en tête de fichier. Cette phrase-là passerait donc
        # encore inaperçue si son chiffre devenait faux.
        #
        # Portée délibérément étroite pour ne pas rouvrir les 3 bugs de
        # proximité regex déjà trouvés en construisant le reste de ce
        # contrôle : un SEUL pourcentage isolé (pas une plage — déjà couverte
        # par RANGE_PCT plus haut), sa distance au nom du symbole ET à
        # l'ancre win-rate/concentration la plus proche, jamais une supposition
        # sur la position relative. Ignore toute ligne de tableau (déjà
        # couverte par _lignes_tableau_symboles juste au-dessus — éviter un
        # double signalement contradictoire sur la même donnée).
        spans_plages = [(m.start(), m.end()) for m in RANGE_PCT.finditer(texte)]
        UN_SEUL_POURCENT = re.compile(r"(?<![\d.,])(\d{1,3})[.,](\d)\s*%(?!\s*[–\-]\s*\d)")
        candidats_seuls = [
            m for m in UN_SEUL_POURCENT.finditer(texte)
            if not any(a <= m.start() < b for a, b in spans_plages)
        ]

        def _ligne_est_tableau(pos: int) -> bool:
            debut_ligne = texte.rfind("\n", 0, pos) + 1
            fin_ligne = texte.find("\n", pos)
            fin_ligne = fin_ligne if fin_ligne != -1 else len(texte)
            return texte[debut_ligne:fin_ligne].strip().startswith("|")

        for symbole, attendu in fuites.items():
            for sm in re.finditer(r"\b%s\b" % re.escape(symbole), texte):
                # le plus proche pourcentage isolé, tous côtés, distance bornée
                # à 70 caractères (largeur déjà utilisée pour les ancres
                # RANGE_PCT ci-dessus — même ordre de grandeur, même famille
                # de contrôle, pas une nouvelle constante inventée au hasard).
                meilleur, meilleure_distance = None, None
                for pm in candidats_seuls:
                    if _ligne_est_tableau(pm.start()):
                        continue
                    d = pm.start() - sm.end() if pm.start() >= sm.end() else sm.start() - pm.end()
                    if d < 0 or d > 70:
                        continue
                    if meilleure_distance is None or d < meilleure_distance:
                        meilleur, meilleure_distance = pm, d
                if meilleur is None:
                    continue

                cite = float("%s.%s" % (meilleur.group(1), meilleur.group(2)))
                avant2 = texte[max(0, meilleur.start() - 80):meilleur.start()]
                apres2 = texte[meilleur.end():meilleur.end() + 40]

                def _distance_min2(regex: re.Pattern) -> int | None:
                    d = [len(avant2) - x.end() for x in regex.finditer(avant2)]
                    d += [x.start() for x in regex.finditer(apres2)]
                    return min(d) if d else None

                d_succes2 = _distance_min2(ANCRE_SUCCES)
                d_concentration2 = _distance_min2(ANCRE_CONCENTRATION)
                if d_succes2 is None and d_concentration2 is None:
                    continue  # aucune ancre proche — pas assez sûr pour bloquer

                # CORRIGÉ : `group(0)` est la correspondance ENTIÈRE, signe %
                # compris, alors que les deux gabarits ci-dessous ajoutent déjà
                # « %% » — d'où un « 181.6%% » affiche en double. Le message
                # jumeau du cas TABLEAU passe `group(1)`, le nombre seul. On
                # s'aligne en retirant le signe plutôt qu'en recomposant, pour
                # garder la notation exacte du document (virgule ou point).
                if d_concentration2 is None or (d_succes2 is not None and d_succes2 < d_concentration2):
                    if abs(cite - attendu["win_rate"]) > 0.05:
                        bloque(
                            rel,
                            "WIN RATE « %s%% » cité près de %s (prose, hors tableau) ne "
                            "correspond pas à sa fenêtre vettée (%dj) dans "
                            "BACKTEST_RESULTS.md (devrait être %s%%)."
                            % (meilleur.group(0).strip().rstrip("%").strip(), symbole, attendu["fenetre"],
                               _fmt(attendu["win_rate"])),
                        )
                else:
                    if attendu["concentration"] is not None and abs(cite - attendu["concentration"]) > 0.05:
                        bloque(
                            rel,
                            "CONCENTRATION « %s%% » citée près de %s (prose, hors tableau) "
                            "ne correspond pas à sa fenêtre vettée (%dj) dans "
                            "BACKTEST_RESULTS.md (devrait être %s%%)."
                            % (meilleur.group(0).strip().rstrip("%").strip(), symbole, attendu["fenetre"],
                               _fmt(attendu["concentration"])),
                        )


# ── CONTRÔLE 6 : TOUTE DÉPENDANCE MODIFIÉE EST SIGNALÉE, JAMAIS AJOUTÉE À L'AVEUGLE ─
# Né le 25/08/2026 d'un quasi-incident réel, pas d'une anticipation : on a
# demandé d'installer un dépôt GitHub externe (affaan-m/ecc) qui prétendait
# "212K+ étoiles" — chiffre invérifiable, jamais confirmé via l'API GitHub —
# et qui modifie explicitement les hooks/rules/conventions MCP des agents de
# code. Refusé (règle de cet environnement : jamais de téléchargement ni
# d'exécution depuis une source non vérifiée, même sur demande explicite).
# Le vrai trou que cet épisode révèle POUR CE PROJET : rien ici n'aurait
# signalé l'ajout d'une dépendance si la demande avait visé requirements.txt
# directement plutôt qu'une install manuelle par ce chat. Même mécanique de
# scellé que le contrôle 2 (hash au premier passage, comparaison ensuite) —
# mais ici on ne bloque JAMAIS : une dépendance légitime est censée changer
# de temps en temps. Juste une alerte, UNE SEULE FOIS au moment du
# changement (le registre se re-scelle tout seul après l'avoir signalé),
# pour forcer une relecture consciente au lieu d'un ajout qui passe
# inaperçu dans un futur commit.
def controle_dependances_scellees() -> None:
    chemin = os.path.join(RACINE, "requirements.txt")
    if not os.path.exists(chemin):
        return
    empreinte_actuelle = hashlib.sha256(open(chemin, "rb").read()).hexdigest()
    registre = os.path.join(RACINE, ".garde_fou_scelles.json")
    registre_existait = os.path.exists(registre)
    connues = {}
    if os.path.exists(registre):
        try:
            connues = json.loads(open(registre, encoding="utf-8").read())
        except Exception:
            alerte(".garde_fou_scelles.json", "illisible — registre des empreintes recréé.")
    empreinte_connue = connues.get("requirements.txt")
    if empreinte_connue is None:
        connues["requirements.txt"] = empreinte_actuelle
        # ECRITURE FERMEE EXPLICITEMENT. Corrige le 28/08/2026 au soir, en
        # lisant les ResourceWarning du journal de CI. Ces registres sont la
        # LIGNE DE BASE qui detecte l'alteration d'un fichier scelle. Une
        # ecriture non fermee compte sur le ramassage de CPython pour etre
        # videe sur le disque : ca marche presque toujours, et « presque » ne
        # convient pas pour la piece qui prouve qu'un fichier n'a pas bouge.
        # Un registre tronque se fait RECREER quelques lignes plus haut --
        # donc une alteration passerait pour un premier scellement.
        with open(registre, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(connues, indent=2))
        alerte("requirements.txt", _message_premier_scelle(
            registre_existait, empreinte_actuelle))
    elif empreinte_connue != empreinte_actuelle:
        connues["requirements.txt"] = empreinte_actuelle
        # ECRITURE FERMEE EXPLICITEMENT. Corrige le 28/08/2026 au soir, en
        # lisant les ResourceWarning du journal de CI. Ces registres sont la
        # LIGNE DE BASE qui detecte l'alteration d'un fichier scelle. Une
        # ecriture non fermee compte sur le ramassage de CPython pour etre
        # videe sur le disque : ca marche presque toujours, et « presque » ne
        # convient pas pour la piece qui prouve qu'un fichier n'a pas bouge.
        # Un registre tronque se fait RECREER quelques lignes plus haut --
        # donc une alteration passerait pour un premier scellement.
        with open(registre, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(connues, indent=2))
        alerte(
            "requirements.txt",
            "A CHANGÉ depuis la dernière empreinte connue (%s… → %s…) — "
            "nouvelle dépendance ajoutée ou modifiée ? Vérifie la provenance "
            "avant de committer (nom exact sur PyPI, pas de typosquat, "
            "mainteneur actif, pas d'install depuis un dépôt GitHub non "
            "vérifié). Cette alerte ne se répétera pas au prochain run — "
            "rappel ponctuel au moment du changement, pas un blocage permanent."
            % (empreinte_connue[:12], empreinte_actuelle[:12]),
        )


# ── EXÉCUTION ────────────────────────────────────────────────────────────
def controle_hooks_actifs() -> None:
    """Le hook local est-il seulement branche ?

    AJOUTE le 27/08/2026. CLAUDE.md decrit une protection en TROIS couches
    (hook de commit, CI, hook de push) et dit d'activer la premiere « une fois
    par clone » :

        git config core.hooksPath githooks

    Rien ne verifiait que ce soit fait. Mesure : dans un clone ou hooksPath
    n'est pas configure, on peut supprimer le refus paper-uniquement de
    config.py et COMMITTER -- le hook n'existe pas, garde_fou.py n'est jamais
    lance, et rien ne dit que la couche est absente. La chaine complete a ete
    verifiee des deux cotes le meme jour : hooksPath configure -> commit
    REFUSE ; hooksPath absent -> commit passe.

    Alerte et non blocage : un clone frais n'a legitimement pas encore ete
    configure, et le refuser empecherait le premier commit d'un nouveau poste.
    Ce qui compte est que l'absence soit DITE, pas qu'elle arrete tout.

    Silencieux en CI : les hooks n'y ont aucun sens (aucun commit n'y est
    fait), et la CI EST la couche de protection a cet endroit. Alerter a chaque
    run apprendrait a ignorer les 🟡.
    """
    if os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"):
        return
    dossier_hooks = os.path.join(RACINE, "githooks")
    if not os.path.isdir(dossier_hooks):
        return
    try:
        proc = subprocess.run(
            ["git", "config", "core.hooksPath"],
            cwd=RACINE, capture_output=True, text=True, timeout=15,
        )
    except Exception as exc:
        alerte("githooks", "impossible de lire core.hooksPath (%s)" % exc)
        return
    configure = proc.stdout.strip()
    if configure == "githooks":
        return
    if not configure:
        alerte(
            "githooks",
            "core.hooksPath N'EST PAS CONFIGURE dans ce clone — les hooks "
            "pre-commit et pre-push ne tournent PAS. La premiere des trois "
            "couches decrites dans CLAUDE.md est absente : un commit qui casse "
            "un garde passerait sans un mot ici (verifie par mutation). "
            "Corrige avec :  git config core.hooksPath githooks",
        )
    else:
        alerte(
            "githooks",
            "core.hooksPath pointe vers %r et non vers 'githooks' — les hooks "
            "de ce depot ne tournent pas. Voulu ?" % configure,
        )


def controle_nombre_de_tests_annonce() -> None:
    """Le chiffre de tests annonce aux livrables correspond-il a la realite ?

    AJOUTE le 28/08/2026. Le README annoncait « 12 offline regression tests ».
    Mesure le meme soir : 495. Le chiffre ne se contentait pas d'etre faux --
    il SOUS-ESTIMAIT le travail d'un facteur 40, sur la ligne « Proof it
    runs » qu'un jury lit en premier.

    POURQUOI UN CONTROLE ET PAS SEULEMENT UNE CORRECTION. controle_chiffres_
    perimes() existe deja, mais c'est une LISTE NOIRE de valeurs connues : il
    ne peut attraper « 12 » que si quelqu'un pense a l'y inscrire, c'est-a-dire
    au moment precis ou il ne l'a pas fait. Celui-ci MESURE LES DEUX COTES --
    ce que le document dit, et ce que le depot contient -- donc il ne peut pas
    devenir perime a son tour.

    Le comptage est STATIQUE (methodes `test_*` lues dans l'arbre syntaxique),
    pas une execution de la suite : garde_fou.py tourne en moins d'une seconde
    et doit le rester. Verifie le 28/08 : le comptage statique rend 495, et
    `unittest discover` en rend 495 aussi -- ecart nul.

    ALERTE et non blocage : c'est un chiffre dans un document, pas une valeur
    fausse dans le code. Choisir de le reformuler appartient a l'auteur ; ne
    pas etre au courant, non.
    """
    reel = 0
    # RACINE est une CHAINE dans ce fichier, pas un Path -- verifie avant de
    # corriger, pas suppose : `RACINE.glob` levait AttributeError.
    # os seulement : ce fichier n'importe pas pathlib, et RACINE est une
    # CHAINE. Verifie dans les imports plutot que suppose -- mes deux essais
    # precedents ont leve AttributeError puis NameError.
    for nom in sorted(os.listdir(RACINE)):
        if not (nom.startswith("test_") and nom.endswith(".py")):
            continue
        try:
            with open(os.path.join(RACINE, nom), encoding="utf-8") as fh:
                arbre = ast.parse(fh.read())
        except (OSError, SyntaxError):
            # On ne peut pas compter : on se tait plutot que d'annoncer un
            # chiffre faux. « Je n'ai pas su lire » n'est pas « il y en a
            # zero » -- ce serait exactement le defaut que ce controle traque.
            return
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.FunctionDef) and noeud.name.startswith("test"):
                reel += 1
    if not reel:
        return

    # `~` et `+` sont acceptes comme APPROXIMATION ASSUMEE. Ajoute dans la
    # foulee : la version stricte a signale trois fois de suite un README que
    # je venais de corriger, parce que chaque test ajoute changeait le total.
    # Exiger un chiffre exact dans un document, c est le condamner a etre faux
    # entre deux commits -- et pousser l auteur a desarmer le controle.
    #
    # « 500+ tests » reste VRAI tant qu il y en a au moins 500 ; « ~500 » tant
    # qu on est a 5 % pres. Un chiffre nu, lui, doit toujours etre exact : on
    # ne relache rien sur l affirmation precise, on autorise seulement de ne
    # pas en faire une.
    ANNONCE = re.compile(
        r"(~)?(\d+)(\+)?\s+(?:offline\s+)?(?:regression\s+|unit\s+|automated\s+)?tests?\b",
        re.I)
    for rel, texte in _charger_textes_livrables().items():
        for m in ANNONCE.finditer(texte):
            annonce = int(m.group(2))
            if m.group(3):        # « 500+ » : un minorant
                juste = reel >= annonce
            elif m.group(1):      # « ~500 » : a 5 % pres
                juste = abs(reel - annonce) <= max(1, annonce * 0.05)
            else:                 # un chiffre nu doit etre EXACT
                juste = (annonce == reel)
            if not juste:
                alerte(
                    rel,
                    "annonce « %s » alors que le depot en contient %d. Un jury "
                    "lit ce chiffre comme une mesure. (Comptage statique des "
                    "methodes test_* ; verifie egal a `unittest discover`.)"
                    % (m.group(0).strip(), reel))


def controle_verrou_dit_hebdomadaire() -> None:
    """Les livrables decrivent-ils le verrou de perte comme HEBDOMADAIRE ?

    AJOUTE le 27/08/2026. risk_gates.py titre lui-meme son commentaire
    « NOM TROMPEUR » et ecrit : « Ce verrou n'est pas hebdomadaire. » Il compare
    l'equite courante a une reference posee UNE FOIS, sans aucune remise a zero
    en fin de semaine -- verifie par test
    (test_la_reference_ne_suit_PAS_le_sommet_ni_la_semaine).

    Le README porte la correction explicitement : « Named "weekly" in the code,
    but measured from the first [...] there is no week-boundary reset. »

    Les TROIS AUTRES livrables -- ceux qu'un jury lit -- ne la portaient pas :

        Video_Script.md  « un verrou automatique si le compte perd 3% sur la
                          semaine »
        Writeup.docx     « 3% weekly drawdown lock »
        Deck.pptx        « 3% weekly drawdown — Sticky lock »

    Ils decrivent un verrou qui repart a zero chaque semaine. Il ne repart
    jamais. Un lecteur en deduirait que l'agent reprend le lundi suivant.

    ALERTE et non blocage : c'est une formulation dans des documents de
    soumission, pas une valeur fausse dans le code. Le choix de reformuler --
    ou d'assumer le raccourci -- appartient a l'auteur. Ce qui ne lui appartient
    pas, c'est de ne pas etre au courant.
    """
    CORRECTIONS = re.compile(
        r"no week-boundary reset|not from the start of each week|"
        r"pas hebdomadaire|n'est pas hebdomadaire|never resets|"
        r"jamais remis a zero|jamais remis à zéro",
        re.I,
    )
    PROXIMITE = re.compile(
        r"(?:weekly|hebdomadaire|sur la semaine|per week)"
        r"[^.\n]{0,60}(?:lock|drawdown|verrou|perte)"
        r"|(?:lock|drawdown|verrou|perte)[^.\n]{0,60}"
        r"(?:weekly|hebdomadaire|sur la semaine|per week)",
        re.I,
    )
    for rel, texte in _charger_textes_livrables().items():
        trouves = [m.group(0).strip() for m in PROXIMITE.finditer(texte)]
        if not trouves:
            continue
        if CORRECTIONS.search(texte):
            continue  # le livrable porte deja la nuance
        alerte(
            rel,
            "decrit le verrou de perte comme HEBDOMADAIRE (« %s ») alors que "
            "risk_gates.py dit explicitement l'inverse -- « Ce verrou n'est pas "
            "hebdomadaire », il n'y a AUCUNE remise a zero en fin de semaine. Un "
            "lecteur en deduirait que l'agent reprend le lundi suivant. Le README "
            "porte la nuance, celui-ci non."
            % trouves[0][:70],
        )


def controle_readme_decrit_les_agents() -> None:
    """Le README decrit-il ce que les plists font REELLEMENT ?

    AJOUTE le 27/08/2026, apres une erreur que ce controle aurait empechee.

    Le README documente, en gras : « This is a deliberate change to a rule this
    project used to hold. » -- la publication du tableau de bord est automatique
    (`publish_dashboard.py --git-push`), la regle precedente est AMENDEE la
    plutot qu'ignoree, et le raisonnement est ecrit noir sur blanc : la page est
    l'URL de soumission, une regle qui la laisse perimee protegeait la mauvaise
    chose.

    Le meme jour, j'ai retire `--git-push` du plist en m'appuyant sur la
    docstring de publish_dashboard.py -- que ce paragraphe declare justement
    perimee. Une decision reflechie et documentee annulee en croyant corriger un
    oubli, parce que RIEN ne reliait le README aux plists.

    Ce controle relie les deux, dans les DEUX sens : une option que le README
    attribue a un agent doit exister dans son plist, et une option active dans
    un plist doit apparaitre dans ce que le README en dit.

    ALERTE et non blocage : il ne tranche pas quelle version a raison. Il rend
    le desaccord visible, pour que la personne qui a pris la decision decide.
    """
    dossier = os.path.join(RACINE, "launchagents")
    chemin_readme = os.path.join(RACINE, "README.md")
    if not os.path.isdir(dossier) or not os.path.exists(chemin_readme):
        return
    texte = open(chemin_readme, encoding="utf-8", errors="replace").read()

    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith(".plist"):
            continue
        contenu = open(os.path.join(dossier, nom),
                       encoding="utf-8", errors="replace").read()
        pos = texte.find(nom)
        if pos == -1:
            # ELARGI le 27/08 : c'etait un `continue` muet. Trouve en lisant
            # l'inventaire du README, qui annoncait « the two macOS scheduling
            # definitions » alors qu'il y en a TROIS -- l'agent de publication
            # manquait de cette liste, meme s'il etait decrit ailleurs.
            #
            # Un agent planifie que le README ne nomme NULLE PART est un
            # comportement automatique que personne n'a documente. Meme regle
            # que dans l'autre sens, quelques lignes plus bas.
            alerte(
                "README.md",
                "ne nomme nulle part %s. Cet agent tourne pourtant tout seul sur "
                "la machine : un comportement automatique non documente est un "
                "comportement que personne n'a decide." % nom,
            )
            continue

        # Les options en `--xxx` reellement passees par le plist. Une ligne
        # commentee (a l'interieur d'un <!-- --> XML) n'en est pas une : on ne
        # garde que les <string> seuls sur leur ligne.
        actives = set()
        for ligne in contenu.splitlines():
            nu = ligne.strip()
            if nu.startswith("<!--") or nu.startswith("--"):
                continue
            m = re.fullmatch(r"<string>(--[\w-]+)</string>", nu)
            if m:
                actives.add(m.group(1))

        # Ce que le README attribue a CET agent : les options citees pres de
        # N'IMPORTE LAQUELLE de ses mentions.
        #
        # RESSERRE le 27/08, aussitot apres avoir complete l'inventaire du
        # README : ce bloc ne regardait que la PREMIERE occurrence du nom. En
        # ajoutant le plist de publication a la liste d'inventaire, sa premiere
        # mention est devenue cette liste -- qui ne cite aucune option -- alors
        # que la description complete, avec --git-push, est 70 lignes plus bas.
        # Le controle a donc signale un desaccord inexistant, cree par ma
        # propre edition.
        #
        # Un README a le droit de nommer un agent a plusieurs endroits : c'est
        # meme le signe qu'il est bien documente. On considere une option comme
        # documentee si elle apparait pres de N'IMPORTE quelle mention.
        citees = set()
        depart = 0
        while True:
            i = texte.find(nom, depart)
            if i == -1:
                break
            citees.update(re.findall(r"(--[\w-]+)", texte[i:i + 300]))
            depart = i + 1

        promises_absentes = sorted(citees - actives)
        actives_non_dites = sorted(actives - citees)

        if promises_absentes:
            alerte(
                "README.md",
                "decrit %s comme lance avec %s, mais le plist ne passe pas "
                "cette option. Le README documente peut-etre une decision "
                "deliberee que le plist a perdue -- ou l'inverse. Les deux ne "
                "peuvent pas avoir raison."
                % (nom, ", ".join(promises_absentes)),
            )
        if actives_non_dites:
            alerte(
                nom,
                "passe %s, que le README ne mentionne pas la ou il decrit cet "
                "agent. Un comportement automatique non documente est un "
                "comportement que personne n'a decide."
                % ", ".join(actives_non_dites),
            )


def _publication_deliberee(rel: str, nom: str, valeur: str) -> bool:
    """La valeur est-elle a l'endroit EXACT ou le depot la publie exprEs ?

    Un seul cas aujourd'hui : le numero de compte, dans
    docs/data.json -> account.account_number. publish_dashboard.py explique
    pourquoi sur dix lignes -- « the dashboard shows the SAME identifier
    that's declared in the submission [...] a mismatch here would make the
    cross-check confusing instead of reassuring ».

    On verifie l'EMPLACEMENT, pas seulement la presence : la meme valeur
    dans recent_decisions, dans positions, ou dans n'importe quel autre
    fichier, n'est pas couverte et alerte toujours.
    """
    if rel != os.path.join("docs", "data.json") or nom != "ALPACA_ACCOUNT_ID":
        return False
    try:
        with open(os.path.join(RACINE, rel), encoding="utf-8") as fh:
            donnees = json.load(fh)
    except (OSError, ValueError):
        return False
    compte = donnees.get("account")
    if not isinstance(compte, dict) or compte.get("account_number") != valeur:
        return False
    # La valeur ne doit apparaitre NULLE PART AILLEURS dans le fichier : on
    # re-serialise sans ce champ et on re-cherche.
    sans = json.loads(json.dumps(donnees))
    sans["account"].pop("account_number", None)
    return valeur not in json.dumps(sans)


def controle_aucun_identifiant_dans_les_fichiers_publies() -> None:
    """Un identifiant est-il present dans un fichier COMMITTE ?

    AJOUTE le 27/08/2026. decision_log.jsonl et docs/data.json ne sont pas
    gitignores : ce sont les preuves publiees, et depuis le retablissement de la
    publication automatique le meme jour, elles partent sur le depot PUBLIC
    toutes les 30 minutes sans intervention humaine.

    Le chemin par lequel une cle pourrait y entrer : alpaca_cli.run() leve,
    quand la sortie du CLI n'est pas du JSON, avec « first 500 chars of output:
    {stdout[:500]} » -- la sortie BRUTE. Les identifiants sont dans
    l'environnement de ce sous-processus. Un CLI en « Alpha Preview » qui
    recracherait son environnement ou une URL signee dans un message d'erreur
    suffirait.

    decision_log.caviarder() ferme ce chemin a l'ECRITURE depuis le meme jour.
    Ce controle-ci est la seconde couche : il regarde ce qui est DEJA sur le
    disque, y compris des lignes ecrites avant que le caviardage existe.

    BLOQUE, contrairement a la plupart des controles de ce script. Une cle
    poussee sur un depot public est publique pour toujours : c'est le seul
    defaut irreversible que ce projet puisse produire.

    Recherche par VALEUR EXACTE, jamais par motif : aucun faux positif possible.
    Sans identifiants dans l'environnement -- le cas de la CI -- il n'y a rien a
    chercher et le controle ne dit rien. C'est voulu : il est effectif la ou il
    compte, dans le hook de pre-commit, sur la machine qui detient les cles.
    """
    # Les identifiants ne sont PAS dans os.environ quand ce script tourne : ils
    # vivent dans les fichiers d'environnement, charges par python-dotenv A
    # L'INTERIEUR de config.py -- que ce script n'importe pas volontairement
    # (config sort du programme sur cles manquantes ; l'importer ferait mourir
    # le garde-fou en CI).
    #
    # Trouve en verifiant ce controle sur le depot reel juste apres l'avoir
    # ecrit : il ne trouvait aucune valeur, donc il ne cherchait RIEN, donc il
    # aurait ete inerte precisement dans le hook de pre-commit -- le seul
    # endroit qui compte. Un controle qu'on ne verifie pas est un controle qui
    # rassure sans proteger. On lit donc les fichiers directement.
    NOMS = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_ACCOUNT_ID")

    def _ressemble_a_un_identifiant(nom: str, v: str) -> bool:
        """Un vrai identifiant Alpaca, pas un remplissage.

        RESSERRE le 27/08, trouve par la reproduction de l'environnement CI
        juste apres avoir elargi ce controle a tous les fichiers suivis. Les
        fichiers de test posent eux-memes des identifiants factices
        (« cle-de-test », « secret-de-test ») ; quand garde_fou tourne avec ces
        valeurs dans l'environnement -- ce que fait la suite -- il les retrouve
        dans les sources et BLOQUE. Un controle qui crie sur des valeurs bidon
        apprend a etre ignore, et c'est le pire sort pour celui-ci.

        Les vraies valeurs Alpaca sont alphanumeriques et longues (cle : 20
        caracteres, secret : 40, numero de compte : « PA » + alphanumerique,
        12 caracteres). Un remplissage lisible par un humain ne l'est pas.

        Le seuil est PAR NOM, corrige aussitot ecrit : un seuil unique a 16
        laissait passer les cles mais rejetait le numero de compte, qui n'en
        fait que 12 -- la detection du numero avait donc disparu sans bruit.
        Trois formats differents ne se filtrent pas avec un seul nombre."""
        if not re.fullmatch(r"[A-Za-z0-9_-]+", v):
            return False
        if nom == "ALPACA_ACCOUNT_ID":
            # Forme Alpaca : « PA » suivi d'alphanumerique majuscule.
            return len(v) >= 10 and re.fullmatch(r"[A-Z0-9]+", v) is not None
        return len(v) >= 16 and sum(c.isalnum() for c in v) >= 12

    trouvees = {}
    for nom in NOMS:
        v = os.environ.get(nom) or ""
        if _ressemble_a_un_identifiant(nom, v):
            trouvees[nom] = v
    for fichier in ('.env', '.env.hackathon'):
        chemin = os.path.join(RACINE, fichier)
        if not os.path.exists(chemin):
            continue
        try:
            contenu = open(chemin, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for ligne in contenu.splitlines():
            ligne = ligne.strip()
            if ligne.startswith("#") or "=" not in ligne:
                continue
            cle, _, val = ligne.partition("=")
            cle = cle.strip()
            val = val.strip().strip("'").strip('"')
            if cle in NOMS and _ressemble_a_un_identifiant(cle, val):
                trouvees[cle] = val
    if not trouvees:
        # AJOUTE le 27/08/2026, apres reproduction dans un clone jetable.
        #
        # La recherche par VALEUR EXACTE est un bon choix : aucun faux positif
        # possible. Mais SANS valeur a chercher, ce controle ne cherche RIEN --
        # et il ne le disait pas. Mesure sur un meme depot portant une meme
        # fausse cle au format Alpaca, committee :
        #
        #     valeurs connues -> 🔴 BLOQUANT, « revoque cette cle »
        #     aucune valeur   -> 🟡, silence complet sur les identifiants
        #
        # Excellent une fois arme, muet sur le fait de ne pas l'etre -- dans le
        # SEUL controle bloquant de ce script, celui qui garde le seul defaut
        # irreversible que ce projet puisse produire.
        #
        # Le cas n'est pas theorique : c'est l'etat de la CI, et celui de tout
        # clone fait sur une autre machine. Le workflow GitHub se presentait
        # justement comme la couche censee rattraper un `git commit
        # --no-verify` ; pour les identifiants elle ne le peut pas, et son
        # commentaire a ete corrige le meme jour. Les deux ne pouvaient pas
        # avoir raison.
        #
        # ALERTE et non blocage : un clone legitime sans identifiants n'a rien
        # fait de mal. Mais un lecteur du log doit savoir que ce controle-la
        # n'a pas tourne. Meme forme que controle_journal() pour PLAN_SPRINT.md
        # absent : « ce controle n'a RIEN verifie ici ».
        alerte("identifiants",
               "AUCUNE valeur d'identifiant connue sur cette machine, donc ce "
               "controle n'a RIEN verifie. Il cherche par valeur exacte (aucun "
               "faux positif possible) et n'a rien a comparer ici. Le controle "
               "par MOTIF, lui, reste actif et couvre les formes Alpaca "
               "reconnaissables ; ce qui reste decouvert, c'est une valeur qui "
               "ne ressemble pas a une cle. C'est l'etat "
               "normal en CI et sur un clone ; il est effectif la ou il compte, "
               "sur la machine qui detient les cles. Ne pas lire ce vert comme "
               "« aucun identifiant publie ».")
        return
    valeurs = sorted(trouvees.items())

    # ELARGI le 27/08 : la premiere version ne regardait que decision_log.jsonl
    # et docs/data.json. Mesure sur les 38 fichiers suivis par git : aucune cle
    # ni secret nulle part -- rassurant -- mais le NUMERO DE COMPTE du hackathon
    # apparait dans trois fichiers source committes (CLAUDE.md, ce script,
    # test_connection.py). Le controle ne les regardait pas.
    #
    # Ce n'est pas grave pour un numero de compte : il n'autorise aucune action
    # sans les cles, et le tableau de bord publie deja celui du compte courant.
    # Ce qui l'est, c'est que le controle aurait ete AVEUGLE a une vraie cle
    # posee dans un .py -- exactement le cas qu'il existe pour attraper.
    #
    # On balaie donc TOUT ce que git suit, avec deux severites :
    #   - une CLE ou un SECRET dans un fichier suivi -> BLOQUE. Irreversible
    #     une fois pousse.
    #   - le NUMERO DE COMPTE -> alerte. C'est un identifiant, pas un pouvoir,
    #     et sa presence peut etre un choix assume ; on le dit sans crier.
    CRITIQUES = {"ALPACA_API_KEY", "ALPACA_SECRET_KEY"}
    try:
        suivis = subprocess.run(
            ["git", "ls-files"], cwd=RACINE, capture_output=True, text=True,
            timeout=20,
        )
        fichiers = suivis.stdout.split("\n") if suivis.returncode == 0 else []
    except Exception as err:
        alerte("git", "impossible de lister les fichiers suivis (%s) -- la "
                      "recherche d'identifiants n'a porte que sur les deux "
                      "fichiers publies." % err)
        fichiers = []
    fichiers = [f for f in fichiers if f.strip()]
    for rel in ("decision_log.jsonl", os.path.join("docs", "data.json")):
        if rel not in fichiers:
            fichiers.append(rel)

    for rel in fichiers:
        chemin = os.path.join(RACINE, rel)
        if not os.path.isfile(chemin):
            continue
        try:
            texte = open(chemin, encoding="utf-8", errors="replace").read()
        except OSError as err:
            alerte(rel, "illisible (%s) -- impossible de verifier qu'aucun "
                        "identifiant ne s'y trouve." % err)
            continue
        for nom, valeur in valeurs:
            if valeur not in texte:
                continue
            if nom in CRITIQUES:
                bloque(
                    rel,
                    "CONTIENT LA VALEUR DE %s. Ce fichier est SUIVI PAR GIT et "
                    "part sur le depot PUBLIC. Ne pas committer, ne pas pousser : "
                    "retirer la valeur, puis REVOQUER cette cle chez Alpaca -- si "
                    "elle est deja partie, elle est publique pour toujours." % nom,
                )
            elif _publication_deliberee(rel, nom, valeur):
                # LA REPONSE EST DANS LE DEPOT, on la lit au lieu de la
                # redemander. Ajoute le 28/08/2026 au soir.
                #
                # L'alerte precedente disait « c'est peut-etre un choix assume.
                # Signale pour que ce soit un choix, pas un oubli » -- et elle
                # n'offrait AUCUN moyen de trancher. Elle restait donc jaune a
                # chaque passage, indefiniment, alors que la reponse est ecrite
                # dans publish_dashboard.py : `account_number` est publie
                # exprES, pour qu'un juge puisse recouper le tableau de bord
                # avec le compte soumis.
                #
                # Une alerte qu'on ne peut jamais resoudre entraine a ignorer
                # les alertes -- la meme faute que la banniere du moniteur
                # avait failli commettre en criant chaque soir.
                #
                # ON NE RELACHE RIEN : la valeur n'est toleree QU'A CET ENDROIT
                # PRECIS -- account.account_number du fichier publie. La meme
                # valeur ailleurs dans data.json, ou dans un autre fichier,
                # alerte toujours.
                pass
            else:
                alerte(
                    rel,
                    "contient la valeur de %s. Un numero de compte n'autorise "
                    "aucune action sans les cles. Ce n'est PAS l'endroit ou le "
                    "tableau de bord le publie volontairement "
                    "(account.account_number) : verifie pourquoi il est la." % nom,
                )

    # ══ L'HISTORIQUE, pas seulement l'arbre de travail ═══════════════════════
    #
    # AJOUTE le 27/08/2026. Tout ce qui precede regarde les fichiers TELS QU'ILS
    # SONT. Une cle committee puis retiree n'y apparait plus -- et reste dans
    # l'historique public pour toujours.
    #
    # Le chemin : `git commit --no-verify` contourne le hook, donc contourne
    # tout ce script. Sans ce balayage, la fuite serait DEFINITIVEMENT
    # silencieuse.
    #
    # Verifie une fois sur ce depot, 87 commits : AUCUNE cle, AUCUN secret n'a
    # jamais ete commite. Le defaut irreversible n'a pas eu lieu. Ce controle
    # existe pour que ca reste vrai.
    #
    # Uniquement les valeurs CRITIQUES : le numero de compte est deja dans
    # l'historique (11 commits, en commentaire depuis le debut) et n'autorise
    # aucune action -- le chercher a chaque run produirait un bruit permanent.
    #
    # Cout mesure : 0,22 s pour quatre valeurs sur 87 commits, soit l'equivalent
    # du temps total de ce script. Negligeable, meme lance 75 fois par jour par
    # l'agent de publication.
    #
    # LE REMEDE N'EST PAS DE RETIRER LA LIGNE. Ce projet s'interdit de reecrire
    # l'historique (« pas de filter-repo, pas de --force » -- regle repetee tout
    # au long du sprint). Si une cle est dans l'historique d'un depot public,
    # la REVOCATION est le seul remede reel, et ce message le dit.
    critiques = [(n, v) for n, v in valeurs if n in CRITIQUES]
    if not critiques:
        return
    for nom, valeur in critiques:
        try:
            trouve = subprocess.run(
                ["git", "log", "--all", "--oneline", "-S", valeur, "--"],
                cwd=RACINE, capture_output=True, text=True, timeout=120,
            )
        except Exception as err:
            alerte(
                "git",
                "impossible de balayer l'historique pour %s (%s) -- une cle "
                "commitee puis retiree ne serait PAS vue ici." % (nom, err),
            )
            continue
        if trouve.returncode != 0:
            alerte(
                "git",
                "`git log -S` a echoue (code %d) -- l'historique n'a PAS ete "
                "verifie pour %s. Une sortie vide est indistinguable d'un "
                "historique propre." % (trouve.returncode, nom),
            )
            continue
        commits = [l for l in trouve.stdout.splitlines() if l.strip()]
        if commits:
            bloque(
                "historique git",
                "LA VALEUR DE %s APPARAIT DANS L'HISTORIQUE (%d commit(s) : %s). "
                "Elle est recuperable par quiconque clone le depot, meme si le "
                "fichier a ete retire depuis. Ce projet s'interdit de reecrire "
                "l'historique : REVOQUER cette cle chez Alpaca est le seul "
                "remede reel."
                % (nom, len(commits), ", ".join(c.split()[0] for c in commits[:5])),
            )


def controle_reveil_programme() -> None:
    """Le Mac est-il programme pour se REVEILLER avant la seance ?

    AJOUTE le 27/08/2026. Le README raconte un incident REEL : le moniteur de
    sorties a echoue 11 fois de suite un apres-midi. Cause trouvee alors -- le
    Mac dormait, et launchd ne declenchait le job que pendant de brefs reveils
    de maintenance, trop courts pour que le Wi-Fi se reconnecte avant que
    l'appel reseau expire. Chaque horodatage d'echec correspondait a la seconde
    au journal de veille du systeme.

    Le remede tient en une ligne, ecrite dans le README :

        sudo pmset repeat wakeorpoweron MTWRF 15:15:00

    Elle demande le mot de passe administrateur, donc elle ne peut pas etre
    automatisee ici -- et RIEN ne verifiait qu'elle ait ete lancee. Mesure le
    27/08 sur cette machine : aucun evenement recurrent programme. Le mecanisme
    qui fait tenir toute la surveillance non surveillee etait absent, en
    silence.

    Le plist market-hours-awake garde la machine EVEILLEE de 15:20 a 22:05,
    mais son propre commentaire le dit : « It can only keep the machine awake
    -- it CANNOT wake a machine that is already asleep. » Les deux sont
    necessaires, et un seul des deux etait verifiable.

    ALERTE et non blocage : c'est un etat de machine, pas un defaut du dossier,
    et un depot clone sur une autre machine n'a aucune raison d'echouer pour ca.
    Silencieux hors macOS et en CI, ou pmset n'existe pas et n'aurait aucun sens.
    """
    if os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"):
        return
    if sys.platform != "darwin":
        return
    try:
        proc = subprocess.run(["pmset", "-g", "sched"], capture_output=True,
                              text=True, timeout=15)
    except FileNotFoundError:
        return
    except Exception as exc:
        alerte("pmset", "impossible de lire les evenements programmes (%s: %s) -- "
                        "le reveil avant seance n'a PAS ete verifie."
                        % (type(exc).__name__, exc))
        return
    if proc.returncode != 0:
        alerte("pmset", "`pmset -g sched` a echoue (code %d) -- le reveil avant "
                        "seance n'a PAS ete verifie. Une sortie vide est "
                        "indistinguable d'une machine correctement programmee."
                        % proc.returncode)
        return
    if re.search(r"repeating power events", proc.stdout, re.I):
        return
    alerte(
        "pmset",
        "AUCUN REVEIL RECURRENT programme sur cette machine. Si le Mac dort a "
        "15:15, launchd ne declenchera le moniteur de sorties que pendant de "
        "brefs reveils de maintenance -- l'incident des 11 echecs consecutifs "
        "raconte dans le README. Le plist market-hours-awake garde la machine "
        "eveillee mais NE PEUT PAS la reveiller. Corrige avec :  "
        "sudo pmset repeat wakeorpoweron MTWRF 15:15:00",
    )


def _ancres_du_markdown(texte: str) -> set:
    """Les ancres qu'un lecteur peut atteindre dans ce document.

    Reproduit la regle de GitHub : minuscules, ponctuation retiree, espaces en
    tirets. Le balisage `code`, **gras** et *italique* est retire d'abord,
    sinon un titre stylise produirait une ancre qui n'existe pas."""
    ancres = set()
    for titre in re.findall(r"^#{1,6}\s+(.+?)\s*$", texte, re.M):
        t = re.sub(r"[`*_]", "", titre).strip().lower()
        t = re.sub(r"[^\w\s-]", "", t)
        ancres.add(re.sub(r"\s+", "-", t))
    return ancres


def controle_ancres_resolvent() -> None:
    """Un lien vers une ancre tombe-t-il sur un titre qui existe ?

    AJOUTE le 29/08/2026, en completant `controle_renvois_resolvent` : celui-ci
    verifie que le FICHIER cite existe, jamais que l'ANCRE citee mene quelque
    part. Or l'effet sur un lecteur est le meme, et pire : un fichier absent
    donne une 404 visible, une ancre morte ne fait RIEN. Le navigateur reste
    ou il est, et le lecteur croit avoir mal cliqué.

    Le README en compte 14 (liens internes) au moment de l'ajout, tous
    valides -- ce controle ne corrige donc rien aujourd'hui. Il ferme la
    moitie qui n'etait pas verifiee, comme le controle des plists CHARGES l'a
    fait le meme jour pour les LaunchAgents.

    Portee volontairement etroite : seuls les .md suivis par git, et seules
    les ancres REELLEMENT citees. Enumerer toutes les ancres possibles pour
    verifier qu'elles sont atteignables produirait du bruit sans lecteur.

    ELARGI le 30/08/2026 aux DEUX moities d'un lien. La premiere version ne
    lisait que l'ancre et abandonnait des qu'il y avait une partie fichier,
    en renvoyant a `controle_renvois_resolvent` -- lequel ne lit que deux
    fichiers en dur et que les chemins entre accents graves. Les deux
    controles se partageaient donc le travail selon un axe qui laissait un
    trou : `[Voir](FICHIER_ABSENT.md#section)` traversait les deux."""
    try:
        suivis = subprocess.run(["git", "ls-files"], cwd=RACINE,
                                capture_output=True, text=True, timeout=20)
        connus = set(suivis.stdout.split()) if suivis.returncode == 0 else set()
    except Exception as exc:
        alerte("git", "impossible de lister les fichiers suivis (%s) -- les "
                      "ancres n'ont PAS ete verifiees." % exc)
        return
    if not connus:
        alerte("git", "aucun fichier suivi listable -- les ancres n'ont PAS "
                      "ete verifiees. Une liste vide est indistinguable d'un "
                      "depot sans ancre morte.")
        return
    ancres_par_fichier = {}
    for rel in [f for f in connus if f.endswith(".md")]:
        chemin = os.path.join(RACINE, rel)
        if not os.path.isfile(chemin):
            continue
        try:
            texte = open(chemin, encoding="utf-8", errors="replace").read()
        except OSError as exc:
            alerte(rel, "illisible (%s) -- ses ancres n'ont PAS ete "
                        "verifiees." % exc)
            continue
        ancres_par_fichier[rel] = _ancres_du_markdown(texte)
        for lien in re.findall(r"\[[^\]]+\]\(([^)\s]+)\)", texte):
            if lien.startswith(("http", "mailto", "./")):
                continue
            fichier, _, ancre = lien.partition("#")

            # LA MOITIE « FICHIER ». Elle etait sautee net (`if fichier:
            # continue`, plus un `if "#" not in lien: continue` un cran plus
            # haut), au motif qu'elle relevait de `controle_renvois_resolvent`.
            # Or celui-ci ne lit QUE deux fichiers en dur et QUE les chemins
            # entre accents graves : mesure du 30/08/2026, sept liens
            # markdown des .md suivis ne passaient devant aucun des deux, et
            # `[Voir](FICHIER_ABSENT.md#section)` traversait les deux. Aucun
            # n'est mort aujourd'hui -- c'etait un trou, pas un defaut. Meme
            # convention de resolution que son jumeau : suivi par git OU
            # present sur le disque.
            vise = rel
            if fichier:
                vise = os.path.normpath(
                    os.path.join(os.path.dirname(rel), fichier))
                if (vise not in connus
                        and not os.path.exists(os.path.join(RACINE, vise))):
                    alerte(rel, "le lien « %s » vise un fichier qui n'existe "
                                "pas : %s." % (lien, vise))
                    continue
                if not vise.endswith(".md"):
                    continue      # une ancre hors markdown : pas de titre a lire
                if vise not in ancres_par_fichier:
                    try:
                        ancres_par_fichier[vise] = _ancres_du_markdown(
                            open(os.path.join(RACINE, vise), encoding="utf-8",
                                 errors="replace").read())
                    except OSError as exc:
                        alerte(rel, "le lien « %s » vise un fichier illisible "
                                    "(%s) -- son ancre n'a PAS ete "
                                    "verifiee." % (lien, exc))
                        continue
            if ancre and ancre not in ancres_par_fichier[vise]:
                ou = "de ce fichier" if vise == rel else "de %s" % vise
                alerte(rel,
                       "le lien « #%s » ne mene a aucun titre %s. "
                       "Un fichier absent donne une 404 visible ; une ancre "
                       "morte ne fait RIEN, et le lecteur croit avoir mal "
                       "clique." % (ancre, ou))


def controle_renvois_resolvent() -> None:
    """Chaque fichier cite dans un livrable existe-t-il vraiment ?

    AJOUTE le 27/08/2026. Un juge qui suit un renvoi vers un fichier absent ne
    voit pas une coquille : il voit un dossier qui parle de choses qui n'y sont
    pas.

    Ce n'est pas theorique. Une session anterieure a trouve 37 renvois morts
    dans ce depot, dont un qui disait litteralement au jury d'aller consulter
    les `BRIEF_*.md` « at the repo root » -- alors qu'ils venaient d'etre
    retires du suivi git. Le fichier existait encore sur la machine de
    l'auteur ; il n'existait plus pour personne d'autre.

    C'est precisement le piege : `os.path.exists` sur SA machine dit oui.
    On croise donc contre ce que GIT SUIT, c'est-a-dire ce qu'un lecteur
    recevra -- en acceptant aussi un fichier present mais non suivi, qui est un
    autre probleme (celui-la se voit au clone, pas ici).

    Les motifs a etoile (`BRIEF_*.md`) sont developpes : c'est la forme exacte
    du renvoi mort d'origine, et une simple existence de chemin ne l'aurait pas
    attrape.

    Portee : les livrables en Markdown, ou les chemins sont cites entre
    accents graves. Le .docx et le .pptx citent en prose, sans marqueur fiable ;
    y deviner des chemins produirait des faux positifs, et un controle qui crie
    a tort s'apprend a ignorer.
    """
    try:
        suivis = subprocess.run(
            ["git", "ls-files"], cwd=RACINE, capture_output=True, text=True,
            timeout=20,
        )
        connus = set(suivis.stdout.split()) if suivis.returncode == 0 else set()
    except Exception as exc:
        alerte("git", "impossible de lister les fichiers suivis (%s) -- les "
                      "renvois des livrables n'ont PAS ete verifies." % exc)
        return
    if not connus:
        alerte("git", "aucun fichier suivi listable -- les renvois des livrables "
                      "n'ont PAS ete verifies. Une liste vide est indistinguable "
                      "d'un depot sans renvoi mort.")
        return

    def _volontairement_ignore(rel_cite: str) -> bool:
        """Le chemin cite est-il gitignore, donc absent d'un clone a dessein ?"""
        try:
            r = subprocess.run(["git", "check-ignore", "-q", rel_cite],
                               cwd=RACINE, capture_output=True, timeout=15)
            return r.returncode == 0
        except Exception:
            return False

    MOTIF = re.compile(
        r"`([A-Za-z0-9_][A-Za-z0-9_.*/-]*"
        r"\.(?:py|md|json|jsonl|yml|yaml|html|plist|txt|docx|pptx|sh))`")

    for rel in ("README.md", os.path.join("submission", "Video_Script.md")):
        chemin = os.path.join(RACINE, rel)
        if not os.path.exists(chemin):
            continue
        texte = open(chemin, encoding="utf-8", errors="replace").read()
        morts = []
        for m in MOTIF.finditer(texte):
            cite = m.group(1)
            # Une URL relative de la page (./data.json) n'est pas un chemin du
            # depot : elle est resolue par le navigateur, pas par un lecteur.
            if cite.startswith("./") or cite.startswith("http"):
                continue
            if "*" in cite:
                import fnmatch
                if any(fnmatch.fnmatch(f, cite) or fnmatch.fnmatch(
                        os.path.basename(f), cite) for f in connus):
                    continue
            elif cite in connus:
                continue
            elif _volontairement_ignore(cite):
                # RESSERRE aussitot ecrit, par un clone frais -- c'est-a-dire ce
                # que voit la CI. La premiere version acceptait aussi
                # `os.path.exists`, donc elle passait sur MA machine (ou
                # state.json existe, genere a l'execution) et CRIAIT sur un
                # clone. Un controle qui crie a chaque run de CI est un controle
                # qu'on apprend a ignorer.
                #
                # Un fichier gitignore est ABSENT DU CLONE PAR CONSTRUCTION :
                # le README le decrit comme cree au vol, pas comme livre. Ce
                # n'est pas un renvoi mort.
                continue
            if cite not in morts:
                morts.append(cite)
        if morts:
            alerte(
                rel,
                "cite %d fichier(s) que le depot ne contient pas : %s. Un "
                "lecteur qui suit ce renvoi ne trouve rien -- exactement ce qui "
                "est arrive quand les notes internes ont ete retirees du suivi "
                "git alors que ce fichier y renvoyait encore."
                % (len(morts), ", ".join(morts[:6])),
            )


# Ce que les autres controles LISENT, et ce qui cesse d'etre verifie sans lui.
# Manifeste ajoute le 27/08/2026 -- voir controle_entrees_attendues_presentes().
ENTREES_ATTENDUES = {
    "BACKTEST_RESULTS.md":
        "la source de verite des chiffres. Sans elle, AUCUN chiffre des "
        "livrables n'est plus recoupe.",
    "STRATEGY_COMPARISON.md":
        "la comparaison des deux strategies : Sharpe in-sample, taux de "
        "succes, statut de fuite.",
    "README.md":
        "l'inventaire des agents et de leurs options, et les chiffres qu'il "
        "reprend de BACKTEST_RESULTS.md.",
    "requirements.txt":
        "les dependances scellees.",
    "decision_log.jsonl":
        "la preuve publiee : recherche d'identifiants et coherence des "
        "decisions.",
    "docs/data.json":
        "l'instantane publie : champs de compte et identifiants.",
    "submission/Hindsight_Alpha_Deck.pptx":
        "les chiffres du deck (plages, nombre d'equipes, verdicts de fuite).",
    "submission/Hindsight_Alpha_Writeup.docx":
        "les chiffres du write-up d'une page.",
    "launchagents":
        "les plists livres : validite XML et cles launchd.",
    "githooks":
        "les hooks pre-commit et pre-push.",
}


MOTIF_CLE_ALPACA = re.compile(r"\b[AP]K[A-Z0-9]{18}\b")
MOTIF_SECRET_AFFECTE = re.compile(
    r"(?i)\b[A-Za-z_]*(?:secret|token|api[_-]?key)[A-Za-z_]*[\"']?\s*[=:]\s*"
    r"[\"']?([A-Za-z0-9/+]{35,})")


def controle_motifs_d_identifiants() -> None:
    """Un identifiant Alpaca est-il present dans un fichier SUIVI, reconnu a
    sa FORME et non a sa valeur ?

    AJOUTE le 27/08/2026 sur decision de l'operateur, pour combler le trou
    mesure le meme jour : controle_aucun_identifiant_dans_les_fichiers_publies
    cherche par VALEUR EXACTE -- aucun faux positif possible, mais il faut
    avoir les valeurs sous la main. Il est donc INERTE en CI et sur tout clone.
    Reproduit dans un depot jetable : une fausse cle au format Alpaca y passait
    un commit NORMAL, hooks actifs.

    Les deux controles sont complementaires, aucun ne remplace l'autre :
      - par VALEUR : attrape n'importe quelle chaine, meme sans forme
        reconnaissable, mais seulement sur la machine qui detient les cles ;
      - par MOTIF (ici) : attrape les formes Alpaca partout, y compris en CI
        et apres un `git commit --no-verify`, mais rate ce qui ne ressemble
        pas a une cle.

    LE RISQUE ASSUME EST LE FAUX POSITIF, et c'est pourquoi ce depot l'avait
    refuse jusqu'ici : « un controle qui crie sur des valeurs bidon apprend a
    etre ignore ». Les motifs ont donc ete mesures DANS LES DEUX SENS avant
    d'etre poses -- 9 cas temoins, 0 ecart, 0 faux positif sur les 38 fichiers
    suivis :

        detecte     : cle paper/live collee dans un .py, cle nue en markdown,
                      secret affecte en .py / json / yaml
        NON detecte : SHA-1 de commit, placeholder « your_key_here », valeurs
                      factices des tests, prose contenant le mot « token »

    La cle d'API est reconnue precisement : « PK » (paper) ou « AK » (live)
    suivis de 18 alphanumeriques MAJUSCULES. Le secret fait 40 caracteres
    base64, indistinguable d'un hash, donc il n'est cherche QUE dans un
    contexte d'affectation nommee.

    BLOQUE : une cle poussee sur un depot public est publique pour toujours,
    et c'est le seul defaut irreversible que ce projet puisse produire."""
    try:
        suivis = subprocess.run(["git", "-C", RACINE, "ls-files"],
                                capture_output=True, text=True, timeout=30)
    except Exception as e:
        alerte("identifiants (motifs)",
               "impossible de lister les fichiers suivis (%s: %s) -- ce "
               "controle n'a RIEN verifie." % (type(e).__name__, e))
        return
    if suivis.returncode != 0:
        alerte("identifiants (motifs)",
               "`git ls-files` a echoue (code %d) -- ce controle n'a RIEN "
               "verifie." % suivis.returncode)
        return
    fichiers = [f for f in suivis.stdout.split() if f]
    if not fichiers:
        alerte("identifiants (motifs)",
               "aucun fichier suivi trouve -- ce controle n'a RIEN verifie.")
        return

    for relatif in fichiers:
        try:
            texte = open(os.path.join(RACINE, relatif),
                         encoding="utf-8", errors="replace").read()
        except (OSError, IsADirectoryError):
            continue
        for nom, motif in (("CLE D'API Alpaca", MOTIF_CLE_ALPACA),
                           ("SECRET affecte a un nom d'identifiant",
                            MOTIF_SECRET_AFFECTE)):
            for m in motif.finditer(texte):
                bloque(relatif,
                       "ligne %d : %s reconnu a sa FORME. Ce fichier est SUIVI "
                       "PAR GIT et part sur le depot PUBLIC. Retirer la valeur, "
                       "puis REVOQUER cette cle chez Alpaca -- si elle est deja "
                       "partie, elle est publique pour toujours."
                       % (texte[:m.start()].count("\n") + 1, nom))


def controle_entrees_attendues_presentes() -> None:
    """Un fichier que les autres controles LISENT a-t-il disparu ?

    AJOUTE le 27/08/2026, apres un balayage systematique : j'ai retire une a
    une les douze entrees de ce script dans un clone jetable. UNE SEULE
    absence sur douze etait signalee. Les onze autres passaient sans un mot --
    le controle concerne se contentait de ne rien verifier.

    CONSEQUENCE MESUREE, pas supposee, et plus mesuree que ce que je
    craignais. Avec une borne falsifiee dans BACKTEST_RESULTS.md :

        livrables en place        -> 🔴 3 bloquants
        deck et write-up renommes -> 🔴 2 bloquants  (toujours REFUSE)

    Le verdict TIENT. Ce qui disparait en silence, c'est un bloquant precis
    sur le write-up (« CONCENTRATION 68.5-82.6% ne correspond pas ») et
    l'alerte du deck. Le refus ne survit que parce que README.md reprend les
    memes chiffres -- une redondance heureuse, pas une protection concue. Sur
    un chiffre que seul le write-up porterait, il n'y aurait plus rien.

    Le scenario n'est pas tire par les cheveux : renommer un livrable au
    moment de le deposer sur lablab est la chose la plus naturelle du monde,
    et c'est exactement le moment ou ces recoupements comptent.

    ALERTE, jamais blocage. Un depot peut legitimement ne pas avoir tous ces
    fichiers -- ce controle ne dit pas « c'est faux », il dit « ceci n'a pas
    ete verifie ». Meme forme que l'aveu ajoute le meme jour au controle
    d'identifiants, et que controle_journal() pour PLAN_SPRINT.md absent.

    PLAN_SPRINT.md est deliberement absent du manifeste : il est gitignore, et
    son propre controle annonce deja son absence. L'y ajouter produirait une
    seconde alerte pour un etat parfaitement normal -- et un controle qui crie
    sur du normal s'apprend a ignorer."""
    manquants = [(nom, quoi) for nom, quoi in sorted(ENTREES_ATTENDUES.items())
                 if not os.path.exists(os.path.join(RACINE, nom))]
    for nom, quoi in manquants:
        # BLOQUANT depuis le 28/08/2026 -- c'etait `alerte`, donc jaune.
        # Mesure : supprimer BACKTEST_RESULTS.md, la source de verite de TOUS
        # les chiffres publies, donnait « 🟡 rien de bloquant » et un code de
        # sortie 0. La CI restait donc VERTE, et le hook pre-commit laissait
        # passer -- pendant que ce meme message annoncait « AUCUN chiffre des
        # livrables n'est plus recoupe ».
        #
        # Le message decrivait une panne bloquante ; le verdict disait le
        # contraire. Les deux ne pouvaient pas avoir raison.
        #
        # C'est la raison d'etre de ce manifeste : ces dix entrees ne sont pas
        # « souhaitables », leur absence REND MUETS d'autres controles. Un
        # controle devenu muet ne doit jamais etre annonce comme « rien de
        # bloquant » -- c'est la version « verdict » du 0.0 qui veut dire
        # « je n'ai pas pu mesurer ».
        #
        # Aucun faux positif possible : les dix sont suivies par git (verifie),
        # donc presentes dans tout clone et dans la CI.
        bloque(nom, "ABSENT — ce que plus rien ne verifie : %s Renomme, deplace "
                    "ou supprime ? Tant qu'il manque, les controles qui le "
                    "lisent ne disent RIEN, ni oui ni non." % quoi)


KICKOFF_UTC = "2026-08-28T15:00:00+00:00"
FICHIER_GEL = "kickoff_freeze.json"

# Les constantes GELEES au kickoff. Pas les seuils de risque seulement : tout
# ce dont la modification transformerait la semaine live en enieme backtest
# ajuste. Lues par IMPORT, pas par lecture de texte -- ce projet a deja appris
# qu'un controle qui cherche deux mots dans un fichier reste vert quand le
# comportement disparait.
CONSTANTES_GELEES = {
    "risk_gates": ("MAX_RISK_PCT_PER_TRADE", "MAX_TOTAL_RISK_PCT",
                   "MAX_SECTOR_EXPOSURE_PCT", "MAX_OPEN_POSITIONS",
                   "WEEKLY_LOSS_LOCK_PCT", "MAX_CONSECUTIVE_LOSSES",
                   "TAKE_PROFIT_PCT", "STOP_LOSS_PCT"),
    "vol_strategy": ("CANDIDATE_HV_WINDOWS", "CHEAP_VOL_PERCENTILE",
                     "RANK_LOOKBACK_DAYS", "IN_SAMPLE_HOLDOUT_DAYS",
                     "MIN_TRADING_DAYS_FOR_SWEEP"),
    "agent": ("DEFAULT_UNIVERSE",),
}


def _valeurs_gelees() -> dict:
    """L'empreinte des constantes, telle qu'elle est REELLEMENT chargee."""
    import importlib
    valeurs = {}
    for module, noms in CONSTANTES_GELEES.items():
        mod = importlib.import_module(module)
        for nom in noms:
            valeurs["%s.%s" % (module, nom)] = getattr(mod, nom)

    # La strategie LIVE : quel module fournit reellement today_regime a
    # agent.py. Comportemental -- une bascule vers momentum_strategy le
    # changerait, meme si l'import etait maquille.
    import agent
    valeurs["agent.strategie_live"] = agent.today_regime.__module__

    # Le seuil de Sharpe par defaut. Lu dans l'AST : construire le parser
    # demanderait d'executer main(). C'est structurel, pas une recherche de
    # mots dans de la prose.
    import ast
    with open(os.path.join(RACINE, "agent.py"), encoding="utf-8") as fh:
        arbre = ast.parse(fh.read())
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Call)
                and getattr(n.func, "attr", None) == "add_argument"
                and any(isinstance(a, ast.Constant) and a.value == "--sharpe-threshold"
                        for a in n.args)):
            for kw in n.keywords:
                if kw.arg == "default" and isinstance(kw.value, ast.Constant):
                    valeurs["agent.sharpe_threshold_defaut"] = kw.value.value
    return valeurs


def _ecrire_gel(chemin: str, valeurs: dict) -> None:
    from datetime import datetime, timezone
    with open(chemin, "w", encoding="utf-8") as fh:
        json.dump({"kickoff": KICKOFF_UTC,
                   "gele_le": datetime.now(timezone.utc).isoformat(),
                   "valeurs": valeurs}, fh, indent=2, sort_keys=True)
        fh.write("\n")


def controle_jobs_dans_la_fenetre_de_veille() -> None:
    """Chaque job programme tombe-t-il DANS la fenetre ou le Mac reste eveille ?

    AJOUTE le 28/08/2026. `controle_reveil_programme` verifie que la machine
    se REVEILLE avant la seance, et il cite meme la fenetre de veille --
    « 15:20 a 22:05 ». Mais personne n'avait verifie que les jobs tombent
    dedans.

    Mesure : la derniere publication du jour etait programmee a 22:05:00, et
    le verrou `caffeinate -t 24300` expirait a 22:05:00. Le verrou de veille
    se relachait a la SECONDE ou la derniere preuve de la seance devait
    s'ecrire.

    Le systeme ne s'endort pas instantanement -- le compteur d'inactivite
    repart ensuite -- donc ce job passait PROBABLEMENT. Se reposer sur ce
    probablement est exactement ce que ce depot traque partout ailleurs.

    La fenetre a ete portee a 25200 s (22:20). Ce controle empeche qu'un job
    ajoute plus tard retombe dehors sans que personne ne s'en apercoive : le
    calcul est refait a partir des plists eux-memes, jamais d'un chiffre
    recopie ici.

    ALERTE et non blocage : c'est une question de planification locale, pas un
    defaut du dossier livre.
    """
    import plistlib
    dossier = os.path.join(RACINE, "launchagents")
    if not os.path.isdir(dossier):
        return
    fenetre, jobs = None, []
    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith(".plist"):
            continue
        try:
            with open(os.path.join(dossier, nom), "rb") as fh:
                p = plistlib.load(fh)
        except Exception as e:
            alerte(nom, "illisible (%s) — la couverture de veille n'a PAS pu "
                        "etre verifiee" % type(e).__name__)
            continue
        args = p.get("ProgramArguments", [])
        intervalles = p.get("StartCalendarInterval", [])
        if isinstance(intervalles, dict):
            intervalles = [intervalles]
        minutes = sorted((d.get("Hour", 0) * 60 + d.get("Minute", 0))
                         for d in intervalles)
        if not minutes:
            continue
        if "caffeinate" in " ".join(args):
            duree = None
            for i, a in enumerate(args):
                if a == "-t" and i + 1 < len(args):
                    try:
                        duree = int(args[i + 1])
                    except ValueError:
                        duree = None
            if duree is None:
                alerte(nom, "caffeinate sans duree `-t` lisible — impossible de "
                            "savoir jusqu'a quand la machine reste eveillee")
                return
            fenetre = (minutes[0], minutes[0] + duree // 60)
        else:
            jobs.append((nom, minutes[0], minutes[-1]))

    if fenetre is None:
        return  # pas d'agent de veille : rien a comparer

    debut, fin = fenetre
    for nom, premier, dernier in jobs:
        if premier < debut or dernier >= fin:
            alerte(nom,
                   "job programme de %02d:%02d a %02d:%02d, hors de la fenetre "
                   "de veille %02d:%02d-%02d:%02d (ou a son bord exact). Le "
                   "verrou de veille peut se relacher au moment meme ou ce job "
                   "doit s'executer."
                   % (premier // 60, premier % 60, dernier // 60, dernier % 60,
                      debut // 60, debut % 60, fin // 60, fin % 60))


def controle_garde_de_compte_actif() -> None:
    """Les trois gardes de compte protegent-ils vraiment cette machine ?

    AJOUTE le 28/08/2026, apres avoir pose ces gardes le matin meme dans
    check_gates (entrees), manage_exits (sorties) et build_snapshot
    (publication). Tous les trois s'appuient sur `config.ACCOUNT_ID`, et tous
    les trois se DEGRADENT en simple avertissement quand il est absent -- a
    dessein : sans compte declare il n'y a rien a comparer, et refuser
    paralyserait un dossier qui n'en declare pas.

    Mais cet avertissement part sur la sortie standard, c'est-a-dire, sous
    launchd, dans un fichier de log que personne ne regarde. Une protection
    inerte qui ne le dit qu'a un log est une protection dont on croit
    disposer.

    Le controle ne se declenche QUE si des identifiants sont charges : c'est
    ce qui distingue « la machine qui trade » d'un clone ou de la CI, ou
    l'absence de ACCOUNT_ID est normale et ou alerter serait du bruit. Meme
    discrimination que le controle d'identifiants, et pour la meme raison.

    `test_connection.py` couvre deja le cas a la main (verdict
    « NON VERIFIE »), mais c'est un script qu'il faut penser a lancer -- le
    trou exact que ce garde-fou existe pour combler ailleurs.
    """
    try:
        import config
    except Exception as e:
        alerte("config.py", "illisible (%s) — impossible de verifier si le "
                            "garde de compte est actif" % type(e).__name__)
        return

    identifiants_charges = bool(getattr(config, "API_KEY", None)
                                and getattr(config, "SECRET_KEY", None))
    if not identifiants_charges:
        return  # clone ou CI : rien a dire, c'est l'etat normal

    if not getattr(config, "ACCOUNT_ID", None):
        alerte("ALPACA_ACCOUNT_ID",
               "ABSENT alors que des identifiants SONT charges : les trois "
               "gardes de compte (entrees, sorties, publication) se degradent "
               "en simple avertissement et ne protegent RIEN sur cette "
               "machine. Rien n'empeche alors de trader, de cloturer ou de "
               "publier sur un compte qui n'est pas celui prevu. "
               "Declare-le dans le fichier de configuration (voir le modele).")


def controle_gel_des_parametres_au_kickoff() -> None:
    """Les parametres de decision ont-ils bouge depuis le kickoff ?

    AJOUTE le 27/08/2026, la veille du kickoff, a la demande de Spap.

    POURQUOI. Rien dans les regles n'interdit de modifier le code pendant la
    semaine -- la seule echeance est le 04/09. Mais la semaine live est le SEUL
    resultat vraiment hors echantillon de tout le dossier. Toucher un seuil ou
    une fenetre candidate en cours de route la transformerait en enieme
    backtest ajuste : exactement l'erreur que ce projet existe pour denoncer.

    Ce controle ne l'empeche pas -- rien ne peut empecher un `git commit`. Il
    le rend VISIBLE et AUTO-DECLARE, au lieu d'etre decouvert par un juge qui
    lit l'historique. « Voici le controle qui m'aurait attrape » vaut mieux que
    « je promets de ne pas avoir touche ».

    LA PROPRIETE QUI COMPTE. Apres le kickoff, ce controle ne se re-calibre
    JAMAIS tout seul. Un gel qui regenere sa propre reference des qu'elle ne
    correspond plus ne gele rien du tout -- c'est du theatre, et ce serait la
    version « controle » du 0.0 qui veut dire « je n'ai pas pu mesurer ».
    Avant le kickoff, au contraire, ajuster est legitime : la reference suit.

    Le fichier de reference est COMMITE : le modifier apres coup laisse une
    trace dans l'historique public, qui est lui-meme la preuve.
    """
    from datetime import datetime, timezone

    chemin = os.path.join(RACINE, FICHIER_GEL)
    kickoff = datetime.fromisoformat(KICKOFF_UTC)
    apres_kickoff = datetime.now(timezone.utc) >= kickoff

    try:
        actuelles = _valeurs_gelees()
    except Exception as e:
        bloque(FICHIER_GEL, "impossible de lire les constantes gelees (%s: %s) — "
                            "le gel ne peut pas être vérifié"
                            % (type(e).__name__, e))
        return

    if not os.path.exists(chemin):
        if apres_kickoff:
            bloque(FICHIER_GEL,
                   "ABSENT alors que le kickoff est passé — la référence du gel "
                   "a disparu, donc plus rien ne prouve que les paramètres n'ont "
                   "pas bougé. Ne pas la régénérer : la restaurer depuis git.")
            return
        _ecrire_gel(chemin, actuelles)
        alerte(FICHIER_GEL, "référence du gel créée (%d constantes) — avant le "
                            "kickoff, c'est normal. À committer."
                            % len(actuelles))
        return

    try:
        with open(chemin, encoding="utf-8") as fh:
            reference = json.load(fh)
        attendues = reference["valeurs"]
    except Exception as e:
        bloque(FICHIER_GEL, "illisible (%s) — le gel ne peut pas être vérifié"
                            % type(e).__name__)
        return

    derives = []
    for cle in sorted(set(attendues) | set(actuelles)):
        avant, apres = attendues.get(cle, "<absente>"), actuelles.get(cle, "<absente>")
        if avant != apres:
            derives.append("%s : %r -> %r" % (cle, avant, apres))

    if not derives:
        return  # vert, silencieux

    if apres_kickoff:
        bloque(FICHIER_GEL,
               "%d paramètre(s) de décision ont CHANGÉ depuis le kickoff — %s. "
               "La semaine live est le seul résultat hors échantillon du "
               "dossier ; la modifier en cours de route en fait un backtest "
               "ajusté." % (len(derives), " | ".join(derives)))
        return

    _ecrire_gel(chemin, actuelles)
    alerte(FICHIER_GEL, "%d paramètre(s) modifiés AVANT le kickoff — légitime, "
                        "référence mise à jour (%s). À committer."
                        % (len(derives), " | ".join(derives)))


def controle_plists_sont_du_xml_valide() -> None:
    """Les plists livres sont-ils du XML que N'IMPORTE QUEL parseur accepte ?

    AJOUTE le 27/08/2026. Trouve en essayant simplement de lire les trois
    plists avec plistlib : deux passent, le troisieme leve
    « not well-formed (invalid token): line 21, column 57 ».

    La cause : un « -- » a l'interieur d'un COMMENTAIRE XML. La specification
    XML l'interdit, sans exception. Le mien venait d'une phrase francaise
    ordinaire (« la docstring -- que ce paragraphe declare perimee ») dans le
    commentaire qui explique pourquoi `--git-push` est la. Ecrit par moi le
    matin meme, en retablissant cette option.

    POURQUOI CE N'EST PAS BENIN, ET POURQUOI CE N'EST PAS GRAVE NON PLUS.
    `plutil -lint` repond OK sur les trois : le parseur d'Apple
    (CoreFoundation) tolere la faute. launchd utilise ce meme parseur, donc le
    job SE CHARGE et l'automatisation fonctionne -- mesure, pas suppose.

    Mais le depot LIVRE ces fichiers : le README dit de les copier dans
    ~/Library/LaunchAgents. Tout outil strict -- plistlib, xmllint, la plupart
    des validateurs d'editeur, une CI qui verifie les plists -- les refuse.
    Un fichier « valide seulement sur mon Mac » est precisement le genre
    d'hypothese silencieuse que ce projet passe son temps a debusquer
    ailleurs.

    Le controle ALERTE, il ne bloque pas : l'automatisation tourne, rien n'est
    en danger. Il refuse simplement de laisser passer un fichier livre qui
    n'est pas ce qu'il pretend etre.

    On verifie aussi les cles dont launchd a besoin. Un plist parfaitement
    bien forme mais sans Label ne se charge pas -- et l'erreur, elle,
    n'apparait que dans les logs systeme."""
    import plistlib

    dossier = os.path.join(RACINE, "launchagents")
    if not os.path.isdir(dossier):
        return
    trouves = sorted(n for n in os.listdir(dossier) if n.endswith(".plist"))
    if not trouves:
        # Le dossier existe mais est vide : ce controle ne verifie alors RIEN.
        # Le dire plutot que de rendre un vert qui ne veut rien dire.
        alerte("launchagents/", "dossier present mais AUCUN .plist dedans -- "
                                "ce controle n'a rien verifie.")
        return

    for nom in trouves:
        chemin = os.path.join(dossier, nom)
        try:
            with open(chemin, "rb") as fh:
                donnees = plistlib.load(fh)
        except Exception as e:
            alerte("launchagents/%s" % nom,
                   "XML INVALIDE pour un parseur strict (%s: %s). `plutil -lint` "
                   "l'accepte -- le parseur d'Apple tolere la faute, donc launchd "
                   "charge quand meme le job -- mais ce fichier est LIVRE et le "
                   "README dit de le copier. Cause la plus frequente : un « -- » "
                   "a l'interieur d'un commentaire <!-- ... -->, que la "
                   "specification XML interdit."
                   % (type(e).__name__, e))
            continue
        for cle in ("Label", "ProgramArguments"):
            if not donnees.get(cle):
                alerte("launchagents/%s" % nom,
                       "cle launchd « %s » absente ou vide : le job ne se "
                       "chargera pas, et l'erreur n'apparaitra que dans les "
                       "logs systeme." % cle)


def controle_le_refus_annonce_tient_dans_le_journal() -> None:
    """Le README annonce qu'un symbole est refuse A CHAQUE PASSAGE. Le
    journal le confirme-t-il encore ?

    AJOUTE le 29/08/2026. C'est la revendication la plus visible du dossier
    -- elle apparait QUATRE FOIS dans le README, dont le tableau de tete et
    le diagramme -- et c'est aussi la plus fragile : mesure du meme jour, le
    desaccord de XLK se joue a 0,024 de Sharpe entre deux fenetres
    candidates, et il DISPARAIT si l'on interroge le flux IEX au lieu du
    flux SIP. Quelques seances de donnees nouvelles peuvent le retourner.

    Si cela arrive pendant la semaine jugee, la premiere ligne que lit un
    juge devient fausse et PERSONNE NE LE VERRAIT : le tableau de bord
    afficherait simplement un verdict de plus, vert au lieu de rouge.

    Verifie le 29/08 sur le journal committe : 15 verdicts XLK, 15 refus,
    tous par le garde anti-retrospection, zero retenu. Un seizieme passage
    n'evaluait pas XLK -- il date du 24/08, avant que ce symbole entre dans
    l'univers.

    AUCUNE LISTE RECOPIEE : l'univers est lu dans agent.py, le symbole
    revendique est lu dans le README, et le resultat est lu dans le journal.
    Ce controle ne sait rien de « XLK » par lui-meme.

    TROIS ISSUES, et la troisieme est celle qui compte :
      . tous refuses            -> rien a dire ;
      . un seul retenu          -> alerte nommant la date ;
      . AUCUN verdict trouve    -> alerte aussi. « Je n'ai pas pu verifier »
        n'est pas « c'est verifie » -- surtout pour la phrase de tete."""
    chemin_journal = os.path.join(RACINE, "decision_log.jsonl")
    if not os.path.exists(chemin_journal):
        return
    univers = _univers_de_l_agent()
    if not univers:
        alerte("agent.py", "DEFAULT_UNIVERSE n'a pas pu etre lu : la "
                           "revendication « refuse a chaque passage » n'a PAS "
                           "ete verifiee.")
        return
    # LES DEUX SURFACES QUE LIT UN JUGE, pas seulement le README. Ajoute dans
    # la demi-heure qui a suivi la premiere version de ce controle : elle ne
    # lisait que README.md, alors que docs/index.html porte la MEME phrase
    # (« XLK earns it on every run », dans « How to read this page »). Une
    # regle appliquee a un fichier et pas a son jumeau -- le motif meme que
    # le controle 20 detecte a cote, retrouve dans le controle 21 vingt
    # minutes apres l'avoir ecrit.
    for rel in ("README.md", os.path.join("docs", "index.html")):
        chemin = os.path.join(RACINE, rel)
        if not os.path.exists(chemin):
            continue
        texte = open(chemin, encoding="utf-8", errors="replace").read()
        for sym in univers:
            if not _revendique_un_refus_permanent(texte, sym):
                continue
            total, retenus = _verdicts_du_journal(chemin_journal, sym)
            if total == 0:
                alerte(rel,
                       "annonce que %s est refuse a CHAQUE passage, et le "
                       "journal ne contient AUCUN verdict pour ce symbole : "
                       "la phrase n'est pas verifiee, elle est invérifiable "
                       "ici." % sym)
            elif retenus:
                alerte(rel,
                       "annonce que %s est refuse a CHAQUE passage, mais le "
                       "journal contient %d verdict(s) OU IL EST RETENU (%s) "
                       "sur %d. Ce que lit un juge n'est plus vrai."
                       % (sym, len(retenus), ", ".join(retenus[:3]), total))


def _revendique_un_refus_permanent(texte: str, symbole: str) -> bool:
    """Ce texte affirme-t-il que `symbole` est refuse a CHAQUE passage ?

    On exige les deux dans la meme fenetre de 90 caracteres : le symbole et
    un mot de refus. Sans cela, le separateur du kickoff -- « Nothing is
    hidden — every run this project ever logged is still here » -- serait
    pris pour une revendication."""
    for m in re.finditer(r"every run", texte, re.I):
        avant = texte[max(0, m.start() - 90):m.start()]
        if (re.search(r"\b%s\b" % re.escape(symbole), avant)
                and re.search(r"refus", avant, re.I)):
            return True
    return False


def _univers_de_l_agent() -> list:
    """DEFAULT_UNIVERSE, lu dans agent.py par l'arbre syntaxique -- pas
    importe (agent.py a des effets de bord au chargement) et pas recopie."""
    try:
        with open(os.path.join(RACINE, "agent.py"), encoding="utf-8") as fh:
            arbre = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Assign):
            continue
        if not any(getattr(t, "id", "") == "DEFAULT_UNIVERSE" for t in n.targets):
            continue
        if not isinstance(n.value, (ast.List, ast.Tuple)):
            return []
        return [e.value for e in n.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _verdicts_du_journal(chemin: str, symbole: str) -> "tuple[int, list]":
    """(nombre de verdicts pour ce symbole, dates de ceux ou il est RETENU).

    Une ligne illisible est sautee : le journal est append-only et porte des
    formes anciennes. Ce qui compte ici est de ne jamais compter un verdict
    inexistant, pas de tout lire."""
    total, retenus = 0, []
    try:
        with open(chemin, encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    e = json.loads(ligne)
                except (ValueError, TypeError):
                    continue
                if not isinstance(e, dict):
                    continue
                for v in (e.get("verdicts") or []):
                    if not isinstance(v, dict) or v.get("symbol") != symbole:
                        continue
                    total += 1
                    if v.get("tradeable"):
                        retenus.append(str(e.get("timestamp"))[:19])
    except OSError:
        return 0, []
    return total, retenus


def controle_pannes_traitees_symetriquement() -> None:
    """Une meme fonction traite-t-elle ses pannes JUMELLES de la meme facon ?

    AJOUTE le 29/08/2026, apres avoir trouve QUATRE FOIS DANS LA JOURNEE le
    meme motif a la main : une regle appliquee a une branche et pas a sa
    jumelle.

        bilan_semaine     une fenetre de gel illisible arretait le script ;
                          un JOURNAL illisible, non -- il accusait l agent
                          d avoir manque ses passages
        verifier_kickoff  les FICHIERS plist etaient compares ; l etat
                          CHARGE, non -- la ligne s appelait pourtant
                          « LaunchAgents charges »
        verifier_kickoff  un comptage git reussi etait lu ; un ECHEC de git
                          rendait la meme chaine vide, lue comme « zero »
        publish_dashboard un commit refuse et un push EXPIRE etaient
                          expliques ; un push REJETE remontait sans un mot

    Une regle qu on se rappelle ne vaut rien face a une regle que l outil
    applique -- c est ce que dit ce fichier depuis le 25/08 a propos de
    lui-meme. Ce controle applique enfin cette phrase au motif qui a produit
    le plus de defauts de la semaine.

    CE QU IL VOIT, ET C EST UNE SEULE DES QUATRE FORMES : dans une meme
    fonction, plusieurs `subprocess.run(..., check=True)` dont CERTAINS sont
    enveloppes d un handler qui attrape CalledProcessError et d autres non.
    C est exactement la quatrieme ligne du tableau ci-dessus, et c est la
    seule des quatre qui se lise dans un arbre syntaxique.

    CE QU IL NE VOIT PAS, dit ici plutot que sous-entendu : les trois autres
    formes sont SEMANTIQUES -- un message qui nomme une cause non mesuree,
    une valeur de repli confondue avec une mesure, un titre qui promet plus
    que le test. Aucune ne se detecte sans heuristique, et une heuristique
    qui se trompe sur ce fichier bloquerait des commits justes. Ce controle
    couvre un quart du motif, et le dire fait partie du controle.

    NON BLOQUANT : une asymetrie est une piste, pas une preuve. Elle peut
    etre deliberee -- encore faut-il l avoir decidee."""
    for rel, fonction in _fonctions_du_depot(
            "la symetrie des pannes", "aucune asymetrie trouvee"):
        couverts, nus = _appels_verifies(fonction)
        if couverts and nus:
            alerte(
                rel,
                "dans %s(), %d appel(s) subprocess check=True sont "
                "proteges par un handler et %d ne le sont pas (ligne(s) "
                "%s) : une panne jumelle remonterait sans explication."
                % (fonction.name, len(couverts), len(nus),
                   ", ".join(str(l) for l in nus)))


def _fuseau_garanti(fonction: ast.AST) -> "str | None":
    r"""Cette fonction analyse-t-elle un horodatage ISO sans garantir son
    fuseau ? Rend le motif de l'alerte, ou None si elle est en regle.

    `datetime.fromisoformat("2026-08-28T14:00:00")` ne leve RIEN : elle rend
    un datetime naif. La panne arrive une ligne plus loin, a la comparaison,
    avec « can't compare offset-naive and offset-aware datetimes ». Le `try`
    qu'on met autour de l'analyse ne l'attrape donc jamais -- il est vise une
    ligne trop tot.

    QUATRE PARADES SONT ACCEPTEES, parce que les quatre existent dans ce
    depot et sont justes :

      . normaliser -- `t.replace(tzinfo=...)` ou un test `t.tzinfo is None`
        (`agent.py`, `bilan_semaine.py`, `alpaca_cli.py`) ;
      . rattraper le `TypeError` de la comparaison (`monitor_exits.py`, qui
        le nomme et explique pourquoi il traite le cas comme « du », pas
        comme « silencieux ») ;
      . analyser une CONSTANTE en majuscules (`garde_fou.py` lui-meme, avec
        `KICKOFF_UTC`, un litteral qui porte son fuseau et ne peut pas
        deriver).

    UNE FORME EST TOUJOURS SIGNALEE, meme si elle ressemble a une parade :
    `datetime.now(valeur_analysee.tzinfo)`. C'est astucieux -- ca ne leve
    jamais de TypeError -- et c'est le defaut mesure le 29/08/2026 dans la
    porte de fraicheur d'`alpaca_cli.py` : quand la valeur est naive,
    `tzinfo` vaut None, `datetime.now(None)` rend l'heure LOCALE, et le
    verdict d'une porte de donnees se met a dependre du fuseau de la machine.
    Sur une barre vieille de 5 j 3 h et une limite de 5 jours : REFUSE a
    Paris et a UTC, ACCEPTE a Los Angeles et a Honolulu. Cette expression
    n'evite pas le probleme, elle le rend silencieux -- et du cote qui
    AUTORISE.

    POURQUOI CE CONTROLE EXISTE : c'est la CINQUIEME occurrence en une
    session du motif « une regle appliquee ici mais pas a son jumeau », et la
    seconde qui se lise dans un arbre syntaxique. Rejoue sur l'arbre tel
    qu'il etait avant les corrections du 29/08, cette regle crie sur les
    trois sites fautifs et sur eux seuls ; rejouee sur l'arbre corrige, elle
    se tait entierement. C'etait la condition pour l'ajouter : une alerte
    qu'on ne peut pas resoudre apprend a ignorer les alertes.

    Lu dans l'ARBRE et non en sous-chaines, apres mesure : la version en
    sous-chaines exemptait `alpaca_cli._horodatage_utc` parce que sa
    docstring CITE le defaut qu'elle corrige."""
    analyse = normalise = rattrape = constante = False
    now_sur_le_fuseau = False
    for n in ast.walk(fonction):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr == "fromisoformat":
                analyse = True
                premier = n.args[0] if n.args else None
                if isinstance(premier, ast.Name) and premier.id.isupper():
                    constante = True
            if n.func.attr == "replace" and any(k.arg == "tzinfo"
                                                for k in n.keywords):
                normalise = True
            if n.func.attr == "now":
                for a in n.args:
                    if isinstance(a, ast.Attribute) and a.attr == "tzinfo":
                        now_sur_le_fuseau = True
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Attribute) \
                and n.left.attr == "tzinfo":
            normalise = True
        if isinstance(n, ast.ExceptHandler) and n.type is not None:
            for t in ast.walk(n.type):
                if isinstance(t, ast.Name) and t.id == "TypeError":
                    rattrape = True
    if not analyse:
        return None
    if now_sur_le_fuseau:
        return ("lit le fuseau SUR la valeur analysee pour fabriquer now() : "
                "quand l'horodatage est naif, c'est l'heure LOCALE de la "
                "machine qui sert de reference, et le verdict se met a "
                "dependre du fuseau ou tourne l'agent")
    if normalise or rattrape or constante:
        return None
    return ("analyse un horodatage ISO sans garantir son fuseau : un "
            "horodatage naif ne fait pas echouer l'analyse, il fait echouer "
            "la COMPARAISON une ligne plus loin")


def controle_horodatages_toujours_conscients_du_fuseau() -> None:
    """Un horodatage analyse doit toujours porter son fuseau — voir
    `_fuseau_garanti` pour ce qui est accepte et pourquoi.

    NON BLOQUANT : comme le controle des pannes jumelles, une absence de
    parade est une piste. Elle peut etre deliberee — encore faut-il l'avoir
    decidee."""
    for rel, fonction in _fonctions_du_depot(
            "les fuseaux horaires", "aucun horodatage naif"):
        motif = _fuseau_garanti(fonction)
        if motif:
            alerte(rel, "dans %s(), %s." % (fonction.name, motif))


def _appels_verifies(fonction: ast.AST) -> "tuple[list, list]":
    """(lignes protegees, lignes nues) des `subprocess.run(check=True)` de
    cette fonction. « Protege » = enveloppe d'un `try` dont un handler
    attrape CalledProcessError, Exception, ou tout.

    RECRIT le 29/08/2026, une heure apres sa premiere version, qui comptait
    CERTAINS appels DES DEUX COTES. Elle notait un noeud puis descendait
    dedans : un `try` niche dans une boucle etait donc parcouru deux fois,
    une fois par le marquage du noeud parent (etat « nu ») et une fois par la
    descente (etat « protege »). Cas construit :

        def f(y, a, b):
            for x in y:
                try:
                    subprocess.run(a, check=True)   # ligne 6
                except Exception:
                    pass
            subprocess.run(b, check=True)

        proteges = [6]      nus = [6, 9]

    Le rapport aurait donc nomme la ligne 6 comme non protegee, alors qu'elle
    l'est -- une accusation que le controle n'avait pas mesuree, dans le
    controle ecrit pour trouver exactement ce defaut-la. Aucune occurrence
    dans ce depot aujourd'hui, verifie : le bug etait latent, a un
    refactoring pres.

    Chaque noeud est desormais visite UNE fois, avec son etat de protection."""
    couverts, nus = [], []
    ATTRAPENT = {"Exception", "BaseException", "subprocess.CalledProcessError",
                 "CalledProcessError"}

    def _attrape(essai: ast.Try) -> bool:
        for h in essai.handlers:
            if h.type is None:
                return True
            noms = ({ast.unparse(e) for e in h.type.elts}
                    if isinstance(h.type, ast.Tuple) else {ast.unparse(h.type)})
            if noms & ATTRAPENT:
                return True
        return False

    def _est_run_verifie(appel: ast.Call) -> bool:
        if not ast.unparse(appel.func).endswith("subprocess.run"):
            return False
        return any(k.arg == "check" and isinstance(k.value, ast.Constant)
                   and k.value.value is True for k in appel.keywords)

    def visiter(noeud, protege):
        # Une fonction imbriquee a ses propres jumelles : on ne melange pas.
        if (isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef))
                and noeud is not fonction):
            return
        if isinstance(noeud, ast.Call) and _est_run_verifie(noeud):
            (couverts if protege else nus).append(noeud.lineno)
        if isinstance(noeud, ast.Try):
            dedans = protege or _attrape(noeud)
            for x in noeud.body:
                visiter(x, dedans)
            for x in noeud.handlers + noeud.orelse + noeud.finalbody:
                visiter(x, protege)
            return
        for enfant in ast.iter_child_nodes(noeud):
            visiter(enfant, protege)

    visiter(fonction, False)
    return sorted(set(couverts)), sorted(set(nus))


_ARBRES_DU_DEPOT = {}


def _fonctions_du_depot(quoi: str, sinon: str):
    """Les (fichier, fonction) de tout le dossier, arbre syntaxique deja lu.

    SORTI EN GENERATEUR le 30/08/2026. Les deux controles qui lisent l'AST --
    la symetrie des pannes et les fuseaux horaires -- avaient chacun leur
    copie de cet echafaudage : meme ouverture, meme `ast.parse`, meme
    `except (OSError, SyntaxError)` suivi de la meme alerte, meme `ast.walk`.
    Seule la regle par fonction differait.

    Le vrai cout n'etait pas le temps (les 21 fichiers etaient parses deux
    fois, 60 ms sur 1,5 s). C'etait qu'une propriete jamais ecrite --
    « un fichier illisible n'est pas un fichier propre » -- se trouvait
    implementee DEUX FOIS. Un troisieme controle AST l'aurait implementee une
    troisieme fois, ou pas du tout. C'est le motif meme que
    `controle_pannes_traitees_symetriquement` a ete ecrit pour attraper,
    dans le fichier qui l'attrape.

    `quoi` et `sinon` rendent le message d'alerte identique au caractere
    pres a ce que chaque controle disait deja."""
    for rel, chemin in _fichiers_python_du_depot():
        if chemin not in _ARBRES_DU_DEPOT:
            try:
                with open(chemin, encoding="utf-8") as fh:
                    _ARBRES_DU_DEPOT[chemin] = ast.parse(fh.read())
            except (OSError, SyntaxError):
                _ARBRES_DU_DEPOT[chemin] = None
        arbre = _ARBRES_DU_DEPOT[chemin]
        if arbre is None:
            # Ni vert ni silencieux : un fichier qu on ne sait pas lire n a
            # pas « aucune asymetrie ». L alerte part dans CHAQUE controle,
            # meme si le fichier n est lu qu une fois.
            alerte(rel, "n'a pas pu etre analyse pour %s — ce n'est pas "
                        "« %s »." % (quoi, sinon))
            continue
        for fonction in [n for n in ast.walk(arbre)
                         if isinstance(n, (ast.FunctionDef,
                                           ast.AsyncFunctionDef))]:
            yield rel, fonction


def _fichiers_python_du_depot() -> list:
    """Les .py suivis par git, hors tests : ce sont eux qui tournent."""
    out = []
    for nom in sorted(os.listdir(RACINE)):
        if not nom.endswith(".py") or nom.startswith("test_"):
            continue
        out.append((nom, os.path.join(RACINE, nom)))
    return out


def main() -> int:
    print("=" * 74)
    print("GARDE-FOU — hindsight-alpha — %s" % datetime.now().strftime("%d/%m/%Y %H:%M"))
    print("=" * 74)

    # La liste, plutot que sept appels alignes : le nombre de controles est
    # affiche en bas de ce meme script, et il a deja PERIME DEUX FOIS -- le
    # commentaire y admet lui-meme qu'il « trainait encore a 4 » et qu'il a
    # fallu une revue croisee pour le voir. Un chiffre recopie a la main perime ;
    # un chiffre derive de la realite, non. len(CONTROLES) est desormais la
    # seule source.
    CONTROLES = (
        controle_motifs_d_identifiants,
        controle_entrees_attendues_presentes,
        controle_plists_sont_du_xml_valide,
        controle_gel_des_parametres_au_kickoff,
        controle_garde_de_compte_actif,
        controle_jobs_dans_la_fenetre_de_veille,
        controle_journal,
        controle_env_hackathon_scelle,
        controle_garde_live_trading,
        controle_chiffres_perimes,
        controle_source_de_verite,
        controle_dependances_scellees,
        controle_hooks_actifs,
        controle_nombre_de_tests_annonce,
        controle_verrou_dit_hebdomadaire,
        controle_readme_decrit_les_agents,
        controle_aucun_identifiant_dans_les_fichiers_publies,
        controle_reveil_programme,
        controle_renvois_resolvent,
        controle_pannes_traitees_symetriquement,
        controle_horodatages_toujours_conscients_du_fuseau,
        controle_le_refus_annonce_tient_dans_le_journal,
        controle_ancres_resolvent,
    )
    for controle in CONTROLES:
        controle()

    if blocages:
        print("🔴 BLOQUANT : %d" % len(blocages))
        for fichier, message in blocages:
            print("   %-45s %s" % (fichier, message))
        print()
    if alertes:
        print("🟡 À REGARDER : %d" % len(alertes))
        for fichier, message in alertes:
            print("   %-45s %s" % (fichier, message))
        print()

    print("-" * 74)
    if blocages:
        print("VERDICT : 🔴 REFUSÉ — corrige le dossier, jamais ce script, pour faire taire ça.")
        return 1
    if alertes:
        print("VERDICT : 🟡 À VÉRIFIER — rien de bloquant, mais relis les points ci-dessus.")
        code = 0
    else:
        print("VERDICT : 🟢 APPROUVÉ — aucun contrôle en défaut.")
        code = 0

    # Affiché à CHAQUE run, même vert : le nombre de contrôles est maintenant DÉRIVÉ de
    # la liste CONTROLES ci-dessus (27/08). Il était recopié à la main et a
    # périmé deux fois — ce commentaire admettait lui-même qu'il « trainait
    # encore à 4 » après le passage à 6, trouvé par une revue croisée. Tous
    # sont nés d'erreurs déjà trouvées, jamais d'une anticipation. Un dossier approuvé
    # peut encore être faux sur tout ce que ce script ne sait pas encore
    # chercher.
    #
    # 🟢 CORRIGÉ le 26/08/2026, sur demande explicite : le trou XLK
    # (contrôle 5 excluait par construction les symboles en fuite de ses
    # plages mécaniques — trouvé le 25/08 en revue croisée, corrigé dans
    # README.md mais pas encore comblé mécaniquement) est désormais fermé
    # pour les citations en PROSE (hors tableau) d'un symbole en fuite — la
    # forme exacte du bug d'origine. Témoin : « XLK's 181.6% » (l'ancien
    # chiffre faux) déclenche un vrai blocage 🔴 ; restauré à 136.7%, silence.
    # Portée volontairement étroite (un seul pourcentage isolé, avec ancre
    # win-rate/concentration à proximité) pour ne pas rouvrir les mêmes bugs
    # de proximité regex déjà trouvés ailleurs dans ce contrôle — voir le
    # commentaire juste au-dessus de la boucle `for symbole, attendu in
    # fuites.items()` dans controle_source_de_verite(), et PLAN_SPRINT.md.
    print()
    print("  ⚠️  Même au vert : ce script attrape %d formes d'erreur précises,"
          % len(CONTROLES))
    print("     pas le fond. Un dossier qu'il approuve peut encore être faux.")
    return code


if __name__ == "__main__":
    sys.exit(main())
