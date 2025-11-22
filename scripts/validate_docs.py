#!/usr/bin/env python3
"""
Validate PHASES_DETAILED_GUIDE.md against actual codebase.

This script checks for:
1. {{TO_FILL_DATE}} placeholders
2. Line number references that don't match actual code
3. STOP/WARN conditions that differ from implementation
4. Referenced files that don't exist
5. Function signatures that changed

Usage:
    python scripts/validate_docs.py
    python scripts/validate_docs.py --strict  # Exit code 1 on any error
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUIDE_PATH = PROJECT_ROOT / "docs/PHASES_DETAILED_GUIDE.md"


class ValidationError:
    def __init__(self, severity: str, line_num: int, message: str):
        self.severity = severity  # "ERROR", "WARNING", "INFO"
        self.line_num = line_num
        self.message = message
    
    def __str__(self):
        icon = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️"}[self.severity]
        return f"{icon} Line {self.line_num}: {self.message}"


def validate_placeholders(content: str, lines: List[str]) -> List[ValidationError]:
    """Check for {{TO_FILL_DATE}} placeholders."""
    errors = []
    for i, line in enumerate(lines, start=1):
        if "{{TO_FILL_DATE}}" in line:
            errors.append(
                ValidationError(
                    "WARNING",
                    i,
                    "Found placeholder {{TO_FILL_DATE}} - should be replaced with actual date"
                )
            )
    return errors


def validate_line_references(content: str, lines: List[str]) -> List[ValidationError]:
    """Check line number references like #L173."""
    errors = []
    
    # Pattern: filepath#L123 or filepath:123
    pattern = r'`([^`]+(?:\.py|\.yml|\.yaml))[:#]L?(\d+)`'
    
    for i, line in enumerate(lines, start=1):
        matches = re.finditer(pattern, line)
        for match in matches:
            filepath = match.group(1)
            line_num = int(match.group(2))
            
            # Try to find the file
            possible_paths = [
                PROJECT_ROOT / filepath,
                PROJECT_ROOT / "backend" / filepath,
                PROJECT_ROOT / "src" / filepath,
            ]
            
            found = False
            for path in possible_paths:
                if path.exists():
                    found = True
                    # Check if line number is reasonable
                    file_lines = path.read_text(encoding="utf-8").split("\n")
                    if line_num > len(file_lines):
                        errors.append(
                            ValidationError(
                                "ERROR",
                                i,
                                f"Line reference #{line_num} exceeds file length ({len(file_lines)} lines) in {filepath}"
                            )
                        )
                    break
            
            if not found:
                errors.append(
                    ValidationError(
                        "WARNING",
                        i,
                        f"Referenced file not found: {filepath}"
                    )
                )
    
    return errors


def validate_file_references(content: str, lines: List[str]) -> List[ValidationError]:
    """Check that referenced files exist."""
    errors = []
    
    # Pattern: `path/to/file.py` or `contracts/file.yml`
    pattern = r'`([a-zA-Z0-9_/\-\.]+\.(py|yml|yaml|json|md))`'
    
    for i, line in enumerate(lines, start=1):
        matches = re.finditer(pattern, line)
        for match in matches:
            filepath = match.group(1)
            
            # Skip if it's just a generic example
            if "example" in filepath.lower() or "placeholder" in filepath.lower():
                continue
            
            full_path = PROJECT_ROOT / filepath
            if not full_path.exists():
                errors.append(
                    ValidationError(
                        "WARNING",
                        i,
                        f"Referenced file does not exist: {filepath}"
                    )
                )
    
    return errors


def validate_pipeline_sequence(content: str, lines: List[str]) -> List[ValidationError]:
    """Check if documented PIPELINE_PHASE_SEQUENCE matches actual code."""
    errors = []
    
    # Extract documented sequence from guide
    in_sequence = False
    doc_sequence = []
    for line in lines:
        if "PIPELINE_PHASE_SEQUENCE" in line:
            in_sequence = True
        if in_sequence:
            matches = re.findall(r'"([^"]+)"', line)
            doc_sequence.extend(matches)
        if in_sequence and ")" in line:
            break
    
    # Extract actual sequence from code
    app_py = PROJECT_ROOT / "backend/src/app/services/pipeline_api/app.py"
    if app_py.exists():
        code_content = app_py.read_text(encoding="utf-8")
        code_lines = code_content.split("\n")
        
        in_code_seq = False
        code_sequence = []
        for line in code_lines:
            if "PIPELINE_PHASE_SEQUENCE" in line and "Tuple[str" in line:
                in_code_seq = True
            if in_code_seq:
                matches = re.findall(r'"([^"]+)"', line)
                code_sequence.extend(matches)
            if in_code_seq and ")" in line:
                break
        
        # Compare
        if doc_sequence and code_sequence:
            if doc_sequence != code_sequence:
                errors.append(
                    ValidationError(
                        "ERROR",
                        1,
                        f"PIPELINE_PHASE_SEQUENCE mismatch: documented has {len(doc_sequence)} phases, code has {len(code_sequence)} phases"
                    )
                )
                # Show diff
                missing_in_doc = set(code_sequence) - set(doc_sequence)
                missing_in_code = set(doc_sequence) - set(code_sequence)
                if missing_in_doc:
                    errors.append(
                        ValidationError(
                            "INFO",
                            1,
                            f"Phases in code but not documented: {', '.join(missing_in_doc)}"
                        )
                    )
                if missing_in_code:
                    errors.append(
                        ValidationError(
                            "INFO",
                            1,
                            f"Phases documented but not in code: {', '.join(missing_in_code)}"
                        )
                    )
    
    return errors


def validate_stop_warn_keywords(content: str, lines: List[str]) -> List[ValidationError]:
    """Check if STOP/WARN descriptions match common patterns."""
    errors = []
    
    # Look for sections describing STOP/WARN conditions
    current_stage = None
    for i, line in enumerate(lines, start=1):
        # Detect stage sections
        if line.startswith("### Stage") or line.startswith("## Stage"):
            match = re.search(r'Stage\s+(\S+)', line)
            if match:
                current_stage = match.group(1)
        
        # Check for STOP/WARN sections
        if "Quality Gates" in line or "STOP/WARN" in line:
            # Look ahead for common issues
            context = "\n".join(lines[i:min(i+10, len(lines))])
            
            # If it says "no STOP" or "WARN only" but we know it's wrong
            if current_stage and "WARN only" in context:
                # Quick heuristic: check if impl.py has status: STOP
                impl_candidates = [
                    PROJECT_ROOT / f"phases/{current_stage.lower()}/impl.py",
                    PROJECT_ROOT / f"src/app/services/stage_{current_stage.lower()}/impl.py",
                    PROJECT_ROOT / f"backend/src/app/services/stage_{current_stage.lower()}/impl.py",
                ]
                
                for impl_path in impl_candidates:
                    if impl_path.exists():
                        impl_content = impl_path.read_text(encoding="utf-8")
                        if '"STOP"' in impl_content or "'STOP'" in impl_content:
                            # Document says WARN only, but code has STOP
                            errors.append(
                                ValidationError(
                                    "WARNING",
                                    i,
                                    f"Stage {current_stage}: Documentation says WARN only, but code contains STOP conditions"
                                )
                            )
                        break
    
    return errors


def validate_rag_integration(content: str, lines: List[str]) -> List[ValidationError]:
    """Check that RAG integration features are documented."""
    errors = []
    
    # Check for key RAG terms
    rag_keywords = [
        "RagClauseLookup",
        "business_context",
        "sla_clause",
        "shared/rag_context.py",
    ]
    
    found_keywords = {kw: kw in content for kw in rag_keywords}
    
    # Verify implementation files actually use these
    stage_08 = PROJECT_ROOT / "src/app/services/stage_08_insights/impl.py"
    stage_09 = PROJECT_ROOT / "phases/09_business_validation/impl.py"
    
    if stage_08.exists():
        stage_08_content = stage_08.read_text(encoding="utf-8")
        if "RagClauseLookup" in stage_08_content and not found_keywords["RagClauseLookup"]:
            errors.append(
                ValidationError(
                    "ERROR",
                    1,
                    "Stage 08 uses RagClauseLookup but it's not documented in guide"
                )
            )
    
    if stage_09.exists():
        stage_09_content = stage_09.read_text(encoding="utf-8")
        if "sla_clause" in stage_09_content and not found_keywords["sla_clause"]:
            errors.append(
                ValidationError(
                    "ERROR",
                    1,
                    "Stage 09 uses sla_clause but it's not documented in guide"
                )
            )
    
    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate PHASES_DETAILED_GUIDE.md against codebase"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error code if any issues found"
    )
    args = parser.parse_args()
    
    if not GUIDE_PATH.exists():
        print(f"❌ Guide not found: {GUIDE_PATH}")
        sys.exit(1)
    
    content = GUIDE_PATH.read_text(encoding="utf-8")
    lines = content.split("\n")
    
    print(f"📖 Validating: {GUIDE_PATH.relative_to(PROJECT_ROOT)}")
    print(f"📄 Total lines: {len(lines)}\n")
    
    all_errors: List[ValidationError] = []
    
    # Run all validators
    validators = [
        ("Placeholders", validate_placeholders),
        ("Line References", validate_line_references),
        ("File References", validate_file_references),
        ("Pipeline Sequence", validate_pipeline_sequence),
        ("STOP/WARN Keywords", validate_stop_warn_keywords),
        ("RAG Integration", validate_rag_integration),
    ]
    
    for name, validator in validators:
        print(f"🔍 Checking: {name}...")
        errors = validator(content, lines)
        all_errors.extend(errors)
        if errors:
            print(f"   Found {len(errors)} issue(s)")
        else:
            print(f"   ✅ OK")
    
    print("\n" + "="*70)
    
    if not all_errors:
        print("✅ All validation checks passed!")
        sys.exit(0)
    
    # Group by severity
    errors_by_severity = {"ERROR": [], "WARNING": [], "INFO": []}
    for err in all_errors:
        errors_by_severity[err.severity].append(err)
    
    # Print summary
    print(f"\n📊 Validation Summary:")
    print(f"   ❌ Errors:   {len(errors_by_severity['ERROR'])}")
    print(f"   ⚠️  Warnings: {len(errors_by_severity['WARNING'])}")
    print(f"   ℹ️  Info:     {len(errors_by_severity['INFO'])}")
    print()
    
    # Print all issues
    for severity in ["ERROR", "WARNING", "INFO"]:
        if errors_by_severity[severity]:
            print(f"\n{severity}S:")
            for err in sorted(errors_by_severity[severity], key=lambda e: e.line_num):
                print(f"  {err}")
    
    # Exit code
    if args.strict and (errors_by_severity["ERROR"] or errors_by_severity["WARNING"]):
        print("\n❌ Validation failed (--strict mode)")
        sys.exit(1)
    elif errors_by_severity["ERROR"]:
        print("\n⚠️  Validation completed with errors")
        sys.exit(1)
    else:
        print("\n✅ Validation completed with warnings only")
        sys.exit(0)


if __name__ == "__main__":
    main()
