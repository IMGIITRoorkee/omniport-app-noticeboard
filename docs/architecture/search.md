# Notice search

How keyword search works, what the numbers in `utils/search.py` do, and how to
check that a change to them made things better rather than worse.

## The pipeline

A search request arrives at one of three places:

| Endpoint | View | Used by |
|---|---|---|
| `/api/noticeboard/new/?keyword=` | `NoticeViewSet.get_queryset` | the main list |
| `/api/noticeboard/filter/?keyword=` | `FilterViewSet` → `filter_search` | the banner filter |
| `/api/noticeboard/date_filter_view/?keyword=` | `DateFilterViewSet` → `filter_search` | the date filter |

All three end up in `get_ranked_notice_ids` in `utils/search.py`, which returns
notice ids in the order they should appear. The caller then fetches those rows
from PostgreSQL and preserves the order with a `Case`/`When`.

Elasticsearch decides **which notices match and in what order**. PostgreSQL only
supplies the rows. The index holds `id`, `is_draft`, `title`, `content` and
`datetime_modified` — nothing else, which is why searching by banner or by
creation date is not possible without a reindex.

## The three phases

`_build_phases` builds three queries. They run in order and their results are
merged, strict first:

| Phase | What it asks for | Purpose |
|---|---|---|
| **strict** | the phrase, or a prefix of it, in the title | precision |
| **relaxed** | 75% of the words anywhere | recall |
| **fuzzy** | the words within one or two edits | misspellings |

Strict and relaxed **always both run**. Fuzzy runs only if those two together
return fewer than `MIN_SEARCH_RESULTS` hits, because it is a spelling fallback
rather than a way of finding more.

The strict phase has three clauses, any one of which is enough to match:

- `multi_match` `type=phrase` over `title^5` and `content` — the whole phrase,
  words adjacent, title counted five times as heavily as body
- `match_phrase_prefix` on the title, boost 5 — so `micro` finds `Microsoft`.
  Separate tokens do not match each other, so `title^5` alone cannot do this
- `wildcard` `*keyword*` on the title, boost 2 — catches a fragment in the
  middle of a word, which is what makes `goog` and `amaz` work

Every phase filters `is_draft: false`. Unpublished notices are never searchable.

Each strict clause is named, and Elasticsearch reports the names a hit matched
back in `matched_queries`. That is what a tier is read from, below.

## Relevance tiers

Score alone is a poor final order. For `microsoft` the 107 notices carrying it
in the title score from 72.6 down to 40.4, and the whole spread is BM25's
field-length normalisation: "Microsoft: Design Challenge" beats "Microsoft
(Applied Scientist): Shortlist for Interviews" for having fewer words. To a
reader those are equally relevant and the order is noise.

The boundary between groups, on the other hand, is sharp. The first body-only
match for `microsoft` scores 7.31 — a 5.5× cliff, not a gradient — and it lines
up with *how* the notice matched rather than with any number. So the group is
read off `matched_queries` and no threshold has to be tuned:

| Tier | Matched | Meaning |
|---|---|---|
| 1 | `title_prefix` + `phrase` | the phrase is in the title |
| 2 | `title_prefix` | a partly typed word at the start of a title word |
| 3 | `phrase` | the exact phrase is in the body |
| 4 | `title_wildcard` only | a fragment inside a title word |
| 5 | the relaxed phase | 75% of the words, anywhere |
| 6 | the fuzzy phase | within one or two edits |

Results are ordered by tier, then **by date inside tiers 1 to 4** and **by score
inside tiers 5 and 6**. That split is not a matter of taste; it was measured.
Date-ordering the fuzzy tier as well took `gogle` from 100% precision to 23%,
because inside that tier the score is what separates Google from Goel. Inside
the title tiers it separates nothing but title length.

Tier 4 sits under tier 3 deliberately. A wildcard hit is a fragment inside a
word — `art` matches "Dep**art**ment", "India**MART**", "Flipk**art**" — so it
stays available, since it is what makes `goog` and `amaz` work, without
displacing a genuine body match.

Set `NOTICEBOARD_TIERED_RELEVANCE=0` to fall back to ordering by score alone.

## Ranking

Scores are Elasticsearch's own BM25, multiplied by a recency factor from
`_wrap_with_recency_decay`:

```
multiplier = gauss(age) * (1 - FLOOR) + FLOOR
```

`gauss` falls from 1 to 0 as a notice ages. Weighting it at `1 - FLOOR` and
adding a constant `FLOOR` gives a multiplier confined to `[FLOOR, 1.0]` — a
fresh notice keeps its whole score, an ancient one keeps `FLOOR` of it, and the
most recency can ever swing a result is `1 / FLOOR`, currently 2×.

That bound is the whole point. A title match scores roughly six times a
body-only match, so a 2× recency swing reorders notices within a relevance tier
but can never lift a passing mention above a notice actually about the term.

## The numbers

All are overridable by environment variable, so a deployment can retune without
a code change.

| Constant | Default | Effect |
|---|---|---|
| `RECENCY_DECAY_FLOOR` | `0.5` | share of score recency cannot remove. Lower favours recent notices harder; `0` deletes old ones entirely |
| `RECENCY_DECAY_SCALE` | `365d` | how quickly the curve falls |
| `RECENCY_DECAY_OFFSET` | `30d` | grace period before any decay |
| `RECENCY_DECAY_FACTOR` | `0.5` | curve value one scale past the offset |
| `MIN_SEARCH_RESULTS` | `5` | below this, escalate to the next phase. Escalating only on zero would strand a misspelling that also appears in the notices themselves |
| `MAX_SEARCH_RESULTS` | `2000` | cap on ids returned to the notice list |
| `MAX_FILTERED_SEARCH_RESULTS` | `10000` | cap for the filter views, which intersect the result with a date or banner afterwards and so need more headroom. Also Elasticsearch's default `max_result_window` |
| `TIERED_RELEVANCE` | on | group equally relevant notices and date-order each group; `0` restores plain score order |

The caps are paid for twice — Elasticsearch sorts that many hits, and the caller
then orders that many ids in a `Case`/`When` at roughly 0.2ms an id. Measured on
this corpus, one page of the heaviest query costs 0.5s at 1000, 0.7s at 2000 and
1.5s at 10000, which is why the list view stops at 2000 while the filter views,
which have to intersect afterwards, do not.

`title^5` and the clause boosts are not configurable; they are structural to the
query and are asserted by the tests.

## Sort modes

The frontend sends `sort=relevance` or `sort=date`.

**Relevance** groups the results into the tiers above, orders the title tiers by
date and leaves the weak tiers in score order.

**Date** pushes `datetime_modified desc` into Elasticsearch and drops the
scoring block entirely. This matters more than it looks: the query is capped at
`MAX_SEARCH_RESULTS`, so whatever Elasticsearch sorts by decides *which* notices
survive the cut. Sorting by score and reordering afterwards silently drops
recent-but-weak matches, which is exactly what it used to do.

"Most Recent" therefore means the newest `MAX_SEARCH_RESULTS` matches, not all
of them, and `datetime_modified` means last edited — a revised notice resurfaces.

## When Elasticsearch is down

Every failure inside `get_ranked_notice_ids` is re-raised as
`ElasticsearchUnavailable`. Both callers catch it and fall back to PostgreSQL
full-text search — `postgres_search` in `utils/filters.py`, weighted `A` on the
title and `B` on the body so relevance ordering still roughly holds. Search gets
worse; it does not break.

## What changed in August 2026

Search returned HTTP 500 on every keyword for four days. The cause was outside
this repo: `omniport-backend` was checked out from `elastic` onto `master`,
which does not carry `settings/third_party/elastic.py`, so `ELASTICSEARCH_DSL`
was undefined and the connection lookup raised. Fixing that exposed four ranking
defects, all now closed and all covered by tests:

1. **Recency annihilated relevance.** The decay was a bare gaussian multiplier
   at `scale=60d, decay=0.20`, reaching `3.6e-26` at one year and underflowing
   to zero by five. Searching `google` gave 6 genuinely relevant results in the
   top 50; the other 44 were placement notices that linked a Google Form. Now 40.
2. **"Most Recent" sorted after the cut-off.** For `exam`, 362 of the 1000
   newest matching notices never reached the caller.
3. **A typo that exists in the corpus blocked correction.** Phases escalated
   only on zero results, so `intership` matched the four notices that share the
   misspelling and stopped, returning 4 where ~1968 were available.
4. **Multi-word queries were gated behind adjacency.** `bio data final year`
   returned 6 of 1620, because most notices read "Bio Data **for** Final Year".

Ordering by score was then replaced by the tiers described above. With the four
defects fixed the top of the results was right, but inside a group of equally
relevant notices the order was arbitrary — 107 title matches for `microsoft`
sorted by how short their titles were. Tiers keep the groups in relevance order
and run each group newest first, and the cap moved from 1000 to 2000 so the
grouping operates on more of the match set.

A fifth, unrelated defect was also fixed: marking a notice read returned 403,
because the frontend reads its CSRF cookie under a deployment-specific name that
Django was not writing. That fix is `CSRF_COOKIE_NAME` in
`omniport/settings/base/security.py`.

## Tests

```
python -m unittest discover --start-directory tests --verbose
```

42 tests, well under a second, and they need **neither Django nor a running
Elasticsearch** — only `elasticsearch-dsl`, which is pure Python. CI runs them
on every push and pull request via `.github/workflows/tests.yml`.

They can do this because the ranking decisions do not touch the database:
`_wrap_with_recency_decay` returns a dict, `_build_phases` returns query objects
with a `.to_dict()`, and `_run_phase` takes the client as an argument.
`tests/test_search_ranking.py` loads `utils/search.py` directly with `importlib`
so the code under test is the code that ships, and hands it a `FakeElasticsearch`
that records the request body and replays canned hits.

Five groups:

**`TestRecencyDecayShape`** recomputes the gaussian in the test at ages from 0 to
10 years and checks the resulting multiplier stays inside `[FLOOR, 1.0]`, that
the floor is above zero at all, and that the swing stays under 3×. This is the
group that fails if anyone reintroduces defect 1.

**`TestFieldWeights`** asserts the query DSL itself — `title^5` present in all
three phases, the prefix clause at boost 5, the wildcard at boost 2,
`minimum_should_match` of `2<75%` on relaxed, `fuzziness=AUTO` on fuzzy, and that
no phase can return a draft.

**`TestSortMode`** asserts that a relevance search carries a `function_score` and
no explicit sort, and that a date search carries an Elasticsearch `sort` and **no**
`function_score`. That second assertion is defect 2 written down.

**`TestPhaseOrchestration`** drives the whole function against the fake client:
relaxed runs even when strict found plenty, fuzzy is skipped when it should be
and runs when it should be, ids are de-duplicated with the stricter phase keeping
the better rank, a date sort is reapplied across the merged phases, the result is
truncated to `size`, and a failing client raises `ElasticsearchUnavailable`.

**`TestRelevanceTiers`** covers the grouping: every strict clause carries its
name, each combination of names maps to the right tier, a hit with no names at
all still gets one, a stronger tier beats a weaker one however old it is, each
tier runs newest first, a notice found twice keeps its strongest tier, the weak
tiers keep the order Elasticsearch scored them in, a date search is untouched,
and the flag turns the whole thing off.

### These tests were checked against real defects

Each defect was reintroduced on a throwaway copy to confirm a test notices:

| Mutation | Caught by |
|---|---|
| escalate on any hit | 5 tests in `TestPhaseOrchestration` |
| score the date sort | `test_a_date_sort_is_pushed_down_into_elasticsearch` |
| remove `title^5` | 2 tests in `TestFieldWeights` |
| weaken the prefix clause | `test_a_partly_typed_word_is_scored_against_the_title` |
| let drafts through | `test_no_phase_can_ever_return_a_draft` |
| set the floor to zero | 2 tests in `TestRecencyDecayShape` |
| invert the tier order | 4 tests in `TestRelevanceTiers` |
| date-order the weak tiers as well | 2 tests in `TestRelevanceTiers` |
| drop a clause name | `test_every_strict_clause_is_named_so_a_tier_can_be_read_back` |
| let a later phase overwrite the tier | 2 tests across both merge groups |
| ignore the tier and keep score order | 3 tests in `TestRelevanceTiers` |

Worth repeating if the suite is extended. A test that cannot fail proves
nothing, and doing this found a real weakness: the original floor assertion
compared against the module's own floor, so setting that floor to zero made the
test pass vacuously.

## Relevance harness

The unit tests prove the query is built as intended. They cannot prove the
results are any good — that needs real notices.

```
docker exec <django-container> bash -c \
    'cd /omniport && DJANGO_SETTINGS_MODULE=omniport.settings.settings \
     python apps/noticeboard/scripts/relevance_eval.py'
```

30 queries chosen from what this noticeboard actually contains — companies,
placement and academic phrases, hostel names, acronyms and misspellings. Each
result in the top 30 is graded **strong** (every query word in the title),
**partial** (some in the title, or all in the body) or **junk**, and each query
carries a floor it must hold. The script exits non-zero if any query drops below
its floor, so it can gate a release.

The last column is a histogram of the tiers the top 30 came from — `T=` the
phrase in the title, `T~` a partly typed word, `C=` the phrase in the body, `T*`
a fragment inside a word, `rx` relaxed, `fz` fuzzy. Read it alongside the
precision: it is what showed that date-ordering the fuzzy tier had broken the
misspelling cases, since every regressed query read `fz30`.

`scripts/corpus_profile.py` prints the most common words, phrases and banners in
the corpus. Use it to pick new cases that reflect what people really search.

**Read the results, not only the number.** The grader scores token overlap, so it
cannot tell a notice about Google from one that merely links a Google Form: it
reports 100% for `google` where reading the top 30 by hand gives 23/30. It is a
regression detector, not a measure of quality.

Three cases sit below the rest for reasons that are not defects, documented in
the script: `gate` matches Gateway and Gates, `ganga bhawan` has only two real
matches in the whole corpus, and one `scholarship` hit is a notice whose own
typo joins two words.

## Known limitations

- **The cap is real.** A query matching more than `MAX_SEARCH_RESULTS` notices
  returns only that many, and the count shown to the user is the capped number.
  Three of the thirty harness queries exceed 2000. Elasticsearch will serve
  10,000 without a reindex, but the `Case`/`When` that reapplies the order costs
  about 0.2ms an id, so raising it trades a second of page load for coverage of
  the most generic queries.
- **Boilerplate ranks.** "Google Form" appears in 5% of notice bodies, so about
  7 of the top 30 for `google` are notices titled after a form. Demoting the
  phrase would fix it at the cost of hand-tuning for one phrase.
- **A prefix must be a real prefix.** `gogl` finds "Goel", not "Google": it is
  not a substring, so the wildcard misses, and it is two edits away, so fuzzy
  misses. An edge-ngram field on the title would fix this, and needs a reindex.
- **Banner and creation date are not indexed.** Searching a department or hostel
  name finds only notices that happen to mention it in the title or body, and
  the date filter intersects after the cut-off rather than filtering inside
  Elasticsearch. Both would need `documents.py` changes and a full reindex.
