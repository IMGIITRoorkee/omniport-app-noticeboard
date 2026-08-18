"""
Profile the noticeboard corpus: vocabulary, phrases, banners and boilerplate.

Run it inside the Django container:

    docker exec <django-container> bash -c \
        'cd /omniport && DJANGO_SETTINGS_MODULE=omniport.settings.settings \
         python apps/noticeboard/scripts/corpus_profile.py'

Use it to pick realistic queries for relevance_eval.py, and to spot phrases
that are common enough to pollute ranking.
"""

import collections
import random
import re

import django

django.setup()

from django.db.models import Count

from noticeboard.documents import strip_html_tags
from noticeboard.models import Notice

BODY_SAMPLE = 1500

STOP = set(
    'for the and of to in a an is are on at with by from be this that as or '
    'notice notices submission student students final year regarding all '
    'dated date last will has have been not you your it its shall may can '
    'we us our who whom which'.split()
)

BOILERPLATE = [
    'google form', 'click here', 'interested students', 'last date',
    'kindly note', 'for further', 'registration link', 'apply through',
    'shortlisted candidates', 'attached herewith', 'fill the form',
    'reporting time', 'venue', 'eligible students',
]


def tokenise(text):
    return [
        word.strip('.-')
        for word in re.findall(r'[a-zA-Z][a-zA-Z\.\-]{2,}', (text or '').lower())
    ]


def report_titles(titles):
    words = collections.Counter()
    bigrams = collections.Counter()

    for title in titles:
        tokens = [word for word in tokenise(title) if len(word) > 2]
        for word in tokens:
            if word not in STOP:
                words[word] += 1
        for first, second in zip(tokens, tokens[1:]):
            if first not in STOP and second not in STOP:
                bigrams[first + ' ' + second] += 1

    print()
    print('=== most common title words ===')
    for word, count in words.most_common(40):
        print('   %-26s %6d' % (word, count))

    print()
    print('=== most common title bigrams ===')
    for phrase, count in bigrams.most_common(30):
        print('   %-34s %6d' % (phrase, count))


def report_banners():
    print()
    print('=== top banners by notice count ===')
    rows = (
        Notice.objects.filter(is_draft=False)
        .values('banner__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    total = Notice.objects.filter(is_draft=False).count()
    for row in rows:
        print('   %-46s %6d  (%.0f%%)' % (
            row['banner__name'], row['count'], 100.0 * row['count'] / total))


def report_boilerplate(bodies):
    print()
    print('=== boilerplate frequency in bodies (sample of %d) ===' % len(bodies))
    counts = collections.Counter()
    for body in bodies:
        stripped = strip_html_tags(body or '').lower()
        for phrase in BOILERPLATE:
            if phrase in stripped:
                counts[phrase] += 1
    for phrase, count in counts.most_common():
        print('   %-26s %5d  (%.0f%% of notices)' % (
            phrase, count, 100.0 * count / len(bodies)))


def main():
    rows = list(
        Notice.objects.filter(is_draft=False).values_list('title', 'content')
    )
    print('notices analysed: %d' % len(rows))

    random.seed(7)
    print()
    print('=== a random sample of real titles ===')
    for title, _ in random.sample(rows, min(12, len(rows))):
        print('   %s' % (title or '')[:88])

    report_titles([title for title, _ in rows])
    report_banners()
    report_boilerplate([
        content for _, content in random.sample(rows, min(BODY_SAMPLE, len(rows)))
    ])


if __name__ == '__main__':
    main()
