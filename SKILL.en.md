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
scripts/gflight.sh TPE KIX 2026-11-15                   # one way (omit return; codes pin one airport)
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
Both arguments go straight into the query string, so **plain city names work fine and are usually
safer than hunting for airport codes**; use codes only when the user explicitly wants one airport.
The same applies to hotel locations — a place name is enough, no IDs to look up.

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
- **Arrival airport** — the cheapest option often lands at the farther airport, adding an hour and a fare to reach the city
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

**Hotel prices are per night, not the stay total.** Google's default display is the nightly rate
(taxes and fees included); there is a "total stay" toggle on the page but the scripts read the
default. So multiply by nights for a budget, and **never divide it by nights** thinking it was a
total — that mistake has been made in practice and produced a figure five times too low. The true
total is usually not an exact multiple either, since longer stays often get a discount.

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

## Traps (these produce wrong prices with no error at all)

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
Two constraints: the name **must match the current interface language** (`China Airlines` returns
zero results under `hl=zh-TW`, and the Chinese name returns zero under `GFH_LANG=en` — both
verified), and only one airline can be filtered at a time, so the script queries each in turn and
merges.

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

### Google is not the whole market

Google lists partners it has deals with. Flash sales on budget carriers' own sites and many regional
OTAs never appear. "Cheapest on Google" is not "cheapest available". Say so when the amount is large
or the user is clearly comparison shopping — do not let them believe they have seen every option.

### Only the first screen

`curl` returns the server-rendered first screen: roughly 20-24 flights, 18-20 hotels. That is
entirely sufficient for price discovery and date comparison, but it is not the full list. When the
user wants an exhaustive answer ("list every nonstop option"), state the limitation and switch to a
browser if needed.

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

## When something goes wrong

- **"date is in the past"** — the script blocks this and states the reason. Usually the user gave a
  month with no year, that month has already passed this year, and it was resolved to this year
  anyway. Re-run with next year.
- **"(no data)"** with no error message — check airport codes and place spelling; dates must be
  `YYYY-MM-DD`.
- **Some dates return nothing during a scan** — the script warns that this may be throttling rather
  than genuinely sold out. Concurrency is capped at 6 as a courtesy to the source. If it persists,
  narrow the range and run in batches. **Do not tell the user "there are no flights on those days"** —
  that is usually false.
- **Prices look implausible** (New Year cheaper than a weekday) — the classic symptom of dates not
  taking effect. Check whether a URL was assembled by hand instead of going through the scripts.

Prices are live; Google notes its results are within the last 24 hours. Mention once that fares may
have moved by the time the user books — once is enough, no need for a disclaimer every time.
