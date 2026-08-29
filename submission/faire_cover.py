# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha

"""Fabrique submission/cover.png -- l'image de couverture de la soumission.

POURQUOI CE FICHIER EXISTE. lablab exige une cover image (« recommended 16:9
ratio », page Hackathon Guidelines). Elle manquait, et une image faite a la
main ne se refait pas : celle-ci se REGENERE, comme HINDSIGHT_HOLDOUT.md.

PILLOW N'EST PAS DANS requirements.txt, ET C'EST DELIBERE. L'agent n'en a
aucun besoin ; le seul module tiers du depot reste python-dotenv, et
`controle_dependances_scellees` scelle ce fichier-la. On installe donc Pillow
a cote, jamais dans l'environnement de l'agent :

    python3 -m pip install --target /tmp/pylibs Pillow
    PYTHONPATH=/tmp/pylibs python3 submission/faire_cover.py

CE QUE L'IMAGE DIT, ET RIEN DE PLUS. Les deux fenetres gagnantes de XLK
(90 jours sur l'historique complet, 10 jours en in-sample) sont celles que
BACKTEST_RESULTS.md enregistre et que la reproduction independante du 29/08 a
confirmees. « Refused every run » est verifie dans decision_log.jsonl : 15
verdicts XLK, 15 refus. Le taux de fausse alerte mesure (23 %) figure dans le
bas de l'image -- une couverture qui vend le mecanisme sans dire qu'il se
trompe une fois sur quatre serait exactement ce que ce projet reproche ailleurs.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

L, H = 1920, 1080                      # 16:9
FOND = (11, 13, 18)                    # --bg du tableau de bord
CARTE = (21, 24, 34)                   # --card
BORD = (35, 40, 56)                    # --border
TEXTE = (232, 234, 240)
DISCRET = (139, 146, 165)
ROUGE = (248, 113, 113)
VERT = (52, 211, 153)

POLICES = "/System/Library/Fonts/Supplemental"


def _police(nom: str, taille: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(POLICES, nom), taille)


def _largeur(d: ImageDraw.ImageDraw, texte: str, police) -> int:
    g, h, dr, b = d.textbbox((0, 0), texte, font=police)
    return dr - g


def _carte(d, x, y, l, h, bord=BORD, fond=CARTE):
    d.rounded_rectangle([x, y, x + l, y + h], radius=18, fill=fond,
                        outline=bord, width=2)


def construire() -> Image.Image:
    img = Image.new("RGB", (L, H), FOND)
    d = ImageDraw.Draw(img)

    titre = _police("Arial Bold.ttf", 104)
    sous = _police("Arial.ttf", 40)
    etiquette = _police("Arial.ttf", 28)
    valeur = _police("Arial Bold.ttf", 60)
    verdict = _police("Arial Bold.ttf", 46)
    pied = _police("Arial.ttf", 28)

    MARGE = 120
    d.text((MARGE, 96), "Hindsight Alpha", font=titre, fill=TEXTE)
    d.text((MARGE, 232),
           "An options-trading agent that refuses to trade when its own",
           font=sous, fill=DISCRET)
    d.text((MARGE, 286),
           "parameter selection fails an out-of-sample check.",
           font=sous, fill=DISCRET)

    # Les deux notations, cote a cote, puis le refus.
    haut, hcarte, lcarte, ecart = 420, 220, 520, 60
    _carte(d, MARGE, haut, lcarte, hcarte)
    d.text((MARGE + 40, haut + 38), "SCORED ON THE FULL HISTORY",
           font=etiquette, fill=DISCRET)
    d.text((MARGE + 40, haut + 96), "90-day window", font=valeur, fill=TEXTE)

    x2 = MARGE + lcarte + ecart
    _carte(d, x2, haut, lcarte, hcarte)
    d.text((x2 + 40, haut + 38), "SCORED ON YESTERDAY ONLY",
           font=etiquette, fill=DISCRET)
    d.text((x2 + 40, haut + 96), "10-day window", font=valeur, fill=TEXTE)

    # Le signe qui porte toute la these.
    ne = _police("Arial Bold.ttf", 72)
    lne = _largeur(d, "≠", ne)
    d.text((MARGE + lcarte + (ecart - lne) // 2, haut + hcarte // 2 - 44),
           "≠", font=ne, fill=ROUGE)

    x3 = x2 + lcarte + ecart
    _carte(d, x3, haut, L - MARGE - x3, hcarte, bord=ROUGE,
           fond=(46, 20, 24))
    d.text((x3 + 40, haut + 38), "THE TWO WINNERS DISAGREE",
           font=etiquette, fill=ROUGE)
    d.text((x3 + 40, haut + 92), "XLK refused", font=verdict, fill=ROUGE)
    d.text((x3 + 40, haut + 148), "every run, on real bars",
           font=etiquette, fill=DISCRET)

    # Ce que la couverture ne cache pas.
    d.text((MARGE, 720),
           "The refusal is the product — not the P&L.",
           font=sous, fill=VERT)
    d.text((MARGE, 786),
           "And the guard's own false-alarm rate, measured and published: 23%.",
           font=etiquette, fill=DISCRET)

    d.line([MARGE, 900, L - MARGE, 900], fill=BORD, width=2)
    d.text((MARGE, 936), "Alpaca AI Trading Agents Hackathon", font=pied,
           fill=DISCRET)
    droite = "github.com/s-papy/hindsight-alpha  ·  paper trading only"
    d.text((L - MARGE - _largeur(d, droite, pied), 936), droite, font=pied,
           fill=DISCRET)
    return img


def _rien_ne_deborde(img: Image.Image, marge: int = 100) -> None:
    """Aucun pixel dessine ne doit toucher les bords.

    MESURE plutot que calcul : on relit l'image et on cherche un pixel
    different du fond dans les bandes de `marge` pixels. Recalculer les
    largeurs de texte reproduirait le raisonnement qui a servi a placer ce
    texte -- et reproduirait donc son erreur. Meme discipline que la
    verification de debordement du tableau de bord, faite dans un navigateur
    et pas dans la feuille de style."""
    px = img.load()
    for x in list(range(marge)) + list(range(img.width - marge, img.width)):
        for y in range(0, img.height, 4):
            if px[x, y] != FOND:
                raise SystemExit("du contenu touche le bord vertical en "
                                 "x=%d, y=%d" % (x, y))
    for y in list(range(marge // 2)) + list(range(img.height - marge // 2,
                                                  img.height)):
        for x in range(0, img.width, 4):
            if px[x, y] != FOND:
                raise SystemExit("du contenu touche le bord horizontal en "
                                 "x=%d, y=%d" % (x, y))


def main() -> None:
    img = construire()
    _rien_ne_deborde(img)
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "cover.png")
    img.save(chemin, "PNG", optimize=True)
    print("ecrit %s (%dx%d, %d octets)"
          % (chemin, img.width, img.height, os.path.getsize(chemin)))


if __name__ == "__main__":
    main()
