# flight-hotel-search

**English** · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md)

[![tests](https://github.com/HungHsunLin/flight-hotel-search/actions/workflows/tests.yml/badge.svg)](https://github.com/HungHsunLin/flight-hotel-search/actions/workflows/tests.yml)

Live airfare and hotel rates from Google Flights / Google Hotels, as a
[Claude Code](https://claude.com/claude-code) skill — with plain CLI scripts you can also run on
their own.

**The core insight:** Google server-side renders the first screen of results into the HTML, so most
queries need nothing more than `curl` — roughly 20x faster than driving a browser. Only the
"who is actually selling this fare" layer is loaded dynamically and needs a real browser.

Supports **Traditional Chinese, English and Japanese** interfaces with independent currency
selection.

## Requirements

`bash`, `curl`, `python3`. No third-party packages, no API keys, no build step.

Verified in CI on Linux with Python 3.9, 3.11, 3.13 and 3.14, and on macOS with 3.14. The code uses
no version-specific syntax, and the shell scripts avoid `date` flags that differ between GNU and BSD
(the CI run asserts the past-date guard actually fires on each platform, rather than being silently
skipped).

## Quick start

```bash
# The default locale is zh-TW (see "Languages and currency"), so set this first
# or the output comes back in Chinese with TWD prices.
export GFH_LANG=en

# Round trip, city names cover every airport in the metro area
scripts/gflight.sh Taipei Tokyo 2026-10-01 2026-10-05

# One way (omit the return date)
scripts/gflight.sh TPE KIX 2026-11-15

# Hotels: place, check-in, check-out, adults
scripts/ghotel.sh Kanazawa 2026-11-24 2026-11-26 2

# Which date is cheapest across a range
python3 scripts/gscan.py flight TPE TYO 2026-10-01 2026-10-31 --nights 4
python3 scripts/gscan.py hotel Kanazawa 2026-11-20 2026-11-30 --nights 2

# Round trips on full-service carriers only (see "Gotchas" for why this needs its own script)
python3 scripts/gnolcc.py Taipei Osaka 2026-03-15 2026-03-20
```

### Booking sources (official site vs. OTA)

Identifying *who* is selling a given fare is the one layer that is **not** server-rendered, so it
needs real browser automation rather than `curl`. That workflow lives in
[`references/booking-sources.md`](references/booking-sources.md) and is written for the Claude Code
skill (it drives a browser via MCP). If you are only using the CLI scripts, you will not need it.

## Languages and currency

Everything is driven by environment variables. Defaults are `zh-TW` / `TWD` / `tw`.

| Variable | Default | Notes |
|---|---|---|
| `GFH_LANG` | `zh-TW` | `zh-TW`, `en`, `ja` |
| `GFH_CURR` | follows language | Independent of language — see below |
| `GFH_REGION` | follows language | Google's `gl` parameter |
| `GFH_UA` | a normal browser string | Set to use your own identifier |

```bash
GFH_LANG=en scripts/gflight.sh Taipei Tokyo 2026-10-01 2026-10-05
GFH_LANG=ja scripts/ghotel.sh 金沢 2026-11-24 2026-11-26 2

# Language and currency are independent: Chinese UI, prices in yen
GFH_LANG=zh-TW GFH_CURR=JPY scripts/ghotel.sh 京都 2026-11-24 2026-11-26 2
```

Querying Japanese hotels with `GFH_LANG=ja` generally surfaces more local operators and more
complete property names than the English interface.

## How it works

Google writes the result data into `aria-label` attributes as **natural-language sentences**, and
the word order differs completely per language:

```
zh-TW  來回總價 <price> 新台幣起。 搭乘<airline>的直達航班。 … 於<airport>出發，…
en     From <price> US dollars round trip total. Nonstop flight with <airline>. Leaves <airport> …
ja     往復の合計金額 <price> 円～。 <airline> が運航する直行便。 … <airport>発、…
```

Hotels are worse — the price and the name swap places:

```
zh-TW  <hotel>，價格 $<price> 起                 <- name first
en     Prices starting from $<price>, <hotel>     <- price first
ja     <hotel>、NT$<price>～                       <- name first
```

So there is no single universal regex. `scripts/locales.py` holds one pattern set per language,
using named capture groups (`name`, `price`, `dep`, `arr`, …) so the parsers stay language-agnostic.

## Gotchas

These are the things that produce **wrong numbers without any error**, which is far more dangerous
than a crash. All of them were found by actually diffing responses, not by reading docs.

**Google silently ignores parameters it does not recognise.** It never returns a 400 — it quietly
computes a result with default values. Any time you build query parameters by hand, run a control
test: change an input that *should* produce an obviously different result (New Year's Eve vs. a
random Tuesday). If the output does not move, your parameter is not taking effect.

**Hotel dates and currency live inside the `ts=` protobuf, not in URL parameters.** Writing
`?checkin=2026-12-30&checkout=2027-01-03` returns a perfectly normal-looking page for *tomorrow
night*. Likewise `curr=USD` is ignored for hotels — the currency field inside `ts` wins. Measured:
the same property showed 1,348 with fake dates vs. 4,207 for a real 4-night New Year stay, a
3.1x difference. `scripts/gtsgen.py` builds `ts` correctly; go through the scripts and you are fine.

**Occupancy is encoded as a repeated field, not a number.** One adult is one `{1:{1:3}}` group; two
adults means repeating it twice. Putting the count in a numeric field is silently ignored and you
always get the 2-person rate. Single-occupancy rates are typically 20-30% cheaper.

**"Round trip from X" only names the outbound carrier.** The price is a floor computed by pairing
the cheapest available return, which is often a budget airline. Filtering the result list by airline
therefore only filters the outbound leg. `gnolcc.py` exists for this: it pushes the airline name
into the query string, where Google applies it to **both** legs. Measured TPE-KIX: the listing showed
one full-service carrier at 11,711, which was really that carrier outbound + a budget airline
back; a genuine both-legs round trip was 13,819.

**Airline names must match the current interface language.** `China Airlines` returns zero results
under `hl=zh-TW`; `中華航空` returns zero under `hl=en`. `locales.py` carries the right list per
language, and only one airline can be filtered at a time.

**Hotel results carry both the nightly rate and the stay total** (taxes and fees included, with
the total read from the page rather than multiplied out), and the scanner ranks dates by the **median**
nightly rate rather than the minimum — the cheapest listing is usually a hostel or capsule, so a
single cheap bed makes a genuinely expensive date look like a bargain.

**Google is not the whole market.** It lists partners. Budget-carrier flash sales on their own sites
and many regional OTAs never appear. "Cheapest on Google" is not "cheapest available".

**Only the first screen is server-rendered** — about 20-24 flights and 18-20 hotels. That is plenty
for price discovery, but it is not an exhaustive list.

**There is a booking horizon at roughly 330 days**, and hotels cross it dangerously. Flights past it
return nothing; hotels return a normal-looking page of **one-night** rates instead of the range you
asked for. `ghotel.sh` reconciles the nights the page reports against the nights requested and warns
above the table, and queries more than 300 days out print an advisory.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

35 tests, no network access, no third-party test runner. They run against **synthetic fixtures** in
`tests/fixtures.py` — invented airlines, hotels and prices (`Example Air`, `範例航空`, …). Only the
airport names are real, because that is what the lookup table is being tested against, and place
names are facts.

Two consequences worth understanding:

- The suite verifies **that our regexes behave as designed**, not that Google's output still matches
  them. If Google rewrites its labels, these tests stay green while live queries return nothing. So
  when you change a pattern in `locales.py`, verify it against a real page as well.
- No page content from the source site is stored in this repository. Checking in a real HTML capture
  as a fixture would be the easy path, but it means committing someone else's page into version
  control.

Most cases correspond to a bug that actually occurred; each says so in its name or comment. The
suite has been verified by mutation testing — reintroducing four historical bugs (the swallowed
`DEAL` suffix, a too-small label cap, dropping the currency from `ts`, and removing the CJK width
calculation) turns it red each time.

CI runs the suite on every push and pull request across Linux and macOS — see
[`.github/workflows/tests.yml`](.github/workflows/tests.yml). It performs **no live queries**:
sending automated requests from shared CI runners is a different proposition from a person running
the CLI locally, and those runners get throttled quickly, which would make the tests flaky. The
trade-off is that CI stays green when the source site changes its output format; only real use
catches that.

## Adding a language

1. Copy an entry in `LOCALES` in `scripts/locales.py`.
2. **Actually fetch a page in that language** and diff the real `aria-label` strings against your
   patterns. Do not write them from grammar intuition.
3. Confirm the parser returns a non-zero row count. Google does not report parse failures — you
   just get an empty list, which is indistinguishable from a typo'd place name or throttling.

Two things to watch when adding a language. English labels are far longer than CJK ones (measured on
nonstop flights: 233-277 characters for English vs. 108-131 for Chinese), so the extraction length
cap has to be set per language — a cap that is too small silently drops the tail of the sentence
(arrival time, total duration) with no error at all. And English spells the currency out
(`From <price> US dollars`) instead of using a symbol, so matching on `$` finds nothing.

## Using it as a Claude Code skill

The repository doubles as a [Claude Code](https://claude.com/claude-code) skill. Drop the directory
into `~/.claude/skills/` and the CLI picks it up.

| File | Purpose |
|---|---|
| `SKILL.md` | The skill definition Claude Code loads. Written in Traditional Chinese. |
| `SKILL.en.md` | English equivalent. **To use it, swap the two filenames** — Claude Code only reads `SKILL.md`. |
| `evals/evals.json` | Trigger and behaviour evaluations for the skill, in the format used by Claude Code's `skill-creator`. Not a unit-test suite, and not needed to use the CLI scripts — the prompts are in Chinese and assume a Taiwan travel context. |
| `references/local.md` | **Optional, not in version control.** If you create this file, `SKILL.md` instructs Claude to read it. Use it for machine-specific wiring — which of *your* other skills handles writing results into trip documents, your own file conventions, and anything else that should not be baked into a public repository. |

The skill definition is deliberately generic about what it hands off to: it says results should be
passed to "whichever skill manages those documents" rather than naming one. Keeping the specifics in
an ignored `references/local.md` lets the published skill stay portable while your own setup stays
private.

The CLI scripts work standalone and need none of the above.

## Support and maintenance

Maintained on a best-effort basis, with no guarantee of support or response time.

Be aware of what this project depends on: the parsers read Google's rendered output, so **a wording
or markup change on their side breaks them, and the failure is silent** — queries return an empty
list rather than an error. That is a question of when, not if. If results suddenly go empty, compare
`locales.py` against a freshly fetched page before assuming throttling.

Bug reports with a reproducible query are welcome. Pull requests adding a language are welcome if
they follow the process in "Adding a language" — in particular, patterns must be verified against a
real page, and no captured page content may be committed.

## Legal

This tool is for **personal research and educational use**. It reads publicly accessible pages and
extracts factual data (prices, times, ratings); it does not cache, resell, or redistribute anything.

You are responsible for ensuring your use complies with the terms of service of any site you query
and with the laws of your jurisdiction. Google's Terms of Service prohibit automated access to their
services. The author provides this software as-is and accepts no liability for how it is used.

Please do not deploy this as a public, hosted API or scraping service. Running a CLI for yourself
and operating a commercial scraping endpoint are very different things, legally and ethically.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
