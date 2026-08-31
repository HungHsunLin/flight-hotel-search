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
