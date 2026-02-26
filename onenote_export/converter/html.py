"""HTML converter for OneNote content model.

Converts Page objects with ContentElements into self-contained HTML
documents with embedded CSS. Images and attachments are saved as
separate files (same as Markdown).
"""

import html

from onenote_export.converter.base import BaseConverter, _sanitize_filename
from onenote_export.model.content import (
    ContentElement,
    EmbeddedFile,
    ImageElement,
    RichText,
    TableElement,
)
from onenote_export.model.page import Page

_CSS = """\
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    max-width: 800px;
    margin: 2rem auto;
    padding: 0 1rem;
    line-height: 1.6;
    color: #222;
}
h1, h2, h3, h4, h5, h6 { margin-top: 1.5em; margin-bottom: 0.5em; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ccc; padding: 0.5em 0.75em; text-align: left; }
th { background: #f5f5f5; }
img { max-width: 100%; height: auto; }
a { color: #0366d6; }
footer { color: #666; font-size: 0.9em; margin-top: 2em; }
ul, ol { padding-left: 1.5em; }
"""


class HTMLConverter(BaseConverter):
    """Converts OneNote content model to self-contained HTML files."""

    FILE_EXTENSION = ".html"

    def render_page(self, page: Page) -> str:
        """Render a single page to a complete HTML document."""
        body_parts: list[str] = []

        if page.title:
            body_parts.append(f"<h1>{html.escape(page.title)}</h1>")

        ordered_counters: dict[int, int] = {}

        for element in page.elements:
            if isinstance(element, RichText) and element.list_type == "ordered":
                level = element.indent_level
                if level not in ordered_counters:
                    ordered_counters[level] = 0
                for k in list(ordered_counters):
                    if k > level:
                        del ordered_counters[k]
                ordered_counters[level] += 1
                rendered = self._render_rich_text(
                    element,
                    ordered_number=ordered_counters[level],
                )
            else:
                if not (isinstance(element, RichText) and element.list_type):
                    ordered_counters.clear()
                rendered = self._render_element(element)

            if rendered:
                body_parts.append(rendered)

        if page.author:
            escaped_author = html.escape(page.author)
            body_parts.append("<hr>")
            body_parts.append(f"<footer>Author: {escaped_author}</footer>")

        title = html.escape(page.title) if page.title else "Untitled"
        body = "\n".join(body_parts)

        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" '
            'content="width=device-width, initial-scale=1.0">\n'
            f"<title>{title}</title>\n"
            f"<style>\n{_CSS}</style>\n"
            "</head>\n"
            "<body>\n"
            f"{body}\n"
            "</body>\n"
            "</html>\n"
        )

    def _render_element(self, element: ContentElement) -> str:
        """Render a single content element to HTML."""
        if isinstance(element, RichText):
            return self._render_rich_text(element)
        elif isinstance(element, ImageElement):
            return self._render_image(element)
        elif isinstance(element, TableElement):
            return self._render_table(element)
        elif isinstance(element, EmbeddedFile):
            return self._render_embedded_file(element)
        return ""

    def _render_rich_text(
        self,
        rt: RichText,
        ordered_number: int = 0,
    ) -> str:
        """Render rich text to HTML."""
        parts: list[str] = []

        for run in rt.runs:
            text = run.text
            if not text:
                continue

            text = html.escape(text)

            if run.hyperlink_url:
                escaped_url = html.escape(run.hyperlink_url, quote=True)
                text = f'<a href="{escaped_url}">{text}</a>'

            if not rt.heading_level:
                if run.bold:
                    text = f"<strong>{text}</strong>"
                if run.italic:
                    text = f"<em>{text}</em>"
                if run.underline and not run.hyperlink_url:
                    text = f"<u>{text}</u>"
                if run.strikethrough:
                    text = f"<del>{text}</del>"
                if run.superscript:
                    text = f"<sup>{text}</sup>"
                if run.subscript:
                    text = f"<sub>{text}</sub>"

            parts.append(text)

        inline = "".join(parts)

        if rt.heading_level:
            level = min(rt.heading_level, 6)
            return f"<h{level}>{inline}</h{level}>"

        align_style = ""
        if rt.alignment and rt.alignment != "left":
            align_style = f' style="text-align: {html.escape(rt.alignment)}"'

        if rt.list_type:
            tag = "ol" if rt.list_type == "ordered" else "ul"
            prefix = f"<{tag}>" + "<li><ul>" * rt.indent_level
            suffix = "</ul></li>" * rt.indent_level + f"</{tag}>"
            return f"{prefix}<li>{inline}</li>{suffix}"

        if rt.indent_level > 0:
            prefix = "<ul>" * rt.indent_level
            suffix = "</ul>" * rt.indent_level
            return f"{prefix}<li>{inline}</li>{suffix}"

        return f"<p{align_style}>{inline}</p>"

    def _render_image(self, img: ImageElement) -> str:
        """Render image reference in HTML."""
        alt = html.escape(img.alt_text or img.filename or "image")
        if img.data:
            filename = _sanitize_filename(
                img.filename or f"image.{img.format or 'bin'}"
            )
            escaped_filename = html.escape(filename, quote=True)
            return f'<img src="./images/{escaped_filename}" alt="{alt}">'
        escaped_name = html.escape(img.filename or "image", quote=True)
        return f'<img src="{escaped_name}" alt="{alt}">'

    def _render_table(self, table: TableElement) -> str:
        """Render table in HTML."""
        if not table.rows:
            return ""

        lines: list[str] = ["<table>"]

        for i, row in enumerate(table.rows):
            lines.append("<tr>")
            cell_tag = "th" if i == 0 else "td"
            for cell_elements in row:
                cell_html = " ".join(
                    self._render_element(e)
                    for e in cell_elements
                    if self._render_element(e)
                )
                lines.append(f"<{cell_tag}>{cell_html}</{cell_tag}>")
            lines.append("</tr>")

        lines.append("</table>")
        return "\n".join(lines)

    def _render_embedded_file(self, ef: EmbeddedFile) -> str:
        """Render embedded file reference in HTML."""
        name = html.escape(ef.filename or "attachment")
        if ef.data:
            filename = _sanitize_filename(ef.filename or "attachment")
            escaped_filename = html.escape(filename, quote=True)
            return f'<a href="./attachments/{escaped_filename}">{name}</a>'
        return f"<span>{name}</span>"
