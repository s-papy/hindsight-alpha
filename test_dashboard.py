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
    { id, style: {}, className: "", textContent: "", innerHTML: "",
      dataset: {} }) };
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

    def test_un_agent_MORT_n_est_pas_confondu_avec_un_agent_SANS_EDGE(self):
        """LA distinction qui porte ce dossier.

        Le tableau de bord publiait la santé du moniteur de SORTIES et RIEN
        sur l'agent — celui qui prend les positions. Si `agent.py` meurt un
        lundi, le moniteur continue de tourner toutes les 15 min, sa
        bannière reste verte, la page affiche `positions: []`, et plus rien
        ne distingue :

          « a tourné et n'a rien retenu »  — un RÉSULTAT, le garde
                                             anti-rétrospection au travail
          « mort depuis trois jours »      — une PANNE

        Le message doit dire explicitement qu'une liste vide signifie « ne
        tourne pas », et non « pas d'edge »."""
        r = self.executer(self.PRE + """
            renderAgentHealth({last_run_at: ilYA(30), outcome: "no_trade",
                               dry_run: false, symbols_evaluated: 4, trades: 0});
            _resultats.classe = document.getElementById('agent-health-banner').className;
            _resultats.texte  = document.getElementById('agent-health-banner').textContent;
        """)
        self.assertEqual(r["classe"], "health-red")
        self.assertIn("MISSED", r["texte"])
        self.assertIn('NOT "found no edge"', r["texte"],
                      "la bannière ne dit pas ce qu'une liste vide signifie "
                      "vraiment : %s" % r["texte"])

    def test_un_agent_qui_a_tourne_sans_rien_retenir_reste_VERT(self):
        """TÉMOIN, et c'est lui qui compte le plus.

        Sans lui, une bannière qui crierait au rouge dès qu'aucun ordre n'est
        passé transformerait le RÉSULTAT central du projet — refuser de
        trader quand le garde anti-rétrospection dit non — en panne
        permanente. Zéro ordre est une réponse, pas une défaillance."""
        r = self.executer(self.PRE + """
            // ilYA(0.01) ~ 36 s : un horodatage TOUJOURS posterieur au
            // dernier passage attendu, a n'importe quelle heure. Ma premiere
            // version utilisait ilYA(0.2) -- 12 minutes -- et elle est tombee
            // DANS L'HEURE : juste apres 19:37 UTC, « il y a 12 minutes »
            // devient « avant le passage attendu », donc en retard. Exactement
            // la fragilite que j'avais corrigee deux heures plus tot dans le
            // temoin du moniteur, et que j'ai reintroduite ici.
            renderAgentHealth({last_run_at: ilYA(0.01), outcome: "no_trade",
                               dry_run: false, symbols_evaluated: 4, trades: 0});
            _resultats.classe = document.getElementById('agent-health-banner').className;
            _resultats.texte  = document.getElementById('agent-health-banner').textContent;
        """)
        self.assertEqual(r["classe"], "health-green",
                         "zéro ordre est traité comme une panne : %s"
                         % r["texte"])
        self.assertIn("0 order(s) submitted", r["texte"])

    def test_un_dry_run_de_l_agent_n_a_pas_droit_au_vert(self):
        """Même leçon que pour le moniteur : un dry-run n'ouvre AUCUNE
        position."""
        r = self.executer(self.PRE + """
            renderAgentHealth({last_run_at: ilYA(0.2), outcome: "no_trade",
                               dry_run: true, symbols_evaluated: 4, trades: 0});
            _resultats.classe = document.getElementById('agent-health-banner').className;
        """)
        self.assertEqual(r["classe"], "health-yellow")

    def test_un_agent_sans_passage_du_tout_le_DIT(self):
        r = self.executer(self.PRE + """
            renderAgentHealth(null);
            _resultats.classe = document.getElementById('agent-health-banner').className;
            _resultats.texte  = document.getElementById('agent-health-banner').textContent;
        """)
        self.assertEqual(r["classe"], "health-muted")
        self.assertIn("no run recorded", r["texte"])

    def test_une_publication_manquee_n_accuse_pas_le_moniteur(self):
        """La page transporte un horodatage plus vieux qu'elle-même.

        Le moniteur tourne toutes les 15 min ; la publication seulement à
        :00, :05 et :30. L'horodatage porté par la page est donc, par
        construction, plus ancien qu'elle — jusqu'à 15 min de plus.

        Il existait donc une fenêtre où la page avait moins de 45 min (donc
        n'était pas « périmée ») mais où l'horodatage qu'elle portait en
        avait plus : la cascade tombait alors dans la branche qui accuse le
        MONITEUR.

        Mesuré sous node, horloge figée en plein marché, AVANT correction :

            page 35 min, moniteur 50 min
            -> « Exit monitor: last check 50 minutes ago — later than the
               usual 15-minute cadence »

        alors que le moniteur allait parfaitement bien : c'est la
        publication qui avait manqué. Un message ne doit pas nommer une
        cause qu'il n'a pas mesurée.
        """
        r = self.executer(self.PRE + """
            // page ecrite il y a 35 min, portant un moniteur de 50 min :
            // sain A LA PUBLICATION (15 min d'ecart), en retard AUJOURD'HUI.
            renderMonitorHealth([], {last_run_at: ilYA(50/60), outcome:"checked"},
                                ilYA(35/60));
            _resultats.classe = lire().className;
            _resultats.texte  = lire().textContent;
        """)
        self.assertEqual(r["classe"], "health-yellow")
        self.assertIn("snapshot", r["texte"],
                      "la bannière n'annonce pas que c'est la PAGE qui est "
                      "vieille : %s" % r["texte"])
        self.assertNotIn("15-minute cadence", r["texte"],
                         "la bannière accuse le moniteur d'un retard de "
                         "cadence alors qu'il était à l'heure quand la page "
                         "a été écrite : %s" % r["texte"])

    def test_un_moniteur_REELLEMENT_en_retard_est_toujours_accuse(self):
        """TÉMOIN, et c'est lui qui compte.

        Sans lui, une bannière qui dirait « snapshot » dans TOUS les cas
        passerait le test ci-dessus — et un moniteur réellement mort ne
        serait plus jamais signalé. Ici le décalage était DÉJÀ au-delà du
        seuil au moment de la publication : la page est fraîche, le
        moniteur est en panne, et c'est bien lui qu'il faut nommer."""
        r = self.executer(self.PRE + """
            renderMonitorHealth([], {last_run_at: ilYA(65/60), outcome:"checked"},
                                ilYA(5/60));
            _resultats.classe = lire().className;
            _resultats.texte  = lire().textContent;
        """)
        # PAS d'assertion sur la COULEUR : cette branche-ci passe par
        # isUsMarketHoursNow(), donc elle est jaune pendant le marché et verte
        # en dehors. Ma première version exigeait health-yellow — elle serait
        # passée ce soir et aurait échoué demain matin. Un test qui dépend de
        # l'heure ment un jour sur deux. On assert donc ce qui est vrai à
        # toute heure, et qui suffit à attraper la dérive redoutée.
        self.assertIn("Exit monitor", r["texte"])
        self.assertNotIn("snapshot", r["texte"],
                         "un moniteur réellement en panne est excusé comme "
                         "un simple retard de publication : %s" % r["texte"])

    def test_un_dry_run_n_a_jamais_droit_au_vert(self):
        """Un dry-run ne ferme AUCUNE position — c'est sa définition. Il
        produit pourtant un horodatage frais et `outcome: "checked"`, donc il
        franchissait toutes les portes jusqu'au vert.

        Mesuré : moniteur programmé mort, bannière rouge ; un seul
        `monitor_exits.py --dry-run` lancé à la main, et la même bannière
        passait au 🟢 « healthy » sans qu'une seule position ait été protégée.

        Même faute que le Ctrl-C corrigé le même jour, mais en pire : le Ctrl-C
        est un accident, le dry-run est ce que le README et le script vidéo
        disent de lancer."""
        r = self.executer(self.PRE + """
            renderMonitorHealth([], {last_run_at: ilYA(0.1), outcome:"checked",
                                     dry_run: true}, ilYA(0.1));
            _resultats.classe = lire().className;
            _resultats.texte  = lire().textContent;
        """)
        self.assertNotEqual(r["classe"], "health-green",
                            "un dry-run est annoncé « healthy » alors qu'il "
                            "n'a rien fermé : %r" % r["texte"])
        self.assertEqual(r["classe"], "health-yellow")
        self.assertIn("DRY RUN", r["texte"])

    def test_un_run_reel_reste_vert(self):
        """TÉMOIN. Sans lui, refuser le vert à TOUT passerait le test
        ci-dessus — et la bannière ne dirait plus jamais que tout va bien."""
        r = self.executer(self.PRE + """
            renderMonitorHealth([], {last_run_at: ilYA(0.1), outcome:"checked",
                                     dry_run: false}, ilYA(0.1));
            _resultats.classe = lire().className;
        """)
        self.assertEqual(r["classe"], "health-green")

    def test_une_page_publiee_avant_ce_champ_se_comporte_comme_avant(self):
        """SECOND TÉMOIN : `dry_run` absent (data.json d'avant ce correctif)
        vaut `undefined`, donc faux. Le comportement des anciennes pages ne
        doit pas changer — sinon le correctif repeindrait en jaune tout
        l'historique déjà publié."""
        r = self.executer(self.PRE + """
            renderMonitorHealth([], {last_run_at: ilYA(0.1), outcome:"checked"},
                                ilYA(0.1));
            _resultats.classe = lire().className;
        """)
        self.assertEqual(r["classe"], "health-green")

    def test_un_dry_run_EN_ECHEC_reste_rouge(self):
        """L'ordre des branches compte : un échec l'emporte sur le dry-run.
        Sinon un vrai plantage serait adouci en jaune parce qu'il se trouve
        avoir été lancé en dry-run."""
        r = self.executer(self.PRE + """
            renderMonitorHealth([], {last_run_at: ilYA(0.1), outcome:"error",
                                     dry_run: true}, ilYA(0.1));
            _resultats.classe = lire().className;
        """)
        self.assertEqual(r["classe"], "health-red")

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
        # On coupe sur la balise ENTIÈRE : `split("kickoff-divider")` tranchait
        # au milieu de `<tr class="kickoff-divider">`, donc le `<tr` du
        # séparateur restait du côté « au-dessus » et faussait le compte de un.
        avant_sep = html.split('<tr class="kickoff-divider"')[0]
        # `- 1` pour la ligne d'en-tête du <thead>.
        lignes_au_dessus = avant_sep.count("<tr") - 1
        self.assertEqual(lignes_au_dessus, 2,
                         "le séparateur n'est pas à la frontière : %d ligne(s) "
                         "au-dessus au lieu de 2" % lignes_au_dessus)

    def test_le_separateur_dit_ce_qu_il_y_a_en_dessous(self):
        html = self._tableau(["2026-08-31T19:37:00+00:00",
                              "2026-08-24T19:05:00+00:00"])
        bas = html.lower()
        self.assertIn("predate the hackathon", bas,
                      "le séparateur n'explique pas ce qui suit")
        self.assertIn("28 aug 15:00 utc", bas,
                      "la frontière exacte n'est pas nommée")
        self.assertIn("nothing is hidden", bas,
                      "le séparateur ne dit pas que rien n'a été retiré — "
                      "c'est justement ce qu'un juge doit pouvoir vérifier")

    def test_le_separateur_dit_COMBIEN_de_lignes_sont_en_dessous(self):
        """AJOUTÉ le 29/08. La ligne disait « tout ce qui suit date d'avant »
        sans dire ce que « tout » pesait. Sur la fenêtre publiée du 28/08 au
        soir : 28 enregistrements sur 30 — la table qu'un juge parcourt est à
        93 % antérieure à l'événement jugé, et rien ne le lui disait.

        Compter est le contraire de filtrer : on ne retire rien, on nomme la
        proportion."""
        html = self._tableau(["2026-08-31T19:37:00+00:00",
                              "2026-08-25T13:13:00+00:00",
                              "2026-08-24T19:05:00+00:00"])
        bas = html.lower()
        self.assertIn("2 of the 3 records", bas,
                      "le séparateur ne dit pas combien de lignes le suivent")

    def test_un_horodatage_illisible_n_est_pas_compte_comme_anterieur(self):
        """TÉMOIN : le compte doit utiliser EXACTEMENT la comparaison qui pose
        le séparateur. Un horodatage illisible rend NaN ; `NaN < kickoff` est
        faux, donc l'enregistrement reste au-dessus de la ligne — et il ne
        doit pas non plus être compté en dessous, sinon le chiffre et la
        position se contrediraient dans la même phrase."""
        html = self._tableau(["2026-08-31T19:37:00+00:00",
                              "pas-une-date",
                              "2026-08-24T19:05:00+00:00"])
        bas = html.lower()
        self.assertIn("1 of the 3 records", bas,
                      "l'illisible a été compté comme antérieur alors qu'il "
                      "reste affiché au-dessus de la ligne")

    def test_rien_n_est_masque(self):
        """Le témoin qui compte le plus. Étiqueter n'est pas filtrer."""
        horodatages = ["2026-08-31T19:37:00+00:00", "2026-08-25T13:13:00+00:00",
                       "2026-08-24T19:05:00+00:00"]
        html = self._tableau(horodatages)
        # On compte les LIGNES de données, pas les « badge » : la classe
        # `badge badge-green` contient le mot deux fois, et mon premier
        # témoin échouait pour cette raison de comptage, pas de comportement.
        # Lignes de DONNÉES = toutes les balises `<tr`, moins l'en-tête du
        # <thead>, moins la ligne du séparateur. L'ancien calcul soustrayait
        # seulement le séparateur et tombait juste par COÏNCIDENCE : à
        # l'époque le motif `"<tr>"` n'attrapait pas le séparateur, et le
        # `- 1` retirait en fait l'en-tête. Les deux termes sont désormais
        # nommés séparément.
        lignes = html.count("<tr") - 1 - html.count('class="kickoff-divider"')
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
        # Les trois enregistrements de cette fixture n'ont pas d'horodatage,
        # donc aucun n'est posterieur au kickoff : le total se lit dans
        # « 1 across the last 3 logged runs ».
        self.assertIn("1 across the last 3 logged runs", r["texte"],
                      "le compteur de fuites ne compte pas exactement les "
                      "prises de hindsight_guard : %r" % r["texte"])

    def test_le_compteur_separe_le_kickoff_du_developpement(self):
        """MESURE le 29/08 sur la fenetre publiee : 11 fuites attrapees, dont
        UNE depuis le kickoff. La banniere affichait « 11 » en tete de page
        sans cette distinction, et le separateur qui l'explique est deux
        sections plus bas, dans le tableau. « last 30 logged runs » etait
        exact et ne suffisait pas : un juge lit le chiffre comme le resultat
        de la semaine live."""
        r = self.executer("""
            const el = document.getElementById('leak-stat');
            const fuite = [{symbol:"XLK", reason:"hindsight_guard: winners disagree"}];
            renderLeakStat([
              {timestamp:"2026-08-28T19:37:00+00:00", verdicts:fuite},
              {timestamp:"2026-08-24T19:05:00+00:00", verdicts:fuite},
              {timestamp:"2026-08-24T18:05:00+00:00", verdicts:fuite}
            ]);
            _resultats.texte = el.textContent;
        """)
        self.assertIn("1 since the 28 Aug kickoff", r["texte"], r["texte"])
        self.assertIn("3 across the last 3 logged runs", r["texte"], r["texte"])
        self.assertIn("2 of them from development", r["texte"], r["texte"])

    def test_tout_depuis_le_kickoff_ne_parle_pas_de_developpement(self):
        """TEMOIN : la phrase ne doit pas inventer des runs de developpement
        quand il n'y en a aucun -- « 3, 0 of them from development » se lit
        comme une precaution, pas comme une mesure."""
        r = self.executer("""
            const el = document.getElementById('leak-stat');
            const fuite = [{symbol:"XLK", reason:"hindsight_guard: winners disagree"}];
            renderLeakStat([
              {timestamp:"2026-08-28T19:37:00+00:00", verdicts:fuite},
              {timestamp:"2026-08-29T19:37:00+00:00", verdicts:fuite}
            ]);
            _resultats.texte = el.textContent;
        """)
        self.assertIn("2 — all since the 28 Aug kickoff", r["texte"], r["texte"])
        self.assertNotIn("development", r["texte"])

    def test_un_horodatage_illisible_compte_comme_du_developpement(self):
        """SECOND TEMOIN, et c'est le sens PRUDENT : ne pas savoir quand un
        run a eu lieu ne le fait pas entrer dans la semaine live. `NaN >=
        kickoff` est faux, exactement comme dans le separateur du tableau --
        la meme comparaison, sur la meme constante partagee."""
        r = self.executer("""
            const el = document.getElementById('leak-stat');
            const fuite = [{symbol:"XLK", reason:"hindsight_guard: winners disagree"}];
            renderLeakStat([
              {timestamp:"2026-08-28T19:37:00+00:00", verdicts:fuite},
              {timestamp:"pas-une-date", verdicts:fuite}
            ]);
            _resultats.texte = el.textContent;
        """)
        self.assertIn("1 since the 28 Aug kickoff", r["texte"], r["texte"])
        self.assertIn("1 of them from development", r["texte"], r["texte"])

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
                    html.count("<tr"), 3,
                    "%s : les enregistrements SAINS ont disparu avec lui "
                    "(%d lignes)" % (cas, html.count("<tr")))

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
        # `"<tr"` et non `"<tr>"` : depuis le 28/08 les lignes anterieures
        # au kickoff portent une classe (elles sont ATTENUEES, jamais
        # retirees), donc le motif exact ne les comptait plus. On compte
        # toujours les LIGNES -- l'intention n'a pas bouge, le motif si.
        self.assertEqual(html.count("<tr"), 3, html[:200])   # 2 lignes + entête
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


class TestLeSensDuTradeEstLisible(BaseRendu):
    """Trouvé en simulant de bout en bout le PREMIER ordre réel — aucun n'a
    encore été soumis (0 dans decision_log.jsonl), donc ce rendu n'avait
    jamais été vu avec de vraies données.

    La page imprimait `direction` BRUT, à quatre endroits. Un juge aurait lu
    « SPY 260904P00640000 **-1** · qty 6 » : un entier signé, qui ne dit rien
    et ressemble à un bug d'affichage."""

    PRE = "const T = 3600000;\n"

    def _rendu(self, direction):
        champ = ("direction:%r," % direction) if direction is not None else ""
        r = self.executer(self.PRE + """
            _resultats.html = renderTrade({run_type:"agent",
              chosen_symbol:"SPY 260904P00640000", qty:6, %s
              order_id:"ord-1"});
        """ % champ)
        import re
        return re.sub(r"<[^>]+>", " ", r["html"] or "")

    def test_un_put_se_lit_put(self):
        sortie = self._rendu(-1)
        self.assertIn("put", sortie)
        # Assertion RESSERREE : ma premiere version cherchait « -1 » n'importe
        # ou dans la ligne et le trouvait dans « ord-1 », l'identifiant de
        # l'ordre. Un test trop large echoue sur ce qu'il ne visait pas -- et
        # aurait pu, dans l'autre sens, passer pour une mauvaise raison.
        # On vise l'EMPLACEMENT de la direction, juste apres le symbole.
        self.assertNotIn("00640000 -1", sortie,
                         "la valeur interne occupe encore la place du sens")

    def test_un_call_se_lit_call(self):
        self.assertIn("call", self._rendu(1))

    def test_une_direction_absente_n_invente_rien(self):
        """TÉMOIN : ne pas savoir ne doit pas produire « call » par défaut.
        Sans lui, une conversion qui rendrait toujours « call » passerait le
        test ci-dessus."""
        sortie = self._rendu(None)
        self.assertNotIn("call", sortie)
        self.assertNotIn("put", sortie)
        self.assertIn("ord-1", sortie, "le reste de la ligne a disparu")

    def test_une_valeur_inattendue_est_montree_telle_quelle(self):
        """SECOND TÉMOIN : une direction qu'on ne sait pas traduire doit
        rester VISIBLE, pas disparaître. Masquer une valeur inconnue, c'est
        la version affichage du « je ne sais pas » rendu en silence."""
        self.assertIn("7", self._rendu(7))


class TestAucuneValeurNeDeborde(BaseRendu):
    """MESURE dans un navigateur le 29/08/2026, a 1280 px de large : la valeur
    de la carte « Account ID » occupait 177 px dans une boite de 139 px.

    Le debordement etait `visible`, donc le texte ne s'arretait pas a la
    bordure -- il continuait SOUS la carte suivante, dont le fond est opaque
    et peint apres. Le dernier caractere du numero -- 12 en tout -- etait invisible, et aucune
    ellipse ne prevenait qu'il manquait quelque chose.

    Le champ tronque etait le seul de la page qui serve a PROUVER sur quel
    compte tourne l'agent -- celui qu'on compare a la valeur declaree. Un
    juge qui lit onze caracteres et en cherche douze conclut a un ecart.

    (Le numero REEL ne figure ni ici ni dans la page : le garde-fou l'a
    signale dans les deux le 29/08, et il avait raison -- une fixture n'a
    pas besoin d'une valeur vraie pour mesurer une largeur.)

    Ce que ces tests peuvent et ne peuvent pas faire : le harnais est Node
    avec un DOM simule, sans moteur de rendu. Il ne MESURE donc aucune
    largeur -- c'est le navigateur qui l'a fait, une fois. Ce qu'il verrouille
    ici, c'est la cause : la classe posee par le rendu, et la regle CSS qui
    la sert. Si l'une des deux disparait, le defaut revient sans bruit."""

    def test_la_carte_identifiant_porte_sa_classe(self):
        r = self.executer("""
            const a = document.getElementById('account-cards');
            renderAccount({account_number:"PA0EXEMPLE00", status:"ACTIVE"});
            _resultats.compte = a.innerHTML;
        """)
        self.assertIn("identifiant", r["compte"],
                      "la carte du numero de compte ne porte plus la classe "
                      "qui l'empeche de deborder")
        self.assertIn("PA0EXEMPLE00", r["compte"],
                      "prerequis : le numero est bien rendu en entier")

    def test_les_autres_cartes_ne_la_portent_pas(self):
        """TEMOIN : mettre la classe partout passerait le test ci-dessus tout
        en rapetissant les montants, qu'on veut lisibles de loin."""
        r = self.executer("""
            const a = document.getElementById('account-cards');
            renderAccount({account_number:"PA1", equity:"1", cash:"2",
                           buying_power:"3", status:"ACTIVE"});
            _resultats.compte = a.innerHTML;
        """)
        # Le message couvre les DEUX sens de l'echec : ma premiere version
        # disait « s'applique a plus d'une carte » et sortait ce texte-la
        # quand la classe avait en fait disparu de partout. Un message qui
        # nomme une cause qu'il n'a pas mesuree, c'est le defaut que ce depot
        # traque ailleurs -- il n'a pas sa place dans un test non plus.
        self.assertEqual(1, r["compte"].count("identifiant"),
                         "exactement une carte doit porter la classe des "
                         "identifiants ; il y en a %d"
                         % r["compte"].count("identifiant"))

    def test_la_regle_css_qui_retient_les_valeurs_existe(self):
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("overflow-wrap: anywhere", page,
                      "plus rien n'empeche une valeur longue de passer sous "
                      "la carte voisine")
        self.assertIn(".card .value.identifiant", page,
                      "la regle qui fait tenir un numero de compte a disparu")


class TestLaPageTientSurUnTelephone(BaseRendu):
    """MESURE dans un navigateur a 375 px le 29/08/2026 : le tableau des
    decisions faisait 427 px dans un conteneur de 327.

    Le conteneur defile bien horizontalement, donc rien n'etait PERDU. Mais la
    colonne « Symbol verdicts » n'etait visible que sur 37 de ses 112 px,
    derriere une barre de defilement qui, sur iOS, n'apparait que pendant
    qu'on defile -- pendant que le bloc « How to read this page », trois
    ecrans plus haut, dit « Look for [le refus] in the verdicts below ». La
    page dirigeait le lecteur vers ce qu'elle avait mis hors-champ.

    Mesure apres empilement : 327 px de large, plus aucun defilement lateral,
    et 4020 px de haut contre 4085 -- les cellules cessent de s'etrangler.

    CE QUE CES TESTS NE FONT PAS : le harnais est Node avec un DOM simule,
    sans moteur de rendu ; aucune largeur n'y est mesurable. Les chiffres
    ci-dessus viennent du navigateur, une fois. Ce qui est verrouille ici,
    c'est ce dont la mise en page depend : les etiquettes que le CSS
    telephone reaffiche, et le bloc de regles lui-meme."""

    def test_chaque_cellule_de_position_porte_son_etiquette(self):
        """Sans en-tete, « us_option / 2 / $778,00 » empile ne veut plus rien
        dire. Le CSS telephone masque le thead et reaffiche `data-colonne`
        devant chaque valeur -- si l'attribut disparait, il ne reste que des
        nombres nus."""
        r = self.executer("""
            const p = document.getElementById('positions-container');
            renderPositions([{symbol:"SPY260904P00769000", asset_class:"us_option",
                              qty:"2", cost_basis:"778", unrealized_plpc:"-0.049"}]);
            _resultats.pos = p.innerHTML;
        """)
        for etiquette in ("Symbol", "Asset class", "Qty", "Cost basis",
                          "Unrealized P&L"):
            self.assertIn('data-colonne="%s"' % etiquette, r["pos"],
                          "la colonne %r n'a plus d'etiquette : empilee sur "
                          "un telephone, sa valeur est un nombre sans nom"
                          % etiquette)

    def test_l_etiquette_ne_remplace_pas_la_valeur(self):
        """TEMOIN : rendre les etiquettes sans les valeurs passerait le test
        ci-dessus."""
        r = self.executer("""
            const p = document.getElementById('positions-container');
            renderPositions([{symbol:"SPY260904P00769000", asset_class:"us_option",
                              qty:"2", cost_basis:"778", unrealized_plpc:"-0.049"}]);
            _resultats.pos = p.innerHTML;
        """)
        self.assertIn("SPY260904P00769000", r["pos"])
        self.assertIn("us_option", r["pos"])
        self.assertIn("-4.9%", r["pos"])

    def test_le_bloc_de_regles_telephone_existe(self):
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 700px)", page,
                      "la mise en page etroite a disparu : sur un telephone, "
                      "la colonne des verdicts ressort de l'ecran")
        for cible in ("#decisions-container thead { display: none; }",
                      "#positions-container thead { display: none; }"):
            self.assertIn(cible, page,
                          "regle manquante : %s" % cible)
        self.assertIn("content: attr(data-colonne)", page,
                      "les etiquettes ne sont plus reaffichees : les valeurs "
                      "des positions s'empilent sans nom")


class TestLeSymboleOptionSeLit(BaseRendu):
    """La table des positions affichait « SPY260904P00769000 » et rien
    d'autre. C'est le seul endroit de la page ou le symbole est SEUL :
    ailleurs renderTrade dit deja « bearish (put) » et les verdicts donnent
    le raisonnement. Un juge qui a cinq minutes ne decode pas dix-huit
    caracteres a la main -- il passe, et la seule position ouverte du
    portefeuille ne lui apprend ni le strike, ni l'echeance, ni le sens."""

    def _pos(self, symbole):
        r = self.executer("""
            const p = document.getElementById('positions-container');
            renderPositions([{symbol:%s, asset_class:"us_option", qty:"2",
                              cost_basis:"778", unrealized_plpc:"-0.049"}]);
            _resultats.pos = p.innerHTML;
        """ % json.dumps(symbole))
        return r["pos"]

    def test_un_symbole_occ_se_lit_en_clair(self):
        sortie = self._pos("SPY260904P00769000")
        self.assertIn("SPY 769 put", sortie)
        self.assertIn("expires 4 Sep 2026", sortie)

    def test_le_symbole_brut_reste_affiche(self):
        """TEMOIN QUI COMPTE : c'est le brut qu'on recopie pour verifier la
        position chez Alpaca. Traduire ne doit pas faire disparaitre la
        reference -- sinon la page devient plus lisible et moins
        verifiable."""
        self.assertIn("SPY260904P00769000", self._pos("SPY260904P00769000"))

    def test_un_call_ne_devient_pas_un_put(self):
        sortie = self._pos("SPY260904C00769000")
        self.assertIn("SPY 769 call", sortie)
        self.assertNotIn("put", sortie)

    def test_un_strike_fractionnaire_garde_ses_decimales(self):
        self.assertIn("SPY 769.5 put", self._pos("SPY260904P00769500"))

    def test_ce_qui_n_est_pas_du_occ_reste_intact(self):
        """TEMOIN : une action ordinaire ne doit rien gagner d'invente. Sans
        lui, un decodage laxiste passerait les tests ci-dessus tout en
        fabriquant une echeance pour n'importe quoi."""
        sortie = self._pos("SPY")
        self.assertIn("SPY", sortie)
        self.assertNotIn("expires", sortie)
        self.assertNotIn("put", sortie)
        self.assertNotIn("call", sortie)

    def test_une_date_impossible_n_est_pas_traduite(self):
        """SECOND TEMOIN : le mois 00 passe la forme (deux chiffres) sans
        etre un mois. Plutot le symbole brut qu'une echeance inventee --
        _MOIS[-1] rendrait `undefined` en plein milieu de la ligne."""
        sortie = self._pos("SPY260004P00769000")
        self.assertIn("SPY260004P00769000", sortie)
        self.assertNotIn("expires", sortie)
        self.assertNotIn("undefined", sortie)

    def test_un_symbole_absent_ne_casse_rien(self):
        r = self.executer("""
            const p = document.getElementById('positions-container');
            renderPositions([{asset_class:"us_option", qty:"2"}]);
            _resultats.pos = p.innerHTML;
        """)
        self.assertIn("—", r["pos"])
        self.assertNotIn("undefined", r["pos"])


class TestChaqueSectionPeutDireQuElleAEchoue(unittest.TestCase):
    """DEUX DES SIX IDENTIFIANTS ETAIENT FAUX, et la panne etait avalee.

    La boucle de rendu isole chaque section : si l'une leve, son catch ecrit
    « This section could not be rendered (…) » DANS son element. Mais deux
    entrees nommaient « account » et « positions », alors que les elements
    s'appellent « account-cards » et « positions-container ».
    getElementById rendait null, le `if (cible)` etait faux, et il ne se
    passait RIEN.

    Reproduit dans un navigateur avant correction, en faisant lever les deux
    rendus :

        ACCOUNT            -> « Loading… », pour toujours
        OPEN POSITIONS     -> VIDE, pas un mot
        bandeau d'erreur   -> pas affiche

    ...et tout le reste de la page rendu normalement, donc d'apparence saine.
    Une liste de positions vide se lit « aucune position ouverte » : la page
    l'affirmait sans avoir rien lu.

    Ce test lit la SOURCE plutot que d'executer la boucle : le DOM simule du
    harnais rend un objet pour n'importe quel identifiant et ne peut donc
    jamais produire le null qui est tout le defaut. Enonce plutot que
    masque."""

    def _ids_des_sections(self):
        page = PAGE.read_text(encoding="utf-8")
        bloc = re.search(r"const sections = \[(.*?)\n    \];", page, re.S)
        self.assertIsNotNone(bloc, "le tableau `sections` n'a pas ete trouve "
                                   "dans docs/index.html ; ce test ne verifie "
                                   "plus rien tant qu'il n'est pas reecrit")
        ids = re.findall(r'\[\s*"([a-z0-9-]+)"\s*,', bloc.group(1))
        # Un motif qui ne trouve plus rien doit ECHOUER, pas passer : c'est
        # exactement ainsi qu'un controle devient decoratif.
        self.assertGreaterEqual(len(ids), 6,
                                "seulement %d section(s) reconnue(s) — le "
                                "motif ne lit plus le tableau" % len(ids))
        return ids

    def test_chaque_identifiant_de_section_existe_dans_la_page(self):
        page = PAGE.read_text(encoding="utf-8")
        for identifiant in self._ids_des_sections():
            self.assertIn('id="%s"' % identifiant, page,
                          "la section %r ecrit son message d'echec dans un "
                          "element qui n'existe pas : sa panne serait "
                          "silencieuse" % identifiant)

    def test_le_compte_et_les_positions_sont_bien_dans_la_liste(self):
        """TEMOIN : le test ci-dessus passerait aussi si quelqu'un RETIRAIT
        les deux sections fautives de la boucle au lieu de corriger leur
        identifiant -- elles perdraient alors toute isolation."""
        ids = self._ids_des_sections()
        self.assertIn("account-cards", ids)
        self.assertIn("positions-container", ids)


class TestUneSectionVideDitPourquoi(BaseRendu):
    """Rendu dans un navigateur avec un data.json absent : le bandeau rouge
    s'affichait bien en haut, et en dessous « ACCOUNT » restait sur
    « Loading… » -- qui ne se resoudra jamais -- pendant que « OPEN
    POSITIONS » et « RECENT DECISIONS » etaient vides, sans un mot.

    Un bandeau en haut ne suffit pas : on ne lit pas une page de haut en bas
    en cherchant a quoi rattacher un vide."""

    def test_les_sections_non_chargees_le_disent(self):
        r = self.executer("""
            _direQueRienN_aEteCharge();
            _resultats.compte = document.getElementById('account-cards').innerHTML;
            _resultats.pos = document.getElementById('positions-container').innerHTML;
            _resultats.dec = document.getElementById('decisions-container').innerHTML;
        """)
        for cle in ("compte", "pos", "dec"):
            self.assertIn("Not loaded", r[cle])
            self.assertIn('not "nothing to report"', r[cle],
                          "le message ne dit pas que le vide n'est pas une "
                          "absence de resultat : %r" % r[cle])

    def test_une_section_deja_rendue_n_est_pas_ecrasee(self):
        """TEMOIN : le repli ne doit pas effacer ce qui a REUSSI avant une
        panne plus tardive. Sans lui, un message d'indisponibilite
        remplacerait des chiffres reels."""
        r = self.executer("""
            const el = document.getElementById('account-cards');
            el.innerHTML = 'DES CHIFFRES REELS';
            el.dataset.rendu = '1';
            _direQueRienN_aEteCharge();
            _resultats.compte = el.innerHTML;
        """)
        self.assertEqual(r["compte"], "DES CHIFFRES REELS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
