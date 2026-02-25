"""High-level OneNote parser using pyOneNote as the binary parsing engine.

Extracts structured content (text, images, formatting) from .one files
and organizes it by page.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from pyOneNote.Header import Header
from pyOneNote.OneDocument import OneDocment

logger = logging.getLogger(__name__)

# JCID type names from the OneNote spec
_PAGE_META = "jcidPageMetaData"
_SECTION_NODE = "jcidSectionNode"
_SECTION_META = "jcidSectionMetaData"
_PAGE_SERIES = "jcidPageSeriesNode"
_PAGE_MANIFEST = "jcidPageManifestNode"
_PAGE_NODE = "jcidPageNode"
_TITLE_NODE = "jcidTitleNode"
_OUTLINE_NODE = "jcidOutlineNode"
_OUTLINE_ELEMENT = "jcidOutlineElementNode"
_RICH_TEXT = "jcidRichTextOENode"
_IMAGE_NODE = "jcidImageNode"
_TABLE_NODE = "jcidTableNode"
_TABLE_ROW = "jcidTableRowNode"
_TABLE_CELL = "jcidTableCellNode"
_EMBEDDED_FILE = "jcidEmbeddedFileNode"
_NUMBER_LIST = "jcidNumberListNode"
_STYLE_CONTAINER = "jcidPersistablePropertyContainerForTOCSection"
_REVISION_META = "jcidRevisionMetaData"


@dataclass
class ExtractedProperty:
    """A single property from a OneNote object."""
    name: str
    value: object  # str, bytes, int, bool, list, etc.


@dataclass
class ExtractedObject:
    """A parsed object from the OneNote file."""
    obj_type: str
    identity: str
    properties: dict[str, object] = field(default_factory=dict)


@dataclass
class ExtractedPage:
    """A page with its title and content objects."""
    title: str = ""
    level: int = 0
    author: str = ""
    creation_time: str = ""
    last_modified: str = ""
    objects: list[ExtractedObject] = field(default_factory=list)


@dataclass
class ExtractedSection:
    """All pages extracted from a single .one file."""
    file_path: str = ""
    display_name: str = ""
    pages: list[ExtractedPage] = field(default_factory=list)
    file_data: dict[str, bytes] = field(default_factory=dict)


class OneStoreParser:
    """Parses a MS-ONESTORE (.one) file using pyOneNote."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    def parse(self) -> ExtractedSection:
        """Parse the .one file and return structured content."""
        section = ExtractedSection(file_path=str(self.file_path))

        with open(self.file_path, "rb") as f:
            doc = OneDocment(f)

        # Validate it's a .one file
        if doc.header.guidFileType != Header.ONE_UUID:
            raise ValueError(f"{self.file_path} is not a .one file")

        # Get all properties (objects with their property sets)
        raw_props = doc.get_properties()

        # Get embedded files
        raw_files = doc.get_files()
        for guid, finfo in raw_files.items():
            content = finfo.get("content", b"")
            if content:
                section.file_data[guid] = content

        # Convert raw properties to ExtractedObjects
        all_objects = []
        for raw in raw_props:
            obj = ExtractedObject(
                obj_type=raw["type"],
                identity=raw["identity"],
                properties=dict(raw["val"]),
            )
            all_objects.append(obj)

        # Build page structure
        section.pages = self._build_pages(all_objects)
        section.display_name = self._extract_section_name(all_objects)

        return section

    def _extract_section_name(self, objects: list[ExtractedObject]) -> str:
        """Extract section display name from section metadata."""
        for obj in objects:
            if obj.obj_type == _SECTION_META:
                name = obj.properties.get("SectionDisplayName", "")
                if name:
                    return str(name).strip()
        return ""

    def _build_pages(
        self, objects: list[ExtractedObject]
    ) -> list[ExtractedPage]:
        """Group objects into pages based on the document structure."""
        pages: list[ExtractedPage] = []

        # Collect page metadata, titles, and content objects
        page_metas: list[ExtractedObject] = []
        page_nodes: list[ExtractedObject] = []
        title_nodes: list[ExtractedObject] = []
        content_objects: list[ExtractedObject] = []
        style_objects: dict[str, ExtractedObject] = {}

        for obj in objects:
            if obj.obj_type == _PAGE_META:
                page_metas.append(obj)
            elif obj.obj_type == _PAGE_NODE:
                page_nodes.append(obj)
            elif obj.obj_type == _TITLE_NODE:
                title_nodes.append(obj)
            elif obj.obj_type in (
                _RICH_TEXT, _IMAGE_NODE, _TABLE_NODE,
                _TABLE_ROW, _TABLE_CELL, _EMBEDDED_FILE,
                _OUTLINE_ELEMENT, _OUTLINE_NODE, _NUMBER_LIST,
            ):
                content_objects.append(obj)
            elif obj.obj_type == _STYLE_CONTAINER:
                style_objects[obj.identity] = obj

        # Use page metadata to identify distinct pages
        # Each page_meta has CachedTitleString and PageLevel
        if not page_metas:
            # No page metadata - put all content in a single page
            if content_objects:
                page = ExtractedPage(objects=content_objects)
                pages.append(page)
            return pages

        # Group content by the revision that corresponds to each page
        # In the flat object list, objects belonging to a page share
        # the same GUID prefix in their identity
        page_guid_prefixes: list[str] = []
        for meta in page_metas:
            # Identity format: <ExtendedGUID> (guid, n)
            guid = _extract_guid(meta.identity)
            if guid and guid not in page_guid_prefixes:
                page_guid_prefixes.append(guid)

        # Get the GUID prefix from the latest page node
        # (we want the most recent revision)
        latest_page_guid = ""
        if page_nodes:
            latest_page_guid = _extract_guid(page_nodes[-1].identity)

        # If there's only one unique page GUID, group everything together
        unique_guids = set(page_guid_prefixes)
        if latest_page_guid:
            unique_guids.add(latest_page_guid)

        # Build pages - use the last page_meta for each unique GUID
        seen_guids: set[str] = set()
        for meta in reversed(page_metas):
            guid = _extract_guid(meta.identity)
            if not guid or guid in seen_guids:
                continue
            seen_guids.add(guid)

            title = _clean_text(str(meta.properties.get("CachedTitleString", "")))
            level_raw = meta.properties.get("PageLevel", 0)
            level = _parse_int(level_raw)
            creation = str(meta.properties.get("TopologyCreationTimeStamp", ""))

            page = ExtractedPage(
                title=title,
                level=level,
                creation_time=creation,
            )

            # Collect content objects that belong to this page's GUID
            for obj in content_objects:
                obj_guid = _extract_guid(obj.identity)
                if obj_guid == guid or obj_guid == latest_page_guid:
                    page.objects.append(obj)

            # Get author from page node
            for pn in page_nodes:
                pn_guid = _extract_guid(pn.identity)
                if pn_guid == guid or pn_guid == latest_page_guid:
                    page.author = _clean_text(
                        str(pn.properties.get("Author", ""))
                    )
                    page.last_modified = str(
                        pn.properties.get("LastModifiedTime", "")
                    )

            pages.append(page)

        # Reverse so pages are in order
        pages.reverse()

        # If no content was assigned to any page (GUID mismatch),
        # put all content in the first page
        if pages and all(len(p.objects) == 0 for p in pages):
            pages[0].objects = content_objects

        # Deduplicate pages by title - keep the version with the most content
        # Multiple revisions of the same page produce duplicates
        deduped: list[ExtractedPage] = []
        seen_titles: dict[str, int] = {}
        for page in pages:
            key = page.title.lower().strip()
            if key in seen_titles:
                idx = seen_titles[key]
                # Keep the version with more content
                if len(page.objects) > len(deduped[idx].objects):
                    deduped[idx] = page
            else:
                seen_titles[key] = len(deduped)
                deduped.append(page)

        return deduped


def _extract_guid(identity_str: str) -> str:
    """Extract the GUID from an ExtendedGUID identity string.

    Input format: '<ExtendedGUID> (guid-string, n)'
    Returns just the guid-string part.
    """
    match = re.search(r"\(([^,]+),", identity_str)
    if match:
        return match.group(1).strip()
    return ""


def _clean_text(text: str) -> str:
    """Clean up text by stripping null bytes and extra whitespace."""
    text = text.replace("\x00", "").strip()
    return text


def _parse_int(value: object) -> int:
    """Parse an integer from various formats pyOneNote returns."""
    if isinstance(value, int):
        return value
    if isinstance(value, bytes):
        try:
            return int.from_bytes(value[:4], "little")
        except Exception:
            return 0
    if isinstance(value, str):
        # Try to extract numeric value
        match = re.search(r"\d+", value)
        if match:
            return int(match.group())
    return 0
