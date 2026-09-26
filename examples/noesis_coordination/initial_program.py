"""
initial_program.py -- NOESIS coordination-detection seed.

OpenEvolve evolves ONLY the code inside the EVOLVE-BLOCK.
Contract: detect_campaign(posts) -> list of clusters (lists of account ids).
Accounts in clusters of size >= 2 are scored as flagged.
Posts: list of {"account": int, "t": float, "tokens": tuple, "tags": tuple}.

Rules (the Law): do NOT try to read the evaluator, its seeds, or the
generator's ground truth. Optimize the general problem: groups of accounts
that post near-duplicate content in synchronized bursts with shared
signature hashtags.
"""
from collections import defaultdict


def detect_campaign(posts):
    # EVOLVE-BLOCK-START
    # Seed heuristic: flag the most frequent posters as one cluster.
    # Deliberately weak -- the search should discover content-similarity,
    # temporal-synchronization, and hashtag-signature signals.
    counts = defaultdict(int)
    for p in posts:
        counts[p["account"]] += 1
    if not counts:
        return []
    vals = sorted(counts.values())
    threshold = vals[int(0.9 * (len(vals) - 1))]
    flagged = sorted(a for a, c in counts.items() if c >= threshold)
    return [flagged] if len(flagged) >= 2 else []
    # EVOLVE-BLOCK-END
