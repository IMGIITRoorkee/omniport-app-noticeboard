"""
Graded relevance evaluation for noticeboard Elasticsearch search.

Run it inside the Django container:

    docker exec <django-container> bash -c \
        'cd /omniport && DJANGO_SETTINGS_MODULE=omniport.settings.settings \
         python apps/noticeboard/scripts/relevance_eval.py'

Each query is run through the live search code and the top N results are
graded:

    strong   every query token appears in the title
    partial  some tokens in the title, or every token in the body
    junk     neither

Boilerplate phrases are stripped from the body before grading, otherwise the
5% of notices that link a Google Form all count as relevant hits for 'google'.

Every case carries the precision it must hold. The script exits non-zero if any
query falls below its floor, so it can gate a release rather than being read and
forgotten. The floors sit a little under the figures measured in August 2026,
because the index grows and a point or two of drift is not a regression.

Read the results, do not only read the number. The grader scores token overlap,
so it cannot tell a notice about Google from one that merely links a Google
Form: it reports 100% for 'google' where reading the top 30 by hand gives 23/30.
It is a regression detector, not a measure of quality.

Three cases are known to sit below the rest, for reasons that are not defects:

    gate           'Gateway.fm' and 'Gates foundation' are real prefix
                   expansions of the query, just not the GATE exam. No purely
                   lexical scheme separates them.
    ganga bhawan   only two notices genuinely match, so the query escalates
                   past the strict phase whatever the threshold is.
    scholarship    one hit is 'Aaryam Foundation Scholarshipfor Excellence', a
                   notice whose own typo joins two words. Prefix matching finds
                   it correctly; the grader cannot see it as a token.
"""

import re
import sys

import django

django.setup()

from noticeboard.documents import strip_html_tags
from noticeboard.models import Notice
from noticeboard.utils.search import get_ranked_notice_ids

TOP_N = 30

BOILERPLATE = [
    'google form', 'google forms', 'google meet', 'google drive',
    'google sheet', 'google doc', 'registration link', 'click here',
]

STOP = set(
    'for the and of to in a an is are on at with by from be this that as or '
    'all last will has have not you your it its shall may can we us our'.split()
)

# query, category, term to grade against when it differs, precision floor
CASES = [
    ('google', 'company', None, 0.90),
    ('microsoft', 'company', None, 0.90),
    ('tata steel', 'company', None, 0.90),
    ('ola electric', 'company', None, 0.90),
    ('goldman sachs', 'company', None, 0.90),
    ('shortlist for interviews', 'placement', None, 0.90),
    ('bio data submission', 'placement', None, 0.90),
    ('pre-final year', 'placement', None, 0.90),
    ('summer internship', 'placement', None, 0.90),
    ('off campus', 'placement', None, 0.90),
    ('deadline extended', 'placement', None, 0.90),
    ('viva-voce examination', 'academic', None, 0.90),
    ('ph.d viva', 'academic', None, 0.90),
    ('mid-term examination', 'academic', None, 0.90),
    ('autumn semester', 'academic', None, 0.90),
    ('spring semester', 'academic', None, 0.90),
    ('room allotment', 'campus', None, 0.90),
    ('cautley bhawan', 'campus', None, 0.90),
    ('ganga bhawan', 'campus', None, 0.80),
    ('hostel', 'campus', None, 0.90),
    ('fee waiver', 'finance', None, 0.90),
    ('tuition fee', 'finance', None, 0.90),
    ('scholarship', 'finance', None, 0.90),
    ('jrf', 'acronym', None, 0.90),
    ('gate', 'acronym', None, 0.80),
    ('gogle', 'typo', 'google', 0.90),
    ('hostl', 'typo', 'hostel', 0.90),
    ('intership', 'typo', 'internship', 0.90),
    ('scholarshp', 'typo', 'scholarship', 0.90),
    ('bhawn', 'typo', 'bhawan', 0.90),
]


def normalise(text):
    return ' ' + re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).strip() + ' '


def significant_tokens(term):
    return [
        token for token in normalise(term).split()
        if len(token) > 2 and token not in STOP
    ]


def grade(tokens, title, body):
    """
    Grade a single result against the query tokens
    :param tokens: the significant tokens of the query
    :param title: the notice title
    :param body: the notice body, HTML already stripped
    :return: 2 for a strong hit, 1 for a partial one, 0 for junk
    """

    normalised_title = normalise(title)
    in_title = [
        token for token in tokens
        if ' ' + token + ' ' in normalised_title
    ]

    if tokens and len(in_title) == len(tokens):
        return 2

    normalised_body = normalise(body)
    for phrase in BOILERPLATE:
        normalised_body = normalised_body.replace(' ' + phrase + ' ', ' ')

    in_body = [
        token for token in tokens
        if ' ' + token + ' ' in normalised_body
    ]

    if in_title:
        return 1
    if tokens and len(in_body) == len(tokens):
        return 1
    return 0


def evaluate(query, judge_as=None):
    notice_id_list = get_ranked_notice_ids(query, sort_by_relevance=True)
    top = notice_id_list[:TOP_N]

    notices = {notice.id: notice for notice in Notice.objects.filter(id__in=top)}
    ordered = [notices[pk] for pk in top if pk in notices]

    tokens = significant_tokens(judge_as or query)
    grades = [
        grade(tokens, notice.title, strip_html_tags(notice.content or ''))
        for notice in ordered
    ]

    return notice_id_list, ordered, grades


def main():
    """
    Grade every case and report
    :return: the process exit status, non-zero if any query is below its floor
    """

    print('%-26s %-9s %6s   %s' % (
        'query', 'category', 'hits',
        'top%d: strong / partial / junk    P@%d  floor' % (TOP_N, TOP_N)))
    print('-' * 100)

    results = []
    below_floor = []

    for query, category, judge_as, floor in CASES:
        notice_id_list, ordered, grades = evaluate(query, judge_as)

        strong = grades.count(2)
        partial = grades.count(1)
        junk = grades.count(0)
        precision = (strong + partial) / len(grades) if grades else 0.0

        failed = precision < floor
        if failed:
            below_floor.append((query, precision, floor))

        print('%-26s %-9s %6d   %2d / %2d / %2d           %3.0f%%  %3.0f%% %s' % (
            query, category, len(notice_id_list), strong, partial, junk,
            100 * precision, 100 * floor, 'BELOW FLOOR' if failed else ''))
        results.append((query, precision, junk, ordered, grades))

    print()
    print('=' * 100)
    print('WORST PERFORMERS, with examples of what was graded junk')
    print('=' * 100)

    for query, precision, junk, ordered, grades in sorted(
            results, key=lambda row: row[1])[:5]:
        if not junk:
            continue
        print()
        print('%s  (P@%d = %.0f%%, %d junk)' % (query, TOP_N, 100 * precision, junk))
        shown = 0
        for notice, notice_grade in zip(ordered, grades):
            if notice_grade == 0 and shown < 4:
                print('    %s' % (notice.title or '')[:74])
                shown += 1

    print()
    if below_floor:
        print('FAILED: %d of %d queries are below their floor' % (
            len(below_floor), len(CASES)))
        for query, precision, floor in below_floor:
            print('    %-26s %.0f%%, needs %.0f%%' % (
                query, 100 * precision, 100 * floor))
        return 1

    print('PASSED: all %d queries are at or above their floor' % len(CASES))
    return 0


if __name__ == '__main__':
    sys.exit(main())
