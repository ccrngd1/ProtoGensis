# MemoryGuard Quick Start

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd memory-guard

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package
pip install -e .
```

## Usage

### Run the demo

```bash
memoryguard demo
```

### Scan a memory file

```bash
memoryguard scan path/to/MEMORY.md
```

### Generate a report

```bash
# Markdown report
memoryguard scan MEMORY.md --output report.md

# JSON report
memoryguard scan MEMORY.md --output report.json --format json
```

### Use in CI/CD

```bash
# Exit with non-zero if high-risk issues found
memoryguard scan MEMORY.md --json | jq -e '.summary.high_risk == 0'
```

## Example Output

```
Loading memory file: demo/sample_memory.md
✓ Loaded 7 entries
Running detection modules...

┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Metric             ┃ Value  ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ Entries Scanned    │ 7      │
│ Entries Flagged    │ 2      │
│ High Risk (≥70)    │ 2      │
│ Medium Risk (40-69)│ 0      │
│ Low Risk (<40)     │ 0      │
└────────────────────┴────────┘

⚠ Issues Detected:

● injected-override (Risk: 95)
  [90] Directive pattern detected: 'IGNORE ALL PREVIOUS INSTRUCTIONS'
  [95] Privilege escalation pattern detected

● injected-bypass (Risk: 85)
  [85] Directive pattern detected: '<SYSTEM>'
  [75] Directive pattern detected: 'Do not read'
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=memoryguard --cov-report=html
```
