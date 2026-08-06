"""
campaign_generator.py -- make_campaign(): synthetic coordinated-behavior
world generator for the NOESIS detection task (Milestone B).

Design DNA: same role as make_trial() in the torsion task -- a PROGRAMMATIC
world model (the Genie role, but free): infinite procedurally generated
campaigns with perfect ground truth, both ways (IO + organic labels).

Pure stdlib + numpy. Deterministic: same seed -> identical campaign.

Campaign anatomy (the three canonical coordination signals):
  1. copypasta      : group posts derive from a shared template, degraded
                      by per-group paraphrase (token substitution + dropout)
  2. synchronization: group members post within +/- jitter_s of burst times
  3. signature tags : burst posts carry group-unique hashtags w.p. tag_share_p
Decoys: organic "fan communities" (shared hashtag, high frequency, but
UNSYNCHRONIZED and no shared template) punish naive frequency and
tag-only detectors.
Difficulty knobs: paraphrase range, jitter_s, tag_share_p, n_decoys.
"""
import numpy as np

SECONDS_PER_DAY = 86400.0
VOCAB = 2000      # token ids 0..1999
N_HASHTAGS = 500  # organic hashtag pool


def make_campaign(seed, n_organic=300, n_groups=5, group_size=8, days=30,
                  posts_per_organic=18, posts_per_io=25,
                  jitter_s=60.0, tag_share_p=0.85,
                  paraphrase_lo=0.08, paraphrase_hi=0.30,
                  n_decoys=2, decoy_size=10, posts_per_decoy=30):
    rng = np.random.default_rng(seed)
    span = days * SECONDS_PER_DAY

    n_io = n_groups * group_size
    io_accounts = set(range(n_organic, n_organic + n_io))

    group_tags = {g: tuple(range(3 * g, 3 * g + 3)) for g in range(n_groups)}
    templates = {g: tuple(rng.integers(0, VOCAB, size=10).tolist())
                 for g in range(n_groups)}
    # per-group paraphrase rate: some groups near-verbatim, some heavily
    # reworded -- a content-only detector cannot catch them all
    para = {g: float(rng.uniform(paraphrase_lo, paraphrase_hi))
            for g in range(n_groups)}

    posts = []

    def organic_post(a, t, rng):
        ntok = int(rng.integers(6, 13))
        tokens = tuple(rng.integers(0, VOCAB, size=ntok).tolist())
        tags = tuple(rng.integers(0, N_HASHTAGS,
                     size=int(rng.random() < 0.7)).tolist())
        posts.append({"account": a, "t": float(t), "tokens": tokens,
                      "tags": tags})

    # ---- ordinary organic background ----
    decoy_accounts = set()
    for d in range(n_decoys):
        decoy_accounts |= set(range(d * decoy_size, (d + 1) * decoy_size))
    decoy_tag = {d: int(rng.integers(0, N_HASHTAGS)) for d in range(n_decoys)}

    for a in range(n_organic):
        if a in decoy_accounts:
            d = a // decoy_size
            n_posts = max(1, int(rng.poisson(posts_per_decoy)))
            for _ in range(n_posts):
                t = rng.uniform(0, span)
                ntok = int(rng.integers(6, 13))
                tokens = tuple(rng.integers(0, VOCAB, size=ntok).tolist())
                # one shared community tag + occasional random tag
                tags = [decoy_tag[d]]
                if rng.random() < 0.25:
                    tags.append(int(rng.integers(0, N_HASHTAGS)))
                posts.append({"account": a, "t": float(t),
                              "tokens": tokens, "tags": tuple(tags)})
        else:
            n_posts = max(1, int(rng.poisson(posts_per_organic)))
            for _ in range(n_posts):
                organic_post(a, rng.uniform(0, span), rng)

    # ---- coordinated groups ----
    for g in range(n_groups):
        members = [n_organic + g * group_size + i for i in range(group_size)]
        burst_times = np.sort(rng.uniform(0, span, size=posts_per_io))
        for bt in burst_times:
            for m in members:
                t = min(max(bt + rng.uniform(-jitter_s, jitter_s), 0.0), span)
                s = para[g]
                tokens = []
                for tok in templates[g]:
                    r = rng.random()
                    if r < 0.05:
                        continue                      # dropout
                    if r < 0.05 + s:
                        tokens.append(int(rng.integers(0, VOCAB)))  # substitution
                    else:
                        tokens.append(tok)
                if len(tokens) < 2:
                    tokens = list(templates[g][:2])
                n_sig = int(rng.random() < tag_share_p) + \
                        int(rng.random() < tag_share_p)
                tags = tuple(rng.choice(group_tags[g], size=n_sig,
                                        replace=False).tolist()) \
                    if n_sig else ()
                posts.append({"account": m, "t": float(t),
                              "tokens": tuple(tokens), "tags": tags})

    posts.sort(key=lambda p: (p["t"], p["account"]))

    labels = {}
    for a in range(n_organic):
        labels[a] = (False, -1)
    for g in range(n_groups):
        for i in range(group_size):
            labels[n_organic + g * group_size + i] = (True, g)

    return posts, labels


def io_accounts_of(labels):
    return {a for a, (is_io, _) in labels.items() if is_io}
