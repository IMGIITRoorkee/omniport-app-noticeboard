"""
Tests for how notice search ranks and how much of it comes back

These drive the real query builders in `utils/search.py`. Django is not needed
to run them, because none of the ranking decisions touch the ORM: the phase
builders return Elasticsearch DSL objects, the recency wrapper is a dict, and
`_run_phase` takes the client as an argument. `elasticsearch_dsl` is installed
rather than stubbed, since it is pure Python and needs no server, and stubbing
`Q` would mean asserting against our own fake instead of the query the cluster
would really receive. The client itself is a stand-in that records the bodies
it was handed and replays canned hits.

Each group names the defect it holds shut. All four were live on stage in
August 2026 and were found by hand, because this app had no tests.
"""

import importlib.util
import math
import pathlib
import unittest

APP = pathlib.Path(__file__).resolve().parent.parent


def _load_search_module():
    """
    Load utils/search.py without importing the noticeboard package

    Only `logging` and `os` are imported at its top level; everything that
    needs Elasticsearch is imported inside the functions, so the module loads
    on its own.
    """

    path = APP / 'utils/search.py'
    spec = importlib.util.spec_from_file_location('noticeboard_search', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


search = _load_search_module()


class FakeElasticsearch:
    """
    Stands in for the client, recording bodies and replaying canned hits

    `responses` holds one list of (id, datetime_modified) pairs per phase, in
    the order the phases run, so a test can say what strict, relaxed and fuzzy
    each return. Running out of responses means the phase was not expected to
    run at all, and yields nothing.
    """

    def __init__(self, responses=None, raises=None):
        self.responses = list(responses or [])
        self.raises = raises
        self.bodies = []

    def search(self, index, body, request_timeout=None):
        if self.raises is not None:
            raise self.raises

        self.bodies.append(body)
        hits = self.responses.pop(0) if self.responses else []

        return {
            'hits': {
                'total': {'value': len(hits)},
                'hits': [
                    {'_source': {'id': pk, 'datetime_modified': modified}}
                    for pk, modified in hits
                ],
            }
        }


class ConnectionsStub:
    """
    Stands in for elasticsearch_dsl.connections, handing back one client
    """

    def __init__(self, client):
        self.client = client

    def get_connection(self, *args, **kwargs):
        return self.client


def _use_client(client):
    """
    Point `get_ranked_notice_ids` at a stand-in client

    It resolves the connection inside the function body, so the attribute on
    the real connections singleton is swapped and handed back for restoring.
    """

    from elasticsearch_dsl import connections as connections_module

    original = connections_module.connections.get_connection
    connections_module.connections.get_connection = (
        ConnectionsStub(client).get_connection
    )
    return connections_module, original


def _restore_client(connections_module, original):
    connections_module.connections.get_connection = original


def _days(value):
    """
    Turn an Elasticsearch day span such as '365d' into a number
    """

    if not value.endswith('d'):
        raise AssertionError(f'expected a span in days, got {value!r}')
    return float(value[:-1])


def _multiplier_from(function_score, age_in_days):
    """
    Work out what the recency block multiplies a score by at a given age

    Mirrors Elasticsearch: the gaussian is exp(-max(0, age - offset)^2 / 2s^2)
    where s^2 is chosen so the curve equals `decay` one `scale` past the
    offset. The two functions are then summed, because score_mode is sum.
    """

    functions = function_score['functions']
    gauss = next(f for f in functions if 'gauss' in f)
    constant = next(f for f in functions if 'gauss' not in f)

    field = gauss['gauss']['datetime_modified']
    scale = _days(field['scale'])
    offset = _days(field['offset'])
    decay = field['decay']

    sigma_squared = -(scale ** 2) / (2 * math.log(decay))
    distance = max(0.0, age_in_days - offset)
    curve = math.exp(-(distance ** 2) / (2 * sigma_squared))

    return curve * gauss['weight'] + constant['weight']


def _should_clause(query, kind):
    """
    Pull one clause out of the strict phase's should list by its query type
    """

    for clause in query.to_dict()['bool']['should']:
        if kind in clause:
            return clause[kind]
    raise AssertionError(f'no {kind!r} clause in {query.to_dict()}')


def _phases(keyword='google'):
    return dict(search._build_phases(keyword))


AGES_IN_DAYS = [0, 30, 60, 180, 365, 730, 1825, 3650]


class TestRecencyDecayShape(unittest.TestCase):
    """
    Recency may reorder equally good matches; it may not erase old ones

    The original block was a bare gaussian multiplier at scale 60d and decay
    0.20, which reached 3.6e-26 at one year and underflowed to zero by five.
    A perfect title match from 2023 scored 37.9 and then lost to a week-old
    notice that only said 'Google Form'.
    """

    def setUp(self):
        self.function_score = search._wrap_with_recency_decay(
            {'match_all': {}}
        )['function_score']

    def test_there_is_a_floor_at_all(self):
        """
        This is the finding. A floor of zero is the old behaviour restored.

        Asserted separately from the shape below, which compares against the
        configured floor and would pass vacuously if that floor were zero.
        """

        self.assertGreater(
            search.RECENCY_DECAY_FLOOR,
            0.0,
            'without a floor the gaussian decays to zero, so age multiplies '
            'relevance out of existence rather than ordering it',
        )

    def test_the_multiplier_never_falls_below_the_floor(self):
        """
        The curve has to stay inside the band the floor promises
        """

        floor = search.RECENCY_DECAY_FLOOR

        for age in AGES_IN_DAYS:
            with self.subTest(age_in_days=age):
                multiplier = _multiplier_from(self.function_score, age)
                self.assertGreaterEqual(
                    multiplier,
                    floor,
                    f'a notice {age} days old is multiplied by {multiplier}, '
                    f'below the floor of {floor}; recency is deleting '
                    f'relevance rather than ordering it',
                )

    def test_the_multiplier_never_exceeds_one(self):
        """
        Recency is a discount on stale notices, not a bonus on fresh ones
        """

        for age in AGES_IN_DAYS:
            with self.subTest(age_in_days=age):
                self.assertLessEqual(
                    _multiplier_from(self.function_score, age), 1.0
                )

    def test_a_fresh_notice_keeps_its_whole_score(self):
        self.assertAlmostEqual(
            _multiplier_from(self.function_score, 0), 1.0, places=6
        )

    def test_recency_can_only_swing_a_score_so_far(self):
        """
        Relevance decides the tier, recency only orders within it

        A title match scores roughly six times a body-only match, so as long
        as the swing stays well under that, no amount of age moves a body
        match above a title match.
        """

        newest = _multiplier_from(self.function_score, 0)
        ancient = _multiplier_from(self.function_score, max(AGES_IN_DAYS))

        self.assertLessEqual(
            newest / ancient,
            3.0,
            'recency can swing a score by more than 3x, which is enough to '
            'lift a body-only match above a title match',
        )

    def test_the_scores_are_summed_and_then_multiplied_in(self):
        """
        score_mode must be sum: multiply would collapse the floor to zero
        """

        self.assertEqual(self.function_score['score_mode'], 'sum')
        self.assertEqual(self.function_score['boost_mode'], 'multiply')

    def test_there_is_a_curve_and_a_floor_and_they_add_up(self):
        functions = self.function_score['functions']
        self.assertEqual(len(functions), 2, functions)

        gauss = next(f for f in functions if 'gauss' in f)
        constant = next(f for f in functions if 'gauss' not in f)

        self.assertAlmostEqual(
            gauss['weight'] + constant['weight'], 1.0, places=6
        )
        self.assertAlmostEqual(
            constant['weight'], search.RECENCY_DECAY_FLOOR, places=6
        )


class TestFieldWeights(unittest.TestCase):
    """
    The title outranks the body, and a partial word still finds the title
    """

    def test_the_title_outweighs_the_body_in_every_phase(self):
        for name, query in _phases().items():
            with self.subTest(phase=name):
                self.assertIn(
                    'title^5',
                    str(query.to_dict()),
                    f'the {name} phase no longer boosts the title, so a '
                    f'passing mention in a long body ranks as high as a '
                    f'notice actually about the term',
                )

    def test_the_strict_phase_matches_the_whole_phrase_in_order(self):
        clause = _should_clause(_phases()['strict'], 'multi_match')
        self.assertEqual(clause['type'], 'phrase')
        self.assertEqual(clause['fields'], ['title^5', 'content'])

    def test_a_partly_typed_word_is_scored_against_the_title(self):
        """
        'micro' and 'microsoft' are different tokens, so title^5 cannot fire.
        The wildcard matches but is constant-scored, so before the prefix
        clause existed the first Microsoft notice sat at rank 71.
        """

        clause = _should_clause(_phases()['strict'], 'match_phrase_prefix')
        self.assertEqual(clause['title']['boost'], 5)
        self.assertEqual(clause['title']['max_expansions'], 50)

    def test_the_wildcard_still_catches_a_fragment_mid_word(self):
        """
        This is what makes 'goog' and 'amaz' work, so it has to stay
        """

        clause = _should_clause(_phases()['strict'], 'wildcard')
        self.assertEqual(clause['title']['boost'], 2)
        self.assertIn('*', clause['title']['value'])

    def test_one_strict_clause_is_enough_to_match(self):
        self.assertEqual(
            _phases()['strict'].to_dict()['bool']['minimum_should_match'], 1
        )

    def test_the_relaxed_phase_asks_for_most_of_the_words(self):
        must = _phases()['relaxed'].to_dict()['bool']['must']
        clause = next(c['multi_match'] for c in must if 'multi_match' in c)

        self.assertEqual(clause['type'], 'best_fields')
        self.assertEqual(clause['minimum_should_match'], '2<75%')

    def test_the_fuzzy_phase_tolerates_a_misspelling(self):
        must = _phases()['fuzzy'].to_dict()['bool']['must']
        clause = next(c['multi_match'] for c in must if 'multi_match' in c)

        self.assertEqual(clause['fuzziness'], 'AUTO')
        self.assertEqual(clause['prefix_length'], 1)
        self.assertEqual(clause['max_expansions'], 50)

    def test_no_phase_can_ever_return_a_draft(self):
        for name, query in _phases().items():
            with self.subTest(phase=name):
                self.assertIn(
                    {'term': {'is_draft': False}},
                    query.to_dict()['bool']['must'],
                    f'the {name} phase no longer excludes drafts, so unpublished '
                    f'notices are searchable',
                )


class TestSortMode(unittest.TestCase):
    """
    Sorting by date must happen in Elasticsearch, not after the cut-off

    Ranking by score and then reordering the top 1000 by date hides recent
    but weakly matching notices entirely. For 'exam', 362 of the 1000 newest
    matches never reached the caller.
    """

    def setUp(self):
        self.query = _phases()['strict']

    def _body_for(self, sort_by_relevance):
        client = FakeElasticsearch(responses=[[]])
        search._run_phase(client, self.query, 25, sort_by_relevance)
        return client.bodies[0]

    def test_relevance_scores_the_results_and_lets_the_score_order_them(self):
        body = self._body_for(sort_by_relevance=True)

        self.assertIn('function_score', body['query'])
        self.assertNotIn(
            'sort',
            body,
            'a relevance search must not pin an order, or the score is wasted',
        )

    def test_a_date_sort_is_pushed_down_into_elasticsearch(self):
        """
        This is the finding. Sorting after truncation dropped recent notices.
        """

        body = self._body_for(sort_by_relevance=False)

        self.assertEqual(
            body['sort'], [{'datetime_modified': {'order': 'desc'}}]
        )
        self.assertNotIn(
            'function_score',
            body['query'],
            'scoring a date sort makes the cut-off keep the most relevant '
            'thousand and then reorder them, which is the bug this replaced',
        )

    def test_only_the_fields_needed_to_order_and_fetch_are_returned(self):
        for relevance in (True, False):
            with self.subTest(sort_by_relevance=relevance):
                body = self._body_for(relevance)
                self.assertEqual(
                    body['_source'], ['id', 'datetime_modified']
                )

    def test_the_caller_decides_how_many_results_come_back(self):
        client = FakeElasticsearch(responses=[[]])
        search._run_phase(client, self.query, 7, True)
        self.assertEqual(client.bodies[0]['size'], 7)


class TestPhaseOrchestration(unittest.TestCase):
    """
    Strict and relaxed always both run; fuzzy is only for misspellings

    Escalating only on zero results meant 'intership' matched the four notices
    that share the typo and stopped, returning 4 where 1968 were available.
    Gating relaxed behind exact adjacency meant 'bio data final year' returned
    6 of 1620, because most notices read 'Bio Data for Final Year'.
    """

    def setUp(self):
        self.client = None
        self.connections_module = None
        self.original = None

    def tearDown(self):
        if self.connections_module is not None:
            _restore_client(self.connections_module, self.original)

    def _run(self, responses, **kwargs):
        self.client = FakeElasticsearch(responses=responses)
        self.connections_module, self.original = _use_client(self.client)
        return search.get_ranked_notice_ids('anything', **kwargs)

    @staticmethod
    def _hits(count, start=1):
        return [(pk, f'2026-01-{pk:02d}T00:00:00+00:00')
                for pk in range(start, start + count)]

    def test_relaxed_runs_even_when_strict_already_found_plenty(self):
        """
        This is the finding for multi-word queries.
        """

        plenty = search.MIN_SEARCH_RESULTS + 5
        self._run([self._hits(plenty), self._hits(3, start=100)])

        self.assertEqual(
            len(self.client.bodies),
            2,
            'strict and relaxed must both run: requiring the words to be '
            'adjacent is too narrow a reading of a multi-word query',
        )

    def test_fuzzy_is_skipped_once_enough_real_matches_exist(self):
        plenty = search.MIN_SEARCH_RESULTS + 5
        self._run([self._hits(plenty), []])

        self.assertEqual(len(self.client.bodies), 2)

    def test_fuzzy_runs_when_the_real_matches_are_too_few(self):
        """
        This is the finding for typos that also appear in the notices.
        """

        thin = max(0, search.MIN_SEARCH_RESULTS - 3)
        self._run([self._hits(thin), [], self._hits(20, start=200)])

        self.assertEqual(
            len(self.client.bodies),
            3,
            'a query matching only a handful of notices must fall through to '
            'the fuzzy phase, or a misspelling that exists in the corpus '
            'returns just the notices that share the misspelling',
        )

    def test_a_notice_matched_by_two_phases_is_returned_once(self):
        found = self._run([
            [(1, '2026-01-01T00:00:00+00:00'), (2, '2026-01-02T00:00:00+00:00')],
            [(2, '2026-01-02T00:00:00+00:00'), (3, '2026-01-03T00:00:00+00:00')],
        ])

        self.assertEqual(found, [1, 2, 3])

    def test_the_stricter_phase_keeps_the_better_ranks(self):
        """
        Merging must not let a fuzzy guess outrank an exact match
        """

        found = self._run([
            [(10, '2020-01-01T00:00:00+00:00')],
            [(20, '2026-01-01T00:00:00+00:00')],
            [(30, '2026-06-01T00:00:00+00:00')],
        ])

        self.assertEqual(found[0], 10, found)

    def test_a_date_sort_is_reapplied_across_the_merged_phases(self):
        """
        Each phase is ordered on its own, so the union needs sorting again
        """

        found = self._run(
            [
                [(1, '2020-05-05T00:00:00+00:00')],
                [(2, '2026-08-01T00:00:00+00:00')],
                [(3, '2023-02-02T00:00:00+00:00')],
            ],
            sort_by_relevance=False,
        )

        self.assertEqual(found, [2, 3, 1])

    def test_no_more_than_the_requested_number_come_back(self):
        found = self._run([self._hits(4), self._hits(4, start=50)], size=3)
        self.assertEqual(len(found), 3)

    def test_a_cluster_that_refuses_the_query_is_reported_as_unavailable(self):
        """
        The callers fall back to PostgreSQL on this, so it must be this type
        """

        self.client = FakeElasticsearch(raises=RuntimeError('cluster down'))
        self.connections_module, self.original = _use_client(self.client)

        with self.assertRaises(search.ElasticsearchUnavailable):
            search.get_ranked_notice_ids('anything')


if __name__ == '__main__':
    unittest.main()
