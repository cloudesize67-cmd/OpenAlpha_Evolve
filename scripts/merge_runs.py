#!/usr/bin/env python3
"""Coalesce fragmented text runs in a WordprocessingML document so text is findable.

Word stores paragraph text in a sequence of *runs* (``<w:r>``), each holding a
``<w:t>`` text element and an optional ``<w:rPr>`` block of run properties
(bold, colour, spellcheck spans, and so on). A single logical sentence is
routinely shredded across many runs -- spell-check, grammar spans, cursor
history and rendering all leave seams -- so a phrase like "Hello world" can live
as ``Hel`` + ``lo wor`` + ``ld`` in three separate runs. That makes the text
impossible to find (and therefore impossible to search-and-replace) even though
it reads as one string.

This script merges *adjacent* runs that share the same parent and carry
identical run properties, concatenating their ``<w:t>`` text into a single run.
It is deliberately conservative:

  * Only "simple text runs" merge -- a run whose children are an optional
    ``<w:rPr>`` followed by exactly one ``<w:t>``. Runs containing breaks,
    tabs, drawings, field codes, footnote/endnote references, comment marks or
    any other content are left untouched, and act as barriers.
  * Runs merge only with an immediately-adjacent sibling of the same parent, so
    text is never dragged across a ``<w:ins>``/``<w:del>`` tracked-change
    boundary, a hyperlink boundary, or a paragraph boundary.
  * Run properties are compared by canonical (c14n) form, so runs merge only
    when their formatting is genuinely identical.
  * ``xml:space="preserve"`` is set on the merged text whenever the combined
    string has leading/trailing whitespace or either source asked to preserve
    it, so no whitespace is silently dropped.

lxml is used so the rest of the document round-trips faithfully: namespace
prefixes, attribute order and untouched byte ranges are preserved. The file is
edited in place and is NOT reformatted or pretty-printed.

Usage:
    python scripts/merge_runs.py unpacked/               # an unpacked .docx dir
    python scripts/merge_runs.py unpacked/word/document.xml
    python scripts/merge_runs.py unpacked/ --dry-run     # report, do not write
    python scripts/merge_runs.py unpacked/ --parts document.xml,footnotes.xml
"""
import argparse
import os
import sys

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"

W = "{%s}" % W_NS
XML_SPACE = "{%s}space" % XML_NS

# Parts of an unpacked .docx that hold runs worth coalescing.
_DEFAULT_PARTS = (
    "document.xml", "footnotes.xml", "endnotes.xml",
    "header1.xml", "header2.xml", "header3.xml",
    "footer1.xml", "footer2.xml", "footer3.xml",
    "comments.xml",
)


def _localname(elem):
    tag = elem.tag
    if not isinstance(tag, str):  # comments / PIs have callable tags
        return None
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _is_simple_text_run(run):
    """True if ``run`` is a ``<w:r>`` whose only content is one ``<w:t>``.

    An optional leading ``<w:rPr>`` is allowed. Anything else (breaks, tabs,
    drawings, field chars, footnote refs, comment marks, a second ``<w:t>``,
    ...) disqualifies the run so it is never merged away.
    """
    if _localname(run) != "r":
        return False
    seen_text = False
    for child in run:
        name = _localname(child)
        if name == "rPr":
            continue
        if name == "t":
            if seen_text:
                return False  # more than one text element
            seen_text = True
            continue
        return False  # any other content element -> not simple
    return seen_text


def _run_props(run):
    """Return the ``<w:rPr>`` child of a run, or None."""
    for child in run:
        if _localname(child) == "rPr":
            return child
    return None


def _text_elem(run):
    for child in run:
        if _localname(child) == "t":
            return child
    return None


def _canonical(elem):
    """Canonical (c14n) serialisation, used to compare run properties."""
    if elem is None:
        return b""
    return etree.tostring(elem, method="c14n")


def _props_equal(run_a, run_b):
    return _canonical(_run_props(run_a)) == _canonical(_run_props(run_b))


def _wants_preserve(text_elem):
    return text_elem is not None and text_elem.get(XML_SPACE) == "preserve"


def _merge_pair(first, second):
    """Fold ``second`` (a simple text run) into ``first`` and drop it.

    Both runs are assumed adjacent siblings, simple text runs, with equal
    properties. Their text is concatenated onto ``first``'s ``<w:t>``.
    """
    t_first = _text_elem(first)
    t_second = _text_elem(second)
    combined = (t_first.text or "") + (t_second.text or "")
    t_first.text = combined
    # Preserve whitespace if either source did, or if the join created edge space.
    if (_wants_preserve(t_first) or _wants_preserve(t_second)
            or combined != combined.strip()):
        t_first.set(XML_SPACE, "preserve")
    parent = second.getparent()
    parent.remove(second)


def _merge_runs_in_tree(root):
    """Merge coalescible runs throughout ``root``. Returns the number removed.

    Runs are grouped by their parent element so a merge never crosses a
    structural boundary. Within each parent, immediately-adjacent simple text
    runs with equal properties fold left into the first of the group.
    """
    removed = 0
    # Snapshot parents first: we mutate children as we go.
    parents = {run.getparent() for run in root.iter(W + "r")}
    for parent in parents:
        if parent is None:
            continue
        anchor = None  # the run others are folding into
        for child in list(parent):
            if _localname(child) == "r" and _is_simple_text_run(child):
                if anchor is not None and _props_equal(anchor, child):
                    _merge_pair(anchor, child)
                    removed += 1
                    continue
                anchor = child
            else:
                # Any non-mergeable node (including complex runs) breaks the run.
                anchor = None
    return removed


def _resolve_part_paths(target, parts):
    """Map a CLI target to a list of concrete XML files to process."""
    if os.path.isfile(target):
        return [target]
    if os.path.isdir(target):
        word_dir = os.path.join(target, "word")
        base = word_dir if os.path.isdir(word_dir) else target
        found = []
        for name in parts:
            candidate = os.path.join(base, name)
            if os.path.isfile(candidate):
                found.append(candidate)
        if not found:
            sys.exit(f"no processable parts found under {base!r} "
                     f"(looked for: {', '.join(parts)})")
        return found
    sys.exit(f"path not found: {target!r}")


def process_file(path, dry_run=False):
    """Merge runs in one XML part. Returns the count of runs removed."""
    # Keep the byte structure of the file intact apart from the merges.
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    tree = etree.parse(path, parser)
    removed = _merge_runs_in_tree(tree.getroot())
    if removed and not dry_run:
        tree.write(path, xml_declaration=True, encoding="UTF-8", standalone=True)
    return removed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "target",
        help="an unpacked .docx directory, or a path to a single XML part")
    parser.add_argument(
        "--parts", default=",".join(_DEFAULT_PARTS),
        help="comma-separated part filenames to process when target is a "
             "directory (default: the standard document/notes/headers/footers)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report how many runs would be merged without writing files")
    args = parser.parse_args(argv)

    parts = [p.strip() for p in args.parts.split(",") if p.strip()]
    paths = _resolve_part_paths(args.target, parts)

    total = 0
    for path in paths:
        removed = process_file(path, dry_run=args.dry_run)
        total += removed
        if removed:
            verb = "would merge" if args.dry_run else "merged"
            print(f"{verb} {removed} run(s) in {path}")
    tail = " (dry run)" if args.dry_run else ""
    print(f"Done: {total} run(s) coalesced across {len(paths)} part(s){tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
