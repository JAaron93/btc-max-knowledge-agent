# GitHub Actions YAML Indentation Guide

## Proper Indentation Structure

In GitHub Actions workflows, proper YAML indentation is crucial for parsing. Here's the correct structure:

### ✅ Correct Indentation

```yaml
jobs:
  test:                           # 2 spaces from left margin
    runs-on: ubuntu-latest        # 4 spaces from left margin
    strategy:                     # 4 spaces from left margin
      matrix:                     # 6 spaces from left margin
        python-version: ["3.8"]   # 8 spaces from left margin
    
    steps:                        # 4 spaces from left margin
      - uses: actions/checkout@v3 # 6 spaces from left margin (list item)
      
      - name: Set up Python       # 6 spaces from left margin (list item)
        uses: actions/setup-python@v4  # 8 spaces from left margin
        with:                     # 8 spaces from left margin
          python-version: ${{ matrix.python-version }}  # 10 spaces
```

### ❌ Incorrect Indentation (What Was Fixed)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3   # ❌ Same level as 'steps' - WRONG!
    - name: Set up Python        # ❌ Same level as 'steps' - WRONG!
      uses: actions/setup-python@v4
```

## Key Rules

1. **List items** (`-`) should be indented **2 spaces** from their parent key
2. **Child properties** should be indented **2 spaces** from their parent
3. **Consistency** is crucial - maintain the same indentation pattern throughout

## Indentation Levels in Our Workflow

- `jobs:` - 0 spaces (root level)
- `test:` - 2 spaces
- `runs-on:`, `strategy:`, `steps:` - 4 spaces
- `matrix:` - 6 spaces
- `python-version:` - 8 spaces
- `- uses:`, `- name:` (list items under steps) - 6 spaces
- Properties under list items (`uses:`, `with:`, `run:`) - 8 spaces
- Properties under `with:` - 10 spaces

## Validation

You can validate YAML syntax using:

```bash
# Using Python
python -c "import yaml; yaml.safe_load(open('.github/workflows/tests-example.yml'))"

# Using yamllint (if installed)
yamllint .github/workflows/tests-example.yml
```

## Common Mistakes

1. **List items at wrong level**: List items (`-`) must be indented from their parent key
2. **Inconsistent spacing**: Mixing tabs and spaces or inconsistent space counts
3. **Missing colons**: YAML keys must end with `:`
4. **Incorrect nesting**: Child elements must be properly indented under parents

The fix applied to `tests-example.yml` corrected the list item indentation under the `steps:` key, ensuring proper YAML parsing.