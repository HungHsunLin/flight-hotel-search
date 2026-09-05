# Changelog

Dated entries rather than version numbers: this is a skill you copy into
`~/.claude/skills/`, not a package you install at a pinned version, so "which day did
I take my copy" is the question a reader actually has.

English only, deliberately. The READMEs are translated three ways and a test keeps
them structurally aligned; a changelog does not earn that maintenance cost, and a
stale translation of a correction is worse than no translation.

**Read the Corrected sections first.** Several statements in this repo were measured
and found to be false. If you copied the skill before the date on the entry, those
statements are still in your `SKILL.md`, and the model reads them as evidence.

---

## 2026-09-05

Triggered by a full field session (2027 Japan ski trip comparison, ~200 queries) whose
output contained two wrong conclusions that shipped to the user before being caught.

### Fixed (behaviour)

- **Flights with no fare are no longer silently discarded without a trace.** `gfparse.py`
  dropped every row whose aria-label lacked a price, on the assumption that "no price means
  it is not a flight row". That assumption is false: Google simply omits fares on some
  segments, and **an entire airline could disappear from the output**. Measured Tokyo to
  Sapporo: 38 ANA rows present in the page, zero in the parsed result; filtering the query
  to ANA dropped all 62 rows and printed "(no data)" with four listed causes, none of which
  was the real one. `parse()` now accepts a `dropped` dict and `render()` prints the tally
  **above** the table (and on zero-row results, where it matters most).
- **Truncation is now stated.** `render(limit=12)` printed 12 rows while the footer said
  "N results". Because rows sort by price and nonstops are pricier, nonstops were
  systematically pushed past the cutoff — the field session counted "2 nonstops" from a
  table where the full set had 32. The footer now says how many were hidden and why not to
  count from the table.
- **`gflight.sh` can now raise the limit** via `GFH_TOP`; `gfparse.py` accepts `--top`.
- **`ghparse.py` warns when the sample is too small** (under 10 rows) — a 4-row median was
  nearly used as a regional rate, which would have shifted a total by NT$50,000+.
- **`gnolcc.py --eu`** switches to a Gulf-hub + European full-service list. The default list
  is Asia-only, so "exclude LCCs" was effectively unusable on Europe/US routes: the cheapest
  Taipei-Zurich fare was Etihad, followed by Emirates, Turkish, SWISS and Lufthansa — none
  of them on the list.

### Corrected

- **"Flights return roughly 20-24 rows" was wrong**, and wrong in a way readers would act
  on. Actual parsed counts: Taipei-Tokyo full-service 48-53, Tokyo-Sapporo 51,
  Taipei-Sapporo full-service 26-29, Taipei-Geneva 2. Printed rows: always 12. Neither
  number matched the documented one.
- **"Re-run the same query 2-3 times" is necessary but not sufficient.** It catches random
  failures (the ~18% empty response) and cannot catch systematic ones, which fail
  identically every time — both the ANA case and the `二世谷` case survived repeated runs.
  Added: after a re-run passes, ask whether the result defies common sense.
- **There is no HTTP caching here** (`cache-control: no-cache, no-store`; three fetches gave
  three different md5s). Identical repeat results come from stable fares, not a cache. This
  corrects a plausible-sounding assumption rather than a previous claim in this file.
- **`gnolcc.py`'s docstring advertised `# 單程` (one-way)**, directly contradicting
  SKILL.md's measured finding that omitting the return date still prices a round trip.
  Following the docstring would sum two round-trip fares to fake an open-jaw.

### Added (traps)

- **Long-haul first screens are unusable, off by 2-4x.** Taipei-Warsaw via curl: 2 rows from
  NT$59,213 (29h); in a browser: 12 rows from NT$28,019 (18h). Taipei-Stockholm: NT$110,374
  vs NT$27,310. Fingerprint: every row shares one carrier and one departure time, with a
  duration far above the route norm. Use a browser for these routes.
- **Local place names can return nothing or the wrong city.** `二世谷` returns 0 hotels
  (Google's Chinese is `新雪谷`); `華沙` returns hotels in Shanghai (use `Warsaw`). Hotel
  queries have no title diagnostic, so re-running is the wrong second step — change the
  spelling instead.
- **Room type is unlabelled and skews the median both ways.** The existing capsule-hotel
  note covered the cheap direction; European ski villages are the expensive one (Ischgl
  median NT$43,327 against Innsbruck's NT$3,962 the same week) because whole chalets are
  priced into a solo search.
- **Single-query hotel medians can swing far more than the 5% quoted elsewhere** — Krakow
  gave 956 / 1,987 / 1,315 on identical dates, making month-to-month ranking meaningless
  without 3 runs.

### Notes

- `ghparse.py` has no `limit` and never truncated; the flights lesson does not transfer.
- The zsh `set -- $var` warning moved to the top of the Date scanning section. A fourth
  session hit it, having correctly used a script file earlier in the same session and then
  switched to a one-liner — knowing the rule is not enough to avoid it.

---

## 2026-09-02

### Corrected

- **"Plain city names work fine and are usually safer than hunting for airport
  codes."** Understated the risk badly. Both spellings can fail, and the failure is
  silent. Measured Taipei→Kumamoto: `熊本` resolves to Kumamoto *Prefecture*, which
  Flights cannot search, and returns zero rows; `熊本市` and `KMJ` both return 6. The
  deciding factor is whether the whole natural-language sentence parses, not which
  spelling you picked — all four endpoint combinations (`TPE`/`臺北市` ×
  `KMJ`/`熊本市`) returned 6 rows on their own.

- **"`China Airlines` returns zero results under `hl=zh-TW`; the Chinese name is
  required."** Marked "verified" in earlier copies. It is false: Taipei→Kumamoto with
  `China Airlines` returned 5/5/5/0 rows across four runs under `hl=zh-TW`, and
  `Starlux` worked too. Matching the interface language remains the safer habit, but
  it is not a hard rule. The lone zero was the intermittent empty response below —
  which is almost certainly how the claim got written in the first place.

- **"Re-run a query known to work to tell throttling apart."** Cannot tell them apart.
  The same query re-run is not deterministic: `TPE KMJ 中華航空` returned zero rows on
  2 of 11 runs (~18%), while a differently-worded control query passed during those
  failures. The rule is now to re-run **the same query** 2-3 times before concluding
  anything is absent.

- **"`gflight.sh A B departure` (omit return) = one-way."** It is not. Taipei→Kumamoto
  one-way 9/12 and round-trip 9/12-9/16 both returned 6 rows with the same NT$9,272
  minimum; Google supplies a default return and prices a round trip either way. Anyone
  building an open-jaw itinerary from two such queries is adding two round-trip fares.
  The tool cannot price one-way or open-jaw at all, and now says so.

### Added

- **Zero rows now come with a diagnosis.** The page `<title>` states what Google
  resolved the query to, and it distinguishes all three outcomes: a resolved route, a
  route resolved to an administrative region (title ends in the Explore page rather
  than Flights), and a query that never parsed (the generic home-page title). On zero
  rows the parser prints it verbatim. It is deliberately not decomposed into
  origin/destination — parsing that would hard-code locale structure, while printing
  the title as-is is self-explanatory in all three languages.

- `gnolcc.py` no longer collapses exceptions into an empty result. A network failure
  and "this airline does not fly the route" used to be indistinguishable in the
  output; failures are now reported separately on stderr.

- Traps for the hotel place parameter being a loose match rather than a geographic
  area (`新大阪` returned 17 properties including Shinsaibashi, Namba and Kitashinchi),
  for brand names not filtering anything, and for capsule/cabin properties sitting in
  the list with no field distinguishing them from ordinary rooms.

- `references/booking-sources.md` documents the Dormy Inn public JSON API (no token
  required) and, more importantly, that its response schema depends on parameter
  completeness: the full parameter set yields `inventories` as a 15-entry list, and
  dropping any single one yields a 14-entry date-keyed dict. Deterministic across
  three runs each.

- A note that `set -- $var` word-splits in bash but not zsh, so batch loops silently
  return empty for every query. Three independent sessions hit this.

---

## 2026-08-31

### Corrected

- **"The stay total is not an exact multiple of the nightly rate — long stays get a
  discount."** It always is, to within 1-3 units of rounding. Measured across 4
  queries and 72 hotels at 2/3/5/7 nights. Google's nightly figure *is* the total
  divided by nights, so any multi-night discount is already inside it. The parser now
  uses that relationship as a reconciliation check rather than repeating the caveat.

- **"Re-running `ghotel.sh` returns the same set of hotels."** It does not. The same
  Osaka query on identical dates, run three times, returned sets differing by 7 of 18
  properties, with the median nightly rate moving across NT$1,830 / 1,839 / 1,931. A
  single query's median carries roughly 5% sampling noise and should not be handed
  over as a precise budget figure.

  Rotation is still not the same as eventually covering the market: whether a
  property Google never surfaces will appear on some later rotation was **not**
  measured, and closing that gap still means querying the brand's own site or a
  narrower place name.

- **Hotel results silently stop matching your dates past roughly 330 days.** Beyond
  the booking horizon Google does not fail — it returns a normal-looking page of
  *one-night* rates for a five-night request. A 2027-10-13 query for 5 nights came
  back as 1 night, with a per-night column that looked entirely unremarkable while
  being off by a factor of five. Flights fail honestly with an empty list; hotels do
  not. Measured boundary: correct at 317 days, fallen back by 345.

- **"Speak up when Google marks an itinerary as separate tickets."** The scripts have
  never surfaced that label. `gfparse.py` does not parse it and the table has no
  column for it, so *not seeing the marker was never evidence that there was none*.
  It exists only in the browser layer — 34 matches on the return-leg page, zero in
  the first screen `curl` retrieves.

### Fixed

- **Arguments were overwriting the figures in the instructions.** Invoking the skill
  through the Skill tool with arguments substitutes `$1`, `$2` and so on at render
  time, so `NT$2,481` arrived as `NTQQCHARLIE,481` — the caller's own words spliced
  into the measured evidence the model reasons from. Amounts in the NT$1,000-2,999
  band were the ones that broke.

  Invisible from a normal session: the slash command renders correctly and only the
  Skill tool substitutes, which is exactly the path a subagent uses. All 29 amounts
  are now backslash-escaped, which disappears in both the skill rendering and GitHub
  markdown, so nothing changes visually.

- **English hotel names swallowed the `GREAT DEAL` suffix.** Google marks a large
  discount as `GREAT DEAL` and a small one as plain `DEAL`; only the latter
  terminated the name pattern. The damage went past the stray word — ratings are
  matched to prices *by name*, so a corrupted name silently lost its rating
  entirely. It hit the three biggest-discount hotels in a search, which is the set a
  price-conscious user cares most about.

- **Date scans hid the most expensive dates.** With `--top` at 10 and twelve dates
  scanned, the two priciest vanished while the summary still printed the maximum —
  the number visible, its date not. "Which day is cheaper" is equally a question
  about which days to avoid. The scan now names the priciest omitted date, and stays
  quiet when everything fits.

- The documented procedure for reading the booking page produced wrong answers.
  Sources that appear only after expanding the list are in no `aria-label`, so
  following the instructions concluded "this route has no OTAs at all". Re-reading
  through `document.body.innerText` found three to four on every path.

### Added

- **`ghotel.sh` reports the stay total alongside the nightly rate**, both including
  taxes and fees. The total is read from the page rather than multiplied out; two
  hotels priced identically per night come back with different totals, which is the
  evidence that the position-anchored pairing works. A mispaired total is the worst
  failure this parser can produce — every figure individually valid, simply belonging
  to a different hotel — so each row is reconciled against nightly x nights and
  disagreement is reported.

- **A warning when Google ignores the dates that were sent.** `ghotel.sh` passes the
  requested number of nights to the parser and warns *above* the table when they
  disagree; below eighteen rows of data it would not be read. `gscan.py` drops such a
  date entirely, since a one-night rate inside a median ranking yields a date ranking
  that reads as sensible and is wrong throughout. Queries more than 300 days out
  print an advisory, deliberately earlier than the point where data vanishes.

- Empty-result messages now name all three causes — bad input, throttling, past the
  horizon — and say how to tell throttling apart, instead of only suggesting a typo.

- Osaka airport transfer figures, which the arrival-airport guidance previously
  lacked: Itami reaches Umeda in 30 min for ¥640, Kansai needs 60-70 min and
  ¥1,150-2,160. A fare a few hundred cheaper into KIX can lose the saving on ground
  transport alone.

- Three evals covering the silent failures, and one assertion requiring a source for
  any claim about what a price includes. The three existing evals all tested whether
  the skill *does something it should*; none tested whether it *avoids asserting
  something false*, which is where every defect in this project has lived.

---

## 2026-08-30

### Added

- Traditional Chinese and Japanese READMEs.
- GitHub Actions CI: the test suite on Ubuntu with Python 3.9 / 3.11 / 3.13 / 3.14
  and on macOS with 3.14, plus shellcheck. No live queries run in CI — the tests use
  synthetic fixtures, shared runner IPs would be throttled quickly, and what needs
  verifying is the parsing logic rather than what the source returned today.
- A test that fails the build when the translated documents drift apart. Prose cannot
  have a single source across languages, so the next best thing is making drift
  impossible to miss: every language version must have an identical heading-level
  sequence. Comparing the sequence rather than the count also catches a heading that
  was demoted or reordered while the total stayed the same.

### Fixed

- `SKILL.en.md` was missing the `references/local.md` instruction, so the documented
  filename swap silently disabled local wiring.
- README quick starts ran under the zh-TW default regardless of which language the
  reader had opened.
- shellcheck could not resolve the sourced `_common.sh`; fixed with a `source=`
  directive rather than suppressing the warning, which would have left that file
  unchecked entirely.

---

## 2026-08-29

Initial public release. Live airfare and hotel rates from Google Flights and Google
Hotels, three locales (zh-TW / en / ja), date scanning, and the non-LCC round-trip
query that applies the airline filter to both legs.
