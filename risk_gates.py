# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

"""Risk gates: several concurrent positions across different underlyings (not
stacked on the same one), a per-trade cap AND a total-exposure cap, a weekly
drawdown lock, and take-profit/stop-loss position management.

Why this exists: an agent that can buy a new option every day with no check
on whether it already holds one, no cap on how much of the account it risks
per trade, and no circuit breaker if the week goes badly isn't a trading
agent — it's a liability generator that happens to have a good idea buried
inside it. The hackathon's required one-page write-up has to cover "risk
gates" explicitly; describing a policy in prose without enforcing it in code
would be exactly the kind of gap this whole project (hindsight_guard) exists
to catch in other people's work. This mirrors the discipline already
established and sealed in an earlier trading project: a hard per-trade
risk cap and a drawdown lock, checked before every order, not just written
down.

Changed 24/08 from a strict single-position gate to several concurrent
positions, at the operator's explicit direction: "plusieurs symboles différents...
jamais tous les mêmes, œuf dans le même panier" (multiple different symbols,
never all the same, don't put all eggs in one basket) -- see agent.py's
DEFAULT_UNIVERSE, now spanning uncorrelated sectors (broad market,
commodities, tech, healthcare) instead of three similarly-correlated
broad-market ETFs. Allowing several open positions only makes sense with
symbols that are NOT highly correlated -- stacking positions on SPY, QQQ,
and IWM at the same time is close to one leveraged bet on the same regime,
not real diversification. This module doesn't check correlation itself
(no data source for that here); it trusts the universe was chosen with
that in mind.

Two caps now apply together, not just one: MAX_RISK_PCT_PER_TRADE bounds any
single trade, and MAX_TOTAL_RISK_PCT bounds the sum of premium committed
across every position open at once -- so opening a 4th position doesn't just
check "is there room for one more trade", it checks "is there still budget
left in the total exposure cap after what's already open". The weekly
drawdown lock did NOT need to change: it already compares total account
equity (which reflects every open position's unrealized P&L combined, not
per-position) against the recorded starting equity -- that check was already
portfolio-level by construction, verified by rereading it rather than
assumed correct just because it used to be.

Added 24/08, second pass, after a direct question "we improved the
strategy, but the agent is the real deliverable -- what improves the AGENT?"
and pointed at researching competitors and past hackathons for the answer.
Found in an Alpaca-published reference architecture (alpaca.markets/learn,
May 2026), which lists "portfolio-level exposure caps that [cannot be]
individually breached" / max_sector_exposure_pct as a named control,
distinct from a per-position cap:

  MAX_SECTOR_EXPOSURE_PCT caps committed premium per SECTOR (SECTOR_MAP),
  not just per underlying. With today's 1-symbol-per-sector universe
  (agent.DEFAULT_UNIVERSE) this rarely binds in practice -- the existing
  duplicate-underlying block already prevents two positions on SPY at once,
  and SPY is the only "broad_market" symbol. But it stops being a no-op the
  moment the universe grows (e.g. adding QQQ alongside SPY, or a second
  tech ETF alongside XLK) -- exactly the "diversification is a policy, not
  a control" gap this module's docstring already warns against elsewhere.
  Coding it now, while it's cheap and low-risk to test, means the universe
  can grow later without silently reopening that gap.

State (starting equity, lock status) persists in state.json next to this
file so the weekly lock survives the agent being re-run as a scheduled job
across multiple days. Not a secret, but run-specific — see .gitignore.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import alpaca_cli
import config

class StateNotPersisted(Exception):
    """Raised by the bookkeeping writers when _save_state() refused to write
    (corrupted state.json). Added 24/08 after a cleanup review: _save_state
    used to return None on refusal exactly as it did on success, so the
    caller-side guards written earlier the same day COULD NEVER FIRE on a
    corrupted file -- agent.py would log outcome="order_submitted" with no
    caveat while the duplicate-order guard was never armed, and manage_exits
    would state "consecutive losses now N" as fact with N not on disk. The
    choke point protected the evidence but dropped the signal that it had --
    the same family as the five bugs those guards were written for.

    Deliberately NOT caught by name anywhere -- checked 24/08 by reproducing
    both raise sites rather than by reading. The two generic handlers that
    already wrap these calls surface the message better than a named catch
    would:
      - agent.py puts it under its own key, record_order_submitted_failed,
        so decision_log.jsonl carries "StateNotPersisted: ... the
        duplicate-order guard was NOT armed for this order" as a dedicated
        field next to outcome="order_submitted", not buried in prose.
      - manage_exits appends it to the action line, which then reads
        "... CLOSED -- stop-loss hit (-60.0%) (consecutive-loss count NOT
        updated: StateNotPersisted: ...)" -- the close and the failed
        bookkeeping stated together, which is exactly what a human needs.
    A named except at either site would duplicate handling for no gain. The
    class earns its keep by making the message specific and greppable, not
    by being caught separately."""


STATE_FILE = Path(__file__).parent / "state.json"
HALT_FILE = Path(__file__).parent / "HALT"  # manual pause switch -- see is_halted()

MAX_RISK_PCT_PER_TRADE = 0.01   # cap premium spent on any single trade at 1% of equity
MAX_TOTAL_RISK_PCT = 0.03       # cap combined premium across ALL open positions at once at 3% of equity
MAX_SECTOR_EXPOSURE_PCT = 0.015 # cap combined premium within any ONE sector at 1.5% of equity (half the total cap)
WEEKLY_LOSS_LOCK_PCT = 0.03     # stop trading for the week if equity drops 3% from the start
# NOM TROMPEUR, mesure faite le 26/08/2026 et CONSERVEE telle quelle.
#
# Ce verrou n'est pas hebdomadaire. Il compare l'equite courante a
# `starting_equity`, posee UNE FOIS par compte et jamais rebaselinee autrement
# que sur un changement de compte -- il n'existe aucune logique de frontiere de
# semaine dans ce fichier: ni isocalendar, ni weekday, ni date de reference
# dans state.json. C'est donc "depuis la premiere execution", pour toujours.
#
# Deux consequences mesurees, opposees:
#   +10% puis -4,5% DEPUIS LE SOMMET  -> passe (on est encore au-dessus de
#                                       la reference d'origine)
#   -3,5% etale sur plusieurs semaines -> bloque, et ne se relache jamais seul
#
# LE COMPORTEMENT EST GARDE, le nom corrige en commentaire. Implementer une
# vraie remise a zero hebdomadaire AFFAIBLIRAIT le controle: il se relacherait
# chaque lundi, alors que la philosophie de ce fichier est explicitement
# l'inverse (le disjoncteur de pertes consecutives ne se reinitialise pas non
# plus, "stop and let a human look, don't quietly retry").
#
# La constante n'est pas renommee: CLAUDE.md inscrit WEEKLY_LOSS_LOCK_PCT dans
# la liste des seuils qu'on ne touche pas sans decision explicite, et un
# renommage brouillerait cette regle pour un gain cosmetique.
#
# Pour le hackathon, la distinction est sans effet: le compte dedie demarre a
# exactement 100 000 $ le 28/08 et la fenetre jugee va du 31/08 au 03/09 --
# "depuis la premiere execution" et "cette semaine" designent la meme periode.
MAX_OPEN_POSITIONS = 4          # never hold more than 4 positions at once, one per underlying
TAKE_PROFIT_PCT = 0.50          # close a position once unrealized gain hits +50% of premium paid
STOP_LOSS_PCT = 0.50            # close a position once unrealized loss hits -50% of premium paid
MAX_CONSECUTIVE_LOSSES = 3      # stop opening new positions after this many stop-losses in a row (see _record_exit_outcome)

# Maps each universe symbol to a sector bucket -- kept here (not in agent.py)
# since risk_gates is what enforces it. A symbol not in this map falls back
# to being its own sector (see sector_of) rather than silently landing in a
# shared "other" bucket, which would let two genuinely unrelated unmapped
# symbols quietly share a cap neither was designed against.
SECTOR_MAP = {
    "SPY": "broad_market",
    "GLD": "commodities",
    "XLK": "technology",
    "XLV": "healthcare",
}


def sector_of(symbol: str) -> str:
    return SECTOR_MAP.get(symbol.upper(), symbol.upper())


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    qty: int = 0
    committed_dollars: float = 0.0  # what this decision would add to total exposure, if allowed --
    # agent.py accumulates this, keyed by underlying, across a single run's
    # loop over several symbols (see check_gates'
    # already_committed_this_run_by_underlying param for why).


def _load_state() -> dict:
    """Falls back to an empty state (not a crash) on a MISSING state.json --
    that's just "first run," safe to start fresh. A CORRUPTED state.json
    (exists, but fails to parse) is handled very differently: returns a
    sentinel ({"_corrupted": True}) instead of quietly re-baselining, and
    check_gates() below refuses ALL new entries the moment it sees that
    sentinel, before ever touching starting_equity/locked.

    Correction made 24/08, on re-review, after re-reading this
    function's OWN reasoning and realizing it proved too much: the original
    version returned {} on corruption too, on the argument that "a process
    killed mid-write... is a real enough scenario that the whole agent
    shouldn't go down over it." True for a NEW/never-run state.json. Not
    true if the corruption hit a state.json that already had locked=True
    (the weekly drawdown lock) or a tripped consecutive_losses count --
    _record_starting_equity() treats "starting_equity missing from state"
    (which a corrupted file also produces) identically to "this account has
    never been seen before," and would have silently cleared BOTH the lock
    and the loss counter along with it. That's the exact opposite of fail-
    safe: a crash mid-write, at the worst possible moment, would have
    quietly un-paused an agent that was supposed to have stopped trading
    for the week. Corruption obscuring what the prior state actually was is
    a reason to be MORE cautious (refuse and wait for a human), not less --
    same principle already applied to the consecutive-loss breaker
    (deliberately not self-resetting). A human can always delete
    state.json by hand to intentionally re-baseline once they've confirmed
    it's safe; the agent should never do that silently on its own."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(
            f"WARNING: {STATE_FILE} exists but is corrupted (not valid JSON) -- likely a "
            "crash mid-write. This could be hiding an active weekly loss lock or "
            "consecutive-loss breaker from before the crash, so new entries are refused "
            "until a human looks (see check_gates). Exits are unaffected -- manage_exits() "
            "does not depend on this file being intact. Delete state.json by hand once "
            "you've confirmed it's safe to re-baseline from scratch."
        )
        return {"_corrupted": True}


def _save_state(state: dict) -> bool:
    """Refuses to write a state carrying the _corrupted sentinel -- found
    24/08, on re-review, by reproducing it rather than by inspection.

    _load_state() promises, in its own docstring, that a corrupted
    state.json is "left untouched on disk until a human deliberately
    intervenes". check_gates() honours that carefully (it refuses before
    ever calling _record_starting_equity). But the EXIT path does not go
    through check_gates at all -- by design, exits must keep running under
    a lock -- so manage_exits() -> _record_exit_outcome() reached
    _load_state() + _save_state() with no corruption check, and overwrote
    the damaged file with a freshly serialised one.

    Measured, on a real corrupted file that was hiding locked=true:
    starting_equity and locked were both GONE afterwards, replaced by
    {"_corrupted": true, "consecutive_losses": 1}.

    Scope of the damage, stated precisely: this did NOT open a trading
    hole. The _corrupted key survives the round-trip, so check_gates keeps
    refusing every new entry exactly as intended. What was destroyed is the
    EVIDENCE -- the bytes a human needs to decide whether a weekly lock was
    active before the crash -- while the module's own stated invariant said
    those bytes would be preserved.

    Guarding here rather than in each caller is deliberate: _save_state is
    the single choke point every writer already goes through, so this also
    covers record_order_submitted() (same latent shape, currently
    unreachable only because check_gates refuses first) and any writer
    added later, which a per-caller check would not."""
    if state.get("_corrupted"):
        print(
            f"  WARNING: refusing to overwrite {STATE_FILE} -- it is corrupted and its original "
            "contents are the only record of what was in effect before the crash (a weekly loss "
            "lock, a consecutive-loss count). Bookkeeping for this action was NOT persisted. "
            "New entries stay refused until a human deletes or repairs the file by hand."
        )
        return False

    # Atomic write -- found 24/08, on re-review, and demonstrated rather
    # than assumed: Path.write_text() opens in mode "w", which truncates the
    # file to 0 bytes BEFORE writing a single byte of the new content (probed
    # directly: 77 bytes -> 0 immediately on open, content only afterwards).
    # A process killed inside that window leaves a truncated or partial file
    # -- reproduced by killing a writer mid-write, which produced exactly the
    # invalid JSON _load_state() now flags as _corrupted.
    #
    # That mattered less this morning than it does now, for two reasons that
    # both landed today:
    #   - the corruption handling added earlier in this same pass makes a
    #     corrupted state.json STICKY on purpose: every new entry is refused
    #     until a human intervenes. Safe, but it means a torn write is no
    #     longer a transient annoyance -- it stops the agent for the rest of
    #     an unattended week.
    #   - monitor_exits.py is now scheduled every 15 minutes (launchd), so a
    #     SECOND process can reach this function at all, and the two can
    #     overlap. (Corrected 24/08 by a cleanup review: an earlier version
    #     of this note claimed the 15-minute cadence made writes happen "far
    #     more often". It does not -- manage_exits only reaches _save_state
    #     when a close actually fires, so the routine 15-minute path writes
    #     nothing. The overlap risk is real; the frequency claim was not.)
    #
    # Writing to a temp file in the same directory and os.replace()-ing it in
    # is atomic on POSIX: a reader (or a crash) sees either the complete old
    # file or the complete new one, never a half-written one. fsync before
    # the swap so the content is durable before it becomes visible.
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(state, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, STATE_FILE)
    except Exception:
        # Leave no partial sidecar behind: a human doing the post-crash
        # forensics the _corrupted sentinel exists to force should find the
        # damaged state.json, not a second half-written file next to it.
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return True


class StateLockUnavailable(Exception):
    """Raised when the exclusive lock on state.json cannot be taken in time.

    Fail-closed on purpose: the caller wanted to update the bookkeeping that
    the risk gates read, and could not. Continuing without the lock is exactly
    the bug this class exists to prevent."""


@contextlib.contextmanager
def _state_lock(timeout_s: float = 10.0):
    """Hold an exclusive lock for the whole read-modify-write of state.json.

    AJOUTE le 26/08/2026. _save_state() is atomic -- it writes a temp file and
    os.replace()s it, so a reader never sees a half-written file. Atomicity
    prevents a TORN file. It does not prevent a LOST UPDATE, which is a
    different failure and the one actually reachable here.

    Reproduced, not assumed. Two processes, interleaved the way launchd can
    produce them (agent.py daily, monitor_exits.py every 15 minutes -- the
    overlap risk _save_state's own note already flagged):

        A reads state           B reads state          (both see locked=False)
        B sets locked=True, writes                     (weekly loss lock ON)
        A appends SPY to traded_today, writes          (from its STALE copy)
        -> final state: locked=False

    Measured output of that script: "LE VERROU DE PERTE A DISPARU". The lock
    that stops the agent for the rest of the week was silently cleared by a
    routine write from the other process -- no crash, no corruption, no error.
    The mirror case loses traded_today instead, disarming the duplicate-order
    guard for that symbol.

    This is the same failure the corruption handling was written to prevent
    ("a crash would quietly un-pause an agent that was supposed to have
    stopped"), except no crash is required -- two normal writes suffice.

    flock() is per-open-file-description, so the lock is released by close()
    even if the process is killed inside the critical section -- no stale lock
    can wedge the agent. The wait is bounded because every critical section
    guarded here is pure computation with no network I/O (checked: no
    alpaca_cli call sits between any load/save pair), so 10 s is already
    absurdly generous; blocking forever under launchd would be worse than
    failing loudly.
    """
    lock_path = STATE_FILE.with_name(STATE_FILE.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Pas d'encoding : ce descripteur ne sert QU'a flock(), on n'y lit ni
    # n'y ecrit jamais de texte. Le preciser suggererait le contraire.
    fh = open(lock_path, "a+")
    try:
        limite = time.monotonic() + timeout_s
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= limite:
                    raise StateLockUnavailable(
                        f"another process has held the lock on {STATE_FILE} for more than "
                        f"{timeout_s:g}s. Bookkeeping was NOT updated; refusing to write from a "
                        f"possibly stale copy, which is how a loss lock gets silently cleared."
                    )
                time.sleep(0.05)
        yield
    finally:
        fh.close()  # releases the flock


def _record_starting_equity(equity: float, state: dict, account_id: Optional[str]) -> dict:
    """Sets the baseline the weekly lock measures drawdown against — once,
    the first time this account is seen.

    account_id is compared against whatever is already saved in state.json.
    Without this check, switching .env from the dev account to the dedicated
    hackathon account at kickoff (a planned step) would
    silently compare the new account's real equity against the OLD account's
    starting_equity -- two unrelated numbers, since state.json is a single
    shared file with no account awareness. That could either falsely trip
    the weekly loss lock on the very first real run, or (worse) mis-size
    trades against a wrong baseline, depending on which account happened to
    have more equity. Re-baselining whenever the account_id changes makes
    the forgetting-to-wipe-state.json failure mode self-correcting instead
    of relying on remembering a manual step during the kickoff handoff.

    Extended 24/08, second pass: also resets traded_today and
    consecutive_losses on an account switch. Both were added later the
    same day (duplicate-order guard, consecutive-loss circuit breaker) and
    were NOT included in the original reset list -- found by testing the
    exact kickoff scenario this function's own docstring describes (switch
    from dev to the dedicated account) against the two newer fields, not
    by inspection. Without this, a symbol already traded today on the OLD
    account would look "already traded" on a brand-new account that has
    never placed a single order, and a losing streak from the OLD account
    could immediately trip the circuit breaker on an account with zero
    real losses -- the identical failure shape this function already
    exists to prevent for starting_equity/locked, just not yet extended to
    fields added after it was written."""
    # AJOUTE le 27/08/2026, la veille du kickoff -- donc sur le code qui ne
    # s'executera qu'UNE fois, sans personne devant, a la bascule de compte.
    #
    # `bascule_de_compte = state.get("account_id") not in (None, account_id)`.
    # Quand account_id vaut None -- une reponse de compte sans champ « id » --
    # l'expression devient `etat_id not in (None,)`, donc VRAI. Un identifiant
    # ILLISIBLE etait donc traite exactement comme une vraie bascule.
    #
    # Reproduit, sur un etat portant un verrou de perte ACTIF :
    #     meme compte         -> verrou=True   pertes=2  sorties=1
    #     vraie bascule       -> verrou=False  pertes=0  sorties=0
    #     id illisible (None) -> verrou=False  pertes=0  sorties=0
    #
    # Le verrou hebdomadaire efface, le disjoncteur remis a zero, la memoire
    # des sorties videe -- sur une donnee qu'on n'a pas su lire. C'est la
    # famille que le docstring ci-dessus decrit deja mot pour mot.
    #
    # LA GARDE EST ETROITE, volontairement : elle ne protege que ce qui EXISTE
    # deja. Sur un etat vierge il n'y a aucune protection a preserver, et
    # refuser la fabriquerait une panne -- l'agent ne pourrait jamais poser sa
    # reference d'equite, donc jamais demarrer, y compris quand tout va bien.
    identite_inconnue = account_id is None or not str(account_id).strip()
    if identite_inconnue and state.get("account_id") is not None:
        print(
            "  WARNING: the account response carried no usable id, so we "
            "cannot tell whether this is still account %r or a different one. "
            "NOT re-baselining and NOT clearing anything -- an unreadable id "
            "is not an account switch. The weekly lock, the consecutive-loss "
            "counter and the counted-exits memory are left exactly as they "
            "were." % state.get("account_id"),
            flush=True,
        )
        return state

    if state.get("account_id") != account_id or "starting_equity" not in state:
        # Cette branche couvre DEUX situations differentes, et elles ne meritent
        # pas le meme traitement :
        #   - une vraie BASCULE de compte (un autre account_id etait enregistre) ;
        #   - un simple premier passage (starting_equity pas encore pose).
        bascule_de_compte = state.get("account_id") not in (None, account_id)
        if bascule_de_compte:
            print(
                f"NOTE: state.json was for account {state.get('account_id')!r}, "
                f"now running as {account_id!r} -- re-baselining starting_equity, clearing any lock, "
                f"today's traded-symbols record, the consecutive-loss counter, and the "
                f"already-counted-exits memory."
            )
        state["account_id"] = account_id
        # NE JAMAIS ENREGISTRER UNE LIGNE DE BASE QU'ON NE PEUT PAS CROIRE.
        # Ajoute le 28/08/2026, premier soir de la semaine live, apres
        # reproduction complete :
        #
        #   1. bascule de compte + equite illisible -> _record_exit_outcome
        #      passe `equity or 0.0`, donc 0.0 -> starting_equity = 0.0
        #   2. un passage NORMAL ensuite, equite parfaitement lisible a
        #      101 000 $, ne le repare PAS : la re-calibration ne se declenche
        #      que si le compte change ou si le champ MANQUE, or 0.0 est present
        #   3. `drawdown_pct = (starting - equity) / starting if starting else 0`
        #      rend alors 0 % meme a 50 000 $ d'equite -> le verrou de perte
        #      hebdomadaire ne se declenche PLUS JAMAIS
        #
        # Un filet de securite desactive en silence, definitivement, et dont le
        # declencheur est exactement la bascule de compte prevue ce soir.
        #
        # check_gates() refuse deja une equite <= 0 ou non finie (ligne ~1424)
        # et n'appelle donc jamais cette fonction avec un chiffre douteux. Le
        # chemin des SORTIES, lui, ne validait rien.
        #
        # En laissant le champ ABSENT plutot qu'a zero, on rend la main a la
        # regle qui existe deja : « starting_equity manquant » declenche une
        # re-calibration au prochain passage de check_gates, avec une equite
        # cette fois verifiee. On ne change AUCUN seuil ; on refuse seulement
        # d'ecrire une mesure qu'on n'a pas.
        equite_sure = (isinstance(equity, (int, float))
                       and not isinstance(equity, bool)
                       and math.isfinite(equity) and equity > 0)
        if equite_sure:
            state["starting_equity"] = equity
        else:
            state.pop("starting_equity", None)
            print(
                "  WARNING: refusing to record %r as the starting equity for "
                "account %r -- it is not a usable figure. No baseline is "
                "written, so the next run that reads a clean equity will set "
                "one. Recording zero here would leave the weekly loss lock "
                "permanently disabled, since a drawdown against a zero "
                "baseline always computes as 0%%." % (equity, account_id),
                flush=True,
            )
        state["locked"] = False
        state["lock_reason"] = None
        state["traded_today"] = {"date": _today(), "symbols": []}
        state["consecutive_losses"] = 0
        # AJOUTE le 27/08/2026, le jour meme ou exits_counted a ete introduit --
        # et exactement la faute que le docstring ci-dessus decrit deja pour
        # traded_today et consecutive_losses : un champ ajoute apres coup, oublie
        # dans la liste de remise a zero. Trouve en relisant cette fonction juste
        # apres avoir ajoute le champ.
        #
        # L'effet est etroit (la memoire se purge d'elle-meme contre les
        # positions ouvertes, donc des symboles d'un autre compte disparaissent
        # au premier passage) mais reel : si le nouveau compte detient le MEME
        # contrat OCC, sa premiere vraie perte serait prise pour un doublon et
        # ne serait pas comptee.
        #
        # test_l_etat_apres_bascule_de_compte_est_epingle verrouille desormais
        # la liste ENTIERE : le prochain champ ajoute fera tomber ce test au lieu
        # d'etre oublie une troisieme fois.
        #
        # MAIS uniquement sur une VRAIE bascule de compte -- et cette nuance a
        # ete trouvee par la suite de tests, pas par relecture. Premiere version
        # de ce correctif : effacement sur les deux chemins. Trois tests sont
        # tombes aussitot.
        #
        # La raison : manage_exits() ecrit exits_counted (via
        # _premiere_fois_qu_on_compte_cette_sortie) IMMEDIATEMENT avant
        # d'appeler _record_exit_outcome(), qui atterrit ici. Sur un etat ou
        # starting_equity n'est pas encore pose -- le cas normal d'une machine
        # ou seul monitor_exits.py a tourne, puisqu'il n'appelle jamais
        # check_gates -- l'effacement detruisait ce qui venait d'etre inscrit
        # dans la MEME iteration. La position bloquee etait donc recomptee au
        # passage suivant : le defaut corrige quelques minutes plus tot
        # revenait par la porte de service.
        #
        # traded_today et consecutive_losses n'ont pas ce probleme : rien ne les
        # ecrit dans cette fenetre-la.
        if bascule_de_compte:
            state["exits_counted"] = {}
        _save_state(state)
    return state


def _extract_float(position: dict, key: str) -> Optional[float]:
    """Same string-vs-number defensiveness as _extract_unrealized_plpc below,
    for any other numeric position field -- cost_basis in particular, needed
    to sum up total premium committed across multiple open positions."""
    # AJOUTE le 27/08/2026 : le filtre `math.isfinite`, comme dans
    # _extract_unrealized_plpc corrige quelques minutes plus tot. Ici la
    # consequence est PIRE, parce que ce champ alimente les PLAFONDS.
    #
    # Mesure avant correctif, sur une position au cout « nan » :
    #
    #     lu = nan          positions_au_cout_illisible : ne la signale PAS
    #     _total_committed  = nan
    #     check_gates       -> AUTORISE un nouveau trade
    #
    # Le mecanisme : remaining_total_budget = 3000 - nan = nan, et
    # `nan <= 0` est FAUX, donc le plafond d'exposition totale est franchi
    # sans bruit. Un seul cout non fini parmi les positions ouvertes et le
    # plafond de 3% cesse simplement de s'appliquer -- pour toutes les
    # positions suivantes de la journee.
    #
    # C'est la panne la plus grave que ce fichier puisse produire : non pas
    # refuser a tort, mais AUTORISER sans limite. Un cout non fini rejoint
    # donc les couts illisibles, que positions_au_cout_illisible() fait
    # refuser explicitement.
    #
    # `inf` refusait deja, par accident : 3000 - inf est negatif. On ne
    # s'appuie pas sur cet accident.
    def _fini(x):
        return x if math.isfinite(x) else None

    value = position.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _fini(float(value))
    if isinstance(value, str) and value.strip():
        try:
            return _fini(float(value))
        except ValueError:
            return None
    return None


def positions_au_cout_illisible(open_positions: List[dict]) -> List[str]:
    """Les positions ouvertes dont on n'arrive pas a lire le montant engage.

    AJOUTE le 26/08/2026. _total_committed() comptait ces positions pour ZERO
    dollar -- son propre docstring l'assumait : « counting as 0, not skipped
    silently [...] doesn't block sizing on data the CLI failed to provide
    cleanly ». Le choix est explicite, et c'est le mauvais cote : une donnee
    ILLISIBLE agrandissait le budget de risque au lieu de le fermer.

    Mesure, equite $100 000, plafond global 3% = $3 000 :

        3 positions a $900   lisibles  -> engage $2 700 -> taille 1 contrat
        les MEMES            illisibles-> engage $0     -> taille 3 contrats
        3 positions a $2 900 lisibles  -> REFUSE (8,7% deja expose)
        les MEMES            illisibles-> ouvre une position pleine
        3 positions a $25 000 lisibles -> REFUSE (75% deja expose)
        les MEMES            illisibles-> ouvre une position pleine

    La porte refuse correctement DES QU'ELLE SAIT LIRE. Elle cesse d'exister
    exactement quand l'agent a perdu la trace de son exposition. Le depassement
    est borne par MAX_OPEN_POSITIONS x MAX_RISK_PCT_PER_TRADE, soit 4% pour un
    plafond annonce a 3% -- mais le principe est ce qui compte : on n'ajoute pas
    du risque au moment precis ou l'on ne sait plus combien on en porte.

    Atteignabilite NON demontree : l'API Alpaca renvoie toujours cost_basis, et
    la frontiere alpaca_cli leve desormais sur une reponse illisible plutot que
    de rendre une liste vide. C'est donc du code defensif -- mais du code
    defensif qui avait ANTICIPE le cas et choisi l'echec ouvert. On garde
    l'avertissement imprime, on refuse seulement l'entree NOUVELLE ; les sorties
    ne passent pas par ici et restent intactes, ce qui est l'ordre des priorites
    de tout ce fichier."""
    illisibles = []
    for pos in open_positions:
        if _extract_float(pos, "cost_basis") is None:
            illisibles.append(str(pos.get("symbol", "<symbole inconnu>")))
    return illisibles


def positions_au_sous_jacent_illisible(open_positions: List[dict]) -> List[str]:
    """Les positions ouvertes dont on n'arrive pas a lire le SOUS-JACENT.

    AJOUTE le 27/08/2026, comme pendant durable d'un correctif de motif dans
    alpaca_cli.py. Le motif OCC n'acceptait que la forme compacte
    (« SPY260831P00764000 ») et pas la forme STANDARD a 21 caracteres, dont la
    racine est completee par des espaces (« SPY   260831P00764000 »).

    Consequence mesuree de bout en bout, MEME position, deux ecritures :
        OCC compact  -> refuse : « already holding an open position on SPY »
        OCC standard -> AUTORISE un 2e SPY, dimensionne 3 contrats

    C'est la signature exacte du trou deja documente dans check_gates
    (« TROU REPRODUIT »): l'exposition TOTALE restait juste, seule la regle
    anti-doublon cedait. Mais cette route-la ne demandait QU'UNE condition.

    Elargir le motif ferme la porte trouvee. Ceci ferme les autres : la regle
    anti-doublon compare `underlying` a l'ensemble des sous-jacents ouverts ;
    un None s'y glisse sans bruit, et « SPY » n'est pas dans {None}. Si l'on
    ne sait pas sur quoi porte une position ouverte, on ne PEUT PAS verifier
    la regle -- donc on n'ouvre pas.

    Meme raisonnement que positions_au_cout_illisible() juste au-dessus, et
    que list_positions() dans alpaca_cli : « je n'ai pas compris » n'est pas
    « il n'y a rien ». Les SORTIES ne passent pas par ici et restent
    intactes -- manage_exits() lit toutes les positions, pas la liste filtree,
    ce qui a ete verifie en meme temps."""
    return [str(pos.get("symbol", "<symbole inconnu>"))
            for pos in open_positions
            if alpaca_cli.option_underlying(pos) is None]


def _total_committed(open_positions: List[dict]) -> float:
    """Sum of cost_basis across every open option position -- what's already
    at risk before sizing a new trade. Positions whose cost_basis can't be
    read are counted as 0, not skipped silently: printed so it's visible,
    but doesn't block sizing on data the CLI failed to provide cleanly."""
    total = 0.0
    for pos in open_positions:
        cost = _extract_float(pos, "cost_basis")
        if cost is None:
            print(f"  WARNING: could not read cost_basis for {pos.get('symbol')}, counting as $0 committed")
            continue
        total += cost
    return total


def _sector_committed(open_positions: List[dict], sector: str) -> float:
    """Sum of cost_basis across open positions whose underlying maps to the
    given sector -- the sector-level analogue of _total_committed above."""
    total = 0.0
    for pos in open_positions:
        underlying = alpaca_cli.option_underlying(pos)
        if underlying and sector_of(underlying) == sector:
            cost = _extract_float(pos, "cost_basis")
            if cost is not None:
                total += cost
    return total


def _extract_unrealized_plpc(position: dict) -> Optional[float]:
    """Unrealized P&L as a fraction of cost basis (0.5 = +50%). Tries
    Alpaca's standard field name first (unrealized_plpc, already a
    fraction), falls back to computing it from unrealized_pl / cost_basis
    if the CLI names it differently."""
    # VERIFIED 24/08 (`alpaca position list --schema`, CLI v0.0.13): every
    # numeric position field is typed *string* ("unrealized_plpc: string"),
    # so the original isinstance(plpc, (int, float)) check could never fire
    # against the real CLI. The result stayed correct only because the
    # fallback below recomputes from unrealized_pl / cost_basis -- but that
    # made the authoritative field dead code, and left the exit gate relying
    # on cost_basis being present and non-zero. Accept the string form.
    # AJOUTE le 27/08/2026 : `math.isfinite`. `float("nan")` REUSSIT sur une
    # chaine, et le NaN qui en sort traversait tout le reste comme une mesure.
    # Mesure de bout en bout :
    #
    #     unrealized_plpc = "-0.60"  -> would_close   (juste)
    #     unrealized_plpc = "nan"    -> HOLDING       silencieux
    #     unrealized_plpc = "inf"    -> would_close   absurde
    #
    # Le NaN est le plus grave : toute comparaison avec lui rend False, donc
    # ni le take-profit ni le stop-loss ne se declenchent, et la position
    # ressort en HOLDING -- l'issue ROUTINIERE, celle qui n'est meme pas
    # journalisee. Alors que le cas voisin (valeur illisible -> None) produit
    # un ExitKind.UNREADABLE bien visible en jaune.
    #
    # Deux chemins « je n'ai pas su lire », deux traitements opposes, a
    # l'endroit precis ou ca compte. On les fait converger : non fini -> None,
    # donc UNREADABLE, donc visible.
    #
    # C'est exactement le correctif de _sharpe() du matin meme, ailleurs : une
    # valeur qui veut dire « je n'ai pas pu mesurer » circulait comme un
    # resultat.
    def _fini(x):
        return x if math.isfinite(x) else None

    plpc = position.get("unrealized_plpc")
    if isinstance(plpc, (int, float)) and not isinstance(plpc, bool):
        return _fini(float(plpc))
    if isinstance(plpc, str) and plpc.strip():
        try:
            return _fini(float(plpc))
        except ValueError:
            pass
    pl = position.get("unrealized_pl")
    cost_basis = position.get("cost_basis")
    try:
        pl = float(pl)
        cost_basis = float(cost_basis)
    except (TypeError, ValueError):
        return None
    if cost_basis == 0:
        return None
    # Le repli peut lui aussi produire un NaN : float("nan") / 840 vaut nan.
    return _fini(pl / cost_basis)


def _today() -> str:
    # CORRIGE le 27/08/2026. datetime.utcnow() est DEPRECIE depuis Python 3.12
    # et sera SUPPRIME. Le workflow CI demande `python-version: "3.x"`, donc la
    # derniere version disponible : le jour ou utcnow() disparait, l'agent ne
    # demarre plus -- pas un avertissement, une panne.
    #
    # Trouve en constatant que TOUTE la suite n'a jamais tourne que sur le
    # Python 3.9 de cette machine, alors que la CI en utilise une autre. Aucun
    # autre interpreteur n'etant installe ici, la verification s'est faite en
    # cherchant les constructions dont le comportement differe, pas en
    # executant.
    #
    # Le remplacement est mecaniquement equivalent : les trois usages
    # n'extraient qu'une DATE UTC, sans arithmetique sur les fuseaux. utcnow()
    # rendait un datetime naif, now(timezone.utc) en rend un conscient -- mais
    # .date() et strftime("%Y-%m-%d") donnent le meme resultat dans les deux cas.
    return datetime.now(timezone.utc).date().isoformat()


def already_traded_today(underlying: str) -> bool:
    """Local, process-independent duplicate-order guard -- checked FIRST in
    check_gates(), before anything that depends on the live API. Answers
    "did THIS process (or an earlier crashed one, today) already submit an
    order for this underlying", from state.json, not from re-querying
    Alpaca. That distinction matters: the already_committed_this_run_by_underlying/
    already_open_this_run_underlyings params added earlier today only protect
    against API lag WITHIN one run's loop over several symbols. They can't protect
    against agent.py crashing right after submit_paper_option_order()
    succeeds but before the position is visible via list_positions(), then
    being re-run (by the operator, or a cron retry) within that same lag window --
    a fresh process has no in-memory state, so it would re-evaluate the
    same symbol from scratch and could resubmit the identical order.
    Recording locally, synchronously, right after submission (see
    record_order_submitted) closes that gap independent of API timing.

    Added 24/08, second pass -- named "idempotency keys on every order...
    a retry after a timeout sends the order twice" in an external
    architecture guide researched after asking what would improve the
    AGENT, not the strategy."""
    state = _load_state()
    record = state.get("traded_today", {})
    return record.get("date") == _today() and underlying.upper() in record.get("symbols", [])


def record_order_submitted(underlying: str) -> None:
    """Call immediately after alpaca_cli.submit_paper_option_order()
    succeeds -- writes synchronously so the record survives even if the
    process crashes on the very next line. Resets the symbol list whenever
    the date rolls over, so this never accumulates across days."""
    with _state_lock():
        state = _load_state()
        record = state.get("traded_today", {})
        if record.get("date") != _today():
            record = {"date": _today(), "symbols": []}
        if underlying.upper() not in record["symbols"]:
            record["symbols"].append(underlying.upper())
        state["traded_today"] = record
        persiste = _save_state(state)
    if not persiste:
        raise StateNotPersisted("state.json is corrupted; the duplicate-order guard was NOT armed for this order")


def is_halted() -> tuple:
    """Manual pause switch: create a file named HALT next to this module
    (any content, or empty) to stop the agent from opening any NEW
    position, without touching credentials, .env, or code -- checked
    before every entry attempt, in agent.py's _run(), AFTER manage_exits()
    has already run. Deliberately does not block exits: a halt is a
    risk-reducing pause on taking on MORE risk, not a reason to also stop
    closing positions that already hit take-profit/stop-loss -- the same
    asymmetry the weekly loss lock already has (see check_gates' lock,
    which also only blocks entries).

    Added 24/08, second pass, after asking what would improve the
    AGENT (not the strategy) and external research
    on both a Alpaca-published reference architecture and a separate
    trading-agent guide independently named an untested/inaccessible kill
    switch as a real production failure mode: "a kill switch nobody can
    activate at 2am is not a control." This is deliberately the simplest
    possible implementation of one -- a file, not a service, a database
    row, or a running process to keep alive -- because the whole point is
    that it has to work even if everything else about the agent's
    environment is degraded. Gitignored (see .gitignore): a local,
    ephemeral operational control, not something to publish or share the
    history of.

    Returns (halted: bool, reason: str)."""
    # CORRIGE le 27/08/2026. C'etait `if not HALT_FILE.exists(): return False`.
    # `Path.exists()` SUIT les liens symboliques et rend False quand la cible
    # manque. Mesure : un lien symbolique casse nomme HALT donnait
    # is_halted() -> (False, '') -- l'agent continuait d'ouvrir des positions
    # alors qu'un fichier nomme HALT etait pose la, cree par un humain.
    #
    # Pour un coupe-circuit, la bonne question n'est pas « la cible est-elle
    # lisible » mais « CE NOM EST-IL LA ». os.lstat() ne suit pas les liens et
    # repond exactement a celle-la.
    #
    # Et une erreur qui n'est pas ENOENT (permissions, E/S) compte desormais
    # comme une PAUSE, avec le diagnostic dans la raison. Avant, EACCES faisait
    # remonter un PermissionError brut depuis les entrailles de pathlib :
    # l'agent s'arretait quand meme -- verifie -- mais par un plantage, pas par
    # une decision, et le tableau de bord n'affichait qu'une trace. Ne pas
    # pouvoir determiner si l'operateur a demande l'arret doit se lire comme un
    # arret : c'est la seule direction sure, et elle ne bloque que les ENTREES,
    # jamais les sorties (voir le docstring ci-dessus).
    try:
        os.lstat(HALT_FILE)
    except FileNotFoundError:
        return False, ""
    except OSError as err:
        return True, (
            "HALT file could not be checked (%s: %s) -- treating the agent as "
            "PAUSED. A kill switch that cannot be read is not a kill switch that "
            "is off. Exits are unaffected." % (type(err).__name__, err)
        )

    try:
        content = HALT_FILE.read_text(encoding="utf-8").strip()
    except OSError as err:
        return True, (
            "HALT file present but unreadable (%s) -- paused. Its reason text "
            "could not be recovered." % type(err).__name__
        )
    reason = content if content else "HALT file present (no reason given)"
    return True, reason


def _record_exit_outcome(is_win: bool, account_id: Optional[str] = None, equity: Optional[float] = None) -> int:
    """Updates the consecutive-loss counter in state.json: a win resets it
    to 0, a loss increments it. Returns the new count.

    Added 24/08, second pass -- "consecutive_losses: 3" appears as a named
    escalation trigger in an external trading-agent architecture guide,
    distinct from and complementary to the weekly %-drawdown lock: a fast
    losing streak can be a real signal before it adds up to -3% of equity.
    Scope, stated honestly: this only sees losses the AGENT ITSELF closed
    via manage_exits() (take-profit/stop-loss). A position closed some
    other way (manually by the operator, expiry, a broker-side liquidation) isn't
    seen here -- not full account-wide P&L tracking, just a check on the
    agent's own run of decisions, which is what MAX_CONSECUTIVE_LOSSES is
    actually meant to catch: "is my own signal currently not working."

    Once the counter reaches MAX_CONSECUTIVE_LOSSES, check_gates() blocks
    new entries -- a sticky stop, same as the weekly lock, cleared the same
    way (state.json reset or a win bringing the count back to 0 before the
    cap is hit). Deliberately NOT self-resetting once tripped: if new
    entries are blocked, no new trade can ever produce the win that would
    reset it, which is the point -- a losing streak is a "stop and have a
    human look" signal, not something the agent should quietly work
    through on its own.

    account_id/equity added 25/08, on re-review: this function used to
    mutate state["consecutive_losses"] with NO idea which account's exit
    actually caused the mutation. check_gates() is the only place that
    compares state.json's saved account_id against the currently active
    one and re-baselines (_record_starting_equity) -- and manage_exits()/
    monitor_exits.py never goes through check_gates() by design (exits
    must keep running under a lock, so they can't be gated on anything).
    Reproduced 25/08: seeded state.json as account "A"'s (consecutive_losses:
    1), then closed a losing position while alpaca_cli was mocked to
    represent a DIFFERENT account "B" -- consecutive_losses on disk went to
    2, still labeled account_id "A", with nothing anywhere recording that
    the loss producing that "2" was actually B's. Not hypothetical for this
    project specifically: monitor_exits.py is scheduled via launchd to run
    unattended every 15 minutes, and this same project's own workflow
    repeatedly swaps .env by hand for testing -- if that scheduled job ever
    fires during such a swap window, and .env is switched back before any
    check_gates() call happens on the account it was briefly pointed at,
    the real account's circuit breaker silently inherits a stranger's
    loss/win history, with no warning anywhere, because state.json's
    account_id never gets compared or corrected on this path.

    Fix: when account_id is supplied (manage_exits() always supplies it
    now), reconcile through the SAME _record_starting_equity() check_gates()
    already relies on -- a no-op when it already matches (every routine
    15-minute tick, once an account is settled), a full reset (including
    this very counter, to 0) when it doesn't, so the win/loss update below
    always applies to a freshly-correct baseline for whichever account's
    position actually just closed, never to a number left behind under
    someone else's account_id. Optional/default-None so a caller that
    genuinely doesn't have an account_id handy (none exist today, but
    future ones might in a mocked/offline context) degrades to the old,
    account-blind behavior rather than raising -- narrower than before, not
    a new failure mode."""
    with _state_lock():
        state = _load_state()
        if account_id is not None:
            state = _record_starting_equity(equity or 0.0, state, account_id)
        count = 0 if is_win else state.get("consecutive_losses", 0) + 1
        state["consecutive_losses"] = count
        persiste = _save_state(state)
    if not persiste:
        raise StateNotPersisted(f"state.json is corrupted; the consecutive-loss count ({count}) was NOT persisted")
    return count


class ExitKind(str, Enum):
    """What happened to one position during a manage_exits() pass. A str
    Enum on purpose: `action.kind == "holding"` still reads naturally at
    every call site, no import of this class required just to compare."""
    HOLDING = "holding"
    CLOSED = "closed"
    WOULD_CLOSE = "would_close"
    UNREADABLE = "unreadable"  # position present, but its P&L% couldn't be read
    ERROR = "error"            # the close attempt itself raised
    # AJOUTE le 27/08/2026 : position presente, mais on ne sait pas la CLASSER
    # -- ni option reconnaissable, ni action declaree. Voir la boucle de
    # manage_exits() pour la raison.
    UNRECOGNISED = "unrecognised"
    # AJOUTE le 29/08/2026. Position DECLAREE comme action ordinaire -- donc
    # parfaitement classee, contrairement a UNRECOGNISED -- mais cet agent
    # n'ouvre JAMAIS d'action : il n'achete que des options a 7-21 jours.
    # Une ligne actions sur ce compte ne peut donc venir que d'un exercice ou
    # d'une assignation a l'echeance. Voir manage_exits().
    EQUITY_UNEXPECTED = "equity_unexpected"


@dataclass
class ExitAction:
    """Structured replacement (24/08) for the plain human-readable strings
    manage_exits() used to return. Found while writing the persistent-
    failure dedup logic in monitor_exits.py: deciding "is this the same
    problem as last time" by re-parsing a sentence built for a human to
    read (matching ": holding (" as the one routine substring) was already
    fragile -- the exact gap the engineering log flagged as "the last place in
    the code where a human-readable string decides control flow" once the
    other four were fixed earlier. `kind` and the structured fields below
    are what callers should branch on; `text` / `__str__` exist purely for
    display and are kept byte-for-byte identical to the original sentences
    so `monitor_exits.log` and printed output don't change shape.

    `to_dict()` is what actually lands in decision_log.jsonl and therefore
    docs/data.json -- a plain, JSON-serializable dict, never this class
    itself. docs/index.html was updated alongside this to accept either
    shape, since decision_log.jsonl is committed (never rewritten) and
    already holds thousands of exit_actions entries as bare strings from
    before this change."""
    symbol: str
    kind: ExitKind
    pnl_pct: Optional[float] = None
    label: Optional[str] = None  # "take-profit" / "stop-loss", set for CLOSED/WOULD_CLOSE
    consecutive_losses: Optional[int] = None  # set only on a successful stop-loss CLOSE
    bookkeeping_error: Optional[str] = None   # set only if that same streak update then failed
    error: Optional[str] = None               # exception text, for UNREADABLE / ERROR

    def __str__(self) -> str:
        if self.kind == ExitKind.HOLDING:
            return (f"{self.symbol}: holding ({self.pnl_pct:+.1%}, thresholds are "
                     f"+{TAKE_PROFIT_PCT:.0%}/-{STOP_LOSS_PCT:.0%})")
        if self.kind == ExitKind.UNREADABLE:
            return f"{self.symbol}: could not read unrealized P&L% — leaving position open"
        if self.kind == ExitKind.WOULD_CLOSE:
            return f"{self.symbol}: WOULD CLOSE — {self.label} hit ({self.pnl_pct:+.1%})"
        if self.kind == ExitKind.CLOSED:
            if self.consecutive_losses is not None:
                streak_note = f", consecutive losses now {self.consecutive_losses}"
            elif self.bookkeeping_error is not None:
                streak_note = f" (consecutive-loss count NOT updated: {self.bookkeeping_error})"
            else:
                streak_note = ""
            return f"{self.symbol}: CLOSED — {self.label} hit ({self.pnl_pct:+.1%}){streak_note}"
        if self.kind == ExitKind.ERROR:
            return f"{self.symbol}: ERROR managing this position ({self.error}) — left open, check manually"
        return f"{self.symbol}: {self.kind.value}"  # unreachable in practice; never silently blank

    def to_dict(self) -> dict:
        d: dict = {"symbol": self.symbol, "kind": self.kind.value, "text": str(self)}
        if self.pnl_pct is not None:
            d["pnl_pct"] = round(self.pnl_pct, 4)
        if self.label is not None:
            d["label"] = self.label
        if self.consecutive_losses is not None:
            d["consecutive_losses"] = self.consecutive_losses
        if self.bookkeeping_error is not None:
            d["bookkeeping_error"] = self.bookkeeping_error
        if self.error is not None:
            d["error"] = self.error
        return d

    def is_routine(self) -> bool:
        return self.kind == ExitKind.HOLDING

    def failure_signature(self) -> Optional[tuple]:
        """Identity used by monitor_exits.py to recognize "this is the same
        stuck problem as last time" rather than a fresh one. None for
        anything that isn't a failure (holding/closed/would_close never
        need dedup: holding is filtered before logging anyway, and a close
        can't repeat -- the position leaves list_positions() once it's
        closed).

        Uses only the leading "ExceptionType" prefix of `error`, not the
        full text -- found minutes after writing the first version, by
        reproducing against a realistic error message instead of trusting
        the mocked static strings every test up to that point had used.
        alpaca_cli.py builds AlpacaCLIError from `result.stderr` (see its
        _run_cli, subprocess error path), which for a real transient network
        failure varies call to call (connection timing, a retry count the
        CLI itself reports) even when it's the exact same underlying
        problem recurring. Keying on the full string meant the SAME stuck
        failure produced a DIFFERENT signature almost every 15-minute check
        -- monitor_exits.py's heartbeat throttle would never engage against
        the one case (a persistent network/API issue) it exists to catch,
        silently reverting to logging every occurrence, the exact flooding
        this dedup layer was built to prevent. `type(e).__name__: message`
        is the format every raise site in this codebase already follows
        (grepped, not assumed), so splitting on the first ": " reliably
        recovers a stable exception-class identity; a message with no colon
        (e.g. UNREADABLE's fixed string, which has none) falls back to the
        whole string unchanged, so that case is unaffected."""
        if self.kind in (ExitKind.ERROR, ExitKind.UNREADABLE):
            error_kind = (self.error or "").split(":", 1)[0].strip() or (self.error or "")
            return (self.symbol, self.kind.value, error_kind)
        return None


def _premiere_fois_qu_on_compte_cette_sortie(option_symbol: str, est_un_gain: bool, symboles_ouverts: set) -> bool:
    """True si la sortie de CE contrat n'a pas deja ete comptabilisee.

    AJOUTE le 27/08/2026. Le compteur de pertes consecutives comptait des
    TENTATIVES DE FERMETURE, pas des positions fermees.

    close_position() soumet un ordre de cloture ; l'execution est asynchrone.
    Entre la soumission et le fill, la position figure toujours dans
    list_positions(). Le moniteur repasse 15 minutes plus tard, revoit le meme
    contrat sous le seuil, le referme -- et recompte la perte.

    Reproduit le 27/08, meme position a -55%, close_position reussissant a
    chaque passage sans que la position disparaisse :

        passage  fermetures  consecutive_losses
        1        1           1
        2        2           2
        3        3           3   <- MAX_CONSECUTIVE_LOSSES atteint
        5        5           5

    UNE position bloquee faisait donc sauter le disjoncteur en 45 minutes, sur
    la foi de trois pertes qui n'en etaient qu'une -- et soumettait un ordre de
    cloture en double a chaque cycle.

    Atteignable des que la cloture ne prend pas effet avant le passage suivant :
    ordre rejete de facon asynchrone, marche qui ferme juste apres la
    soumission, ou fill PARTIEL (la quantite baisse, la position reste ouverte
    et toujours sous le seuil).

    La memoire se purge d'elle-meme : un contrat qui n'est plus dans les
    positions ouvertes en sort. Pas de date, donc rien a faire expirer -- et
    une position bloquee plusieurs jours reste comptee UNE fois, pas une par
    jour. On continue de RE-TENTER la fermeture a chaque passage (c'est le bon
    comportement : la premiere n'a pas pris effet), on ne la recompte plus.

    La memoire retient le couple (contrat, ISSUE), pas le seul contrat. Trouve
    en re-lisant ce correctif : avec le seul symbole, une position bloquee dont
    l'issue passerait de perte a gain verrait son gain ignore -- donc le
    compteur de pertes consecutives ne serait PAS remis a zero, alors qu'un
    gain est precisement ce qui doit le remettre a zero. Le cas est extreme (il
    faut un aller-retour de plus de 100 points de pourcentage sans que la
    cloture prenne effet), mais la version correcte ne coute qu'un dictionnaire
    au lieu d'un ensemble."""
    with _state_lock():
        state = _load_state()
        if state.get("_corrupted"):
            # Etat illisible : on ne peut pas savoir si c'est un doublon. On
            # compte, ce qui ferme le disjoncteur plus tot -- le cote sur. De
            # toute facon _save_state refusera d'ecrire par-dessus.
            return True
        memoire = state.get("exits_counted") or {}
        if not isinstance(memoire, dict):
            memoire = {}          # ancienne forme (liste) ou valeur aberrante
        # Purge : un contrat qui n'est plus ouvert n'a plus a etre memorise.
        memoire = {k: v for k, v in memoire.items() if k in symboles_ouverts}
        issue = "win" if est_un_gain else "loss"
        premiere = memoire.get(option_symbol) != issue
        if premiere:
            memoire[option_symbol] = issue
        state["exits_counted"] = memoire
        _save_state(state)
        return premiere


def manage_exits(dry_run: bool = False) -> List[ExitAction]:
    """Checks every open option position and closes any that have hit the
    take-profit or stop-loss threshold on unrealized P&L. Called once at
    the start of each run, before evaluating any new entry — position
    management isn't conditional on whether a new trade looks good today.
    Returns one structured ExitAction per position (see that class) --
    `str(action)` reproduces the original human-readable line, for
    printing and for anything reading old decision_log.jsonl entries.

    dry_run=True never calls close_position (a real order), only reports
    what it would have done — same contract as agent.py's --dry-run for
    the rest of the pipeline. Consistently, it also does NOT update the
    consecutive-loss counter in dry-run mode -- a simulated close is not a
    real outcome to count.

    Each position's close attempt is wrapped in its own try/except -- found
    24/08, on re-review, the most important gap of the day: this loop
    can hold up to MAX_OPEN_POSITIONS positions since the multi-position
    redesign, but close_position() was called with NO per-position
    isolation, unlike every other per-item loop already fixed earlier today
    (evaluate_symbol, agent.py's entry loop, backtest.py,
    compare_strategies.py). If closing position A raised (a transient CLI
    hiccup, a network blip, an already-closed position via a race with a
    manual close) the exception would propagate straight out of this
    function -- meaning position B, checked immediately after A in the same
    loop, would NEVER get its own take-profit/stop-loss check THIS run, even
    if B independently needed closing too. This is the single function
    monitor_exits.py exists to make sure keeps running often -- and unlike
    every other exception-isolation gap found today (which all failed safe,
    just refusing otherwise-fine trades), this one is the first to fail on
    the DANGEROUS side: a real losing position could sit open, unmanaged,
    specifically because an unrelated position's close attempt failed
    earlier in the same loop. Not yet triggered for real -- found by
    re-reading this function immediately after fixing the same-shaped gap
    in check_gates(), not by a live failure."""
    actions: List[ExitAction] = []
    # Materialise une fois : la liste sert AUSSI a purger la memoire des sorties
    # deja comptees (voir _premiere_fois_qu_on_compte_cette_sortie).
    positions = list(alpaca_cli.list_positions())
    symboles_ouverts = {str(p.get("symbol", "")) for p in positions}
    for pos in positions:
        asset_class = str(pos.get("asset_class", "")).lower()
        symbol = str(pos.get("symbol", ""))
        # CORRIGE le 27/08/2026, en relisant le correctif d'entree du meme jour.
        #
        # Cette ligne etait une COPIE de la logique d'alpaca_cli.is_option_position(),
        # et les deux copies avaient deja diverge : l'originale normalise la
        # casse depuis ce matin, celle-ci non, donc un symbole en minuscules
        # echappait encore ici. Une regle ecrite deux fois finit toujours par
        # etre vraie a un seul endroit -- on appelle la fonction.
        if not alpaca_cli.is_option_position(pos):
            # Et surtout : le `continue` etait NU. Une position qu'on ne sait
            # pas classer disparaissait sans AUCUNE trace -- pas d'ExitAction,
            # pas de ligne de journal, rien sur le tableau de bord. Un P&L
            # illisible produit au moins une action UNREADABLE visible ; ne pas
            # savoir de QUOI il s'agit ne produisait rien du tout.
            #
            # Or manage_exits() est le seul mecanisme protegeant une position
            # ouverte : Alpaca ne supporte pas les ordres bracket/OCO sur
            # options. Ecarter en silence, c'est decider qu'une position n'a
            # pas besoin de stop-loss sans l'avoir verifie.
            #
            # Une action ORDINAIRE reste ecartee en silence : elle est
            # explicitement declaree comme telle, il n'y a pas de doute a
            # signaler, et une alerte a chaque passage est le bruit qui apprend
            # a ignorer un journal.
            if "equity" not in asset_class:
                actions.append(ExitAction(
                    symbol, ExitKind.UNRECOGNISED,
                    error="position ni reconnue comme option (asset_class=%r, "
                          "symbole non-OCC) ni declaree comme action -- aucun "
                          "stop-loss ne peut lui etre applique, verifier a la "
                          "main" % asset_class))
            else:
                # CORRIGE le 29/08/2026. Une action ordinaire etait ecartee en
                # SILENCE, au motif qu'elle est « explicitement declaree comme
                # telle, il n'y a pas de doute a signaler ».
                #
                # Ce raisonnement vaut pour un outil general. Il ne vaut pas
                # ici : CET agent n'ouvre jamais d'action. DEFAULT_UNIVERSE ne
                # sert qu'a choisir un CONTRAT, et find_near_the_money_contract
                # ne rend que des symboles OCC a 7-21 jours. Une ligne actions
                # sur ce compte ne peut donc venir que d'un EXERCICE ou d'une
                # ASSIGNATION a l'echeance.
                #
                # Et c'est exactement le scenario mesure le 29/08 : la seule
                # position ouverte est un put SPY 769 qui expire le 04/09, le
                # jour de la date limite, avec SPY a 769,28 -- a la monnaie a
                # 0,04 % pres. Une option laissee dans la monnaie a l'echeance
                # est exercee automatiquement : 200 SPY short, ~154 000 $ de
                # notionnel sur un compte de 100 000 $. Les regles +50/-50 %
                # ne s'y opposent pas, et manage_exits est le SEUL mecanisme
                # qui protege une position ouverte.
                #
                # AUCUN SEUIL N'EST AJOUTE et rien n'est ferme : ce serait un
                # garde de risque, et aucun seuil de ce depot ne bouge sans
                # decision humaine. On MESURE et on DIT -- meme choix que la
                # marge avant la cloche et que le compte a rebours d'echeance.
                #
                # Zero bruit en fonctionnement normal : cette branche ne peut
                # se declencher que si une action apparait, ce qui n'arrive
                # jamais tant qu'aucune option n'est exercee.
                actions.append(ExitAction(
                    symbol, ExitKind.EQUITY_UNEXPECTED,
                    error="position ACTIONS sur un compte qui n'en ouvre "
                          "jamais (asset_class=%r) : cet agent n'achete que "
                          "des options, donc celle-ci vient d'un exercice ou "
                          "d'une assignation a l'echeance. Aucun stop-loss ne "
                          "lui est applique -- a traiter a la main."
                          % asset_class))
            continue

        try:
            plpc = _extract_unrealized_plpc(pos)
            if plpc is None:
                actions.append(ExitAction(symbol, ExitKind.UNREADABLE,
                                           error="unrealized_plpc missing or unparseable in `alpaca position list` output"))
                continue

            would_close_profit = plpc >= TAKE_PROFIT_PCT
            would_close_loss = plpc <= -STOP_LOSS_PCT

            if would_close_profit or would_close_loss:
                label = "take-profit" if would_close_profit else "stop-loss"
                if dry_run:
                    actions.append(ExitAction(symbol, ExitKind.WOULD_CLOSE, pnl_pct=plpc, label=label))
                else:
                    # AJOUTE le 28/08/2026, matin du kickoff. check_gates
                    # refuse desormais une ENTREE sur un compte qui n'est pas
                    # celui declare ; les SORTIES n'avaient pas d'equivalent.
                    #
                    # Le precedent du HALT ne s'applique pas ici, et c'est ce
                    # qui a fait pencher : une pause bloque le risque NOUVEAU
                    # mais laisse proteger le risque EXISTANT. Sur un mauvais
                    # compte, il n'y a AUCUN risque existant a nous : les
                    # positions vues appartiennent a l'autre compte, et chaque
                    # cloture est un ordre non voulu. Ne rien faire ne laisse
                    # aucune position de ce dossier sans protection -- on n'y
                    # est meme pas connecte.
                    #
                    # L'appel est paye ICI et pas en tete de manage_exits() :
                    # il n'a lieu que quand une cloture se declenche
                    # reellement, ce qui est rare. La minimalite par tick que
                    # le docstring de monitor_exits.py revendique est donc
                    # intacte -- verifie : ce bloc est sous
                    # `if would_close_profit or would_close_loss`.
                    try:
                        refus = config.raison_de_refus_du_compte(
                            alpaca_cli.get_account())
                    except Exception as e:
                        actions.append(ExitAction(
                            symbol, ExitKind.ERROR,
                            error="refused to close: could not verify which "
                                  "account this run is on (%s: %s)"
                                  % (type(e).__name__, e)))
                        continue
                    if refus:
                        actions.append(ExitAction(
                            symbol, ExitKind.ERROR,
                            error="refused to close: %s. Closing here would "
                                  "place an unintended order on another "
                                  "account." % refus))
                        continue
                    alpaca_cli.close_position(symbol)
                    # _record_exit_outcome() is bookkeeping AFTER the close
                    # already succeeded -- wrapped in its own inner
                    # try/except, separate from the outer one, so that a
                    # failure updating the consecutive-loss counter (a
                    # state.json write hiccup, for instance) can never get
                    # mislabeled by the outer except as "left open, check
                    # manually" below. Found 24/08 re-reading my OWN fix
                    # from moments earlier in this same review pass
                    # pass: the position IS closed at this point -- only the
                    # streak count might be stale -- and reporting the
                    # opposite would be actively misleading, not just
                    # unhelpful, on the one action (a real stop-loss firing)
                    # this project cares most about being honest about.
                    consecutive_losses = None
                    bookkeeping_error = None
                    # account/equity fetched here, not once at the top of
                    # manage_exits() -- only paid for when a close actually
                    # fires (rare: most 15-minute ticks are all HOLDING),
                    # same "only pay the API cost when you actually need to
                    # act" shape as _check_cli_version's once-per-process
                    # cache. See _record_exit_outcome's docstring for why
                    # this call exists at all: without it, this bookkeeping
                    # had no way to notice state.json belongs to a
                    # DIFFERENT account than the one that just closed.
                    account_id = None
                    account_equity = None
                    try:
                        account = alpaca_cli.get_account()
                        account_id = account.get("id")
                        account_equity = float(account.get("equity", account.get("portfolio_value", 0)))
                    except Exception as e:
                        # Can't reconcile the account without this call --
                        # fall through with account_id=None, which makes
                        # _record_exit_outcome skip reconciliation entirely
                        # (old, account-blind behavior) rather than guessing.
                        print(f"  WARNING: could not fetch account info to reconcile {symbol}'s exit "
                              f"bookkeeping against the correct account ({type(e).__name__}: {e}) -- "
                              "recording the outcome against state.json's existing account_id as-is.")
                    deja_compte = not _premiere_fois_qu_on_compte_cette_sortie(
                        symbol, would_close_profit, symboles_ouverts)
                    if deja_compte:
                        print(f"  {symbol}: cloture re-tentee (la precedente n'a pas pris effet), "
                              "mais la sortie a deja ete comptabilisee -- le compteur de pertes "
                              "consecutives n'est PAS re-incremente.")
                    if not would_close_profit:
                        try:
                            if not deja_compte:
                                consecutive_losses = _record_exit_outcome(is_win=False, account_id=account_id, equity=account_equity)
                        except Exception as e:
                            bookkeeping_error = f"{type(e).__name__}: {e}"
                    else:
                        try:
                            if not deja_compte:
                                _record_exit_outcome(is_win=True, account_id=account_id, equity=account_equity)
                        except Exception as e:
                            print(f"  WARNING: {symbol} closed on a win but failed to reset the "
                                  f"consecutive-loss counter ({type(e).__name__}: {e}) -- the close "
                                  "itself is unaffected.")
                    actions.append(ExitAction(symbol, ExitKind.CLOSED, pnl_pct=plpc, label=label,
                                               consecutive_losses=consecutive_losses,
                                               bookkeeping_error=bookkeeping_error))
            else:
                actions.append(ExitAction(symbol, ExitKind.HOLDING, pnl_pct=plpc))
        except Exception as e:
            actions.append(ExitAction(symbol, ExitKind.ERROR, error=f"{type(e).__name__}: {e}"))
    return actions


def check_gates(
    underlying: str,
    option_symbol: str,
    already_committed_this_run_by_underlying: Optional[Dict[str, float]] = None,
    already_open_this_run_underlyings: Optional[set] = None,
) -> RiskDecision:
    """Run every gate in order, cheapest/most-decisive first. Returns a
    single RiskDecision — allowed=False means agent.py must not trade,
    regardless of what the strategy/hindsight_guard verdict said.

    underlying is the stock symbol this option is written on (e.g. "SPY"),
    separate from option_symbol (the OCC contract, e.g. "SPY260831P00763000")
    -- needed since 24/08 to check "is a position already open on THIS
    underlying" without re-parsing the OCC string, now that several
    concurrent positions on DIFFERENT underlyings are allowed.

    already_committed_this_run_by_underlying / already_open_this_run_underlyings,
    added 24/08 after noticing the gap: agent.py can now attempt several
    symbols in ONE run, calling check_gates() once per symbol in a loop.
    Each call re-reads alpaca_cli.list_open_option_positions() from the live
    API -- but a just-submitted paper order isn't guaranteed to show up in
    that list immediately (order submit returns on acceptance, not
    necessarily on fill). Without these params, a second or third symbol in
    the SAME run could pass the total-exposure, sector, and position-count
    checks as if the earlier order(s) from THIS SAME run never happened,
    silently exceeding MAX_TOTAL_RISK_PCT / MAX_SECTOR_EXPOSURE_PCT /
    MAX_OPEN_POSITIONS in aggregate before the API catches up. agent.py
    accumulates both, keyed by underlying, across its loop and passes them
    in on every call after the first.

    Keyed by underlying (not a running total/count) since 24/08, second
    fix, a review pass: the original version of this same-run-lag fix
    (added earlier the same day) took a single running float/int and always
    added it in full, on the assumption the live API is ALWAYS behind
    within one run. That's not guaranteed -- a paper order can fill and
    become visible in list_open_option_positions() before the next symbol
    in agent.py's loop gets checked, especially with only 2-3 API calls
    between submissions. If that happens, the same position would be
    counted TWICE: once via open_positions (now that the API caught up) and
    once via the unconditional this-run addition -- silently shrinking the
    real remaining budget more than actually true. Direction is fail-safe
    (more conservative, not less -- refuses trades that were actually still
    safe, never allows an unsafe one), but a P&L-judged week doesn't want
    real trades refused for a phantom reason either. Fixed by tracking
    per-underlying dollars/membership and only counting an underlying's
    this-run contribution if it does NOT already show up in
    already_on_this_underlying below -- if the API has caught up, the
    freshly-fetched open_positions already accounts for it, so adding the
    this-run figure too would double it.

    Duplicate-underlying isn't at the same risk either way: the loop only
    ever visits each universe symbol once per run, so it can't attempt the
    same underlying twice in a single run by construction."""
    # AJOUTE le 27/08/2026 au soir. Le README affirme, mot pour mot :
    # « Creating a file named HALT at the repo root makes check_gates() refuse
    # every new entry ». C'etait FAUX : la pause etait consultee par agent.py
    # (ligne ~357), jamais par cette fonction. Le comportement etait correct --
    # agent.py est aujourd'hui le seul appelant -- mais la regle etait
    # appliquee par L'APPELANT et non par la porte censee l'appliquer.
    #
    # C'est exactement la these de ce projet retournee contre lui : « une
    # limite qui n'est pas verifiee dans le code est une politique, pas un
    # controle » (titre de la diapo « RISK GUARDRAILS — ENTRY » ; on la
    # designe par son titre et non par son rang, qui a deja bouge une
    # fois). Une pause qui depend du fait que
    # chaque appelant pense a la verifier est une politique.
    #
    # On la rend vraie plutot que d'affaiblir la phrase. agent.py garde sa
    # verification precoce -- elle evite tout le travail d'evaluation et donne
    # un message clair -- et cette porte-ci la refait, pour que tout appelant
    # futur en herite sans y penser. Le fichier est relu a chaque appel : une
    # pause posee EN COURS d'execution prend effet des le symbole suivant.
    #
    # Place avant le premier appel reseau : refuser vite coute moins cher, et
    # is_halted() echoue deja FERME sur toute erreur de lecture autre que
    # « le fichier n'existe pas » (corrige le 26/08, sur un lien symbolique
    # casse qui rendait la pause inoperante).
    en_pause, motif_pause = is_halted()
    if en_pause:
        return RiskDecision(
            False,
            "manual pause active (HALT file present): %s -- no new entry. "
            "Exits keep running; remove the HALT file to resume." % motif_pause)

    account = alpaca_cli.get_account()

    # AJOUTE le 28/08/2026, le matin du kickoff. `config.ACCOUNT_ID` existe,
    # et `test_connection.py` le compare bien au compte reel avec un verdict
    # « MAUVAIS COMPTE » qui sort en erreur. Mais c'est un script LANCE A LA
    # MAIN : ni agent.py ni monitor_exits.py ne faisaient cette comparaison.
    # Verifie par recherche : zero occurrence de ACCOUNT_ID ou
    # account_number dans les deux.
    #
    # Consequence concrete : l'agent planifie de 21:37 tradait sur le compte
    # que designent les identifiants, quel qu'il soit. Or CLAUDE.md pose que
    # le compte du hackathon est « intouchable avant le kickoff -- zero trade,
    # zero test [...] un compte reutilise disqualifie », et l'operateur doit
    # basculer a la main le soir meme. Un oubli, dans un sens ou dans l'autre,
    # n'etait rattrape par rien d'automatique.
    #
    # Meme forme que le reste de la journee : le controle existait, mais pas
    # sur le chemin qui agit. Il est pose ICI parce que check_gates est le
    # passage unique de toute entree -- l'ecrire dans agent.py obligerait a
    # l'ecrire aussi ailleurs, et une regle ecrite deux fois n'est vraie qu'a
    # un seul endroit.
    #
    # Trois etats, comme test_connection.py, et surtout PAS deux :
    #   . attendu declare et DIFFERENT -> refus net ;
    #   . attendu declare et illisible -> refus aussi : on ne peut pas
    #     prouver l'identite du compte sur lequel on s'apprete a engager de
    #     l'argent ;
    #   . aucun attendu declare        -> rien a comparer. On AVERTIT et on
    #     laisse passer, sinon un dossier sans ACCOUNT_ID ne traderait plus
    #     du tout -- le meme choix que le controle d'identifiants du
    #     garde-fou fait dans le meme cas.
    refus = config.raison_de_refus_du_compte(account)
    if refus:
        return RiskDecision(
            False,
            "WRONG ACCOUNT: %s. No new entry. Check which credentials are "
            "loaded before trading -- the hackathon account must not carry "
            "trades meant for another one, and vice versa." % refus)
    if not config.compte_est_declare():
        print("  WARNING: no ALPACA_ACCOUNT_ID declared, so this run cannot "
              "check which account it is trading on. Nothing verifies that "
              "the credentials loaded are the intended ones.", flush=True)

    # ELARGI le 27/08/2026. Le garde `equity <= 0` ci-dessous couvrait deja le
    # champ ABSENT et la valeur ZERO -- les deux cas les plus probables -- mais
    # pas une valeur NON NUMERIQUE. Mesure :
    #
    #     equity absent          -> refus clair, « could not read a usable ... »
    #     equity = "0"           -> refus clair
    #     equity = "non-numeric" -> ValueError: could not convert string to
    #                               float: 'non-numeric'
    #
    # Le sens de l'echec etait deja bon -- l'exception remonte, agent.py la
    # rattrape par symbole et journalise `error`, donc rien ne trade a
    # l'aveugle. Ce qui manquait, c'est le MESSAGE : « could not convert
    # string to float » ne nomme ni l'equite, ni le compte, ni quoi faire,
    # alors que les deux autres cas ont une phrase qui le dit.
    #
    # Meme exigence que partout ailleurs dans ce fichier : echouer ferme ne
    # dispense pas d'echouer clairement.
    brut = account.get("equity", account.get("portfolio_value", 0))
    try:
        equity = float(brut)
    except (TypeError, ValueError):
        return RiskDecision(
            False,
            "could not read a usable equity figure from the account: got %r, "
            "which is not a number. Every cap and every position size is a "
            "percentage of this figure, so nothing is sized until it reads "
            "cleanly." % (brut,))
    # `math.isfinite` ajoute le 27/08 : une equite a NaN ou infinie plantait
    # plus loin sur « cannot convert float NaN to integer » -- fail-closed,
    # donc sans danger, mais avec un message inutile, affiche a l'identique
    # pour NaN ET pour l'infini. Les cas voisins (absente, zero, non
    # numerique) ont tous une phrase qui dit ce qui ne va pas ; celui-la
    # n'en avait pas.
    if not math.isfinite(equity) or equity <= 0:
        return RiskDecision(
            False,
            "could not read a usable equity figure from the account: got %r. "
            "Every cap and every position size is a percentage of this "
            "figure, so nothing is sized until it reads cleanly." % (brut,))

    account_id = account.get("id")
    # TROUVE le 31/08/2026, jour du kickoff : ce read-modify-write (charger,
    # eventuellement re-baseliner, eventuellement ecrire) tournait SANS
    # _state_lock() -- le seul appelant de _record_starting_equity() a ne
    # pas etre garde, alors que _state_lock() existe precisement pour cette
    # classe de defaut (voir son docstring : deux ecritures concurrentes de
    # state.json peuvent effacer un verrou de perte ou un compteur, sans
    # aucune erreur). Reproduit : deux threads appelant _load_state() puis
    # _record_starting_equity() en meme temps sur un state.json neuf --
    # 20/20 essais en FileNotFoundError, les deux ecritures se marchant
    # dessus sur le meme fichier .tmp. C'est exactement le scenario du jour
    # meme : premier run reel de la semaine, starting_equity absent, agent.py
    # relance a la main pendant qu'un passage planifie tourne encore.
    with _state_lock():
        state = _load_state()

        # Checked BEFORE _record_starting_equity(): a corrupted state.json (see
        # _load_state's docstring) would otherwise be treated identically to a
        # brand-new account and silently re-baselined -- clearing any weekly
        # loss lock or consecutive-loss count that was in effect before the
        # corruption happened. Refusing here, without ever calling
        # _record_starting_equity, means state.json is left untouched on disk
        # (still corrupted) until a human deliberately intervenes, rather than
        # this function silently "fixing" it by overwriting it with a fresh,
        # unlocked state.
        if state.get("_corrupted"):
            return RiskDecision(
                False,
                f"{STATE_FILE} is corrupted and could not be parsed -- refusing all new "
                "entries until a human looks (it may be hiding an active weekly loss lock "
                "or consecutive-loss breaker from before a crash). Delete state.json by hand "
                "once you've confirmed it's safe to re-baseline. Exits are unaffected.",
            )

        state = _record_starting_equity(equity, state, account_id)

    # already_traded_today() reads state["traded_today"], which
    # _record_starting_equity() above has just reset if the account
    # changed -- MUST run after that reset, not before. Originally placed
    # before the account fetch (to skip an API call in the common case),
    # moved here 24/08 after finding the bug: a stale traded_today (or
    # consecutive_losses) record from an OLD account would otherwise leak
    # into a brand-new account with zero real trades on it -- the same
    # failure shape _record_starting_equity was already written to prevent
    # for starting_equity/locked, just not extended to these two newer
    # fields when they were added. See the engineering log for the caught-and-
    # fixed writeup; found by testing this exact scenario, not by
    # inspection.
    if already_traded_today(underlying):
        return RiskDecision(False, f"already submitted an order for {underlying} today (local record, state.json) -- not resubmitting on a rerun")

    if state.get("locked"):
        return RiskDecision(False, f"weekly loss lock already active: {state.get('lock_reason')}")

    starting_equity = state["starting_equity"]
    drawdown_pct = (starting_equity - equity) / starting_equity if starting_equity else 0
    if drawdown_pct >= WEEKLY_LOSS_LOCK_PCT:
        reason = (
            f"equity down {drawdown_pct:.1%} from the recorded starting equity "
            f"(${starting_equity:,.2f} -> ${equity:,.2f}), >= the {WEEKLY_LOSS_LOCK_PCT:.0%} weekly lock threshold"
        )
        # Re-lu sous verrou plutot que d'ecrire le `state` charge ~50 lignes
        # plus haut : entre les deux, l'autre processus a pu incrementer le
        # compteur de pertes ou enregistrer un symbole. Ecrire la copie perimee
        # effacerait sa mise a jour. Poser locked=True est monotone -- le
        # rabattre sur l'etat frais est exactement la bonne fusion.
        with _state_lock():
            frais = _load_state()
            if not frais.get("_corrupted"):
                frais["locked"] = True
                frais["lock_reason"] = reason
                _save_state(frais)
        return RiskDecision(False, f"weekly loss lock triggered: {reason}")

    consecutive_losses = state.get("consecutive_losses", 0)
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        return RiskDecision(
            False,
            f"consecutive-loss circuit breaker: {consecutive_losses} stop-losses in a row "
            f"(>= {MAX_CONSECUTIVE_LOSSES}) -- pausing new entries for a human to look, not resetting on its own",
        )

    open_positions = alpaca_cli.list_open_option_positions()

    # CE QUE CETTE LISTE NE CONTIENT PAS, mesure du 29/08/2026. Elle ne rend
    # QUE les options. Apres un exercice ou une assignation a l'echeance, le
    # compte porte une ligne ACTIONS -- et elle est invisible a tout ce qui
    # suit :
    #
    #     list_open_option_positions()  ->  ['SPY260904P00769000']
    #     option_underlying(ligne actions)  ->  None
    #
    #   . la regle « jamais deux positions sur le meme sous-jacent » ne la
    #     voit pas : une nouvelle option SPY serait autorisee alors que le
    #     compte porte deja 200 SPY short ;
    #   . MAX_OPEN_POSITIONS ne la compte pas ;
    #   . les plafonds 1 % / 3 % / 1,5 % somment de la PRIME d'option : une
    #     position actions y contribue zero, quel que soit son notionnel.
    #
    # CE QUI LA VOIT QUAND MEME, et ce n'est pas rien : le verrou de perte
    # hebdomadaire lit l'EQUITE du compte, donc le P&L d'une position actions
    # y entre normalement. Et manage_exits() emet depuis le 29/08 une action
    # EQUITY_UNEXPECTED, journalisee et rendue en rouge sur la page publique,
    # a chacun de ses 28 passages quotidiens.
    #
    # AUCUN REFUS N'EST AJOUTE ICI. Refuser une entree tant qu'une ligne
    # actions traine serait un garde de risque, et aucun seuil de ce depot ne
    # bouge sans decision humaine -- c'est une decision a prendre, pas un
    # oubli a corriger. Elle est ecrite ici pour qu'elle soit prise en
    # connaissance de cause, et non decouverte apres coup.

    # Avant tout dimensionnement : sait-on seulement ce qu'on porte deja ?
    # Voir positions_au_cout_illisible() pour la mesure. Place ici, donc AVANT
    # le plafond sectoriel comme avant le plafond global -- les deux reposent
    # sur la meme somme.
    illisibles = positions_au_cout_illisible(open_positions)
    if illisibles:
        return RiskDecision(
            False,
            "cannot read cost_basis for open position(s): "
            + ", ".join(illisibles)
            + " -- refusing a NEW entry while total exposure is unmeasurable. "
            "Counting them as $0 would let the exposure caps pass on data that "
            "is missing, not small. Exits are unaffected. Fix or close the "
            "position(s), or re-run once the API returns a complete payload.")

    # Voir positions_au_sous_jacent_illisible() pour la mesure. Place AVANT la
    # regle anti-doublon, car c'est elle qui devient invérifiable : un None se
    # glisse sans bruit dans l'ensemble ci-dessous, et « SPY » n'est pas dans
    # {None}.
    sans_sous_jacent = positions_au_sous_jacent_illisible(open_positions)
    if sans_sous_jacent:
        return RiskDecision(
            False,
            "impossible de lire le sous-jacent de "
            + ", ".join(sans_sous_jacent)
            + " : la regle « jamais deux positions sur le meme sous-jacent » "
              "ne peut pas etre verifiee, donc aucune nouvelle entree. Les "
              "sorties restent gerees normalement.")

    already_on_this_underlying = {
        alpaca_cli.option_underlying(pos) for pos in open_positions
    }
    if underlying.upper() in already_on_this_underlying:
        return RiskDecision(False, f"already holding an open option position on {underlying}; not stacking a second one on the same underlying")

    # CORRIGE le 26/08/2026. Ce controle ne consultait QUE l'API, alors que
    # `already_open_this_run_underlyings` existe precisement pour couvrir la
    # fenetre ou l'API n'a pas encore rattrape. Ce parametre n'alimentait que
    # le compteur de positions simultanees, plus bas -- pas la regle
    # anti-doublon, dont il porte pourtant le nom.
    #
    # TROU REPRODUIT, et il demande DEUX conditions:
    #   1. le meme sous-jacent deux fois dans une execution. `agent.py` fait
    #      `[s.strip().upper() for s in args.symbols.split(",")]` SANS
    #      dedoublonner, donc `--symbols SPY,SPY` suffit.
    #   2. l'echec de `record_order_submitted()` -- cas qu'agent.py prevoit
    #      explicitement, signale par un AVERTISSEMENT, et apres lequel il
    #      continue. Sans cet enregistrement, le garde `traded_today` de
    #      state.json ne rattrape plus rien.
    # Mesure: deux ordres sur SPY dans la meme execution, contre une regle
    # que ce projet enonce comme non negociable.
    #
    # A noter, et c'est rassurant sur le reste: l'accumulateur d'exposition
    # TOTALE fonctionnait pendant ce trou -- le second passage dimensionnait 2
    # contrats au lieu de 3, il savait donc que 840 $ etaient deja engages.
    # Seule la regle anti-doublon cedait.
    run_open_upper = {u.upper() for u in (already_open_this_run_underlyings or set())}
    if underlying.upper() in run_open_upper:
        return RiskDecision(
            False,
            f"already submitted an order for {underlying} earlier in THIS run; not stacking a "
            "second one on the same underlying (the live API may not show it yet)",
        )

    # Only count a this-run underlying's contribution if the live API does
    # NOT already show it as open -- otherwise it's already counted via
    # open_positions below, and adding it again would double it. See this
    # function's docstring for the exact failure this prevents.
    run_committed = already_committed_this_run_by_underlying or {}
    run_committed_not_yet_visible = {
        u: v for u, v in run_committed.items() if u.upper() not in already_on_this_underlying
    }
    run_open_underlyings = already_open_this_run_underlyings or set()
    run_open_not_yet_visible = [u for u in run_open_underlyings if u.upper() not in already_on_this_underlying]

    sector = sector_of(underlying)
    sector_committed_this_run = sum(v for u, v in run_committed_not_yet_visible.items() if sector_of(u) == sector)
    sector_committed = _sector_committed(open_positions, sector) + sector_committed_this_run
    sector_cap_dollars = equity * MAX_SECTOR_EXPOSURE_PCT
    remaining_sector_budget = sector_cap_dollars - sector_committed
    if remaining_sector_budget <= 0:
        return RiskDecision(
            False,
            f"sector concentration cap reached for {sector!r}: ${sector_committed:,.2f} already committed, "
            f">= the {MAX_SECTOR_EXPOSURE_PCT:.1%} sector cap (${sector_cap_dollars:,.2f} of ${equity:,.2f} equity)",
        )

    effective_open_count = len(open_positions) + len(run_open_not_yet_visible)
    if MAX_OPEN_POSITIONS <= 0 or effective_open_count >= MAX_OPEN_POSITIONS:
        return RiskDecision(
            False,
            f"already at the concurrent-position cap ({effective_open_count}/{MAX_OPEN_POSITIONS} open"
            + (f", including {len(run_open_not_yet_visible)} opened earlier this run" if run_open_not_yet_visible else "")
            + ")",
        )

    ask = alpaca_cli.get_option_ask_price(option_symbol)
    if ask is None:
        return RiskDecision(False, f"could not price {option_symbol} (no usable ask found); refusing to trade blind")

    cost_per_contract = ask * 100  # options are quoted per share, contracts are 100 shares

    committed_this_run = sum(run_committed_not_yet_visible.values())
    committed = _total_committed(open_positions) + committed_this_run
    total_cap_dollars = equity * MAX_TOTAL_RISK_PCT
    remaining_total_budget = total_cap_dollars - committed
    if remaining_total_budget <= 0:
        return RiskDecision(
            False,
            f"total exposure cap reached: ${committed:,.2f} already committed across "
            f"{effective_open_count} position(s)"
            + (f" (${committed_this_run:,.2f} of that from earlier this run)" if committed_this_run else "")
            + f", >= the {MAX_TOTAL_RISK_PCT:.0%} total cap (${total_cap_dollars:,.2f} of ${equity:,.2f} equity)",
        )

    per_trade_dollars = min(equity * MAX_RISK_PCT_PER_TRADE, remaining_total_budget, remaining_sector_budget)
    qty = int(per_trade_dollars // cost_per_contract)
    if qty < 1:
        return RiskDecision(
            False,
            f"1 contract of {option_symbol} costs ~${cost_per_contract:,.2f}, "
            f"which exceeds the available budget for this trade (${per_trade_dollars:,.2f} "
            f"= min of the {MAX_RISK_PCT_PER_TRADE:.0%} per-trade cap, the "
            f"${remaining_total_budget:,.2f} left under the {MAX_TOTAL_RISK_PCT:.0%} total cap, and the "
            f"${remaining_sector_budget:,.2f} left under the {MAX_SECTOR_EXPOSURE_PCT:.1%} {sector!r} sector cap)",
        )

    actual_cost = qty * cost_per_contract
    return RiskDecision(
        True,
        f"cleared all gates: sizing {qty} contract(s) at ~${cost_per_contract:,.2f} each",
        qty,
        committed_dollars=actual_cost,
    )
