from html.parser import HTMLParser
from noticeboard.models import Notice
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry


class HTMLStripper(HTMLParser):
    
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_stripped_text(self):
        return ''.join(self.fed)


def strip_html_tags(html_content):

    if not html_content:
        return ''
    try:
        s = HTMLStripper()
        s.feed(html_content)
        return s.get_stripped_text()
    except Exception:
        return html_content


@registry.register_document
class NoticeDocument(Document):

    title = fields.Text()
    content = fields.Text()

    class Index:
        name = 'notice'

    class Django:
        model = Notice
        fields = ('id', 'is_draft')

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_content(self, instance):
        return strip_html_tags(instance.content or '')

    def save(self, **kwargs):
        #Strip HTML from the content before saving
        self.content = strip_html_tags(self.content if self.content else '')
        return super().save(**kwargs)


def sync_notice_document(notice):

    if notice.is_draft:
        remove_notice_document(notice.id)
        return

    doc = NoticeDocument(
        meta={'id': notice.id},
        title=notice.title,
        content=notice.content,
        is_draft=notice.is_draft,
        id=notice.id,
    )
    doc.save()


def remove_notice_document(notice_id):

    try:
        client = NoticeDocument._index.get_connection()
        client.delete(index=NoticeDocument.Index.name, id=notice_id)
    except Exception:
        pass
