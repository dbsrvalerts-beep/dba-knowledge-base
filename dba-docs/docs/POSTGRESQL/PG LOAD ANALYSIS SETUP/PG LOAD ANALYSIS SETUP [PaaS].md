# PG LOAD ANALYSIS SETUP [PaaS]
**PostgreSQL Load Analysis**

**Azure Database for PostgreSQL - Flexible Server**

Implementation Steps · Schema Changes · Analysis Queries · Retention Lifecycle

_Ginesys / Browntape Technologies | DBA Team | June 2026_

_This is the consolidated PaaS implementation document. It combines the original v2.1 implementation steps (Phase 1-2), the DB Head schema change request (Phase 3: cpu_ms_est, blk_read/write_time, query_id), and the new Phase 4 Retention Lifecycle (3-day rolling purge via pg_cron). PostgreSQL version: PG 17 (Azure Flexible Server). The collection job uses PG17 column names shared_blk_read_time / shared_blk_write_time from pg_stat_statements. Deploy in order: Phase 1 → Phase 2 → Phase 3 → Phase 4._

## Phase 1 - Pre-Requisites & Environment Check

### 1.1 Verify pg_stat_statements is enabled

Run on each Flexible Server cluster before starting. If not enabled, add to postgresql.conf (server parameters) and reload.

-- Check if extension is loaded

```sql
SELECT name, setting FROM pg_settings WHERE name = 'shared_preload_libraries';
```

-- Check extension exists

```sql
SELECT * FROM pg_extension WHERE extname = 'pg_stat_statements';
```

-- If not present, add to server parameters in Azure Portal:

-- shared_preload_libraries = 'pg_stat_statements'

-- Then run:
```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```
### 1.2 Create monitoring user

Dedicated read-only role - do not use a superuser account for collection.

```sql
CREATE ROLE pg_monitor_reader LOGIN PASSWORD 'set-a-strong-password';
```sql
GRANT pg_monitor TO pg_monitor_reader;
```sql
GRANT CONNECT ON DATABASE postgres TO pg_monitor_reader;
```sql
GRANT USAGE ON SCHEMA public TO pg_monitor_reader;
```sql
GRANT SELECT ON pg_stat_statements TO pg_monitor_reader;
```sql
GRANT SELECT ON pg_stat_activity TO pg_monitor_reader;
```sql
GRANT SELECT ON pg_stat_database TO pg_monitor_reader;
```sql
GRANT SELECT ON pg_locks TO pg_monitor_reader;
```
### 1.3 Create the monitoring schema and tables

Created in a separate monitoring database - not on the production databases being measured. These are the final table definitions including all DB Head columns added in Phase 3.

```sql
CREATE DATABASE pg_loadmon;
\\c pg_loadmon
```sql
CREATE SCHEMA monitoring;
```

-- Statement-level snapshots (every 1 min)

```sql
CREATE TABLE monitoring.stmt_snapshots (
id BIGSERIAL PRIMARY KEY,
captured_at TIMESTAMPTZ DEFAULT NOW(),
dbname TEXT,
application_name TEXT,
query_text TEXT, -- first 200 chars
calls BIGINT,
total_exec_time DOUBLE PRECISION,
rows BIGINT,
shared_blks_hit BIGINT,
shared_blks_read BIGINT,
query_id BIGINT, -- queryid from pg_stat_statements
temp_blks_written BIGINT,
wal_bytes BIGINT,
blk_read_time DOUBLE PRECISION, -- our column name; source on PG17: shared_blk_read_time
blk_write_time DOUBLE PRECISION, -- our column name; source on PG17: shared_blk_write_time
cpu_ms_est DOUBLE PRECISION -- total_exec_time - shared_blk_read_time - shared_blk_write_time
);
```sql
CREATE INDEX ON monitoring.stmt_snapshots (captured_at);
CREATE INDEX ON monitoring.stmt_snapshots (query_id);
```
-- Active session snapshots (every 30 sec)

```sql
CREATE TABLE monitoring.session_snapshots (
id BIGSERIAL PRIMARY KEY,
captured_at TIMESTAMPTZ DEFAULT NOW(),
pid INT,
dbname TEXT,
application_name TEXT,
state TEXT,
wait_event_type TEXT,
wait_event TEXT,
query_start TIMESTAMPTZ,
duration_secs DOUBLE PRECISION,
query_id BIGINT -- from pg_stat_activity (Phase 3)
);
```sql
CREATE INDEX ON monitoring.session_snapshots (captured_at);
CREATE INDEX ON monitoring.session_snapshots (query_id);
```
-- Lock wait snapshots (every 30 sec)

```sql
CREATE TABLE monitoring.lock_snapshots (
id BIGSERIAL PRIMARY KEY,
captured_at TIMESTAMPTZ DEFAULT NOW(),
waiting_pid INT,
waiting_app TEXT,
blocking_pid INT,
blocking_app TEXT,
lock_type TEXT,
relation TEXT,
wait_secs DOUBLE PRECISION
);
```sql
CREATE INDEX ON monitoring.lock_snapshots (captured_at);
```

-- Database-level snapshots (every 60 sec)

```sql
CREATE TABLE monitoring.db_snapshots (
id BIGSERIAL PRIMARY KEY,
captured_at TIMESTAMPTZ DEFAULT NOW(),
dbname TEXT,
numbackends INT,
xact_commit BIGINT,
xact_rollback BIGINT,
blks_hit BIGINT,
blks_read BIGINT,
tup_returned BIGINT,
tup_fetched BIGINT
);
```sql
CREATE INDEX ON monitoring.db_snapshots (captured_at, dbname);
```

-- Grant INSERT + SELECT on all tables to collection user:

```sql
GRANT INSERT, SELECT ON ALL TABLES IN SCHEMA monitoring TO pg_monitor_reader;
```sql
GRANT USAGE, UPDATE ON ALL SEQUENCES IN SCHEMA monitoring TO pg_monitor_reader;
_The table definitions above are the final combined schema (v2.1 base + Phase 3 additions). If you already created the tables from v2.1, use the ALTER TABLE statements in Phase 3 instead of recreating._
```

## Phase 2 - Monitoring Stack Deployment (pg_cron Jobs)

All collection runs inside pg_loadmon via pg_cron using cron.schedule_in_database(). Connect as superuser to pg_loadmon to register jobs. Collection queries run as the postgres user inside pg_cron workers.

_These are the final job definitions including all Phase 3 columns. If you already have earlier jobs registered, skip to Phase 3 Section 3.1 to drop and recreate them._

### 2.1 Job 1 - Statement snapshots (every 1 minute)

```sql
SELECT cron.schedule_in_database(
'collect_stmts',

'*/1 * * * *',

$$

INSERT INTO monitoring.stmt_snapshots
(dbname, application_name, query_text, calls, total_exec_time,

rows, shared_blks_hit, shared_blks_read, query_id,

temp_blks_written, wal_bytes,

blk_read_time, blk_write_time, cpu_ms_est)

SELECT
d.datname,

COALESCE(sa.application_name, 'unknown') AS application_name,

s.query AS query_text,

s.calls, s.total_exec_time, s.rows,

s.shared_blks_hit, s.shared_blks_read, s.queryid,

s.temp_blks_written, s.wal_bytes,

s.shared_blk_read_time, -- PG17+ name

s.shared_blk_write_time, -- PG17+ name

s.total_exec_time - s.shared_blk_read_time - s.shared_blk_write_time

FROM pg_stat_statements s
JOIN pg_database d ON d.oid = s.dbid

LEFT JOIN pg_stat_activity sa ON sa.query_id = s.queryid

AND sa.usesysid = s.userid

AND sa.state = 'active';

$$,

'postgres'

);
```

### 2.2 Job 2 - Sessions + locks at :00 (every minute)

```sql
SELECT cron.schedule_in_database(
'collect_sessions_locks_00',

'* * * * *',

$$

INSERT INTO monitoring.session_snapshots
(pid, dbname, application_name, state, wait_event_type,

wait_event, query_start, duration_secs, query_id)

SELECT pid, datname, application_name, state,
wait_event_type, wait_event, query_start,

EXTRACT(EPOCH FROM (NOW() - query_start)),

query_id

FROM pg_stat_activity
WHERE state = 'active' AND pid <> pg_backend_pid();

INSERT INTO monitoring.lock_snapshots
(waiting_pid, waiting_app, blocking_pid, blocking_app,

lock_type, relation, wait_secs)

SELECT w.pid, w.application_name, b.pid, b.application_name,
lw.locktype, c.relname,

EXTRACT(EPOCH FROM (NOW() - w.query_start))

FROM pg_stat_activity w
JOIN pg_locks lw ON lw.pid = w.pid AND NOT lw.granted

JOIN pg_locks lb ON lb.locktype = lw.locktype AND lb.granted

AND lb.relation IS NOT DISTINCT FROM lw.relation

JOIN pg_stat_activity b ON b.pid = lb.pid

LEFT JOIN pg_class c ON c.oid = lw.relation

WHERE w.wait_event_type = 'Lock';
$$,

'postgres'

);
```

### 2.3 Job 3 - Sessions + locks at :30 (offset by pg_sleep)

_The leading SELECT pg_sleep(30) is plain SQL - do NOT use PERFORM here (pg_cron bodies are SQL, not PL/pgSQL). The pg_sleep appears as ~98% of pg_cron wall-clock in workload reports. It is harmless (zero CPU) but inflates pg_cron's wall-clock share - exclude it from load conclusions._

```sql
SELECT cron.schedule_in_database(
'collect_sessions_locks_30',

'* * * * *',

$$

SELECT pg_sleep(30);

INSERT INTO monitoring.session_snapshots
(pid, dbname, application_name, state, wait_event_type,

wait_event, query_start, duration_secs, query_id)

SELECT pid, datname, application_name, state,
wait_event_type, wait_event, query_start,

EXTRACT(EPOCH FROM (NOW() - query_start)),

query_id

FROM pg_stat_activity
WHERE state = 'active' AND pid <> pg_backend_pid();

INSERT INTO monitoring.lock_snapshots
(waiting_pid, waiting_app, blocking_pid, blocking_app,

lock_type, relation, wait_secs)

SELECT w.pid, w.application_name, b.pid, b.application_name,
lw.locktype, c.relname,

EXTRACT(EPOCH FROM (NOW() - w.query_start))

FROM pg_stat_activity w
JOIN pg_locks lw ON lw.pid = w.pid AND NOT lw.granted

JOIN pg_locks lb ON lb.locktype = lw.locktype AND lb.granted

AND lb.relation IS NOT DISTINCT FROM lw.relation

JOIN pg_stat_activity b ON b.pid = lb.pid

LEFT JOIN pg_class c ON c.oid = lw.relation

WHERE w.wait_event_type = 'Lock';
$$,

'postgres'

);
```

### 2.4 Job 4 - Database stats (every 1 minute)

```sql
SELECT cron.schedule_in_database(
'collect_db_stats',

'* * * * *',

$$

INSERT INTO monitoring.db_snapshots
(dbname, numbackends, xact_commit, xact_rollback,

blks_hit, blks_read, tup_returned, tup_fetched)

SELECT datname, numbackends, xact_commit, xact_rollback,
blks_hit, blks_read, tup_returned, tup_fetched

FROM pg_stat_database
WHERE datname NOT IN ('template0', 'template1', 'postgres');
$$,

'postgres'

);
```

### 2.5 Verify all four jobs are registered

```sql
SELECT jobid, jobname, schedule, database, active
FROM cron.job
ORDER BY jobid;
```
## Phase 3 - Schema Changes (DB Head Request)

**Purpose:** _Two additive schema changes. Change 1 adds blk_read_time, blk_write_time, and derived cpu_ms_est to stmt_snapshots, giving an estimated CPU figure from pg_stat_statements alone. Change 2 adds query_id to session_snapshots so active sessions can be linked back to their statement. Both are additive - no existing columns change. Skip if you created tables using the Phase 1 definitions above (they already include these columns)._

### 3.1 Prerequisites

**Enable track_io_timing**

blk_read_time and blk_write_time are ALWAYS ZERO unless track_io_timing is ON. Without this setting, cpu_ms_est equals total_exec_time, which is meaningless. Note: on PG 17 the source columns are named shared_blk_read_time / shared_blk_write_time in pg_stat_statements - the collection job uses these PG17 names.

SHOW track_io_timing; -- should return 'on'

-- If off, set in Azure Portal > Server Parameters:

-- track_io_timing = on

-- Then reload (no restart needed):

```sql
SELECT pg_reload_conf();
_Overhead: track_io_timing calls the OS clock on every block read/write. On Azure Flexible Server (modern Linux, tsc clock source) this overhead is negligible._
```

**Verify compute_query_id**

SHOW compute_query_id; -- should be 'on' or 'auto'

-- With pg_stat_statements already loaded, 'auto' is normally on.

-- If off: set compute_query_id = auto in Server Parameters and reload.
### 3.2 Change 1 - Add I/O timing and estimated CPU to stmt_snapshots

Run these ALTER statements on the existing table if upgrading from v2.1 base. If created fresh in Phase 1, these columns already exist.

```sql
ALTER TABLE monitoring.stmt_snapshots
ADD COLUMN IF NOT EXISTS blk_read_time DOUBLE PRECISION, -- our column (source PG17: shared_blk_read_time)

ADD COLUMN IF NOT EXISTS blk_write_time DOUBLE PRECISION, -- our column (source PG17: shared_blk_write_time)

ADD COLUMN IF NOT EXISTS cpu_ms_est DOUBLE PRECISION; -- total_exec_time - shared_blk_read_time - shared_blk_write_time
```
-- cpu_ms_est formula (PG17): total_exec_time - shared_blk_read_time - shared_blk_write_time

-- Removes disk I/O wait. Does NOT remove lock/latch/sleep waits.

-- Label it as an estimate in reports.
_PG17 REQUIRED CHANGE: pg_stat_statements on PostgreSQL 17+ renamed blk_read_time → shared_blk_read_time and blk_write_time → shared_blk_write_time (and added local_/temp_variants). The collection job above uses the PG17 names. Your monitoring.stmt_snapshots column names (blk_read_time, blk_write_time) are unchanged - only the source pg_stat_statements column names differ. On PG 16 reverse the names back. Verify your version's column names: SELECT column_name FROM information_schema.columns WHERE table_name='pg_stat_statements' AND column_name LIKE '%blk%time%';_

### 3.3 Change 2 - Add query_id to session_snapshots
```sql
ALTER TABLE monitoring.session_snapshots
ADD COLUMN IF NOT EXISTS query_id BIGINT;
```sql
CREATE INDEX IF NOT EXISTS ix_session_snap_qid
ON monitoring.session_snapshots (query_id);
```

### 3.4 Drop and recreate pg_cron jobs

The two schema changes require the collection jobs to be updated. Drop existing jobs first, then recreate using the Phase 2 definitions (which already include all new columns).

-- Drop existing jobs:

```sql
SELECT cron.unschedule('collect_stmts');
```sql
SELECT cron.unschedule('collect_sessions_locks_00');
```sql
SELECT cron.unschedule('collect_sessions_locks_30');
```sql
SELECT cron.unschedule('collect_db_stats');
```

-- Verify cleared:

```sql
SELECT jobid, jobname, schedule, database, active FROM cron.job ORDER BY jobid;
```

-- Then recreate using the four job definitions in Phase 2 (Sections 2.1-2.4).
_Order of operations: (1) enable track_io_timing + verify compute_query_id, (2) run both ALTER TABLE statements, (3) drop and recreate jobs. If the columns do not exist when a job runs, the INSERT fails and that snapshot is lost._

### 3.5 Verification after collection

-- Change 1: timing populated (non-zero if track_io_timing=on)

```sql
SELECT query_id, blk_read_time, blk_write_time, cpu_ms_est
FROM monitoring.stmt_snapshots
WHERE captured_at >= NOW() - INTERVAL '10 minutes'
AND blk_read_time > 0 LIMIT 5;
```

-- Change 2: query_id populated in session_snapshots

```sql
SELECT pid, application_name, query_id
FROM monitoring.session_snapshots
WHERE captured_at >= NOW() - INTERVAL '10 minutes'
AND query_id IS NOT NULL LIMIT 5;
```

### 3.6 Analysis - Estimated CPU by application (DB Head rollup)

Ranks applications by estimated CPU instead of raw wall-clock. Built-in answer to I/O-bound vs CPU-bound question:
```sql
SELECT
dbname,

ROUND((SUM(cpu_ms_est)/1000.0)::NUMERIC, 1) AS cpu_est_sec,

ROUND((100.0 * SUM(cpu_ms_est) /

NULLIF(SUM(SUM(cpu_ms_est)) OVER(), 0))::NUMERIC, 2) AS pct_cpu_est,

ROUND((SUM(total_exec_time)/1000.0)::NUMERIC, 1) AS wall_sec,

ROUND((SUM(blk_read_time + blk_write_time)/1000.0)::NUMERIC, 1) AS io_wait_sec,

ROUND((100.0 * SUM(blk_read_time + blk_write_time) /

NULLIF(SUM(total_exec_time), 0))::NUMERIC, 1) AS pct_io_wait

FROM monitoring.stmt_snapshots
WHERE captured_at >= NOW() - INTERVAL '24 hours'
GROUP BY dbname
ORDER BY cpu_est_sec DESC;
```
### 3.7 Analysis - Link active sessions to statement cost (query_id join)

Shows which query_ids were most often caught actively running, and what they cost:
```sql
SELECT
ss.query_id,

COUNT(*) AS times_caught_active,

MAX(st.query_text) AS query_text,

ROUND((MAX(st.cpu_ms_est)/1000.0)::NUMERIC,1) AS cpu_est_sec,

ROUND((MAX(st.blk_read_time)/1000.0)::NUMERIC,1) AS io_read_sec

FROM monitoring.session_snapshots ss
LEFT JOIN LATERAL (
SELECT query_text, cpu_ms_est, blk_read_time
FROM monitoring.stmt_snapshots st
WHERE st.query_id = ss.query_id
ORDER BY st.captured_at DESC LIMIT 1
) st ON true
WHERE ss.captured_at >= NOW() - INTERVAL '24 hours'
AND ss.query_id IS NOT NULL

GROUP BY ss.query_id
ORDER BY times_caught_active DESC
LIMIT 30;
```
### 3.8 DB Head Attribution Rollup Query

Per-application breakdown of execution time, I/O, temp I/O, WAL writes, and buffer cache hit ratio:
```sql
WITH ranked AS (
SELECT
application_name, query_id,

MAX(total_exec_time) AS latest_exec_ms,

MAX(calls) AS latest_calls,

MAX(rows) AS latest_rows,

MAX(shared_blks_read) AS latest_blks_read,

MAX(shared_blks_hit) AS latest_blks_hit,

MAX(temp_blks_written) AS latest_temp_blks,

MAX(wal_bytes) AS latest_wal_bytes,

COUNT(*) AS times_observed_active

FROM monitoring.stmt_snapshots
WHERE captured_at >= NOW() - INTERVAL '24 hours'
GROUP BY application_name, query_id
),

totals AS (

SELECT
application_name,

SUM(latest_exec_ms) AS grp_exec_ms,

SUM(latest_calls) AS grp_calls,

SUM(latest_rows) AS grp_rows,

SUM(latest_blks_read) AS grp_blks_read,

SUM(latest_blks_hit) AS grp_blks_hit,

SUM(latest_temp_blks) AS grp_temp_blks,

SUM(latest_wal_bytes) AS grp_wal_bytes,

SUM(times_observed_active) AS grp_active_observations

FROM ranked
GROUP BY application_name
)

SELECT
application_name,

grp_calls,

ROUND((grp_exec_ms / 1000.0)::NUMERIC, 1) AS total_exec_sec,

ROUND((100.0 * grp_exec_ms / SUM(grp_exec_ms) OVER())::NUMERIC, 2) AS pct_exec_time,

grp_rows,

grp_blks_read AS disk_reads,

ROUND((100.0 * grp_blks_read /

NULLIF(SUM(grp_blks_read) OVER(), 0))::NUMERIC, 2) AS pct_disk_reads,

ROUND((100.0 * grp_blks_hit /

NULLIF(grp_blks_read + grp_blks_hit, 0))::NUMERIC, 2) AS buffer_hit_pct,

grp_temp_blks AS temp_io_blks,

ROUND((grp_wal_bytes / 1024.0 / 1024.0)::NUMERIC, 2) AS wal_mb,

ROUND((100.0 * grp_wal_bytes /

NULLIF(SUM(grp_wal_bytes) OVER(), 0))::NUMERIC, 2) AS pct_wal_writes,

grp_active_observations

FROM totals
ORDER BY pct_exec_time DESC;
```
## Phase 4 - Retention Lifecycle (3-Day Rolling Window)

All four monitoring tables grow continuously. Without a purge job the pg_loadmon database will exhaust its Azure disk allocation within days. The policy is: keep exactly 3 days of data, delete everything older. On Azure Flexible Server, retention is implemented as a daily pg_cron job - no shell scripts, no external schedulers.

### 4.1 Data Growth Estimates

| **Table**                   | **Rows/day** | **MB/day** | **3-day cap** | **Collection frequency**                                     |
| --------------------------- | ------------ | ---------- | ------------- | ------------------------------------------------------------ |
| stmt_snapshots              | ~144,000     | ~62 MB     | ~186 MB       | Every 1 min via pg_cron (1,440 snapshots × ~100 queries/min) |
| session_snapshots           | ~57,600      | ~11 MB     | ~33 MB        | Every 30 sec via pg_cron (active sessions only)              |
| lock_snapshots              | negligible   | <1 MB      | <3 MB         | Every 30 sec (rows only when lock waits exist)               |
| db_snapshots                | ~14,400      | ~1 MB      | ~3 MB         | Every 60 sec (1,440 × ~10 databases)                         |
| **TOTAL (raw + index ~2×)** | ~216,000     | ~75 MB     | ~225 MB       | Stable ceiling once purge job is running                     |

_session_snapshots and lock_snapshots only insert rows when sessions are active / when locks exist - so their actual volume is lower than the theoretical max shown above. stmt_snapshots is the dominant table on busy servers because it captures every tracked query shape every minute._

### 4.2 One-Time Permission Grant

The pg_monitor_reader role has INSERT and SELECT on all monitoring tables. DELETE must be added once before the purge job will succeed:

-- Run as superuser (postgres) once in pg_loadmon:

```sql
GRANT DELETE ON ALL TABLES IN SCHEMA monitoring TO pg_monitor_reader;
_Without this grant, the purge pg_cron job will fail with a permission denied error. The collection jobs will continue to run but the tables will keep growing._
```

### 4.3 Purge Job - pg_cron (runs daily at 02:00)

Register a single pg_cron job that deletes rows older than 3 days from all four tables, then issues VACUUM on each to reclaim pages. This runs inside PostgreSQL - no shell access needed on Azure Flexible Server.

```sql
SELECT cron.schedule_in_database(
'purge_monitoring_3day',

'18 31 * * *', -- daily at 02:00 (server local time)

$$

-- ── DELETE old rows (3-day retention) ────────────────────────────

DELETE FROM monitoring.stmt_snapshots
WHERE captured_at < NOW() - INTERVAL '3 days';

DELETE FROM monitoring.session_snapshots
WHERE captured_at < NOW() - INTERVAL '3 days';

DELETE FROM monitoring.lock_snapshots
WHERE captured_at < NOW() - INTERVAL '3 days';

DELETE FROM monitoring.db_snapshots
WHERE captured_at < NOW() - INTERVAL '3 days';
$$,

'postgres'

);
```

_Why 02:00: after the nightly pg_basebackup backup window and before the morning OLTP peak. The purge deletes ~216,000 rows and VACUUMs four tables - at 02:00 this completes in seconds. Adjust the schedule if your backup window is different._

### 4.4 Important: VACUUM inside pg_cron on Flexible Server

_Azure Flexible Server restricts VACUUM inside pg_cron on some versions. If the purge job fails with 'VACUUM cannot run inside a transaction block', replace the four VACUUM statements with a single call to autovacuum or remove them entirely. Autovacuum will handle the dead tuples on its next run. The DELETE rows are still removed; only the page reclamation is delayed._

Alternative if VACUUM fails inside pg_cron - register a separate job that calls VACUUM outside a transaction block:

-- Alternative: separate VACUUM job (runs right after purge at 02:05)

```sql
SELECT cron.schedule_in_database(
'vacuum_monitoring',

'31 18 * * *',

$$

VACUUM monitoring.stmt_snapshots;

VACUUM monitoring.session_snapshots;

VACUUM monitoring.lock_snapshots;

VACUUM monitoring.db_snapshots;
$$,

'pg_loadmon'

);
```

-- If VACUUM still fails, remove from purge job and rely on autovacuum.

-- Autovacuum fires automatically once dead tuple threshold is reached.

-- Check autovacuum activity: 
```sql
SELECT * FROM pg_stat_user_tables
WHERE schemaname = 'monitoring' ORDER BY n_dead_tup DESC;
```


### 4.5 Verify Purge Job is Registered

-- Confirm the job exists:

```sql
SELECT jobid, jobname, schedule, database, active
FROM cron.job
WHERE jobname = 'purge_monitoring_3day';
```

-- Check last run status (after first execution):

```sql
SELECT jobid, status, return_message, start_time, end_time
FROM cron.job_run_details
WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'purge_monitoring_3day')
ORDER BY start_time DESC LIMIT 5;
```
### 4.6 Verify Retention Is Working

Run after the first purge execution to confirm the window is correct and table sizes are stable:

-- Oldest row in each table (should be ~3 days ago):

```sql
SELECT 'stmt_snapshots' AS tbl, MIN(captured_at) AS oldest,
MAX(captured_at) AS newest, COUNT(*) AS rows
FROM monitoring.stmt_snapshots
UNION ALL
SELECT 'session_snapshots', MIN(captured_at), MAX(captured_at), COUNT(*)
FROM monitoring.session_snapshots
UNION ALL
SELECT 'lock_snapshots', MIN(captured_at), MAX(captured_at), COUNT(*)
FROM monitoring.lock_snapshots
UNION ALL
SELECT 'db_snapshots', MIN(captured_at), MAX(captured_at), COUNT(*)
FROM monitoring.db_snapshots
ORDER BY tbl;
```

-- Physical table sizes:

```sql
SELECT relname,
pg_size_pretty(pg_total_relation_size(oid)) AS total_size
FROM pg_class
WHERE relnamespace = (
SELECT oid FROM pg_namespace WHERE nspname = 'monitoring')
AND relkind = 'r'
ORDER BY pg_total_relation_size(oid) DESC;
```


_Expected steady state: oldest row ~3 days ago for all tables, total size across all four tables ~200-300 MB. If total_size keeps growing day-over-day, the purge job is not running - check cron.job_run_details for errors and confirm the DELETE grant was applied._

## Deployment Order Summary

Follow this sequence exactly. Each phase depends on the previous.

| **Step** | **Action**                                           | **Section**       | **Notes**                                                                                |
| -------- | ---------------------------------------------------- | ----------------- | ---------------------------------------------------------------------------------------- |
| **1**    | **Enable track_io_timing + verify compute_query_id** | Phase 3 § 3.1     | Reload only, no restart. Must be done before ALTER TABLE.                                |
| **2**    | **Create pg_loadmon database + all four tables**     | Phase 1 § 1.3     | Use Phase 1 definitions (include all Phase 3 columns). Skip if upgrading - go to Step 3. |
| **3**    | **ALTER TABLE (upgrades only)**                      | Phase 3 § 3.2-3.3 | Only needed if tables were created from v2.1 base. New installs skip this.               |
| **4**    | **Grant DELETE to pg_monitor_reader**                | Phase 4 § 4.2     | One-time. Required for purge job.                                                        |
| **5**    | **Register collection jobs (Jobs 1-4)**              | Phase 2 § 2.1-2.4 | Or drop + recreate if upgrading from v2.1.                                               |
| **6**    | **Register purge job**                               | Phase 4 § 4.3     | Daily at 02:00. Runs inside pg_loadmon.                                                  |
| **7**    | **Verify collection + Phase 3 columns**              | Phase 3 § 3.5     | Wait 10 minutes after jobs registered.                                                   |
| **8**    | **Verify purge after first run**                     | Phase 4 § 4.6     | Next day after 02:00 - check oldest row and table sizes.                                 |

_This document consolidates: PG_Load_Analysis_Implementation_v2.1_PaaS.docx + PG_Load_Analysis_Implementation_v2.1_PaaS_Query_id_Change.docx + Phase 4 Retention Lifecycle. Azure Flexible Server. pg_stat_statements + pg_cron. PostgreSQL 16._

```sql
SELECT cron.unschedule('collect_stmts');

SELECT cron.unschedule('collect_sessions_locks_00');

SELECT cron.unschedule('collect_sessions_locks_30');

SELECT cron.unschedule('collect_db_stats');

SELECT cron.unschedule('purge_monitoring_3day');
```
