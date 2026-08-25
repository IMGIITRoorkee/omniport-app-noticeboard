from configuration.utils.app_config_class import get_app_config_class

BaseConfig = get_app_config_class(__file__)


class Config(BaseConfig):

    def ready(self):
        super_ready = getattr(super(), 'ready', None)
        if callable(super_ready):
            super_ready()

        from noticeboard import documents
