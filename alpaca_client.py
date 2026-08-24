"""Thin wrapper around alpaca-py for the two things this agent needs:
historical daily bars (to score the momentum lookback sweep) and options
contract lookup + paper order submission (to act on a vetted signal).

Everything here talks to Alpaca's PAPER endpoint only (enforced in
config.require_credentials()). No real money at risk.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

import config
from vol_strategy import Bar

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest, MarketOrderRequest
from alpaca.trading.enums import AssetStatus, ContractType, OrderSide, TimeInForce
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


def trading_client() -> TradingClient:
    return TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)


def data_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(config.API_KEY, config.SECRET_KEY)


def get_daily_bars(symbol: str, lookback_days: int = 250) -> List[Bar]:
    """Fetch ~lookback_days of daily bars for `symbol`. Calendar days are
    padded (weekends/holidays) since only trading days come back."""
    client = data_client()
    start = datetime.utcnow() - timedelta(days=int(lookback_days * 1.6) + 10)
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
    )
    bars = client.get_stock_bars(req)
    rows = bars[symbol] if hasattr(bars, "__getitem__") else bars.data[symbol]
    return [Bar(close=float(row.close)) for row in rows]


def get_last_price(symbol: str) -> float:
    bars = get_daily_bars(symbol, lookback_days=5)
    if not bars:
        raise RuntimeError(f"no recent bars for {symbol}")
    return bars[-1].close


def find_near_the_money_contract(
    underlying: str,
    direction: int,
    min_days_out: int = 7,
    max_days_out: int = 21,
) -> Optional[str]:
    """direction=+1 -> call, direction=-1 -> put. Returns the option symbol
    for the contract whose strike is closest to the current underlying
    price, expiring between min_days_out and max_days_out from today."""
    client = trading_client()
    spot = get_last_price(underlying)
    contract_type = ContractType.CALL if direction > 0 else ContractType.PUT

    today = datetime.utcnow().date()
    req = GetOptionContractsRequest(
        underlying_symbols=[underlying],
        status=AssetStatus.ACTIVE,
        type=contract_type,
        expiration_date_gte=today + timedelta(days=min_days_out),
        expiration_date_lte=today + timedelta(days=max_days_out),
    )
    resp = client.get_option_contracts(req)
    contracts = resp.option_contracts if hasattr(resp, "option_contracts") else resp

    if not contracts:
        return None

    closest = min(contracts, key=lambda c: abs(float(c.strike_price) - spot))
    return closest.symbol


def submit_paper_option_order(option_symbol: str, qty: int = 1) -> str:
    client = trading_client()
    order = MarketOrderRequest(
        symbol=option_symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    result = client.submit_order(order_data=order)
    return result.id
