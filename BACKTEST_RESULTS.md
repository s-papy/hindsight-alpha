# Backtest results — HV-rank strategy vs real historical bars

*Generated 2026-08-24T16:52:45.054766+00:00. Proxy payoff, not real options P&L — see backtest.py's module docstring for exactly what is and isn't simulated.*

## SPY (657 bars used, buy-and-hold over the period: 60.35%)

| window (days) | trade days | freq | cum. proxy payoff | win rate on trades | avg payoff/trade | max drawdown |
|---|---|---|---|---|---|---|
| 10 | 102/393 | 26.0% | 0.1071 | 45.1% | 0.00105 | -0.0241 |
| 20 | 106/383 | 27.7% | -0.0341 | 32.1% | -0.00032 | -0.0877 |
| 30 | 111/373 | 29.8% | -0.1054 | 23.4% | -0.00095 | -0.1273 |
| 60 | 102/343 | 29.7% | -0.0977 | 29.4% | -0.00096 | -0.1262 |
| 90 | 100/313 | 31.9% | -0.1406 | 26.0% | -0.00141 | -0.1586 |

**hindsight_guard verdict for this symbol:** agrees (no leak) — full-window winner: 10 days, in-sample winner: 10 days.

## QQQ (657 bars used, buy-and-hold over the period: 73.34%)

| window (days) | trade days | freq | cum. proxy payoff | win rate on trades | avg payoff/trade | max drawdown |
|---|---|---|---|---|---|---|
| 10 | 107/393 | 27.2% | 0.1771 | 43.9% | 0.00165 | -0.0473 |
| 20 | 100/383 | 26.1% | -0.0728 | 35.0% | -0.00073 | -0.1085 |
| 30 | 94/373 | 25.2% | -0.073 | 30.9% | -0.00078 | -0.1496 |
| 60 | 82/343 | 23.9% | -0.0842 | 30.5% | -0.00103 | -0.1336 |
| 90 | 101/313 | 32.3% | -0.1384 | 27.7% | -0.00137 | -0.1534 |

**hindsight_guard verdict for this symbol:** agrees (no leak) — full-window winner: 10 days, in-sample winner: 10 days.

## IWM (657 bars used, buy-and-hold over the period: 52.75%)

| window (days) | trade days | freq | cum. proxy payoff | win rate on trades | avg payoff/trade | max drawdown |
|---|---|---|---|---|---|---|
| 10 | 125/393 | 31.8% | 0.209 | 54.4% | 0.00167 | -0.0283 |
| 20 | 120/383 | 31.3% | -0.0234 | 40.0% | -0.0002 | -0.0587 |
| 30 | 100/373 | 26.8% | 0.0025 | 40.0% | 3e-05 | -0.0644 |
| 60 | 126/343 | 36.7% | -0.1877 | 32.5% | -0.00149 | -0.2008 |
| 90 | 120/313 | 38.3% | -0.2633 | 29.2% | -0.00219 | -0.2804 |

**hindsight_guard verdict for this symbol:** agrees (no leak) — full-window winner: 10 days, in-sample winner: 10 days.

---

# 🔴 LECTURE HONNÊTE DU RÉSULTAT (session terminal du 24/08, contre données réelles)

**Trois faits, dans l'ordre où ils comptent.**

## ① L'edge n'existe que sur UNE fenêtre sur cinq

| | SPY | QQQ | IWM |
|---|---|---|---|
| **10 jours** | **+0,1071** | **+0,1771** | **+0,2090** |
| 20 jours | −0,0341 | −0,0728 | −0,0234 |
| 30 jours | −0,1054 | −0,0730 | +0,0025 |
| 60 jours | −0,0977 | −0,0842 | −0,1877 |
| 90 jours | −0,1406 | −0,1384 | −0,2633 |

**Quatre des cinq fenêtres candidates perdent de l'argent, sur les trois symboles.** *La même fenêtre (10) gagne partout — ce qui est cohérent, pas rassurant en soi : c'est aussi la moins retardée des cinq.*

## ② Le gain tient à une poignée de jours

**Test de concentration** *(retirer les meilleurs jours du total, sans rien retoucher)* :

| | total | −top1 | −top3 | −top5 | n trades |
|---|---|---|---|---|---|
| SPY | 0,1070 | 0,0834 | 0,0454 | **0,0177** | 102 |
| QQQ | 0,1767 | 0,1351 | 0,0727 | **0,0402** | 107 |
| IWM | 0,2088 | 0,1815 | 0,1369 | **0,0989** | 125 |

> ### **83 % du gain de SPY vient de 5 jours sur 102. 77 % pour QQQ. 53 % pour IWM.**

⚠️ **Ce n'est PAS automatiquement disqualifiant** — acheter de l'optionalité *est* une stratégie à queue longue : on perd un peu souvent et on gagne beaucoup rarement. La concentration est la **signature attendue** du payoff, pas une anomalie. **Mais elle veut dire que sur ~110 trades, l'intervalle de confiance est très large : ce résultat ne distingue pas un edge d'une chance.**

## ③ Le taux de succès est sous 50 % là où l'edge existe

SPY **45,1 %**, QQQ **43,9 %**, IWM **54,4 %**. *Cohérent avec ①+② : la majorité des trades perd.*

## Ce que ce backtest ne dit PAS, et qu'il faut redire à chaque citation

🔴 **Le payoff est un PROXY** — `abs(rendement du lendemain) − coût`, pas une simulation de prime d'option. **Il ignore le spread bid-ask et le theta**, c'est-à-dire précisément les deux coûts qui frappent **chaque** jour de détention, y compris les ~70 % de trades perdants. **Un coût réel plus élevé mangerait d'abord les petits gains, donc exactement ce qui reste après avoir retiré les 5 meilleurs jours.**

🟢 **`hindsight_guard` est propre sur les trois symboles** — la fenêtre gagnante sur tout l'historique gagne aussi en n'utilisant que l'information antérieure. **Aucune fuite dans la sélection de fenêtre.** *C'est ce que le garde-fou promet, et rien de plus : il ne dit pas que l'edge est réel, il dit que le choix de la fenêtre n'a pas triché.*

## Verdict

> **🟠 Edge présent mais fragile, et non prouvé.** *Positif sur la seule fenêtre de 10 jours, sur les trois symboles, sans fuite de sélection — mais porté par une poignée de jours, mesuré avec un payoff qui omet les coûts les plus punitifs, sur un échantillon d'environ 110 trades par symbole.*

**Aucun seuil n'a été retouché après avoir vu ces chiffres.** *`CHEAP_VOL_PERCENTILE`, `CANDIDATE_HV_WINDOWS`, `RANK_LOOKBACK_DAYS` et `COST_MULTIPLIER` sont exactement ceux d'avant le backtest — le projet existe pour attraper ce biais-là, il aurait été absurde de le commettre ici.*
