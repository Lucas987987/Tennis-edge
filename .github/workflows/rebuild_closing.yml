name: Rebuild Closing
on:
  workflow_dispatch:
jobs:
  rebuild:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python scripts/rebuild_closing.py
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add closing_lines.json
          git diff --staged --quiet || git commit -m "Rebuild closing blocks"
          git pull --rebase --autostash 2>/dev/null || true
          git push
