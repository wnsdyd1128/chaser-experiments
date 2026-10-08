"""Post hoc (experiment 41): if a memory access holds the shared L2 for its whole ~220 ns, the shared memory
system is busy D + M per microsecond (L2 requests x 48 ns plus memory accesses x 220 ns). AUC of D + M for a
missed deadline on the experiment 41 runs, against D and max(D, M); and on experiments 17-27 (P rows)."""
import json
from pathlib import Path
import memcost_analysis as ma
import rf_candidates as rc
import rf_devcheck as rd

W = Path('/workspace/experiments/chaser/.cache')
out = W / 'memory-cost-v1'
test = rc.load(W, sources=(('41', ((out.name, 'p', 'wfd', 'wfd'), (out.name, 'p_cgb', 'cgb', 'cgb'))),))
m = {}
for r in test:
    if r['case'] not in m:
        h, load, k = eval(r['case'].split('/', 1)[1])
        case = out / f'{h}/u{round(load * 100):03d}/s{k:02d}'
        m[r['case']] = ma.memory_demand(rc.yarda_tasks(case, json.loads((case / 'wfd/configuration.json').read_text())['tasks']))
y = [1 - r['label'] for r in test]
d = [r['features']['cache_demand'] for r in test]
mm = [m[r['case']] for r in test]
print('experiment 41 runs:', len(test), 'missed', sum(y))
print('AUC D', round(rd.auc(y, d), 3), '| max(D, M)', round(rd.auc(y, [max(a, b) for a, b in zip(d, mm)]), 3), '| D + M', round(rd.auc(y, [a + b for a, b in zip(d, mm)]), 3))
for cell in ('l2-low25', 'mem-low25'):
    idx = [i for i, r in enumerate(test) if f"'{cell}'" in r['case']]
    print(cell, 'mean D', round(sum(d[i] for i in idx) / len(idx), 3), 'mean M', round(sum(mm[i] for i in idx) / len(idx), 3),
          'mean D + M', round(sum(d[i] + mm[i] for i in idx) / len(idx), 3), 'missed', sum(y[i] for i in idx))
mem = [i for i, r in enumerate(test) if "'mem-low25'" in r['case']]
print('within mem cell: AUC D', round(rd.auc([y[i] for i in mem], [d[i] for i in mem]), 3), '| D + M', round(rd.auc([y[i] for i in mem], [d[i] + mm[i] for i in mem]), 3))
old = [r for r in rc.load(W) if r['candidate'] in rc.P_CANDIDATES]
cache = {}
for r in old:
    if r['case'] not in cache:
        source, key = r['case'].split('/', 1)
        h, load, k = eval(key)
        first = next(runs[0][0] for s, runs in rc.SOURCES if s == source)
        case = W / first / f'{h}/u{round(load * 100):03d}/s{k:02d}'
        cache[r['case']] = ma.memory_demand(rc.yarda_tasks(case, json.loads((case / 'wfd/configuration.json').read_text())['tasks']))
yo = [1 - r['label'] for r in old]
print('experiments 17-27 P rows:', len(old), '| AUC D', round(rd.auc(yo, [r['features']['cache_demand'] for r in old]), 3),
      '| D + M', round(rd.auc(yo, [r['features']['cache_demand'] + cache[r['case']] for r in old]), 3))
print('per experiment (P rows): AUC D | D + M | rows, missed')
for s, _ in rc.SOURCES:
    idx = [i for i, r in enumerate(old) if r['source'] == s]
    a = rd.auc([yo[i] for i in idx], [old[i]['features']['cache_demand'] for i in idx])
    b = rd.auc([yo[i] for i in idx], [old[i]['features']['cache_demand'] + cache[old[i]['case']] for i in idx])
    print(f'  {s:24s}', '-' if a is None else f'{a:.3f}', '|', '-' if b is None else f'{b:.3f}', '|', len(idx), sum(yo[i] for i in idx))
for t in (0.8, 0.9, 1.0):
    pred = [int(r['features']['cache_demand'] + cache[r['case']] >= t) for r in old]
    tp = sum(p and q for p, q in zip(pred, yo)); fp = sum(p and not q for p, q in zip(pred, yo)); fn = sum(q and not p for p, q in zip(pred, yo))
    print(f'  D + M >= {t}: predicted miss {sum(pred)}, missed {sum(yo)}, correct miss {tp}, false alarm {fp}, missed but predicted ok {fn}')
result = {'41': dict(rows=len(test), missed=sum(y), d=rd.auc(y, d), d_plus_m=rd.auc(y, [a + b for a, b in zip(d, mm)]))}
for s, _ in rc.SOURCES:
    idx = [i for i, r in enumerate(old) if r['source'] == s]
    result[s] = dict(rows=len(idx), missed=sum(yo[i] for i in idx),
                     d=rd.auc([yo[i] for i in idx], [old[i]['features']['cache_demand'] for i in idx]),
                     d_plus_m=rd.auc([yo[i] for i in idx], [old[i]['features']['cache_demand'] + cache[old[i]['case']] for i in idx]))
result['17-27 pooled'] = dict(rows=len(old), missed=sum(yo), d=rd.auc(yo, [r['features']['cache_demand'] for r in old]),
                              d_plus_m=rd.auc(yo, [r['features']['cache_demand'] + cache[r['case']] for r in old]))
Path(__file__).with_name('posthoc-occupancy.json').write_text(json.dumps(result, indent=1) + '\n')
