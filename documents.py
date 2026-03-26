from html.parser import HTMLParser
from noticeboard.models import Notice
from django_elasticsearch_dsl import Document, fields


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


class NoticeDocument(Document):
    
    title = fields.Text()
    content = fields.Text()

    class Index:
        name = 'notice'

    class Django:
        model = Notice
        fields = ('id', 'title', 'is_draft')
    
    def save(self, **kwargs):
        #Strip HTML from the content before saving
        self.content = strip_html_tags(self.content if self.content else '')
        return super().save(**kwargs)
