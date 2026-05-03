# Chain Monitor Operational Runbook

Quick recovery, diagnostics, and day-to-day operations for the Chain Monitor pipeline.

---

## Restart Sequence After OOM / Crash

```bash
cd ~/chain-monitor

# 1. Kill zombie browsers (always)
killall -9 chromium chromium-browser chrome 2>/dev/null
ps aux | grep -i chrome | grep -v grep | awk '{print $2}' | xargs -r kill -9

# 2. Remove stale Twitter state
rm -f storage/twitter/raw/stale_*.json
rm -f storage/twitter/cookies.json.lock

# 3. Check disk / memory
df -h . | tail -1
free -h | head -2

# 4. Run health check
python3 scripts/doctor.py

# 5. Run pipeline (dry-run first if suspect)
python3 main.py

# 6. Check output
ls -lt storage/agent_input/daily_prompt_*.md | head -1
```

---

## Adding a New Chain

```bash
# Option A: CLI
python3 scripts/chain_monitor_cli.py chains add mychain --category high_tps --tier 2 --coingecko_id mycoin --defillama_slug mychain

# Option B: Edit YAML directly
nano config/chains.yaml

# Then add baselines in config/baselines.yaml

# Then add Twitter accounts in config/twitter_accounts.yaml (optional)

# Verify
python3 scripts/chain_monitor_cli.py chains list | grep mychain
```

---

## Diagnosing Silent Collectors

A collector returning 0 events for 2+ consecutive runs triggers an alert in the digest.

```bash
# Check latest metrics
tail -1 storage/metrics/metrics.jsonl | python3 -m json.tool

# Check collector run state
cat storage/metrics/collector_run_state.json | python3 -m json.tool

# Check specific collector health
grep -i "defillama" storage/health/run_*.json | tail -5

# Quick manual test
python3 -c "from collectors.defillama import DefiLlamaCollector; c=DefiLlamaCollector(); print(len(c.collect()))"
```

---

## Browser Zombie Cleanup

Playwright/Chromium zombies are the #1 cause of OOM on the Steam Deck.

```bash
# See how many chrome processes exist
ps aux | grep -c chrome

# Kill all chrome older than 60 seconds
for pid in $(ps --no-headers -eo pid,etimes,comm | awk '$3 ~ /chrome/ && $2 >= 60 {print $1}'); do kill -9 $pid; done

# Prevent accumulation: run pipeline with --no-twitter if Twitter is borked
# (edit main.py collector list temporarily)
```

---

## API Key Rotation

| Key | Env Var | Where to Get New | How to Validate |
|-----|---------|------------------|---------------|
| CoinGecko | `COINGECKO_API_KEY` | coingecko.com/en/api/pricing | `python3 -c "from collectors.coingecko_collector import CoinGeckoCollector; print(CoinGeckoCollector().collect()[:1])"` |
| CryptoRank | `CRYPTORANK_API_KEY` | cryptorank.io/public-api/pricing | Check events_collector output |
| YouTube | `YOUTUBE_API_KEY` | console.cloud.google.com | `curl "https://www.googleapis.com/youtube/v3/channels?part=snippet&id=UC...&key=YOUR_KEY"` |
| GitHub | `GITHUB_TOKEN` or `gh auth token` | Already have `gh` CLI | `gh auth status` |

After rotation, run `python3 scripts/doctor.py`.

---

## Cron Management

```bash
# Install daily cron at 09:00 UTC
python3 scripts/chain_monitor_cli.py cron install --hour 9

# Install weekly cron at 09:00 UTC on Mondays
# (add manually to crontab — CLI doesn't support weekly yet)
crontab -e
# Add:
# 0 9 * * 1 cd ~/chain-monitor && .venv/bin/python main.py --weekly >> storage/logs/weekly.log 2>&1

# Remove all chain-monitor crons
python3 scripts/chain_monitor_cli.py cron remove

# Check if cron is running
ps aux | grep -i chain-monitor
```

---

## Pipeline Stages Explained

| Stage | What It Does | Failure Mode | Recovery |
|-------|--------------|--------------|----------|
| 1 Collect | 9 collectors run in parallel | Twitter browser hang | Kill chrome, re-run |
| 2 Dedup | O(n) hash dedup | None (pure compute) | N/A |
| 3 Categorize | Agent or source categories | Agent missing | Falls through to source categories |
| 4 Score | Rule-based priority | Bad baseline | Check `config/baselines.yaml` |
| 5 Analyze | Per-chain digest build | Missing chain config | `chains.yaml` entry absent |
| 6 Synthesize | Agent-native synthesis | N/A | Prompt saved to storage/agent_input/ |
| 7 Deliver | Agent-native persistence | N/A | N/A |

---

## Common Errors and Fixes

### `Qdrant lock error` in gateway
The mem0 Qdrant instance is locked by another process. Each gateway needs `MEM0_DIR` set.

```bash
# Check which gateway holds the lock
ls -l ~/.mem0*/

# Fix: ensure each gateway launch script exports MEM0_DIR
# Example wrapper:
export HERMES_HOME=/home/deck/.hermes-mila
export MEM0_DIR=$HERMES_HOME/.mem0
nohup hermes-gateway --profile mila >> /tmp/mila.log 2>&1 &
```

### `ModuleNotFoundError: No module named 'pytest'`
The venv isn't activated in cron or subprocess.

```bash
# Always use .venv/bin/python explicitly in cron
.venv/bin/python -m pytest tests/ -q
```

### `LLM returned empty response`
Ollama model not loaded, or context window too small.

```bash
# Check Ollama
ollama list | grep minimax

# Pull if missing
ollama pull minimax-m2.7:cloud
```

---

## File Locations

| Artifact | Path | Retention |
|----------|------|-----------|
| Daily agent prompt | `storage/agent_input/daily_prompt_YYYYMMDD_HHMMSS.md` | Manual cleanup |
| Daily prose digest | `storage/daily_digests/daily_digest_YYYYMMDD_HHMMSS.md` | Manual cleanup |
| Weekly digest | `storage/agent_input/weekly_digest_YYYYMMDD_HHMMSS.md` | Manual cleanup |
| Pipeline metrics | `storage/metrics/metrics.jsonl` | Append-only, rotate manually |
| Run logs | `storage/health/run_YYYYMMDD_HHMMSS.json` | 90 days (configurable) |
| Twitter raw | `storage/twitter/raw/` | 90 days |
| Collector state | `storage/metrics/collector_run_state.json` | Overwritten each run |

---

## Performance Tuning for Steam Deck

| Resource | Default | Deck Tuned | File |
|----------|---------|------------|------|
| Concurrent collectors | 4 | 4 | `config/pipeline.yaml` |
| Twitter workers | 15 | 15 | `config/pipeline.yaml` |
| Memory throttle MB | 500 | 500 | `config/pipeline.yaml` |
| Throttle concurrency | 2 | 2 | `config/pipeline.yaml` |

If OOM still occurs during Twitter scraping:
- Reduce `twitter.max_workers` to 8
- Reduce `twitter.num_batches` to 5
- Run Twitter standalone in a separate process with a timeout wrapper

---

## Weekly Digest Checklist

Run weekly digest manually before cron is active:

```bash
# 1. Ensure at least 3 days of daily prompts exist
ls storage/agent_input/daily_prompt_*.md | wc -l

# 2. Build weekly
python3 -c "from output.weekly_digest import build_digest; print(build_digest()[:500])"

# 3. Run full weekly pipeline
python3 main.py --weekly

# 4. Check output
ls -lt storage/agent_input/weekly_digest_*.md | head -1
```

---

## Emergency Contacts (Self)

- Project root: `~/chain-monitor`
- Venv Python: `~/chain-monitor/.venv/bin/python`
- Logs: `storage/health/run_*.json`, `storage/metrics/metrics.jsonl`
- Config: `config/pipeline.yaml`, `config/chains.yaml`, `.env`
- Gateway logs: `/tmp/hermes-*.log`, `/tmp/mila.log`
