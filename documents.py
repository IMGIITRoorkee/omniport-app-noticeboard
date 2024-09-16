from noticeboard.models import Notice

from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

@registry.register_document
class NoticeDocument(Document):
    
    class Index:
        name = "notice"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
        
    class Django:
        model = Notice
        fields = [
            "id",
            "title",
            "is_draft",
        ]
    
