# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

"""hindsight_guard — catch parameter choices that only look good because the
scoring window secretly included data that would not have been knowable yet
at decision time.

The failure shape: you sweep candidate parameters, score each one against
some window of data, and pick the best score. If that window spans past the
point that's supposed to be "unseen" (a holdout, a future period, anything
not available live), the number you optimized against is not the number
you'll actually get live — even though nothing about the code looks wrong.

This is a different failure from a stale *read* (the target of tools like
intervalguard for MCP tool-call caching): the data was never wrong or out of
date, it just extends further in time than the decision it's used to justify.

check_selection_leakage() re-runs your own scoring function twice — once on
the full window, once restricted to what was actually knowable in-sample —
and reports when they disagree about which candidate should win, or when
nothing clears the bar without the excluded data.

Origin: found by hand while auditing a trading strategy backtest where a
leverage cap was chosen using a score computed on the *total* period
(in-sample + out-of-sample + holdout combined). The in-sample score was
negative for every candidate; the "best" cap only won because the holdout
window was folded into the selection criterion. See demo_tsmom.py at
https://github.com/<user>/hindsight-guard for the real numbers.

This copy is vendored into hindsight-alpha (same author, MIT license) so the
agent has no path-dependent import to the sibling repo. Canonical source: the
author's separate hindsight-guard repository.

MIT license. Standard library only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence


class HindsightLeakError(Exception):
    """Raised when a selection only wins because of data outside the
    in-sample window, and raise_on_leak=True was requested."""


@dataclass
class LeakageReport:
    candidates: List[Any]
    full_scores: Dict[Any, float]
    in_sample_scores: Dict[Any, float]
    full_winner: Any
    in_sample_winner: Any
    in_sample_clears_bar: bool
    threshold: float
    unscorable: List[Any] = field(default_factory=list)
    # AJOUTES le 27/08/2026 : TOUS les candidats atteignant le maximum, pas
    # seulement le premier rendu par max(). Voir check_selection_leakage().
    full_winners: List[Any] = field(default_factory=list)
    in_sample_winners: List[Any] = field(default_factory=list)
    agrees: bool = field(init=False)

    def __post_init__(self) -> None:
        # Retrocompatibilite : un appelant qui construit un LeakageReport a la
        # main (les tests de ce depot le font) peut ne pas fournir les
        # ensembles. On les deduit alors du gagnant unique.
        if not self.full_winners:
            self.full_winners = [self.full_winner]
        if not self.in_sample_winners:
            self.in_sample_winners = [self.in_sample_winner]

        # `unscorable` domine tout le reste: si un candidat n'a pas pu etre
        # note, on ne peut pas dire lequel gagne, donc on ne dit pas qu'il n'y
        # a pas de fuite.
        #
        # CORRIGE le 27/08/2026. Le test etait `full_winner == in_sample_winner`,
        # ou chaque gagnant venait de max(), qui rend le PREMIER element
        # atteignant le maximum. Une EGALITE en tete faisait donc dependre le
        # verdict de l'ordre de la liste. Mesure, memes scores exactement :
        #
        #     candidats ['A','B'] -> gagnant plein 'A', agrees=True
        #     candidats ['B','A'] -> gagnant plein 'B', agrees=False
        #
        # Meme question, meme score_fn, verdict inverse -- et les DEUX sens
        # sont atteignables, donc une egalite pouvait fabriquer un certificat
        # « pas de fuite ». Pour une bibliotheque qui existe pour refuser les
        # certificats de complaisance, c'est le sens grave.
        #
        # La regle est desormais l'INCLUSION : la selection n'est sans fuite
        # que si TOUT candidat susceptible d'etre retenu sur la fenetre pleine
        # gagne aussi en in-sample. Si la fenetre pleine est indifferente entre
        # A et B, l'appelant peut retenir B -- et si B perd en in-sample, ce
        # choix-la depend bien de donnees non connaissables.
        #
        # Sans egalite, la regle se reduit exactement a l'ancienne egalite de
        # gagnants : ce n'est pas un durcissement du cas courant.
        # UN SEUL CANDIDAT NE PEUT PAS ETRE EN DESACCORD AVEC LUI-MEME.
        # AJOUTE le 28/08/2026 au soir, trouve en sondant cette fonction sur
        # ses cas limites. Mesure AVANT correctif :
        #
        #     check_selection_leakage([10], lambda c, w: 1.0)
        #     -> agrees=True, « OK: full-window winner (10) matches the
        #        in-sample winner and clears the threshold »
        #
        # Le gagnant est le meme PAR CONSTRUCTION : il n'y avait rien a
        # comparer. Le message se lit pourtant comme une verification reussie.
        # C'est le meme defaut que `unscorable` corrige a cote -- « je n'ai pas
        # pu detecter de desaccord » presente comme « il n'y a pas de
        # desaccord » -- et il touche ici la piece centrale du depot.
        #
        # AUCUN EFFET SUR CE DEPOT, verifie avant d'ecrire : les TROIS
        # appelants passent cinq candidats (CANDIDATE_HV_WINDOWS,
        # CANDIDATE_LOOKBACKS, CANDIDATS du benchmark), tous figes au kickoff.
        # Aucun chiffre publie ne bouge, aucun comportement de trading non
        # plus. Ce correctif rend la bibliotheque honnete pour l'usage general
        # qu'elle documente -- « score_fn decide ce que ces deux mots
        # signifient » -- ou un appelant peut tres bien n'avoir qu'un candidat.
        self.comparable = len(self.candidates) >= 2

        self.agrees = (
            self.comparable
            and not self.unscorable
            and bool(self.full_winners)
            and all(g in self.in_sample_winners for g in self.full_winners)
            and self.in_sample_clears_bar
        )

    def _plein_franchit_le_seuil(self) -> bool:
        """Le meilleur score sur la fenetre PLEINE depasse-t-il le seuil ?

        Sert a distinguer « la selection ne tient que grace a des donnees non
        connaissables » (fuite) de « rien ne gagne nulle part » (pas d'edge).
        Meme comparaison stricte que in_sample_clears_bar : `>` et non `>=`."""
        try:
            return self.full_scores[self.full_winner] > self.threshold
        except (KeyError, TypeError):
            return False

    def verdict_label(self) -> str:
        """Le verdict en UN mot-cle, pour les rapports ecrits.

        AJOUTE le 27/08/2026. backtest.py et compare_strategies.py ecrivaient
        chacun `'agrees' if agrees else 'LEAK DETECTED'` -- un binaire, alors
        qu'`agrees` est faux dans TROIS cas dont un qui n'a rien d'une fuite.
        Corrige d'abord dans backtest.py seulement ; le jumeau a ete oublie
        une heure, ce qui est exactement l'argument pour poser la logique ICI
        plutot que chez les appelants. Deux constructions independantes de la
        meme regle finissent toujours par diverger -- ici en trois heures."""
        if self.agrees:
            return "agrees"
        if not getattr(self, "comparable", True) or self.unscorable:
            return "CANNOT CONCLUDE"
        if not self.in_sample_clears_bar and not self._plein_franchit_le_seuil():
            return "NO EDGE"
        return "LEAK DETECTED"

    def summary(self) -> str:
        lines = []
        if self.agrees:
            lines.append(
                f"OK: full-window winner ({self.full_winner!r}) matches the in-sample "
                f"winner and clears the threshold ({self.threshold})."
            )
        elif not getattr(self, "comparable", True):
            lines.append(
                "CANNOT CONCLUDE: only one candidate was given, and a single "
                "candidate cannot disagree with itself."
            )
            lines.append(
                "  -> the two winners match by construction, not by evidence. "
                "Nothing was compared, so nothing is certified leak-free."
            )
        elif self.unscorable:
            lines.append(
                "CANNOT CONCLUDE: score_fn returned a non-finite value (NaN or "
                "infinity) for " + ", ".join(repr(c) for c in self.unscorable) + "."
            )
            lines.append(
                "  -> a candidate that could not be scored is not a candidate that "
                "lost. Refusing to certify this selection as leak-free."
            )
        elif not self.in_sample_clears_bar and not self._plein_franchit_le_seuil():
            # AJOUTE le 27/08/2026, trouve en faisant tourner le pipeline
            # complet sur des barres synthetiques plausibles.
            #
            # Quand AUCUN candidat ne franchit le seuil -- ni en in-sample, NI
            # sur la fenetre pleine -- le message annoncait quand meme :
            #
            #   LEAK DETECTED: this selection depends on data outside the
            #     in-sample window.
            #     full-window winner: 90  (score -0.3807)
            #     -> the apparent winner exists only because the scoring window
            #        included data that would not have been knowable ...
            #
            # Le gagnant « apparent » a un score NEGATIF. Il n'existe pas « a
            # cause de » donnees futures : il perd des deux cotes. Il n'y a pas
            # de fuite, il n'y a pas d'edge -- deux verdicts qu'un outil de ce
            # nom ne peut pas se permettre de confondre. Annoncer une fuite la
            # ou rien n'a fuite est un faux positif dans le TITRE.
            #
            # Le REFUS ne bouge pas d'un iota (agrees reste False, on ne trade
            # pas). Seule la raison change -- et c'est elle qu'un juge lit.
            meilleur = self.full_scores[self.full_winner]
            lines.append(
                "NO EDGE: no candidate clears the threshold on EITHER window."
            )
            lines.append(
                f"  best full-window score:  {self.full_winner!r}  "
                f"({meilleur:.4f}, threshold {self.threshold})"
            )
            lines.append(
                f"  best in-sample score:    "
                f"{self.in_sample_scores[self.in_sample_winner]:.4f}"
            )
            lines.append(
                "  -> this is NOT a hindsight leak: nothing wins on the full "
                "window either. There is simply nothing here worth selecting."
            )
        else:
            # CORRIGE le 27/08/2026, apres `hindsight_benchmark.py`.
            #
            # Ce titre affirmait comme un FAIT que la selection « depend de
            # donnees hors de la fenetre in-sample ». Le banc montre que la
            # meme signature -- le gagnant change quand on retire le holdout --
            # est produite par le seul bruit d'estimation :
            #
            #   candidats REELLEMENT equivalents, aucune fuite  -> 45.2%
            #   aucun edge du tout, aucune fuite                -> 38.0%
            #
            # Le REFUS reste juste dans tous les cas : une selection instable
            # ne merite pas qu'on trade dessus, quelle qu'en soit la cause. Ce
            # qui ne tenait pas, c'est la CAUSE annoncee. Meme raisonnement que
            # l'extraction de « NO EDGE » ci-dessus, pousse d'un cran : ce
            # module ne peut pas se permettre de nommer une fuite la ou il a
            # seulement mesure une instabilite.
            lines.append(
                "LEAK DETECTED: the winning candidate changes when the "
                "unknowable-at-the-time data is removed."
            )
            lines.append(
                f"  full-window winner:      {self.full_winner!r}  "
                f"(score {self.full_scores[self.full_winner]:.4f})"
            )
            if self.in_sample_clears_bar:
                lines.append(
                    f"  in-sample winner:        {self.in_sample_winner!r}  "
                    f"(score {self.in_sample_scores[self.in_sample_winner]:.4f})"
                )
                # AJOUTE le 27/08/2026, juste apres le correctif d'ordre. Le
                # verdict etait redevenu juste, mais son explication se
                # contredisait -- mesure sur une egalite :
                #
                #   full-window winner:      'A'  (score 1.0000)
                #   in-sample winner:        'A'  (score 1.0000)
                #   -> the two windows disagree about which candidate is best.
                #
                # Le meme candidat nomme deux fois, suivi d'une phrase qui
                # affirme un desaccord. Un juge qui lit ca conclut que l'outil
                # est casse. La vraie cause du refus est ailleurs : la fenetre
                # pleine ne DEPARTAGE pas les candidats, et l'un des ex aequo
                # perd en in-sample.
                lines.append(
                    "  -> this is evidence of selection INSTABILITY. Leakage is "
                    "its most interesting cause, not its only one: estimation "
                    "noise alone yields the same signature ~45% of the time "
                    "when two candidates are genuinely equivalent (measured, "
                    "see HINDSIGHT_BENCHMARK.md). The refusal stands either "
                    "way; what does not follow is 'this depends on future "
                    "data'."
                )
                perdants = [c for c in self.full_winners
                            if c not in self.in_sample_winners]
                if len(self.full_winners) > 1:
                    lines.append(
                        "  -> the full window TIES between "
                        + ", ".join(repr(c) for c in self.full_winners)
                        + ", so which one gets picked is arbitrary; "
                        + ", ".join(repr(c) for c in perdants)
                        + " does not win in-sample. A selection that depends on "
                        "breaking that tie is not leak-free."
                    )
                else:
                    lines.append("  -> the two windows disagree about which candidate is best.")
            else:
                best_is = max(self.in_sample_scores, key=self.in_sample_scores.get)
                lines.append(
                    f"  no candidate clears the in-sample threshold ({self.threshold}); "
                    f"best in-sample score is {self.in_sample_scores[best_is]:.4f} "
                    f"({best_is!r})."
                )
                lines.append(
                    "  -> the apparent winner exists only because the scoring window "
                    "included data that would not have been knowable at decision time."
                )
        return "\n".join(lines)


def check_selection_leakage(
    candidates: Sequence[Any],
    score_fn: Callable[[Any, str], float],
    *,
    threshold: float = 0.0,
    raise_on_leak: bool = False,
) -> LeakageReport:
    """Re-score every candidate on two windows and compare the winners.

    score_fn(candidate, window) -> float
        `window` is either "full" or "in_sample". This library never touches
        your data — score_fn decides what those two words mean (a date
        slice, a row mask, a different dataset entirely). All this function
        does is call it twice per candidate and compare verdicts.

    threshold
        A candidate only "clears the bar" in-sample if its in-sample score
        is strictly greater than this. Mirrors: an in-sample Sharpe that's
        negative doesn't justify picking anything, no matter how good the
        full-window number looks.

    raise_on_leak
        If True, raise HindsightLeakError instead of returning a report that
        says agrees=False. Useful as a hard gate in a pipeline; leave False
        to just inspect the report.
    """
    if not candidates:
        # `max()` sur un dictionnaire vide leve "max() arg is an empty
        # sequence", ce qui ne dit rien a l'appelant de ce qu'il a mal fait.
        raise ValueError(
            "check_selection_leakage() needs at least one candidate; got none. "
            "With a single candidate the disagreement test is vacuous by "
            "construction (the same candidate wins both windows), so two or "
            "more is what makes this check meaningful."
        )

    # AJOUTE le 27/08/2026. Les scores vivent dans un dictionnaire indexe par
    # candidat : un doublon s'ecrase en silence. Mesure avant correctif --
    # 3 candidats declares, 2 notes, agrees=True. Un balayage de N parametres
    # qui en teste discretement M est exactement la panne silencieuse que ce
    # module existe pour empecher, ici dans son propre code.
    vus, doublons = set(), []
    for c in candidates:
        if c in vus and c not in doublons:
            doublons.append(c)
        vus.add(c)
    if doublons:
        raise ValueError(
            "check_selection_leakage() got duplicate candidates: "
            + ", ".join(repr(c) for c in doublons)
            + ". Scores are keyed by candidate, so a duplicate would silently "
            "collapse and the sweep would test fewer candidates than it "
            "reports. De-duplicate before calling."
        )

    def _noter(c: Any, fenetre: str) -> float:
        """Note un candidat en refusant tout ce qui n'est pas un nombre.

        AJOUTE le 27/08/2026. Une score_fn qui rend None sur echec est
        l'erreur d'appelant la plus naturelle qui soit. Avant ce garde,
        math.isfinite(None) levait « TypeError: must be real number, not
        NoneType » -- un message qui ne nomme NI le candidat NI la fenetre.
        Pour une bibliotheque dont la these est « un candidat qu'on n'a pas
        pu noter n'est pas un candidat qui a perdu », echouer sans dire
        lequel est la mauvaise moitie du travail.

        On leve plutot que de traiter en `unscorable` : None n'est pas un
        signal defini par cette interface, c'est un bug d'appelant, et le
        maquiller en « je n'ai pas pu noter » le rendrait invisible. Un
        appelant qui veut dire « pas notable » rend NaN, ce que ce module
        traite deja."""
        v = score_fn(c, fenetre)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise TypeError(
                "score_fn(%r, %r) returned %r (%s); it must return a float. "
                "To signal 'this candidate could not be scored', return "
                "float('nan') -- that is handled explicitly and blocks "
                "certification." % (c, fenetre, v, type(v).__name__)
            )
        return float(v)

    full_scores = {c: _noter(c, "full") for c in candidates}
    in_sample_scores = {c: _noter(c, "in_sample") for c in candidates}

    # AJOUTE le 26/08/2026. `max()` compare avec `>`, et toute comparaison avec
    # NaN rend False. Consequence mesuree, et elle depend de l'ORDRE:
    #
    #     scores {"A": nan, "B": 1.0}  -> gagnant A, agrees=False  (echoue ferme)
    #     scores {"A": 1.0, "B": nan}  -> gagnant A, agrees=TRUE   (le NaN est
    #                                     silencieusement ecarte, et le garde
    #                                     certifie l'absence de fuite)
    #
    # Un candidat qu'on n'a PAS PU noter n'est pas un candidat qui a perdu. Si
    # le vrai meilleur candidat echoue a se noter sur une fenetre -- donnee
    # manquante, division par zero -- il disparait sans bruit et un autre est
    # certifie propre. C'est un echec silencieux au coeur meme du mecanisme que
    # cette bibliotheque existe pour fournir.
    #
    # MISE A JOUR le 27/08/2026. Ce commentaire disait « non atteignable
    # aujourd'hui par vol_strategy.py (`_sharpe` rend 0.0 sur un ecart-type nul
    # ou moins de deux points) », et un test verifiait cette propriete. C'etait
    # exact, et c'etait le probleme : la RAISON pour laquelle le cas n'etait pas
    # atteignable ETAIT un defaut de vol_strategy -- elle fabriquait un 0.0
    # plutot que d'avouer qu'elle n'avait rien pu mesurer, donc ce garde ne
    # voyait rien (math.isfinite(0.0) est True) et certifiait des selections ou
    # une fenetre candidate n'avait jamais ete notee. Reproduit avec 325 barres
    # au lieu des 592 requises.
    #
    # _sharpe rend desormais NaN dans ces deux cas, des deux cotes
    # (vol_strategy ET momentum_strategy). Ce garde est donc PORTANT, plus
    # defensif : c'est lui qui transforme « je n'ai pas pu noter cette
    # candidate » en refus de certifier.
    unscorable = [
        c for c in candidates
        if not math.isfinite(full_scores[c]) or not math.isfinite(in_sample_scores[c])
    ]

    def _gagnants(scores: Dict[Any, float]) -> List[Any]:
        """TOUS les candidats atteignant le maximum, dans l'ordre d'origine.

        Restreint aux valeurs FINIES : max() compare avec `>` et toute
        comparaison avec NaN rend False, ce qui rendait meme le gagnant
        dependant de l'ordre. `unscorable` bloque deja la certification dans
        ce cas, mais le representant affiche dans le resume ne doit pas etre
        arbitraire pour autant."""
        finis = {c: v for c, v in scores.items() if math.isfinite(v)}
        if not finis:
            return []
        sommet = max(finis.values())
        return [c for c in candidates if c in finis and finis[c] == sommet]

    full_winners = _gagnants(full_scores)
    in_sample_winners = _gagnants(in_sample_scores)

    # Representants, conserves pour la retrocompatibilite du rapport et du
    # resume. Le VERDICT ne s'appuie plus dessus (voir __post_init__) ; ils ne
    # servent qu'a nommer un exemple lisible. Repli sur max() brut quand aucun
    # score n'est fini -- ce cas est deja bloque par `unscorable`, mais le
    # rapport doit rester constructible.
    full_winner = full_winners[0] if full_winners else max(full_scores, key=full_scores.get)
    in_sample_winner = (in_sample_winners[0] if in_sample_winners
                        else max(in_sample_scores, key=in_sample_scores.get))
    in_sample_clears_bar = bool(in_sample_winners) and \
        in_sample_scores[in_sample_winners[0]] > threshold

    report = LeakageReport(
        candidates=list(candidates),
        full_scores=full_scores,
        in_sample_scores=in_sample_scores,
        full_winner=full_winner,
        in_sample_winner=in_sample_winner,
        in_sample_clears_bar=in_sample_clears_bar,
        threshold=threshold,
        unscorable=unscorable,
        full_winners=full_winners,
        in_sample_winners=in_sample_winners,
    )

    if raise_on_leak and not report.agrees:
        raise HindsightLeakError(report.summary())

    return report
