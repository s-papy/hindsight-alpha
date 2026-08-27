# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

"""Tests du JavaScript de docs/index.html — la page que les juges regardent.

Ajouté le 27/08/2026. Ce fichier porte ~430 lignes de logique de rendu qui
décident de ce qu'un lecteur voit, et n'avait AUCUN test. Plusieurs correctifs
de cette semaine y vivent (bannière de santé qui distinguait mal une page
périmée d'un moniteur mort, badge dry-run, badge d'ordre au sort inconnu), tous
vérifiés à l'œil.

Le script est extrait de la page et exécuté sous node avec un DOM minimal.
Aucun réseau : loadDashboard() est neutralisé, seules les fonctions pures de
rendu sont appelées.

Les tests se SAUTENT proprement si node est absent — la CI et le poste local
doivent rester verts sans dépendance nouvelle, et un test qu'on ne peut pas
exécuter ne doit pas se transformer en échec rouge qu'on apprend à ignorer.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent
PAGE = RACINE / "docs" / "index.html"
NODE = shutil.which("node")


def _script_de_la_page() -> str:
    """Le contenu du <script> de la page, loadDashboard() neutralisé."""
    page = PAGE.read_text(encoding="utf-8")
    blocs = re.findall(r"<script>(.*?)</script>", page, re.S)
    if len(blocs) != 1:
        raise AssertionError(
            "docs/index.html contient %d blocs <script> ; ce test en attend "
            "exactement un. Si la page en a gagné un, il faut décider lequel "
            "est testé plutôt que d'en concaténer deux au hasard." % len(blocs))
    return blocs[0].replace("loadDashboard();", "/* neutralisé pour le test */")


# Un DOM minimal : les fonctions testées ne touchent au document que par
# getElementById. On rend un objet PERSISTANT par identifiant, pour pouvoir
# relire ce qui y a été écrit.
PRELUDE = """
const _elements = {};
const document = { getElementById: (id) => (_elements[id] = _elements[id] ||
    { id, style: {}, className: "", textContent: "", innerHTML: "" }) };
const _resultats = {};
function _publier() { console.log("---JSON---" + JSON.stringify(_resultats)); }
"""


@unittest.skipUnless(NODE, "node absent — tests de rendu sautés")
class BaseRendu(unittest.TestCase):
    def executer(self, corps: str) -> dict:
        """Exécute `corps` après le script de la page ; rend `_resultats`."""
        source = _script_de_la_page() + PRELUDE + corps + "\n_publier();\n"
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "rendu.js"
            chemin.write_text(source, encoding="utf-8")
            proc = subprocess.run([NODE, str(chemin)], capture_output=True,
                                  text=True, timeout=30)
        if proc.returncode != 0:
            self.fail("node a échoué (%d) :\n%s" % (proc.returncode, proc.stderr[:1500]))
        marqueur = "---JSON---"
        self.assertIn(marqueur, proc.stdout,
                      "le harnais n'a rien publié ; sortie node :\n%s" % proc.stdout[:800])
        return json.loads(proc.stdout.split(marqueur, 1)[1].strip())


class TestBadgeDeVerdict(BaseRendu):
    def test_un_ordre_au_sort_inconnu_est_rouge_et_dit_quoi_faire(self):
        r = self.executer("""
            _resultats.inconnu = outcomeBadge({outcome:"order_status_unknown"});
            _resultats.traded  = outcomeBadge({outcome:"order_submitted"});
        """)
        self.assertIn("badge-red", r["inconnu"],
                      "un ordre dont on ignore le sort ne s'affiche pas en rouge")
        self.assertIn("verify manually", r["inconnu"])
        self.assertIn("badge-green", r["traded"],
                      "prérequis : un ordre passé reste vert")

    def test_un_essai_a_blanc_rate_n_est_pas_une_panne_de_production(self):
        """Un `agent.py --dry-run` sans réseau produit outcome='error' tout à
        fait légitime, qui s'affichait en rouge comme un vrai échec."""
        r = self.executer("""
            _resultats.blanc = outcomeBadge({dry_run:true, outcome:"error"});
            _resultats.vrai  = outcomeBadge({dry_run:false, outcome:"error"});
        """)
        self.assertIn("badge-yellow", r["blanc"])
        self.assertIn("badge-red", r["vrai"])

    def test_un_verdict_inconnu_degrade_au_lieu_de_casser(self):
        r = self.executer("""_resultats.x = outcomeBadge({outcome:"zoubidou"});""")
        self.assertIn("badge-muted", r["x"])
        self.assertIn("zoubidou", r["x"])



class TestBadgeDuMoniteurDeSorties(BaseRendu):
    """Ajouté le 27/08, après reproduction sous node.

    outcomeBadge() décidait sur `outcome === 'checked'` seul. Or
    manage_exits() rattrape les échecs PAR POSITION en interne — c'est
    délibéré, pour qu'une position en panne n'empêche pas de traiter les
    autres — et `record["outcome"]` reste donc `'checked'` même quand une
    clôture a échoué. Le badge annonçait « position closed », en VERT, pour
    une position toujours ouverte au-delà de son stop-loss.

    C'est l'événement précis que tout ce sous-système existe pour attraper.
    Le correctif du 24/08 a fait en sorte qu'il soit JOURNALISÉ ; il ne
    s'était jamais rendu jusqu'à l'affichage. Le tableau de bord affirmait
    activement le contraire de la réalité, à l'endroit exact où un juge
    regarde.

    La sévérité se lit désormais sur `exit_actions[].kind` — la donnée
    structurée que risk_gates.py produit déjà — et non sur un `outcome`
    global qui ne peut pas la porter."""

    def _badge(self, record_js):
        r = self.executer("_resultats.b = outcomeBadge(%s);" % record_js)
        b = r["b"]
        import re as _re
        m = _re.search(r"badge-(\w+)", b)
        return (m.group(1) if m else None), _re.sub(r"<[^>]*>", "", b)

    def test_une_cloture_echouee_n_est_pas_annoncee_comme_reussie(self):
        couleur, texte = self._badge("""{
            run_type:'exit_monitor', outcome:'checked', dry_run:false,
            exit_actions:[{symbol:'SPY260831P00764000', kind:'error',
                           pnl_pct:-0.71, error:'AlpacaCLIError: 403'}]}""")
        self.assertNotEqual(couleur, "green",
                            "une clôture ÉCHOUÉE s'affiche en vert « %s » "
                            "alors que la position est toujours ouverte" % texte)
        self.assertNotIn("position closed", texte)

    def test_un_pnl_illisible_n_est_pas_annonce_comme_une_cloture(self):
        """UNREADABLE veut dire qu'on ignore si le stop est franchi. C'est
        une absence d'information, pas une clôture."""
        couleur, texte = self._badge("""{
            run_type:'exit_monitor', outcome:'checked', dry_run:false,
            exit_actions:[{symbol:'GLD260831C00300000', kind:'unreadable'}]}""")
        self.assertNotEqual(couleur, "green", texte)
        self.assertNotIn("position closed", texte)

    def test_un_echec_au_milieu_de_reussites_reste_visible(self):
        """Le cas qui compte vraiment : manage_exits traite plusieurs
        positions, deux ferment proprement, une échoue. Faire la moyenne ou
        prendre la première reviendrait à cacher la seule qui demande une
        action humaine."""
        couleur, texte = self._badge("""{
            run_type:'exit_monitor', outcome:'checked', dry_run:false,
            exit_actions:[{symbol:'A', kind:'closed', pnl_pct:0.9},
                          {symbol:'B', kind:'error', error:'AlpacaCLIError: 403'},
                          {symbol:'C', kind:'closed', pnl_pct:-0.5}]}""")
        self.assertNotEqual(couleur, "green",
                            "un échec noyé dans deux réussites disparaît : %s" % texte)

    def test_une_position_non_classee_est_rouge(self):
        """`unrecognised` est né le 27/08 dans manage_exits(). Le test de pont
        (test_integration.TestVocabulairePartageAvecLaPage) l'a signalé AVANT
        qu'il n'atteigne cette page en `badge-muted` gris — exactement le
        scénario pour lequel ce pont a été posé le matin même.

        Sévérité rouge : la position porte du risque réel et aucun stop-loss
        ne peut lui être appliqué."""
        couleur, texte = self._badge("""{
            run_type:'exit_monitor', outcome:'checked', dry_run:false,
            exit_actions:[{symbol:'CONTRAT-INCONNU-42', kind:'unrecognised'}]}""")
        self.assertEqual(couleur, "red", texte)
        self.assertIn("no stop-loss", texte)

    def test_une_vraie_cloture_reste_verte(self):
        """Pendant obligatoire : si tout devient rouge, plus rien n'est lu."""
        couleur, texte = self._badge("""{
            run_type:'exit_monitor', outcome:'checked', dry_run:false,
            exit_actions:[{symbol:'A', kind:'closed', pnl_pct:-0.52}]}""")
        self.assertEqual(couleur, "green", texte)
        self.assertIn("closed", texte)

    def test_un_essai_a_blanc_reste_distinct_d_une_vraie_cloture(self):
        couleur, texte = self._badge("""{
            run_type:'exit_monitor', outcome:'checked', dry_run:true,
            exit_actions:[{symbol:'A', kind:'would_close', pnl_pct:-0.52}]}""")
        self.assertEqual(couleur, "yellow", texte)
        self.assertIn("would close", texte)

    def test_un_run_interrompu_ne_passe_pas_pour_une_broutille(self):
        """`interrupted` est né du correctif du même jour dans
        monitor_exits.py, et n'avait pas de correspondance ici — il tombait
        donc sur le repli `badge-muted`, gris discret. C'est le même défaut
        de forme que celui qui avait affiché `order_status_unknown` en gris :
        un état qui réclame de l'attention, rendu dans la couleur qui dit
        « rien à signaler »."""
        couleur, texte = self._badge(
            "{run_type:'exit_monitor', outcome:'interrupted', dry_run:false}")
        self.assertNotEqual(couleur, "muted",
                            "un run interrompu s'affiche en gris discret : %s"
                            % texte)

    def test_un_enregistrement_sans_exit_actions_ne_se_declare_pas_cloture(self):
        """Rétrocompatibilité : les entrées publiées avant que
        `exit_actions` existe (24/08) n'ont pas de quoi trancher. Ne pas
        savoir doit donner du gris, pas un vert « position closed »."""
        couleur, texte = self._badge(
            "{run_type:'exit_monitor', outcome:'checked', dry_run:false}")
        self.assertNotEqual(couleur, "green", texte)

class TestLigneParSymbole(BaseRendu):
    """decision_log.jsonl est committé et JAMAIS réécrit : les anciennes formes
    d'enregistrement restent dans le fichier pour toujours et doivent continuer
    de s'afficher. C'est un contrat écrit dans les commentaires de la page, et
    rien ne le vérifiait."""

    def test_les_quatre_formes_d_enregistrement_s_affichent(self):
        r = self.executer("""
            _resultats.moderne = renderTrade({trades:[
                {symbol:"QQQ", direction:"bullish (call)",
                 outcome:"order_submitted", order_id:"ord-1", qty:2}]});
            _resultats.ancien = renderTrade({chosen_symbol:"SPY",
                 direction:"call", order_id:"vieux", qty:1});
            _resultats.sortie_structuree = renderTrade({exit_actions:[
                 {text:"SPY stop-loss at -55%"}]});
            _resultats.sortie_chaine = renderTrade({exit_actions:["chaîne simple"]});
            _resultats.vide = renderTrade({});
        """)
        self.assertIn("ord-1", r["moderne"])
        self.assertIn("vieux", r["ancien"])
        self.assertIn("stop-loss", r["sortie_structuree"])
        self.assertIn("chaîne simple", r["sortie_chaine"])
        self.assertEqual(r["vide"], "—")

    def test_le_detail_d_un_ordre_au_sort_inconnu_dit_quoi_faire(self):
        """Le badge de la run est rouge, mais c'est CETTE ligne qui dit de quel
        symbole il s'agit. Sans branche dédiée, elle affichait la chaîne machine
        « order_status_unknown »."""
        r = self.executer("""
            _resultats.x = renderTrade({trades:[
                {symbol:"SPY", direction:"bullish (call)",
                 outcome:"order_status_unknown", error:"TimeoutExpired: ..."}]});
        """)
        self.assertIn("SPY", r["x"])
        self.assertIn("ORDER MAY HAVE BEEN SUBMITTED", r["x"])
        self.assertNotIn("order_status_unknown", r["x"],
                         "la ligne par symbole affiche la chaîne machine")


class TestBanniereDeSante(BaseRendu):
    """Corrigée le 26/08 : la bannière ne distinguait pas « le moniteur tourne
    mais la page n'a pas été republiée » de « le moniteur est mort », et
    accusait le moniteur dans les deux cas. Rien ne l'avait jamais exécutée."""

    PRE = """
        const T = 3600000;                       // une heure en ms
        const ilYA = (h) => new Date(Date.now() - h*T).toISOString();
        const lire = () => document.getElementById('monitor-health-banner');
    """

    def test_une_page_perimee_n_accuse_pas_le_moniteur(self):
        """Rien ne republie la page automatiquement — c'est le cas NORMAL."""
        r = self.executer(self.PRE + """
            renderMonitorHealth([], {last_run_at: ilYA(20), outcome:"checked"}, ilYA(20));
            _resultats.classe = lire().className;
            _resultats.texte  = lire().textContent;
        """)
        self.assertEqual(r["classe"], "health-yellow")
        self.assertIn("snapshot", r["texte"])
        self.assertNotIn("consecutive failures", r["texte"],
                         "la bannière accuse le moniteur alors que c'est la "
                         "page qui est vieille")

    def test_un_moniteur_reellement_en_echec_passe_au_rouge(self):
        r = self.executer(self.PRE + """
            renderMonitorHealth([], {last_run_at: ilYA(0.1), outcome:"error"}, ilYA(0.1));
            _resultats.classe = lire().className;
            _resultats.texte  = lire().textContent;
        """)
        self.assertEqual(r["classe"], "health-red")
        self.assertIn("failed", r["texte"])

    def test_sans_aucune_donnee_la_banniere_ne_ment_pas(self):
        r = self.executer(self.PRE + """
            renderMonitorHealth([], null, null);
            _resultats.classe = lire().className;
            _resultats.texte  = lire().textContent;
        """)
        self.assertEqual(r["classe"], "health-muted")
        self.assertIn("no run recorded", r["texte"])



    # --- Ajoutés le 27/08 : la bannière était une LISTE NOIRE d'une seule
    # valeur. Elle ne reconnaissait que `error` ; tout le reste tombait dans
    # le `else` final, c'est-à-dire « healthy », en vert. Y compris la valeur
    # `unknown` — le défaut littéral de monitor_exits.py, dont le sens est
    # exactement « on ne sait pas ce qui s'est passé ».
    #
    # Les deux seules valeurs qui prouvent une vérification réussie sont
    # `checked` et `market_closed`. C'est une LISTE BLANCHE, désormais, et
    # ces tests existent pour qu'elle le reste : la seule façon de rendre du
    # vert doit être de le mériter explicitement.

    def test_un_run_dont_on_ignore_le_sort_ne_s_affiche_jamais_en_vert(self):
        """`unknown` est ce qu'écrit un run INTERROMPU (Ctrl-C, ou toute
        BaseException que les deux `except` de main() ne rattrapent pas — voir
        test_integration). Aucune position n'a été vérifiée. La bannière
        annonçait « healthy » en vert."""
        r = self.executer(self.PRE + """
            renderMonitorHealth([], {last_run_at: ilYA(0.01), outcome:"unknown"}, ilYA(0.01));
            _resultats.classe = lire().className;
            _resultats.texte  = lire().textContent;
        """)
        self.assertNotEqual(r["classe"], "health-green",
                            "un run dont le sort est inconnu s'affiche en VERT "
                            "« healthy » : %s" % r["texte"])
        # Assertion sur le SENS, pas sur la sous-chaîne : le message correct
        # contient « not healthy », qu'un assertNotIn("healthy") rejetterait.
        self.assertIn("did not complete", r["texte"])
        self.assertIn("not healthy", r["texte"])

    def test_un_ctrl_c_manuel_ne_repeint_pas_en_vert_un_moniteur_mort(self):
        """Le vrai dégât, et la raison pour laquelle ce n'est pas cosmétique.

        Un run interrompu écrit `unknown` avec un horodatage FRAIS. La
        fraîcheur étant justement le signal que cette bannière surveille, un
        Ctrl-C sur un lancement manuel effaçait les quatre échecs consécutifs
        du moniteur programmé — rouge avant, vert après, alors que rien
        n'avait été réparé. La bannière existe pour rendre le silence
        visible ; elle le masquait."""
        r = self.executer(self.PRE + """
            const echecs = [0.5, 1.0, 1.5, 2.0].map(h => (
                {run_type:'exit_monitor', outcome:'error', timestamp: ilYA(h)}));
            renderMonitorHealth(echecs, {last_run_at: ilYA(0.5), outcome:'error'}, ilYA(0.01));
            _resultats.avant = lire().className;
            renderMonitorHealth(echecs, {last_run_at: ilYA(0.01), outcome:'unknown'}, ilYA(0.01));
            _resultats.apres = lire().className;
            _resultats.texte = lire().textContent;
        """)
        self.assertEqual(r["avant"], "health-red", "prérequis : le moniteur est bien mort")
        self.assertNotEqual(r["apres"], "health-green",
                            "un Ctrl-C manuel a repeint en vert un moniteur "
                            "toujours mort : %s" % r["texte"])

    def test_une_valeur_d_outcome_inconnue_ne_vaut_pas_un_certificat_de_sante(self):
        """Défaut sûr, et non « tout ce qui n'est pas `error` va bien ».

        Ce test-ci est le seul qui protège l'AVENIR : le jour où quelqu'un
        ajoute un `outcome` à monitor_exits.py sans toucher à cette page, la
        valeur nouvelle doit tomber du côté prudent. La casse compte aussi —
        `ERROR` n'est pas `error`."""
        for valeur in ('"ERROR"', '"partial"', '"timeout"', 'null', '""', '"checked "'):
            with self.subTest(outcome=valeur):
                r = self.executer(self.PRE + """
                    renderMonitorHealth([], {last_run_at: ilYA(0.01), outcome: %s}, ilYA(0.01));
                    _resultats.classe = lire().className;
                    _resultats.texte  = lire().textContent;
                """ % valeur)
                self.assertNotEqual(r["classe"], "health-green",
                                    "outcome=%s certifie la santé du moniteur : %s"
                                    % (valeur, r["texte"]))

    def test_un_horodatage_illisible_ne_se_declare_pas_en_bonne_sante(self):
        """La page disait mot pour mot « last check unknown time ago,
        healthy » — elle s'auto-contredisait dans la même phrase. Ne pas
        savoir QUAND le moniteur a tourné, c'est ne pas savoir s'il est en
        vie."""
        r = self.executer(self.PRE + """
            renderMonitorHealth([], {last_run_at:"pas-une-date", outcome:"checked"}, ilYA(0.01));
            _resultats.classe = lire().className;
            _resultats.texte  = lire().textContent;
        """)
        self.assertNotEqual(r["classe"], "health-green",
                            "horodatage illisible certifié sain : %s" % r["texte"])

    def test_les_deux_seuls_temoins_sains_restent_verts(self):
        """Le pendant obligatoire : une liste blanche trop étroite qui met
        tout en jaune serait aussi inutile qu'un vert permanent. Un lecteur
        qui voit du jaune en permanence cesse de le lire."""
        for valeur, attendu in (("checked", ""), ("market_closed", "market was closed")):
            with self.subTest(outcome=valeur):
                r = self.executer(self.PRE + """
                    renderMonitorHealth([], {last_run_at: ilYA(0.01), outcome:"%s"}, ilYA(0.01));
                    _resultats.classe = lire().className;
                    _resultats.texte  = lire().textContent;
                """ % valeur)
                self.assertEqual(r["classe"], "health-green",
                                 "un vrai passage sain n'est plus vert : %s" % r["texte"])
                self.assertIn(attendu, r["texte"])


class TestGardeAntiDoublonNonArme(BaseRendu):
    """Ajouté le 27/08, trouvé en croisant les champs qu'agent.py écrit sur un
    trade avec ceux que la page lit : `record_order_submitted_failed` était
    écrit et n'apparaissait NULLE PART dans docs/index.html.

    Ce que ce champ signifie : l'ordre est parti chez Alpaca, mais
    `risk_gates.record_order_submitted()` a échoué — donc state.json ne sait
    pas que ce sous-jacent a une position. Le garde-fou « jamais deux
    positions sur le même sous-jacent », que ce projet énonce dans ses
    livrables, N'EST PAS ARMÉ. Un second lancement le même jour peut doubler
    la position.

    agent.py fait le travail : il attrape l'échec, prévient, et le consigne
    dans l'enregistrement. Le `print` ne va qu'au log launchd — gitignoré, que
    personne ne regarde, exactement l'argument que ce dépôt tient lui-même à
    propos de monitor_exits.log. Le champ arrivait bien dans data.json ; la
    page ne le lisait pas. Même famille que les trois défauts corrigés le même
    jour : l'action est protégée, l'anomalie est consignée, et la trace meurt
    au rendu."""

    ARME = ("{trades:[{symbol:'SPY', direction:'long', qty:3, order_id:'abc123',"
            " outcome:'order_submitted'}]}")
    NON_ARME = ("{trades:[{symbol:'SPY', direction:'long', qty:3, order_id:'abc123',"
                " outcome:'order_submitted',"
                " record_order_submitted_failed:'StateLockUnavailable: verrou indisponible'}]}")

    def _ligne(self, record_js):
        r = self.executer("_resultats.l = renderTrade(%s);" % record_js)
        import re as _re
        return _re.sub(r"<[^>]*>", " ", r["l"])

    def test_un_garde_non_arme_ne_rend_pas_la_meme_ligne_qu_un_garde_arme(self):
        """Le test le plus simple, et celui qui aurait suffi : les deux
        situations produisaient une sortie identique au caractère près."""
        self.assertNotEqual(self._ligne(self.ARME), self._ligne(self.NON_ARME),
                            "un ordre dont le garde anti-doublon n'a pas pu "
                            "être armé s'affiche exactement comme un ordre "
                            "normal")

    def test_la_ligne_dit_ce_qu_il_faut_verifier(self):
        """Signaler ne suffit pas : un lecteur doit savoir quoi faire. Le
        risque concret est un second lancement le même jour."""
        ligne = self._ligne(self.NON_ARME)
        self.assertIn("duplicate", ligne.lower())
        self.assertIn("re-running", ligne.lower())

    def test_le_cumul_timeout_plus_garde_non_arme_dit_les_deux(self):
        """Le pire cas atteignable, et il est réel : le CLI dépasse ses 30 s,
        agent.py arme le garde par précaution — et cet armement échoue à son
        tour (agent.py ligne ~483). L'ordre est peut-être passé ET rien ne
        protège du doublon. La page ne disait que la première moitié."""
        ligne = self._ligne("""{trades:[{symbol:'SPY', direction:'long',
            outcome:'order_status_unknown', error:'TimeoutExpired: 30s',
            record_order_submitted_failed:'StateLockUnavailable: verrou'}]}""")
        self.assertIn("MAY HAVE BEEN SUBMITTED", ligne,
                      "prérequis : le message de timeout est conservé")
        self.assertIn("duplicate", ligne.lower(),
                      "la moitié « garde non armé » du cumul disparaît")

    def test_le_badge_ne_certifie_pas_un_run_dont_le_garde_a_lache(self):
        """Un badge vert « traded » est une affirmation : tout s'est bien
        passé. Ici ce n'est pas vrai."""
        r = self.executer("_resultats.b = outcomeBadge(%s);" % self.NON_ARME.replace(
            "{trades:", "{outcome:'order_submitted', trades:"))
        self.assertNotIn("badge-green", r["b"],
                         "run certifié vert alors que le garde anti-doublon "
                         "n'est pas armé : %s" % r["b"])

    def test_un_ordre_normal_reste_vert_et_sobre(self):
        """Pendant obligatoire."""
        ligne = self._ligne(self.ARME)
        self.assertNotIn("duplicate", ligne.lower(),
                         "un ordre normal porte un avertissement qui ne le "
                         "concerne pas — le cri perd son sens s'il est constant")
        r = self.executer("_resultats.b = outcomeBadge(%s);" % self.ARME.replace(
            "{trades:", "{outcome:'order_submitted', trades:"))
        self.assertIn("badge-green", r["b"])


class TestSeparateurDuKickoff(BaseRendu):
    """Ajouté le 27/08 au soir, sur une projection chiffrée et non une
    impression.

    La page publie les 30 décisions les plus récentes. Aujourd'hui elle en
    contient 30, dont 11 erreurs DNS du 25/08 — un incident réseau de trois
    jours AVANT le début de l'événement. 43% de la fenêtre est en erreur.

    Et le journal grossit lentement : agent.py écrit un enregistrement par
    exécution, une exécution par jour de bourse. Sur la semaine du hackathon
    cela fait ~5 enregistrements, plus quelques événements notables du
    moniteur. Au 04/09, la fenêtre publique contiendrait donc ~5-10
    enregistrements DE LA SEMAINE et ~20-25 d'AVANT, dont les 11 erreurs.

    Un juge qui ouvre la page verrait surtout du bruit antérieur à
    l'événement qu'il juge.

    RIEN N'EST MASQUÉ — c'est la ligne de ce projet, et l'inverse serait
    exactement la curation d'éléments de preuve qu'il dénonce. On ÉTIQUETTE :
    une ligne de séparation nomme la frontière du kickoff et dit ce qu'il y a
    en dessous. Tout reste affiché, daté, dans le même tableau."""

    KICKOFF = "2026-08-28T15:00:00+00:00"

    def _tableau(self, horodatages):
        lignes = ", ".join(
            '{timestamp:"%s", outcome:"checked", run_type:"exit_monitor"}' % t
            for t in horodatages)
        r = self.executer("""
            renderDecisions([%s]);
            _resultats.html = document.getElementById('decisions-container').innerHTML;
        """ % lignes)
        return r["html"]

    def test_le_separateur_apparait_entre_les_deux_periodes(self):
        html = self._tableau(["2026-08-31T19:37:00+00:00",   # pendant
                              "2026-08-28T16:00:00+00:00",   # pendant
                              "2026-08-25T13:13:00+00:00",   # avant
                              "2026-08-24T19:05:00+00:00"])  # avant
        self.assertEqual(html.count("kickoff-divider"), 1,
                         "séparateur absent ou en double")
        avant_sep = html.split("kickoff-divider")[0]
        # `- 1` pour la ligne d'en-tête du <thead>, que mon premier comptage
        # oubliait : l'assertion échouait pour cette raison, pas parce que le
        # séparateur était mal placé.
        lignes_au_dessus = avant_sep.count("<tr>") - 1
        self.assertEqual(lignes_au_dessus, 2,
                         "le séparateur n'est pas à la frontière : %d ligne(s) "
                         "au-dessus au lieu de 2" % lignes_au_dessus)

    def test_le_separateur_dit_ce_qu_il_y_a_en_dessous(self):
        html = self._tableau(["2026-08-31T19:37:00+00:00",
                              "2026-08-24T19:05:00+00:00"])
        bas = html.lower()
        self.assertIn("predates the hackathon", bas,
                      "le séparateur n'explique pas ce qui suit")
        self.assertIn("28 aug 15:00 utc", bas,
                      "la frontière exacte n'est pas nommée")
        self.assertIn("nothing is hidden", bas,
                      "le séparateur ne dit pas que rien n'a été retiré — "
                      "c'est justement ce qu'un juge doit pouvoir vérifier")

    def test_rien_n_est_masque(self):
        """Le témoin qui compte le plus. Étiqueter n'est pas filtrer."""
        horodatages = ["2026-08-31T19:37:00+00:00", "2026-08-25T13:13:00+00:00",
                       "2026-08-24T19:05:00+00:00"]
        html = self._tableau(horodatages)
        # On compte les LIGNES de données, pas les « badge » : la classe
        # `badge badge-green` contient le mot deux fois, et mon premier
        # témoin échouait pour cette raison de comptage, pas de comportement.
        lignes = html.count("<tr>") - html.count("kickoff-divider")
        self.assertEqual(lignes, len(horodatages),
                         "des enregistrements ont disparu du tableau : %d ligne(s) "
                         "pour %d décisions" % (lignes, len(horodatages)))

    def test_aucun_separateur_si_tout_est_anterieur(self):
        """L'état d'AUJOURD'HUI : les 30 enregistrements sont tous antérieurs
        au kickoff. Un séparateur en tête de tableau, sans rien au-dessus, ne
        dirait rien et ferait du bruit."""
        html = self._tableau(["2026-08-25T13:13:00+00:00",
                              "2026-08-24T19:05:00+00:00"])
        self.assertNotIn("kickoff-divider", html)

    def test_aucun_separateur_si_tout_est_posterieur(self):
        """L'état de la FIN de semaine, si le journal a assez tourné."""
        html = self._tableau(["2026-09-03T19:37:00+00:00",
                              "2026-08-31T19:37:00+00:00"])
        self.assertNotIn("kickoff-divider", html)

class TestCompteurDeFuites(BaseRendu):
    """Le chiffre le plus mis en avant de la page : combien de fuites de
    hindsight_guard ont été attrapées. Il compte sur un préfixe EXACT."""

    def test_seule_une_vraie_prise_de_hindsight_guard_est_comptee(self):
        r = self.executer("""
            const el = document.getElementById('leak-stat');
            renderLeakStat([
              {verdicts:[{symbol:"SPY", reason:"hindsight_guard: winning HV window doesn't hold up in-sample"}]},
              {verdicts:[{symbol:"QQQ", reason:"volatility not cheap today (HV rank 61.2)"}]},
              {verdicts:[{symbol:"IWM", reason:"error evaluating symbol: DataQualityError: ..."}]}
            ]);
            _resultats.texte = el.textContent;
            _resultats.affiche = el.style.display;
        """)
        self.assertEqual(r["affiche"], "block")
        self.assertIn(": 1", r["texte"],
                      "le compteur de fuites ne compte pas exactement les "
                      "prises de hindsight_guard : %r" % r["texte"])

    def test_aucune_fuite_cache_le_bandeau_au_lieu_d_afficher_zero(self):
        r = self.executer("""
            const el = document.getElementById('leak-stat');
            renderLeakStat([{verdicts:[{symbol:"SPY", reason:"no edge"}]}]);
            _resultats.affiche = el.style.display;
        """)
        self.assertEqual(r["affiche"], "none")



class TestIsolationParEnregistrement(BaseRendu):
    """Ajouté le 27/08 au soir. Les cinq fonctions de rendu s'exécutent dans
    UN SEUL try, et renderDecisions boucle sur les enregistrements sans
    isolation. Mesuré :

        trois enregistrements sains        -> tableau rendu, 694 caractères
        un exit_actions en CHAÎNE          -> TypeError, tableau VIDE
        un enregistrement null             -> TypeError, tableau VIDE

    Un seul enregistrement malformé vide donc la totalité du tableau des
    décisions — la section qu'un juge regarde en premier — et empêche au
    passage les sections suivantes de se rendre.

    Ce n'est pas théorique : le README dit que decision_log.jsonl est
    committé et JAMAIS réécrit, donc les anciennes formes d'enregistrement y
    restent pour toujours (« both have to render, not just the new one »).

    Et ce dépôt applique déjà l'isolation par élément PARTOUT ailleurs —
    manage_exits, evaluate_symbol, la boucle d'entrée d'agent.py,
    backtest.py, compare_strategies.py. La page publique est le seul endroit
    qui ne l'avait pas."""

    SAIN = ('{timestamp:"2026-08-31T19:37:00Z", outcome:"order_submitted", '
            'trades:[]}')

    def _rendu(self, decisions_js):
        r = self.executer("""
            renderDecisions([%s]);
            _resultats.html = document.getElementById('decisions-container').innerHTML;
        """ % decisions_js)
        return r["html"]

    def test_un_enregistrement_casse_ne_vide_pas_le_tableau(self):
        for casse, cas in (
                ('{timestamp:"2026-08-31T19:37:00Z", outcome:"checked", '
                 'run_type:"exit_monitor", exit_actions:"cassé"}', "exit_actions en chaîne"),
                ('null', "enregistrement null"),
                ('{timestamp:"2026-08-31T19:37:00Z", outcome:"x", verdicts:"cassé"}',
                 "verdicts en chaîne")):
            with self.subTest(cas=cas):
                html = self._rendu("%s, %s, %s" % (self.SAIN, casse, self.SAIN))
                self.assertTrue(html,
                                "%s : le tableau est VIDE — un seul "
                                "enregistrement a tout emporté" % cas)
                self.assertGreaterEqual(
                    html.count("<tr>"), 3,
                    "%s : les enregistrements SAINS ont disparu avec lui "
                    "(%d lignes)" % (cas, html.count("<tr>")))

    def test_l_enregistrement_casse_est_signale_et_non_masque(self):
        """Sauter l'enregistrement en silence serait le pendant exact du
        défaut : la page montrerait moins que ce que le journal contient,
        sans le dire. On rend une ligne qui l'annonce."""
        html = self._rendu('%s, null' % self.SAIN)
        self.assertIn("could not be rendered", html.lower(),
                      "l'enregistrement illisible disparaît sans un mot : %s"
                      % html[:200])

    def test_des_enregistrements_sains_restent_intacts(self):
        """Témoin : l'isolation ne doit rien changer au cas normal."""
        html = self._rendu("%s, %s" % (self.SAIN, self.SAIN))
        self.assertEqual(html.count("<tr>"), 3, html[:200])   # 2 lignes + entête
        self.assertNotIn("could not be rendered", html.lower())


class TestIsolationParSection(BaseRendu):
    """Le pendant, un cran au-dessus. renderDecisions est isolée par
    enregistrement depuis le correctif précédent, mais loadDashboard()
    enchaîne CINQ sections dans un seul try : si l'une lève, les suivantes ne
    se rendent pas du tout.

    Mesuré après le premier correctif, avec un enregistrement null :

        renderLeakStat        -> TypeError
        renderMonitorHealth   -> TypeError
        renderPositions       -> TypeError  (sur une position nulle)
        renderDecisions       -> ok         (déjà isolée)
        renderAccount         -> ok

    Trois sections pouvaient donc encore emporter tout ce qui vient après
    elles dans la séquence, y compris le tableau qu'on venait de protéger."""

    def _sections(self, decisions_js, positions_js="[]"):
        return self.executer("""
            const d = [%s];
            _resultats.leak = (() => { try { renderLeakStat(d); return "ok"; }
                                       catch (e) { return e.constructor.name; } })();
            _resultats.sante = (() => { try {
                renderMonitorHealth(d, {last_run_at:new Date().toISOString(),
                                        outcome:"checked"}, new Date().toISOString());
                return "ok"; } catch (e) { return e.constructor.name; } })();
            _resultats.positions = (() => { try { renderPositions(%s); return "ok"; }
                                            catch (e) { return e.constructor.name; } })();
        """ % (decisions_js, positions_js))

    SAIN = '{timestamp:"2026-08-31T19:37:00Z", outcome:"order_submitted", trades:[]}'

    def test_aucune_section_ne_leve_sur_un_enregistrement_nul(self):
        r = self._sections("%s, null, %s" % (self.SAIN, self.SAIN))
        for section in ("leak", "sante"):
            with self.subTest(section=section):
                self.assertEqual(r[section], "ok",
                                 "%s lève sur un enregistrement null (%s) et "
                                 "emporte les sections suivantes"
                                 % (section, r[section]))

    def test_les_positions_survivent_a_une_entree_nulle(self):
        r = self._sections(self.SAIN, positions_js="[null, {symbol:'X'}]")
        self.assertEqual(r["positions"], "ok",
                         "renderPositions lève sur une position nulle : %s"
                         % r["positions"])

    def test_les_sections_rendent_toujours_le_cas_normal(self):
        """Témoin : durcir ne doit pas rendre les sections muettes."""
        r = self._sections("%s, %s" % (self.SAIN, self.SAIN),
                           positions_js="[{symbol:'SPY260911C00500000', qty:'1'}]")
        for section in ("leak", "sante", "positions"):
            with self.subTest(section=section):
                self.assertEqual(r[section], "ok")

class TestEchappement(BaseRendu):
    """Tout ce qui vient de data.json était interpolé BRUT dans innerHTML.

    Chaîne tracée de bout en bout le 27/08 :

      1. alpaca_cli.run(), quand la sortie du CLI n'est pas du JSON, lève avec
         « first 500 chars of output: {stdout[:500]} » — la sortie BRUTE ;
      2. un portail captif, un proxy ou une page d'erreur de passerelle renvoie
         du HTML. C'est le cas réaliste d'un portable qui change de réseau,
         précisément ce montage ;
      3. agent.py met ce texte dans trade_record["error"] ;
      4. il part dans decision_log.jsonl — la preuve PUBLIÉE, jamais réécrite ;
      5. publish_dashboard.py le recopie dans docs/data.json ;
      6. renderTrade() l'injectait tel quel dans innerHTML.

    Au mieux la preuve est mutilée — une vraie balise comme <html> disparaît à
    l'affichage. Au pire c'est une injection : innerHTML n'exécute pas
    <script>, mais un <img onerror=...> si.
    """

    def test_une_page_de_portail_captif_est_echappee_et_preservee(self):
        r = self.executer("""
            _resultats.x = renderTrade({trades:[{symbol:"SPY", outcome:"error",
              error:"could not parse JSON: first 500 chars of output: "
                  + "<!DOCTYPE html><html><body>Network login required</body></html>"}]});
        """)
        self.assertNotIn("<html>", r["x"],
                         "du balisage venu du réseau atteint le DOM de la page "
                         "publique")
        self.assertIn("&lt;html&gt;", r["x"],
                      "le message n'est pas seulement neutralisé, il doit "
                      "rester LISIBLE : c'est une preuve publiée")
        self.assertIn("Network login required", r["x"])

    def test_un_gestionnaire_d_evenement_est_neutralise(self):
        r = self.executer("""
            _resultats.x = renderTrade({trades:[{symbol:"SPY", outcome:"error",
              error:"<img src=x onerror=alert(1)>"}]});
        """)
        self.assertNotIn("<img", r["x"])
        self.assertIn("&lt;img", r["x"])

    def test_les_verdicts_par_symbole_sont_echappes_aussi(self):
        r = self.executer("""
            const el = document.getElementById('decisions-container');
            renderDecisions([{timestamp:"2026-08-27T00:00:00Z", outcome:"no_edge",
              verdicts:[{symbol:"<b>SPY", tradeable:false, reason:"<i>oops"}]}]);
            _resultats.x = el.innerHTML;
        """)
        self.assertNotIn("<b>SPY", r["x"])
        self.assertNotIn("<i>oops", r["x"])
        self.assertIn("&lt;b&gt;SPY", r["x"])

    def test_les_positions_et_le_compte_sont_echappes(self):
        r = self.executer("""
            const p = document.getElementById('positions-container');
            renderPositions([{symbol:"<b>X", asset_class:"<i>opt", qty:"1",
                              cost_basis:"1", unrealized_plpc:"0.1"}]);
            _resultats.pos = p.innerHTML;
            const a = document.getElementById('account-cards');
            renderAccount({account_number:"<b>PA1", status:"<i>ACTIVE"});
            _resultats.compte = a.innerHTML;
        """)
        for cle in ("pos", "compte"):
            self.assertNotIn("<b>", r[cle])
            self.assertNotIn("<i>", r[cle])

    def test_un_message_ordinaire_reste_lisible(self):
        """Contrôle : sans lui, échapper trop (ou tout vider) passerait les
        tests ci-dessus."""
        r = self.executer("""
            _resultats.x = renderTrade({trades:[{symbol:"SPY",
              direction:"bullish (call)", outcome:"error",
              error:"TimeoutExpired: command timed out after 30s"}]});
        """)
        self.assertIn("SPY", r["x"])
        self.assertIn("bullish (call)", r["x"])
        self.assertIn("TimeoutExpired: command timed out after 30s", r["x"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
