"""Run this FIRST, before agent.py. Confirms the `alpaca` CLI is installed,
your .env credentials work, and this machine can actually reach Alpaca's
paper API (a sandboxed environment without outbound access cannot — this is
why it needs to run in a
real terminal).

Run: python test_connection.py
"""

from __future__ import annotations

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
    actual_account_number = account.get("account_number")
    if config.ACCOUNT_ID and actual_account_number and actual_account_number != config.ACCOUNT_ID:
        print(
            f"\nWARNING: ALPACA_ACCOUNT_ID in .env ({config.ACCOUNT_ID}) does not match "
            f"the account these keys authenticate as ({actual_account_number}). Double-check "
            "you're pointed at the right account before the real hackathon run."
        )
    elif config.ACCOUNT_ID and not actual_account_number:
        print(
            "\nNOTE: could not read account_number from this account to verify against "
            f"ALPACA_ACCOUNT_ID ({config.ACCOUNT_ID}) -- CLI may name this field differently. "
            f"Full account id was: {account.get('id')}. Not a hard failure, just unverified."
        )

    print("\nAll good — you can now run: python agent.py --dry-run")


if __name__ == "__main__":
    main()
