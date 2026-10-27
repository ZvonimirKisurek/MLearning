# Runbook: run it locally with real keys, then calibrate it

Prereqs: Docker, Python 3.11+, Node 22, an OpenAI key (embeddings) and an Anthropic key (generation). Set a monthly
spend limit on both keys in their consoles before you start.

## 1. Configure
```bash
cp .env.example .env
openssl rand -hex 32            # paste the output as API_TOKEN
```
Edit `.env`: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `API_TOKEN`, `USER_AGENT` (put a real contact email in it, it
is sent to every site you scrape), `TIMEZONE` (e.g. `Europe/Zagreb`). Optional: `ROADMAP_START` (see Roadmap below).
```bash
cp frontend/.env.example frontend/.env.local   # then set API_TOKEN to the SAME value; API_URL stays http://localhost:8000
```

## 2. Infrastructure (Postgres+pgvector, Redis)
```bash
docker compose up -d db redis
docker compose exec db psql -U postgres mlesprint -c '\dt' -c '\dx'   # expect 9 tables and the `vector` extension
```
Migrations run automatically, but only when the data volume is empty (first boot). If you started the DB before this
phase: `docker compose down -v && docker compose up -d db redis` (this deletes local data).

## 3. Backend install + tests
```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
pytest -q                                   # expect 85 passed
```

## 4. Four terminals
```bash
# 1  API            (in backend/, venv active)
uvicorn app.main:app --reload
# 2  Celery worker  (in backend/, venv active)
celery -A app.celery_app worker --loglevel=INFO
# 3  Celery beat    (in backend/, venv active)  - the scheduler
celery -A app.celery_app beat --loglevel=INFO
# 4  Frontend
cd frontend && npm install && npm run dev        # http://localhost:3000
```
Check: `curl localhost:8000/health` returns `{"status":"ok"}` and
`curl -H "Authorization: Bearer $API_TOKEN" localhost:8000/api/skills | head -c 200` returns JSON.

## 5. First real run (in backend/, venv active)
```bash
python -m app.cli ingest --dry-run 2>&1 | tee dryrun.txt   # triage dead sources (see the failure-kind table in the README)
python -m app.cli ingest                                   # fetch -> parse -> embed -> dedup -> store
python -m app.cli embed-skills                             # embed the 7 skill descriptions (the retrieval "queries")
python -m app.cli summarize --limit 120                    # AI summaries for the 120 highest-weight recent articles
python -m app.cli generate-weekly --dry-run                # READ the exact prompt the model will receive
python -m app.cli generate-weekly
python -m app.cli generate-daily
```
Starting mid-week? The weekly job plans the *next* Monday. For the current week run
`python -m app.cli generate-weekly --date <this Monday, YYYY-MM-DD>` before `generate-daily`.

### What you should see
```bash
docker compose exec db psql -U postgres mlesprint \
  -c "select status, stats from ingestion_runs order by started_at desc limit 1" \
  -c "select category, count(*) from articles a join sources s on s.id=a.source_id where duplicate_of is null group by 1" \
  -c "select count(*) filter (where duplicate_of is not null) as duplicates, count(*) filter (where ai_summary is not null) as summarised, count(*) filter (where embedding is not null) as embedded from articles" \
  -c "select slug, embedding is not null as embedded from skills" \
  -c "select week_start, title from weekly_themes" \
  -c "select kind, skill_slug, title from daily_tasks order by kind"
```
- `ingestion_runs.stats`: `sources_ok` (most of them once dead feeds are fixed), `inserted` (hundreds on the first run),
  `duplicates` (few on the first run, more on later ones, because the same story arrives from several feeds).
- `duplicates` rows have `embedding is null` by design (the vector is never queried again).
- Dashboard `/`: Today's Mission with 3 tasks, the weekly theme card, the skill radar. `/feed`: articles with AI summaries
  and skill badges. If `/` says "not ready", click Generate now (needs the worker) or run `generate-daily`.
- Rough LLM cost (estimate, check your console): one weekly or daily generation is ~10-15k input and ~3-6k output
  tokens, i.e. a few cents on Sonnet-class pricing; summaries on Haiku are far cheaper. Order of a few dollars a month.

## 5b. Starting mid-week (roadmap week 1, today's briefing)
The weekly job normally runs Sunday night. To start now, in `backend/` with the venv active:
```bash
MONDAY=$(python3 -c "import datetime as d; t=d.date.today(); print(t-d.timedelta(days=t.weekday()))"); echo $MONDAY
# put ROADMAP_START=<that date> in ../.env  (week 1 = the calendar week containing it)
python -m app.cli generate-weekly --dry-run --date $MONDAY      # check the <roadmap_week> block is in the prompt
python -m app.cli generate-weekly --date $MONDAY --force        # --force replaces any free-mode theme already created
python -m app.cli generate-daily --force                        # today = roadmap day <weekday number>
python -m app.cli usage                                         # what that cost
```
You skip the outline items for the days already past this week (they are in `backend/curriculum/roadmap.yaml`);
do the missed ones on the light weekend days, or set `ROADMAP_START` to next Monday and treat this week as setup.
`generate-daily --dry-run` needs the weekly theme stored first (run `generate-weekly` before it).

## 6. Calibrate the relevance engine
```bash
python -m app.cli feed-stats
python -m app.cli calibrate --n 80 --labels calibration_labels.json   # label ~80 articles (resume anytime: q to quit)
python -m app.cli calibrate --analyze --labels calibration_labels.json
```
Put the suggested `MATCH_STRONG` / `MATCH_MODERATE` into `.env`, restart uvicorn, re-run `feed-stats`.
Edit a skill's description (the retrieval "query"): `update skills set description='...' where slug='rag';` then
`python -m app.cli embed-skills --force`. Keep `calibration_labels.json`: it is Week 2's training set.

## 7. Roadmap mode
Set `ROADMAP_START=<the Monday you begin>` in `.env`. From then on `generate-weekly` follows `backend/curriculum/roadmap.yaml`
(4 weeks), and the news only picks timely readings. After week 4 it returns to free mode. To restart, change the date.
Edit the YAML to change the plan (skills must be existing slugs).
