---
name: flight-hotel-search
description: "Look up live airfares and hotel rates (source: Google Flights / Google Hotels) and compare whether a fare is sold by the airline directly or by an OTA. Trigger whenever the user wants to know what a route costs right now, what accommodation runs in a given city, which date is cheapest to fly or check in, or what a specific hotel currently charges. Covers many phrasings: direct ('check flights Taipei to Tokyo', 'how much are hotels in Kanazawa'), comparative ('which day in October is cheapest', 'how much more is New Year in Tokyo', 'is the airline site cheaper than Agoda'), planning ('I want to go to Hokuriku in November, what should I budget for lodging', 'what are cherry blossom season rates', 'planning 5 days in Fukuoka in March, roughly what do flights plus hotels cost'), and follow-ups ('what about Haneda instead', 'what if I stay four nights'). Trigger even when the user never says 'search flights' or 'search hotels' - if the intent is to learn what something actually costs right now, this skill applies. This skill only queries; it cannot book anything."
---

# Flight & Hotel Search — live fares and room rates

Pulls live prices from Google Flights / Google Hotels. The core insight: **Google server-side
renders the first screen of results into the HTML, so most queries need nothing but `curl`** —
roughly 20x faster than driving a browser. Only the "who is actually selling this fare" layer is
loaded dynamically and requires a real browser.

Work out which of these the user wants before running anything — do not assume all three:

| What the user wants to know | Use | Time |
|---|---|---|
| What this route / this city costs right now | single query (`gflight.sh` / `ghotel.sh`) | ~1 s |
| Which departure / check-in date is cheapest | date scan (`gscan.py`) | ~3 s per 10 days |
| Airline site or OTA? Is this two separate tickets? | browser, booking sources (see references) | ~15 s |

Scripts live in `scripts/`; call them by absolute path. Per-language parsing rules are centralised
in `scripts/locales.py`. Output is already sorted and formatted — relay it directly rather than
rebuilding it into your own table.

## Single query

```bash
scripts/gflight.sh Taipei Tokyo 2026-10-01 2026-10-05   # round trip (city names cover all airports)
scripts/gflight.sh TPE KIX 2026-11-15                   # return date omitted (NOT a one-way fare - see traps)
scripts/gflight.sh Taipei Osaka 2026-03-15 2026-03-20 "EVA Air"   # one airline at a time
python3 scripts/gnolcc.py Taipei Osaka 2026-03-15 2026-03-20      # exclude budget carriers (see traps)
scripts/ghotel.sh Kanazawa 2026-11-24 2026-11-26 2      # place, check-in, check-out, adults
```

**When the user gives a month/day with no year, work out the year yourself before calling the
script.** For phrases like "early February" or "late December", use the *next* occurrence of that
month that has not yet passed — not mechanically the current year. Said in August, "early February"
almost certainly means next year. The scripts reject past dates outright, but treat that as a last
line of defence, not as your way of noticing the mistake.

City codes cover multiple airports: `TYO` = Narita + Haneda, `OSA` = Kansai + Itami. Use `NRT` /
`HND` / `KIX` to pin a single one.

**Watch out for cities whose code does not cover every airport.** Measured example: `TPE` covers
only Taoyuan, not Songshan (`TSA`). Querying Taipei→Tokyo with `TPE` returned 24 results; using the
city name returned 32 — the extra 8 departed from the close-in city airport with better timings.
Both arguments go straight into a natural-language query string, so **codes and place names both
work — and either can fail to parse and silently return zero rows**. An earlier copy of this file
said plain city names are "safer than hunting for airport codes"; that understated the risk.
Measured: `熊本` resolves to Kumamoto *Prefecture* and returns nothing, while `熊本市` and `KMJ`
both work. Read "Zero rows does not mean no flights" below before you conclude anything from an
empty result. Hotel locations likewise need no IDs, but be aware the place string is a loose match
rather than a geographic area (also in the traps).

**Passenger count is an approximation.** The text query interface ignores passenger parameters —
writing "for 2 adults" into `q=` has no effect, and what comes back is always the single-traveller
round-trip price. For groups, multiply yourself and **say clearly that it is a per-person price
multiplied out, not a total the system computed**. This has been verified against the browser for
identical origin/destination pairs, but it will not reflect non-proportional fares such as child or
senior tickets.

Beyond the price itself, these factors usually matter more to the decision — raise them unprompted
when you see them:

- **Duration and connections** — saving money but adding a connection and six hours is often a bad trade
- **Red-eyes** — a 2:00 AM departure looks great on price and costs the user a day plus a night's sleep
- **Arrival airport** — the cheapest option often lands at the farther airport, adding an hour and a fare to reach the city. Osaka is a sharp case: Itami reaches Umeda in 30 min for ¥640 and Namba in ~35 min, while Kansai needs 45 min and ¥930+ to Namba and 60-70 min and ¥1,150-2,160 to Umeda — a fare that is a few hundred cheaper into KIX can lose the saving on ground transport alone
- **Hotel rating vs. review count** — 4.5★ from 30 reviews is far weaker evidence than 4.1★ from 2,000
- **Festivals, public holidays, events in the period** — when a date is unusually expensive or cheap
  there is often a concrete reason (a national holiday, peak foliage or blossom season, a fireworks
  festival, a limited illumination). Confirm with WebSearch and cite the source; that is far more
  useful than "this day is pricier", because the user can judge whether the reason is one they care
  about.

## Language and currency

Defaults are **zh-TW / TWD / tw**. Everything is driven by environment variables:

```bash
GFH_LANG=en scripts/gflight.sh Taipei Tokyo 2026-10-01 2026-10-05   # English UI, USD
GFH_LANG=ja scripts/ghotel.sh 金沢 2026-11-24 2026-11-26 2          # Japanese UI, JPY
GFH_LANG=en GFH_CURR=JPY scripts/ghotel.sh Kanazawa 2026-11-24 2026-11-26 2   # English UI, yen prices
```

| Variable | Default | Notes |
|---|---|---|
| `GFH_LANG` | `zh-TW` | `zh-TW` / `en` / `ja` |
| `GFH_CURR` | follows language | Independent of language |
| `GFH_REGION` | follows language | Google's `gl` parameter |
| `GFH_UA` | a normal browser string | Set to use your own identifier |

**Do not switch language on your own initiative.** Report results in the language the user is
reading, even when another locale would return richer data — a list of property names the user
cannot read is worse than a slightly shorter list they can. Switch only when:

1. **The user asks for it** ("search in Japanese", "give me the price in USD")
2. **The current locale returns nothing** for the target property, or the user is specifically after
   small local operators — then query the local language as a supplement, but **always include the
   name in the user's own language alongside it**, or they will not find the property when booking

**Do not translate airline or hotel names yourself** — relay what the script returns. If you add a
translation for clarity, keep the original alongside it, or the user will not find the property when
they go to book.

Parsing rules live in `scripts/locales.py`. **Adding a language requires actually fetching a page in
that language and diffing the real strings against your patterns** — patterns written from grammar
intuition return an empty list, which is indistinguishable from a typo or throttling.

## Date scanning

Use when the user asks which date is cheapest, which month is better value, or how to avoid the
expensive days.

```bash
python3 scripts/gscan.py flight TPE TYO 2026-10-01 2026-10-31 --nights 4
python3 scripts/gscan.py hotel Tokyo 2026-12-25 2027-01-05 --nights 3
```

`--nights` is the length of stay; the scanner pairs the return / checkout date automatically.

**`ghotel.sh` reports both the nightly rate and the stay total**, each including taxes and fees.
The total is read straight off the page (zh 「總價為 \$12,067」, en "\$381 total", ja 「合計 ￥68,216」)
rather than multiplied out. **Never divide the nightly rate by nights** thinking it was a total —
that mistake has been made in practice and produced a figure five times too low.

Measured across 4 queries and 72 hotels (2/3/5/7 nights), **the total always equals nightly x
nights**, off by only 1-3 units of rounding — any multi-night discount is already baked into that
nightly average. So the intuition that "long stays get a discount, so the total will not be an exact
multiple" is wrong. The parser uses the relationship in reverse, as a reconciliation check: a row
that disagrees means the layout changed and the total was paired with the wrong hotel, and the
output says so. That check earns its keep because a mispairing produces figures that are all
individually valid and simply belong to a different hotel — nothing looks wrong.

`gscan.py` shows the median nightly rate only: each date there is a separate query with a fixed
number of nights, so nightly figures compare across dates more meaningfully than totals would.

**The hotel scan ranks by median nightly rate, not the minimum — deliberately.** The cheapest
listing is often a hostel or capsule, so one cheap bed makes a genuinely expensive date look like a
bargain. Measured: one date had the lowest minimum price across the whole range while its median was
four times the following week's — it was the single worst date to travel. Lead with the median and
offer the minimum as a footnote.

The "spread" figure in the scan output is often the most valuable line: picking the right date on
one measured October route saved 33%. When the spread is small, say so explicitly — "prices are flat
across this period, schedule at your convenience" saves the user from contorting a trip to save
pocket change.

## Booking sources (airline site vs. OTA)

`curl` cannot reach this layer; it needs a browser. Only worth the ~15 seconds when the user asks
who is selling the fare, whether the airline's own site is cheaper, or when they are **about to
book**.

Full procedure in `references/booking-sources.md`: selecting the flight, reaching the booking page,
and the selectors for telling an airline site from an OTA.

The key discriminator: Google attaches a separate badge to the airline's own listing. **Do not match
on whether the source name contains an airline name** — OTA names can contain airline names too.

**For hotels, do not conclude from Google's single "official site" number.** Google shows one price
per channel, but a hotel's own site sells a whole set of plans (early bird, multi-night, breakfast
included, free cancellation, member rates). Measured: 21 plans for the same room, with the 5-night
total varying nearly twofold. To judge whether the direct site is a good deal you have to open it
and expand the full plan list — the default view shows "recommended" plans, which are usually not
the cheapest. Align room type, breakfast, and cancellation terms before comparing, or you are
comparing different products.

## When the user says "I have a membership with X", enumerate the whole brand

**This is a fork in the procedure, not a footnote.** The normal flow is "search Google for the going
rate → pick one → open that property's own site". But the moment the user mentions a membership,
member rates, point rebates and site-exclusive plans follow **the brand, not the individual
property** — so list every branch that brand has in the target city first, then compare them in one
pass.

How: open the brand's branch list on its own site (e.g. `viainn.com`) and collect every branch in
the target city — its slug, plus the booking engine's `code`, which is the `code=` parameter on
that branch page's 「ご宿泊プランはこちら」 link. (Those branch pages are Japanese whatever your
own locale is.) Then query member rates branch by branch with the same dates and occupancy.

**Why this is not optional**: measured in Osaka, VIA INN has 8 branches. A Google search for Osaka /
Umeda surfaced only 2 of them, and the one it did surface (Umeda, NT\$14,273, 13㎡) was **the most
expensive in the entire brand**. The Shinsaibashi branch, which never appeared, was NT\$11,064, and
Prime Shinsaibashi Yotsubashi had a 15㎡ room at a member rate of NT\$12,079 — cheaper than Umeda
and larger. Querying only the one Google handed you recommends the worst option with no sign that
anything is missing.

One related thing you will hit: sold-out dates. The booking page redirects to `/booking/recommender`
and says in so many words that no rooms were found. **Read that sentence before declaring it sold
out** — do not infer it from failing to parse any rooms, because the two look identical.

### Booking pages lazy-load; without scrolling you only see the smallest rooms

Hotel booking engines (tripla and VIA INN's are examples) **render only the first 2 room types**
initially, and the sort order usually puts the cheapest single room first. The "N results" count the
page prints is the real total — **when N disagrees with how many rooms you parsed, the page has not
finished loading**. Repeat `window.scrollTo(0, document.body.scrollHeight)`, wait 2 seconds, and
continue until the room-size label stops appearing more times.

Both the results count and the room-size label are rendered **in whatever display language you
loaded the page in** — match on the labels actually present in the page you fetched, never on a
string hardcoded for one language.

This trap is especially nasty because **the truncated data looks completely normal**: every property
has room types, prices and member rates — they just all happen to be 12-13㎡. Measured across four
VIA INN properties in Osaka, without scrolling each showed only 2 single rooms; after scrolling,
Umeda turned out to have a 17㎡ double and a 23㎡ deluxe twin, and Prime Shinsaibashi Yotsubashi
two 20㎡ room types. When the user complains the rooms are too small, the ones being dropped are
precisely the ones they wanted.

**The general rule**: on any page where a stated "N results" disagrees with the number of rows you
parsed, confirm the page has finished loading before you start comparing prices.

## Traps (these produce wrong prices with no error at all)

### Zero rows does not mean no flights

`gflight.sh` assembles a natural-language sentence for Google (`Flights from A to B on C through D
E`), so **what decides the outcome is whether the whole sentence parses** — not whether you used a
code or a place name. When it fails to parse, Google returns 200 and an empty results page, which
looks exactly like a route with no flights.

Measured 2026-09-02, Taipei→Kumamoto, 9/12-9/16:

| Query | Page title | Rows |
|---|---|---|
| `臺北市 熊本市` | Taipei to Kumamoto City \| Google Flights | 6 |
| `臺北市 熊本` | Taipei to Kumamoto **Prefecture** \| **Explore** | **0** |
| `TPE KMJ` | Taipei to Kumamoto City \| Google Flights | 6 |
| `TPE KMJ 中華航空` | Taipei to Kumamoto City \| Google Flights | 4 |
| `TPE KMJ 星宇航空` | generic "search cheap flights" **home-page title** | **0** |

`熊本` resolved to the *prefecture*, which Flights cannot search, so the request landed on the
Explore page; `TPE KMJ 星宇航空` never parsed at all and fell back to the home page. Neither is
"no flights". Note this overturns the intuitive reading: the problem is not codes vs. names — all
four endpoint spellings (`TPE`/`臺北市` × `KMJ`/`熊本市`) returned 6 rows on their own.

**The script now prints the diagnosis at the point of failure**: on zero rows it adds a line, "What
Google resolved the query to: …", carrying the page title. A prefecture/state/county, or the generic
home-page title, means the query did not parse — rephrase and retry (add the city suffix, switch to
an airport code, or write the airline name in another language).

**And the same query re-run does not return the same thing.** Measured: `TPE KMJ 中華航空` returned
zero rows on 2 of 11 runs (~18%), and a differently-worded "known-good" control query **passes**
during those failures. So the old advice — "re-run a query known to work to tell throttling apart" —
cannot tell them apart at all. Before concluding anything is absent, re-run **the same query** 2-3
times.

This flake has a nastier consequence: **it manufactures false documentation.** The `China Airlines`
claim corrected above got in exactly this way — someone tested once and hit the 18%. Any conclusion
of the form "measured: X returns zero rows" **needs a sample size greater than one**.

### A fifth kind of zero: the flights exist, the fares do not

None of the four causes above covers this one, and it looks **exactly like a fully
successful query**: the page title is normal and the flight rows are there — each row's
aria-label just starts with "no total price available". `gfparse.py` treats price as a hard
filter, so those rows are dropped wholesale and **an entire airline can vanish**.

Measured (2026-09-05, Tokyo to Sapporo, 2027-03-04/09): 38 aria-labels mention ANA, more
than JAL, yet **not one ANA row** survives parsing. Filtering the query to ANA drops all 62
rows (ANA 38 + AIRDO 24) and prints just "(no data)" — while the four reasons that message
lists are **all wrong**, and the title diagnostic reports a successful parse, steering you
toward "probably throttling".

**The scripts now warn**: the drop tally prints at the **top** of the output (especially on
zero rows), e.g. "38 more flights excluded because Google listed no fare: ANA 38". That
means the departures exist and only the price is missing — check the airline's own site,
and do **not** report "no flights found".

### Omitting the return date does not search one-way fares, and cannot do open-jaw

`gflight.sh A B departure` with no return date is **not** a one-way search. Measured
Taipei→Kumamoto: one-way 9/12 and round-trip 9/12-9/16 both returned 6 rows with the same
NT$9,272 minimum — Google supplies a default return and still prices a round trip.

The consequence: anyone building an open-jaw itinerary (different in and out, say into Kumamoto and
out of Fukuoka) from two "one-way" queries is adding up **two round-trip fares**, wildly wrong with
no visible sign. **This tool cannot price open-jaw or one-way**; those need the airline's own site
or an OTA multi-city search.

### The hotel place parameter is a loose match, and a brand name does not filter

`ghotel.sh 新大阪 …` returned 17 properties including ones in Shinsaibashi, Namba, Tanimachi-yonchome,
Kitashinchi and Hommachi — none of them in Shin-Osaka. The place string is a loose search match,
**not a geographic radius**. So do not report results as "the going rate in district X"; list the
property names and let the user judge.

**Putting a brand name in the place parameter does no brand filtering**: `ghotel.sh "大阪 VIA INN" …`
returned zero rows, and none of those 17 Shin-Osaka properties was a VIA INN. Enumerating a brand
needs the procedure in "When the user says I have a membership with X" above.

### Local place names may return nothing, and hotels give you no diagnostic

Google's Chinese UI often uses mainland Chinese renderings. Measured 2027-03-04/09, 1 adult:
`二世谷` (the Taiwanese name for Niseko) returns **0 hotels** three runs in a row, `新雪谷`
(Google's Chinese) returns 10, and `ニセコ` (Japanese) returns 17. Europe is worse — the name
can land on **a different city**: `ghotel.sh 華沙` (Warsaw) returns three hotels in Shanghai;
only the English `Warsaw` works (19 rows). Every field is valid, just for the wrong city.

**And the hotel title is no help**: all spellings produce a title that merely echoes the
query. The flight-side diagnostic (is the title a prefecture / an explore page / the
homepage?) does not exist here, so "re-run 2-3 times" is useless advice for a name error —
it returns 0 every time.

**What to do**: when hotels return 0 rows or look wrong, the second step is not a re-run,
it is **another spelling** — native, English, and mainland-Chinese in turn. **Use Japanese
kana for places in Japan and English names everywhere in Europe and the US.** Always give
the user the local name alongside, or they will not find the property when booking.

### Too few hotel rows means the median is unusable

`ghotel.sh` normally returns 18. Obscure or colliding place names can return single digits,
and **the output looks identical to an 18-row result**. Measured (European ski areas,
2027-03-04/09, 1 adult): Ischgl returned 4 rows, median NT$43,327; St. Anton 8 rows,
NT$14,283 — while Innsbruck the same week returned 19 rows at NT$3,962, an order of
magnitude apart.

With n=4 the median is just the mean of rows 2 and 3; one outlier destroys it. **Below 10
rows the script now warns above the table**, and the median should be read as "this price
point exists", never as a market rate.

A separate issue: **a single query's median can be off by far more than the 5% quoted
elsewhere in this file**. Krakow on identical dates returned 956 / 1,987 / 1,315 across
three runs — the May and June ranges overlapped completely, so month-over-month ranking
from this source is fiction. When comparing cities or months, **run each query 3 times and
take the median**, and only trust differences of 2x or more. Expensive cities are steadier
(Zurich: 4,713-4,752); cheap ones swing because hostels dominate.

### Room type is never labelled, and the median can skew both ways

Among those 17 Shin-Osaka properties was First Cabin Nishi-Umeda, a cabin-style property, at
NT$1,314 — in the middle of a list of business hotels, with **no field marking it as anything
other than a normal room**. Worse is the hybrid case: Hotel Abest Grande Okayama describes itself
as a fusion of business hotel and cabin hotel, offering both Western rooms and cabin types, with
the ladies' cabin having no private bath or toilet.

So confirm the room type before treating a Google figure as "what that hotel costs". A peer session
reported that on such hybrids the Google price lands on the capsule berth and understates a real
single room by nearly 3× — **that specific figure is not reproduced here** (the same property showed
NT$1,675 on re-test, not the NT$1,042 reported, on different dates so not directly comparable), but
the hybrid operation itself is confirmed, which is reason enough to check the room type first.

### The hotel `checkin` / `checkout` parameters are fake

The intuitive `?q=tokyo+hotels&checkin=2026-12-30&checkout=2027-01-03` **does not fail** — it
returns a completely normal-looking page of hotels and prices, with the dates silently ignored and
tomorrow-night rates substituted. Measured on one property: fake dates gave 1,348 versus 4,207 for
the real 4-night New Year stay — a 3.1x difference.

**Occupancy is also in `ts=`, and the encoding is counter-intuitive.** It is not a number in a
field, it is **the number of times a field is repeated** — one adult is one group, two adults repeat
it twice. An earlier version wrote the count into a different field; Google silently ignored it and
always returned the 2-person rate (the symptom: 18 hotels showing identical prices at adults=1/2/4).
**Single-occupancy rates are typically 20-30% cheaper — do not use a 2-person rate as a solo budget.**

**Currency is in `ts=` as well, and the URL's `curr=` has no effect on hotels.** Measured: sending
`curr=USD` and `curr=JPY` both returned TWD prices, because the currency field inside the `ts`
protobuf is what actually applies. `ghotel.sh` and `gscan.py` already pass `GFH_CURR` through, so
going via the scripts is safe.

The real dates live inside `ts=`, a base64 protobuf parameter. `scripts/gtsgen.py` generates it
(byte-for-byte identical to what the browser produces), and the scripts already use it — **so going
through them avoids this entirely**. This is documented because building the URL by hand will not.

Generalising: **Google does not return 400 for parameters it does not recognise — it quietly
computes a result with defaults.** Any time you assemble query parameters by hand, run a control:
change an input that *should* move the result visibly (New Year's Eve vs. an ordinary weekday). If
nothing changes, your parameter is not taking effect.

### "Round trip from X" only names the outbound carrier

Each search result carries **only the outbound leg's airline**, and the price is a floor computed by
pairing the cheapest available return — which is frequently a budget carrier. So **filtering the
result list by airline filters only the outbound**; the return can be a different, cheaper airline,
and the combination becomes two separate tickets.

When the user says "no budget airlines", use `gnolcc.py` rather than filtering `gflight.sh` output:

```bash
python3 scripts/gnolcc.py Taipei Osaka 2026-03-15 2026-03-20
```

It pushes the airline name into the query string, where **Google applies the filter to both legs**.
Matching the current interface language is the safest habit, but it is **not** a hard rule: an
earlier copy of this file claimed `China Airlines` returns zero results under `hl=zh-TW` and marked
it "verified". Re-tested on 2026-09-02 that is **false** — Taipei→Kumamoto returned 5/5/5/0 rows
across four runs, and `Starlux` worked too. That single zero was the intermittent empty response
described below. The real constraint is that only one airline can be filtered at a time, so the
script queries each in turn and merges.

Measured on one round trip: the listing showed one carrier at 11,711, which was really that carrier outbound
plus a budget airline back; a genuine both-legs round trip was 13,819. That gap is enough to invert
the entire comparison, and nothing on the results page reveals it.

### Separate tickets

Budget combinations often pair "airline A out, airline B back" into one cheap total, which Google
labels as separate tickets requiring two bookings. That means two fully independent tickets: bags
are not through-checked, a delayed outbound that causes a missed return is nobody's liability, and
changes are priced separately.

Flag this proactively rather than just reporting the price. The saving buys that risk, and users
usually do not realise they are taking it on. A single-carrier through fare typically costs 30-40%
more — that difference is the insurance premium.

**The scripts do not surface that label.** `gfparse.py` does not parse it and the table has no
column for it, so **not seeing the marker is not evidence that there is none**. Avoid the situation
at the source instead: reach for `gnolcc.py` when the user cares — its airline filter applies to
both legs — and open the browser layer to confirm any particular itinerary.

### Google has no room size

When the user asks how big the room is, do not look for it in Google's data — the field does not
exist. Hotel detail tabs cover price, details, reviews, photos, about, restaurants, attractions and
airports; the search HTML contains no square-metre figures at all. Go to the **hotel's own room
page**, and if that omits it, use the room specification tables on regional booking sites (in Japan:
Jalan, Rakuten Travel, Yahoo! Travel). Japanese booking sites need a browser tool; WebFetch cannot
reach them.

Room size affects decisions more than expected. Measured across one batch of Osaka business hotels:
the cheapest was 14㎡ while two properties costing 30% more were only 10㎡ — price and room size were
essentially uncorrelated, so checking price alone leads to a wrong recommendation. For reference,
10-12㎡ is standard for Japanese business hotels and 16㎡+ counts as spacious.

### Past the booking horizon, hotels silently return a one-night rate

Measured boundary (August 2026, Taipei to Osaka / Osaka hotels): at **304 days out** flights
returned 3 rows, at **317 days** 1 row, at **331 days** none. Hotels still returned a correct
5-night figure at 317 days and had **fallen back to 1 night by 345**.

Flights fail honestly with an empty list. **Hotels do not** — the page comes back full of
normal-looking hotels and prices that are simply one-night rates. Measured: a 2027-10-13 request
for 5 nights returned 1 night, and the per-night column looked entirely unremarkable while being
off by a factor of five.

`ghotel.sh` now passes the requested number of nights to the parser for reconciliation and warns
**above the table** when they disagree — a warning printed below 18 rows of data may as well not
exist. `gscan.py` drops such a date as no-data instead: letting a one-night rate into the median
ranking produces a date ranking that reads as perfectly sensible and is entirely wrong.

Queries more than 300 days out print an advisory. That threshold is deliberately earlier than the
point where data disappears, because between 300 and 330 days the results merely thin out — and a
shrinking sample is much easier to mistake for a real price signal than an empty one is.

### For long-haul (Taipei to Europe/US) the first screen is unusable; prices can be off 2-4x

The note above says "the row count is itself information", but on long-haul routes a low
count is not merely thin supply — **the few rows you do get are themselves wrong**.
Measured 2026-09-05:

| Route | curl first screen | Full browser result | Gap |
|---|---|---|---|
| Taipei to Warsaw | 2 rows, from NT$59,213 (China Airlines+Condor, 29h) | 12 rows, from NT$28,019 (Etihad, 18h) | **2.1x** |
| Taipei to Stockholm | NT$110,374 | NT$27,310 | **4x** |

The failure is silent: price, carrier and duration all look perfectly normal.

**Tell-tale sign**: every row in the batch shares the **same carrier and the same departure
time**, and the duration is far above what the route normally takes (Taipei to Europe with
one stop is normally 17-20h; 25-30h is a red flag). In this skill's field notes, Taipei to
Geneva returned 2 rows on all five dates, all "China Airlines, Condor", 25-30h — that is
the fingerprint.

**What to do**: for long-haul, **skip `gflight.sh` and drive Google Flights in a browser**
(`https://www.google.com/travel/flights?q=Flights from A to B on YYYY-MM-DD through YYYY-MM-DD&curr=TWD&hl=en&gl=us`),
pulling the block between "search results" and "view more flights" from
`document.body.innerText`. Short-haul (Japan, Korea) is unaffected, and so is `ghotel.sh`.

### Google is not the whole market

Google lists partners it has deals with. Flash sales on budget carriers' own sites and many regional
OTAs never appear. "Cheapest on Google" is not "cheapest available". Say so when the amount is large
or the user is clearly comparison shopping — do not let them believe they have seen every option.

### Only the first screen

**Two different numbers: how many were parsed, how many were printed.** `gflight.sh` and
`gnolcc.py` print only the **12 cheapest** by default, but the trailing "N results" line is
the **full parsed count**. Results are sorted by price, and nonstops and full-service
carriers tend to be pricier, so they get **systematically pushed past the cutoff** — never
count "how many nonstops" from the printed table. Measured failure: a 12-row table gave
"only 2 nonstops left on 1/20"; a full re-check showed 32, and that wrong conclusion shipped
to the user. Pass `--top 60` (`gnolcc.py`) or `GFH_TOP=60` (`gflight.sh`) to count. The
output warns when it truncates.

`curl` returns the server-rendered first screen: roughly 20-24 flights, 18-20 hotels. That is
entirely sufficient for price discovery and date comparison, but it is not the full list. When the
user wants an exhaustive answer ("list every nonstop option"), state the limitation and switch to a
browser if needed.

**This limitation does not merely cost completeness — it makes conclusions wrong.** Those 18 are not
"the best 18 in the area". A single chain often gets only one or two of its properties sampled, and
the sampled ones are not necessarily the cheap ones. Measured in Osaka, VIA INN has 8 properties;
Google returned 2, and one of those was the most expensive in the whole brand. The two genuinely
good-value ones (Shinsaibashi at NT\$11,064, Prime Shinsaibashi Yotsubashi with a 15㎡ room at
NT\$12,079) never appeared at all.

**The 18 rotate between runs.** The same query (Osaka, identical dates) run three times returned
sets differing by 7 of 18 properties, with the median nightly rate moving across NT\$1,830 / 1,839 /
1,931. A single query's median therefore carries roughly **5% sampling noise** — do not treat it as
a precise budget figure; run it two or three times and take the median of the medians if precision
matters.

Rotation is **not** the same as eventually filling the gap. Whether a property like VIA INN
Shinsaibashi ever surfaces on some later rotation is untested — what rotates is the sample, which
guarantees nothing about covering the population. To actually close the gap, still query the
brand's own site or search a narrower place name ("Shinsaibashi", "Shin-Osaka").

## Integrating with other skills

This skill **queries only — it cannot book anything.** When the user is ready to book, point them in
the right direction (which channel, roughly what price, watch for separate tickets) and let them
complete it.

If the user keeps trip documents and wants results saved into them, **this skill handles the lookup
and formatting; delegate the actual file writing to whichever skill owns those documents.** That
skill already knows the file structure, formatting conventions, and de-duplication rules; writing
through a second path produces duplicate entries and format conflicts.

Format the results as a clean shortlist (price, timing, rating, your recommendation and the reason
for it), mark clearly which option you are recommending versus which are alternates, then hand off.

**Machine-specific wiring**: if `references/local.md` exists, read it — it records which skill on
this machine actually handles the writing, along with the user's own document conventions. That file
is not in version control, so the published skill assumes no particular skill ecosystem.

## When something goes wrong

- **"date is in the past"** — the script blocks this and states the reason. Usually the user gave a
  month with no year, that month has already passed this year, and it was resolved to this year
  anyway. Re-run with next year.
- **"(no data)"** with no error message — **read the line under it first, "What Google resolved the
  query to:"**. That is the page title and it tells you what Google understood. A prefecture/state,
  or the generic home-page title, means the query never parsed — it is not "no flights". Then re-run
  **the same query** 2-3 times (~18% intermittent empty responses). Only after that check codes,
  place spelling and the `YYYY-MM-DD` date format. See "Zero rows does not mean no flights".
- **Some dates return nothing during a scan** — the script warns that this may be throttling rather
  than genuinely sold out. Concurrency is capped at 6 as a courtesy to the source. If it persists,
  narrow the range and run in batches. **Do not tell the user "there are no flights on those days"** —
  that is usually false.
- **A whole batch loop returns empty** — check your shell first. `set -- $var` word-splits in bash
  but **not in zsh**, so both dates arrive as a single argument and every query comes back empty,
  looking exactly like no data. Three independent sessions hit this. Use `while read -r a b`, or
  run the loop explicitly under `bash -c`.
- **Prices look implausible** (New Year cheaper than a weekday) — the classic symptom of dates not
  taking effect. Check whether a URL was assembled by hand instead of going through the scripts.

Prices are live; Google notes its results are within the last 24 hours. Mention once that fares may
have moved by the time the user books — once is enough, no need for a disclaimer every time.
