# Rule Hierarchy

Clean Code Reviewer uses a 3-level cascading rule system. Higher levels override lower levels when rules conflict.

## Levels

| Level | Directory    | Purpose                           | Example                                  |
| ----- | ------------ | --------------------------------- | ---------------------------------------- |
| 1     | `base.md`    | Universal principles              | "Write clean, readable code"              |
| 2     | `community/` | All external rules (equal status) | Google Python, Airbnb JS, anyone's rules |
| 3     | `team/`      | Your team's overrides (HIGHEST)   | Company-specific conventions             |

**All external rules are equal.** Google's style guide isn't more "official" than your company's.

## Directory Structure

```
.cleancoderules/
├── config.yaml
├── base.md                    # Level 1 - Base principles
├── community/                 # Level 2 - All external rules
│   ├── google/
│   │   └── python.md
│   ├── airbnb/
│   │   └── javascript.md
│   └── anycompany/
│       └── their-rules.md
└── team/                      # Level 3 - YOUR rules (HIGHEST)
    ├── naming.md
    └── logging.md
```

## How Overrides Work

Rules are loaded in order: Level 1 → 2 → 3. Later rules override earlier ones.

### Example: Function Length

```
Level 1 (base.md):
  "Keep functions under 20 lines"

Level 2 (community/google/python.md):
  "Functions should be under 40 lines for Python"

Level 3 (team/exceptions.md):
  "Data processing functions may be up to 100 lines"
```

**Result:** For Python data processing, 100 lines is acceptable. For other Python code, 40 lines. For other languages, 20 lines.

## Adding Rules

### Download from Remote Repository

```bash
# Default: download to community/
ccr add google/python                    # → community/google/python.md
ccr add airbnb/javascript                # → community/airbnb/javascript.md
ccr add anycompany/their-style           # → community/anycompany/their-style.md

# Download to team/ (for shared team templates)
ccr add -d team myteam/standards         # → team/myteam/standards.md
```

### Add Local Files

```bash
# Add to team/
ccr add -d team -f my-rules.md           # → team/my-rules.md
ccr add -d team -f path/to/rule.md       # → team/rule.md (file only)
```

## Rule File Format

Rules are Markdown files with YAML frontmatter:

```markdown
---
name: my-rule
language: python
tags: [security, naming]
---

# Rule Title

Your rule content here...

## Guidelines

- Guideline 1
- Guideline 2
```

### Frontmatter Fields

| Field      | Required | Description                            |
| ---------- | -------- | -------------------------------------- |
| `name`     | No       | Rule identifier (defaults to filename) |
| `language` | No       | Target language (null = all languages) |
| `tags`     | No       | Categorization tags                    |

## Rule Ordering

Rule order within each level is managed through `order.yml`, not frontmatter.

### The order.yml File

```yaml
# Rule ordering - position determines priority
# Later in list = higher priority = overrides earlier

community:
  - google/python
  - airbnb/javascript
team:
  - naming
  - logging
  - security
```

### Using ccr order

Use the `ccr order` command to reorder rules within a level:

```bash
ccr order               # Opens TUI to reorder rules
```

Controls:

- `1/2` - Switch between community/team panels
- `k/↑` - Move rule up (lower priority)
- `j/↓` - Move rule down (higher priority)
- `q` - Save and quit

Rules can only be reordered within their level - you cannot move a team rule to community.

## Conflict Resolution

When the LLM receives the merged rules, it sees:

```
## LEVEL 1: Base Principles
...

## LEVEL 2: Community Rules
...

## LEVEL 3: Team Rules (HIGHEST PRIORITY)
...

---

**CONFLICT RESOLUTION:** If rules conflict, higher levels override lower levels.
Team rules (Level 3) always take precedence.
```

This makes it clear to the LLM which rules should win in case of conflicts.
