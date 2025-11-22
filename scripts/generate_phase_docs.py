#!/usr/bin/env python3
"""
Generate dynamic documentation appendix from actual codebase.

This script extracts PIPELINE_PHASE_SEQUENCE, PHASE_MODULES, function signatures,
and output artifacts from the actual implementation files and generates a markdown
appendix that can be injected into PHASES_DETAILED_GUIDE.md.

Usage:
    python scripts/generate_phase_docs.py
    python scripts/generate_phase_docs.py --output docs/GENERATED_APPENDIX.md
"""

import argparse
import ast
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def extract_pipeline_sequence() -> Optional[Tuple[str, int, List[str]]]:
    """Extract PIPELINE_PHASE_SEQUENCE from pipeline_api/app.py."""
    app_py = PROJECT_ROOT / "backend/src/app/services/pipeline_api/app.py"
    if not app_py.exists():
        return None
    
    content = app_py.read_text(encoding="utf-8")
    lines = content.split("\n")
    
    # Find PIPELINE_PHASE_SEQUENCE definition
    for i, line in enumerate(lines, start=1):
        if "PIPELINE_PHASE_SEQUENCE" in line and "Tuple[str" in line:
            # Extract the sequence
            sequence = []
            in_sequence = False
            for j in range(i - 1, len(lines)):
                if "(" in lines[j]:
                    in_sequence = True
                if in_sequence:
                    # Extract strings
                    matches = re.findall(r'"([^"]+)"', lines[j])
                    sequence.extend(matches)
                if ")" in lines[j] and in_sequence:
                    break
            return (str(app_py.relative_to(PROJECT_ROOT)), i, sequence)
    
    return None


def extract_phase_modules() -> Optional[Tuple[str, int, Dict[str, str]]]:
    """Extract PHASE_MODULES mapping from pipeline_api/app.py."""
    app_py = PROJECT_ROOT / "backend/src/app/services/pipeline_api/app.py"
    if not app_py.exists():
        return None
    
    content = app_py.read_text(encoding="utf-8")
    lines = content.split("\n")
    
    # Find PHASE_MODULES definition
    for i, line in enumerate(lines, start=1):
        if "PHASE_MODULES" in line and ("Dict" in line or ":" in line):
            modules = {}
            in_dict = False
            for j in range(i - 1, min(len(lines), i + 50)):
                if "{" in lines[j]:
                    in_dict = True
                if in_dict:
                    # Extract key-value pairs: "phase_key": module_path
                    match = re.search(r'"([^"]+)":\s*"([^"]+)"', lines[j])
                    if match:
                        modules[match.group(1)] = match.group(2)
                if "}" in lines[j] and in_dict:
                    break
            return (str(app_py.relative_to(PROJECT_ROOT)), i, modules)
    
    return None


def extract_run_signature(impl_path: Path) -> Optional[Tuple[int, str]]:
    """Extract the run() function signature from an impl.py file."""
    if not impl_path.exists():
        return None
    
    content = impl_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    
    for i, line in enumerate(lines, start=1):
        if re.match(r"^def run\(", line.strip()):
            # Extract signature (may span multiple lines)
            sig = line.strip()
            j = i
            while ")" not in sig and j < len(lines):
                sig += " " + lines[j].strip()
                j += 1
            return (i, sig)
    
    return None


def extract_stage_outputs(impl_path: Path) -> Set[str]:
    """Extract artifact file names written by a stage (basic heuristic)."""
    if not impl_path.exists():
        return set()
    
    content = impl_path.read_text(encoding="utf-8")
    
    # Look for common patterns: .write_*, out_dir / "filename", "filename.json"
    patterns = [
        r'["\']([a-z_]+\.(?:json|parquet|jsonl|yaml|yml|md|txt))["\']',
        r'out_dir\s*/\s*["\']([^"\']+)["\']',
        r'Path\(["\']([^"\']+\.(?:json|parquet|jsonl|yaml|yml))["\']',
    ]
    
    outputs = set()
    for pattern in patterns:
        outputs.update(re.findall(pattern, content))
    
    return outputs


def extract_stop_warn_conditions(impl_path: Path) -> Dict[str, List[str]]:
    """Extract STOP and WARN condition comments/strings from impl.py."""
    if not impl_path.exists():
        return {"STOP": [], "WARN": []}
    
    content = impl_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    
    stop_conditions = []
    warn_conditions = []
    
    for line in lines:
        # Look for status assignments or raise statements
        if '"STOP"' in line or "'STOP'" in line or "status: STOP" in line:
            # Extract context
            clean = line.strip()
            if clean and not clean.startswith("#"):
                stop_conditions.append(clean[:100])
        
        if '"WARN"' in line or "'WARN'" in line or "status: WARN" in line:
            clean = line.strip()
            if clean and not clean.startswith("#"):
                warn_conditions.append(clean[:100])
    
    return {
        "STOP": stop_conditions[:5],  # Limit to first 5
        "WARN": warn_conditions[:5],
    }


def generate_appendix() -> str:
    """Generate the full documentation appendix."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    md = []
    md.append("# AUTO-GENERATED DOCUMENTATION APPENDIX")
    md.append(f"\n**Generated:** {now}")
    md.append("**Source:** `scripts/generate_phase_docs.py`")
    md.append("\n> ⚠️ This appendix is auto-generated. Do not edit manually.")
    md.append("> Run `make docs` or `python scripts/generate_phase_docs.py` to regenerate.")
    md.append("\n---\n")
    
    # 1. PIPELINE_PHASE_SEQUENCE
    md.append("## 1. Pipeline Phase Sequence\n")
    seq_info = extract_pipeline_sequence()
    if seq_info:
        filepath, line_num, sequence = seq_info
        md.append(f"**Source:** `{filepath}` (Line {line_num})\n")
        md.append("```python")
        md.append("PIPELINE_PHASE_SEQUENCE = (")
        for phase in sequence:
            md.append(f'    "{phase}",')
        md.append(")")
        md.append("```\n")
        md.append(f"**Total Phases:** {len(sequence)}\n")
    else:
        md.append("❌ Could not extract PIPELINE_PHASE_SEQUENCE\n")
    
    # 2. PHASE_MODULES mapping
    md.append("\n## 2. Phase Module Mapping\n")
    mod_info = extract_phase_modules()
    if mod_info:
        filepath, line_num, modules = mod_info
        md.append(f"**Source:** `{filepath}` (Line {line_num})\n")
        md.append("| Phase Key | Implementation Module |")
        md.append("|-----------|----------------------|")
        for key in sorted(modules.keys()):
            md.append(f"| `{key}` | `{modules[key]}` |")
        md.append("")
    else:
        md.append("❌ Could not extract PHASE_MODULES\n")
    
    # 3. Stage Implementations
    md.append("\n## 3. Stage Implementation Details\n")
    
    stages = [
        ("01_ingestion", "phases/01_ingestion/impl.py"),
        ("02_quality", "phases/02_quality/impl.py"),
        ("03_schema", "phases/03_schema/impl.py"),
        ("03_5_textops", "backend/src/app/services/stage_03_5_textops/impl.py"),
        ("04_profile", "phases/04_profile/impl.py"),
        ("05_missing", "phases/05_missing/impl.py"),
        ("06_standardize", "phases/06_standardize/impl.py"),
        ("06_feature_eng", "phases/06_feature_eng/impl.py"),
        ("07_readiness", "phases/07_readiness/impl.py"),
        ("08_insights", "src/app/services/stage_08_insights/impl.py"),
        ("09_business_validation", "phases/09_business_validation/impl.py"),
        ("10_bi", "phases/phase10_bi/impl.py"),
    ]
    
    for stage_key, impl_path_str in stages:
        impl_path = PROJECT_ROOT / impl_path_str
        md.append(f"\n### Stage: `{stage_key}`\n")
        md.append(f"**Implementation:** `{impl_path_str}`\n")
        
        # Run signature
        sig_info = extract_run_signature(impl_path)
        if sig_info:
            line_num, signature = sig_info
            md.append(f"**Run Function:** Line {line_num}")
            md.append(f"```python\n{signature}\n```\n")
        
        # Outputs
        outputs = extract_stage_outputs(impl_path)
        if outputs:
            md.append(f"**Detected Outputs:** {', '.join(sorted(outputs))}\n")
        
        # STOP/WARN conditions
        conditions = extract_stop_warn_conditions(impl_path)
        if conditions["STOP"]:
            md.append("**STOP Conditions Found:**")
            for cond in conditions["STOP"]:
                md.append(f"- `{cond}`")
            md.append("")
        if conditions["WARN"]:
            md.append("**WARN Conditions Found:**")
            for cond in conditions["WARN"]:
                md.append(f"- `{cond}`")
            md.append("")
    
    # 4. Contract Files Referenced
    md.append("\n## 4. Referenced Contract Files\n")
    contract_files = [
        "contracts/nzv/policy.yml",
        "contracts/kpis/critical_columns.yml",
        "contracts/analytics/gate.yml",
        "contracts/payment/payment_rules.yml",
        "contracts/impute/policy_relaxed.yml",
        "contracts/models/models_catalog.yml",
    ]
    
    md.append("| Contract File | Exists |")
    md.append("|--------------|--------|")
    for contract in contract_files:
        path = PROJECT_ROOT / contract
        status = "✅" if path.exists() else "❌"
        md.append(f"| `{contract}` | {status} |")
    md.append("")
    
    # 5. Validation Metadata
    md.append("\n## 5. Validation Metadata\n")
    md.append(f"- **Generation Date:** {now}")
    md.append(f"- **Project Root:** `{PROJECT_ROOT}`")
    md.append(f"- **Script Version:** 1.0.0")
    md.append("\n---\n")
    md.append("**End of Auto-Generated Appendix**")
    
    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(
        description="Generate dynamic documentation appendix from codebase"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=PROJECT_ROOT / "docs/GENERATED_APPENDIX.md",
        help="Output file path (default: docs/GENERATED_APPENDIX.md)",
    )
    args = parser.parse_args()
    
    appendix = generate_appendix()
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(appendix, encoding="utf-8")
    
    print(f"✅ Generated documentation appendix: {args.output}")
    print(f"📊 Total lines: {len(appendix.split(chr(10)))}")


if __name__ == "__main__":
    main()
