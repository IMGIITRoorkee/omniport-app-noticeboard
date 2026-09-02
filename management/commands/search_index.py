from importlib import import_module

from django.core.management.base import BaseCommand, CommandError
from elasticsearch_dsl.connections import connections

from noticeboard.documents import NoticeDocument


class Command(BaseCommand):

    @staticmethod
    def _should_refresh_notice_index(argv):
        return any(flag in argv for flag in ('--rebuild', '--populate'))

    def run_from_argv(self, argv):
        try:
            upstream_module = import_module(
                'django_elasticsearch_dsl.management.commands.search_index'
            )
            upstream_command = upstream_module.Command()
            result = upstream_command.run_from_argv(argv)
        except Exception as exc:
            raise CommandError(
                'Unable to load django-elasticsearch-dsl search_index command.'
            ) from exc

        # --rebuild and --populate have already written every document by the
        # time the upstream command returns; what they do not do is make the
        # writes searchable, so a rebuild followed straight away by a search
        # comes back short. Refreshing the index opens a new segment reader,
        # which is all that is missing. Indexing the corpus a second time
        # would achieve the same visibility at the cost of re-reading every
        # row from PostgreSQL and re-sending every document.
        if self._should_refresh_notice_index(argv):
            try:
                client = connections.get_connection()
                client.indices.refresh(index=NoticeDocument.Index.name)
            except Exception as exc:
                raise CommandError(
                    'Noticeboard index refresh failed after rebuild.'
                ) from exc

        return result
