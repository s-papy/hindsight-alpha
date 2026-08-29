# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

"""Run this FIRST, before agent.py. Confirms the `alpaca` CLI is installed,
your .env credentials work, and this machine can actually reach Alpaca's
paper API (a sandboxed environment without outbound access cannot — this is
why it needs to run in a
real terminal).

Run: python test_connection.py
"""

from __future__ import annotations

import sys

import alpaca_cli
import config


def main() -> None:
    config.require_credentials()
    print("Checking `alpaca` CLI is installed...")
    print(f"Connecting via CLI (paper mode: {config.PAPER})...")
    account = alpaca_cli.get_account()

    print("Connected. Account summary:")
    for key in ("id", "status", "buying_power", "cash", "portfolio_value", "pattern_day_trader"):
        if key in account:
            print(f"  {key}: {account[key]}")

    # Alpaca returns two different identifiers for the same account: `id`
    # (an internal UUID) and `account_number` (the human-visible "PA..."
    # number shown on the dashboard's account switcher -- exactly what
    # .env.example tells you to paste here, and what .env.hackathon already
    # holds). Comparing ALPACA_ACCOUNT_ID against `id` would
    # compare a "PA..." string against a UUID -- never equal by construction,
    # so this check would print a false "mismatch" warning on every single
    # correctly-configured run. Compare against account_number instead (see
    # engineering log, 24/08 pass -- the same id/account_number confusion was
    # just found and fixed in publish_dashboard.py's dashboard display).
    # REECRIT le 27/08/2026, la veille du kickoff. Ce script est l'outil qu'on
    # lance pour CONFIRMER une bascule de compte, et il repondait mal aux deux
    # seules questions qui comptent ce jour-la. Mesure :
    #
    #   compte declare = compte reel  -> avertit=non   « All good »=OUI  (juste)
    #   MAUVAIS compte                -> avertit=OUI   « All good »=OUI  (faux)
    #   identifiant non declare       -> avertit=non   « All good »=OUI  (faux)
    #
    # Le deuxieme cas affichait l'avertissement PUIS « All good -- you can now
    # run: python agent.py ». Un operateur presse lit la derniere ligne.
    #
    # Le troisieme est pire : sans identifiant de compte declare, la
    # verification entiere etait SAUTEE et le script annoncait quand meme que
    # tout allait bien. C'est le motif poursuivi partout ailleurs dans ce
    # depot : un controle qui ne peut pas conclure et qui parle comme s'il
    # avait conclu.
    actual_account_number = account.get("account_number")
    if not config.ACCOUNT_ID:
        verdict, detail = "NON VERIFIE", (
            "no declared account identifier, so nothing was compared. The "
            "connection works, but WHICH account these keys open is unchecked.")
    elif not actual_account_number:
        verdict, detail = "NON VERIFIE", (
            "the account response carried no account_number, so the declared "
            "identifier (%s) could not be compared against anything. The CLI "
            "may name this field differently." % config.ACCOUNT_ID)
    elif actual_account_number != config.ACCOUNT_ID:
        verdict, detail = "MAUVAIS COMPTE", (
            "the declared identifier is %s, but these keys authenticate as %s."
            % (config.ACCOUNT_ID, actual_account_number))
    else:
        verdict, detail = "OK", ""

    if verdict == "MAUVAIS COMPTE":
        # Le VERDICT est imprime, pas seulement le detail. Corrige le
        # 28/08/2026 a 20h35, une heure avant le premier passage de l'agent,
        # sur un vrai mauvais compte.
        #
        # verifier_le_kickoff.py cherche la chaine « MAUVAIS COMPTE » dans la
        # sortie de ce script. Elle n'y etait JAMAIS : elle vivait seulement
        # dans la variable `verdict`, et ce qu'on imprimait etait
        # « STOP: the declared identifier is ... ». Mesure : zero occurrence
        # de « MAUVAIS COMPTE » dans un print de ce fichier.
        #
        # Consequence constatee en vrai : l'etat le PLUS dangereux -- les cles
        # ouvrent un compte qui n'est pas celui declare -- s'affichait
        # « 🟡 compte Alpaca : non verifie » au lieu de « 🔴 ne lance pas
        # agent.py ». Le pire cas se lisait comme une simple incertitude.
        #
        # Meme famille que le defaut de coherence.py corrige cet apres-midi :
        # deux fichiers couples par un TEXTE, et le texte a derive.
        print("\nSTOP -- MAUVAIS COMPTE: %s" % detail)
        print("Do NOT run agent.py: it would trade the wrong account. If you "
              "just switched accounts, the switch did NOT take effect -- see "
              "the precedence warning config.py prints when a stale value is "
              "still exported in the shell.")
        sys.exit(1)

    if verdict == "NON VERIFIE":
        print("\nCONNECTED, BUT THE ACCOUNT IDENTITY IS NOT VERIFIED: %s" % detail)
        print("Nothing is wrong that this script can see -- but it did not "
              "check the one thing it exists to check. Do not read this as "
              "confirmation that you are on the right account.")
        return

    print("\nAll good - account %s confirmed. You can now run: "
          "python agent.py --dry-run" % actual_account_number)


if __name__ == "__main__":
    try:
        main()
    except alpaca_cli.AlpacaCLIError as echec:
        # AJOUTE le 29/08/2026. Ce script est le premier que le README dit de
        # lancer, et le seul que `verifier_le_kickoff.py` interroge pour le
        # compte. Une panne de reseau ou de certificat le faisait finir sur
        # une TRACE PYTHON brute -- 12 lignes de pile avant le message utile,
        # dans le seul outil que quelqu'un lance justement parce que quelque
        # chose ne va pas.
        #
        # LE POINT QUI COMPTE : ce message ne dit PAS « mauvais compte ». Une
        # panne de connexion n'est pas un verdict sur l'identite du compte, et
        # `verifier_le_kickoff.py` cherche la chaine « MAUVAIS COMPTE » dans
        # cette sortie -- l'ecrire ici transformerait une coupure reseau en
        # accusation. Il ne dit pas non plus que tout va bien : il dit qu'il
        # n'a pas pu regarder.
        #
        # Le code de sortie reste 1, le contrat dont depend l'appelant : il le
        # traite comme une anomalie BLOQUANTE, sans essayer de la nommer.
        print("\nCOULD NOT REACH ALPACA: %s" % echec, file=sys.stderr)
        print("\nThis says nothing about which account you are on -- the "
              "check never got that far. It is a connection, credential or "
              "CLI problem, not an account verdict. Try `alpaca doctor`, then "
              "run this script again.", file=sys.stderr)
        sys.exit(1)
