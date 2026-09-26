"""
evaluator.py -- deterministic scorer for the NOESIS coordination-detection
task (Milestone B). Pure stdlib + numpy (Termux-safe; no pandas/networkx).

Candidate contract: the program defines
    detect_campaign(posts) -> list of clusters
where posts is a list of dicts {"account": int, "t": float,
"tokens": tuple[int,...], "tags": tuple[int,...]} and a cluster is a list
of account ids. Accounts in clusters of size >= 2 count as flagged.

Metric (deterministic, fixed seeds):
  account-level F1 vs is_io labels  +  0.5 * ARI over IO accounts
  (candidate partition = cluster ids, unflagged IO = singletons;
   true partition = group ids).
combined_score = candidate metric - engineer-baseline metric (train seeds).
Publish ONLY --heldout numbers.

The community-detection rule from the build plan: graph partition is
computed OUTSIDE candidate code paths only by fixed deterministic
connected components -- no stochastic algorithms anywhere.
"""
import importlib.util
import math
import sys
from collections import defaultdict, deque

from campaign_generator import make_campaign, io_accounts_of

TRAIN_SEEDS = [11, 23, 37, 53, 71]
HELDOUT_SEEDS = [101, 203, 307, 409, 503]
# held-out = harder difficulty, per claim-boundary rules
TRAIN_KW = dict(jitter_s=60.0, tag_share_p=0.85,
                paraphrase_lo=0.08, paraphrase_hi=0.45, n_decoys=2)
HELDOUT_KW = dict(jitter_s=180.0, tag_share_p=0.5, n_decoys=4,
                  paraphrase_lo=0.25, paraphrase_hi=0.60,
                  n_groups=6, group_size=7)
CANDIDATE_FN_NAMES = ["detect_campaign", "detect", "flag_coordinated"]


# ---------------- metrics ----------------
def f1_accounts(flagged, io_accounts):
    tp = len(flagged & io_accounts)
    if not flagged:
        return 0.0
    prec = tp / len(flagged)
    rec = tp / len(io_accounts) if io_accounts else 0.0
    return 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)


def ari(labels_true, labels_pred):
    """Adjusted Rand index, deterministic, computed by hand."""
    n = len(labels_true)
    assert n == len(labels_pred)
    cont = defaultdict(int)
    a = defaultdict(int)
    b = defaultdict(int)
    for t, p in zip(labels_true, labels_pred):
        cont[(t, p)] += 1
        a[t] += 1
        b[p] += 1
    comb2 = lambda x: x * (x - 1) // 2
    sum_cont = sum(comb2(v) for v in cont.values())
    sum_a = sum(comb2(v) for v in a.values())
    sum_b = sum(comb2(v) for v in b.values())
    total = comb2(n)
    if total == 0:
        return 1.0
    expected = sum_a * sum_b / total
    maxi = 0.5 * (sum_a + sum_b)
    denom = maxi - expected
    return 1.0 if denom == 0 else (sum_cont - expected) / denom


def score_clusters(clusters, labels):
    io_acc = io_accounts_of(labels)
    flagged = set()
    cluster_of = {}
    for cid, c in enumerate(clusters):
        if len(c) >= 2:
            for a in c:
                flagged.add(a)
                cluster_of[a] = cid
    f1 = f1_accounts(flagged, io_acc)
    io_sorted = sorted(io_acc)
    y_true = [labels[a][1] for a in io_sorted]
    y_pred = [cluster_of.get(a, -1 - i) for i, a in enumerate(io_sorted)]
    ari_io = ari(y_true, y_pred)
    return f1 + 0.5 * ari_io, {"f1": round(f1, 4), "ari_io": round(ari_io, 4)}


# ---------------- shared signal helpers (fixed, outside candidates) ----
def shingles(tokens, k=5):
    if len(tokens) < k:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def account_shingles(posts, k=5):
    acc = defaultdict(set)
    for p in posts:
        acc[p["account"]] |= shingles(p["tokens"], k)
    return acc


def sync_counts(posts, w):
    """pairwise co-post counts within window w seconds (sliding window)."""
    pts = sorted((p["t"], p["account"]) for p in posts)
    counts = defaultdict(int)
    j = 0
    for i in range(len(pts)):
        if j < i:
            j = i
        ti, ai = pts[i]
        while j + 1 < len(pts) and pts[j + 1][0] - ti <= w:
            j += 1
            aj = pts[j][1]
            if aj != ai:
                counts[(min(ai, aj), max(ai, aj))] += 1
    return counts


def shared_tag_counts(posts):
    acc_tags = defaultdict(set)
    for p in posts:
        acc_tags[p["account"]] |= set(p["tags"])
    accs = sorted(acc_tags)
    counts = defaultdict(int)
    for i in range(len(accs)):
        ti = acc_tags[accs[i]]
        if not ti:
            continue
        for jj in range(i + 1, len(accs)):
            inter = len(ti & acc_tags[accs[jj]])
            if inter:
                counts[(accs[i], accs[jj])] = inter
    return counts


def components(edge_weight, min_w, min_size):
    """Fixed deterministic partition: threshold edges, BFS components.
    Deterministic via sorted iteration order."""
    adj = defaultdict(list)
    for (u, v), w in sorted(edge_weight.items()):
        if w >= min_w:
            adj[u].append(v)
            adj[v].append(u)
    seen = set()
    out = []
    for start in sorted(adj):
        if start in seen:
            continue
        comp, q = [], deque([start])
        seen.add(start)
        while q:
            x = q.popleft()
            comp.append(x)
            for y in sorted(adj[x]):
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        comp.sort()
        if len(comp) >= min_size:
            out.append(comp)
    return out


# ---------------- reference detectors (the fitness ladder) -------------
def naive_detector(posts):
    """Naive: flag accounts posting above mean+1sd frequency, each as one
    big cluster. Weak: organic heavy posters false-flag; quiet IO missed."""
    cnt = defaultdict(int)
    for p in posts:
        cnt[p["account"]] += 1
    vals = list(cnt.values())
    mean = sum(vals) / len(vals)
    sd = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    flagged = sorted(a for a, c in cnt.items() if c > mean + sd)
    return [flagged] if len(flagged) >= 2 else []


def engineer_baseline(posts):
    """Competent single-signal engineer: account-level k=4 shingle Jaccard.
    Catches near-verbatim copypasta groups; heavily paraphrased groups
    fall below the similarity floor and escape. No temporal or tag signal."""
    acc = account_shingles(posts, k=4)
    accs = sorted(acc)
    edges = {}
    for i in range(len(accs)):
        si = acc[accs[i]]
        if not si:
            continue
        for j in range(i + 1, len(accs)):
            sj = acc[accs[j]]
            union = len(si | sj)
            if union:
                jac = len(si & sj) / union
                if jac >= 0.045:
                    edges[(accs[i], accs[j])] = jac
    return components(edges, min_w=0.045, min_size=2)


def strong_detector(posts):
    """Strong fusion: content Jaccard (k=3) + sync co-posts + shared
    signature tags -> weighted graph -> fixed components."""
    acc = account_shingles(posts, k=3)
    accs = sorted(acc)
    content = {}
    for i in range(len(accs)):
        si = acc[accs[i]]
        if not si:
            continue
        for j in range(i + 1, len(accs)):
            sj = acc[accs[j]]
            union = len(si | sj)
            if union:
                jac = len(si & sj) / union
                if jac >= 0.03:
                    content[(accs[i], accs[j])] = jac * 8.0
    sync = sync_counts(posts, w=300.0)
    sync_e = {p: float(min(c, 8)) for p, c in sync.items() if c >= 3}
    tags = shared_tag_counts(posts)
    tag_e = {p: 2.0 * min(c - 2, 3) for p, c in tags.items() if c >= 3}
    fused = defaultdict(float)
    for src in (content, sync_e, tag_e):
        for p, w in src.items():
            fused[p] += w
    return components(fused, min_w=5.0, min_size=3)


# ---------------- candidate loading & evaluation ----------------------
def load_candidate(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in CANDIDATE_FN_NAMES:
        if hasattr(mod, name):
            return getattr(mod, name)
    raise AttributeError(f"No detect function found (tried {CANDIDATE_FN_NAMES})")


def evaluate_with(fn, seeds, kw):
    scores = []
    for s in seeds:
        posts, labels = make_campaign(s, **kw)
        clusters = fn(posts)
        if not isinstance(clusters, list) or any(
                not isinstance(c, list) for c in clusters):
            return None, None
        m, detail = score_clusters(clusters, labels)
        scores.append(m)
    import numpy as np
    scores = np.array(scores)
    return float(np.median(scores) - 0.5 * np.std(scores)), detail


def evaluate(program_path):
    """OpenEvolve entry point: combined_score vs engineer baseline."""
    try:
        fn = load_candidate(program_path)
        cand, _ = evaluate_with(fn, TRAIN_SEEDS, TRAIN_KW)
        if cand is None:
            return {"combined_score": -100.0, "error": "invalid output"}
        base, _ = evaluate_with(engineer_baseline, TRAIN_SEEDS, TRAIN_KW)
        return {"combined_score": float(cand - base),
                "raw_metric": cand, "baseline_metric": base}
    except Exception as e:
        return {"combined_score": -100.0, "error": str(e)[:200]}


def validate_heldout(program_path):
    fn = load_candidate(program_path)
    m, detail = evaluate_with(fn, HELDOUT_SEEDS, HELDOUT_KW)
    return {"heldout_metric": m, "detail": detail}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        n, _ = evaluate_with(naive_detector, TRAIN_SEEDS, TRAIN_KW)
        b, _ = evaluate_with(engineer_baseline, TRAIN_SEEDS, TRAIN_KW)
        st, _ = evaluate_with(strong_detector, TRAIN_SEEDS, TRAIN_KW)
        bh, _ = evaluate_with(engineer_baseline, HELDOUT_SEEDS, HELDOUT_KW)
        sh, _ = evaluate_with(strong_detector, HELDOUT_SEEDS, HELDOUT_KW)
        print("TRAIN    naive:", round(n, 3), "| baseline:", round(b, 3),
              "| strong:", round(st, 3))
        print("HELDOUT           | baseline:", round(bh, 3),
              "| strong:", round(sh, 3))
    elif len(sys.argv) > 1 and sys.argv[1] == "--heldout":
        print(validate_heldout(sys.argv[2]))
    else:
        print(evaluate(sys.argv[1]))
