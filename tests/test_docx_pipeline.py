"""Tests for the .docx processing pipeline (scripts/merge_runs.py and
scripts/office/validate.py).

Builds minimal WordprocessingML packages in temp directories and exercises run
coalescing, package validation, structural diffing, auto-repair and the
redlining (tracked-change) check.

Uses unittest to match the test style already in this repo
(see tests/test_corpus_seeding.py); lxml is the one external dependency.
"""
import importlib.util
import os
import tempfile
import unittest
import zipfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(module_name, relpath):
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(_REPO_ROOT, relpath))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge_runs = _load("merge_runs", "scripts/merge_runs.py")
validate = _load("office_validate", "scripts/office/validate.py")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_CT = ("application/vnd.openxmlformats-officedocument."
          "wordprocessingml.document.main+xml")
DOC_REL = ("http://schemas.openxmlformats.org/officeDocument/2006/"
           "relationships/officeDocument")

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Types xmlns="{CT}">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    f'<Override PartName="/word/document.xml" ContentType="{DOC_CT}"/>'
    '</Types>')

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{REL}">'
    f'<Relationship Id="rId1" Type="{DOC_REL}" Target="word/document.xml"/>'
    '</Relationships>')

_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{REL}"></Relationships>')


def _document(body_xml):
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document xmlns:w="{W}"><w:body>{body_xml}</w:body></w:document>')


def _run(text, props="", space=False):
    sp = ' xml:space="preserve"' if space else ""
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f"<w:r>{rpr}<w:t{sp}>{text}</w:t></w:r>"


def _para(*runs):
    return "<w:p>" + "".join(runs) + "</w:p>"


def _make_package(tmp, body_xml, extra_parts=None):
    """Return {part_name: str} for a minimal docx with the given body."""
    parts = {
        "[Content_Types].xml": _CONTENT_TYPES,
        "_rels/.rels": _ROOT_RELS,
        "word/document.xml": _document(body_xml),
        "word/_rels/document.xml.rels": _DOC_RELS,
    }
    if extra_parts:
        parts.update(extra_parts)
    return parts


def _write_docx(path, parts):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data)


def _unpack(parts, dest):
    for name, data in parts.items():
        full = os.path.join(dest, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(data)
    return dest


class MergeRunsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _document_text(self, unpacked):
        from lxml import etree
        root = etree.parse(os.path.join(unpacked, "word", "document.xml")).getroot()
        return "".join(t.text or "" for t in root.iter("{%s}t" % W))

    def _run_count(self, unpacked):
        from lxml import etree
        root = etree.parse(os.path.join(unpacked, "word", "document.xml")).getroot()
        return len(list(root.iter("{%s}r" % W)))

    def test_merges_adjacent_identical_runs(self):
        body = _para(_run("Hel"), _run("lo wor"), _run("ld"))
        unpacked = _unpack(_make_package(self.dir, body),
                           os.path.join(self.dir, "unpacked"))
        removed = merge_runs.process_file(
            os.path.join(unpacked, "word", "document.xml"))
        self.assertEqual(removed, 2)
        self.assertEqual(self._run_count(unpacked), 1)
        self.assertEqual(self._document_text(unpacked), "Hello world")

    def test_does_not_merge_different_properties(self):
        body = _para(_run("bold", props="<w:b/>"), _run("plain"))
        unpacked = _unpack(_make_package(self.dir, body),
                           os.path.join(self.dir, "unpacked"))
        removed = merge_runs.process_file(
            os.path.join(unpacked, "word", "document.xml"))
        self.assertEqual(removed, 0)
        self.assertEqual(self._run_count(unpacked), 2)

    def test_does_not_merge_across_tracked_change(self):
        body = _para(_run("keep"),
                     f'<w:ins w:author="A">{_run("added")}</w:ins>',
                     _run("keep2"))
        unpacked = _unpack(_make_package(self.dir, body),
                           os.path.join(self.dir, "unpacked"))
        removed = merge_runs.process_file(
            os.path.join(unpacked, "word", "document.xml"))
        # The <w:ins> is a barrier; the two outer runs are not adjacent siblings
        # of each other in a mergeable way.
        self.assertEqual(removed, 0)

    def test_run_with_break_is_a_barrier(self):
        body = _para(_run("a"),
                     "<w:r><w:br/><w:t>b</w:t></w:r>",
                     _run("c"))
        unpacked = _unpack(_make_package(self.dir, body),
                           os.path.join(self.dir, "unpacked"))
        removed = merge_runs.process_file(
            os.path.join(unpacked, "word", "document.xml"))
        self.assertEqual(removed, 0)

    def test_internal_whitespace_needs_no_preserve(self):
        # A space that becomes internal after merging is safe without preserve.
        body = _para(_run("hello "), _run("world"))
        unpacked = _unpack(_make_package(self.dir, body),
                           os.path.join(self.dir, "unpacked"))
        merge_runs.process_file(os.path.join(unpacked, "word", "document.xml"))
        from lxml import etree
        root = etree.parse(os.path.join(unpacked, "word", "document.xml")).getroot()
        t = next(root.iter("{%s}t" % W))
        self.assertEqual(t.text, "hello world")

    def test_preserves_edge_whitespace(self):
        # Leading whitespace on the merged text would be trimmed by Word unless
        # xml:space="preserve" is set.
        body = _para(_run(" lead", space=True), _run("ing"))
        unpacked = _unpack(_make_package(self.dir, body),
                           os.path.join(self.dir, "unpacked"))
        merge_runs.process_file(os.path.join(unpacked, "word", "document.xml"))
        from lxml import etree
        root = etree.parse(os.path.join(unpacked, "word", "document.xml")).getroot()
        t = next(root.iter("{%s}t" % W))
        self.assertEqual(t.text, " leading")
        self.assertEqual(
            t.get("{http://www.w3.org/XML/1998/namespace}space"), "preserve")

    def test_dry_run_does_not_write(self):
        body = _para(_run("a"), _run("b"))
        unpacked = _unpack(_make_package(self.dir, body),
                           os.path.join(self.dir, "unpacked"))
        path = os.path.join(unpacked, "word", "document.xml")
        before = open(path, encoding="utf-8").read()
        removed = merge_runs.process_file(path, dry_run=True)
        self.assertEqual(removed, 1)
        self.assertEqual(open(path, encoding="utf-8").read(), before)

    def test_directory_target_resolves_word_document(self):
        body = _para(_run("x"), _run("y"))
        unpacked = _unpack(_make_package(self.dir, body),
                           os.path.join(self.dir, "unpacked"))
        rc = merge_runs.main([unpacked])
        self.assertEqual(rc, 0)
        self.assertEqual(self._run_count(unpacked), 1)


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _docx(self, name, parts):
        path = os.path.join(self.dir, name)
        _write_docx(path, parts)
        return path

    def test_valid_package_passes(self):
        parts = _make_package(self.dir, _para(_run("hi")))
        report = validate.validate(self._docx("ok.docx", parts))
        self.assertTrue(report.ok, report.render())

    def test_missing_content_type_is_error_and_repairable(self):
        parts = _make_package(self.dir, _para(_run("hi")))
        parts["word/styles.xml"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:styles xmlns:w="{W}"></w:styles>')
        # styles.xml has extension xml -> covered by Default; make it uncovered
        # by removing the xml Default from content types.
        parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
            '<Default Extension="xml" ContentType="application/xml"/>', "")
        path = self._docx("missing_ct.docx", parts)

        report = validate.validate(path)
        self.assertFalse(report.ok)
        self.assertTrue(any("no content type" in e for e in report.errors))

        repaired = validate.validate(path, auto_repair=True)
        self.assertTrue(repaired.ok, repaired.render())
        self.assertTrue(repaired.repairs)

    def test_dangling_relationship_detected(self):
        parts = _make_package(self.dir, _para(_run("hi")))
        parts["word/_rels/document.xml.rels"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{REL}">'
            '<Relationship Id="rId99" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="media/missing.png"/>'
            '</Relationships>')
        path = self._docx("dangling.docx", parts)

        report = validate.validate(path)
        self.assertFalse(report.ok)
        self.assertTrue(any("missing part" in e for e in report.errors))

        # Unreferenced dangling rel -> auto-repair drops it.
        repaired = validate.validate(path, auto_repair=True)
        self.assertTrue(repaired.ok, repaired.render())

    def test_malformed_xml_detected(self):
        parts = _make_package(self.dir, _para(_run("hi")))
        parts["word/document.xml"] = "<w:document><w:body></w:document>"
        report = validate.validate(self._docx("bad.docx", parts))
        self.assertFalse(report.ok)
        self.assertTrue(any("malformed XML" in e for e in report.errors))

    def test_zip_slip_entry_rejected(self):
        parts = _make_package(self.dir, _para(_run("hi")))
        path = os.path.join(self.dir, "evil.docx")
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in parts.items():
                zf.writestr(name, data)
            zf.writestr("../../etc/evil", "pwned")
        report = validate.validate(path)
        self.assertFalse(report.ok)
        self.assertTrue(any("path traversal" in e for e in report.errors))

    def test_diff_reports_dropped_part(self):
        original = _make_package(
            self.dir, _para(_run("hi")),
            extra_parts={"word/styles.xml":
                         f'<w:styles xmlns:w="{W}"></w:styles>'})
        original["[Content_Types].xml"] = original["[Content_Types].xml"].replace(
            "</Types>",
            '<Override PartName="/word/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.styles+xml"/></Types>')
        orig_path = self._docx("orig.docx", original)

        edited = _make_package(self.dir, _para(_run("hi")))  # styles dropped
        edited_path = self._docx("edited.docx", edited)

        report = validate.validate(edited_path, original=orig_path)
        self.assertTrue(any("missing from output" in w for w in report.warnings),
                        report.render())


class RedliningTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _docx(self, name, body):
        path = os.path.join(self.dir, name)
        _write_docx(path, _make_package(self.dir, body))
        return path

    def test_tracked_insertion_passes(self):
        original = self._docx("orig.docx", _para(_run("The quick fox")))
        # Insert " brown" as a tracked change by Jane Doe.
        edited_body = _para(
            _run("The quick"),
            '<w:ins w:id="1" w:author="Jane Doe" w:date="2026-01-01T00:00:00Z">'
            + _run(" brown", space=True) + '</w:ins>',
            _run(" fox", space=True))
        edited = self._docx("edited.docx", edited_body)

        report = validate.validate(edited, original=original, author="Jane Doe")
        self.assertTrue(report.ok, report.render())

    def test_untracked_edit_is_error(self):
        original = self._docx("orig.docx", _para(_run("The quick fox")))
        # Silently change the text with no tracked-change wrapper.
        edited = self._docx("edited.docx", _para(_run("The slow fox")))

        report = validate.validate(edited, original=original, author="Jane Doe")
        self.assertFalse(report.ok)
        self.assertTrue(any("untracked edit" in e for e in report.errors),
                        report.render())

    def test_tracked_deletion_passes(self):
        original = self._docx("orig.docx", _para(_run("keep drop keep")))
        edited_body = _para(
            _run("keep "),
            '<w:del w:id="2" w:author="Jane Doe" w:date="2026-01-01T00:00:00Z">'
            '<w:r><w:delText xml:space="preserve">drop </w:delText></w:r></w:del>',
            _run("keep"))
        edited = self._docx("edited.docx", edited_body)

        report = validate.validate(edited, original=original, author="Jane Doe")
        self.assertTrue(report.ok, report.render())

    def test_wrong_author_is_flagged(self):
        original = self._docx("orig.docx", _para(_run("The quick fox")))
        edited_body = _para(
            _run("The quick"),
            '<w:ins w:id="1" w:author="Someone Else" w:date="2026-01-01T00:00:00Z">'
            + _run(" brown", space=True) + '</w:ins>',
            _run(" fox", space=True))
        edited = self._docx("edited.docx", edited_body)

        report = validate.validate(edited, original=original, author="Jane Doe")
        # Text still reconstructs, so no error, but the stray author is a warning.
        self.assertTrue(any("other author" in w for w in report.warnings),
                        report.render())


if __name__ == "__main__":
    unittest.main()
