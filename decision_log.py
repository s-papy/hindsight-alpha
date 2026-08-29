# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

"""Append-only log of every agent run's decisions — one JSON object per line
in decision_log.jsonl. This is what the hosted dashboard reads to show a
history, not just today's snapshot, and it's also the raw material for the
one-page write-up and the demo video ("here's what it decided and why,
every day this week").

Not gitignored deliberately — unlike state.json (private run-state) this
log is meant to be committed and published, it's evidence of the agent's
reasoning over the week, not a secret.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Encodage EXPLICITE partout ou un fichier texte est lu ou ecrit (27/08/2026).
# Sans lui, Python utilise celui de la locale. Mesure : sur macOS il rend
# UTF-8 quoi qu'il arrive -- meme sous `env -i`, meme avec LANG=C -- donc le
# defaut n'est PAS atteignable sur la plateforme cible. Mais la CI tourne sur
# Linux, ou LANG=C donne de l'ASCII, et un juge qui clone dans un conteneur
# (ou LANG est souvent absent) est dans ce cas la.
#
# Demontre plutot qu'affirme, avec un codec ascii force :
#   ecriture -> UnicodeEncodeError sur le premier caractere accentue
#   lecture  -> UnicodeDecodeError sur le meme octet
#
# La consequence porte sur la PREUVE PUBLIEE : log_run() leverait et
# l'enregistrement serait perdu du fichier, read_log() leverait et le tableau
# de bord ne se construirait plus.
LOG_FILE = Path(__file__).parent / "decision_log.jsonl"

# NOTE 26/08/2026 : read_log() citait plus bas un troisieme exemple du principe
# « un mauvais enregistrement ne doit pas tout emporter » -- _total_committed()
# comptant un cost_basis illisible comme $0 plutot que de bloquer. Cet exemple a
# ete RETIRE parce que ce n'en etait pas un : mesure le meme jour, ce $0 ne
# faisait pas qu'isoler une donnee illisible, il agrandissait le budget de risque
# (les deux plafonds d'exposition reposent sur cette somme). check_gates refuse
# desormais une entree nouvelle dans ce cas. La distinction vaut d'etre gardee
# ici : isoler un enregistrement illisible d'un JOURNAL est benin, traiter une
# valeur illisible comme un ZERO dans un CALCUL DE RISQUE ne l'est pas. Le meme
# mot -- « degrader proprement » -- couvrait les deux.

# L'ajout concurrent lui-meme a ete mesure le 26/08 et trouve SUR : deux
# processus ecrivant 40 enregistrements chacun donnent 80 lignes toutes
# lisibles, y compris a 200 Ko par enregistrement (200x la taille reelle
# maximale observee, 1006 o). Aucun correctif n'a donc ete applique ici.


# AJOUTE le 27/08/2026. decision_log.jsonl n'est PAS gitignore : c'est la
# preuve publiee, committee, et -- depuis le retablissement de la publication
# automatique le meme jour -- poussee sur le depot PUBLIC toutes les 30 minutes
# sans intervention humaine.
#
# Or rien ne rediger ce qui y entre, et un chemin plausible y mene :
# alpaca_cli.run() leve, quand la sortie du CLI n'est pas du JSON, avec
# « first 500 chars of output: {stdout[:500]} » -- la sortie BRUTE. Les
# identifiants sont dans l'environnement de ce sous-processus (config.cli_env()
# les y met). Un CLI que sa propre documentation qualifie d'« Alpha Preview »
# qui recracherait son environnement, une URL signee ou un en-tete
# Authorization dans un message d'erreur ferait donc atterrir une cle API dans
# un fichier committe et pousse automatiquement.
#
# Le journal actuel est propre -- verifie, aucun motif de cle, de secret,
# d'Authorization. Ce n'est pas une raison de laisser la porte ouverte : c'est
# la contrainte la plus dure de ce projet (« aucun fichier .env, secret ou
# identifiant »), et le seul defaut irreversible qu'il puisse produire. Une cle
# poussee sur un depot public est publique pour toujours.
#
# On caviarde par VALEUR EXACTE, jamais par motif : on sait ce qu'on cherche,
# donc aucun faux positif possible sur un texte legitime. Le seuil de longueur
# evite qu'une variable vide ou d'un caractere ne fasse tout disparaitre.
_VARIABLES_SECRETES = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")
_LONGUEUR_MINIMALE = 8


def caviarder(texte: str) -> str:
    """Remplace toute occurrence d'un identifiant connu par un marqueur.

    ON CHERCHE DEUX FORMES, ET LA SECONDE MANQUAIT. Ce caviardage tourne sur
    la ligne DEJA SERIALISEE -- choix deliberé, documente dans log_run() :
    une cle enfouie a n'importe quelle profondeur est ainsi attrapee sans
    parcourir la structure. Mais json.dumps ECHAPPE certains caracteres, et
    la valeur brute ne se retrouve alors plus telle quelle dans la ligne.

    Mesure du 29/08/2026, en relisant la ligne publiee avec json.loads :

        secret base64 ordinaire    caviarde
        secret contenant un \\      RECUPERABLE dans le fichier public
        secret contenant un "      RECUPERABLE
        secret non-ASCII           RECUPERABLE  (json.dumps ecrit \\uXXXX)

    Trois formes sur quatre traversaient le garde et finissaient dans
    decision_log.jsonl -- un fichier COMMITE, republie tel quel dans
    docs/data.json. Un lecteur n'avait qu'a de-echapper.

    Les cles Alpaca d'aujourd'hui sont alphanumeriques et n'auraient pas
    declenche ce cas. Mais ce garde est la DERNIERE barriere avant un fichier
    public, et il ne doit pas dependre du format qu'un fournisseur choisit
    aujourd'hui. On remplace donc AUSSI la forme echappee -- ce que
    json.dumps aurait ecrit pour cette valeur.

    Le marqueur reste une chaine JSON valide : la ligne doit rester
    relisible apres caviardage, sinon on protege le secret en detruisant la
    preuve. Un temoin le verifie.

    ET LA SECONDE COUCHE NE RATTRAPE PAS CE CAS -- verifie le 29/08 plutot
    que suppose. `garde_fou.controle_aucun_identifiant_dans_les_fichiers_
    publies` cherche bien la valeur dans tout ce que git suit, mais il ne
    cherche QUE des valeurs qui « ressemblent a un identifiant » :
    `[A-Za-z0-9_-]+`. Une valeur contenant un guillemet ou un antislash est
    ecartee par ce filtre avant meme la recherche -- deliberement, pour qu'il
    n'y ait aucun faux positif, et sa docstring le dit deja : « ce qui reste
    decouvert, c'est une valeur qui ne ressemble pas a une cle ».

    Les deux couches ont donc des frontieres COMPLEMENTAIRES, et c'est
    exactement pour cela que celle-ci ne doit pas dependre de la forme du
    secret : elle est la seule des deux a n'avoir aucun filtre."""
    for nom in _VARIABLES_SECRETES:
        valeur = os.environ.get(nom) or ""
        if len(valeur) < _LONGUEUR_MINIMALE:
            continue
        marqueur = "[%s CAVIARDE]" % nom
        for forme in (valeur, json.dumps(valeur)[1:-1]):
            if forme and forme in texte:
                texte = texte.replace(forme, marqueur)
    return texte


def log_run(record: Dict[str, Any]) -> None:
    """Appends one record. Always stamps a UTC timestamp; caller supplies
    the rest (market_open, exits, symbol verdicts, trade decision, error)."""
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
    # Caviardage sur la ligne SERIALISEE : une cle enfouie a n'importe quelle
    # profondeur du dictionnaire est attrapee, sans avoir a parcourir la
    # structure ni a deviner quels champs peuvent en contenir.
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(caviarder(json.dumps(record)) + "\n")


def log_run_or_dump(record: Dict[str, Any], context: str = "") -> bool:
    """log_run(), but never raises at the caller. Returns True if the record
    reached the file, False if it had to be dumped to stdout instead.

    Moved here 24/08 from two near-identical copies in agent.py's and
    monitor_exits.py's `finally` blocks -- they had already diverged in
    wording on their first edit, which is the copy-paste-then-tweak
    signature. This module is the right home because it already owns the
    READ side of exactly this policy: read_log() warns and skips a corrupt
    line rather than aborting its caller. Owning the write side too makes
    the module's guarantee symmetric and stated once -- decision_log never
    takes down its callers, in either direction -- instead of a contract
    enforced from outside by every caller remembering to.

    Dumping to stdout on failure means the trace survives wherever stdout
    goes (launchd's log, a terminal) rather than nowhere. flush=True because
    the situations that break the append (full disk, killed process) are
    exactly the ones where a buffered dump never lands."""
    try:
        log_run(record)
        return True
    except Exception as log_error:
        print(
            f"WARNING: could not write to {LOG_FILE.name} "
            f"({type(log_error).__name__}: {log_error}). "
            + (context + " " if context else "")
            + "Dumping the record here so it is not lost:",
            flush=True,
        )
        # CORRIGE le 27/08/2026. Cette ligne imprimait l'enregistrement BRUT.
        # log_run() caviarde la ligne serialisee avant de l'ecrire ; ce
        # repli-ci, non. Le chemin normal etait protege, le chemin d'URGENCE
        # non -- et c'est celui qu'on emprunte quand quelque chose va deja mal.
        #
        # Sous launchd, cette sortie standard EST le fichier de log declare par
        # le plist. Deux des quatre n'etaient pas gitignores au moment de la
        # decouverte, dont un deja suivi et pousse.
        #
        # Meme famille que le reste de la journee : la protection est posee sur
        # l'action principale, et la trace de secours passe a cote.
        print(caviarder(json.dumps(record, indent=2, default=str)), flush=True)
        return False


def read_log(limit: int = 30) -> List[Dict[str, Any]]:
    """Most recent `limit` records, newest first. Empty list if no log yet.

    Skips (with a warning) any line that fails to parse as JSON, rather
    than raising and aborting the whole read. Found 24/08, "cherche
    encore": log_run() below writes with a single f.write() call, but
    that's still two syscall-level steps (write the bytes, then the OS
    flushes/closes) -- a process kill or a crash at exactly the wrong
    moment (e.g. right after agent.py submits a paper order, one of the
    crash windows this same session's idempotency guard was written to
    survive) can leave a truncated, unparseable final line in
    decision_log.jsonl. Before this fix, ONE bad line here would raise
    json.JSONDecodeError out of read_log(), which publish_dashboard.py
    calls directly and unguarded -- taking down every future dashboard
    build, not just losing that one entry, until someone manually finds
    and fixes the bad line. Same "one bad record shouldn't take down
    everything else" principle this project already applies elsewhere
    (evaluate_symbol's per-symbol isolation, the entry loop's per-symbol
    isolation added earlier this session) -- just never applied here, the one place a single corrupted line could silently
    freeze the public dashboard for the rest of the hackathon week."""
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    records = []
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            enregistrement = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"  WARNING: decision_log.jsonl line {i} is not valid JSON ({e}) -- skipping it, not aborting the whole read")
            continue
        # AJOUTE le 28/08/2026. La promesse ci-dessus etait « ignorer une ligne
        # qui echoue a PARSER ». Mais une ligne qui parse en autre chose qu'un
        # objet n'est pas un enregistrement non plus, et elle passait. Mesure
        # sur un journal contenant `"une chaine"`, `42` et `null` :
        #
        #     read_log() -> [None, 42, 'une chaine', {...}]
        #
        # Consequence : ces trois-la occupent des places dans la fenetre des 30
        # derniers enregistrements que publie le tableau de bord -- exactement
        # le budget que monitor_exits.py protege ailleurs avec son
        # HEARTBEAT_SECONDS, pour empecher du bruit d'evincer les vraies
        # decisions de la page publique.
        #
        # Atteignabilite FAIBLE et dite comme telle : log_run() n'ecrit que des
        # dictionnaires, et une ecriture interrompue produit du JSON invalide,
        # donc la branche du dessus. Ce correctif aligne le contrat sur ce que
        # la fonction promet -- rendre des ENREGISTREMENTS -- plutot que de
        # corriger une panne observee.
        if not isinstance(enregistrement, dict):
            print(f"  WARNING: decision_log.jsonl line {i} parses as "
                  f"{type(enregistrement).__name__}, not an object -- skipping "
                  f"it: it would occupy a slot in the dashboard's 30-record "
                  f"window without being a decision")
            continue
        records.append(enregistrement)
    return list(reversed(records))[:limit]
