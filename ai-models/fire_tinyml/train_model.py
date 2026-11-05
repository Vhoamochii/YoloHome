"""Train temperature-dominant logistic regression from supplied labels, not hand-picked weights."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]


def load_rows(path, header):
    with path.open(encoding="utf-8-sig", newline="") as f:
        if header:
            rows = list(csv.DictReader(f))
            return [(float(r['temperature']), float(r['humidity']), int(r['label']), r['session_id']) for r in rows]
        return [(float(t), float(h), int(y), "reference") for t, h, y in csv.reader(f)]


def fit(X, y):
    # A 100 percentage-point RH change may offset at most 1 degree C.
    # z = a*(T-35)/10 + c*(RH-50)/50 + b, a>0, -.05*a <= c <= 0.
    counts = np.bincount(y.astype(int), minlength=2)
    if min(counts) == 0:
        raise ValueError("Training requires both classes")
    sample_weight = np.where(y == 1, len(y)/(2*counts[1]), len(y)/(2*counts[0]))
    def loss(w):
        z = X @ w
        p = 1/(1+np.exp(-np.clip(z, -500, 500)))
        value = np.mean(sample_weight*(np.logaddexp(0, z)-y*z)) + .002*np.dot(w[:2], w[:2])
        grad = X.T @ (sample_weight*(p-y))/len(y) + np.r_[.004*w[:2], 0]
        return value, grad
    result = minimize(loss, [1., -.025, 0.], jac=True, method='SLSQP',
                      bounds=[(.001, None), (None, 0), (None, None)],
                      constraints=[{'type':'ineq', 'fun':lambda w:.05*w[0]+w[1],
                                    'jac':lambda w:np.array([.05, 1., 0.])}],
                      options={'ftol':1e-12, 'maxiter':1000})
    if not result.success:
        raise RuntimeError(result.message)
    return result.x.astype(np.float32)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path, help='Real CSV: temperature,humidity,label,session_id')
    p.add_argument('--out', type=Path, default=ROOT/'models/temperature_priority')
    p.add_argument('--install', action='store_true')
    args = p.parse_args()
    paths = [args.csv] if args.csv else sorted((ROOT/'data/reference').glob('*.csv'))
    raw = [r for path in paths for r in load_rows(path, bool(args.csv))]
    kept = [r for r in raw if np.isfinite(r[:3]).all() and -40 <= r[0] <= 80 and 0 <= r[1] <= 100 and r[2] in (0, 1)]
    if args.csv and len(kept) != len(raw):
        raise ValueError('Invalid measurements/labels in real data; inspect CSV first')
    # Same labeled pair once in the reference set; once per acquisition session in real data.
    rows = list(dict.fromkeys(kept))
    values = np.array([r[:3] for r in rows], dtype=np.float64)
    groups = np.array([r[3] for r in rows])
    X = np.c_[(values[:,0]-35)/10, (values[:,1]-50)/50, np.ones(len(values))]
    y = values[:,2]
    train = np.arange(len(y)); test = None
    if args.csv:
        from sklearn.model_selection import GroupShuffleSplit
        if len(set(groups)) < 6 or any(not g.strip() for g in groups):
            raise ValueError('Need >=6 independent non-empty sessions; collect more for reliable assessment')
        ntest = max(2, int(np.ceil(.2*len(set(groups)))))
        for tr, te in GroupShuffleSplit(n_splits=100, test_size=ntest, random_state=42).split(X, y, groups):
            if set(y[tr]) == {0, 1} and set(y[te]) == {0, 1}:
                train, test = tr, te
                break
        if test is None:
            raise ValueError('Cannot split independent sessions with both classes; collect more data')
    a, c, b = fit(X[train], y[train])
    model = dict(kind='temperature_dominant_logistic', a=float(a), c=float(c), b=float(b),
                 mean=[35.,50.], scale=[10.,50.], humidity_full_range_equivalent_max_c=1.,
                 sources={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
                 objective='class-balanced binary cross-entropy + 0.002*(a*a+c*c)',
                 constraint='a>=0.001; -0.05*a<=c<=0')
    model['id'] = hashlib.sha256(json.dumps(model, sort_keys=True).encode()).hexdigest()[:12]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'model.json').write_text(json.dumps(model, indent=2)+'\n', encoding='utf-8')
    def num(x):
        s = format(float(x), '.9g')
        return s + ('' if '.' in s or 'e' in s else '.0') + 'f'
    header = '#pragma once\n// Learned coefficients: scripts/train_temperature_model.py\nnamespace tinyfire { namespace weights {\n'
    header += 'static const char id[] = "'+model['id']+'";\n'
    for name, value in [('a',a),('c',c),('b',b)]:
        header += 'static const float '+name+' = '+num(value)+';\n'
    header += '}}\n'
    (args.out/'temperature_model.h').write_text(header, encoding='utf-8')
    idx = test if test is not None else train
    scores = 1/(1+np.exp(-np.clip(X[idx]@np.array([a,c,b]),-500,500)))
    report = dict(raw_rows=len(raw), invalid_rows_excluded=len(raw)-len(kept), unique_rows=len(rows),
                  train_rows=len(train), evaluated_rows=len(idx),
                  evaluation='held-out sessions' if test is not None else 'in-sample reference fit ONLY; no independent accuracy claim',
                  coefficients=model, confusion={})
    for threshold in [.5,.8,.9]:
        pred = scores >= threshold
        report['confusion'][str(threshold)] = [[int(((y[idx]==actual)&(pred==guess)).sum()) for guess in [0,1]] for actual in [0,1]]
    if test is not None:
        report['sessions'] = {'train':sorted(set(groups[train])), 'test':sorted(set(groups[test]))}
    (args.out/'training_report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    if args.install:
        import shutil
        shutil.copyfile(args.out/'temperature_model.h', ROOT/'firmware/include/temperature_model.h')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
