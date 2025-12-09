#!/usr/bin/env python3
"""
Guardian Auto-Scanner
Scans a project and generates a guardian.mdc snapshot automatically.
"""

import os
import json
import re
import ast
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class GuardianScanner:
    """Scans a project and generates a Guardian snapshot."""
    
    # Folders to skip
    SKIP_DIRS = {
        'node_modules', '__pycache__', '.git', '.venv', 'venv',
        'dist', 'build', '.next', '.cache', 'coverage', '.pytest_cache',
        '.cursor', '.windsurf', '.idea', '.vscode'
    }
    
    # Priority 1: Code files (analyzed for functions)
    CODE_EXTENSIONS = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
        '.java', '.kt', '.swift', '.go', '.rs', '.rb', '.php',
        '.c', '.cpp', '.h', '.hpp', '.cs'
    }
    
    # Priority 2: Config files (important but no function extraction)
    CONFIG_EXTENSIONS = {
        '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
        '.env', '.env.example', '.env.local',
        '.gitignore', '.dockerignore', '.prettierrc', '.eslintrc'
    }
    
    # Priority 3: Documentation files
    DOC_EXTENSIONS = {
        '.md', '.mdx', '.txt', '.rst', '.adoc'
    }
    
    # Priority 4: Style files
    STYLE_EXTENSIONS = {
        '.css', '.scss', '.sass', '.less', '.styl'
    }
    
    # Priority 5: Data/Asset files (just list, no analysis)
    DATA_EXTENSIONS = {
        '.sql', '.csv', '.xml', '.html', '.svg'
    }
    
    # Priority 6: All other files (optional, for complete coverage)
    # Any extension not in above categories
    
    def __init__(self, project_path: str, scan_all: bool = True):
        self.project_path = Path(project_path).resolve()
        self.project_name = self.project_path.name
        self.scan_all = scan_all  # If True, scan ALL file types
        self.snapshot = {
            'identity': {},
            'tech_stack': {},
            'dependencies': {'frontend': {}, 'backend': {}},
            'env_vars': {'required': [], 'optional': []},
            'files': {},
            'files_by_category': {
                'code': {},
                'config': {},
                'docs': {},
                'styles': {},
                'data': {},
                'other': {}
            },
            'connections': {},
            'run': {},
            'locked': [],
            'danger': [],
            'issues': [],
            'changes': []
        }

    
    def scan(self) -> dict:
        """Run full project scan."""
        print(f"🔍 Scanning: {self.project_path}")
        
        self._detect_identity()
        self._detect_tech_stack()
        self._detect_dependencies()
        self._detect_env_vars()
        self._scan_files()
        self._detect_connections()
        self._detect_run_commands()
        
        return self.snapshot
    
    def _detect_identity(self):
        """Detect project name and purpose."""
        self.snapshot['identity'] = {
            'name': self.project_name,
            'purpose': self._guess_purpose(),
            'status': 'development'
        }
    
    def _guess_purpose(self) -> str:
        """Try to guess project purpose from README or package.json."""
        readme_path = self.project_path / 'README.md'
        if readme_path.exists():
            content = readme_path.read_text()[:500]
            # Extract first paragraph after title
            lines = content.split('\n')
            for line in lines[1:]:
                if line.strip() and not line.startswith('#'):
                    return line.strip()[:100]
        return "{{ONE_LINE_PURPOSE}}"
    
    def _detect_tech_stack(self):
        """Detect technologies used."""
        stack = {}
        
        # Check package.json for frontend
        pkg_path = self.project_path / 'package.json'
        if pkg_path.exists():
            pkg = json.loads(pkg_path.read_text())
            deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
            
            # Frontend framework
            if 'react' in deps:
                stack['frontend'] = 'React ' + deps.get('react', '').lstrip('^~')
            elif 'vue' in deps:
                stack['frontend'] = 'Vue ' + deps.get('vue', '').lstrip('^~')
            elif 'svelte' in deps:
                stack['frontend'] = 'Svelte'
            elif 'next' in deps:
                stack['frontend'] = 'Next.js'
            
            # Styling
            if 'tailwindcss' in deps:
                stack['styling'] = 'Tailwind CSS'
            elif 'styled-components' in deps:
                stack['styling'] = 'Styled Components'
            
            # Electron
            if 'electron' in deps:
                stack['frontend'] = stack.get('frontend', '') + ' + Electron'
        
        # Check requirements.txt for backend
        req_path = self.project_path / 'requirements.txt'
        if req_path.exists():
            content = req_path.read_text().lower()
            if 'fastapi' in content:
                stack['backend'] = 'FastAPI'
            elif 'django' in content:
                stack['backend'] = 'Django'
            elif 'flask' in content:
                stack['backend'] = 'Flask'
        
        # Check for database
        if list(self.project_path.rglob('*.db')):
            stack['database'] = 'SQLite'
        
        self.snapshot['tech_stack'] = stack
    
    def _detect_dependencies(self):
        """Extract dependency versions."""
        # Frontend deps
        pkg_path = self.project_path / 'package.json'
        if pkg_path.exists():
            pkg = json.loads(pkg_path.read_text())
            deps = pkg.get('dependencies', {})
            # Get top 10 most important
            important = ['react', 'vue', 'next', 'electron', 'tailwindcss', 
                        'typescript', 'vite', 'webpack', 'express']
            for dep in important:
                if dep in deps:
                    self.snapshot['dependencies']['frontend'][dep] = deps[dep].lstrip('^~')
        
        # Backend deps
        req_path = self.project_path / 'requirements.txt'
        if req_path.exists():
            for line in req_path.read_text().split('\n'):
                if '==' in line:
                    name, version = line.split('==')[:2]
                    self.snapshot['dependencies']['backend'][name.strip()] = version.strip()
                elif line.strip() and not line.startswith('#'):
                    self.snapshot['dependencies']['backend'][line.strip()] = 'latest'
    
    def _detect_env_vars(self):
        """Detect environment variables from .env.example or code."""
        env_example = self.project_path / '.env.example'
        if env_example.exists():
            for line in env_example.read_text().split('\n'):
                if '=' in line and not line.startswith('#'):
                    var = line.split('=')[0].strip()
                    self.snapshot['env_vars']['required'].append({
                        'name': var,
                        'description': 'TODO: add description'
                    })
        
        # Also check .env.sample
        env_sample = self.project_path / '.env.sample'
        if env_sample.exists() and not env_example.exists():
            for line in env_sample.read_text().split('\n'):
                if '=' in line and not line.startswith('#'):
                    var = line.split('=')[0].strip()
                    self.snapshot['env_vars']['required'].append({
                        'name': var,
                        'description': 'TODO: add description'
                    })
    
    def _scan_files(self):
        """
        Two-phase file scanning:
        Phase 1: Priority files (code, config, docs) - fast, with function extraction
        Phase 2: All other files (if scan_all=True) - comprehensive listing
        """
        print("📂 Phase 1: Scanning priority files...")
        
        # Phase 1: Code files (with function extraction)
        for ext in self.CODE_EXTENSIONS:
            for file_path in self.project_path.rglob(f'*{ext}'):
                if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                    continue
                
                rel_path = str(file_path.relative_to(self.project_path))
                purpose = self._infer_purpose(file_path)
                functions = self._extract_functions(file_path)
                
                file_info = {'purpose': purpose, 'functions': functions, 'category': 'code'}
                self.snapshot['files'][rel_path] = file_info
                self.snapshot['files_by_category']['code'][rel_path] = file_info
        
        # Phase 1: Config files (no function extraction)
        for ext in self.CONFIG_EXTENSIONS:
            for file_path in self.project_path.rglob(f'*{ext}'):
                if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                    continue
                
                rel_path = str(file_path.relative_to(self.project_path))
                purpose = self._infer_config_purpose(file_path)
                
                file_info = {'purpose': purpose, 'functions': [], 'category': 'config'}
                self.snapshot['files'][rel_path] = file_info
                self.snapshot['files_by_category']['config'][rel_path] = file_info
        
        # Phase 1: Documentation files
        for ext in self.DOC_EXTENSIONS:
            for file_path in self.project_path.rglob(f'*{ext}'):
                if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                    continue
                
                rel_path = str(file_path.relative_to(self.project_path))
                purpose = 'documentation'
                
                file_info = {'purpose': purpose, 'functions': [], 'category': 'docs'}
                self.snapshot['files'][rel_path] = file_info
                self.snapshot['files_by_category']['docs'][rel_path] = file_info
        
        # Phase 1: Style files
        for ext in self.STYLE_EXTENSIONS:
            for file_path in self.project_path.rglob(f'*{ext}'):
                if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                    continue
                
                rel_path = str(file_path.relative_to(self.project_path))
                purpose = 'styling'
                
                file_info = {'purpose': purpose, 'functions': [], 'category': 'styles'}
                self.snapshot['files'][rel_path] = file_info
                self.snapshot['files_by_category']['styles'][rel_path] = file_info
        
        # Phase 2: All other files (if scan_all is True)
        if self.scan_all:
            print("📂 Phase 2: Scanning all remaining files...")
            known_extensions = (
                self.CODE_EXTENSIONS | self.CONFIG_EXTENSIONS | 
                self.DOC_EXTENSIONS | self.STYLE_EXTENSIONS | self.DATA_EXTENSIONS
            )
            
            # Data files
            for ext in self.DATA_EXTENSIONS:
                for file_path in self.project_path.rglob(f'*{ext}'):
                    if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                        continue
                    
                    rel_path = str(file_path.relative_to(self.project_path))
                    if rel_path not in self.snapshot['files']:
                        purpose = 'data'
                        file_info = {'purpose': purpose, 'functions': [], 'category': 'data'}
                        self.snapshot['files'][rel_path] = file_info
                        self.snapshot['files_by_category']['data'][rel_path] = file_info
            
            # All other files (unknown extensions)
            for file_path in self.project_path.rglob('*'):
                if not file_path.is_file():
                    continue
                if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                    continue
                
                rel_path = str(file_path.relative_to(self.project_path))
                
                # Skip if already scanned
                if rel_path in self.snapshot['files']:
                    continue
                
                # Skip binary files (common binary extensions)
                binary_exts = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.webp',
                              '.mp3', '.mp4', '.wav', '.avi', '.mov',
                              '.pdf', '.zip', '.tar', '.gz', '.rar',
                              '.exe', '.dll', '.so', '.dylib',
                              '.woff', '.woff2', '.ttf', '.eot',
                              '.db', '.sqlite', '.sqlite3'}
                if file_path.suffix.lower() in binary_exts:
                    purpose = f'asset ({file_path.suffix})'
                else:
                    purpose = 'other'
                
                file_info = {'purpose': purpose, 'functions': [], 'category': 'other'}
                self.snapshot['files'][rel_path] = file_info
                self.snapshot['files_by_category']['other'][rel_path] = file_info
        
        print(f"   ✅ Total files scanned: {len(self.snapshot['files'])}")
    
    def _infer_config_purpose(self, file_path: Path) -> str:
        """Infer purpose for config files."""
        name = file_path.name.lower()
        
        if 'package.json' in name:
            return 'npm-config'
        if 'tsconfig' in name:
            return 'typescript-config'
        if 'eslint' in name:
            return 'linting-config'
        if 'prettier' in name:
            return 'formatting-config'
        if 'docker' in name:
            return 'docker-config'
        if 'env' in name:
            return 'environment-vars'
        if 'gitignore' in name:
            return 'git-ignore'
        if 'requirements' in name:
            return 'python-deps'
        if 'pyproject' in name:
            return 'python-project'
        
        return 'config'
    
    def _infer_purpose(self, file_path: Path) -> str:
        """Infer file purpose from name and location."""
        name = file_path.stem.lower()
        parent = file_path.parent.name.lower()
        
        # Component patterns
        if parent in ['components', 'component']:
            return f"{name}-ui"
        if parent in ['hooks', 'hook']:
            return f"{name}-logic"
        if parent in ['pages', 'views']:
            return f"{name}-page"
        if parent in ['routes', 'api']:
            return f"{name}-endpoints"
        if parent in ['services', 'service']:
            return f"{name}-service"
        if parent in ['utils', 'helpers', 'lib']:
            return f"{name}-utils"
        if parent in ['models', 'model']:
            return f"{name}-model"
        
        # Entry points
        if name in ['main', 'app', 'index', 'server']:
            return 'entry-point'
        
        return f"{name}"
    
    def _extract_functions(self, file_path: Path) -> List[str]:
        """Extract function/method names from a file."""
        functions = []
        ext = file_path.suffix
        
        try:
            content = file_path.read_text()
            
            if ext == '.py':
                # Python: use AST
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if not node.name.startswith('_'):
                                functions.append(node.name)
                except SyntaxError:
                    pass
            
            elif ext in ['.js', '.jsx', '.ts', '.tsx']:
                # JavaScript/TypeScript: regex patterns
                patterns = [
                    r'(?:function|const|let|var)\s+(\w+)\s*(?:=\s*(?:async\s*)?\(|=\s*(?:async\s*)?function|\()',
                    r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*{',
                    r'export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)',
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    functions.extend(matches)
                
                # Remove duplicates and filter
                functions = list(set(f for f in functions 
                                    if f and not f.startswith('_') 
                                    and f not in ['if', 'for', 'while', 'switch']))
        
        except Exception:
            pass
        
        return functions[:10]  # Limit to top 10
    
    def _detect_connections(self):
        """Detect ports and connections between services."""
        connections = {}
        
        # Search for port definitions
        port_patterns = [
            r'port["\']?\s*[=:]\s*(\d{4,5})',
            r'localhost:(\d{4,5})',
            r'127\.0\.0\.1:(\d{4,5})',
            r'PORT\s*=\s*(\d{4,5})',
        ]
        
        for file_path in self.project_path.rglob('*'):
            if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.env', '.json']:
                if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                    continue
                try:
                    content = file_path.read_text()
                    for pattern in port_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        for port in matches:
                            if 1000 <= int(port) <= 65535:
                                connections[port] = str(file_path.relative_to(self.project_path))
                except Exception:
                    pass
        
        self.snapshot['connections'] = connections
    
    def _detect_run_commands(self):
        """Detect run commands from package.json or common patterns."""
        run = {}
        
        # Check package.json scripts
        pkg_path = self.project_path / 'package.json'
        if pkg_path.exists():
            pkg = json.loads(pkg_path.read_text())
            scripts = pkg.get('scripts', {})
            
            if 'dev' in scripts:
                run['frontend'] = f"npm run dev"
            elif 'start' in scripts:
                run['frontend'] = f"npm start"
            
            if 'test' in scripts:
                run['test_frontend'] = "npm test"
        
        # Check for Python backend
        if (self.project_path / 'requirements.txt').exists():
            main_py = self.project_path / 'main.py'
            api_main = self.project_path / 'api' / 'main.py'
            
            if api_main.exists():
                run['backend'] = "cd api && uvicorn main:app --reload"
            elif main_py.exists():
                run['backend'] = "uvicorn main:app --reload"
        
        self.snapshot['run'] = run
    
    def generate_file_index_markdown(self) -> str:
        """
        Generate a comprehensive file index as markdown.
        This is saved separately and NOT included in LLM-facing MDC files.
        
        Returns:
            Full file listing in markdown format
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # Group files by directory
        files_by_dir = {}
        for path, info in sorted(self.snapshot['files'].items()):
            dir_name = str(Path(path).parent) if Path(path).parent != Path('.') else '(root)'
            if dir_name not in files_by_dir:
                files_by_dir[dir_name] = []
            files_by_dir[dir_name].append((path, info))
        
        # Build comprehensive markdown
        md = f"""# 📂 Complete File Index
> Generated: {timestamp}
> This file contains a comprehensive listing of all project files.
> **Note**: This is for reference only and is NOT included in LLM context.

## 📊 Summary
- **Total Files**: {len(self.snapshot['files'])}
- **Directories**: {len(files_by_dir)}

---

"""
        
        # Add files by directory
        for dir_name in sorted(files_by_dir.keys()):
            md += f"\n## 📁 {dir_name}\n\n"
            for path, info in files_by_dir[dir_name]:
                funcs = ', '.join(info['functions'][:5]) if info['functions'] else '-'
                md += f"### {Path(path).name}\n"
                md += f"- **Path**: `{path}`\n"
                md += f"- **Purpose**: {info['purpose']}\n"
                md += f"- **Functions**: {funcs}\n\n"
        
        md += "\n---\n\n*🛡️ Guardian File Index - For reference, not for LLM context*\n"
        
        return md
    
    def save_file_index(self, guardian_dir: Optional[Path] = None) -> Path:
        """
        Save full file index to .guardian/file_index.md
        
        Args:
            guardian_dir: Guardian directory path (default: .guardian in project root)
            
        Returns:
            Path to saved file index
        """
        if guardian_dir is None:
            guardian_dir = self.project_path / '.guardian'
        
        guardian_dir.mkdir(parents=True, exist_ok=True)
        file_index_path = guardian_dir / 'file_index.md'
        
        content = self.generate_file_index_markdown()
        file_index_path.write_text(content)
        
        print(f"   📄 Full file index saved: {file_index_path}")
        return file_index_path
    
    def generate_mdc(self) -> str:
        """
        Generate COMPACT MDC file content for LLM context.
        Full file index is saved separately in .guardian/file_index.md
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # Build COMPACT files section (max 50 files + directory summary)
        files_str = ""
        file_count = 0
        max_files = 50
        
        # Group files by directory for summary
        dir_summary = {}
        for path, info in sorted(self.snapshot['files'].items()):
            dir_name = str(Path(path).parent) if Path(path).parent != Path('.') else '(root)'
            if dir_name not in dir_summary:
                dir_summary[dir_name] = 0
            dir_summary[dir_name] += 1
            
            # Only show first 50 files in detail
            if file_count < max_files:
                funcs = ', '.join(info['functions'][:3]) if info['functions'] else '-'
                files_str += f"{path}: {info['purpose']} | {funcs}\n"
                file_count += 1
        
        # Add summary line if more files exist
        total_files = len(self.snapshot['files'])
        if total_files > max_files:
            files_str += f"\n... and {total_files - max_files} more files\n"
        
        # Add directory summary
        files_str += f"\n📊 Directory Summary ({len(dir_summary)} directories):\n"
        for dir_name, count in sorted(dir_summary.items(), key=lambda x: -x[1])[:10]:
            files_str += f"  {dir_name}: {count} files\n"
        
        # Build dependencies section
        deps_frontend = '\n  '.join(f"{k}: {v}" for k, v in self.snapshot['dependencies']['frontend'].items())
        deps_backend = '\n  '.join(f"{k}: {v}" for k, v in self.snapshot['dependencies']['backend'].items())
        
        # Build env vars section
        env_required = '\n  '.join(f"- {v['name']}: {v['description']}" 
                                   for v in self.snapshot['env_vars']['required'])
        
        # Build connections section
        connections_str = '\n'.join(f"  port_{port}: {file}" 
                                    for port, file in self.snapshot['connections'].items())
        
        # Build run section
        run_str = '\n'.join(f"{k}: {v}" for k, v in self.snapshot['run'].items())
        
        mdc = f"""---
description: 🛡️ PROJECT SNAPSHOT - Read before ANY action
globs: **/*
alwaysApply: true
---

# 🧠 {self.snapshot['identity']['name']} SNAPSHOT
> ⚠️ READ THIS BEFORE ANY CODE CHANGE
> Auto-synced: {timestamp}

---

## IDENTITY
```yaml
name: {self.snapshot['identity']['name']}
purpose: {self.snapshot['identity']['purpose']}
status: {self.snapshot['identity']['status']}
```

---

## TECH_STACK
> ❌ DO NOT SUGGEST ALTERNATIVES
```yaml
{chr(10).join(f"{k}: {v}" for k, v in self.snapshot['tech_stack'].items())}
```

---

## DEPENDENCIES
```yaml
frontend:
  {deps_frontend if deps_frontend else '# No frontend dependencies detected'}
backend:
  {deps_backend if deps_backend else '# No backend dependencies detected'}
```

---

## ENV_VARS
```yaml
required:
  {env_required if env_required else '# No env vars detected - check .env.example'}
optional:
  # Add optional vars here
```

---

## FILES
> 📂 CHECK HERE BEFORE CREATING ANY FILE
> 📄 Full listing: `.guardian/file_index.md` (NOT for LLM context)
```
{files_str if files_str else '# No code files detected'}

💡 For complete file listing, open and review: .guardian/file_index.md
```

---

## CONNECTIONS
```yaml
{connections_str if connections_str else '# No connections detected'}
```

---

## RUN
> ⚡ USE EXACTLY THESE COMMANDS
```bash
{run_str if run_str else '# Add run commands here'}
```

---

## LOCKED
> 🔒 CANNOT CHANGE WITHOUT USER APPROVAL
```yaml
# Add locked decisions here
# Example: - React: framework # locked: PERMANENT
```

---

## DANGER
> ⚠️ THESE FILES BREAK EASILY
```yaml
# Add dangerous files here
# Example: - path: main.py, reason: port hardcoded
```

---

## ISSUES
> 🐛 CURRENT KNOWN ISSUES
```yaml
# Add known issues here
```

---

## CHANGES
> 📝 RECENT CHANGES (Last 10)
```yaml
- {timestamp}: Initial Guardian scan | auto-generated
```

---

## AGENT_RULES
> 🤖 YOU MUST FOLLOW THESE

### Before ANY Action:
1. ✅ Read this snapshot
2. ✅ Check FILES - does similar exist?
3. ✅ Check LOCKED - am I violating any?
4. ✅ Check DANGER - is this risky?

### Before Creating File:
- CHECK: FILES section for same purpose
- IF EXISTS: Ask "تعديل الموجود أم إنشاء جديد؟"
- LOCATION: Follow existing folder pattern

### After ANY Change:
- UPDATE: FILES if new file created
- UPDATE: CHANGES section
"""
        return mdc
    
    def generate_lite_mdc(self) -> str:
        """Generate compact, AI-optimized MDC format."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # Build tech stack
        tech_str = '\n'.join(f"  {k}: {v}" for k, v in self.snapshot['tech_stack'].items())
        
        # Build files (compact format)
        files_str = ""
        for path, info in sorted(self.snapshot['files'].items())[:50]:  # Limit to 50
            files_str += f"  {path}: {info['purpose']}\n"
        
        # Build connections
        conn_str = ""
        for port, file in self.snapshot['connections'].items():
            conn_str += f"  port_{port}: {file}\n"
        
        mdc = f"""---
description: 🛡️ GUARDIAN - Read BEFORE any action
globs: **/*
alwaysApply: true
---

# 🛡️ {self.snapshot['identity']['name']} GUARDIAN
> Auto-synced: {timestamp}

---

## 📋 RULES (Decision Table)

| Action | Check | Do |
|--------|-------|-----|
| Create file | `FILES` has similar? | → ASK user first |
| Modify file | In `DANGER`? | → WARN before proceed |
| Change config | In `LOCKED`? | → STOP, ask approval |
| Any change | - | → TEST then UPDATE |

---

## ⚡ QUICK_RULES
```yaml
before_action:
  1: Read this file
  2: Check FILES section
  3: Check DANGER section
  4: If unclear → ASK user

after_action:
  1: Test the change
  2: Update CHANGES section
  3: Show proof of success
```

---

## 🏗️ TECH_STACK
```yaml
# ❌ DO NOT SUGGEST ALTERNATIVES
{tech_str if tech_str else '  # Not detected'}
```

---

## 📂 FILES
```yaml
# CHECK before creating
{files_str if files_str else '  # No files detected'}
```

---

## 🔌 CONNECTIONS
```yaml
{conn_str if conn_str else '  # No connections detected'}
```

---

## 🔒 LOCKED
```yaml
# CANNOT change without user approval
  # Add locked decisions here
```

---

## ⚠️ DANGER
```yaml
# WARN before touching
  # Add dangerous files here
```

---

## 📝 CHANGES
```yaml
- {timestamp}: Initial Guardian scan
```

---

## 🧠 THINKING
```yaml
problem_solving:
  1: Read error → Trace flow → Find root cause
  2: Check FILES → Check DANGER → Design solution
  3: One change → Test → Confirm → Show proof

code_quality:
  performance: Measure first, optimize later
  extensibility: Small functions, DI
  simplicity: KISS, YAGNI, DRY
  structure:
    - Modularize: File < 300 lines, Func < 50 lines
    - Anchors: Use docstrings & regions
    - Naming: Descriptive filenames

if_confused: ASK "هل تقصد X أم Y؟"
```
"""
        return mdc
    
    def save(self, output_path: Optional[str] = None) -> str:
        """Save the generated MDC file."""
        if output_path is None:
            output_path = self.project_path / 'guardian.mdc'
        else:
            output_path = Path(output_path)
        
        content = self.generate_mdc()
        output_path.write_text(content)
        print(f"✅ Saved: {output_path}")
        return str(output_path)


def scan_project(project_path: str, output_path: Optional[str] = None) -> str:
    """
    Scan a project and generate a Guardian snapshot.
    
    Args:
        project_path: Path to the project root
        output_path: Optional custom output path for the MDC file
    
    Returns:
        Path to the generated guardian.mdc file
    """
    scanner = GuardianScanner(project_path)
    scanner.scan()
    return scanner.save(output_path)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python guardian_scanner.py <project_path> [output_path]")
        print("Example: python guardian_scanner.py /path/to/myproject")
        sys.exit(1)
    
    project_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = scan_project(project_path, output_path)
    print(f"\n🛡️ Guardian snapshot generated: {result}")
