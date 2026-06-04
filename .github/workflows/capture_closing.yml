name: Capture Closing Lines

on:
  # Cron lâche : sert UNIQUEMENT à découvrir les matchs du jour
  # (les ajouter à closing_lines.json pour que le worker connaisse leur commence_time).
  # Le timing serré du closing est géré par le worker Cloudflare via repository_dispatch.
  schedule:
    - cron: '7 6-22 * * *'        # 1×/h, minute 7 pour éviter la congestion de :00
  # Déclenché par le worker Cloudflare quand un match approche (T-25 / T-10)
  repository_dispatch:
    types: [capture_closing]
  workflow_dispatch:

# Évite que deux captures se marchent dessus (cron + worker en même temps)
concurrency:
  group: capture-closing
  cancel-in-progress: false

jobs:
  capture:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Capture closing lines
        env:
          ODDS_API_KEY_1: ${{ secrets.ODDS_API_KEY_1 }}
          ODDS_API_KEY_2: ${{ secrets.ODDS_API_KEY_2 }}
          ODDS_API_KEY_3: ${{ secrets.ODDS_API_KEY_3 }}
          ODDS_API_KEY_4: ${{ secrets.ODDS_API_KEY_4 }}
          ODDS_API_KEY_5: ${{ secrets.ODDS_API_KEY_5 }}
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python scripts/capture_closing.py

      - name: Commit closing lines
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add closing_lines.json odds_alerts_state.json odds_alerts_log.jsonl odds_logged_state.json games_markets.json 2>/dev/null || true
          git diff --staged --quiet || git commit -m "Closing lines update"
          git pull --rebase --autostash 2>/dev/null || true
          git push

