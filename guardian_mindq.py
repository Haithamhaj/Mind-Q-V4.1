#!/usr/bin/env python3
"""
Mind-Q Guardian Adapter
=======================

A specialized Guardian adapter for the Mind-Q V4.1 logistics data pipeline.
Provides phase-aware context generation and pipeline-specific monitoring.

Features:
- Automatic phase detection and spine generation
- Phase card generation for each pipeline stage
- Reduced context strings optimized for LLM agents
- KPI and business impact tracking per phase
"""

import os
import re
import json
import yaml
import subprocess
import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class MindQStatus:
    """
    Structured status representation for Mind-Q Guardian.
    Used for compact MDC integration.
    """
    status: str  # 'NO_CHANGES' | 'NO_PLAN_FOR_CHANGES' | 'PLAN_VIOLATIONS' | 'ON_TRACK'
    last_goal: str  # Truncated to 100 chars
    target_phases: List[str]
    planned_files_count: int
    extra_files_count: int


@dataclass
class CleanupItem:
    """
    Structured representation of a cleanup/refactoring opportunity.
    Used by the deep code scanner for Refactor Radar.
    """
    id: str  # e.g., "CLEANUP-001"
    kind: str  # unused_import, unused_symbol, orphan_module, duplicate_function, etc.
    file: str  # Relative path
    symbol: Optional[str]  # Function name, class name, import name, or None
    why_suspected: str  # Short explanation
    confidence: float  # 0.0-1.0
    related_phase: Optional[str]  # Phase ID if applicable
    suggested_action: str  # e.g., "remove_import_on_phase_04_refactor"
    line_number: Optional[int] = None  # Line number if applicable
    details: Optional[str] = None  # Additional details


class MindQGuardianAdapter:
    """
    Mind-Q specific Guardian adapter for phase-aware project analysis.
    
    This adapter understands the Mind-Q pipeline structure and can generate
    optimized context for AI agents working on logistics data pipelines.
    """
    
    def __init__(self, mindq_repo_path: str):
        """
        Initialize the Mind-Q Guardian adapter.
        
        Args:
            mindq_repo_path: Path to the Mind-Q repository root
        """
        self.repo_path = Path(mindq_repo_path).resolve()
        self.phases_path = self.repo_path / "phases"
        self.docs_path = self.repo_path / "docs"
        self.guide_path = self.docs_path / "PHASES_DETAILED_GUIDE.md"
        
        # Pipeline phase sequence (canonical order)
        self.phase_sequence = [
            "01_ingestion",
            "02_quality",
            "03_schema",
            "03_5_textops",
            "04_profile",
            "05_missing",
            "06_standardize",
            "06_feature_eng",
            "07_readiness",
            "07_5_feature_report",
            "07_6_llm_summary",
            "07_7_business_correlations",
            "07_analytics",
            "07_timeseries",
            "07_knime_bridge",
            "08_insights",
            "09_business_validation",
            "09_5_causal",
            "10_bi",
            "11_ml_lab",
            "12_routing"
        ]
        
        # Phase metadata cache
        self._phase_metadata = {}
        self._spine_data = None
        
    def build_spine(self) -> Dict[str, Any]:
        """
        Build the Mind-Q pipeline spine from PHASES_DETAILED_GUIDE.md.
        
        Returns:
            Dictionary containing spine structure with phases, flows, and KPIs
        """
        if not self.guide_path.exists():
            self._spine_data = self._build_default_spine()
            return self._spine_data
        
        with open(self.guide_path, 'r', encoding='utf-8') as f:
            guide_content = f.read()
        
        spine = {
            "project": "Mind-Q V4.1",
            "type": "logistics_data_pipeline",
            "generated_at": datetime.now().isoformat(),
            "phases": [],
            "flows": [],
            "kpis": self._extract_kpis(guide_content)
        }
        
        # Extract phases
        for phase_id in self.phase_sequence:
            phase_info = self._extract_phase_info(phase_id, guide_content)
            if phase_info:
                spine["phases"].append(phase_info)
        
        # Build flow edges
        spine["flows"] = self._build_phase_flows(spine["phases"])
        
        self._spine_data = spine
        return spine
    
    def _extract_kpis(self, guide_content: str) -> List[Dict[str, Any]]:
        """Extract KPIs mentioned in the guide with phase mappings."""
        kpis = [
            {
                "name": "RTO%", 
                "description": "Return to Origin percentage", 
                "category": "delivery",
                "impacted_by": ["01_ingestion", "07_readiness", "08_insights", "09_business_validation"]
            },
            {
                "name": "SLA", 
                "description": "Service Level Agreement compliance", 
                "category": "service",
                "impacted_by": ["01_ingestion", "07_readiness", "08_insights", "09_business_validation", "10_bi"]
            },
            {
                "name": "COD", 
                "description": "Cash on Delivery collection rate", 
                "category": "financial",
                "impacted_by": ["01_ingestion", "02_quality", "08_insights", "09_business_validation"]
            },
            {
                "name": "PSI", 
                "description": "Population Stability Index for data drift", 
                "category": "quality",
                "impacted_by": ["04_profile", "05_missing", "06_standardize", "07_readiness"]
            },
            {
                "name": "NZV", 
                "description": "Near Zero Variance for feature stability", 
                "category": "quality",
                "impacted_by": ["04_profile", "06_feature_eng", "07_readiness"]
            },
            {
                "name": "Delivery Success", 
                "description": "Successful delivery rate", 
                "category": "delivery",
                "impacted_by": ["01_ingestion", "08_insights", "09_business_validation", "12_routing"]
            },
            {
                "name": "Hub Efficiency", 
                "description": "Hub throughput and processing time", 
                "category": "operations",
                "impacted_by": ["08_insights", "12_routing"]
            },
            {
                "name": "Data Quality Score",
                "description": "Overall data quality and completeness",
                "category": "quality",
                "impacted_by": ["02_quality", "03_schema", "04_profile", "05_missing"]
            }
        ]
        return kpis
    
    def _extract_phase_info(self, phase_id: str, guide_content: str) -> Optional[Dict[str, Any]]:
        """Extract phase information from guide content."""
        # Normalize phase ID for searching
        search_patterns = [
            f"### Stage {phase_id.replace('_', ' ').replace('0', '').strip()}",
            f"### Stage {phase_id.split('_')[0]}",
            f"## Phase {phase_id}"
        ]
        
        phase_name = self._phase_id_to_name(phase_id)
        phase_dir = self.phases_path / phase_id
        
        return {
            "id": phase_id,
            "name": phase_name,
            "order": self.phase_sequence.index(phase_id) if phase_id in self.phase_sequence else 99,
            "exists": phase_dir.exists(),
            "group": self._get_phase_group(phase_id),
            "optional": self._is_optional_phase(phase_id)
        }
    
    def _phase_id_to_name(self, phase_id: str) -> str:
        """Convert phase ID to human-readable name."""
        name_map = {
            "01_ingestion": "Data Ingestion",
            "02_quality": "Quality Checks",
            "03_schema": "Schema Validation",
            "03_5_textops": "Text Operations",
            "04_profile": "Data Profiling",
            "05_missing": "Missing Value Repair",
            "06_standardize": "Standardization",
            "06_feature_eng": "Feature Engineering",
            "07_readiness": "Readiness Assessment",
            "07_5_feature_report": "Feature Reporting",
            "07_6_llm_summary": "LLM Summary",
            "07_7_business_correlations": "Business Correlations",
            "07_analytics": "Analytics (optional)",
            "07_timeseries": "Timeseries Analysis (optional)",
            "07_knime_bridge": "KNIME Bridge",
            "08_insights": "Insights Generation",
            "09_business_validation": "Business Validation",
            "09_5_causal": "Causal Inference (optional)",
            "10_bi": "BI Delivery",
            "11_ml_lab": "ML Lab",
            "12_routing": "Routing (optional)"
        }
        return name_map.get(phase_id, phase_id.replace('_', ' ').title())
    
    def _get_phase_group(self, phase_id: str) -> str:
        """Determine which group a phase belongs to."""
        if phase_id.startswith(('01', '02', '03', '04')):
            return "data_foundation"
        elif phase_id.startswith(('05', '06', '07')):
            return "advanced_analytics"
        elif phase_id.startswith('08'):
            return "ai_insights"
        elif phase_id.startswith(('09', '10')):
            return "business_intelligence"
        elif phase_id.startswith('11'):
            return "ml_lab"
        else:
            return "optional"
    
    def _is_optional_phase(self, phase_id: str) -> bool:
        """Check if a phase is optional in the pipeline."""
        optional_phases = [
            "03_5_textops",
            "07_analytics",
            "07_timeseries",
            "09_5_causal",
            "11_ml_lab",
            "12_routing"
        ]
        return phase_id in optional_phases
    
    def _build_phase_flows(self, phases: List[Dict]) -> List[Dict[str, str]]:
        """Build edges between phases based on sequence."""
        flows = []
        for i in range(len(phases) - 1):
            from_phase = phases[i]
            to_phase = phases[i + 1]
            
            # Skip flows from/to optional phases that don't exist
            if (from_phase.get("optional") and not from_phase.get("exists")) or \
               (to_phase.get("optional") and not to_phase.get("exists")):
                continue
            
            flows.append({
                "from": from_phase["id"],
                "to": to_phase["id"],
                "type": "sequential"
            })
        
        return flows
    
    def _build_default_spine(self) -> Dict[str, Any]:
        """Build a minimal spine when guide is not available."""
        return {
            "project": "Mind-Q V4.1",
            "type": "logistics_data_pipeline",
            "generated_at": datetime.now().isoformat(),
            "phases": [{"id": p, "name": self._phase_id_to_name(p), "order": i} 
                      for i, p in enumerate(self.phase_sequence)],
            "flows": [{"from": self.phase_sequence[i], "to": self.phase_sequence[i+1], "type": "sequential"} 
                     for i in range(len(self.phase_sequence)-1)],
            "kpis": []
        }
    
    def save_spine(self, output_path: Optional[str] = None) -> str:
        """
        Save the spine to a YAML file.
        
        Args:
            output_path: Optional custom output path. Defaults to docs/mindq_spine.yaml
            
        Returns:
            Path where the spine was saved
        """
        if self._spine_data is None:
            self.build_spine()
        
        if output_path is None:
            output_path = self.docs_path / "mindq_spine.yaml"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._spine_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        return str(output_path)
    
    def generate_phase_card(self, phase_id: str) -> Dict[str, Any]:
        """
        Generate a phase card for a specific phase.
        
        Args:
            phase_id: Phase identifier (e.g., "01_ingestion")
            
        Returns:
            Dictionary containing phase card data
        """
        phase_dir = self.phases_path / phase_id
        phase_name = self._phase_id_to_name(phase_id)
        
        # Read guide for this phase
        guide_section = self._extract_phase_section_from_guide(phase_id)
        
        # Detect main code files
        code_files = self._find_phase_code_files(phase_id)
        
        # Build phase card
        card = {
            "phase_id": phase_id,
            "name": phase_name,
            "goal": guide_section.get("goal", f"Execute {phase_name} stage"),
            "inputs": guide_section.get("inputs", []),
            "outputs": guide_section.get("outputs", []),
            "code_files": code_files[:6],  # Limit to 6 entries
            "kpis": guide_section.get("kpis", []),
            "upstream": self._get_upstream_phases(phase_id),
            "downstream": self._get_downstream_phases(phase_id),
            "group": self._get_phase_group(phase_id),
            "optional": self._is_optional_phase(phase_id),
            "business_impact": guide_section.get("business_impact", ""),
            "generated_at": datetime.now().isoformat()
        }
        
        return card
    
    def _extract_phase_section_from_guide(self, phase_id: str) -> Dict[str, Any]:
        """Extract phase-specific section from guide with real parsing."""
        if not self.guide_path.exists():
            return self._get_default_phase_data(phase_id)
        
        with open(self.guide_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Default values
        section_data = self._get_default_phase_data(phase_id)
        
        # Find the stage section in the guide
        stage_num = phase_id.split('_')[0]  # e.g., "01", "03"
        
        # Build pattern to find section - looking for "### Stage 01" or "### Stage 01:"
        pattern = rf'### Stage {stage_num}[:\s]([^\n]*)\n+(.*?)(?=\n###|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        
        if not match:
            # Try alternate pattern without colon
            pattern = rf'### Stage {stage_num}\s+(.*?)(?=\n###|\Z)'
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        
        if not match:
            return section_data
        
        section_content = match.group(0) if match.lastindex == 1 else match.group(2)
        
        # Extract Stage Definition (as goal)
        goal_match = re.search(
            r'#### Stage Definition\s+(.*?)(?=####|\Z)',
            section_content,
            re.DOTALL
        )
        if goal_match:
            goal_text = goal_match.group(1).strip()
            # Take first sentence
            sentences = re.split(r'\.\s+', goal_text)
            if sentences:
                section_data["goal"] = sentences[0].strip() + ('.' if not sentences[0].endswith('.') else '')
                if len(section_data["goal"]) > 250:
                    section_data["goal"] = section_data["goal"][:247] + "..."
        
        # Extract Inputs
        inputs_match = re.search(
            r'#### Inputs\s+(.*?)(?=####|\Z)',
            section_content,
            re.DOTALL
        )
        if inputs_match:
            inputs_text = inputs_match.group(1).strip()
            # Extract items that look like inputs
            input_items = []
            for line in inputs_text.split('\n'):
                line = line.strip()
                if line.startswith('-'):
                    # Extract after the dash
                    item = line.lstrip('- ').strip()
                    # If it has input["xxx"], extract the xxx part
                    input_match = re.search(r'`inputs?\["([^"]+)"\]`', item)
                    if input_match:
                        input_items.append(input_match.group(1))
                    elif ':' in item:
                        # Take description before colon
                        input_items.append(item.split(':')[0].strip('`"\''))
                    elif item and len(item) < 100:
                        input_items.append(item.split('.')[0])
            
            if input_items:
                section_data["inputs"] = input_items[:5]
        
        # Extract Outputs & Reports
        outputs_match = re.search(
            r'#### Outputs & Reports\s+(.*?)(?=####|\Z)',
            section_content,
            re.DOTALL
        )
        if outputs_match:
            outputs_text = outputs_match.group(1).strip()
            # Extract artifact file names
            artifacts = re.findall(r'[├└]──\s+(\S+)|[-*]\s+`?([a-zA-Z0-9_]+\.(?:parquet|json|yaml|jsonl))`?', outputs_text)
            output_files = [a for group in artifacts for a in group if a]
            if output_files:
                section_data["outputs"] = output_files[:8]
        
        # Extract Business Objective
        business_match = re.search(
            r'#### Business Objective\s+(.*?)(?=####|\Z)',
            section_content,
            re.DOTALL
        )
        if business_match:
            business_text = business_match.group(1).strip()
            # Take first 2-3 sentences
            sentences = re.split(r'\.\s+', business_text)
            business_summary = '. '.join(sentences[:2])
            if business_summary and not business_summary.endswith('.'):
                business_summary += '.'
            section_data["business_impact"] = business_summary[:350]
        
        # Extract KPIs mentioned in this section
        kpi_keywords = ['RTO', 'SLA', 'COD', 'PSI', 'NZV', 'delivery', 'quality', 'compliance', 'drift', 'variance']
        found_kpis = set()
        for kpi in kpi_keywords:
            if re.search(rf'\b{kpi}\b', section_content, re.IGNORECASE):
                found_kpis.add(kpi.upper() if len(kpi) <= 3 else kpi.title())
        section_data["kpis"] = sorted(list(found_kpis))[:5]
        
        return section_data
    
    def _get_default_phase_data(self, phase_id: str) -> Dict[str, Any]:
        """Get default phase data as fallback."""
        return {
            "goal": f"Execute {self._phase_id_to_name(phase_id)} pipeline stage",
            "inputs": ["Upstream phase outputs"],
            "outputs": ["Phase artifacts"],
            "kpis": [],
            "business_impact": "Contributes to data quality and pipeline reliability"
        }
    
    def _find_phase_code_files(self, phase_id: str) -> List[str]:
        """Find main code files for a phase with extended discovery."""
        code_files = []
        
        # 1. Standard phase directory
        phase_dir = self.phases_path / phase_id
        if phase_dir.exists():
            # Look for impl.py, run.py, or other Python files
            for pattern in ["impl.py", "run.py", "*.py"]:
                for file_path in phase_dir.glob(pattern):
                    if file_path.is_file() and not file_path.name.startswith('__'):
                        rel_path = file_path.relative_to(self.repo_path)
                        code_files.append(str(rel_path))
            
            # Look for config files
            for pattern in ["config.yaml", "config.json", "*.yaml", "*.json"]:
                for file_path in phase_dir.glob(pattern):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(self.repo_path)
                        code_files.append(str(rel_path))
        
        # 2. Extended paths - phase-specific contracts and services
        PHASE_EXTRA_PATHS = {
            "05_missing": ["contracts/impute/", "contracts/nzv/"],
            "06_standardize": ["contracts/nzv/"],
            "08_insights": ["contracts/analytics/", "backend/src/app/services/stage_08_insights/"],
            "09_business_validation": ["contracts/sla/", "contracts/payment/"],
        }
        
        if phase_id in PHASE_EXTRA_PATHS:
            for extra_path in PHASE_EXTRA_PATHS[phase_id]:
                extra_dir = self.repo_path / extra_path
                if extra_dir.exists():
                    for pattern in ["*.py", "*.yaml", "*.json"]:
                        for file_path in extra_dir.glob(pattern):
                            if file_path.is_file() and not file_path.name.startswith('__'):
                                rel_path = file_path.relative_to(self.repo_path)
                                if str(rel_path) not in code_files:
                                    code_files.append(str(rel_path))
        
        # 3. Generic heuristic: search backend/src/app/services/ for phase number
        phase_num = phase_id.split('_')[0]  # e.g., "08" from "08_insights"
        services_path = self.repo_path / "backend" / "src" / "app" / "services"
        if services_path.exists():
            for service_dir in services_path.iterdir():
                if service_dir.is_dir() and phase_num in service_dir.name:
                    for pattern in ["*.py", "*.yaml"]:
                        for file_path in service_dir.glob(pattern):
                            if file_path.is_file() and not file_path.name.startswith('__'):
                                rel_path = file_path.relative_to(self.repo_path)
                                if str(rel_path) not in code_files:
                                    code_files.append(str(rel_path))
        
        # 4. Search contracts/ for YAML files mentioned in phase impl
        contracts_path = self.repo_path / "contracts"
        if contracts_path.exists() and len(code_files) < 6:
            for yaml_file in contracts_path.rglob("*.yaml"):
                # Check if phase_id is mentioned in filename or content
                if phase_id in yaml_file.name or phase_num in yaml_file.name:
                    rel_path = yaml_file.relative_to(self.repo_path)
                    if str(rel_path) not in code_files:
                        code_files.append(str(rel_path))
        
        # Limit to 6 entries total and deduplicate
        seen = set()
        unique_files = []
        for f in code_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)
                if len(unique_files) >= 6:
                    break
        
        return unique_files
    
    def _get_upstream_phases(self, phase_id: str) -> List[str]:
        """Get upstream phases for a given phase."""
        try:
            idx = self.phase_sequence.index(phase_id)
            if idx > 0:
                return [self.phase_sequence[idx-1]]
        except ValueError:
            pass
        return []
    
    def _get_downstream_phases(self, phase_id: str) -> List[str]:
        """Get downstream phases for a given phase."""
        try:
            idx = self.phase_sequence.index(phase_id)
            if idx < len(self.phase_sequence) - 1:
                return [self.phase_sequence[idx+1]]
        except ValueError:
            pass
        return []
    
    def save_phase_card(self, phase_id: str, output_dir: Optional[str] = None) -> str:
        """
        Save a phase card to a markdown file.
        
        Args:
            phase_id: Phase identifier
            output_dir: Optional custom output directory. Defaults to docs/phases/
            
        Returns:
            Path where the card was saved
        """
        card = self.generate_phase_card(phase_id)
        
        if output_dir is None:
            output_dir = self.docs_path / "phases"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{phase_id}.md"
        
        # Generate markdown content
        md_content = self._card_to_markdown(card)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        return str(output_file)
    
    def _card_to_markdown(self, card: Dict[str, Any]) -> str:
        """Convert phase card to markdown format."""
        md = f"""# {card['name']} ({card['phase_id']})

**Group:** {card['group'].replace('_', ' ').title()}  
**Optional:** {'Yes' if card['optional'] else 'No'}

## Goal
{card['goal']}

## Business Impact
{card['business_impact']}

## Inputs
"""
        for inp in card['inputs']:
            md += f"- {inp}\n"
        
        md += "\n## Outputs\n"
        for out in card['outputs']:
            md += f"- {out}\n"
        
        md += "\n## Main Code Files\n"
        for code_file in card['code_files']:
            md += f"- `{code_file}`\n"
        
        if card['kpis']:
            md += "\n## KPIs\n"
            for kpi in card['kpis']:
                md += f"- {kpi}\n"
        
        md += "\n## Pipeline Position\n"
        if card['upstream']:
            md += f"**Upstream:** {', '.join(card['upstream'])}\n"
        if card['downstream']:
            md += f"**Downstream:** {', '.join(card['downstream'])}\n"
        
        md += f"\n---\n*Generated: {card['generated_at']}*\n"
        
        return md
    
    def generate_all_phase_cards(self, output_dir: Optional[str] = None) -> List[str]:
        """
        Generate phase cards for all phases in the pipeline.
        
        Args:
            output_dir: Optional custom output directory
            
        Returns:
            List of paths where cards were saved
        """
        saved_paths = []
        for phase_id in self.phase_sequence:
            phase_dir = self.phases_path / phase_id
            if phase_dir.exists() or not self._is_optional_phase(phase_id):
                try:
                    path = self.save_phase_card(phase_id, output_dir)
                    saved_paths.append(path)
                except Exception as e:
                    print(f"Warning: Could not generate card for {phase_id}: {e}")
        return saved_paths
    
    # Context generation methods for LLM agents
    
    def get_spine_context(self) -> str:
        """
        Get a compact spine context string for LLM agents.
        
        Returns:
            Formatted string describing the pipeline structure
        """
        if self._spine_data is None:
            self.build_spine()
        
        context = f"# Mind-Q Pipeline Structure\n\n"
        context += f"**Type:** {self._spine_data['type']}\n"
        context += f"**Phases:** {len(self._spine_data['phases'])}\n\n"
        
        context += "## Pipeline Flow\n"
        for phase in self._spine_data['phases']:
            optional_mark = " (optional)" if phase.get('optional') else ""
            context += f"{phase['order']+1}. **{phase['id']}** - {phase['name']}{optional_mark}\n"
        
        context += "\n## Key KPIs\n"
        for kpi in self._spine_data['kpis'][:5]:  # Top 5 KPIs
            context += f"- **{kpi['name']}**: {kpi['description']}\n"
        
        return context
    
    def get_phase_context(self, phase_ids: List[str]) -> str:
        """
        Get context for specific phases.
        
        Args:
            phase_ids: List of phase identifiers
            
        Returns:
            Formatted string with phase details
        """
        context = f"# Phase Details\n\n"
        
        for phase_id in phase_ids:
            card = self.generate_phase_card(phase_id)
            context += f"## {card['name']} ({phase_id})\n"
            context += f"**Goal:** {card['goal']}\n"
            context += f"**Impact:** {card['business_impact'][:150]}...\n"
            context += f"**Files:** {', '.join(card['code_files'][:3])}\n\n"
        
        return context
    
    def get_guardian_context_for_request(self, user_request: str) -> str:
        """
        Generate optimized Guardian context based on user request.
        
        Uses map_request_to_phases() as the single source of truth for
        mapping requests to relevant phases, eliminating duplicated logic.
        
        Args:
            user_request: User's request or query
            
        Returns:
            Tailored context string for the request
        """
        # Use unified phase mapping
        target_phases = self.map_request_to_phases(user_request)
        
        # Build KPI context if KPIs mentioned
        kpi_context = self._build_kpi_context_for_request(user_request.lower())
        
        # If no specific phases or KPIs detected, provide spine overview
        if not target_phases and not kpi_context:
            return self.get_spine_context()
        
        # Build context
        context = ""
        
        # Add KPI block if relevant
        if kpi_context:
            context += kpi_context + "\n\n"
        
        # Add phase details (limit to 3 phases for context size)
        if target_phases:
            context += self.get_phase_context(target_phases[:3])
        
        return context if context else self.get_spine_context()
    
    def _build_kpi_context_for_request(self, request_lower: str) -> str:
        """
        Build KPI context for a request.
        
        Reuses the same KPI detection logic as map_request_to_phases()
        for consistency.
        
        Args:
            request_lower: Lowercased user request
            
        Returns:
            Formatted KPI context string
        """
        if self._spine_data is None:
            self.build_spine()
        
        # Find mentioned KPIs using same logic as map_request_to_phases
        mentioned_kpis = []
        for kpi in self._spine_data['kpis']:
            kpi_name_lower = kpi['name'].lower()
            kpi_desc_words = kpi['description'].lower().split()[:5]
            
            if kpi_name_lower in request_lower or any(word in request_lower for word in kpi_desc_words):
                mentioned_kpis.append(kpi)
        
        if not mentioned_kpis:
            return ""
        
        # Build context
        context = "# Relevant KPIs\n\n"
        for kpi in mentioned_kpis[:3]:  # Limit to 3 KPIs for context size
            context += f"**{kpi['name']}** - {kpi['description']}\n"
            if 'impacted_by' in kpi and kpi['impacted_by']:
                phases_str = ', '.join(kpi['impacted_by'][:4])
                context += f"  *Affected by phases:* {phases_str}\n"
            context += "\n"
        
        return context.strip()
    
    def get_kpi_phase_mapping(self) -> Dict[str, List[str]]:
        """
        Get mapping of KPIs to phases that impact them.
        
        Returns:
            Dictionary mapping KPI names to list of phase IDs
        """
        if self._spine_data is None:
            self.build_spine()
        
        mapping = {}
        for kpi in self._spine_data['kpis']:
            if 'impacted_by' in kpi:
                mapping[kpi['name']] = kpi['impacted_by']
        
        return mapping
    
    def get_phase_kpi_impact(self, phase_id: str) -> List[Dict[str, str]]:
        """
        Get list of KPIs impacted by a specific phase.
        
        Args:
            phase_id: Phase identifier
            
        Returns:
            List of KPI dictionaries that this phase impacts
        """
        if self._spine_data is None:
            self.build_spine()
        
        impacted_kpis = []
        for kpi in self._spine_data['kpis']:
            if 'impacted_by' in kpi and phase_id in kpi['impacted_by']:
                impacted_kpis.append({
                    "name": kpi['name'],
                    "description": kpi['description'],
                    "category": kpi['category']
                })
        
        return impacted_kpis
    
    def map_request_to_phases(self, user_request: str) -> List[str]:
        """
        Map a user request to relevant phases in the pipeline.
        
        Analyzes the request for:
        - KPI mentions → adds phases from impacted_by
        - Phase ID/name mentions → adds those phases
        
        Args:
            user_request: User's request or query
            
        Returns:
            Deduplicated list of phase IDs (max 4 phases)
        """
        if self._spine_data is None:
            self.build_spine()
        
        request_lower = user_request.lower()
        relevant_phases = []
        
        # Check for KPI mentions
        for kpi in self._spine_data['kpis']:
            kpi_name_lower = kpi['name'].lower()
            kpi_desc_words = kpi['description'].lower().split()[:5]
            
            if kpi_name_lower in request_lower or any(word in request_lower for word in kpi_desc_words):
                # Add phases that impact this KPI
                if 'impacted_by' in kpi:
                    relevant_phases.extend(kpi['impacted_by'])
        
        # Check for direct phase mentions
        for phase_id in self.phase_sequence:
            phase_name = self._phase_id_to_name(phase_id).lower()
            phase_num = phase_id.split('_')[0]
            
            if (phase_id in request_lower or 
                phase_num in request_lower or
                any(word in request_lower for word in phase_name.split())):
                relevant_phases.append(phase_id)
        
        # Deduplicate while preserving order
        seen = set()
        unique_phases = []
        for phase in relevant_phases:
            if phase not in seen:
                seen.add(phase)
                unique_phases.append(phase)
                if len(unique_phases) >= 4:
                    break
        
        return unique_phases
    
    def build_change_request(self, user_request: str) -> Dict[str, Any]:
        """
        Build a structured change request from a user query.
        
        Args:
            user_request: User's request description
            
        Returns:
            Change request dictionary with metadata
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        return {
            "id": f"mqr_{timestamp}",
            "goal": user_request[:100],  # Truncate long requests
            "full_request": user_request,
            "target_phases": self.map_request_to_phases(user_request),
            "non_goals": [],  # User can populate this
            "allowed_operations": ["refactor", "bugfix"],
            "created_at": datetime.now().isoformat(),
            "status": "planned"
        }
    
    def plan_change(self, change_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a change plan from a change request.
        
        Identifies:
        - Files to edit (from target phases)
        - Affected KPIs
        - Potential risks
        
        Args:
            change_request: Change request dictionary from build_change_request
            
        Returns:
            Change plan dictionary
        """
        target_phases = change_request.get("target_phases", [])
        
        # Collect files from all target phases
        files_to_edit = []
        for phase_id in target_phases:
            card = self.generate_phase_card(phase_id)
            files_to_edit.extend(card.get("code_files", []))
        
        # Deduplicate files
        files_to_edit = list(set(files_to_edit))
        
        # Collect affected KPIs
        affected_kpis = []
        for phase_id in target_phases:
            phase_kpis = self.get_phase_kpi_impact(phase_id)
            for kpi in phase_kpis:
                if kpi not in affected_kpis:
                    affected_kpis.append(kpi)
        
        # Identify potential risks
        potential_risks = []
        if len(target_phases) > 2:
            potential_risks.append("Multiple phases affected - ensure consistency across changes")
        if any(kpi['category'] == 'business_critical' for kpi in affected_kpis):
            potential_risks.append("Business-critical KPIs affected - extra testing recommended")
        
        plan = {
            "change_request_id": change_request["id"],
            "files_to_edit": files_to_edit,
            "files_to_avoid": [],  # Could be populated with locked files
            "affected_kpis": [kpi['name'] for kpi in affected_kpis],
            "affected_kpi_details": affected_kpis,
            "potential_risks": potential_risks,
            "recommended_tests": [f"Test {phase_id} phase" for phase_id in target_phases]
        }
        
        # Soft guidance: Create/update checklist (non-blocking)
        try:
            self.update_checklist(change_request, plan)
        except Exception:
            pass  # Soft: don't fail if checklist update fails
        
        return plan
    
    def record_change(self, change_request: Dict[str, Any], plan: Dict[str, Any], 
                     files_changed: Optional[List[str]] = None) -> str:
        """
        Record a change in the Guardian change log.
        
        Appends record to .guardian/mindq_changes.json for audit trail.
        
        Args:
            change_request: Change request dictionary
            plan: Change plan dictionary
            files_changed: Optional list of actually changed files
            
        Returns:
            Path to the change log file
        """
        guardian_dir = self.repo_path / ".guardian"
        guardian_dir.mkdir(exist_ok=True)
        
        change_log_path = guardian_dir / "mindq_changes.json"
        
        # Load existing changes
        if change_log_path.exists():
            with open(change_log_path, 'r', encoding='utf-8') as f:
                changes = json.load(f)
        else:
            changes = []
        
        # Create record
        record = {
            "id": change_request["id"],
            "timestamp": datetime.now().isoformat(),
            "goal": change_request["goal"],
            "target_phases": change_request["target_phases"],
            "files_planned": plan["files_to_edit"],
            "files_changed": files_changed if files_changed else [],
            "affected_kpis": plan["affected_kpis"],
            "status": "completed" if files_changed else "planned"
        }
        
        changes.append(record)
        
        # Save updated log
        with open(change_log_path, 'w', encoding='utf-8') as f:
            json.dump(changes, f, indent=2, ensure_ascii=False)
        
        # Soft guidance: Update checklist to mark as completed (non-blocking)
        if files_changed:
            try:
                # Mark all items as done when change is completed
                checklist = self.generate_checklist_for_change(change_request, plan)
                items_done = list(range(len(checklist)))  # Mark all as done
                self.update_checklist(change_request, plan, items_done)
            except Exception:
                pass  # Soft: don't fail if checklist update fails
        
        return str(change_log_path)
    
    def build_llm_change_context(self, user_request: str) -> str:
        """
        Build a compact, structured markdown context for an LLM agent
        planning a change.
        
        This is the primary method for providing change guidance to AI agents.
        Returns a focused, actionable context that includes:
        - Target phases
        - Files to edit
        - KPIs that will be affected
        - Potential risks
        
        Args:
            user_request: User's change request description
            
        Returns:
            Structured markdown context for the LLM agent
        """
        # Build change request and plan
        change_req = self.build_change_request(user_request)
        plan = self.plan_change(change_req)
        
        # Build compact context
        context = f"""# Mind-Q Change Guidance

## Request
{user_request}

## Target Phases
"""
        for phase_id in change_req['target_phases']:
            phase_name = self._phase_id_to_name(phase_id)
            context += f"- **{phase_id}**: {phase_name}\n"
        
        context += f"\n## Files to Edit\n"
        for file_path in plan['files_to_edit'][:6]:  # Limit to 6 files
            context += f"- `{file_path}`\n"
        
        if plan['affected_kpis']:
            context += f"\n## Affected KPIs\n"
            for kpi_name in plan['affected_kpis']:
                context += f"- {kpi_name}\n"
        
        if plan['potential_risks']:
            context += f"\n## ⚠️ Risks & Considerations\n"
            for risk in plan['potential_risks']:
                context += f"- {risk}\n"
        
        # Add phase details for first 2 target phases
        if change_req['target_phases']:
            context += f"\n## Phase Details\n\n"
            context += self.get_phase_context(change_req['target_phases'][:2])
        
        # Add recommendation
        context += f"""\n\n## 📋 Recommended Workflow

1. **Review** the files listed above in target phases
2. **Check** for dependencies between phases if multiple affected
3. **Test** changes in each phase independently
4. **Verify** that affected KPIs are tracked after changes
5. **Record** the change using `record_change()` for audit trail
"""
        
        return context
    
    def get_mindq_context_for_mdc(self) -> str:
        """
        Generate Mind-Q specific context for inclusion in Guardian MDC files.
        
        This method is called by GuardianEnhanced to add Mind-Q pipeline
        context to IDE rule files (.cursor/rules, .windsurf/rules, etc.)
        
        Uses scan_guardian_status() for compact, status-aware MDC integration.
        
        Returns:
            Formatted Mind-Q context section for MDC (compact ~20 lines)
        """
        if self._spine_data is None:
            self.build_spine()
        
        # Get structured status
        status = self.scan_guardian_status()
        
        # Build compact Mind-Q context with status-aware messaging
        context = """
## 🔧 MIND-Q PIPELINE STATUS

> This is a Mind-Q V4.1 logistics data pipeline project (21 phases, 8 KPIs tracked).
"""
        
        # Status-specific messaging
        if status.status == 'NO_CHANGES':
            context += f"""
**Status**: ✅ NO_CHANGES (ready for new changes)

**Pipeline**: 21 phases (01_ingestion → 12_routing)
**KPIs Tracked**: RTO%, SLA, COD, PSI, NZV, Delivery Success, Hub Efficiency, Data Quality

✅ **Ready**: No uncommitted changes detected.

**📋 Next Steps**:
1. Open and review `.guardian/mindq_status.md` for any previous checklist
2. Plan new changes with: `python -m src.guardian_mindq . --plan-change "Your change description"`
"""
        
        elif status.status == 'NO_PLAN_FOR_CHANGES':
            context += f"""
**Status**: ⚠️  NO_PLAN_FOR_CHANGES ({status.extra_files_count} files changed without plan)

**Changed Files**: {status.extra_files_count} file(s) modified (0 planned, {status.extra_files_count} extra)

⚠️  **Warning**: You have file changes without a documented change plan.
Large structural changes without a plan can lead to issues.

**📋 Action Required**:
1. Open and review `.guardian/mindq_status.md` for current status
2. Consider creating a change plan with: `python -m src.guardian_mindq . --plan-change "Your change description"`
3. Review checklist before making large structural changes
4. Avoid touching multiple phases without understanding dependencies
"""
        
        elif status.status == 'PLAN_VIOLATIONS':
            phases_str = ', '.join(status.target_phases) if status.target_phases else 'None'
            context += f"""
**Status**: 🔔 PLAN_VIOLATIONS

**Last Change**: "{status.last_goal}"
**Target Phases**: {phases_str}
**Files**: {status.planned_files_count} changed ({status.planned_files_count} planned, {status.extra_files_count} extra) ⚠️

🔔 **Alert**: Extra files detected outside the documented plan.

**📋 Important**:
1. Open and review `.guardian/mindq_status.md` to see which files are extra
2. Review if extra files are related to your change goal
3. Consider updating the plan if scope changed
4. Mark checklist items complete as you verify them
"""
        
        else:  # ON_TRACK
            phases_str = ', '.join(status.target_phases) if status.target_phases else 'None'
            context += f"""
**Status**: ✅ ON_TRACK

**Last Change**: "{status.last_goal}"
**Target Phases**: {phases_str}
**Files**: {status.planned_files_count} changed ({status.planned_files_count} planned, 0 extra) ✅

✅ **Good Progress**: Following documented plan

**📋 Next Steps**:
1. Open and review `.guardian/mindq_status.md` for checklist progress
2. Continue with planned changes
3. Mark checklist items complete as you finish them
4. Record completion with: `record_change()` when done
"""
        
        # Add usage instructions (compact)
        context += """
### 🤖 For AI Agents

**Phase-Aware Commands:**
```bash
# Get context for your task
python -m src.guardian_mindq . --context "your task"

# Plan a change (creates checklist)
python -m src.guardian_mindq . --plan-change "your change"

# Check cleanup needed
python -m src.guardian_mindq . --cleanup

# Refresh docs after code changes
python -m src.guardian_mindq . --refresh-docs
```

**Important**: Always review `.guardian/mindq_status.md` before large changes.
Cleanup reports are in `.guardian/mindq_cleanup.md` (NOT shown here to keep MDC compact).
"""
        
        return context
    
    # ================================================================
    # SOFT GUARDIAN LAYER - Status Tracking & Checklist Management
    # ================================================================
    
    def _load_last_change_record(self) -> Optional[Dict]:
        """
        Load the last change record from .guardian/mindq_changes.json, if any.
        
        Returns:
            Last change dict or None if no records exist
        """
        guardian_dir = self.repo_path / ".guardian"
        changes_file = guardian_dir / "mindq_changes.json"
        
        if not changes_file.exists():
            return None
        
        try:
            with open(changes_file, 'r', encoding='utf-8') as f:
                changes = json.load(f)
                if isinstance(changes, list) and len(changes) > 0:
                    return changes[-1]
        except (json.JSONDecodeError, IOError):
            pass
        
        return None
    
    def get_changed_files(self) -> List[str]:
        """
        Return a list of files changed in git compared to HEAD.
        
        Soft helper: if git is not available or errors, returns empty list.
        
        Returns:
            List of changed file paths
        """
        import subprocess
        
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                return files
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass
        
        return []
    
    def get_status_summary(self) -> str:
        """
        Get a compact status summary for inclusion in MDC.
        
        This provides a brief overview of the current change status
        without overwhelming the MDC file.
        
        Returns:
            Compact (<500 chars) status summary
        """
        last_change = self._load_last_change_record()
        changed_files = self.get_changed_files()
        
        if not last_change and not changed_files:
            return "📊 **Status**: Clean workspace - ready for new changes"
        
        summary = "📊 **Mind-Q Status**\n\n"
        
        if last_change:
            goal = last_change.get('goal', 'Unknown')[:50]
            phases = ', '.join(last_change.get('target_phases', [])[:3])
            summary += f"**Last Change**: {goal}\n"
            summary += f"**Target Phases**: {phases}\n"
        
        if changed_files:
            file_count = len(changed_files)
            summary += f"**Changed Files**: {file_count} file(s) modified\n"
            summary += f"\n💡 *Tip: Review checklist in `.guardian/mindq_status.md`*\n"
        
        return summary
    
    def generate_checklist_for_change(self, change_request: Dict, plan: Dict) -> List[str]:
        """
        Generate a checklist for a change request.
        
        Args:
            change_request: The change request dict
            plan: The change plan dict
            
        Returns:
            List of checklist items
        """
        checklist = []
        
        # Basic checklist items
        checklist.append("[ ] Review change goal and target phases")
        
        # Phase-specific items
        for phase_id in change_request.get('target_phases', []):
            phase_name = self._phase_id_to_name(phase_id)
            checklist.append(f"[ ] Review and test changes in {phase_name} ({phase_id})")
        
        # File-specific items
        if plan.get('files_to_edit'):
            checklist.append(f"[ ] Edit and test {len(plan['files_to_edit'])} identified files")
        
        # KPI items
        if plan.get('affected_kpis'):
            checklist.append(f"[ ] Verify {len(plan['affected_kpis'])} affected KPIs are tracked")
        
        # Risk items
        if plan.get('potential_risks'):
            checklist.append("[ ] Address identified risks and considerations")
        
        # Final items
        checklist.append("[ ] Run tests for all affected phases")
        checklist.append("[ ] Update documentation if needed")
        checklist.append("[ ] Record change completion with `record_change()`")
        
        return checklist
    
    def update_checklist(self, change_request: Dict, plan: Dict, items_done: Optional[List[int]] = None) -> str:
        """
        Update or create checklist in .guardian/mindq_status.md.
        
        Args:
            change_request: The change request dict
            plan: The change plan dict
            items_done: List of 0-based indices of completed items (optional)
            
        Returns:
            Path to the status file
        """
        guardian_dir = self.repo_path / ".guardian"
        guardian_dir.mkdir(exist_ok=True)
        
        status_file = guardian_dir / "mindq_status.md"
        
        # Generate checklist
        checklist = self.generate_checklist_for_change(change_request, plan)
        
        # Mark items as done if specified
        if items_done:
            for idx in items_done:
                if 0 <= idx < len(checklist):
                    checklist[idx] = checklist[idx].replace("[ ]", "[x]", 1)
        
        # Build status document
        content = f"""# Mind-Q Change Status

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Current Change

**ID**: `{change_request.get('id', 'N/A')}`  
**Goal**: {change_request.get('goal', 'N/A')}  
**Target Phases**: {', '.join(change_request.get('target_phases', []))}  
**Created**: {change_request.get('created_at', 'N/A')}

## Checklist

"""
        for item in checklist:
            content += f"{item}\n"
        
        content += f"""

## Files to Edit ({len(plan.get('files_to_edit', []))})

"""
        for file_path in plan.get('files_to_edit', []):
            content += f"- `{file_path}`\n"
        
        if plan.get('affected_kpis'):
            content += f"\n## Affected KPIs ({len(plan['affected_kpis'])})\n\n"
            for kpi_name in plan['affected_kpis']:
                content += f"- {kpi_name}\n"
        
        if plan.get('potential_risks'):
            content += f"\n## ⚠️ Risks & Considerations\n\n"
            for risk in plan['potential_risks']:
                content += f"- {risk}\n"
        
        content += """

---

"""
        content += "💡 **Tip**: Update this checklist as you complete items. You can mark items as done by changing `[ ]` to `[x]`.\n\n"
        content += "📝 **Record**: When done, call `record_change()` to log this change in the audit trail.\n"
        
        # Write to file
        with open(status_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(status_file)
    
    def scan_guardian_status(self) -> MindQStatus:
        """
        Scan current Mind-Q Guardian status for compact MDC integration.
        
        Returns structured status with:
        - status code (NO_CHANGES, NO_PLAN_FOR_CHANGES, PLAN_VIOLATIONS, ON_TRACK)
        - last change goal (truncated to 100 chars)
        - target phases
        - planned vs extra files count
        """
        last_change = self._load_last_change_record()
        changed_files = self.get_changed_files()
        
        # Determine status
        if not changed_files:
            # No changes in git
            status_code = 'NO_CHANGES'
            last_goal = ''
            target_phases = []
            planned_count = 0
            extra_count = 0
        elif not last_change:
            # Changes exist but no documented plan
            status_code = 'NO_PLAN_FOR_CHANGES'
            last_goal = ''
            target_phases = []
            planned_count = 0
            extra_count = len(changed_files)
        else:
            # Have a documented change
            last_goal = last_change.get('goal', '')[:100]  # Truncate to 100 chars
            target_phases = last_change.get('target_phases', [])
            
            # Check if files match plan
            plan = last_change.get('plan', {})
            planned_files = set(plan.get('files_to_edit', []))
            changed_set = set(changed_files)
            
            # Count planned vs extra
            planned_count = len(changed_set & planned_files)
            extra_count = len(changed_set - planned_files)
            
            if extra_count > 0:
                status_code = 'PLAN_VIOLATIONS'
            else:
                status_code = 'ON_TRACK'
        
        return MindQStatus(
            status=status_code,
            last_goal=last_goal,
            target_phases=target_phases,
            planned_files_count=planned_count,
            extra_files_count=extra_count
        )
    
    def run_cleanup(self) -> Dict[str, Any]:
        """
        Run cleanup analysis on Mind-Q project (non-blocking).
        
        Identifies:
        - Unused phase directories
        - Outdated phase cards (older than implementation)
        - Missing phase cards
        - Stale contracts
        
        Returns cleanup report dict and saves to .guardian/mindq_cleanup.md
        Does NOT inject anything into MDC - agents should review the file.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "unused_phases": [],
            "outdated_cards": [],
            "missing_cards": [],
            "stale_contracts": [],
            "recommendations": []
        }
        
        try:
            # Check for unused phase directories
            phases_dir = self.repo_path / "phases"
            if phases_dir.exists():
                for phase_dir in phases_dir.iterdir():
                    if phase_dir.is_dir() and phase_dir.name.startswith(('0', '1')):
                        phase_id = phase_dir.name
                        # Check if phase is in spine
                        if phase_id not in [p['id'] for p in self._spine_data.get('phases', [])]:
                            report["unused_phases"].append(phase_id)
            
            # Check for outdated/missing phase cards
            docs_phases = self.repo_path / "docs" / "phases"
            for phase in self._spine_data.get('phases', []):
                phase_id = phase['id']
                card_path = docs_phases / f"{phase_id}.md"
                impl_path = self.repo_path / "phases" / phase_id / "impl.py"
                
                if not card_path.exists():
                    report["missing_cards"].append(phase_id)
                elif impl_path.exists():
                    # Check if card is older than implementation
                    try:
                        card_mtime = card_path.stat().st_mtime
                        impl_mtime = impl_path.stat().st_mtime
                        if card_mtime < impl_mtime:
                            report["outdated_cards"].append(phase_id)
                    except:
                        pass
            
            # Generate recommendations
            if report["unused_phases"]:
                report["recommendations"].append(
                    f"Consider removing or documenting {len(report['unused_phases'])} unused phase directories"
                )
            if report["outdated_cards"]:
                report["recommendations"].append(
                    f"Refresh {len(report['outdated_cards'])} outdated phase cards with: python -m src.guardian_mindq . --refresh-docs"
                )
            if report["missing_cards"]:
                report["recommendations"].append(
                    f"Generate {len(report['missing_cards'])} missing phase cards"
                )
            
            # Save report to .guardian/mindq_cleanup.md
            guardian_dir = self.repo_path / ".guardian"
            guardian_dir.mkdir(exist_ok=True)
            
            cleanup_file = guardian_dir / "mindq_cleanup.md"
            content = f"""# 🧹 Mind-Q Cleanup Report

**Generated**: {report['timestamp']}

## Summary

- **Unused Phases**: {len(report['unused_phases'])}
- **Outdated Cards**: {len(report['outdated_cards'])}
- **Missing Cards**: {len(report['missing_cards'])}

"""
            
            if report['unused_phases']:
                content += "## 🗑️ Unused Phase Directories\n\n"
                for phase_id in report['unused_phases']:
                    content += f"- `phases/{phase_id}/` - Not in current pipeline spine\n"
                content += "\n"
            
            if report['outdated_cards']:
                content += "## 📅 Outdated Phase Cards\n\n"
                for phase_id in report['outdated_cards']:
                    content += f"- `{phase_id}` - Implementation newer than documentation\n"
                content += "\n"
            
            if report['missing_cards']:
                content += "## ❌ Missing Phase Cards\n\n"
                for phase_id in report['missing_cards']:
                    content += f"- `{phase_id}` - No documentation card found\n"
                content += "\n"
            
            if report['recommendations']:
                content += "## 💡 Recommendations\n\n"
                for rec in report['recommendations']:
                    content += f"- {rec}\n"
                content += "\n"
            
            content += "---\n\n"
            content += "💡 **Note**: This is an informational report. No automatic cleanup is performed.\n"
            content += "Review the findings and take action as appropriate for your project.\n\n"
            content += "🔧 **Actions**:\n"
            content += "- Refresh outdated docs: `python -m src.guardian_mindq . --refresh-docs`\n"
            content += "- Clean unused phases manually after verification\n"
            
            with open(cleanup_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            report["cleanup_file"] = str(cleanup_file)
            
        except Exception as e:
            report["error"] = str(e)
        
        return report
    
    def _scan_python_file_for_issues(self, file_path: Path, cleanup_id_counter: int) -> List[CleanupItem]:
        """
        Deep scan a single Python file for refactoring opportunities using AST.
        
        Args:
            file_path: Path to Python file
            cleanup_id_counter: Starting ID counter for cleanup items
            
        Returns:
            List of CleanupItem findings
        """
        items = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
                tree = ast.parse(source, filename=str(file_path))
            
            rel_path = str(file_path.relative_to(self.repo_path))
            
            # Track imports, definitions, and usages
            imported_names = set()
            defined_symbols = set()
            used_symbols = set()
            function_sizes = {}
            
            # Walk the AST
            for node in ast.walk(tree):
                # Track imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
                
                # Track function definitions and sizes
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined_symbols.add(node.name)
                    # Count lines (rough estimate)
                    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                        size = node.end_lineno - node.lineno
                        function_sizes[node.name] = (node.lineno, size)
                
                # Track class definitions
                elif isinstance(node, ast.ClassDef):
                    defined_symbols.add(node.name)
                
                # Track name usages
                elif isinstance(node, ast.Name):
                    used_symbols.add(node.id)
            
            # Detect unused imports
            unused_imports = imported_names - used_symbols
            for unused in unused_imports:
                items.append(CleanupItem(
                    id=f"CLEANUP-{cleanup_id_counter:03d}",
                    kind="unused_import",
                    file=rel_path,
                    symbol=unused,
                    why_suspected=f"Import '{unused}' is not used in the file",
                    confidence=0.85,
                    related_phase=self._detect_phase_from_path(file_path),
                    suggested_action=f"remove_unused_import",
                    line_number=None
                ))
                cleanup_id_counter += 1
            
            # Detect oversized functions
            for func_name, (lineno, size) in function_sizes.items():
                if size > 100:
                    items.append(CleanupItem(
                        id=f"CLEANUP-{cleanup_id_counter:03d}",
                        kind="oversized_function",
                        file=rel_path,
                        symbol=func_name,
                        why_suspected=f"Function has {size} lines (threshold: 100)",
                        confidence=0.9,
                        related_phase=self._detect_phase_from_path(file_path),
                        suggested_action="consider_splitting_function",
                        line_number=lineno,
                        details=f"Large function may be hard to maintain and test"
                    ))
                    cleanup_id_counter += 1
            
            # Detect oversized files
            line_count = len(source.split('\n'))
            if line_count > 500:
                items.append(CleanupItem(
                    id=f"CLEANUP-{cleanup_id_counter:03d}",
                    kind="oversized_file",
                    file=rel_path,
                    symbol=None,
                    why_suspected=f"File has {line_count} lines (threshold: 500)",
                    confidence=0.8,
                    related_phase=self._detect_phase_from_path(file_path),
                    suggested_action="consider_splitting_module",
                    line_number=None,
                    details=f"Large file may benefit from being split into smaller modules"
                ))
                cleanup_id_counter += 1
                
        except Exception as e:
            # Silently skip files with parse errors
            pass
        
        return items
    
    def _detect_phase_from_path(self, file_path: Path) -> Optional[str]:
        """Detect which phase a file belongs to based on its path."""
        try:
            rel_path = str(file_path.relative_to(self.repo_path))
            # Check if path contains a phase ID
            for phase_id in self.phase_sequence:
                if phase_id in rel_path:
                    return phase_id
            return None
        except:
            return None
    
    def _find_duplicate_functions(self, cleanup_items: List[CleanupItem], cleanup_id_counter: int) -> List[CleanupItem]:
        """
        Detect potential duplicate functions across the codebase.
        Uses a simple heuristic: functions with same name in different files.
        
        Args:
            cleanup_items: Existing cleanup items to add to
            cleanup_id_counter: Starting ID counter
            
        Returns:
            List of new duplicate findings
        """
        duplicates = []
        function_locations = {}
        
        # Scan all Python files in phases/
        phases_dir = self.repo_path / "phases"
        if not phases_dir.exists():
            return duplicates
        
        for py_file in phases_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read(), filename=str(py_file))
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        func_name = node.name
                        if func_name not in function_locations:
                            function_locations[func_name] = []
                        function_locations[func_name].append(
                            (py_file, node.lineno if hasattr(node, 'lineno') else None)
                        )
            except:
                pass
        
        # Find functions that appear in multiple files
        for func_name, locations in function_locations.items():
            if len(locations) > 1 and not func_name.startswith('_'):
                # Skip private functions and common names
                if func_name in ('main', 'run', 'execute', 'process'):
                    continue
                
                files_str = ", ".join([str(loc[0].relative_to(self.repo_path)) for loc in locations[:3]])
                duplicates.append(CleanupItem(
                    id=f"CLEANUP-{cleanup_id_counter:03d}",
                    kind="duplicate_function",
                    file=str(locations[0][0].relative_to(self.repo_path)),
                    symbol=func_name,
                    why_suspected=f"Function '{func_name}' appears in {len(locations)} files",
                    confidence=0.6,
                    related_phase=None,
                    suggested_action="review_for_consolidation",
                    line_number=locations[0][1],
                    details=f"Found in: {files_str}"
                ))
                cleanup_id_counter += 1
        
        return duplicates
    
    def run_deep_cleanup(self) -> Dict[str, Any]:
        """
        Run deep code-aware cleanup analysis on Mind-Q project.
        
        This is an upgraded version of run_cleanup() that performs AST-based
        code analysis to detect:
        - Unused imports
        - Unused symbols (functions, classes)
        - Orphan modules
        - Duplicate functions across files
        - Oversized files (>500 lines)
        - Oversized functions (>100 lines)
        - Outdated phase documentation
        - Missing phase documentation
        
        Returns comprehensive cleanup report and saves to:
        - .guardian/mindq_cleanup.md (markdown report)
        - .guardian/mindq_cleanup.json (structured data)
        
        Does NOT modify any code - purely informational "Refactor Radar".
        Does NOT inject anything into MDC.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "scan_type": "deep_code_aware",
            "findings": [],
            "summary": {
                "total_items": 0,
                "by_kind": {},
                "by_confidence": {"high": 0, "medium": 0, "low": 0},
                "by_phase": {}
            },
            "recommendations": []
        }
        
        cleanup_id_counter = 1
        
        try:
            # Part 1: Scan all Python files in phases/ for code issues
            phases_dir = self.repo_path / "phases"
            if phases_dir.exists():
                for py_file in phases_dir.rglob("*.py"):
                    if py_file.name != "__init__.py":
                        items = self._scan_python_file_for_issues(py_file, cleanup_id_counter)
                        report["findings"].extend(items)
                        cleanup_id_counter += len(items)
            
            # Part 2: Find duplicate functions
            duplicates = self._find_duplicate_functions(report["findings"], cleanup_id_counter)
            report["findings"].extend(duplicates)
            cleanup_id_counter += len(duplicates)
            
            # Part 3: Documentation issues (from original run_cleanup)
            # Load spine if not already loaded
            if not self._spine_data:
                self.build_spine()
            
            docs_phases = self.repo_path / "docs" / "phases"
            for phase in self._spine_data.get('phases', []):
                phase_id = phase['id']
                card_path = docs_phases / f"{phase_id}.md"
                impl_path = self.repo_path / "phases" / phase_id / "impl.py"
                
                if not card_path.exists():
                    report["findings"].append(CleanupItem(
                        id=f"CLEANUP-{cleanup_id_counter:03d}",
                        kind="missing_phase_doc",
                        file=f"docs/phases/{phase_id}.md",
                        symbol=None,
                        why_suspected=f"Phase {phase_id} has no documentation card",
                        confidence=1.0,
                        related_phase=phase_id,
                        suggested_action="generate_phase_card",
                        line_number=None
                    ))
                    cleanup_id_counter += 1
                elif impl_path.exists():
                    try:
                        card_mtime = card_path.stat().st_mtime
                        impl_mtime = impl_path.stat().st_mtime
                        if card_mtime < impl_mtime:
                            report["findings"].append(CleanupItem(
                                id=f"CLEANUP-{cleanup_id_counter:03d}",
                                kind="outdated_phase_doc",
                                file=f"docs/phases/{phase_id}.md",
                                symbol=None,
                                why_suspected="Documentation older than implementation",
                                confidence=0.9,
                                related_phase=phase_id,
                                suggested_action="refresh_phase_card",
                                line_number=None
                            ))
                            cleanup_id_counter += 1
                    except:
                        pass
            
            # Build summary
            report["summary"]["total_items"] = len(report["findings"])
            
            for item in report["findings"]:
                # Count by kind
                report["summary"]["by_kind"][item.kind] = report["summary"]["by_kind"].get(item.kind, 0) + 1
                
                # Count by confidence
                if item.confidence >= 0.8:
                    report["summary"]["by_confidence"]["high"] += 1
                elif item.confidence >= 0.6:
                    report["summary"]["by_confidence"]["medium"] += 1
                else:
                    report["summary"]["by_confidence"]["low"] += 1
                
                # Count by phase
                if item.related_phase:
                    report["summary"]["by_phase"][item.related_phase] = report["summary"]["by_phase"].get(item.related_phase, 0) + 1
            
            # Generate recommendations
            if report["summary"]["by_kind"].get("unused_import", 0) > 0:
                report["recommendations"].append(
                    f"Consider removing {report['summary']['by_kind']['unused_import']} unused imports"
                )
            if report["summary"]["by_kind"].get("oversized_function", 0) > 0:
                report["recommendations"].append(
                    f"Review {report['summary']['by_kind']['oversized_function']} oversized functions for potential splitting"
                )
            if report["summary"]["by_kind"].get("oversized_file", 0) > 0:
                report["recommendations"].append(
                    f"Consider refactoring {report['summary']['by_kind']['oversized_file']} large files"
                )
            if report["summary"]["by_kind"].get("duplicate_function", 0) > 0:
                report["recommendations"].append(
                    f"Review {report['summary']['by_kind']['duplicate_function']} potential duplicate functions"
                )
            if report["summary"]["by_kind"].get("outdated_phase_doc", 0) > 0:
                report["recommendations"].append(
                    f"Refresh {report['summary']['by_kind']['outdated_phase_doc']} outdated phase docs with: python -m src.guardian_mindq . --refresh-docs"
                )
            
            # Save reports
            guardian_dir = self.repo_path / ".guardian"
            guardian_dir.mkdir(exist_ok=True)
            
            # Save JSON report (structured data for tools)
            json_file = guardian_dir / "mindq_cleanup.json"
            json_data = {
                "timestamp": report["timestamp"],
                "scan_type": report["scan_type"],
                "summary": report["summary"],
                "findings": [
                    {
                        "id": item.id,
                        "kind": item.kind,
                        "file": item.file,
                        "symbol": item.symbol,
                        "why_suspected": item.why_suspected,
                        "confidence": item.confidence,
                        "related_phase": item.related_phase,
                        "suggested_action": item.suggested_action,
                        "line_number": item.line_number,
                        "details": item.details
                    }
                    for item in report["findings"]
                ],
                "recommendations": report["recommendations"]
            }
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)
            
            # Save markdown report (human-readable)
            md_file = guardian_dir / "mindq_cleanup.md"
            content = f"""# 🔍 Mind-Q Deep Cleanup Report (Refactor Radar)

**Generated**: {report['timestamp']}  
**Scan Type**: Deep Code-Aware Analysis

## 📊 Executive Summary

- **Total Findings**: {report['summary']['total_items']}
- **High Confidence**: {report['summary']['by_confidence']['high']}
- **Medium Confidence**: {report['summary']['by_confidence']['medium']}
- **Low Confidence**: {report['summary']['by_confidence']['low']}

### Findings by Category

"""
            
            for kind, count in sorted(report['summary']['by_kind'].items(), key=lambda x: -x[1]):
                emoji = {
                    "unused_import": "📦",
                    "unused_symbol": "🔤",
                    "oversized_file": "📄",
                    "oversized_function": "🔧",
                    "duplicate_function": "👯",
                    "outdated_phase_doc": "📅",
                    "missing_phase_doc": "❌",
                    "orphan_module": "🏚️"
                }.get(kind, "🔍")
                content += f"- {emoji} **{kind.replace('_', ' ').title()}**: {count}\n"
            
            content += "\n"
            
            # Group findings by confidence
            high_conf = [f for f in report["findings"] if f.confidence >= 0.8]
            med_conf = [f for f in report["findings"] if 0.6 <= f.confidence < 0.8]
            low_conf = [f for f in report["findings"] if f.confidence < 0.6]
            
            if high_conf:
                content += "## 🔴 High Confidence Findings\n\n"
                for item in high_conf[:20]:  # Limit to top 20
                    content += f"### {item.id}: {item.kind.replace('_', ' ').title()}\n\n"
                    content += f"- **File**: `{item.file}`\n"
                    if item.symbol:
                        content += f"- **Symbol**: `{item.symbol}`\n"
                    if item.line_number:
                        content += f"- **Line**: {item.line_number}\n"
                    content += f"- **Why**: {item.why_suspected}\n"
                    content += f"- **Confidence**: {item.confidence:.0%}\n"
                    if item.related_phase:
                        content += f"- **Phase**: {item.related_phase}\n"
                    content += f"- **Action**: {item.suggested_action.replace('_', ' ')}\n"
                    if item.details:
                        content += f"- **Details**: {item.details}\n"
                    content += "\n"
                
                if len(high_conf) > 20:
                    content += f"_...and {len(high_conf) - 20} more high-confidence findings. See JSON report for full list._\n\n"
            
            if med_conf and len(med_conf) <= 10:
                content += "## 🟡 Medium Confidence Findings\n\n"
                for item in med_conf:
                    content += f"- **{item.id}**: {item.kind} in `{item.file}`"
                    if item.symbol:
                        content += f" (`{item.symbol}`)"
                    content += f" - {item.why_suspected}\n"
                content += "\n"
            elif med_conf:
                content += f"## 🟡 Medium Confidence Findings ({len(med_conf)})\n\n"
                content += "_See JSON report for details._\n\n"
            
            if low_conf:
                content += f"## 🟢 Low Confidence Findings ({len(low_conf)})\n\n"
                content += "_These are potential issues that may need manual verification. See JSON report for details._\n\n"
            
            if report['recommendations']:
                content += "## 💡 Recommendations\n\n"
                for i, rec in enumerate(report['recommendations'], 1):
                    content += f"{i}. {rec}\n"
                content += "\n"
            
            content += "---\n\n"
            content += "## 📝 Notes\n\n"
            content += "- This is an **informational report only** - no automatic changes are made\n"
            content += "- Review each finding and take appropriate action based on your project needs\n"
            content += "- Confidence levels indicate likelihood of the finding being actionable\n"
            content += "- Low confidence findings may be false positives and require manual review\n\n"
            content += "## 🔧 Available Actions\n\n"
            content += "- **Refresh docs**: `python -m src.guardian_mindq . --refresh-docs`\n"
            content += "- **Review JSON**: `.guardian/mindq_cleanup.json` for structured data\n"
            content += "- **Create refactor plan**: Use findings to create a structured refactor plan\n\n"
            content += "---\n\n"
            content += f"Generated by Mind-Q Guardian v1.4 - Refactor Radar\n"
            
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            report["cleanup_md_file"] = str(md_file)
            report["cleanup_json_file"] = str(json_file)
            
        except Exception as e:
            report["error"] = str(e)
        
        return report
    
    def refresh_docs_after_changes(self, phases_to_refresh: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Refresh Mind-Q documentation (spine + phase cards) after real code changes.
        
        Use this after making actual changes to phase implementations to keep
        documentation in sync.
        
        Args:
            phases_to_refresh: Optional list of specific phase IDs to refresh.
                              If None, refreshes all phases.
        
        Returns:
            Dict with paths to refreshed documentation
        """
        results = {
            "spine_refreshed": False,
            "spine_path": None,
            "phase_cards_refreshed": [],
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Always rebuild spine to pick up any structural changes
            self.build_spine()
            results["spine_path"] = self.save_spine()
            results["spine_refreshed"] = True
            
            # Refresh phase cards
            if phases_to_refresh:
                # Refresh specific phases
                for phase_id in phases_to_refresh:
                    try:
                        card_path = self.save_phase_card(phase_id)
                        results["phase_cards_refreshed"].append({
                            "phase_id": phase_id,
                            "path": card_path,
                            "status": "success"
                        })
                    except Exception as e:
                        results["phase_cards_refreshed"].append({
                            "phase_id": phase_id,
                            "status": "error",
                            "error": str(e)
                        })
            else:
                # Refresh all phases
                all_cards = self.generate_all_phase_cards()
                for card_path in all_cards:
                    phase_id = Path(card_path).stem
                    results["phase_cards_refreshed"].append({
                        "phase_id": phase_id,
                        "path": card_path,
                        "status": "success"
                    })
            
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    def refresh_all(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Refresh all Mind-Q Guardian artifacts.
        
        Args:
            output_dir: Optional custom output directory
            
        Returns:
            Summary of generated artifacts
        """
        results = {
            "spine_path": None,
            "phase_cards": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # Build and save spine
        self.build_spine()
        results["spine_path"] = self.save_spine()
        
        # Generate all phase cards
        results["phase_cards"] = self.generate_all_phase_cards(output_dir)
        
        return results


# CLI Interface
def main():
    """Command-line interface for Mind-Q Guardian."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Mind-Q Guardian Adapter")
    parser.add_argument("repo_path", help="Path to Mind-Q repository")
    parser.add_argument("--build-spine", action="store_true", help="Build and save spine")
    parser.add_argument("--generate-cards", action="store_true", help="Generate all phase cards")
    parser.add_argument("--refresh-all", action="store_true", help="Refresh all artifacts")
    parser.add_argument("--refresh-docs", action="store_true", help="Refresh documentation after code changes")
    parser.add_argument("--cleanup", action="store_true", help="Run basic cleanup analysis (docs only)")
    parser.add_argument("--deep-cleanup", action="store_true", help="Run deep code-aware cleanup analysis (Refactor Radar)")
    parser.add_argument("--status", action="store_true", help="Show current Guardian status")
    parser.add_argument("--phase", help="Generate card for specific phase")
    parser.add_argument("--context", help="Get context for user request")
    parser.add_argument("--kpi-mapping", action="store_true", help="Show KPI to phase mapping")
    parser.add_argument("--phase-kpis", help="Show KPIs impacted by specific phase")
    parser.add_argument("--map-request", help="Map a user request to relevant phases")
    parser.add_argument("--plan-change", help="Create a change plan from a user request")
    parser.add_argument("--demo", action="store_true", help="Run demo showcasing all features")
    
    args = parser.parse_args()
    
    adapter = MindQGuardianAdapter(args.repo_path)
    
    if args.build_spine:
        spine_path = adapter.save_spine()
        print(f"✅ Spine saved to: {spine_path}")
        print(f"\n📊 Generated spine with {len(adapter._spine_data['phases'])} phases and {len(adapter._spine_data['kpis'])} KPIs")
    
    elif args.generate_cards:
        cards = adapter.generate_all_phase_cards()
        print(f"✅ Generated {len(cards)} phase cards")
        for card_path in cards:
            print(f"   - {card_path}")
    
    elif args.refresh_all:
        results = adapter.refresh_all()
        print(f"✅ Refreshed all artifacts:")
        print(f"   Spine: {results['spine_path']}")
        print(f"   Phase cards: {len(results['phase_cards'])}")
    
    elif args.refresh_docs:
        print("🔄 Refreshing documentation after code changes...")
        results = adapter.refresh_docs_after_changes()
        if results.get('error'):
            print(f"❌ Error: {results['error']}")
        else:
            print(f"✅ Documentation refreshed:")
            print(f"   Spine: {results['spine_refreshed']}")
            print(f"   Phase cards: {len(results['phase_cards_refreshed'])}")
            for card_info in results['phase_cards_refreshed']:
                if card_info['status'] == 'success':
                    print(f"      ✅ {card_info['phase_id']}")
                else:
                    print(f"      ❌ {card_info['phase_id']}: {card_info.get('error', 'Unknown error')}")
    
    elif args.cleanup:
        print("🧹 Running cleanup analysis...")
        report = adapter.run_cleanup()
        if report.get('error'):
            print(f"❌ Error: {report['error']}")
        else:
            print(f"\n📊 Cleanup Summary:")
            print(f"   Unused phases: {len(report['unused_phases'])}")
            print(f"   Outdated cards: {len(report['outdated_cards'])}")
            print(f"   Missing cards: {len(report['missing_cards'])}")
            
            if report['recommendations']:
                print(f"\n💡 Recommendations:")
                for rec in report['recommendations']:
                    print(f"   - {rec}")
            
            if report.get('cleanup_file'):
                print(f"\n📄 Full report saved to: {report['cleanup_file']}")
                print(f"   (Review this file for details, NOT included in MDC)")
    
    elif args.deep_cleanup:
        print("🔍 Running deep code-aware cleanup analysis (Refactor Radar)...")
        print("   This may take a moment...\n")
        report = adapter.run_deep_cleanup()
        if report.get('error'):
            print(f"❌ Error: {report['error']}")
        else:
            print(f"📊 Deep Cleanup Summary:")
            print(f"   Total findings: {report['summary']['total_items']}")
            print(f"   High confidence: {report['summary']['by_confidence']['high']}")
            print(f"   Medium confidence: {report['summary']['by_confidence']['medium']}")
            print(f"   Low confidence: {report['summary']['by_confidence']['low']}")
            
            if report['summary']['by_kind']:
                print(f"\n📋 Findings by Category:")
                for kind, count in sorted(report['summary']['by_kind'].items(), key=lambda x: -x[1])[:5]:
                    print(f"   - {kind.replace('_', ' ').title()}: {count}")
            
            if report['recommendations']:
                print(f"\n💡 Recommendations:")
                for rec in report['recommendations'][:5]:
                    print(f"   - {rec}")
            
            print(f"\n📄 Reports saved:")
            print(f"   Markdown: {report.get('cleanup_md_file', 'N/A')}")
            print(f"   JSON: {report.get('cleanup_json_file', 'N/A')}")
            print(f"\n💡 Review the markdown report for detailed findings.")
            print(f"   Use JSON report for programmatic analysis.")
    
    elif args.status:
        print("📊 Mind-Q Guardian Status\n")
        status = adapter.scan_guardian_status()
        print(f"Status: {status.status}")
        if status.last_goal:
            print(f"Last Goal: {status.last_goal}")
        if status.target_phases:
            print(f"Target Phases: {', '.join(status.target_phases)}")
        print(f"Files: {status.planned_files_count} planned, {status.extra_files_count} extra")
        
        # Show compact status summary
        print(f"\n{adapter.get_status_summary()}")
    
    elif args.phase:
        card_path = adapter.save_phase_card(args.phase)
        print(f"✅ Phase card saved to: {card_path}")
        
        # Show KPIs impacted by this phase
        kpis = adapter.get_phase_kpi_impact(args.phase)
        if kpis:
            print(f"\n📊 KPIs impacted by {args.phase}:")
            for kpi in kpis:
                print(f"   - {kpi['name']}: {kpi['description']}")
    
    elif args.context:
        context = adapter.get_guardian_context_for_request(args.context)
        print(context)
    
    elif args.kpi_mapping:
        adapter.build_spine()
        mapping = adapter.get_kpi_phase_mapping()
        print("📊 KPI → Phase Mapping:\n")
        for kpi_name, phases in mapping.items():
            print(f"{kpi_name}:")
            for phase in phases:
                print(f"  - {phase}")
            print()
    
    elif args.phase_kpis:
        kpis = adapter.get_phase_kpi_impact(args.phase_kpis)
        if kpis:
            print(f"📊 KPIs impacted by {args.phase_kpis}:\n")
            for kpi in kpis:
                print(f"- **{kpi['name']}** ({kpi['category']})")
                print(f"  {kpi['description']}\n")
        else:
            print(f"No KPIs directly impacted by {args.phase_kpis}")
    
    elif args.map_request:
        phases = adapter.map_request_to_phases(args.map_request)
        print(f"🗺️  Request: '{args.map_request}'")
        print(f"\n📍 Mapped to phases:")
        for phase in phases:
            print(f"   - {phase}: {adapter._phase_id_to_name(phase)}")
        if not phases:
            print("   (No specific phases identified)")
    
    elif args.plan_change:
        print(f"📋 Creating change plan for: '{args.plan_change}'")
        print("=" * 60)
        
        # Build change request
        change_req = adapter.build_change_request(args.plan_change)
        print(f"\n1️⃣ Change Request:")
        print(f"   ID: {change_req['id']}")
        print(f"   Target phases: {', '.join(change_req['target_phases']) if change_req['target_phases'] else 'None detected'}")
        
        # Create plan
        plan = adapter.plan_change(change_req)
        print(f"\n2️⃣ Change Plan:")
        print(f"   Files to edit: {len(plan['files_to_edit'])}")
        for f in plan['files_to_edit'][:5]:
            print(f"      - {f}")
        if len(plan['files_to_edit']) > 5:
            print(f"      ... and {len(plan['files_to_edit']) - 5} more")
        
        print(f"\n   Affected KPIs: {', '.join(plan['affected_kpis']) if plan['affected_kpis'] else 'None'}")
        
        if plan['potential_risks']:
            print(f"\n   ⚠️  Potential Risks:")
            for risk in plan['potential_risks']:
                print(f"      - {risk}")
        
        # Record the plan
        log_path = adapter.record_change(change_req, plan)
        print(f"\n✅ Change plan recorded to: {log_path}")
    
    elif args.demo:
        print("🎯 Mind-Q Guardian Adapter Demo")
        print("=" * 50)
        
        # 1. Build spine
        print("\n1️⃣ Building pipeline spine...")
        adapter.build_spine()
        print(f"   ✅ Found {len(adapter._spine_data['phases'])} phases")
        print(f"   ✅ Tracking {len(adapter._spine_data['kpis'])} KPIs")
        
        # 2. Show KPI mapping
        print("\n2️⃣ KPI → Phase Mapping (sample):")
        mapping = adapter.get_kpi_phase_mapping()
        for kpi_name in list(mapping.keys())[:3]:
            print(f"   {kpi_name}: {', '.join(mapping[kpi_name][:3])}...")
        
        # 3. Generate sample phase card
        print("\n3️⃣ Generating sample phase card (01_ingestion)...")
        card = adapter.generate_phase_card("01_ingestion")
        print(f"   Goal: {card['goal'][:80]}...")
        print(f"   Inputs: {len(card['inputs'])} | Outputs: {len(card['outputs'])}")
        
        # 4. Context generation example
        print("\n4️⃣ Context generation example:")
        query = "Fix data quality issues in profiling stage"
        context = adapter.get_guardian_context_for_request(query)
        print(f"   Query: '{query}'")
        print(f"   Context size: {len(context)} chars (vs ~150KB traditional)")
        
        # 5. Save artifacts
        print("\n5️⃣ Saving artifacts...")
        results = adapter.refresh_all()
        print(f"   ✅ Spine: {Path(results['spine_path']).name}")
        print(f"   ✅ Phase cards: {len(results['phase_cards'])}")
        
        # 6. Extended file discovery demo
        print("\n6️⃣ Extended file discovery (05_missing):")
        card = adapter.generate_phase_card("05_missing")
        print(f"   Found {len(card['code_files'])} code files (including contracts)")
        for f in card['code_files'][:3]:
            print(f"      - {f}")
        
        # 7. Change planning demo
        print("\n7️⃣ Change planning example:")
        test_request = "Fix PSI calculation in missing value imputation"
        change_req = adapter.build_change_request(test_request)
        plan = adapter.plan_change(change_req)
        print(f"   Request: '{test_request}'")
        print(f"   Mapped to phases: {', '.join(change_req['target_phases'])}")
        print(f"   Files to edit: {len(plan['files_to_edit'])}")
        print(f"   Affected KPIs: {', '.join(plan['affected_kpis'][:3])}...")
        
        # 8. Soft guardian layer demo
        print("\n8️⃣ Soft Guardian Layer:")
        print("   📊 Status tracking & checklist management")
        
        # Show status using new API
        status = adapter.scan_guardian_status()
        print(f"   Status: {status.status}")
        if status.last_goal:
            print(f"   Last goal: {status.last_goal[:50]}...")
        
        # Show checklist location
        guardian_dir = adapter.repo_path / ".guardian"
        status_file = guardian_dir / "mindq_status.md"
        if status_file.exists():
            print(f"   ✅ Checklist: .guardian/mindq_status.md")
        else:
            print(f"   📝 Checklist created automatically on plan_change()")
        
        # 9. Cleanup analysis demo (UPGRADED)
        print("\n9️⃣ Cleanup Analysis (UPGRADED - Refactor Radar):")
        print("   Running deep code-aware cleanup analysis...")
        cleanup_report = adapter.run_deep_cleanup()
        if not cleanup_report.get('error'):
            print(f"   Total findings: {cleanup_report['summary']['total_items']}")
            print(f"   High confidence: {cleanup_report['summary']['by_confidence']['high']}")
            if cleanup_report['summary']['by_kind']:
                top_kind = max(cleanup_report['summary']['by_kind'].items(), key=lambda x: x[1])
                print(f"   Top issue: {top_kind[0].replace('_', ' ').title()} ({top_kind[1]})")
            if cleanup_report.get('cleanup_md_file'):
                print(f"   📄 Reports: .guardian/mindq_cleanup.md + .json")
                print(f"   (Not included in MDC - agents review separately)")
        
        # 10. Documentation refresh demo
        print("\n🔟 Documentation Refresh:")
        print("   After code changes, refresh with:")
        print("   python -m src.guardian_mindq . --refresh-docs")
        print("   Keeps spine + phase cards in sync with implementation")
        
        print("\n✨ Demo complete! Mind-Q Guardian v1.4 - Now with Refactor Radar 🔍")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
