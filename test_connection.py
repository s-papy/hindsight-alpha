"""Run this FIRST, before agent.py. Confirms the `alpaca` CLI is installed,
your .env credentials work, and this machine can actually reach Alpaca's
paper API (the Cowork sandbox cannot — this is why it needs to run in a
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

    if config.ACCOUNT_ID and account.get("id") != config.ACCOUNT_ID:
        print(
            f"\nWARNING: ALPACA_ACCOUNT_ID in .env ({config.ACCOUNT_ID}) does not match "
            f"the account these keys authenticate as ({account.get('id')}). Double-check "
            "you're pointed at the right account before the real hackathon run."
        )

    print("\nAll good — you can now run: python agent.py --dry-run")


if __name__ == "__main__":
    main()
