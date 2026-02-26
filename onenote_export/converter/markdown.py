"""Markdown converter for OneNote content model.

Converts Page objects with ContentElements into Markdown text.
File I/O is handled by the BaseConverter superclass.
"""

from onenote_export.converter.base import BaseConverter, _sanitize_filename
from onenote_export.model.content import (
    ContentElement,
    EmbeddedFile,
    ImageElement,
    RichText,
    TableElement,
)
from onenote_export.model.page import Page


class MarkdownConverter(BaseConverter):
    """Converts OneNote content model to Markdown files."""

    FILE_EXTENSION = ".md"

    def render_page(self, page: Page) -> str:
        """Render a single page to Markdown text."""
        lines: list[str] = []

        if page.title:
            lines.append(f"# {page.title}")
            lines.append("")

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
                md = self._render_rich_text(
                    element,
                    ordered_number=ordered_counters[level],
                )
            else:
                if not (isinstance(element, RichText) and element.list_type):
                    ordered_counters.clear()
                md = self._render_element(element)

            if md:
                lines.append(md)
                lines.append("")

        if page.author:
            lines.append("---")
            lines.append(f"*Author: {page.author}*")
            lines.append("")

        return "\n".join(lines)

    def _render_element(self, element: ContentElement) -> str:
        """Render a single content element to Markdown."""
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
        """Render rich text to Markdown."""
        parts: list[str] = []

        for run in rt.runs:
            text = run.text
            if not text:
                continue

            if not rt.heading_level:
                if run.strikethrough:
                    text = f"~~{text}~~"
                if run.bold and run.italic:
                    text = f"***{text}***"
                elif run.bold:
                    text = f"**{text}**"
                elif run.italic:
                    text = f"*{text}*"
                if run.underline and not run.hyperlink_url:
                    text = f"*{text}*"

            if run.hyperlink_url:
                text = f"[{run.text}]({run.hyperlink_url})"

            if not rt.heading_level:
                if run.superscript:
                    text = f"<sup>{text}</sup>"
                if run.subscript:
                    text = f"<sub>{text}</sub>"

            parts.append(text)

        result = "".join(parts)

        if rt.heading_level:
            prefix = "#" * rt.heading_level
            result = f"{prefix} {result}"
        elif rt.list_type:
            indent = "   " * rt.indent_level
            if rt.list_type == "ordered":
                num = ordered_number if ordered_number > 0 else 1
                marker = f"{num}."
            else:
                marker = "-"
            result = f"{indent}{marker} {result}"
        elif rt.indent_level > 0:
            indent = "   " * rt.indent_level
            result = f"{indent}- {result}"

        return result

    def _render_image(self, img: ImageElement) -> str:
        """Render image reference in Markdown."""
        alt = img.alt_text or img.filename or "image"
        if img.data:
            filename = _sanitize_filename(
                img.filename or f"image.{img.format or 'bin'}"
            )
            return f"![{alt}](./images/{filename})"
        return f"![{alt}]({img.filename})"

    def _render_table(self, table: TableElement) -> str:
        """Render table in Markdown."""
        if not table.rows:
            return ""

        lines: list[str] = []

        for i, row in enumerate(table.rows):
            cells = []
            for cell_elements in row:
                cell_text = " ".join(
                    self._render_element(e).strip()
                    for e in cell_elements
                    if self._render_element(e).strip()
                )
                cells.append(cell_text or " ")

            lines.append("| " + " | ".join(cells) + " |")

            if i == 0:
                lines.append("| " + " | ".join("---" for _ in cells) + " |")

        return "\n".join(lines)

    def _render_embedded_file(self, ef: EmbeddedFile) -> str:
        """Render embedded file reference in Markdown."""
        name = ef.filename or "attachment"
        if ef.data:
            filename = _sanitize_filename(name)
            return f"[{name}](./attachments/{filename})"
        return f"[{name}]"
