#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.
"""Rendre le deck en HTML pour pouvoir REGARDER sa mise en page.

POURQUOI CE FICHIER EXISTE
==========================
Cette machine n'a ni LibreOffice, ni `pdftoppm`, ni `markitdown`, et le
validateur pptx du skill exige Python 3.10 quand la machine a 3.9.6. La mise
en page du deck etait donc la seule chose du dossier que PERSONNE ne pouvait
verifier autrement qu'a l'oeil, sur une autre machine -- ce qui, dans un
projet dont la these est « ne rien affirmer qu'on n'a pas mesure », est
exactement le trou qu'il ne faut pas laisser.

Ce script ne convertit pas le deck. Il le REJOUE : il lit la geometrie
absolue de chaque forme dans l'XML et la repose en HTML positionne au pixel.
Le navigateur fait ensuite le retour a la ligne avec les vraies polices, ce
qui permet de MESURER les debordements au lieu de les estimer.

CE QU'IL REND FIDELEMENT
========================
Mesure faite sur ce deck avant d'ecrire une ligne -- 216 formes, et rien
d'autre que :

    rect 152, roundRect 48, ellipse 15, line 1
    aucune image, aucun groupe, aucun degrade, un seul graphique
    216 formes sur 216 portent leur propre <a:xfrm>

C'est ce qui rend ce rendu honnete : il n'y a AUCUN heritage de gabarit a
deviner. Le script le REVERIFIE a chaque execution et refuse de rendre une
forme sans geometrie plutot que de l'inventer.

Positions, tailles, remplissages, bordures, coins arrondis, ancrage vertical,
tailles de police, gras/italique, interlettrage, couleurs, alignement,
interligne : tous lus dans le fichier.

CE QU'IL NE REND PAS, ET C'EST DIT ICI PLUTOT QUE SOUS-ENTENDU
==============================================================
  . le GRAPHIQUE de la slide 8 -- un cadre gris nomme le remplace. Rendre un
    graphique OOXML serait un second projet, et un faux graphique serait pire
    qu'un trou signale ;
  . les ombres (`a:effectLst`) -- elles ne deplacent rien ;
  . la substitution de police. Le deck demande Calibri ; si le navigateur ne
    l'a pas, il en prend une autre et les LARGEURS changent. Le rapport le
    dit, et c'est la limite qui compte le plus pour un controle de
    debordement.

Usage :
    python3 submission/rendre_le_deck.py
    python3 submission/rendre_le_deck.py --slide 3
    python3 submission/rendre_le_deck.py --sortie /chemin/apercu.html
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from pathlib import Path
from xml.dom import minidom

RACINE = Path(__file__).resolve().parent
DECK = RACINE / "Hindsight_Alpha_Deck.pptx"

# 1 pouce = 914400 EMU, et on rend a 96 points par pouce.
EMU_PAR_PIXEL = 9525.0
# Marges internes d'une zone de texte quand `a:bodyPr` ne les precise pas.
# Valeurs par defaut d'OOXML : 0,1 pouce a gauche/droite, 0,05 en haut/bas.
INSETS_DEFAUT = {"lIns": 91440, "rIns": 91440, "tIns": 45720, "bIns": 45720}


def px(emu: object) -> float:
    return round(float(emu) / EMU_PAR_PIXEL, 2)


def _premier(noeud, nom):
    for e in noeud.getElementsByTagName(nom):
        return e
    return None


def _enfant_direct(noeud, nom):
    for e in noeud.childNodes:
        if getattr(e, "tagName", None) == nom:
            return e
    return None


def _couleur(noeud) -> "str | None":
    """La couleur pleine d'un noeud, ou None. On ne lit que `srgbClr` :
    ce deck n'emploie pas de couleurs de theme, verifie a la mesure."""
    if noeud is None:
        return None
    plein = _enfant_direct(noeud, "a:solidFill")
    if plein is None:
        return None
    c = _enfant_direct(plein, "a:srgbClr")
    return "#" + c.getAttribute("val") if c is not None else None


def _geometrie(sp) -> "tuple[float, float, float, float] | None":
    # `p:xfrm` autant que `a:xfrm` : un `p:graphicFrame` porte sa geometrie
    # sous le prefixe `p:`. Trouve en verifiant le rapport « ce qui n'a pas ete
    # rendu » -- il annoncait ZERO probleme alors que le graphique de la
    # slide 8 n'etait pas rendu. La fonction rendait None, et l'appelant
    # faisait `continue` : le seul element que ce script ne sait pas rendre
    # etait aussi le seul qu'il oubliait de signaler. Exactement le defaut que
    # ce depot traque -- un evenement reel qui perd sa trace dans la
    # comptabilite qui le suit.
    xfrm = _premier(sp, "a:xfrm") or _premier(sp, "p:xfrm")
    if xfrm is None:
        return None
    off, ext = _premier(xfrm, "a:off"), _premier(xfrm, "a:ext")
    if off is None or ext is None:
        return None
    return (px(off.getAttribute("x")), px(off.getAttribute("y")),
            px(ext.getAttribute("cx")), px(ext.getAttribute("cy")))


def _style_de_forme(sp) -> str:
    """Fond, bordure, coins -- lus dans `p:spPr`."""
    spPr = _premier(sp, "p:spPr")
    morceaux = []
    fond = _couleur(spPr)
    morceaux.append("background:%s" % fond if fond else "background:transparent")

    ln = _enfant_direct(spPr, "a:ln") if spPr is not None else None
    if ln is not None:
        trait = _couleur(ln)
        largeur = ln.getAttribute("w")
        if trait:
            morceaux.append("border:%spx solid %s"
                            % (max(1, round(float(largeur) / EMU_PAR_PIXEL))
                               if largeur else 1, trait))

    geom = _premier(sp, "a:prstGeom")
    forme = geom.getAttribute("prst") if geom is not None else "rect"
    if forme == "ellipse":
        morceaux.append("border-radius:50%")
    elif forme == "roundRect":
        # OOXML exprime le rayon en fraction du petit cote ; 0.1 est le defaut
        # et ce deck ne le surcharge nulle part (verifie).
        morceaux.append("border-radius:10px")
    return ";".join(morceaux)


def _paragraphes(sp) -> "list[dict]":
    corps = _premier(sp, "p:txBody")
    if corps is None:
        return []
    sortie = []
    for p in corps.getElementsByTagName("a:p"):
        pPr = _enfant_direct(p, "a:pPr")
        algn = pPr.getAttribute("algn") if pPr is not None else ""
        interligne = None
        if pPr is not None:
            lnSpc = _enfant_direct(pPr, "a:lnSpc")
            if lnSpc is not None:
                pct = _enfant_direct(lnSpc, "a:spcPct")
                if pct is not None:
                    interligne = float(pct.getAttribute("val")) / 100000.0
            aft = _enfant_direct(pPr, "a:spcAft")
            if aft is not None:
                pts = _enfant_direct(aft, "a:spcPts")
                if pts is not None:
                    sortie_apres = float(pts.getAttribute("val")) / 100.0
                else:
                    sortie_apres = 0.0
            else:
                sortie_apres = 0.0
        else:
            sortie_apres = 0.0

        runs = []
        for r in p.getElementsByTagName("a:r"):
            t = _premier(r, "a:t")
            texte = t.firstChild.nodeValue if (t is not None and t.firstChild) else ""
            if not texte:
                continue
            rPr = _premier(r, "a:rPr")
            style = []
            if rPr is not None:
                sz = rPr.getAttribute("sz")
                if sz:
                    style.append("font-size:%.2fpt" % (float(sz) / 100.0))
                if rPr.getAttribute("b") == "1":
                    style.append("font-weight:700")
                if rPr.getAttribute("i") == "1":
                    style.append("font-style:italic")
                if rPr.getAttribute("u") not in ("", "none"):
                    style.append("text-decoration:underline")
                spc = rPr.getAttribute("spc")
                if spc:
                    style.append("letter-spacing:%.2fpt" % (float(spc) / 100.0))
                col = _couleur(rPr)
                if col:
                    style.append("color:%s" % col)
                latin = _premier(rPr, "a:latin")
                if latin is not None and latin.getAttribute("typeface"):
                    style.append('font-family:"%s",Calibri,Carlito,'
                                 '"Helvetica Neue",Arial,sans-serif'
                                 % latin.getAttribute("typeface"))
            runs.append((texte, ";".join(style)))
        sortie.append({"algn": algn, "interligne": interligne,
                       "apres": sortie_apres, "runs": runs})
    return sortie


ALIGNEMENT = {"ctr": "center", "r": "right", "just": "justify", "l": "left"}


def _forme_en_html(sp, index: int, nom_slide: str) -> "tuple[str, str | None]":
    """(html, probleme). `probleme` non nul = quelque chose n'a pas pu etre
    rendu FIDELEMENT ; il est signale, jamais devine."""
    geo = _geometrie(sp)
    if geo is None:
        return "", ("%s forme %d : aucune geometrie explicite — non rendue "
                    "plutot qu'inventee" % (nom_slide, index))
    x, y, w, h = geo

    corps = _premier(sp, "p:txBody")
    bodyPr = _premier(corps, "a:bodyPr") if corps is not None else None
    insets = dict(INSETS_DEFAUT)
    if bodyPr is not None:
        for cle in insets:
            v = bodyPr.getAttribute(cle)
            if v:
                insets[cle] = float(v)
    ancre = bodyPr.getAttribute("anchor") if bodyPr is not None else ""
    justif = {"ctr": "center", "b": "flex-end"}.get(ancre, "flex-start")

    lignes = []
    for para in _paragraphes(sp):
        if not para["runs"]:
            lignes.append('<p class="vide"></p>')
            continue
        style_p = ["margin:0"]
        if para["algn"]:
            style_p.append("text-align:%s" % ALIGNEMENT.get(para["algn"], "left"))
        if para["interligne"]:
            style_p.append("line-height:%.3f" % para["interligne"])
        if para["apres"]:
            style_p.append("margin-bottom:%.2fpt" % para["apres"])
        morceaux = "".join('<span style="%s">%s</span>'
                           % (s, html.escape(t)) for t, s in para["runs"])
        lignes.append('<p style="%s">%s</p>' % (";".join(style_p), morceaux))

    style_boite = (
        "position:absolute;left:%spx;top:%spx;width:%spx;height:%spx;"
        "box-sizing:border-box;overflow:visible;%s"
        % (x, y, w, h, _style_de_forme(sp)))
    style_texte = (
        "position:absolute;inset:%spx %spx %spx %spx;display:flex;"
        "flex-direction:column;justify-content:%s;overflow:visible"
        % (px(insets["tIns"]), px(insets["rIns"]),
           px(insets["bIns"]), px(insets["lIns"]), justif))

    return ('<div class="forme" data-forme="%s#%d" style="%s">'
            '<div class="txt" style="%s">%s</div></div>'
            % (nom_slide, index, style_boite, style_texte, "".join(lignes))), None


SONDE = """
// Mesure des debordements. Le navigateur vient de faire le retour a la ligne
// avec les vraies polices : c'est le seul moment ou « ce texte deborde-t-il »
// est une MESURE et non une estimation.
window.__DEBORDEMENTS = [];
document.querySelectorAll('.forme').forEach(function (f) {
  var t = f.querySelector('.txt');
  if (!t || !t.textContent.trim()) return;
  var hb = f.getBoundingClientRect().height;
  var ht = t.scrollHeight;
  var lb = f.getBoundingClientRect().width;
  var large = 0;
  t.querySelectorAll('p').forEach(function (p) {
    large = Math.max(large, p.scrollWidth);
  });
  var depasse_bas = ht - (hb - PADV);
  var depasse_droite = large - (lb - PADH);
  if (depasse_bas > 1 || depasse_droite > 1) {
    f.classList.add('deborde');
    window.__DEBORDEMENTS.push({
      forme: f.dataset.forme,
      bas: Math.round(depasse_bas),
      droite: Math.round(depasse_droite),
      texte: t.textContent.trim().slice(0, 60)
    });
  }
});
// Hors de la diapo : une forme qui commence ou finit au-dela du cadre.
window.__HORS_CADRE = [];
document.querySelectorAll('.slide').forEach(function (s) {
  var r = s.getBoundingClientRect();
  s.querySelectorAll('.forme').forEach(function (f) {
    var q = f.getBoundingClientRect();
    if (q.left < r.left - 1 || q.top < r.top - 1 ||
        q.right > r.right + 1 || q.bottom > r.bottom + 1) {
      f.classList.add('hors-cadre');
      window.__HORS_CADRE.push({forme: f.dataset.forme});
    }
  });
});
var e = document.getElementById('verdict');
e.textContent = window.__DEBORDEMENTS.length + ' debordement(s), '
  + window.__HORS_CADRE.length + ' forme(s) hors cadre';
e.className = (window.__DEBORDEMENTS.length + window.__HORS_CADRE.length)
  ? 'mauvais' : 'bon';
"""


def construire(chemin_deck: Path, seulement: "int | None") -> "tuple[str, list]":
    z = zipfile.ZipFile(chemin_deck)
    pres = minidom.parseString(z.read("ppt/presentation.xml"))
    taille = _premier(pres, "p:sldSz")
    largeur, hauteur = px(taille.getAttribute("cx")), px(taille.getAttribute("cy"))

    noms = sorted(
        [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
        key=lambda n: int(re.search(r"\d+", n.split("/")[-1]).group()))

    problemes, slides = [], []
    for numero, nom in enumerate(noms, 1):
        if seulement is not None and numero != seulement:
            continue
        doc = minidom.parseString(z.read(nom))
        formes = []
        for i, sp in enumerate(doc.getElementsByTagName("p:sp"), 1):
            frag, souci = _forme_en_html(sp, i, "slide%d" % numero)
            if souci:
                problemes.append(souci)
            formes.append(frag)
        for cadre in doc.getElementsByTagName("p:graphicFrame"):
            problemes.append("slide%d : un graphique OOXML — remplace par un "
                             "cadre nomme, pas rendu" % numero)
            geo = _geometrie(cadre)
            if geo is None:
                problemes.append("slide%d : ce graphique n'a meme pas de "
                                 "geometrie lisible — rien n'apparaitra a sa "
                                 "place sur le rendu" % numero)
                continue
            x, y, w, h = geo
            formes.append(
                '<div class="forme non-rendu" data-forme="slide%d#graphique" '
                'style="position:absolute;left:%spx;top:%spx;width:%spx;'
                'height:%spx">GRAPHIQUE NON RENDU</div>' % (numero, x, y, w, h))
        slides.append('<figure><figcaption>slide %d — %s</figcaption>'
                      '<div class="slide" style="width:%spx;height:%spx">%s</div>'
                      '</figure>' % (numero, html.escape(nom.split("/")[-1]),
                                     largeur, hauteur, "".join(formes)))

    page = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Hindsight Alpha — rendu du deck</title><style>
 body{margin:0;padding:24px;background:#12141a;color:#e6e8ee;
      font:14px/1.5 system-ui,-apple-system,sans-serif}
 h1{font-size:18px;margin:0 0 4px}
 #verdict{font-weight:700;padding:6px 10px;border-radius:6px;display:inline-block}
 #verdict.bon{background:#0f766e;color:#fff}
 #verdict.mauvais{background:#b91c1c;color:#fff}
 .avert{color:#fbbf24;margin:10px 0 20px;max-width:1280px}
 figure{margin:0 0 28px}
 figcaption{font:12px ui-monospace,monospace;color:#8b93a7;margin-bottom:6px}
 .slide{position:relative;background:#fff;color:#111;overflow:hidden;
        box-shadow:0 2px 18px rgba(0,0,0,.55)}
 .forme{}
 .forme p{margin:0}
 .deborde{outline:2px solid #ef4444;outline-offset:1px}
 .hors-cadre{outline:2px dashed #f59e0b}
 .non-rendu{display:flex;align-items:center;justify-content:center;
            border:2px dashed #94a3b8;color:#64748b;
            font:12px ui-monospace,monospace;background:#f1f5f9}
</style></head><body>
<h1>Hindsight Alpha — rendu du deck</h1>
<div id="verdict">mesure en cours…</div>
<p class="avert">Ce rendu rejoue la géométrie du fichier ; il ne le convertit
pas. <b>Le graphique de la slide 8 n'est pas rendu</b> (cadre gris), les ombres
sont ignorées, et si ce navigateur n'a pas Calibri il substitue une police
dont les <b>largeurs diffèrent</b> — c'est la limite qui compte pour un
contrôle de débordement. Cadre rouge = le texte dépasse sa boîte. Cadre
orange = la forme sort de la diapo.</p>
%s
<script>var PADV=0,PADH=0;%s</script>
</body></html>""" % ("".join(slides), SONDE)
    return page, problemes


# ---------------------------------------------------------------------------
# Mesure des debordements, SANS navigateur
# ---------------------------------------------------------------------------
#
# Le rendu HTML ci-dessus se regarde ; il ne se mesure pas ici, parce que le
# retour a la ligne est fait par le navigateur. Deux chemins ont ete essayes
# le 29/08/2026 pour recuperer cette mesure, et tous deux sont fermes sur
# cette machine :
#
#   . le volet d'apercu rend les fichiers hors projet en INSTANTANE STATIQUE,
#     donc le JS de sonde ne tourne pas ;
#   . servir la page en HTTP local echoue : le bac a sable refuse d'ouvrir un
#     port en ecoute (`socket.bind -> PermissionError`), et le connecteur
#     Chrome force `https://` sur toute URL, donc `file://` est inatteignable.
#
# La sortie n'est donc pas d'attendre un navigateur, c'est de calculer la
# largeur du texte SOI-MEME a partir du fichier de police. C'est plus fiable :
# deterministe, reproductible, et le resultat ne depend pas de quel navigateur
# a ouvert la page.
#
# CE QUE CETTE MESURE NE PEUT PAS SAVOIR, et c'est la limite qui compte :
# **Calibri n'est pas installe sur ce Mac** (verifie). Le deck le demande 128
# fois, et Cambria 35. La mesure se fait donc avec la police de remplacement
# reellement disponible, dont les largeurs DIFFERENT. C'est pour ca que le
# seuil d'alerte est pose a 90 % de remplissage et pas a 100 : les 10 %
# restants sont la marge d'incertitude de la substitution, pas du confort.

# Calibri et Cambria sont proprietaires et absentes de ce Mac. Carlito et
# Caladea sont leurs clones LIBRES et METRIQUEMENT COMPATIBLES : memes chasses,
# donc une mesure faite avec eux vaut pour la police reelle.
#
# Et ca se VERIFIE plutot que de se croire. Carlito declare upem=2048,
# ascendante 1950, descendante -550 -- les valeurs exactes de Calibri. Le
# script le controle au demarrage et le dit ; si un jour il tombe sur une
# Carlito qui ne les porte plus, il annonce une mesure APPROCHEE au lieu de
# continuer a promettre l'exactitude.
#
# Avant leur installation, la mesure se faisait avec Arial, environ 8 % plus
# large : le seuil devait alors absorber cette incertitude. Il ne le doit plus
# quand les metriques sont exactes -- voir SEUIL_EXACT.
_MAISON = str(Path.home() / "Library" / "Fonts")
POLICES = {
    "Calibri": {
        "": [_MAISON + "/Carlito-Regular.ttf",
             "/System/Library/Fonts/Supplemental/Arial.ttf"],
        "b": [_MAISON + "/Carlito-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    },
    "Cambria": {
        "": [_MAISON + "/Caladea-Regular.ttf",
             "/System/Library/Fonts/Supplemental/Times New Roman.ttf"],
        "b": [_MAISON + "/Caladea-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"],
    },
}
# Metriques attendues d'une police metriquement compatible, par famille visee.
METRIQUES_ATTENDUES = {"Calibri": (2048, 1950, -550)}
# 0.98 quand les metriques sont EXACTES (clone metriquement compatible), 0.90
# sinon. Les 10 % de l'ancien seuil n'etaient pas du confort : c'etait la marge
# d'incertitude de la substitution par Arial. Une fois cette incertitude
# supprimee, la garder reviendrait a signaler des zones qui vont bien.
SEUIL_EXACT = 0.98
SEUIL_APPROCHE = 0.90


def _lire_metriques(chemin: str) -> dict:
    import struct
    d = Path(chemin).read_bytes()
    nb = struct.unpack(">H", d[4:6])[0]
    tables = {}
    for i in range(nb):
        o = 12 + 16 * i
        tag = d[o:o + 4].decode("latin-1")
        off, ln = struct.unpack(">II", d[o + 8:o + 16])
        tables[tag] = (off, ln)
    ho = tables["head"][0]
    upem = struct.unpack(">H", d[ho + 18:ho + 20])[0]
    hh = tables["hhea"][0]
    nhm = struct.unpack(">H", d[hh + 34:hh + 36])[0]
    asc, desc, gap = struct.unpack(">hhh", d[hh + 4:hh + 10])
    hm = tables["hmtx"][0]
    aw = [struct.unpack(">H", d[hm + 4 * i:hm + 4 * i + 2])[0] for i in range(nhm)]
    co = tables["cmap"][0]
    n = struct.unpack(">H", d[co + 2:co + 4])[0]
    sub = None
    for i in range(n):
        pid, eid, off = struct.unpack(">HHI", d[co + 4 + 8 * i:co + 12 + 8 * i])
        if (pid, eid) in ((3, 1), (0, 3), (3, 10), (0, 4)):
            sub = co + off
    carte = {}
    if sub is not None and struct.unpack(">H", d[sub:sub + 2])[0] == 4:
        segx2 = struct.unpack(">H", d[sub + 6:sub + 8])[0]
        seg = segx2 // 2
        e = sub + 14
        ends = struct.unpack(">%dH" % seg, d[e:e + segx2]); e += segx2 + 2
        starts = struct.unpack(">%dH" % seg, d[e:e + segx2]); e += segx2
        deltas = struct.unpack(">%dh" % seg, d[e:e + segx2]); e += segx2
        ro_off = e
        ros = struct.unpack(">%dH" % seg, d[e:e + segx2])
        for i in range(seg):
            for c in range(starts[i], min(ends[i], 0xFFFF) + 1):
                if ros[i] == 0:
                    g = (c + deltas[i]) & 0xFFFF
                else:
                    p = ro_off + 2 * i + ros[i] + 2 * (c - starts[i])
                    if p + 2 > len(d):
                        continue
                    g = struct.unpack(">H", d[p:p + 2])[0]
                    if g:
                        g = (g + deltas[i]) & 0xFFFF
                if g:
                    carte[c] = g
    return {"upem": upem, "asc": asc, "desc": desc, "gap": gap,
            "aw": aw, "carte": carte, "fichier": Path(chemin).name}


def _largeur(m: dict, texte: str, pt: float, interlettrage: float = 0.0) -> float:
    total = 0.0
    for ch in texte:
        g = m["carte"].get(ord(ch), 0)
        total += m["aw"][g] if g < len(m["aw"]) else m["aw"][-1]
    return total / m["upem"] * pt + interlettrage * len(texte)


def _lignes(m, mots, pt, spc, largeur_dispo) -> int:
    """Retour a la ligne gourmand, comme le fait une zone de texte."""
    if not mots:
        return 1
    n, courante = 1, ""
    for mot in mots:
        essai = (courante + " " + mot).strip()
        if _largeur(m, essai, pt, spc) <= largeur_dispo or not courante:
            courante = essai
        else:
            n += 1
            courante = mot
    return n


def _reglages(paras, caches):
    """(paragraphe, famille, taille, interlettrage) pour chaque paragraphe
    dont la police est disponible. Sorti en fonction parce que la boucle de
    mesure et le test « une seule ligne ? » doivent lire EXACTEMENT les memes
    reglages ; deux lectures separees divergent au premier changement."""
    for para in paras:
        if not para["runs"]:
            continue
        pt, spc, famille, graisse = 18.0, 0.0, "Calibri", ""
        for _t, style in para["runs"]:
            if "font-weight:700" in style:
                graisse = "b"
            m = re.search(r"font-size:([\d.]+)pt", style)
            if m:
                pt = float(m.group(1))
            m = re.search(r"letter-spacing:([\d.]+)pt", style)
            if m:
                spc = float(m.group(1))
            m = re.search(r'font-family:"([^"]+)"', style)
            if m:
                famille = m.group(1)
        if (famille, graisse) in caches:
            yield para, (famille, graisse), pt, spc


def mesurer(chemin_deck: Path,
            seulement: "int | None") -> "tuple[list, list, list, float]":
    """(alertes, notes). Une alerte = une zone dont le texte remplit plus que
    du seuil de remplissage, ou dont un mot depasse en largeur."""
    caches, notes, exact_par_cle = {}, [], {}
    for demandee, variantes in POLICES.items():
        for graisse, chemins in variantes.items():
            for c in chemins:
                if Path(c).exists():
                    m = _lire_metriques(c)
                    caches[(demandee, graisse)] = m
                    attendu = METRIQUES_ATTENDUES.get(demandee)
                    compatible = attendu is None or (
                        m["upem"], m["asc"], m["desc"]) == attendu
                    exact_par_cle[(demandee, graisse)] = bool(
                        attendu is not None and compatible)
                    if attendu is not None and compatible:
                        notes.append(
                            "« %s »%s : mesure avec %s — metriquement "
                            "compatible, VERIFIE (upem %d, asc %d, desc %d, "
                            "les valeurs exactes de %s)"
                            % (demandee, " gras" if graisse else "",
                               Path(c).name, m["upem"], m["asc"], m["desc"],
                               demandee))
                    else:
                        # Distinguer « les metriques CONTREDISENT la
                        # reference » de « je n'ai aucune reference ». Caladea
                        # tombait dans le second cas et etait annoncee comme si
                        # elle avait echoue a un controle qui n'existait pas
                        # pour elle. Nommer la mauvaise cause est le defaut que
                        # ce depot traque le plus souvent.
                        if attendu is None:
                            raison = ("aucune valeur de reference pour %s ici "
                                      "— largeurs traitees comme approchees"
                                      % demandee)
                        else:
                            raison = ("metriques DIFFERENTES de %s "
                                      "(upem %d/%d, asc %d/%d) — largeurs "
                                      "approchees"
                                      % (demandee, m["upem"], attendu[0],
                                         m["asc"], attendu[1]))
                        notes.append("« %s »%s : mesure avec %s — %s"
                                     % (demandee, " gras" if graisse else "",
                                        Path(c).name, raison))
                    break
            else:
                notes.append("« %s »%s : aucune police trouvee — les zones "
                             "qui l'emploient ne sont PAS mesurees"
                             % (demandee, " gras" if graisse else ""))
    # Le seuil est propre a CHAQUE forme, pas global. Ma premiere version
    # gardait un seul drapeau « exactes » : une seule famille non verifiee
    # (Cambria, 35 emplois) faisait annoncer « mesure approchee » sur les 128
    # zones en Calibri, qui sont mesurees exactement. Un fait par element,
    # resume en un drapeau unique, redevient faux pour presque tous.
    seuil_global = (SEUIL_EXACT if exact_par_cle and all(exact_par_cle.values())
                    else SEUIL_APPROCHE)

    z = zipfile.ZipFile(chemin_deck)
    noms = sorted(
        [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
        key=lambda n: int(re.search(r"\d+", n.split("/")[-1]).group()))

    alertes, non_mesurables = [], []
    for numero, nom in enumerate(noms, 1):
        if seulement is not None and numero != seulement:
            continue
        doc = minidom.parseString(z.read(nom))
        for i, sp in enumerate(doc.getElementsByTagName("p:sp"), 1):
            geo = _geometrie(sp)
            paras = _paragraphes(sp)
            if geo is None or not any(p["runs"] for p in paras):
                continue
            _x, _y, w, h = geo
            corps = _premier(sp, "p:txBody")
            bodyPr = _premier(corps, "a:bodyPr") if corps is not None else None
            insets = dict(INSETS_DEFAUT)
            if bodyPr is not None:
                for cle in insets:
                    v = bodyPr.getAttribute(cle)
                    if v:
                        insets[cle] = float(v)
            # px -> pt : 96 px/pouce, 72 pt/pouce
            dispo_l = (w - px(insets["lIns"]) - px(insets["rIns"])) * 0.75
            dispo_h = (h - px(insets["tIns"]) - px(insets["bIns"])) * 0.75

            hauteur = 0.0
            plus_large = 0.0
            reglages = list(_reglages(paras, caches))
            mesure_partielle = (
                len(reglages) != len([p for p in paras if p["runs"]]))
            for para, cle, pt, spc in reglages:
                met = caches[cle]
                texte = "".join(t for t, _s in para["runs"])
                n = _lignes(met, texte.split(), pt, spc, dispo_l)
                interligne = para["interligne"] or 1.2
                hauteur += n * pt * interligne + para["apres"]
                # NON CLAMPEE, exprès. Ma premiere version prenait
                # `min(largeur, dispo)` des qu'il y avait retour a la ligne,
                # si bien que « de combien une police devrait-elle etre plus
                # etroite » rendait ZERO sur tous les cas qui la justifiaient.
                # La question porte sur la ligne UNIQUE, pas sur le texte
                # replie.
                plus_large = max(plus_large, _largeur(met, texte, pt, spc))
            # Une boite plus etroite que ses propres marges internes donne une
            # largeur disponible NEGATIVE. Ca arrive pour les fleches
            # decoratives de la slide 4 (boite de 10 pt, marges de 14,4 pt) :
            # le texte y deborde PAR CONSTRUCTION, centre dans un trait fin.
            # Ma premiere version les comptait comme « 22 pt trop large » --
            # quatre fausses alertes sur dix. Une mesure impossible n'est pas
            # une mesure ratee : elle se DIT, elle ne se convertit pas en
            # verdict.
            if mesure_partielle or dispo_h <= 0 or dispo_l <= 0:
                if dispo_l <= 0 < dispo_h:
                    non_mesurables.append(
                        "slide %d forme %d : boite plus etroite que ses "
                        "marges internes — debordement voulu, non mesure"
                        % (numero, i))
                continue
            taux = hauteur / dispo_h
            # Un texte qui se replie n'est pas « trop large » : il tient,
            # sur plusieurs lignes. Seule une zone d'une SEULE ligne peut
            # deborder en largeur.
            une_seule_ligne = all(
                _lignes(caches[cle], "".join(t for t, _s in p["runs"]).split(),
                        pt_, spc_, dispo_l) == 1
                for p, cle, pt_, spc_ in reglages)
            trop_large = (plus_large - dispo_l) if une_seule_ligne else 0.0
            exact_ici = bool(reglages) and all(
                exact_par_cle.get(cle) for _p, cle, _pt, _spc in reglages)
            seuil = SEUIL_EXACT if exact_ici else SEUIL_APPROCHE
            if taux > seuil or trop_large > 1:
                extrait = "".join(t for p in paras for t, _s in p["runs"])[:58]
                # De combien une police devrait-elle etre PLUS ETROITE pour
                # que ce texte tienne sur une ligne ? C'est ce qui repond a
                # « est-ce un vrai debordement ou l'effet de la substitution
                # de police ? » : Calibri est environ 8 % plus etroite
                # qu'Arial, donc au-dela de ~10 % le debordement tient quelle
                # que soit la police.
                besoin = (round((1 - dispo_l / plus_large) * 100)
                          if plus_large > dispo_l else 0)
                alertes.append({
                    "slide": numero, "forme": i,
                    "remplissage": round(taux * 100, 1),
                    "debord_largeur": round(trop_large, 1),
                    "police_plus_etroite": besoin,
                    "boite": (_x, _y, w, h), "exact": exact_ici,
                    "hauteur_texte_px": hauteur / 0.75,
                    "texte": extrait})

        # Un debordement ne se voit que s'il TOUCHE quelque chose. Le texte
        # deborde d'une boite ancree au centre a parts egales en haut et en
        # bas ; on regarde si ce debord recouvre une autre forme de la meme
        # diapo. C'est la seule des trois mesures qui dise « c'est casse »
        # plutot que « c'est serre ».
        boites = []
        for i, sp in enumerate(doc.getElementsByTagName("p:sp"), 1):
            g = _geometrie(sp)
            if g is not None:
                boites.append((i, g))
        for al in [a for a in alertes if a["slide"] == numero and "boite" in a]:
            x, y, w, h = al["boite"]
            debord = max(0.0, al["hauteur_texte_px"] - h) / 2.0
            if debord <= 1:
                continue
            haut, bas = y - debord, y + h + debord
            touches = []
            for j, (bx, by, bw, bh) in boites:
                if j == al["forme"]:
                    continue
                if not (bx < x + w and bx + bw > x):
                    continue
                # Le chevauchement doit etre CAUSE par le debordement.
                # Corrige le 29/08 apres verification a la main : la premiere
                # version signalait « le debord recouvre la forme 1 » sur la
                # slide 4, ou les deux boites se chevauchent DEJA (43-77 contre
                # 72-158) sans qu'aucun texte ne deborde. Elle nommait les
                # bonnes formes pour la mauvaise raison -- et « ce debordement
                # casse quelque chose » est precisement ce qu'un lecteur
                # croirait sur parole.
                deja = by < y + h and by + bh > y
                apres = by < bas and by + bh > haut
                if apres and not deja:
                    touches.append(j)
            al["touche"] = touches
    return alertes, notes, non_mesurables, seuil_global


def main() -> None:
    a = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--deck", default=str(DECK))
    a.add_argument("--slide", type=int, default=None,
                   help="ne rendre qu'une diapo (numerotee a partir de 1)")
    a.add_argument("--sortie", default=str(RACINE / "apercu_deck.html"))
    args = a.parse_args()

    chemin = Path(args.deck)
    if not chemin.exists():
        print("deck introuvable : %s" % chemin, file=sys.stderr)
        raise SystemExit(2)

    page, problemes = construire(chemin, args.slide)
    Path(args.sortie).write_text(page, encoding="utf-8")
    print("ecrit : %s" % args.sortie)
    if problemes:
        print("\nCE QUI N'A PAS ETE RENDU FIDELEMENT (%d) :" % len(problemes))
        for p in problemes:
            print("  . %s" % p)
    alertes, notes, non_mesurables, seuil_utilise = mesurer(
        chemin, args.slide)
    print("\nMESURE DES DEBORDEMENTS (metriques de police lues dans le "
          "fichier TTF, sans navigateur)")
    for n in notes:
        print("  . %s" % n)
    print("  . seuil d'alerte : %d %% quand les metriques sont exactes, "
          "%d %% sinon — et c'est decide PAR ZONE, selon les polices qu'elle "
          "emploie." % (SEUIL_EXACT * 100, SEUIL_APPROCHE * 100))
    if not alertes:
        print("\n  aucune zone au-dela du seuil.")
    else:
        print("\n  %d zone(s) a regarder :" % len(alertes))
        for al in sorted(alertes, key=lambda x: -x["remplissage"]):
            print("    slide %-2d forme %-3d  %5.1f %% de la hauteur"
                  % (al["slide"], al["forme"], al["remplissage"]))
            print("        « %s »" % al["texte"])
            if al.get("police_plus_etroite"):
                # Cette phrase disait « pourrait tenir en Calibri (~8 % plus
                # etroite qu'Arial) » — vraie tant que la mesure se faisait
                # avec Arial, FAUSSE des l'installation de Carlito, qui donne
                # les chasses exactes de Calibri. Une phrase qui survit au
                # changement de sa propre premisse est le defaut le plus
                # courant de ce depot ; elle lit desormais la premisse.
                verdict = ("le texte passe a la ligne, mesure exacte"
                           if al.get("exact")
                           else "mesure approchee : sous ~10 %, la vraie "
                                "police pourrait le faire tenir")
                print("        il faudrait une police %d %% plus etroite "
                      "pour une seule ligne — %s"
                      % (al["police_plus_etroite"], verdict))
            if al.get("touche"):
                print("        >>> le debord RECOUVRE la ou les formes %s"
                      % ", ".join(str(t) for t in al["touche"]))
            elif "touche" in al:
                print("        le debord ne recouvre aucune autre forme")
        if non_mesurables:
            print("\n  non mesure (%d) :" % len(non_mesurables))
            for nm in non_mesurables:
                print("    . %s" % nm)


if __name__ == "__main__":
    main()
