#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from flask import current_app
from pony.orm import db_session

from mini_fiction.models import Story, Chapter


def initsphinx():
    sys.stderr.write(' Cleaning...')
    sys.stderr.flush()
    with current_app.sphinx as sphinx:
        sphinx.delete('stories', id__gte=0)
    with current_app.sphinx as sphinx:
        sphinx.delete('chapters', id__gte=0)
    sys.stderr.write('\n')
    sys.stderr.flush()

    ok = 0
    pk = 0
    stories = None
    with db_session:
        count = Story.select().count()
    while True:
        with db_session:
            stories = tuple(Story.select(lambda x: x.id > pk).prefetch(
                Story.contributors,
                Story.characters,
                Story.categories,
                Story.classifications,
            ).order_by(Story.id)[:100])
            if not stories:
                break

            Story.bl.add_stories_to_search(stories)
            pk = stories[-1].id
            ok += len(stories)
            sys.stderr.write(' [%.1f%%] %d/%d stories\r' % (ok * 100 / count, ok, count))
            sys.stderr.flush()

    with current_app.sphinx as sphinx:
        sphinx.flush('stories')

    sys.stderr.write('\n')

    ok = 0
    pk = 0
    chapters = None
    with db_session:
        count = Chapter.select().count()
    while True:
        with db_session:
            chapters = tuple(Chapter.select(lambda x: x.id > pk).order_by(Chapter.id)[:20])
            if not chapters:
                break

            Chapter.bl.add_chapters_to_search(chapters)
            pk = chapters[-1].id
            ok += len(chapters)
            sys.stderr.write(' [%.1f%%] %d/%d chapters\r' % (ok * 100 / count, ok, count))
            sys.stderr.flush()

    with current_app.sphinx as sphinx:
        sphinx.flush('chapters')

    sys.stderr.write('\n')
    sys.stderr.flush()
