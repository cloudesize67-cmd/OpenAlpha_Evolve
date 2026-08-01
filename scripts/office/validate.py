#!/usr/bin/env python3
"""Validate a repacked .docx and (optionally) diff it against the original.

After editing an unpacked document and zipping it back up it is easy to produce a
file that Word silently refuses to open: a part left out of ``[Content_Types].xml``,
a relationship pointing at a part that no longer exists, a malformed XML body, or
an unsafe entry name smuggled in by an untrusted source. This tool catches those
before the file ships.

Checks performed on the target package:

  * **Zip safety** -- rejects absolute paths, ``..`` traversal (zip-slip) and
    entries whose names look like directory escapes. Untrusted .docx files are
    treated as hostile input.
  * **Well-formedness** -- every ``*.xml``/``*.rels`` part must parse.
  * **Required parts** -- ``[Content_Types].xml``, ``_rels/.rels`` and the main
    document part must be present, and ``_rels/.rels`` must point at the document.
  * **Content types** -- every part is covered by a ``Default`` extension or an
    ``Override`` in ``[Content_Types].xml``.
  * **Relationships** -- every internal (non-``External``) relationship target
    resolves to a part that exists.

Optional modes:

  * ``--original doc.docx`` -- structural diff: reports parts added or dropped
    relative to the source package.
  * ``--author NAME`` -- redlining check (requires ``--original``): verifies that
    every textual change relative to the original is wrapped in a tracked change
    (``<w:ins>``/``<w:del>``). If rejecting all tracked changes does not
    reproduce the original text, an untracked edit slipped in and is reported.
    Tracked changes attributed to an author other than NAME are flagged.
  * ``--auto-repair`` -- fixes the common, safe issues (missing content-type
    entries; relationships dangling to nonexistent, unreferenced targets) and
    rewrites the package in place.
  * ``--schema-dir DIR`` -- if a directory of ECMA-376 ``.xsd`` files is
    supplied, the main document part is additionally validated against
    ``wml.xsd`` found there.

Exit status is non-zero if any error-level problem remains after optional repair.

Usage:
    python scripts/office/validate.py out.docx
    python scripts/office/validate.py out.docx --original doc.docx
    python scripts/office/validate.py out.docx --original doc.docx --author "Jane Doe"
    python scripts/office/validate.py out.docx --auto-repair
"""
import argparse
import os
import posixpath
import sys
import zipfile

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_TYPE = ("http://schemas.openxmlformats.org/officeDocument/2006/"
                "relationships/officeDocument")

W = "{%s}" % W_NS
CONTENT_TYPES = "[Content_Types].xml"

# Content types for parts we know how to repair into [Content_Types].xml.
_KNOWN_OVERRIDES = {
    "word/document.xml":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    "word/footnotes.xml":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
    "word/endnotes.xml":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml",
    "word/comments.xml":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
    "word/styles.xml":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
    "word/settings.xml":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml",
    "word/numbering.xml":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml",
    "word/fontTable.xml":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml",
}
_KNOWN_DEFAULTS = {
    "rels": "application/vnd.openxmlformats-package.relationships+xml",
    "xml": "application/xml",
}


class Report:
    """Accumulates findings; ``ok`` is False once any error is recorded."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.repairs = []
        self.notes = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def repair(self, msg):
        self.repairs.append(msg)

    def note(self, msg):
        self.notes.append(msg)

    @property
    def ok(self):
        return not self.errors

    def render(self):
        lines = []
        for msg in self.repairs:
            lines.append(f"  repaired: {msg}")
        for msg in self.errors:
            lines.append(f"  ERROR: {msg}")
        for msg in self.warnings:
            lines.append(f"  warning: {msg}")
        for msg in self.notes:
            lines.append(f"  {msg}")
        return "\n".join(lines)


def _is_unsafe_name(name):
    """True for zip entry names that try to escape the extraction root."""
    if name.startswith("/") or name.startswith("\\"):
        return True
    if ".." in name.replace("\\", "/").split("/"):
        return True
    # Windows drive-letter absolute paths.
    if len(name) >= 2 and name[1] == ":":
        return True
    return False


def _read_parts(path):
    """Return {part_name: bytes} for a .docx, checking zip safety.

    Raises ValueError on an unreadable zip. Unsafe entry names are returned
    separately so the caller can report them without materialising the bytes.
    """
    parts = {}
    unsafe = []
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/"):
                continue  # directory entry
            if _is_unsafe_name(name):
                unsafe.append(name)
                continue
            parts[name] = zf.read(info)
    return parts, unsafe


def _parse_xml(data):
    parser = etree.XMLParser(resolve_entities=False)
    return etree.fromstring(data, parser)


def _check_wellformed(parts, report):
    for name, data in sorted(parts.items()):
        if name.endswith(".xml") or name.endswith(".rels"):
            try:
                _parse_xml(data)
            except etree.XMLSyntaxError as exc:
                report.error(f"malformed XML in {name}: {exc}")


def _content_type_maps(parts, report):
    """Return (defaults_by_ext, overrides_by_partname) from [Content_Types].xml."""
    defaults, overrides = {}, {}
    if CONTENT_TYPES not in parts:
        return defaults, overrides
    try:
        root = _parse_xml(parts[CONTENT_TYPES])
    except etree.XMLSyntaxError:
        return defaults, overrides
    for el in root:
        tag = etree.QName(el).localname if el.tag is not etree.Comment else ""
        if tag == "Default":
            defaults[el.get("Extension", "").lower()] = el.get("ContentType")
        elif tag == "Override":
            # PartNames are absolute ("/word/document.xml"); zip part names are
            # not -- normalise so the two compare equal.
            overrides[el.get("PartName", "").lstrip("/")] = el.get("ContentType")
    return defaults, overrides


def _check_required(parts, report):
    for required in (CONTENT_TYPES, "_rels/.rels"):
        if required not in parts:
            report.error(f"missing required part: {required}")
    doc = _main_document_part(parts, report)
    if doc and doc not in parts:
        report.error(f"main document part {doc!r} referenced by "
                     "_rels/.rels does not exist")
    return doc


def _main_document_part(parts, report):
    """Resolve the main document part via _rels/.rels; fall back to a default."""
    rels = parts.get("_rels/.rels")
    if rels is not None:
        try:
            root = _parse_xml(rels)
        except etree.XMLSyntaxError:
            root = None
        if root is not None:
            for rel in root:
                if rel.get("Type") == DOC_REL_TYPE:
                    target = rel.get("Target", "")
                    return posixpath.normpath(target.lstrip("/"))
    return "word/document.xml" if "word/document.xml" in parts else None


def _check_content_types(parts, defaults, overrides, report):
    for name in sorted(parts):
        if name == CONTENT_TYPES:
            continue
        if name in overrides:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext in defaults:
            continue
        report.error(f"no content type declared for part {name!r} "
                     "(no matching Override or Default extension)")


def _iter_rels_parts(parts):
    """Yield (rels_name, owner_dir) for every *.rels part."""
    for name in parts:
        if name.endswith(".rels"):
            # _rels lives beside the part it describes: a/_rels/b.rels -> owner dir a/
            owner_dir = posixpath.dirname(posixpath.dirname(name))
            yield name, owner_dir


def _check_relationships(parts, report):
    for rels_name, owner_dir in _iter_rels_parts(parts):
        try:
            root = _parse_xml(parts[rels_name])
        except etree.XMLSyntaxError:
            continue  # already reported by well-formedness check
        for rel in root:
            if rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target", "")
            resolved = posixpath.normpath(posixpath.join(owner_dir, target.lstrip("/"))
                                          if not target.startswith("/")
                                          else target.lstrip("/"))
            if resolved not in parts:
                report.error(f"{rels_name}: relationship {rel.get('Id')!r} "
                             f"targets missing part {resolved!r}")


# ---------------------------------------------------------------------------
# Structural diff against the original package
# ---------------------------------------------------------------------------

def _diff_parts(original_parts, edited_parts, report):
    orig = set(original_parts)
    edited = set(edited_parts)
    for dropped in sorted(orig - edited):
        report.warn(f"part present in original but missing from output: {dropped}")
    for added in sorted(edited - orig):
        report.note(f"new part added relative to original: {added}")


# ---------------------------------------------------------------------------
# Redlining / tracked-change verification
# ---------------------------------------------------------------------------

def _paragraph_text(paragraph, mode):
    """Text of one ``<w:p>`` under a tracked-change ``mode``.

    mode="reject": as if all tracked changes were rejected -- excludes inserted
        text (``<w:ins>``), includes deleted text (``<w:del>``/``<w:delText>``).
        This should reproduce the original document.
    mode="accept": as if accepted -- includes insertions, excludes deletions.
    """
    out = []

    def walk(node, in_ins, in_del):
        for child in node:
            if child.tag is etree.Comment:
                continue
            local = etree.QName(child).localname
            if local == "ins":
                walk(child, True, in_del)
            elif local == "del":
                walk(child, in_ins, True)
            elif local == "t":
                if mode == "reject" and in_ins:
                    continue
                if mode == "accept" and in_del:
                    continue
                out.append(child.text or "")
            elif local == "delText":
                if mode == "accept":
                    continue  # deletion removed on accept
                out.append(child.text or "")
            elif local == "tab":
                out.append("\t")
            elif local in ("br", "cr"):
                out.append("\n")
            else:
                walk(child, in_ins, in_del)

    walk(paragraph, False, False)
    return "".join(out)


def _document_paragraph_texts(doc_bytes, mode):
    root = _parse_xml(doc_bytes)
    return [_paragraph_text(p, mode) for p in root.iter(W + "p")]


def _tracked_change_authors(doc_bytes):
    root = _parse_xml(doc_bytes)
    authors = set()
    for local in ("ins", "del"):
        for el in root.iter(W + local):
            authors.add(el.get(W + "author"))
    return authors


def _norm(seq):
    """Collapse internal whitespace per paragraph and drop empty paragraphs.

    Makes the comparison robust to run fragmentation and cosmetic whitespace
    while still catching genuine textual changes.
    """
    return [" ".join(p.split()) for p in seq if p.strip()]


def _check_redlining(original_parts, edited_parts, author, report):
    doc_orig = _main_document_part(original_parts, report)
    doc_edit = _main_document_part(edited_parts, report)
    if not doc_orig or not doc_edit:
        report.warn("cannot run redlining check: main document part not found")
        return
    try:
        original_text = _norm(_document_paragraph_texts(original_parts[doc_orig], "reject"))
        rejected_text = _norm(_document_paragraph_texts(edited_parts[doc_edit], "reject"))
    except etree.XMLSyntaxError as exc:
        report.warn(f"cannot run redlining check: {exc}")
        return

    if rejected_text != original_text:
        first = _first_difference(original_text, rejected_text)
        report.error(
            "untracked edit detected: rejecting all tracked changes does not "
            "reproduce the original text" + (f" ({first})" if first else ""))

    authors = {a for a in _tracked_change_authors(edited_parts[doc_edit]) if a}
    stray = sorted(authors - {author})
    if stray:
        report.warn("tracked changes attributed to other author(s): "
                    + ", ".join(repr(a) for a in stray))
    if author not in authors and authors == set():
        report.note(f"no tracked changes authored by {author!r} were found")


def _first_difference(expected, actual):
    for i, (a, b) in enumerate(zip(expected, actual)):
        if a != b:
            return (f"first mismatch at paragraph {i}: "
                    f"expected {a[:60]!r}, got {b[:60]!r}")
    if len(expected) != len(actual):
        return (f"paragraph count differs: original {len(expected)}, "
                f"rejected {len(actual)}")
    return ""


# ---------------------------------------------------------------------------
# Auto-repair
# ---------------------------------------------------------------------------

def _repair(parts, report):
    """Fix common, safe problems in-place on the ``parts`` dict.

    Returns True if anything changed. Handles missing content-type entries for
    known parts and drops relationships that dangle to a nonexistent target and
    are not referenced by any r:id/r:embed in the package.
    """
    changed = False
    changed |= _repair_content_types(parts, report)
    changed |= _repair_dangling_rels(parts, report)
    return changed


def _repair_content_types(parts, report):
    if CONTENT_TYPES not in parts:
        return False
    try:
        root = _parse_xml(parts[CONTENT_TYPES])
    except etree.XMLSyntaxError:
        return False
    defaults, overrides = _content_type_maps(parts, report)
    changed = False
    for name in sorted(parts):
        if name == CONTENT_TYPES:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if name in overrides or ext in defaults:
            continue
        if name in _KNOWN_OVERRIDES:
            ov = etree.SubElement(root, "{%s}Override" % CT_NS)
            ov.set("PartName", "/" + name)
            ov.set("ContentType", _KNOWN_OVERRIDES[name])
            report.repair(f"added content-type Override for {name}")
            changed = True
        elif ext in _KNOWN_DEFAULTS:
            df = etree.SubElement(root, "{%s}Default" % CT_NS)
            df.set("Extension", ext)
            df.set("ContentType", _KNOWN_DEFAULTS[ext])
            defaults[ext] = _KNOWN_DEFAULTS[ext]
            report.repair(f"added content-type Default for .{ext}")
            changed = True
    if changed:
        parts[CONTENT_TYPES] = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return changed


def _referenced_rel_ids(parts):
    """All relationship ids referenced via r:id / r:embed across the package."""
    r_ns = ("http://schemas.openxmlformats.org/officeDocument/2006/"
            "relationships")
    used = set()
    for name, data in parts.items():
        if not (name.endswith(".xml")):
            continue
        try:
            root = _parse_xml(data)
        except etree.XMLSyntaxError:
            continue
        for el in root.iter():
            for attr in ("id", "embed", "link"):
                val = el.get("{%s}%s" % (r_ns, attr))
                if val:
                    used.add(val)
    return used


def _repair_dangling_rels(parts, report):
    used = _referenced_rel_ids(parts)
    changed = False
    for rels_name, owner_dir in list(_iter_rels_parts(parts)):
        try:
            root = _parse_xml(parts[rels_name])
        except etree.XMLSyntaxError:
            continue
        removed_any = False
        for rel in list(root):
            if rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target", "")
            resolved = posixpath.normpath(
                posixpath.join(owner_dir, target.lstrip("/")))
            if resolved in parts:
                continue
            rid = rel.get("Id")
            if rid in used:
                # Referenced but missing: cannot safely drop; leave the error.
                continue
            root.remove(rel)
            removed_any = True
            report.repair(f"{rels_name}: dropped dangling unreferenced "
                          f"relationship {rid!r} -> {resolved!r}")
        if removed_any:
            parts[rels_name] = etree.tostring(
                root, xml_declaration=True, encoding="UTF-8", standalone=True)
            changed = True
    return changed


def _write_docx(path, parts):
    """Rewrite ``path`` from ``parts``. [Content_Types].xml is stored first."""
    ordered = sorted(parts, key=lambda n: (n != CONTENT_TYPES, n))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ordered:
            zf.writestr(name, parts[name])


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def validate(target, original=None, author=None, auto_repair=False,
             schema_dir=None):
    report = Report()
    try:
        parts, unsafe = _read_parts(target)
    except (zipfile.BadZipFile, OSError) as exc:
        report.error(f"cannot read {target!r} as a zip package: {exc}")
        return report
    for name in unsafe:
        report.error(f"unsafe zip entry name (path traversal): {name!r}")

    _check_wellformed(parts, report)

    if auto_repair and _repair(parts, report):
        _write_docx(target, parts)
        parts, _ = _read_parts(target)  # re-read to validate the repaired file

    defaults, overrides = _content_type_maps(parts, report)
    _check_required(parts, report)
    _check_content_types(parts, defaults, overrides, report)
    _check_relationships(parts, report)

    if schema_dir:
        _check_schema(parts, schema_dir, report)

    if original:
        try:
            original_parts, _ = _read_parts(original)
        except (zipfile.BadZipFile, OSError) as exc:
            report.error(f"cannot read original {original!r}: {exc}")
            original_parts = None
        if original_parts is not None:
            _diff_parts(original_parts, parts, report)
            if author:
                _check_redlining(original_parts, parts, author, report)
    elif author:
        report.warn("--author has no effect without --original")

    return report


def _check_schema(parts, schema_dir, report):
    wml = os.path.join(schema_dir, "wml.xsd")
    if not os.path.isfile(wml):
        report.warn(f"--schema-dir given but wml.xsd not found in {schema_dir!r}; "
                    "skipping XSD validation")
        return
    doc = _main_document_part(parts, report)
    if not doc or doc not in parts:
        return
    try:
        schema = etree.XMLSchema(etree.parse(wml))
        schema.assertValid(_parse_xml(parts[doc]))
        report.note(f"XSD-valid against {wml}")
    except etree.DocumentInvalid as exc:
        report.error(f"{doc} fails XSD validation: {exc}")
    except etree.XMLSchemaParseError as exc:
        report.warn(f"could not load schema {wml}: {exc}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("docx", help="the .docx package to validate")
    parser.add_argument("--original", help="original .docx to diff against")
    parser.add_argument("--author",
                        help="verify every edit is tracked under this author "
                             "(requires --original)")
    parser.add_argument("--auto-repair", action="store_true",
                        help="fix common issues and rewrite the package in place")
    parser.add_argument("--schema-dir",
                        help="directory of ECMA-376 .xsd files for XSD validation")
    args = parser.parse_args(argv)

    report = validate(args.docx, original=args.original, author=args.author,
                      auto_repair=args.auto_repair, schema_dir=args.schema_dir)

    rendered = report.render()
    print(f"Validation of {args.docx}:")
    if rendered:
        print(rendered)
    if report.ok:
        print("OK" if not report.warnings else "OK (with warnings)")
        return 0
    print(f"FAILED: {len(report.errors)} error(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
