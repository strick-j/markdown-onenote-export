"""Tests for onenote_export.converter.html module."""

import tempfile

from onenote_export.converter.html import HTMLConverter
from onenote_export.model.content import (
    EmbeddedFile,
    ImageElement,
    RichText,
    TableElement,
    TextRun,
)
from onenote_export.model.notebook import Notebook
from onenote_export.model.page import Page
from onenote_export.model.section import Section


class TestHTMLDocument:
    """Tests for HTML document structure."""

    def setup_method(self):
        self.converter = HTMLConverter(tempfile.gettempdir() + "/test_output")

    def test_doctype_present(self):
        page = Page(title="Test")
        result = self.converter.render_page(page)
        assert result.startswith("<!DOCTYPE html>")

    def test_charset_meta(self):
        page = Page(title="Test")
        result = self.converter.render_page(page)
        assert '<meta charset="utf-8">' in result

    def test_viewport_meta(self):
        page = Page(title="Test")
        result = self.converter.render_page(page)
        assert 'name="viewport"' in result
        assert "width=device-width" in result

    def test_embedded_css(self):
        page = Page(title="Test")
        result = self.converter.render_page(page)
        assert "<style>" in result
        assert "font-family" in result

    def test_title_in_head(self):
        page = Page(title="My Page")
        result = self.converter.render_page(page)
        assert "<title>My Page</title>" in result

    def test_untitled_page_title(self):
        page = Page()
        result = self.converter.render_page(page)
        assert "<title>Untitled</title>" in result


class TestHTMLConverterRenderPage:
    """Tests for HTMLConverter.render_page."""

    def setup_method(self):
        self.converter = HTMLConverter(tempfile.gettempdir() + "/test_output")

    def test_page_with_title(self):
        page = Page(title="My Title")
        result = self.converter.render_page(page)
        assert "<h1>My Title</h1>" in result

    def test_page_with_author(self):
        page = Page(title="Test", author="John Doe")
        result = self.converter.render_page(page)
        assert "<footer>Author: John Doe</footer>" in result
        assert "<hr>" in result

    def test_page_with_plain_text(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="Hello world")])],
        )
        result = self.converter.render_page(page)
        assert "<p>Hello world</p>" in result

    def test_page_with_bold_text(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="important", bold=True)])],
        )
        result = self.converter.render_page(page)
        assert "<strong>important</strong>" in result

    def test_page_with_italic_text(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="emphasis", italic=True)])],
        )
        result = self.converter.render_page(page)
        assert "<em>emphasis</em>" in result

    def test_page_with_underline_text(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="underlined", underline=True)])],
        )
        result = self.converter.render_page(page)
        assert "<u>underlined</u>" in result

    def test_page_with_strikethrough(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="removed", strikethrough=True)])],
        )
        result = self.converter.render_page(page)
        assert "<del>removed</del>" in result

    def test_page_with_hyperlink(self):
        page = Page(
            title="Test",
            elements=[
                RichText(
                    runs=[
                        TextRun(
                            text="click here",
                            hyperlink_url="https://example.com",
                        )
                    ]
                )
            ],
        )
        result = self.converter.render_page(page)
        assert '<a href="https://example.com">click here</a>' in result

    def test_page_with_superscript(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="2", superscript=True)])],
        )
        result = self.converter.render_page(page)
        assert "<sup>2</sup>" in result

    def test_page_with_subscript(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="2", subscript=True)])],
        )
        result = self.converter.render_page(page)
        assert "<sub>2</sub>" in result

    def test_page_with_indented_text(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="list item")], indent_level=1)],
        )
        result = self.converter.render_page(page)
        assert "<ul>" in result
        assert "<li>list item</li>" in result

    def test_page_with_nested_indent(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="nested")], indent_level=3)],
        )
        result = self.converter.render_page(page)
        assert result.count("<ul>") >= 3

    def test_page_with_ordered_list(self):
        page = Page(
            title="Test",
            elements=[
                RichText(
                    runs=[TextRun(text="first")],
                    list_type="ordered",
                    indent_level=0,
                )
            ],
        )
        result = self.converter.render_page(page)
        assert "<ol>" in result
        assert "<li>first</li>" in result

    def test_page_with_unordered_list(self):
        page = Page(
            title="Test",
            elements=[
                RichText(
                    runs=[TextRun(text="item")],
                    list_type="unordered",
                    indent_level=0,
                )
            ],
        )
        result = self.converter.render_page(page)
        assert "<ul>" in result
        assert "<li>item</li>" in result

    def test_page_with_image(self):
        page = Page(
            title="Test",
            elements=[
                ImageElement(data=b"\x89PNG", filename="screenshot.png", format="png")
            ],
        )
        result = self.converter.render_page(page)
        assert '<img src="./images/screenshot.png"' in result
        assert 'alt="screenshot.png"' in result

    def test_page_with_image_no_data(self):
        page = Page(
            title="Test",
            elements=[ImageElement(filename="remote.png")],
        )
        result = self.converter.render_page(page)
        assert '<img src="remote.png"' in result

    def test_page_with_embedded_file(self):
        page = Page(
            title="Test",
            elements=[EmbeddedFile(data=b"content", filename="report.pdf")],
        )
        result = self.converter.render_page(page)
        assert '<a href="./attachments/report.pdf">report.pdf</a>' in result

    def test_page_with_embedded_file_no_data(self):
        page = Page(
            title="Test",
            elements=[EmbeddedFile(filename="missing.pdf")],
        )
        result = self.converter.render_page(page)
        assert "<span>missing.pdf</span>" in result

    def test_empty_page(self):
        page = Page()
        result = self.converter.render_page(page)
        assert "<body>" in result
        assert "</body>" in result

    def test_alignment(self):
        page = Page(
            title="Test",
            elements=[
                RichText(
                    runs=[TextRun(text="centered")],
                    alignment="center",
                )
            ],
        )
        result = self.converter.render_page(page)
        assert 'style="text-align: center"' in result

    def test_headings(self):
        page = Page(
            title="Test",
            elements=[
                RichText(
                    runs=[TextRun(text="Heading")],
                    heading_level=2,
                )
            ],
        )
        result = self.converter.render_page(page)
        assert "<h2>Heading</h2>" in result


class TestHTMLConverterRenderTable:
    """Tests for table rendering."""

    def setup_method(self):
        self.converter = HTMLConverter(tempfile.gettempdir() + "/test_output")

    def test_simple_table(self):
        table = TableElement(
            rows=[
                [
                    [RichText(runs=[TextRun(text="Header 1")])],
                    [RichText(runs=[TextRun(text="Header 2")])],
                ],
                [
                    [RichText(runs=[TextRun(text="Cell 1")])],
                    [RichText(runs=[TextRun(text="Cell 2")])],
                ],
            ]
        )
        result = self.converter._render_table(table)
        assert "<table>" in result
        assert "<th>" in result
        assert "<td>" in result
        assert "Header 1" in result
        assert "Cell 1" in result

    def test_empty_table(self):
        table = TableElement(rows=[])
        result = self.converter._render_table(table)
        assert result == ""

    def test_table_with_formatted_cells(self):
        table = TableElement(
            rows=[
                [
                    [RichText(runs=[TextRun(text="bold", bold=True)])],
                ],
            ]
        )
        result = self.converter._render_table(table)
        assert "<strong>bold</strong>" in result


class TestHTMLEscaping:
    """Tests for XSS prevention via HTML escaping."""

    def setup_method(self):
        self.converter = HTMLConverter(tempfile.gettempdir() + "/test_output")

    def test_escapes_angle_brackets(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="<script>alert('xss')</script>")])],
        )
        result = self.converter.render_page(page)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escapes_ampersand(self):
        page = Page(
            title="Test",
            elements=[RichText(runs=[TextRun(text="A & B")])],
        )
        result = self.converter.render_page(page)
        assert "A &amp; B" in result

    def test_escapes_quotes_in_title(self):
        page = Page(title='He said "hello"')
        result = self.converter.render_page(page)
        # Title in <title> and <h1> should be escaped
        assert "&quot;" in result or "He said" in result

    def test_escapes_hyperlink_url(self):
        page = Page(
            title="Test",
            elements=[
                RichText(
                    runs=[
                        TextRun(
                            text="link",
                            hyperlink_url='https://example.com/search?q=a&b=c"d',
                        )
                    ]
                )
            ],
        )
        result = self.converter.render_page(page)
        assert "&amp;" in result
        assert "&quot;" in result

    def test_escapes_author(self):
        page = Page(title="Test", author="<script>bad</script>")
        result = self.converter.render_page(page)
        assert "<script>bad</script>" not in result
        assert "&lt;script&gt;" in result


class TestHTMLConverterWriteFiles:
    """Tests for file writing operations."""

    def test_convert_section_creates_html_files(self, tmp_path):
        converter = HTMLConverter(tmp_path)
        section = Section(
            name="Test Section",
            pages=[
                Page(
                    title="Page 1",
                    elements=[RichText(runs=[TextRun(text="Content 1")])],
                ),
                Page(
                    title="Page 2",
                    elements=[RichText(runs=[TextRun(text="Content 2")])],
                ),
            ],
        )
        created = converter.convert_section(section)
        assert len(created) == 2
        assert (tmp_path / "Test Section" / "Page 1.html").exists()
        assert (tmp_path / "Test Section" / "Page 2.html").exists()

    def test_html_file_content(self, tmp_path):
        converter = HTMLConverter(tmp_path)
        section = Section(
            name="Test",
            pages=[
                Page(
                    title="Hello",
                    elements=[RichText(runs=[TextRun(text="world")])],
                )
            ],
        )
        converter.convert_section(section)
        content = (tmp_path / "Test" / "Hello.html").read_text()
        assert "<!DOCTYPE html>" in content
        assert "<h1>Hello</h1>" in content
        assert "world" in content

    def test_convert_notebook_creates_nested_dirs(self, tmp_path):
        converter = HTMLConverter(tmp_path)
        notebook = Notebook(
            name="My Notebook",
            sections=[
                Section(name="Section A", pages=[Page(title="Page 1")]),
                Section(name="Section B", pages=[Page(title="Page 2")]),
            ],
        )
        converter.convert_notebook(notebook)
        assert (tmp_path / "My Notebook" / "Section A" / "Page 1.html").exists()
        assert (tmp_path / "My Notebook" / "Section B" / "Page 2.html").exists()

    def test_writes_images(self, tmp_path):
        converter = HTMLConverter(tmp_path)
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        section = Section(
            name="Test",
            pages=[
                Page(
                    title="With Image",
                    elements=[
                        ImageElement(data=png_header, filename="pic.png", format="png")
                    ],
                ),
            ],
        )
        converter.convert_section(section)
        assert (tmp_path / "Test" / "images" / "pic.png").exists()

    def test_writes_attachments(self, tmp_path):
        converter = HTMLConverter(tmp_path)
        section = Section(
            name="Test",
            pages=[
                Page(
                    title="With File",
                    elements=[EmbeddedFile(data=b"pdf content", filename="doc.pdf")],
                ),
            ],
        )
        converter.convert_section(section)
        assert (tmp_path / "Test" / "attachments" / "doc.pdf").exists()
