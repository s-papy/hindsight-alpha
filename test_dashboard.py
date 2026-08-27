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


if __name__ == "__main__":
    unittest.main(verbosity=2)
