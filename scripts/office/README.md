# .docx processing pipeline

Small, dependency-light tooling for editing Word documents by hand at the XML
level and shipping a file Word will actually open. Two scripts:

- **`scripts/merge_runs.py`** — coalesces fragmented text runs so text is
  findable (and therefore search-and-replaceable).
- **`scripts/office/validate.py`** — validates a repacked `.docx`, diffs it
  against the original, and checks that edits are tracked (redlining).

Both depend only on `lxml`, which round-trips OOXML faithfully — namespace
prefixes, attribute order and untouched byte ranges survive, and the files are
never pretty-printed.

## The workflow

```bash
unzip -q doc.docx -d unpacked/
find unpacked -type l -delete            # strip symlink entries — docx from
                                         # external parties is untrusted
python scripts/merge_runs.py unpacked/   # coalesce fragmented runs so text is findable

# edit unpacked/word/document.xml in place — do NOT reformat or pretty-print

(cd unpacked && rm -f ../out.docx && zip -Xr ../out.docx .)

python scripts/office/validate.py out.docx --original doc.docx   # structural checks
# redlining? add --author "<the name you redlined under>" to check every edit is tracked
```

## Why merge runs first

Word shreds a single logical sentence across many `<w:r>` runs — spell-check,
grammar spans, cursor history and rendering all leave seams. `Hello world` can
live as `Hel` + `lo wor` + `ld` in three runs, so a plain search for the phrase
finds nothing. `merge_runs.py` folds adjacent runs that share identical run
properties (`<w:rPr>`) into one, concatenating their text. It is deliberately
conservative:

- Only "simple text runs" (an optional `<w:rPr>` plus exactly one `<w:t>`)
  merge; runs with breaks, tabs, drawings, field codes or footnote refs are
  barriers.
- Runs merge only with an immediately-adjacent sibling of the same parent, so
  text never crosses a `<w:ins>`/`<w:del>` tracked-change, hyperlink, or
  paragraph boundary.
- `xml:space="preserve"` is added whenever a merge would otherwise strand
  edge whitespace.

By default it processes `document.xml`, the notes, headers, footers and
comments; pass `--parts a.xml,b.xml` to narrow it, or `--dry-run` to preview.

## What `validate.py` checks

- **Zip safety** — rejects absolute paths and `..` traversal (zip-slip);
  untrusted `.docx` files are hostile input.
- **Well-formedness** of every XML/rels part.
- **Required parts** — `[Content_Types].xml`, `_rels/.rels` and the main
  document part.
- **Content types** — every part covered by a `Default` extension or `Override`.
- **Relationships** — every internal target resolves to an existing part.

Optional:

- `--original doc.docx` — reports parts added or dropped relative to the source.
- `--author NAME` (needs `--original`) — the redlining check. It reconstructs
  the document *as if every tracked change were rejected*; if that does not
  reproduce the original text, an untracked edit slipped in and is reported with
  the first mismatching paragraph. Tracked changes attributed to anyone other
  than `NAME` are flagged.
- `--auto-repair` — fixes common, safe problems (missing content-type entries;
  relationships dangling to a nonexistent, unreferenced target) and rewrites the
  package in place.
- `--schema-dir DIR` — if a directory of ECMA-376 `.xsd` files is supplied, the
  main document is additionally validated against `wml.xsd` there.

Exit status is non-zero if any error-level problem remains after optional repair.

## Tests

```bash
python -m pytest tests/test_docx_pipeline.py
```
