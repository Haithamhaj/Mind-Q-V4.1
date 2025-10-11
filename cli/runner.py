from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any, Dict, List

PHASES: List[tuple[str, str]] = [
    ("01_ingestion", "impl"),
    ("02_quality", "impl"),
]


def _call_phase(phase_dir: str, module_name: str, run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    mod = importlib.import_module(f"phases.{phase_dir}.{module_name}")
    return mod.run(run_id=run_id, inputs=inputs, config=config)


def flow(run_id: str) -> None:
    artifacts_root = "artifacts"
    data_csv = Path("data/basic.csv")
    fallback_csv = Path("data/header_offset.csv")
    input_files: List[str] = []
    if data_csv.exists():
        input_files = [str(data_csv.resolve())]
    elif fallback_csv.exists():
        input_files = [str(fallback_csv.resolve())]

    cfg: Dict[str, Any] = {"artifacts_root": artifacts_root}
    cur_inputs: Dict[str, Any] = {"files": input_files}

    results: List[Dict[str, Any]] = []
    for phase_dir, module in PHASES:
        try:
            res = _call_phase(phase_dir, module, run_id, cur_inputs, cfg)
            results.append({"phase": phase_dir, **res})
            raw = res.get("outputs", {}).get("raw")
            if raw:
                cur_inputs = {"files": [raw]}
        except Exception as exc:
            results.append({"phase": phase_dir, "status": "STOP", "error": str(exc)})
            break

    out = Path(artifacts_root) / run_id / "flow_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(prog="cli.runner")
    ap.add_argument("flow", help="run the default flow", nargs="?")
    ap.add_argument("--run-id", dest="run_id", default="demo")
    ns = ap.parse_args()
    flow(ns.run_id)


if __name__ == "__main__":
    main()
import argparse
import glob
import json
import pathlib
import sys
import importlib.util

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_ingest():
    try:
        from phases._01_ingestion.impl import run as ingest  # type: ignore
        return ingest
    except Exception:
        pass
    p = ROOT / 'phases' / '01_ingestion' / 'impl.py'
    if not p.exists():
        raise FileNotFoundError(p.as_posix())
    spec = importlib.util.spec_from_file_location('stage_01_impl', p.as_posix())
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader, 'Invalid import spec'
    spec.loader.exec_module(mod)  # type: ignore
    return mod.run  # type: ignore


def _load_quality():
    try:
        from phases._02_quality.impl import run as quality  # type: ignore
        return quality
    except Exception:
        pass
    p = ROOT / 'phases' / '02_quality' / 'impl.py'
    if not p.exists():
        raise FileNotFoundError(p.as_posix())
    spec = importlib.util.spec_from_file_location('stage_02_impl', p.as_posix())
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader, 'Invalid import spec'
    spec.loader.exec_module(mod)  # type: ignore
    return mod.run  # type: ignore


def _summary(meta_p: pathlib.Path, rep_p: pathlib.Path) -> dict:
    meta = json.load(open(meta_p, encoding='utf-8'))
    rep = json.load(open(rep_p, encoding='utf-8'))
    return {
        'status': rep.get('status'),
        'n_rows': meta.get('n_rows'),
        'n_cols': meta.get('n_cols'),
        'pivot_detected': meta.get('pivot_detected'),
        'pii_masked': meta.get('pii_masked'),
        'header_row': meta.get('header_row'),
        'encodings': meta.get('encodings'),
        'delimiters': meta.get('delimiters'),
        'preview_first_row': (meta.get('preview') or [{}])[0] if meta.get('preview') else {},
    }


def cmd_stage01(args: argparse.Namespace) -> int:
    ingest = _load_ingest()
    files: list[str] = []
    for pat in args.files:
        files.extend(glob.glob(pat))
    if not files:
        print('No input files')
        return 2
    run_id = args.run_id or 'manual-01'
    config = {
        'detect_encoding': True,
        'try_delimiters': [',',';','|','\t'],
        'header_max_seek_rows': 10,
        'arabic_normalize': True,
        'mask_pii': True,
        'pivot': {'detect': True, 'min_date_like_cols': 3, 'id_vars_max': 6},
        'preview_rows': 10,
    }
    res = ingest(run_id, {'files': files}, config)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if (res.get('status') != 'STOP') else 1


def cmd_stage02(args: argparse.Namespace) -> int:
    quality = _load_quality()
    run_id = args.run_id or 'manual-01'
    artifacts_root = args.artifacts_root or 'artifacts'
    raw_default = pathlib.Path(artifacts_root) / run_id / 'stage_01_ingestion' / 'raw.parquet'
    inputs = {'raw': str(args.raw or raw_default)}
    config = {
        'schema_uri': args.schema or str(ROOT / 'contracts' / 'schemas' / 'orders_v1.json'),
        'dq_uri': args.dq or str(ROOT / 'contracts' / 'dq' / 'orders.yml'),
        'preview_rows': 10,
        'artifacts_root': artifacts_root,
    }
    res = quality(run_id, inputs, config)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if (res.get('status') != 'STOP') else 1


def _write_samples(data_dir: pathlib.Path) -> None:
    data_dir.mkdir(exist_ok=True)
    (data_dir / 'basic.csv').write_text(
        'order_id,created_at,region,carrier,amount\nA1,2025-01-01,شرق,C1,100\nA2,2025-01-02,غرب,C2,150\n',
        encoding='utf-8')
    (data_dir / 'semicolon.csv').write_text(
        'id;date;amount\nB1;2025-02-01;200\nB2;2025-02-02;250\n', encoding='utf-8')
    (data_dir / 'header_offset.csv').write_text(
        '#junk1\n#junk2\norder_id,created_at,amount\nC1,2025-03-01,300\n', encoding='utf-8')
    (data_dir / 'pivot.csv').write_text(
        'client,service,2024-01,2024-02,2024-03\nX,DEL,10,11,12\nY,RET,1,2,3\n', encoding='utf-8')
    arabic = 'رقم,تاريخ,اسم,هاتف\r\nD1,2025-04-01,أحمد,0501234567\r\n'
    bytes_ = bytes(arabic, encoding='cp1256', errors='ignore')
    (data_dir / 'ar_cp1256.csv').write_bytes(bytes_)


def cmd_verify(args: argparse.Namespace) -> int:
    data_dir = ROOT / 'data'
    _write_samples(data_dir)
    ingest = _load_ingest()
    run_id = 'verify-01'
    files = [
        str(data_dir / 'basic.csv'),
        str(data_dir / 'semicolon.csv'),
        str(data_dir / 'header_offset.csv'),
        str(data_dir / 'pivot.csv'),
        str(data_dir / 'ar_cp1256.csv'),
    ]
    config = {
        'detect_encoding': True,
        'try_delimiters': [',',';','|','\t'],
        'header_max_seek_rows': 10,
        'arabic_normalize': True,
        'mask_pii': True,
        'pivot': {'detect': True, 'min_date_like_cols': 3, 'id_vars_max': 6},
        'preview_rows': 10,
    }
    res = ingest(run_id, {'files': files}, config)
    print('RES_JSON:')
    print(json.dumps(res, ensure_ascii=False, indent=2))
    base = ROOT / 'artifacts' / run_id / 'stage_01_ingestion'
    meta_p = base / 'meta_ingestion.json'
    rep_p = base / 'ingestion_report.json'
    raw_p = base / 'raw.parquet'
    logs_p = base / 'logs.jsonl'
    print('PATHS:')
    print('PATH_META:', meta_p.resolve().as_posix())
    print('PATH_REPORT:', rep_p.resolve().as_posix())
    print('PATH_RAW:', raw_p.resolve().as_posix())
    print('PATH_LOGS:', logs_p.resolve().as_posix())
    print('SUMMARY_JSON:')
    print(json.dumps(_summary(meta_p, rep_p), ensure_ascii=False, indent=2))
    return 0 if (res.get('status') != 'STOP') else 1


def main() -> int:
    ap = argparse.ArgumentParser('Mind-Q CLI')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p1 = sub.add_parser('stage01', help='Run stage 01 ingestion')
    p1.add_argument('--files', nargs='+', required=True, help='One or more file globs (e.g., data/*.csv)')
    p1.add_argument('--run-id', default='manual-01')
    p1.set_defaults(func=cmd_stage01)

    p2 = sub.add_parser('verify-samples', help='Generate samples and run stage 01')
    p2.set_defaults(func=cmd_verify)

    p3 = sub.add_parser('stage02', help='Run stage 02 quality')
    p3.add_argument('--run-id', default='manual-01')
    p3.add_argument('--raw', help='Path to raw parquet from stage 01 (optional)')
    p3.add_argument('--schema', help='Path to schema JSON (optional)')
    p3.add_argument('--dq', help='Path to DQ YAML (optional)')
    p3.add_argument('--artifacts-root', default='artifacts')
    p3.set_defaults(func=cmd_stage02)

    args = ap.parse_args()
    return int(args.func(args) or 0)


if __name__ == '__main__':
    raise SystemExit(main())
