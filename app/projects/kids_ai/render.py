"""Safe basic markdown for assistant replies. Child messages stay plain text."""

from html import escape
from html.parser import HTMLParser

import markdown

ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "ul",
    "ol",
    "li",
    "code",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "a",
}


class _AllowlistParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in ALLOWED_TAGS:
            return
        if tag == "br":
            self.parts.append("<br>")
            return
        if tag == "a":
            href = ""
            for key, value in attrs:
                if key == "href" and value and (
                    value.startswith("http://")
                    or value.startswith("https://")
                    or value.startswith("/")
                ):
                    href = escape(value, quote=True)
            if href:
                self.parts.append(
                    f'<a href="{href}" rel="noopener noreferrer" target="_blank">'
                )
            else:
                self.parts.append("<a>")
            return
        self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in ALLOWED_TAGS and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self.skip_depth:
            return
        self.parts.append(escape(data))

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.parts.append("<br>")


def render_assistant_html(text):
    raw = markdown.markdown(text or "", extensions=["nl2br", "fenced_code"])
    parser = _AllowlistParser()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        return f"<p>{escape(text or '')}</p>"
    return "".join(parser.parts)
