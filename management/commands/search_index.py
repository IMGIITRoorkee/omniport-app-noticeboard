from importlib import import_module

from django.core.management.base import BaseCommand, CommandError

from noticeboard.documents import NoticeDocument
from noticeboard.models import Notice


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

        if self._should_refresh_notice_index(argv):
            try:
                NoticeDocument().update(Notice.objects.all(), refresh=True)
            except Exception as exc:
                raise CommandError(
                    'Noticeboard index refresh failed after rebuild.'
                ) from exc

        return result
