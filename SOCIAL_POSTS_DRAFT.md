# Brouillons de posts X/LinkedIn — Hindsight Alpha

*Créé 25/08 sur demande explicite de Spap, après avoir trouvé sur la page officielle du hackathon que "Social engagement" est un des 5 CRITÈRES DE JUGEMENT du classement principal (P&L Performance, Technology Implementation, Creativity & Originality, Presentation & Execution, Social engagement) — pas seulement le prix bonus séparé à $500/équipe ("Build in Public"). `PLAN_SPRINT.md` le traitait jusqu'ici comme "piste bonus" — sous-estimé.*

**Règles du hackathon à respecter à chaque post** : tagger `@lablabai` et `@AlpacaHQ` sur X, `lablab.ai` et `Alpaca` sur LinkedIn. Jusqu'à 5 liens de posts dans la soumission finale — donc 5 posts bien choisis valent mieux que 15 posts creux. Montrer le raisonnement et les revers, pas juste le résultat final (c'est littéralement ce que les critères demandent : "Share your process, your reasoning, and your setbacks").

**Comment utiliser ce fichier** : chaque post ci-dessous est un brouillon, pas un texte final — à relire, personnaliser, et poster toi-même (je ne poste jamais à ta place). Les `[...]` sont des chiffres réels à remplir une fois que la semaine aura commencé, pas des estimations. Poster tôt dans la journée où l'événement se produit, pas après coup.

---

## Post 1 — Jour du kickoff (28/08), à poster après avoir commencé à builder

**X (280 car. max) :**
> Built an options-trading agent that refuses to trust its own backtest. Before every trade it asks: would this same parameter still win if I'd only known what was knowable at the time? If the answer is no, it skips the trade and says why. Building live for @AlpacaHQ x @lablabai's hackathon 🦙
>
> github.com/s-papy/hindsight-alpha

**LinkedIn (plus long, contexte) :**
> Starting the Alpaca AI Trading Agents Hackathon (lablab.ai x Alpaca) with a question that bugs most backtested strategies: if you sweep parameters and pick the best-scoring one, how do you know the winner isn't just an artifact of a scoring window that secretly included data you wouldn't have had at decision time?
>
> Hindsight Alpha is an options-trading agent built around answering that question honestly, every single day, before it trades anything: it re-scores every candidate volatility window twice — once on the full history, once on only what was actually knowable in-sample — and if the two disagree, it refuses to trade and logs why. That refusal is the product, not a fallback.
>
> Building in public this week. Repo, dashboard, and reasoning all public: github.com/s-papy/hindsight-alpha
>
> #AlpacaHackathon @Alpaca @lablab.ai

---

## Post 2 — Milieu de semaine (~31/08 ou 1/09), un vrai refus ou une vraie découverte

*À choisir selon ce qui arrive vraiment cette semaine-là — deux versions selon le scénario.*

**Si `hindsight_guard` refuse un trade pour de vrai (très probable — XLK échouait déjà en backtest) :**

**X :**
> Today the guard did its job: [SYMBOL] looked tradeable on the full history, but the in-sample check disagreed — so the agent refused to trade it, logged why, and moved on. A strategy that never says no isn't being tested, it's being trusted blindly.
>
> Dashboard: s-papy.github.io/hindsight-alpha
> @AlpacaHQ @lablabai

**Si un vrai trade se déclenche :**

**X :**
> First real trade of the week: [SYMBOL] [call/put], sized at [X]% of equity under a hard 1%-per-trade / 3%-total cap. The volatility regime cleared the bar, the leak check agreed on both windows, risk gates approved the size. Full reasoning on the dashboard.
>
> s-papy.github.io/hindsight-alpha
> @AlpacaHQ @lablabai

---

## Post 3 — Milieu/fin de semaine (~2-3/09), un revers assumé

*Le critère demande explicitement "your setbacks" — pas juste les victoires. Choisir un vraiincident de la semaine (un bug trouvé, un trade perdant, un refus qui a coûté une opportunité) plutôt que d'en inventer un a posteriori.*

**X :**
> Setback, logged honestly: [ex: a stop-loss fired on SYMBOL at -50%, exactly as designed — the risk gate did its job, the trade still lost money]. The point of this build was never "never lose" — it's "never lose to something the agent should have caught." Full trace in decision_log.jsonl, nothing hidden after the fact.
>
> @AlpacaHQ @lablabai

---

## Post 4 — Avant-dernier jour (~3/09), zoom technique

**X :**
> Under the hood: Alpaca CLI (not the SDK) — chose it deliberately to match Alpaca's own guidance (CLI for scheduled/cron agents, MCP for interactive AI-host sessions), and because a scheduled agent that runs once a day + a standalone exit-monitor every 15 min is exactly the CLI's use case, not a persistent session.
>
> github.com/s-papy/hindsight-alpha
> @AlpacaHQ @lablabai

**LinkedIn (angle "found bugs by testing, not luck") :**
> A few of the things this build caught before they became real losses, because they were tested rather than assumed:
> — An unbounded options-strike lookup that would have silently refused every trade forever (the first page of results didn't even contain the current price).
> — A state-file corruption path that could have silently cleared an active loss lock.
> — A missing per-position exception isolation that could have left a real losing position unmanaged because an unrelated position's close failed.
>
> All three are documented with their reproduction test in the public commit history — not smoothed over after the fact. That's the actual engineering story of this hackathon: not "it works", but "here's exactly how I know it works, and what I found when I checked."
>
> #AlpacaHackathon @Alpaca @lablab.ai

---

## Post 5 — Dernier jour (4/09), bilan honnête avant la deadline

**X :**
> Wrapping up the Alpaca AI Trading Agents Hackathon. Final numbers, real account, nothing cherry-picked: [P&L réel] over [N] trades, [N] refusals logged with reasons. hindsight_guard caught [N] real leak(s) this week. Dashboard + full decision log are public.
>
> s-papy.github.io/hindsight-alpha
> @AlpacaHQ @lablabai

**LinkedIn (clôture, plus long) :**
> Wrapping the Alpaca AI Trading Agents Hackathon (lablab.ai x Alpaca). The thesis going in: an agent that refuses to trust its own backtest is worth more than one that always has an answer. Here's what actually happened this week, honestly reported — [insérer 2-3 phrases sur le vrai résultat, y compris les refus].
>
> Everything is public: the code, the risk gates, every decision the agent made and why (including every refusal), and the dashboard tracking the real paper account live.
>
> Repo: github.com/s-papy/hindsight-alpha
> Dashboard: s-papy.github.io/hindsight-alpha
>
> #AlpacaHackathon @Alpaca @lablab.ai

---

## Note sur le rythme

5 posts espacés sur 7 jours (28/08 → 4/09), pas tous le même jour — les critères mentionnent explicitement l'engagement généré (likes, commentaires, partages), qui a besoin de temps entre les posts pour respirer. Éviter de tout poster le dernier jour : ça ressemblerait à une case cochée après coup plutôt qu'à un vrai "build in public".
