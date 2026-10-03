"""Which PhonoLib features does the old basis retrieve correctly and the new one miss?

Gate 3's act_prec is a feature-recall score: over the dimensions where the query
segment is positive, the fraction where the retrieved set is also positive. The
summary basis wins place retrieval by a wide margin and still loses act_prec
0.499 to the old basis's 0.649, and no change to the geometry has moved that
number at all. So the deficit is not place and not the metric form -- it is
feature coverage.

This breaks act_prec down per feature dimension, under both bases, with the
metric fitted on training folds only exactly as Gate 3 does. A dimension where
the old basis recovers most of its positives and the new one recovers almost
none names the axis the summary basis is missing.

The bias that matters: 38 PhonoLib columns are mostly negative, so a dimension
can score badly simply because few segments carry it. Dimensions are therefore
reported with their positive count, and a low score on a dimension with almost
no positives is noise, not a finding.

Run: python tools/audit_loco_features.py
"""

import io
import json
import os

import numpy as np

import gate_retrieval as G

DATA = G.DATA
OUT = os.path.join(DATA, 'loco_feature_audit.json')

# Below this many positives across all held-out segments a dimension cannot
# carry a reliable rate; 2 keeps single-segment dimensions out of the ranking.
MIN_POSITIVES = 8


def main():
    syms, bases = G.load_bases()
    wanted = set(syms)
    feat, feats, _, _ = G.load_phoible(wanted)
    per_lang, _ = G.load_svmcc_tokens(wanted)
    order = {s: i for i, s in enumerate(syms)}
    n = len(syms)
    nf = len(next(iter(feat.values())))
    F = np.zeros((n, nf))
    for s, v in feat.items():
        F[order[s]] = v

    print('LOCO act_prec decomposed over %d PhonoLib dimensions' % nf)
    print('metric fitted on training folds only, same k=%d as Gate 3\n' % G.KNN)

    hit = {b: np.zeros(nf) for b in bases}   # positives carried by the retrieval
    pos = {b: np.zeros(nf) for b in bases}   # positives the queries actually have

    for held in G.SVMCC:
        held_rows = np.array([order[s] for s in sorted(per_lang[held])])
        train_syms = sorted(set().union(
            *[set(per_lang[l]) for l in G.SVMCC if l != held])
            - set(per_lang[held]))
        if len(train_syms) < G.MIN_TRAIN:
            continue
        ref = np.array([order[s] for s in train_syms])
        Ftrain = [order[s] for s in train_syms if s in feat]
        mask = np.ones(n, bool)
        mask[held_rows] = False
        pool = np.where(mask)[0]

        for bname, (dims, X) in bases.items():
            w, _, live = G.fit_metric(X, F, Ftrain, ref)
            Z, dead = G._standardise(X, ref)
            D = np.sqrt(np.maximum(((Z[:, None, :] - Z[None, :, :]) ** 2) @ w,
                                   0.0))
            np.fill_diagonal(D, np.inf)
            for row in held_rows:
                cand = pool[pool != row]
                nb = cand[np.argsort(D[row][cand], kind='stable')[:G.KNN]]
                pred = F[nb].mean(axis=0)
                act = F[row] > 0.5
                hit[bname][act] += (pred[act] >= 0.5).astype(float)
                pos[bname][act] += 1.0

    rates = {}
    for b in bases:
        with np.errstate(invalid='ignore', divide='ignore'):
            rates[b] = np.where(pos[b] > 0, hit[b] / np.maximum(pos[b], 1), np.nan)

    names = list(feats)
    ranked = []
    for j in range(nf):
        po = pos['old'][j]
        if po < MIN_POSITIVES:
            continue
        ro, rn = rates['old'][j], rates['new'][j]
        ranked.append((ro - rn, names[j], int(po), ro, rn))
    ranked.sort(reverse=True)

    print('dimensions where the old basis recovers positives the new one '
          'misses (>=%d positives):' % MIN_POSITIVES)
    print('  %-22s %6s %8s %8s' % ('feature', 'pos', 'old', 'new'))
    for delta, nm, po, ro, rn in ranked[:12]:
        print('  %-22s %6d %8.3f %8.3f   delta %+.3f'
              % (nm, po, ro, rn, delta))

    print('\ndimensions where the new basis is BETTER:')
    for delta, nm, po, ro, rn in sorted(ranked)[:6]:
        print('  %-22s %6d %8.3f %8.3f   delta %+.3f' % (nm, po, ro, rn, delta))

    tot_o = hit['old'].sum() / max(pos['old'].sum(), 1)
    tot_n = hit['new'].sum() / max(pos['new'].sum(), 1)
    print('\noverall act_prec pooled over folds: old %.4f  new %.4f'
          % (tot_o, tot_n))
    share = sum(max(d, 0) * p for d, _, p, _, _ in ranked[:12]) \
        / max(pos['old'].sum(), 1)
    print('the top %d dimensions alone account for %.1f%% of the old basis\'s '
          'advantage' % (len(ranked[:12]), 100 * share))

    def _jsonable(a):
        return np.where(np.isnan(a), None, a).tolist()

    out = {'feature_names': names,
           'positives': {b: pos[b].tolist() for b in bases},
           'recall': {b: _jsonable(rates[b]) for b in bases},
           'min_positives': MIN_POSITIVES,
           'pooled_act_prec': {'old': tot_o, 'new': tot_n}}
    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    print('\nwrote %s' % OUT)


if __name__ == '__main__':
    main()