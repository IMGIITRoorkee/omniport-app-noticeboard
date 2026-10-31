from configuration.utils.app_config_class import get_app_config_class

BaseConfig = get_app_config_class(__file__)


class Config(BaseConfig):

    def ready(self):
        super_ready = getattr(super(), 'ready', None)
        if callable(super_ready):
            super_ready()

        from noticeboard import documents

        from django.db.models.signals import pre_save
        from categories.models import Category
        from noticeboard.utils.push_topics import mark_on_save
        pre_save.connect(
            mark_on_save, sender=Category, dispatch_uid='noticeboard_push_topics'
        )
