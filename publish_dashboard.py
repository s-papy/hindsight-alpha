# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

"""Builds docs/data.json — the snapshot the hosted dashboard (docs/index.html)
reads. Run this after (or as part of) each agent.py run.

Hosting choice: GitHub Pages serving the docs/ folder of this same public
repo, not a separate server. Two reasons: it reuses a dashboard pattern
already proven on an earlier project, and — more importantly — it means the API secret keys
never have to live anywhere except this machine's .env. A hosted server
approach would need the keys wherever it runs; a static page instead just
needs a JSON snapshot regenerated locally, committed, and pushed. The public
page never talks to Alpaca directly and never sees a key.

Usage:
    python publish_dashboard.py             # writes docs/data.json only
    python publish_dashboard.py --git-push   # also git add/commit/push

--git-push is opt-in and separate on purpose: writing the file is safe to
run unattended every day, but pushing to the public repo is a step this
project's own rules say needs an explicit decision each time, not a silent
default in a script.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import alpaca_cli
import config
import decision_log
from monitor_exits import MONITOR_STATUS_FILE

DOCS_DIR = Path(__file__).parent / "docs"
GEL = Path(__file__).parent / "kickoff_freeze.json"
DATA_FILE = DOCS_DIR / "data.json"


def _read_monitor_status() -> dict | None:
    """Best-effort read of monitor_exits.py's every-run status marker (see
    MONITOR_STATUS_FILE's own comment in monitor_exits.py for why this exists
    separately from decision_log.jsonl: found 25/08, by checking the dashboard
    health banner against a real incident, that decision_log.jsonl alone
    can't tell a reader whether the monitor is CURRENTLY healthy -- only
    whether it was ever interesting -- because a routine successful check is
    never logged there. Missing or corrupt file -> None, same non-blocking
    default as every other best-effort read in this project (e.g. a bad
    decision_log line just gets skipped, not fatal): a stale/missing status
    file should degrade the dashboard's health banner to 'no data', never
    break the whole snapshot build."""
    try:
        return json.loads(MONITOR_STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _dernier_passage_de_l_agent(entrees) -> "dict | None":
    """Quand agent.py a-t-il tourne pour la derniere fois, et comment ?

    AJOUTE le 28/08/2026, premier soir de la semaine live. Le tableau de
    bord publiait `monitor_status` -- la sante du moniteur de SORTIES -- et
    RIEN sur l'agent, celui qui prend les positions.

    Consequence, si agent.py meurt lundi : le moniteur continue de tourner
    toutes les 15 minutes et sa banniere reste verte, la page affiche
    `positions: []`, et plus rien ne distingue

        « l'agent a tourne et n'a rien trouve »   -- un RESULTAT, le garde
                                                    anti-retrospection qui fait
                                                    son travail
        « l'agent est mort depuis trois jours »   -- une PANNE

    C'est pourtant la distinction qui porte tout ce dossier. Le moniteur a
    eu sa banniere le 25/08, apres onze echecs silencieux ; l'agent n'a
    jamais eu la sienne.

    ON NE TOUCHE PAS A agent.py CE SOIR, deliberement : il tourne dans un
    quart d'heure pour son premier passage live, et une erreur ici couterait
    la journee. Un `finally` garantit deja qu'il ecrit une entree dans
    decision_log.jsonl A CHAQUE passage, quoi qu'il arrive -- l'information
    existe, elle n'etait simplement pas publiee. On la lit donc la, sans
    rien changer au chemin de trading.

    CORRECTION DE CE COMMENTAIRE, le meme soir. J'y avais ecrit que l'agent
    etait identifie « par la NEGATIVE » et qu'« un futur run_type inconnu
    serait pris pour l'agent ». C'est FAUX, et le test le montre : la
    condition liste des valeurs EXPLICITES (None, "", "agent"), donc
    'backtest' ou 'inconnu' sont ignores -- verifie, pas relu. J'avais decrit
    un risque qui n'existait pas ; le laisser aurait fait chercher un
    probleme ailleurs qu'ou il est.

    Ce qui etait vrai, en revanche : l'agent n'ecrivait AUCUN marqueur, et
    l'absence de `run_type` servait de signature. C'est repare depuis --
    agent.py ecrit `run_type: "agent"`. On accepte encore l'absence pour les
    21 entrees ANTERIEURES du journal, sinon tout l'historique d'avant le
    kickoff disparaitrait du tableau de bord.
    """
    # `run_type: "agent"` est pose depuis le 28/08/2026 au soir. Les entrees
    # ANTERIEURES -- 21 dans le journal a cette date -- n en ont pas : on
    # accepte donc aussi l absence de marqueur, sinon l historique d avant le
    # kickoff disparaitrait du tableau de bord. Ce qu on n accepte plus, c est
    # un type INCONNU : « ce n est pas le moniteur » ne veut pas dire « c est
    # l agent », et prendre un futur type pour un passage d agent ferait
    # paraitre vivant un agent mort.
    for e in entrees:
        if not isinstance(e, dict):
            continue
        if e.get("run_type") in (None, "", "agent"):
            return {
                "last_run_at": e.get("timestamp"),
                "outcome": e.get("outcome", "unknown"),
                "dry_run": bool(e.get("dry_run", False)),
                # Combien de symboles ont ete EXAMINES : distingue « a tourne
                # et n'a rien retenu » de « a tourne et a tout rate ».
                "symbols_evaluated": len(e.get("symbols") or []),
                "trades": len(e.get("trades") or []),
            }
    return None


# AJOUTE le 27/08/2026. Le commentaire de `account` ci-dessous enonce le
# principe -- « le payload d'Alpaca est recopie ici, et il grandira » -- et
# c'est pour cela que `account` a ete reduit a six champs choisis. `positions`,
# une ligne plus bas, recopiait pourtant le payload ENTIER.
#
# Mesure sur la position reellement ouverte, chacun des 19 champs publies
# croise contre docs/index.html ET test_dashboard.py :
#
#   consommes (7)  asset_class, cost_basis, qty, side, symbol,
#                  unrealized_pl, unrealized_plpc
#   personne (12)  asset_id, asset_marginable, avg_entry_price, change_today,
#                  current_price, exchange, lastday_price, market_value,
#                  qty_available, unrealized_intraday_pl,
#                  unrealized_intraday_plpc, usd
#
# `asset_id` est un UUID interne : exactement la nature du champ retire de
# `account` le meme jour, pour exactement ce motif. Le probleme n'est pas
# qu'un de ces champs soit dangereux -- aucun n'autorise quoi que ce soit
# sans les cles -- c'est que DOUZE champs partaient sans que personne ne
# l'ait decide, dans un fichier suivi par git et servi publiquement.
#
# La liste ci-dessous est donc une DECISION, pas un reste. Y ajouter un champ
# doit rester un acte volontaire : un test refuse tout champ publie que la
# page n'utilise pas.
CHAMPS_DE_POSITION_PUBLIES = (
    "symbol", "qty", "side", "asset_class",
    "cost_basis", "unrealized_pl", "unrealized_plpc",
)


def _position_publiable(position: dict) -> dict:
    """Ne publie que les champs que la page affiche reellement.

    `.get()` plutot qu'une indexation : un champ absent du payload devient
    None, ce que la page sait deja rendre. L'inverse -- lever ici -- ferait
    echouer toute la publication a cause d'un seul champ manquant sur une
    seule position, alors que ce fichier n'a qu'un role d'affichage.
    """
    return {champ: position.get(champ) for champ in CHAMPS_DE_POSITION_PUBLIES}


def _kickoff_publie() -> "str | None":
    """La frontiere du kickoff, LUE dans le fichier de gel et publiee avec le
    reste.

    AJOUTE le 29/08/2026. La page portait la meme date EN DUR :

        docs/index.html   const KICKOFF_MS = Date.UTC(2026, 7, 28, 15, 0);
        kickoff_freeze.json   "kickoff": "2026-08-28T15:00:00+00:00"

    Les deux valeurs sont identiques aujourd'hui -- ce n'est pas un ecart
    constate, c'est une seconde source de verite. Et bilan_semaine.py refuse
    explicitement d'ecrire cette date en dur, en disant pourquoi dans sa
    docstring : « une date en dur serait une seconde source de verite, et
    elles finissent toujours par diverger ». La regle etait appliquee d'un
    cote et pas de l'autre.

    Or cette frontiere gouverne les DEUX chiffres de tete de la page : le
    partage « 1 depuis le kickoff / 11 au total » et le « 28 des 30
    enregistrements » du separateur. Si le kickoff bougeait, le bilan
    suivrait et la page non.

    Rend None si le fichier est illisible : la page a une valeur de repli
    compilee, et elle DIT laquelle elle a utilisee."""
    try:
        with open(GEL, encoding="utf-8") as fh:
            valeur = json.load(fh).get("kickoff")
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return valeur if isinstance(valeur, str) and valeur else None


def _semaine_publiable() -> "dict | None":
    """Le compte de la fenetre notee, ou None si la fenetre est inconnue.

    None plutot que des zeros : sans `kickoff_freeze.json` on ne sait pas
    quelles entrees comptent, et publier « 0 refus » se lirait comme « le
    garde n'a rien refuse » au lieu de « je n'ai pas su compter ». La page
    affiche alors la phrase correspondante -- meme regle que partout
    ailleurs ici : ce qu'un controle fait quand il ne peut pas conclure
    compte plus que ce qu'il dit quand tout va bien."""
    import bilan_semaine
    fenetre = bilan_semaine._fenetre()
    if fenetre is None:
        return None
    entrees, illisibles = bilan_semaine._lire_journal()
    if entrees is None:
        return None
    c = bilan_semaine.compter_la_semaine(entrees, fenetre)
    return {
        # TOUJOURS publie, meme a zero -- comme le rapport hebdomadaire
        # l'imprime toujours. Trouve en cassant le journal a la main : avec
        # toutes les lignes illisibles, ce bloc annoncait « 0 verdict », ce
        # qui se lit « l'agent n'a rien decide » alors que la vraie reponse
        # est « je n'ai pas su lire ». Un compte qui omet en silence ce
        # qu'il n'a pas pu lire est le defaut que ce depot traque.
        "unreadable_log_lines": illisibles,
        # Exclus des chiffres, mais DITS : un essai a blanc ne soumet rien,
        # et le retirer en silence serait le defaut d'a cote.
        "dry_runs_excluded": c["essais_a_blanc"],
        "runs": len(c["passages"]),
        "runs_expected": c["attendus"],
        "verdicts": c["retenus"] + sum(c["refus"].values()),
        "tradeable": c["retenus"],
        "refused": dict(c["refus"]),
        "guard_refused_by_symbol": dict(c["refus_par_symbole"]),
        # L'ENTONNOIR, ajoute le 02/09/2026 : combien de symboles retenus
        # ont franchi les portes de risque et donne un ordre. Compte sur les
        # MEMES passages que le reste du bloc.
        "orders_submitted": sum(
            1 for e in c["passages"] for t in (e.get("trades") or [])
            if isinstance(t, dict) and t.get("outcome") == "order_submitted"),
        "gate_blocked": sum(
            1 for e in c["passages"] for t in (e.get("trades") or [])
            if isinstance(t, dict) and t.get("outcome") == "risk_gate_blocked"),
    }


# ---------------------------------------------------------------------------
# AJOUTE le 02/09/2026, apres avoir compare la page aux 65 autres soumissions
# du hackathon. Les tableaux de bord les mieux notes (Vetoed, optionwright)
# montrent en dix secondes ce que la page d'ici enterrait sous du texte : la
# courbe d'equite, le P&L realise, les trades fermes, l'entonnoir verdicts ->
# ordres. Tout cela EXISTAIT deja dans les donnees de ce depot ou a un appel
# CLI en lecture seule ; rien n'est invente, rien n'est estime.
#
# Chaque bloc est BEST-EFFORT, comme le reste de ce fichier : une panne du
# CLI sur l'historique de portefeuille rend None, la page le dit, et la
# publication continue. Un tableau de bord qui meurt parce qu'une courbe
# decorative a echoue serait l'inverse de ce que ce depot pratique.
# ---------------------------------------------------------------------------
_POINTS_MAX_COURBE = 240


def _equite_de_depart(courbe: "dict | None") -> "float | None":
    """L'equite de reference du compte, ou None.

    LUE DANS L'HISTORIQUE DE PORTEFEUILLE (base_value, la valeur de depart
    qu'Alpaca tient lui-meme pour ce compte), PAS dans state.json. Premiere
    version du 02/09 : un import de STATE_FILE depuis le module des portes de
    risque -- et le test test_deux_travaux_ne_se_disputent_pas_l_etat_a_la_
    meme_minute a refuse le commit : tout script qui importe ce module entre
    dans le perimetre des travaux qui touchent l'etat, et publish-dashboard
    demarre 13 fois par jour a la MEME minute que monitor-exits. Un simple
    import, meme pour une lecture, aurait fait crier ce controle a chaque
    commit, ou pire, l'aurait fait taire par habitude. Le compte de
    competition part de 100 000 $ et n'a rien trade avant le kickoff : les
    deux valeurs sont egales aujourd'hui, et celle-ci vient de la source qui
    ne pose pas de verrou."""
    if not isinstance(courbe, dict):
        return None
    try:
        valeur = float(courbe.get("base_value"))
    except (TypeError, ValueError):
        return None
    return valeur if valeur > 0 else None


def _courbe_d_equite(kickoff: "str | None") -> "dict | None":
    """Historique d'equite du compte, par pas de 15 minutes, depuis le
    kickoff quand il est connu. None si le CLI ne repond pas."""
    try:
        d = alpaca_cli.run(["account", "portfolio", "--period", "1W",
                            "--timeframe", "15Min"])
    except Exception as e:  # noqa: BLE001 -- best-effort, dit et non fatal
        print("  WARNING: portfolio history unavailable (%s: %s) -- the "
              "equity curve is skipped in this snapshot." % (type(e).__name__, e),
              flush=True)
        return None
    if not isinstance(d, dict):
        return None
    horodatages, equites = d.get("timestamp") or [], d.get("equity") or []
    points = [[int(t), float(e)] for t, e in zip(horodatages, equites)
              if isinstance(t, (int, float)) and isinstance(e, (int, float))]
    import bilan_semaine
    debut = bilan_semaine._en_utc(kickoff) if kickoff else None
    if debut is not None:
        seuil = debut.timestamp()
        points = [pt for pt in points if pt[0] >= seuil]
    if len(points) > _POINTS_MAX_COURBE:
        pas = len(points) / float(_POINTS_MAX_COURBE)
        points = [points[int(i * pas)] for i in range(_POINTS_MAX_COURBE)] + [points[-1]]
    return {"timeframe": d.get("timeframe"), "base_value": d.get("base_value"),
            "points": points}


def _fills_du_compte() -> list:
    """Les executions (FILL) du compte, ou [] si le CLI ne repond pas."""
    try:
        d = alpaca_cli.run(["account", "activity", "list",
                            "--activity-types", "FILL", "--page-size", "100"])
    except Exception as e:  # noqa: BLE001
        print("  WARNING: account activity unavailable (%s: %s) -- realized "
              "P&L per closed trade is left blank." % (type(e).__name__, e),
              flush=True)
        return []
    if isinstance(d, dict):
        d = d.get("activities") or []
    return [f for f in d if isinstance(f, dict)] if isinstance(d, list) else []


def _pnl_realise(fills: list, symbole: str) -> "float | None":
    """Ventes moins achats sur `symbole`, en dollars, multiplicateur 100 pour
    un contrat d'options (format OCC). None s'il manque un cote."""
    achats = ventes = 0.0
    vu_achat = vu_vente = False
    for f in fills:
        if f.get("symbol") != symbole:
            continue
        try:
            montant = float(f.get("price")) * float(f.get("qty"))
        except (TypeError, ValueError):
            continue
        if f.get("side") == "buy":
            achats += montant; vu_achat = True
        elif f.get("side") == "sell":
            ventes += montant; vu_vente = True
    if not (vu_achat and vu_vente):
        return None
    multiplicateur = 100 if alpaca_cli.is_option_position({"symbol": symbole}) else 1
    return round((ventes - achats) * multiplicateur, 2)


def _trades_fermes_publiables(entrees, fenetre, fills) -> list:
    """Les positions FERMEES par le moniteur de sorties dans la fenetre notee,
    du plus recent au plus ancien, avec le P&L realise quand les fills le
    permettent."""
    import bilan_semaine
    if fenetre is None:
        return []
    debut, fin = fenetre
    fermes = []
    for e in entrees or []:
        if not isinstance(e, dict) or e.get("dry_run"):
            continue
        t = bilan_semaine._en_utc(e.get("timestamp"))
        if t is None or not (debut <= t <= fin):
            continue
        for a in e.get("exit_actions") or []:
            if not isinstance(a, dict) or a.get("kind") != "closed":
                continue
            # UN CONTRAT SANS AUCUN FILL SUR CE COMPTE N'EST PAS UN TRADE DE
            # CE COMPTE. Vu sur le premier instantane du 02/09 : le journal
            # est partage avec le compte de developpement, et une position
            # de celui-ci a ete fermee six secondes apres le kickoff. Elle
            # apparaissait ici comme un stop-loss du compte de competition.
            # Quand les fills ont pu etre lus, un symbole qui n'y figure
            # jamais est ecarte ; sans fills (CLI muet) on ne peut pas
            # trancher et on garde tout, realise a None.
            if fills and not any(f.get("symbol") == a.get("symbol") for f in fills):
                continue
            fermes.append({
                "timestamp": e.get("timestamp"),
                "symbol": a.get("symbol"),
                "pnl_pct": a.get("pnl_pct"),
                "label": a.get("label"),
                "realized": _pnl_realise(fills, a.get("symbol")),
            })
    fermes.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return fermes


def _prix_des_sous_jacents(positions) -> dict:
    """Dernier cours de cloture connu de chaque sous-jacent d'option ouverte,
    pour tracer le payoff a l'echeance. Best-effort : un sous-jacent muet est
    simplement absent, la page trace alors le payoff sans le spot."""
    import re as _re
    prix = {}
    for pos in positions or []:
        m = _re.match(r"^([A-Z]{1,6})\d{6}[CP]\d{8}$", str((pos or {}).get("symbol") or ""))
        if not m or m.group(1) in prix:
            continue
        try:
            prix[m.group(1)] = float(alpaca_cli.get_last_price(m.group(1)))
        except Exception as e:  # noqa: BLE001
            print("  WARNING: last price unavailable for %s (%s) -- payoff drawn "
                  "without the spot." % (m.group(1), type(e).__name__), flush=True)
    return prix


def build_snapshot() -> dict:
    config.require_credentials()
    account = alpaca_cli.get_account()

    # AJOUTE le 28/08/2026, en completant le garde de compte pose le meme
    # matin dans check_gates (entrees) puis manage_exits (sorties). Ce
    # fichier-ci est le troisieme acteur, et c'est celui qu'un JUGE regarde :
    # il publie `account_number`, les positions et l'equite sur une page
    # publique, toutes les 30 minutes, sans personne devant.
    #
    # Sur un mauvais compte, il republiait donc en silence le numero, les
    # positions et l'equite d'un AUTRE compte -- ecrasant la preuve du
    # hackathon. Un juge qui compare le numero declare dans la soumission a
    # celui affiche sur la page verrait un desaccord sans explication, sur la
    # seule chose que ce projet lui demande de croire.
    #
    # On LEVE plutot que de publier. La page porte deja une banniere qui
    # vieillit et qui dit « snapshot from X ago » : une page perimee est
    # honnete, une page qui affirme le mauvais compte ne l'est pas. Sous
    # launchd, l'echec part dans le log declare par le plist.
    refus = config.raison_de_refus_du_compte(account)
    if refus:
        raise RuntimeError(
            "refusing to publish: %s. Publishing would overwrite the public "
            "dashboard with another account's positions and equity." % refus)
    if not config.compte_est_declare():
        print("  WARNING: no ALPACA_ACCOUNT_ID declared -- this snapshot is "
              "published without any check that it describes the intended "
              "account.", flush=True)

    positions = alpaca_cli.list_positions()
    recent = decision_log.read_log(limit=30)
    monitor_status = _read_monitor_status()
    historique = decision_log.read_log(limit=200)
    agent_status = _dernier_passage_de_l_agent(historique)
    kickoff = _kickoff_publie()
    import bilan_semaine
    fenetre = bilan_semaine._fenetre()
    fills = _fills_du_compte()
    courbe = _courbe_d_equite(kickoff)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # AJOUTES le 02/09/2026 -- voir le bloc de commentaires au-dessus de
        # _equite_de_depart(). Chacun a son rendu dans docs/index.html ; un
        # champ publie que la page n'affiche pas est le defaut que le test
        # de « champs morts » traque.
        "starting_equity": _equite_de_depart(courbe),
        "equity_curve": courbe,
        "closed_trades": _trades_fermes_publiables(historique, fenetre, fills),
        "underlying_prices": _prix_des_sous_jacents(positions),
        # LU par docs/index.html pour placer le separateur du kickoff et
        # partager le compteur de fuites. Publie parce qu'il est lu : meme
        # discipline que celle appliquee a `portfolio_value`, retire le 28/08
        # pour la raison inverse.
        "kickoff": kickoff,
        "team": "Hindsight Alpha",
        # Provenance embarquee dans les DONNEES, pas seulement dans la
        # page : si quelqu'un reprend data.json sans le HTML, l'origine
        # part avec. Trois champs statiques, aucun pistage.
        "source": "https://github.com/s-papy/hindsight-alpha",
        "author": "Spap",
        "license": "MIT",
        "account": {
            # RETIRE le 27/08 : "id": account.get("id") -- l'UUID INTERNE du
            # compte, 36 caracteres. Trouve en croisant ce que ce fichier
            # publie avec ce que docs/index.html lit : la page ne s'en sert
            # QUE comme repli derriere account_number, toujours present sur un
            # compte reel. Il n'etait donc affiche a personne, jamais, et
            # partait pourtant dans un fichier suivi par git et servi
            # publiquement par GitHub Pages a chaque publication.
            #
            # Il etait deja dans 6 commits pousses au moment de la
            # decouverte. Rien ne l'en retire sans reecrire l'historique, ce
            # que ce projet s'interdit : ce correctif arrete la suite, pas le
            # passe. Ni cet UUID ni le numero de compte n'autorisent quoi que
            # ce soit sans les cles -- ce sont des identifiants, pas des
            # pouvoirs. Ce qui compte, c'est qu'un champ soit parti sans que
            # personne ne l'ait decide : le payload d'Alpaca est recopie ici,
            # et il grandira.
            #
            # risk_gates.py continue d'utiliser account["id"] pour detecter
            # une bascule de compte -- usage INTERNE, jamais publie.
            #
            # account_number ("PA..." on paper accounts) is the human-visible
            # identifier -- what the hackathon submission form's "Alpaca
            # account ID" field almost certainly means, per Alpaca's own docs
            # distinguishing it from the internal UUID `id`. Surfaced
            # separately so the dashboard shows the SAME identifier that's
            # declared in the submission, not just the UUID -- a mismatch
            # here would make the "does this dashboard match the submitted
            # account" cross-check (the whole reason the dashboard shows an
            # account ID at all) confusing instead of reassuring.
            "account_number": account.get("account_number"),
            "status": account.get("status"),
            "equity": account.get("equity"),
            "cash": account.get("cash"),
            "buying_power": account.get("buying_power"),
            # `portfolio_value` RETIRE le 28/08 : publie, lu par
            # personne -- ni la page, ni les tests. Il sert bien de
            # repli a `equity` dans risk_gates, mais celui-la lit
            # l'API en direct, pas ce fichier. Meme discipline que
            # celle appliquee aux positions le meme matin : ce qui est
            # publie doit etre lu.
        },
        # LE COMPTE DE LA SEMAINE, pas seulement les decisions une par une.
        # AJOUTE le 30/08/2026 : la page listait chaque passage, donc un
        # lecteur devait compter lui-meme combien de fois le garde a refuse.
        # C'est pourtant le fait que ce projet existe pour montrer. Calcule
        # par `bilan_semaine.compter_la_semaine`, PAS reimplemente ici :
        # deux comptes du meme fait divergent au premier changement.
        "week": _semaine_publiable(),
        "positions": [_position_publiable(p) for p in positions],
        "recent_decisions": recent,
        "monitor_status": monitor_status,
        "agent_status": agent_status,
    }


def write_snapshot() -> Path:
    DOCS_DIR.mkdir(exist_ok=True)
    snapshot = build_snapshot()
    # Atomic write -- flagged but deliberately left alone in a "cherche
    # encore" pass earlier the same day ("same shape as state.json's [fixed]
    # torn-write bug, but exposure is lower: this script isn't scheduled,
    # write and commit happen in the same process, and the next run
    # overwrites the file"). Revisited and fixed on request: that reasoning
    # was about how LIKELY a torn write is here, not about the CONSEQUENCE
    # if one happens, and the consequence is real -- unlike state.json,
    # which is code this project runs, docs/data.json is content a judge's
    # browser parses with JSON.parse(). Path.write_text() opens in mode "w",
    # which truncates to 0 bytes before writing a single byte of the new
    # content (probed directly on this exact file, same mechanism as the
    # state.json bug: 40 bytes -> 0 the instant the file is opened) -- a
    # process killed mid-write (or a --git-push mid-commit interrupted the
    # same way) would leave docs/data.json invalid, and GitHub Pages would
    # serve that broken file to every visitor, including a judge, until the
    # next successful run overwrites it. Same fix as _save_state() in
    # risk_gates.py: write to a temp file in the same directory, fsync, then
    # os.replace() -- atomic on POSIX, so a reader always sees either the
    # complete old snapshot or the complete new one, never a half-written
    # file.
    tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(snapshot, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, DATA_FILE)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return DATA_FILE


# AJOUTE le 27/08/2026, le jour ou les LaunchAgents ont ete charges -- donc
# sur du code qui tourne desormais SANS PERSONNE DEVANT, toutes les 30 minutes.
#
# Sous launchd il n'y a AUCUN terminal. Si git decide de demander quoi que ce
# soit -- identifiants expires, trousseau verrouille, empreinte d'hote changee --
# il attend une reponse qui ne viendra jamais. GIT_TERMINAL_PROMPT=0 le fait
# ECHOUER au lieu d'attendre, et GIT_ASKPASS pointe vers un programme qui rend
# toujours faux pour fermer le second chemin (celui des helpers graphiques).
#
# Mieux vaut un echec net dans le log qu'un processus fige : launchd ne demarre
# pas une seconde instance tant que la premiere tourne, donc une seule attente
# infinie arrete la publication POUR DE BON.
_ENV_GIT = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="/usr/bin/false")

# Les operations locales sont rapides ; seul le reseau merite d'attendre.
_DELAI_LOCAL = 30
_DELAI_RESEAU = 120


def _integrer_l_amont() -> bool:
    """Met les commits locaux A JOUR par rapport a l'amont AVANT de pousser.

    AJOUTE le 02/09/2026, apres TROIS JOURS de tableau de bord public fige --
    lundi 31/08 et mardi 01/09 en entier, les deux premiers jours ouvres de la
    semaine jugee, plus le mercredi matin. Cause mesuree dans
    publish_dashboard.log et push_pending.log, pas devinee : quatre PR
    (#2 a #5) fusionnees sur GitHub les 30 et 31/08 ont fait avancer
    origin/main de 16 commits, pendant que CE clone -- celui que launchd
    fait tourner -- continuait a committer ses instantanes par-dessus
    l'ancien sommet. Des lors, CHAQUE `git push` etait rejete
    « non-fast-forward », 25 fois de suite, toutes les 30 minutes, et
    24 instantanes se sont empiles en local sans jamais etre publies. Les
    agents, eux, tournaient : une position fermee en take-profit, une autre
    ouverte -- mais la page publique n'en montrait rien.

    Le message d'erreur du push rejete nommait bien « the remote having
    moved ahead » -- mais ne faisait rien pour l'integrer, et attribuait le
    cas a une collision avec push-pending.plist « qui se cicatrise au cycle
    suivant ». Une fusion de PR ne se cicatrise jamais toute seule.

    Ce que fait cette fonction : `git fetch`, puis, si l'amont contient des
    commits que HEAD n'a pas, `git rebase` des commits LOCAUX (les
    instantanes, qui ne touchent que docs/data.json et decision_log.jsonl)
    par-dessus l'amont. Ce n'est PAS une reecriture d'historique au sens
    interdit par CLAUDE.md : seuls des commits que personne n'a encore vus
    sont deplaces, l'amont n'est jamais touche, et le push qui suit reste un
    fast-forward -- githooks/pre-push continue de refuser tout le reste.

    Si le rebase echoue (conflit reel, arbre de travail sale), il est AVORTE
    tout de suite : le depot revient exactement a l'etat d'avant, rien n'est
    perdu, et on le dit. Le push qui suit sera rejete comme avant -- mais
    avec la cause ecrite juste au-dessus.

    Rend True si le push peut etre tente, False si l'integration a echoue.
    Ne leve jamais : un echec ici ne doit pas masquer celui, plus parlant, du
    push lui-meme.
    """
    try:
        subprocess.run(["git", "fetch", "--quiet"], check=True,
                       timeout=_DELAI_RESEAU, env=_ENV_GIT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print("  WARNING: `git fetch` failed (%s) -- cannot tell whether the "
              "remote moved ahead; trying the push anyway, it will say."
              % type(e).__name__, flush=True)
        return True
    contenu = subprocess.run(["git", "merge-base", "--is-ancestor",
                              "@{upstream}", "HEAD"],
                             capture_output=True, timeout=_DELAI_LOCAL,
                             env=_ENV_GIT)
    if contenu.returncode == 0:
        return True          # l'amont est deja sous HEAD : rien a integrer
    if contenu.returncode != 1:
        print("  WARNING: cannot compare HEAD with its upstream (exit %d): "
              "no upstream configured? Trying the push anyway."
              % contenu.returncode, flush=True)
        return True
    print("  The remote moved ahead of this branch (a PR merged on GitHub, "
          "most likely): rebasing the local commits on top of it before "
          "pushing.", flush=True)
    try:
        subprocess.run(["git", "rebase", "--quiet", "@{upstream}"], check=True,
                       timeout=_DELAI_LOCAL, env=_ENV_GIT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        try:
            subprocess.run(["git", "rebase", "--abort"],
                           timeout=_DELAI_LOCAL, env=_ENV_GIT)
        except Exception:
            pass
        print("  ERROR: rebasing the local commits onto the remote FAILED "
              "(%s) and was ABORTED: the repo is exactly as before, nothing "
              "is lost, the local commits are intact -- but they cannot be "
              "published until an operator integrates the remote by hand "
              "(`git pull --rebase`, then resolve what conflicts). The usual "
              "causes: a remote commit touched docs/data.json or "
              "decision_log.jsonl too, or the working tree has uncommitted "
              "changes to a file the remote also changed."
              % type(e).__name__, flush=True)
        return False
    print("  Remote integrated; the push below is a fast-forward again.",
          flush=True)
    return True


def git_publish() -> None:
    paths = ["docs/data.json", "decision_log.jsonl"]
    # LA TROISIEME JUMELLE. Le commit refuse et le push rejete sont expliques
    # plus bas ; ce `git add` ne l'etait pas, et c'est le nouveau controle de
    # symetrie de garde_fou.py qui l'a signale -- pas une relecture.
    #
    # La panne realiste ici n'est pas une faute de frappe : c'est
    # `index.lock`. Ce depot a DEUX ecrivains -- l'operateur dans un terminal
    # et launchd toutes les 30 minutes -- et git refuse d'indexer pendant
    # qu'une autre commande tient le verrou. Transitoire, mais sans un mot
    # elle produisait la meme trace brute que les deux autres.
    try:
        subprocess.run(["git", "add", *paths], check=True,
                       timeout=_DELAI_LOCAL, env=_ENV_GIT)
    except subprocess.CalledProcessError as refus:
        print("  ERROR: `git add` was refused (exit %d). Nothing was staged, "
              "so nothing is committed and nothing is published -- the "
              "snapshot file on disk is still up to date. The usual cause is "
              "another git command holding .git/index.lock at this exact "
              "moment (this repo has two writers: a terminal and launchd "
              "every 30 minutes), which clears by itself. If it persists, "
              "run `git status` by hand." % refus.returncode, flush=True)
        raise
    except subprocess.TimeoutExpired:
        print("  ERROR: `git add` did not answer within %ds -- most likely "
              "another git command holding .git/index.lock. Nothing was "
              "staged; the next run republishes." % _DELAI_LOCAL, flush=True)
        raise
    # Both calls below are scoped to `paths` on purpose -- found 24/08,
    # a review pass. `git diff --cached --quiet` with NO pathspec checks
    # the whole index, not just the two files just staged above: if anything
    # else happened to already be staged in this working tree at this exact
    # moment (a terminal session mid multi-file review, say -- this repo's
    # own workflow runs plenty of ad hoc `git add` before this function is
    # ever called), that unrelated staged diff makes this "did anything
    # change" check report true even when docs/data.json and
    # decision_log.jsonl are byte-identical to HEAD. And an unscoped `git
    # commit` would then scoop that unrelated staged file into a commit
    # whose message claims to be only "dashboard: snapshot ...", pushing it
    # to the public repo under a misleading label -- a commit lying about
    # its own contents is exactly the kind of untrustworthy trace this
    # project exists to catch elsewhere. Reproduced in a throwaway repo:
    # staged an unrelated file, left the dashboard files unchanged, and
    # confirmed the unscoped diff reported "changed" anyway (exit 1); the
    # scoped `-- <pathspec>` form correctly reported "unchanged" (exit 0) in
    # the same state, and `git commit -m ... -- <pathspec>` committed only
    # the intended files while leaving the unrelated staged file untouched
    # and still staged for whoever put it there.
    result = subprocess.run(["git", "diff", "--cached", "--quiet", "--", *paths],
                            timeout=_DELAI_LOCAL, env=_ENV_GIT)
    if result.returncode == 0:
        # LE COMMIT EST SAUTE, PAS LA PUBLICATION. Corrige le 29/08/2026.
        #
        # Ce `return` sautait aussi le `git push` plus bas -- et `git push`
        # pousse la BRANCHE, pas seulement le commit qu'on vient de faire.
        # Consequence mesuree : tant que l'instantane ne bougeait pas, aucun
        # commit local n'etait publie, quel qu'en soit le nombre.
        #
        # En pratique data.json change presque toujours (generated_at bouge a
        # chaque execution), donc le cas est rare -- mais « rare » n'est pas
        # « impossible », et quand il arrive c'est TOUT le travail local qui
        # reste a quai sans que rien ne le dise.
        #
        # On pousse donc quand meme, s'il y a quelque chose a pousser. C'est
        # le seul chemin automatique de publication de ce depot.
        print("Nothing changed since last publish — skipping commit.")
        _publier_le_retard_local()
        return
    # AJOUTE le 27/08/2026 au soir, apres avoir lu publish_dashboard.log en
    # vrai : le hook de pre-commit lance garde_fou.py a CHAQUE publication,
    # toutes les 30 minutes, et le log en porte la trace complete.
    #
    # Le couplage qui en decoule : si le verdict passe au 🔴 -- un chiffre de
    # livrable qui derive, un faux positif d'un controle, un plist casse --
    # `git commit` est REFUSE, CalledProcessError remonte, et ce script meurt.
    # Toutes les 30 minutes. Le tableau de bord public gele pendant la semaine
    # ou des juges le regardent.
    #
    # Mesure avant ce correctif : l'exception remontait SANS UN MOT, sur une
    # trace brute, dans un fichier de log gitignore que personne ne lit.
    #
    # La banniere de la page finit par dire « snapshot from X ago » (chemin
    # verifie le 26/08), donc le silence devient visible. Sa CAUSE, non -- et
    # c'est elle qui permet d'agir. On la nomme, et on releve : un commit
    # refuse reste une ERREUR, sans quoi launchd croirait a une publication
    # reussie.
    try:
        subprocess.run(
            ["git", "commit", "-m", f"dashboard: snapshot {datetime.now(timezone.utc).isoformat()}", "--", *paths],
            check=True, timeout=_DELAI_LOCAL, env=_ENV_GIT,
        )
    except subprocess.CalledProcessError as refus:
        print(
            "  ERROR: `git commit` was refused (exit %d). The most likely "
            "cause is this repo's own pre-commit hook, which runs "
            "garde_fou.py and refuses the commit on a red verdict. While that "
            "verdict stands, EVERY publish attempt fails the same way and the "
            "public dashboard stops updating -- its banner will start "
            "reporting a stale snapshot, without saying why. Run "
            "`python3 garde_fou.py` to see what it is refusing."
            % refus.returncode,
            flush=True,
        )
        raise

    # Le push, et le seul appel qui parle au reseau. Sa panne se raconte comme
    # celle de l'ordre qui expire dans agent.py, corrigee le matin meme : un
    # delai depasse ne veut pas dire « ca a echoue », il veut dire « ON NE SAIT
    # PAS ». Le commit local est deja fait ; le push a pu atteindre GitHub sans
    # rendre la main. Le dire, plutot que de laisser croire a un echec net.
    #
    # AVANT le push, depuis le 02/09/2026 : integrer ce que l'amont a recu
    # entre-temps (une PR fusionnee sur GitHub), sinon le push est rejete
    # « non-fast-forward » a CHAQUE cycle et rien ne se cicatrise jamais --
    # trois jours de page publique figee. Voir _integrer_l_amont().
    _integrer_l_amont()
    try:
        subprocess.run(["git", "push"], check=True,
                       timeout=_DELAI_RESEAU, env=_ENV_GIT)
    except subprocess.TimeoutExpired:
        print("  WARNING: `git push` did not answer within %ds. The commit is "
              "already made LOCALLY, and the push MAY OR MAY NOT have reached "
              "GitHub -- this is UNKNOWN, not a failure. Run `git push` by hand "
              "and check the repo before assuming the dashboard is stale."
              % _DELAI_RESEAU, flush=True)
        return
    except subprocess.CalledProcessError as refus:
        # LA TROISIEME BRANCHE, ajoutee le 29/08/2026. Les deux voisines
        # etaient deja expliquees -- un `git commit` refuse juste au-dessus, un
        # push qui expire juste avant -- et un push REJETE, le cas le plus
        # courant des trois, ne disait rien du tout.
        #
        # Reproduit dans un depot jetable dont le remote ne repond pas : le
        # commit est fait LOCALEMENT, CalledProcessError remonte, et le script
        # meurt sur une trace brute. Sous launchd, cela se repete toutes les
        # 30 minutes dans publish_dashboard.log -- un fichier gitignore que
        # personne ne lit -- pendant que la page publique vieillit en silence.
        #
        # Ce n'est pas theorique : ce depot a deja rencontre un push rejete
        # par GitHub (GH007, adresse privee) le 28/08.
        #
        # L'etat exact, parce que c'est lui qui dit quoi faire : le commit
        # EXISTE, il n'est PAS publie, et l'historique local continue de
        # s'accumuler. Un seul `git push` a la main republie tout le retard.
        print(
            "  ERROR: `git push` was REJECTED (exit %d) -- this is a failure, "
            "not a timeout. The snapshot IS committed locally but is NOT "
            "published: the public dashboard will age and its banner will say "
            "so without saying why. Local commits keep piling up, and a single "
            "successful `git push` publishes the whole backlog at once. Common "
            "causes: credentials expired, GitHub refusing the commit e-mail "
            "(GH007), or the remote having moved ahead of this branch in the "
            "seconds since it was integrated just above -- push-pending.plist "
            "(runs every 30 min, 7 days a week) winning the same race, "
            "confirmed reproducible 31/08 with two real concurrent pushes; "
            "that one self-heals next cycle. A remote that moved ahead by a "
            "PR merge does NOT self-heal by itself: it is rebased under the "
            "local commits before every push since 02/09 -- if that rebase "
            "failed, its ERROR is printed just above. If it persists, run "
            "`git push` by hand to see the exact refusal."
            % refus.returncode,
            flush=True,
        )
        raise


def _commits_en_attente() -> "int | None":
    """Combien de commits locaux ne sont pas encore chez l'amont, ou None si
    la question n'a pas pu etre posee.

    None, jamais 0 : sans amont configure, « je n'ai pas pu compter » n'est
    pas « il n'y a rien a pousser » -- meme lecon que verifier_le_kickoff.py
    a apprise le meme jour sur exactement ce comptage."""
    try:
        r = subprocess.run(["git", "rev-list", "--count", "@{upstream}..HEAD"],
                           capture_output=True, text=True,
                           timeout=_DELAI_LOCAL, env=_ENV_GIT)
    except Exception:
        return None
    sortie = r.stdout.strip()
    if r.returncode != 0 or not sortie.isdigit():
        return None
    return int(sortie)


def _publier_le_retard_local() -> None:
    """Pousse le travail local deja commite quand l'instantane, lui, n'a rien
    de neuf a dire. Best-effort : ne doit jamais faire echouer la
    publication, qui a deja reussi a ce stade."""
    retard = _commits_en_attente()
    if retard is None:
        print("  (impossible de savoir s'il reste des commits a pousser — "
              "pas d'amont lisible ; ce n'est PAS « rien en attente »)",
              flush=True)
        return
    if retard == 0:
        return
    print("  %d commit(s) local(aux) en attente : publication." % retard,
          flush=True)
    pousser_les_commits_en_attente()


def pousser_les_commits_en_attente() -> None:
    """Pousse ce qui est deja COMMITE, sans rien publier de neuf.

    AJOUTE le 28/08/2026, en mesurant l'effet de bord du garde de compte pose
    le matin meme. `git_publish()` est la SEULE poussee automatique de ce
    depot. Si build_snapshot() refuse -- mauvais compte, identite illisible --
    l'exception remonte et main() n'atteint jamais git_publish : plus rien
    n'est pousse, ni le tableau de bord, NI LES COMMITS DE CODE.

    Or l'historique public horodate est precisement la preuve d'anteriorite
    que PROVENANCE.md revendique. Un refus de publier des DONNEES ne doit pas
    geler la publication de l'HISTOIRE : ce sont deux choses differentes, et
    seule la premiere est douteuse quand le compte ne correspond pas.

    Best-effort et jamais fatal : si la poussee echoue, on le dit et on
    laisse remonter l'erreur d'origine, qui est plus interessante.
    """
    _integrer_l_amont()
    try:
        subprocess.run(["git", "push"], check=True,
                       timeout=_DELAI_RESEAU, env=_ENV_GIT)
        print("  (les commits deja faits ont ete pousses, meme si "
              "l'instantane a ete refuse)", flush=True)
    except Exception as e:
        print("  WARNING: les commits en attente n'ont pas pu etre pousses "
              "non plus (%s: %s)." % (type(e).__name__, e), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git-push", action="store_true", help="also commit and push docs/data.json")
    parser.add_argument("--pousser-seulement", action="store_true",
                        help="ne publie AUCUN instantane : pousse seulement "
                             "les commits locaux deja faits")
    args = parser.parse_args()

    if args.pousser_seulement:
        # LE CHEMIN LE PLUS PETIT POSSIBLE, ajoute le 29/08/2026. Aucun appel
        # a Alpaca, aucun ordre, aucun commit cree : uniquement la
        # publication de ce qui est deja commite.
        #
        # CE QU'IL FAUT NE PAS DIRE : « aucun identifiant lu ». Mesure du
        # 29/08, l'import de ce module charge config, donc API_KEY,
        # SECRET_KEY et ACCOUNT_ID sont bien en memoire sur ce chemin -- ils
        # n'y servent a rien, c'est tout. Ma premiere redaction l'affirmait,
        # et c'etait faux.
        #
        # POURQUOI IL EXISTE SEPAREMENT : la publication du tableau de bord
        # est un job d'HEURES DE MARCHE -- jours ouvres, 15:30 a 22:05. Le
        # travail local, lui, s'accumule aussi le soir et le week-end, et
        # `git push` publie la BRANCHE. Le faire porter par le job de marche
        # forcerait a le sortir de sa fenetre de veille, ou a republier des
        # instantanes identiques hors seance -- deux effets de bord pour une
        # operation qui n'a besoin ni de reseau Alpaca ni de commit.
        _publier_le_retard_local()
        return

    try:
        path = write_snapshot()
    except Exception:
        # Le refus reste FATAL -- il doit se voir dans le log launchd et la
        # banniere de la page doit vieillir. Mais l'historique, lui, continue
        # d'etre publie : voir pousser_les_commits_en_attente().
        if args.git_push:
            pousser_les_commits_en_attente()
        raise
    print(f"Wrote {path}")

    if args.git_push:
        git_publish()
        print("Published to GitHub Pages (after the next Pages build completes).")


if __name__ == "__main__":
    main()
