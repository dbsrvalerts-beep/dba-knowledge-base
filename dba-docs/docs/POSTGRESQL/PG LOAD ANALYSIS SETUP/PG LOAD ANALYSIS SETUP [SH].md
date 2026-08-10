# PG LOAD ANALYSIS SETUP [SH]
**PostgreSQL Load Analysis - Self-Hosted**

pg_stat_statements + pg_stat_kcache + pg_proctab - RHEL 8 + PostgreSQL 16

_Updated: adds pg_stat_kcache (per-query real CPU), DB Head columns (blk_read_time, blk_write_time, cpu_ms_est), and query_id in session_snapshots | June 2026_

Purpose: This is the recommended self-hosted stack. It drops pg_stat_monitor (which crash-looped on prod-05) and uses three mature extensions: pg_stat_statements (per-query wall-clock + I/O), pg_stat_kcache (per-query REAL CPU and physical disk bytes, joined to pg_stat_statements on queryid), and pg_proctab (per-process CPU/memory, including background workers). With kcache, the previous limitation is gone - you now get true CPU attributed to each query, not just per application. Also folds in the DB Head's requested columns (blk_read_time, blk_write_time, cpu_ms_est) and query_id in session_snapshots.

## 0. What This Stack Delivers

With pg_stat_kcache added, every analysis question is now answerable - including the one that was previously impossible (CPU per query).

| **Question**                        | **Answer source**                                | **Granularity**               |
| ----------------------------------- | ------------------------------------------------ | ----------------------------- |
| Real CPU per QUERY (was impossible) | pg_stat_kcache exec_user_time + exec_system_time | **Per query - REAL CPU**      |
| Physical disk bytes per query       | pg_stat_kcache exec_reads / exec_writes          | **Per query - actual bytes**  |
| Real CPU per APPLICATION            | pg_proctab (by application_name)                 | Per application - cross-check |
| Wall-clock + I/O wait per query     | pg_stat_statements + blk_read/write_time         | Per query                     |
| Estimated CPU (DB Head formula)     | total_exec_time - blk_read_time - blk_write_time | Per query - estimate          |
| Memory + page faults per backend    | pg_proctab rss / pg_stat_kcache minflts/majflts  | Per process / per query       |

_pg_stat_kcache keys on (queryid, dbid, userid) - the SAME key as pg_stat_statements - so it joins cleanly into stmt_snapshots. This is why it succeeds where pg_proctab alone could not: pg_proctab keys on PID, kcache keys on query. With both, you get per-query CPU (kcache) AND per-process CPU including background workers (pg_proctab)._

_Stability: pg_stat_kcache is a thin getrusage() wrapper and is mature (part of the PoWA stack). It is far lower-risk than pg_stat_monitor. However it is still a third C extension in shared_preload_libraries on a server that previously crash-looped. Test the full three-extension set on a non-production VM for several days before production. If kcache proves stable, it makes the DB Head's cpu_ms_est estimate obsolete (kcache gives real CPU, not an estimate)._

## 1. Configuration

### 1.1 postgresql.conf

_Load order matters: pg_stat_kcache MUST appear AFTER pg_stat_statements in shared_preload_libraries - kcache depends on pg_stat_statements being initialised first. Do NOT load pg_stat_monitor._

```sql
shared_preload_libraries = 'pg_stat_statements,pg_stat_kcache,pg_proctab'

pg_stat_statements.max = 10000

pg_stat_statements.track = top

pg_stat_statements.save = on

track_activity_query_size = 4096
```

\# Required for blk_read_time / blk_write_time (DB Head columns) to be non-zero:
```sql
track_io_timing = on
```

\# Required for query_id in pg_stat_activity (session_snapshots):
```sql
compute_query_id = on
```

shared_preload_libraries needs a full restart:

```sql
sudo systemctl restart postgresql-16
```

### 1.2 Create extensions
```sql
sudo -u postgres psql -d pg_loadmon

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE EXTENSION IF NOT EXISTS pg_stat_kcache; -- depends on pg_stat_statements
CREATE EXTENSION IF NOT EXISTS pg_proctab;
```
### 1.3 Grants

```sql
GRANT pg_monitor TO pg_monitor_reader;
```sql
GRANT SELECT ON pg_stat_statements TO pg_monitor_reader;
```sql
GRANT SELECT ON pg_stat_kcache TO pg_monitor_reader;
```sql
GRANT EXECUTE ON FUNCTION pg_stat_kcache() TO pg_monitor_reader;
```sql
GRANT EXECUTE ON FUNCTION pg_proctab() TO pg_monitor_reader;
_Verify all three loaded: SELECT extname,extversion FROM pg_extension WHERE extname IN ('pg_stat_statements','pg_stat_kcache','pg_proctab'); and confirm SHOW track_io_timing; and SHOW compute_query_id; both return on._
```

## 2. Schema

### 2.1 stmt_snapshots - per-query (every 5 min)

Holds pg_stat_statements wall-clock/I/O, the DB Head columns, and the pg_stat_kcache real CPU + physical disk columns:

```sql
CREATE TABLE monitoring.stmt_snapshots (
id BIGSERIAL PRIMARY KEY,
captured_at TIMESTAMPTZ DEFAULT NOW(),
dbname TEXT,
query_id BIGINT,
query_text TEXT,
calls BIGINT,
total_exec_time DOUBLE PRECISION, -- wall-clock ms
mean_exec_time DOUBLE PRECISION,
rows BIGINT,
shared_blks_hit BIGINT,
shared_blks_read BIGINT,
temp_blks_written BIGINT,
wal_bytes BIGINT,
-- DB Head columns (pg_stat_statements + track_io_timing)

blk_read_time DOUBLE PRECISION, -- ms waiting on block reads
blk_write_time DOUBLE PRECISION, -- ms waiting on block writes
cpu_ms_est DOUBLE PRECISION, -- total_exec_time - blk_read - blk_write (ESTIMATE)
-- pg_stat_kcache columns (REAL CPU + physical disk)

cpu_user_ms DOUBLE PRECISION, -- real user CPU (ms)
cpu_sys_ms DOUBLE PRECISION, -- real kernel CPU (ms)
cpu_total_ms DOUBLE PRECISION, -- real total CPU (ms)
phys_read_bytes BIGINT, -- actual disk bytes read
phys_write_bytes BIGINT, -- actual disk bytes written
exec_minflts BIGINT, -- minor page faults
exec_majflts BIGINT -- major page faults (memory pressure)
);

CREATE INDEX ON monitoring.stmt_snapshots (captured_at);


CREATE INDEX ON monitoring.stmt_snapshots (query_id);
```

_cpu_ms_est (DB Head estimate) and cpu_total_ms (kcache real) are both kept. cpu_ms_est removes only disk I/O wait; cpu_total_ms is true CPU from getrusage. Compare them in query 4.4 - where they diverge, the query had lock/latch/sleep waits that the estimate cannot see. Once kcache is trusted, cpu_total_ms supersedes cpu_ms_est._

### 2.2 session_snapshots - active sessions (every 30 sec)

Adds query_id (DB Head request) so a sampled active session links to its stmt_snapshots row:

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
query_id BIGINT -- NEW (DB Head request)
);
CREATE INDEX ON monitoring.session_snapshots (captured_at);

CREATE INDEX ON monitoring.session_snapshots (query_id);
```


### 2.3 process_snapshots - all pg_proctab columns (every 30 sec)

Stores every pg_proctab column for per-process CPU/memory, including background workers. Key analysis columns: utime, stime (CPU ticks) and rss (memory pages).

```sql
CREATE TABLE monitoring.process_snapshots (
id BIGSERIAL PRIMARY KEY,
captured_at TIMESTAMPTZ DEFAULT NOW(),
application_name TEXT,
dbname TEXT,
pid INT, comm TEXT, fullcomm TEXT, state TEXT, ppid INT, pgrp INT,
session INT, tty_nr INT, tpgid INT, flags BIGINT,
minflt BIGINT, cminflt BIGINT, majflt BIGINT, cmajflt BIGINT,
utime BIGINT, stime BIGINT, cutime BIGINT, cstime BIGINT,
priority BIGINT, nice BIGINT, num_threads BIGINT, itrealvalue BIGINT,
starttime BIGINT, vsize BIGINT, rss BIGINT,
exit_signal INT, processor INT, rt_priority INT, policy INT,
delayacct_blkio_ticks BIGINT, uid BIGINT, username TEXT,
rchar BIGINT, wchar BIGINT, syscr BIGINT, syscw BIGINT,
reads BIGINT, writes BIGINT, cwrites BIGINT
);

CREATE INDEX ON monitoring.process_snapshots (captured_at, application_name);

CREATE INDEX ON monitoring.process_snapshots (pid);
```

_rss is in PAGES (x 4096 / 1024 = KB); vsize is bytes; utime/stime are ticks (x 10 = ms on RHEL 8). process_snapshots is the per-PROCESS view (captures background workers like checkpointer, walwriter, pg_cron launcher that have no query). pg_stat_kcache is the per-QUERY view. They are complementary._

### 2.4 lock_snapshots - lock waits (every 30 sec)

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
CREATE INDEX ON monitoring.lock_snapshots (captured_at);
```
### 2.5 db_snapshots - per-database stats (every 60 sec)

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
CREATE INDEX ON monitoring.db_snapshots (captured_at, dbname);
```



-- Grant on all five tables:

```sql
GRANT INSERT, SELECT ON ALL TABLES IN SCHEMA monitoring TO pg_monitor_reader;
GRANT USAGE, UPDATE ON ALL SEQUENCES IN SCHEMA monitoring TO pg_monitor_reader;
```
## 3. Collection Queries

### 3.1 stmt_snapshots - pg_stat_statements + pg_stat_kcache (every 5 min)

The kcache function is LEFT JOINed to pg_stat_statements on (queryid, dbid, userid). exec_user_time/exec_system_time are in SECONDS, so multiply by 1000 for ms to match total_exec_time:

```sql
INSERT INTO monitoring.stmt_snapshots (
dbname, query_id, query_text, calls, total_exec_time, mean_exec_time,
rows, shared_blks_hit, shared_blks_read, temp_blks_written, wal_bytes,

blk_read_time, blk_write_time, cpu_ms_est,

cpu_user_ms, cpu_sys_ms, cpu_total_ms,

phys_read_bytes, phys_write_bytes, exec_minflts, exec_majflts)

SELECT
d.datname,

s.queryid,

LEFT(s.query, 300),

s.calls, s.total_exec_time, s.mean_exec_time, s.rows,

s.shared_blks_hit, s.shared_blks_read, s.temp_blks_written, s.wal_bytes,

s.blk_read_time,

s.blk_write_time,

s.total_exec_time - s.blk_read_time - s.blk_write_time AS cpu_ms_est,

k.exec_user_time * 1000 AS cpu_user_ms,

k.exec_system_time * 1000 AS cpu_sys_ms,

(k.exec_user_time + k.exec_system_time) * 1000 AS cpu_total_ms,

k.exec_reads AS phys_read_bytes,

k.exec_writes AS phys_write_bytes,

k.exec_minflts, k.exec_majflts

FROM pg_stat_statements s
JOIN pg_database d ON d.oid = s.dbid

LEFT JOIN pg_stat_kcache() k ON k.queryid = s.queryid

AND k.dbid = s.dbid

AND k.userid = s.userid

AND k.top IS TRUE

WHERE s.calls > 0;
```
_k.top IS TRUE matches top-level statements (pg_stat_statements.track = top). If your kcache version errors on the top column, remove that one line - older kcache builds do not expose it. exec_reads/exec_writes are bytes from getrusage (ru_inblock/ru_oublock x 512); on some filesystems they can read 0 even with real I/O - cross-check against shared_blks_read if so._

### 3.2 session_snapshots - add query_id (every 30 sec)

```sql
INSERT INTO monitoring.session_snapshots (
pid, dbname, application_name, state,

wait_event_type, wait_event, query_start, duration_secs, query_id)


SELECT pid, datname, application_name, state,
wait_event_type, wait_event, query_start,

EXTRACT(EPOCH FROM (NOW() - query_start)),

query_id

FROM pg_stat_activity
WHERE state = 'active' AND pid <> pg_backend_pid();
```
### 3.3 process_snapshots - pg_proctab (every 30 sec)

FROM pg_proctab() LEFT JOIN pg_stat_activity so background workers (no pg_stat_activity row) are kept. Filter on the postgres OS user to capture ALL database processes:
```sql
INSERT INTO monitoring.process_snapshots (
application_name, dbname, pid, comm, fullcomm, state, ppid, pgrp,


session, tty_nr, tpgid, flags, minflt, cminflt, majflt, cmajflt,

utime, stime, cutime, cstime, priority, nice, num_threads, itrealvalue,

starttime, vsize, rss, exit_signal, processor, rt_priority, policy,

delayacct_blkio_ticks, uid, username, rchar, wchar, syscr, syscw,

reads, writes, cwrites)

SELECT
COALESCE(NULLIF(sa.application_name,''),

CASE WHEN sa.pid IS NULL THEN pt.fullcomm ELSE 'unknown' END),

sa.datname, pt.pid, pt.comm, pt.fullcomm, pt.state, pt.ppid, pt.pgrp,

pt.session, pt.tty_nr, pt.tpgid, pt.flags, pt.minflt, pt.cminflt,

pt.majflt, pt.cmajflt, pt.utime, pt.stime, pt.cutime, pt.cstime,

pt.priority, pt.nice, pt.num_threads, pt.itrealvalue, pt.starttime,

pt.vsize, pt.rss, pt.exit_signal, pt.processor, pt.rt_priority,

pt.policy, pt.delayacct_blkio_ticks, pt.uid, pt.username,

pt.rchar, pt.wchar, pt.syscr, pt.syscw, pt.reads, pt.writes, pt.cwrites

FROM pg_proctab() pt
LEFT JOIN pg_stat_activity sa ON sa.pid = pt.pid

WHERE pt.username = 'postgres';
```
### 3.4 lock_snapshots - lock waits (every 30 sec, same script as sessions)

Collected in the same 30-second script as sessions and process_snapshots:

```sql
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
```
### 3.5 db_snapshots - per-database stats (every 60 sec)

```sql
INSERT INTO monitoring.db_snapshots
(dbname, numbackends, xact_commit, xact_rollback,


blks_hit, blks_read, tup_returned, tup_fetched)


SELECT datname, numbackends, xact_commit, xact_rollback,
blks_hit, blks_read, tup_returned, tup_fetched

FROM pg_stat_database
WHERE datname NOT IN ('template0','template1','postgres','pg_loadmon');
```
_Script-to-query mapping: collect_stmts.sh runs 3.1 (5 min). collect_sessions.sh runs 3.2 + 3.3 + 3.4 together (30 sec, two cron entries for :00 and :30). collect_db.sh runs 3.5 (60 sec). The shell scripts in Section 5 contain exactly these queries._

## 4. Analysis Queries

### 4.1 Per-query REAL CPU (pg_stat_kcache) - the new headline

This is what kcache unlocks: true CPU attributed to each query shape, ranked. Previously impossible without pg_stat_monitor.
```sql
WITH ranked AS (

SELECT query_id,
MAX(query_text) AS query_text,


MAX(cpu_total_ms) AS cpu_total_ms,

MAX(cpu_user_ms) AS cpu_user_ms,

MAX(cpu_sys_ms) AS cpu_sys_ms,

MAX(total_exec_time) AS wall_ms,

MAX(calls) AS calls

FROM monitoring.stmt_snapshots
WHERE captured_at >= NOW() - INTERVAL '24 hours'
GROUP BY query_id
)

SELECT
LEFT(query_text, 90) AS query_text,

calls,

ROUND((cpu_total_ms/1000.0)::NUMERIC,1) AS cpu_sec,

ROUND((100.0*cpu_total_ms/

NULLIF(SUM(cpu_total_ms) OVER(),0))::NUMERIC,2) AS pct_cpu,

ROUND((wall_ms/1000.0)::NUMERIC,1) AS wall_sec,

ROUND((100.0*(wall_ms-cpu_total_ms)/

NULLIF(wall_ms,0))::NUMERIC,1) AS pct_wait

FROM ranked
ORDER BY cpu_total_ms DESC NULLS LAST
LIMIT 30;
```
_pct_wait here is real: wall-clock minus real CPU = all waiting (I/O + locks + sleep). Unlike cpu_ms_est, this captures lock and sleep waits too, because cpu_total_ms is true getrusage CPU. A pg_sleep query shows ~100% pct_wait and ~0 cpu_sec - correctly._

### 4.2 Per-query CPU vs I/O wait vs physical disk

Combine kcache real CPU, the DB Head I/O-wait columns, and kcache physical bytes to classify each query as CPU-bound vs I/O-bound:
```sql
SELECT
LEFT(MAX(query_text),80) AS query_text,

ROUND((MAX(cpu_total_ms)/1000.0)::NUMERIC,1) AS cpu_sec,

ROUND((MAX(blk_read_time+blk_write_time)/1000.0)::NUMERIC,1) AS io_wait_sec,

pg_size_pretty(MAX(phys_read_bytes)) AS phys_read,

MAX(exec_majflts) AS major_faults,

CASE WHEN MAX(cpu_total_ms) > MAX(blk_read_time+blk_write_time)

THEN 'CPU-bound' ELSE 'IO-bound' END AS profile

FROM monitoring.stmt_snapshots
WHERE captured_at >= NOW() - INTERVAL '24 hours'
GROUP BY query_id
ORDER BY MAX(cpu_total_ms) DESC NULLS LAST LIMIT 30;
```
### 4.3 Per-application real CPU (pg_proctab) - cross-check

pg_proctab provides the per-application view and catches background-worker CPU that has no query_id. Two levels: MAX per PID (peak of the cumulative counter), then SUM per application. ticks x 10 = ms; rss pages x 4096 / 1024 = KB.
```sql
WITH per_pid AS (
SELECT
application_name,

pid,

MAX(utime) AS pid_user_ticks, -- cumulative, take peak per PID

MAX(stime) AS pid_sys_ticks,

MAX(rss) AS pid_rss_pages

FROM monitoring.process_snapshots
WHERE captured_at >= NOW() - INTERVAL '24 hours'
GROUP BY application_name, pid
),

totals AS (

SELECT
application_name,

SUM((pid_user_ticks + pid_sys_ticks) * 10) AS cpu_ms, -- ticks*10 = ms

SUM(pid_user_ticks * 10) AS user_ms,

SUM(pid_sys_ticks * 10) AS sys_ms,

SUM(pid_rss_pages * 4096 / 1024) AS rss_kb, -- pages -> KB

COUNT(DISTINCT pid) AS pids

FROM per_pid
GROUP BY application_name
)

SELECT
application_name,

ROUND((cpu_ms/1000.0)::NUMERIC,1) AS cpu_sec,

ROUND((100.0*cpu_ms/NULLIF(SUM(cpu_ms) OVER(),0))::NUMERIC,2) AS pct_cpu,

ROUND((user_ms/1000.0)::NUMERIC,1) AS user_sec,

ROUND((sys_ms/1000.0)::NUMERIC,1) AS sys_sec,

ROUND((rss_kb/1024.0)::NUMERIC,1) AS rss_mb,

pids

FROM totals
ORDER BY pct_cpu DESC;
```
_Why two levels: pg_proctab CPU is a CUMULATIVE counter per PID. Summing utime directly across snapshots would add the same growing counter many times and over-count. MAX per PID takes each backend's peak, then SUM per application. Read against 4.1: where 4.3 shows CPU that 4.1 (per-query) cannot account for, that is background-worker CPU (checkpointer, walwriter, autovacuum, pg_cron launcher) with no query_id - exactly what pg_proctab catches and kcache cannot. For pooled backends that served many apps, 4.3 is the cross-check; 4.1 (kcache per-query) is the precise figure._

### 4.4 Estimate vs real - how good is cpu_ms_est?

Shows the DB Head's estimate beside kcache's real CPU. Large gaps reveal queries with lock/sleep waits the estimate cannot detect:
```sql
SELECT
LEFT(MAX(query_text),80) AS query_text,

ROUND((MAX(cpu_ms_est)/1000.0)::NUMERIC,1) AS est_cpu_sec,

ROUND((MAX(cpu_total_ms)/1000.0)::NUMERIC,1) AS real_cpu_sec,

ROUND((100.0*(MAX(cpu_ms_est)-MAX(cpu_total_ms))/

NULLIF(MAX(cpu_ms_est),0))::NUMERIC,1) AS est_overstate_pct

FROM monitoring.stmt_snapshots
WHERE captured_at >= NOW() - INTERVAL '24 hours'
GROUP BY query_id
ORDER BY MAX(cpu_total_ms) DESC NULLS LAST LIMIT 30;
```
_est_overstate_pct shows how much the DB Head estimate over-counts CPU for each query. For pure compute queries it is near 0 (estimate is accurate). For lock/sleep-heavy queries it is high (estimate wrongly counts the wait as CPU). This quantifies why kcache is worth having._

### 4.5 Link active sessions to statement cost (query_id join)

With query_id now in both tables, join the sampled active sessions to their real per-query CPU:
```sql
SELECT ss.query_id,
COUNT(*) AS times_caught_active,

LEFT(MAX(st.query_text),80) AS query_text,

ROUND((MAX(st.cpu_total_ms)/1000.0)::NUMERIC,1) AS real_cpu_sec

FROM monitoring.session_snapshots ss
LEFT JOIN LATERAL (


SELECT query_text, cpu_total_ms FROM monitoring.stmt_snapshots st
WHERE st.query_id = ss.query_id ORDER BY st.captured_at DESC LIMIT 1
) st ON true

WHERE ss.captured_at >= NOW() - INTERVAL '24 hours' AND ss.query_id IS NOT NULL
GROUP BY ss.query_id ORDER BY times_caught_active DESC LIMIT 30;
```
## 5. Collection Shell Scripts (RHEL 8 system cron)

Three scripts under /opt/pgmon/. Credentials via ~/.pgpass (0600), never in the scripts.

sudo mkdir -p /opt/pgmon /var/log/pgmon && sudo chown postgres:postgres /opt/pgmon /var/log/pgmon

### 5.1 /opt/pgmon/collect_stmts.sh (every 5 min)

```bash
#!/bin/bash

PSQL="psql -h localhost -U pg_monitor_reader -d pg_loadmon -v ON_ERROR_STOP=1"

$PSQL <<'SQL'

INSERT INTO monitoring.stmt_snapshots (

dbname, query_id, query_text, calls, total_exec_time, mean_exec_time,

rows, shared_blks_hit, shared_blks_read, temp_blks_written, wal_bytes,

blk_read_time, blk_write_time, cpu_ms_est,

cpu_user_ms, cpu_sys_ms, cpu_total_ms,

phys_read_bytes, phys_write_bytes, exec_minflts, exec_majflts)

SELECT d.datname, s.queryid, LEFT(s.query,300),

s.calls, s.total_exec_time, s.mean_exec_time, s.rows,

s.shared_blks_hit, s.shared_blks_read, s.temp_blks_written, s.wal_bytes,

s.blk_read_time, s.blk_write_time,

s.total_exec_time - s.blk_read_time - s.blk_write_time,

k.exec_user_time*1000, k.exec_system_time*1000,

(k.exec_user_time + k.exec_system_time)*1000,

k.exec_reads, k.exec_writes, k.exec_minflts, k.exec_majflts

FROM pg_stat_statements s

JOIN pg_database d ON d.oid = s.dbid

LEFT JOIN pg_stat_kcache() k ON k.queryid=s.queryid AND k.dbid=s.dbid

AND k.userid=s.userid AND k.top IS TRUE

WHERE s.calls > 0;

SQL
```

### 5.2 /opt/pgmon/collect_sessions.sh (every 30 sec)

```bash
#!/bin/bash

PSQL="psql -h localhost -U pg_monitor_reader -d pg_loadmon -v ON_ERROR_STOP=1"

$PSQL <<'SQL'

\-- active sessions (with query_id)

INSERT INTO monitoring.session_snapshots

(pid,dbname,application_name,state,wait_event_type,wait_event,

query_start,duration_secs,query_id)

SELECT pid,datname,application_name,state,wait_event_type,wait_event,

query_start, EXTRACT(EPOCH FROM (NOW()-query_start)), query_id

FROM pg_stat_activity WHERE state='active' AND pid<>pg_backend_pid();

\-- per-process metrics (pg_proctab, all columns)

INSERT INTO monitoring.process_snapshots (

application_name,dbname,pid,comm,fullcomm,state,ppid,pgrp,session,

tty_nr,tpgid,flags,minflt,cminflt,majflt,cmajflt,utime,stime,cutime,

cstime,priority,nice,num_threads,itrealvalue,starttime,vsize,rss,

exit_signal,processor,rt_priority,policy,delayacct_blkio_ticks,

uid,username,rchar,wchar,syscr,syscw,reads,writes,cwrites)

SELECT COALESCE(NULLIF(sa.application_name,''),

CASE WHEN sa.pid IS NULL THEN pt.fullcomm ELSE 'unknown' END),

sa.datname, pt.pid,pt.comm,pt.fullcomm,pt.state,pt.ppid,pt.pgrp,

pt.session,pt.tty_nr,pt.tpgid,pt.flags,pt.minflt,pt.cminflt,pt.majflt,

pt.cmajflt,pt.utime,pt.stime,pt.cutime,pt.cstime,pt.priority,pt.nice,

pt.num_threads,pt.itrealvalue,pt.starttime,pt.vsize,pt.rss,

pt.exit_signal,pt.processor,pt.rt_priority,pt.policy,

pt.delayacct_blkio_ticks,pt.uid,pt.username,pt.rchar,pt.wchar,

pt.syscr,pt.syscw,pt.reads,pt.writes,pt.cwrites

FROM pg_proctab() pt

LEFT JOIN pg_stat_activity sa ON sa.pid=pt.pid

WHERE pt.username='postgres';

\-- lock waits

INSERT INTO monitoring.lock_snapshots

(waiting_pid,waiting_app,blocking_pid,blocking_app,

lock_type,relation,wait_secs)

SELECT w.pid,w.application_name,b.pid,b.application_name,

lw.locktype,c.relname,EXTRACT(EPOCH FROM (NOW()-w.query_start))

FROM pg_stat_activity w

JOIN pg_locks lw ON lw.pid=w.pid AND NOT lw.granted

JOIN pg_locks lb ON lb.locktype=lw.locktype AND lb.granted

AND lb.relation IS NOT DISTINCT FROM lw.relation

JOIN pg_stat_activity b ON b.pid=lb.pid

LEFT JOIN pg_class c ON c.oid=lw.relation

WHERE w.wait_event_type='Lock';

SQL
```

Run collect_sessions.sh twice per minute for 30-second sampling (cron entry at :00 plus a sleep-30 entry), as in section 5.4.

### 5.3 /opt/pgmon/collect_db.sh (every 60 sec)

```bash
#!/bin/bash

PSQL="psql -h localhost -U pg_monitor_reader -d pg_loadmon -v ON_ERROR_STOP=1"

$PSQL <<'SQL'

INSERT INTO monitoring.db_snapshots

(dbname,numbackends,xact_commit,xact_rollback,

blks_hit,blks_read,tup_returned,tup_fetched)

SELECT datname,numbackends,xact_commit,xact_rollback,

blks_hit,blks_read,tup_returned,tup_fetched

FROM pg_stat_database

WHERE datname NOT IN ('template0','template1','postgres','pg_loadmon');

SQL
```

### 5.4 Crontab + permissions

sudo chmod +x /opt/pgmon/*.sh

sudo crontab -u postgres -e
```sql
*/5 * * * * /opt/pgmon/collect_stmts.sh >> /var/log/pgmon/stmts.log 2>&1

* * * * * /opt/pgmon/collect_sessions.sh >> /var/log/pgmon/sessions.log 2>&1

* * * * * sleep 30; /opt/pgmon/collect_sessions.sh >> /var/log/pgmon/sessions.log 2>&1

* * * * * /opt/pgmon/collect_db.sh >> /var/log/pgmon/db.log 2>&1
```
\# ~/.pgpass for postgres user (0600): localhost:5432:pg_loadmon:pg_monitor_reader:PASSWORD

## 6. Retention Lifecycle - 3-Day Rolling Window

All five monitoring tables grow continuously. Without a purge job, the pg_loadmon database will exhaust disk space within days. The policy is: keep exactly 3 days of data, delete everything older. A daily purge cron job (run at 02:00) handles all five tables in a single psql session. VACUUM reclaims the freed pages immediately after deletion.

### 6.1 Data Growth Estimates (3-day retention)

| **Table**                   | **Rows/day** | **MB/day**  | **3-day cap** | **Collection frequency**                    |
| --------------------------- | ------------ | ----------- | ------------- | ------------------------------------------- |
| stmt_snapshots              | ~144,000     | ~62 MB      | **~186 MB**   | Every 5 min (288 snapshots x ~500 queries)  |
| process_snapshots           | ~86,400      | ~21 MB      | **~63 MB**    | Every 30 sec (2,880 snapshots x ~30 PIDs)   |
| session_snapshots           | ~57,600      | ~11 MB      | **~33 MB**    | Every 30 sec (active sessions only)         |
| db_snapshots                | ~14,400      | ~1 MB       | **~3 MB**     | Every 60 sec (1,440 snapshots x ~10 dbs)    |
| lock_snapshots              | negligible   | <1 MB       | **<3 MB**     | Every 30 sec (only rows during lock events) |
| **TOTAL (raw + index ~2x)** | **~302,400** | **~190 MB** | **~570 MB**   | Stable ceiling after purge job is running   |

_process_snapshots is the largest table because it stores every pg_proctab column for every postgres PID, twice per minute. If disk is very constrained, consider reducing the capture frequency from every 30 sec to every 60 sec - halves the process_snapshots volume. The analysis queries are unaffected; they work with any sampling granularity._

### 6.2 Purge Script - /opt/pgmon/purge_monitoring.sh

Deletes rows older than 3 days from all five tables in a single psql session, then runs VACUUM to reclaim pages. Run daily at 02:00 when the server is quietest.

```bash
#!/bin/bash

\# /opt/pgmon/purge_monitoring.sh - delete data older than 3 days, then VACUUM

\# Runs as postgres user via cron. Credentials from ~/.pgpass (0600).

PSQL="psql -h localhost -U pg_monitor_reader -d pg_loadmon -v ON_ERROR_STOP=1"

CUTOFF="NOW() - INTERVAL '3 days'"

$PSQL <<'SQL'

\-- ── 1. DELETE old rows (all five tables) ──────────────────────────────

DELETE FROM monitoring.stmt_snapshots WHERE captured_at < NOW() - INTERVAL '3 days';

DELETE FROM monitoring.session_snapshots WHERE captured_at < NOW() - INTERVAL '3 days';

DELETE FROM monitoring.process_snapshots WHERE captured_at < NOW() - INTERVAL '3 days';

DELETE FROM monitoring.lock_snapshots WHERE captured_at < NOW() - INTERVAL '3 days';

DELETE FROM monitoring.db_snapshots WHERE captured_at < NOW() - INTERVAL '3 days';

\-- ── 2. VACUUM to reclaim freed pages immediately ──────────────────────

\-- VACUUM marks dead tuples as reusable. VACUUM FULL would compact the

\-- table file but requires an AccessExclusiveLock - avoid on production.

VACUUM monitoring.stmt_snapshots;

VACUUM monitoring.session_snapshots;

VACUUM monitoring.process_snapshots;

VACUUM monitoring.lock_snapshots;

VACUUM monitoring.db_snapshots;

SQL
```

_pg_monitor_reader requires DELETE privilege to run the purge. Add it once: GRANT DELETE ON ALL TABLES IN SCHEMA monitoring TO pg_monitor_reader; - this is in addition to the INSERT, SELECT grants from Section 2. Without DELETE, the purge script will fail silently if ON_ERROR_STOP is not set._

### 6.3 Crontab Entry for Purge

Add this line to the postgres user crontab (sudo crontab -u postgres -e), alongside the existing collection entries from Section 5.4:

\# --- existing collection jobs (Section 5.4) ---

```sql
*/5 * * * * /opt/pgmon/collect_stmts.sh >> /var/log/pgmon/stmts.log 2>&1

* * * * * /opt/pgmon/collect_sessions.sh >> /var/log/pgmon/sessions.log 2>&1

* * * * * sleep 30; /opt/pgmon/collect_sessions.sh >> /var/log/pgmon/sessions.log 2>&1

* * * * * /opt/pgmon/collect_db.sh >> /var/log/pgmon/db.log 2>&1

\# --- NEW: daily retention purge (3-day window) ---

**0 2 * * * /opt/pgmon/purge_monitoring.sh >> /var/log/pgmon/purge.log 2>&1**
```

_The purge runs at 02:00 - after pg_basebackup completes and before the morning OLTP peak. It deletes roughly 300,000 rows and runs VACUUM on five tables. At 02:00 the server is near-idle so the DELETE + VACUUM complete in seconds without impacting any active sessions. The purge.log captures row counts (DELETE returns the count in psql verbose output) - tail -f /var/log/pgmon/purge.log to confirm it ran._

### 6.4 One-Time Permission Grant (run once as superuser)

The existing pg_monitor_reader role has INSERT and SELECT on all monitoring tables (Section 2). DELETE must be added once before the purge script will work:

-- Run as postgres superuser once:

```sql
GRANT DELETE ON ALL TABLES IN SCHEMA monitoring TO pg_monitor_reader;
```
### 6.5 Verify Retention Is Working

Run after the first purge execution to confirm the window is correct and sizes are stable:

-- Check oldest row in each table (should be ~3 days ago):

```sql
SELECT 'stmt_snapshots' AS tbl, MIN(captured_at) AS oldest, MAX(captured_at) AS newest, COUNT(*) AS rows FROM monitoring.stmt_snapshots
UNION ALL
SELECT 'session_snapshots' AS tbl, MIN(captured_at), MAX(captured_at), COUNT(*) FROM monitoring.session_snapshots
UNION ALL
SELECT 'process_snapshots' AS tbl, MIN(captured_at), MAX(captured_at), COUNT(*) FROM monitoring.process_snapshots
UNION ALL
SELECT 'lock_snapshots' AS tbl, MIN(captured_at), MAX(captured_at), COUNT(*) FROM monitoring.lock_snapshots
UNION ALL
SELECT 'db_snapshots' AS tbl, MIN(captured_at), MAX(captured_at), COUNT(*) FROM monitoring.db_snapshots
ORDER BY tbl;
```

-- Check physical table sizes on disk:

```sql
SELECT relname, pg_size_pretty(pg_total_relation_size(oid)) AS total_size
FROM pg_class WHERE relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'monitoring')
AND relkind = 'r' ORDER BY pg_total_relation_size(oid) DESC;
```

_Expected output after steady state: oldest row ~3 days ago for all tables, row counts ~302,000 total, total_size across all five tables ~500-600 MB including indexes. If total_size keeps growing day-over-day, the purge job is not running - check /var/log/pgmon/purge.log for errors._

## 7. Reconciling With Absolute CPU (Azure VM Metrics)

kcache and pg_proctab give RELATIVE attribution (per query / per process). The Azure VM 'Percentage CPU (Max)' metric gives ABSOLUTE utilisation. Read them together.

| **Source**                    | **What it tells you**                                                                           |
| ----------------------------- | ----------------------------------------------------------------------------------------------- |
| Azure VM Percentage CPU (Max) | Absolute whole-VM utilisation (e.g. daily sawtooth to ~100%). The urgency + right-sizing input. |
| pg_stat_kcache (query 4.1)    | Real CPU per query - which query to optimise. The precise what-to-fix.                          |
| pg_proctab (query 4.3)        | Real CPU per application + background workers - cross-check and non-query CPU.                  |
| cpu_ms_est (DB Head)          | Estimate from wall-clock minus I/O wait - fallback if kcache ever unavailable.                  |

_If the Azure VM peaks near 100% daily, use kcache query 4.1 to find the top real-CPU queries and optimise or offload them. cpu_total_ms (real) is now the authoritative figure; cpu_ms_est is retained only as a fallback and a teaching comparison._

_Stack: pg_stat_statements + pg_stat_kcache + pg_proctab. kcache gives per-query REAL CPU and physical disk (joined on queryid) - removing the prior 'no per-query CPU' limitation. DB Head columns (blk_read_time, blk_write_time, cpu_ms_est) and session query_id are included. Test all three extensions non-production first given the prod-05 crash history. track_io_timing and compute_query_id must be ON._

**What is pg_stat_kcache?**

pg_stat_kcache is a PostgreSQL extension that tracks kernel-level statistics, including CPU usage, disk I/O, and block-level access.

Standard monitoring tools like pg_stat_statements provide valuable insights about execution counts and total time, but they don't tell you how much CPU or I/O resources each query consumes.

This is where the PostgreSQL extension pg_stat_kcache comes into play. It bridges the gap between PostgreSQL query statistics and operating system-level resource usage, giving you a granular view of how queries impact your system

It answers questions such as:

Which databases or queries are consuming the most CPU?

Which queries cause heavy disk reads or writes?

Are queries I/O-bound or CPU-bound?

How pg_stat_kcache Works

pg_stat_kcache hooks into PostgreSQL's statistics coxlector and uses Linux kernel counters to measure query-level resource usage. It tracks:

CPU Time

exec_user_time - Time spent in user mode

exec_system_time - Time spent in kernel mode

Disk I/O

exec_reads / exec_reads_blks - Reads in rows/blocks

exec_writes / exec_writes_blks - Writes in rows/blocks

Other Metrics

Swaps, signals, messages, and page faults

These metrics are stored in views: pg_stat_kcache (database-level aggregation) and pg_stat_kcache_detail (query-level details).

**what is pg_proctab?**

pg_proctab is a PostgreSQL extension that reads data from the Linux /proc filesystem and exposes it through SQL functions. It allows PostgreSQL to query operating system-level statistics such as CPU usage, memory usage, disk I/O, system load, and per-process information.

|                               | pg_proctab         | pg_stat_kcache              |
| ----------------------------- | ------------------ | --------------------------- |
| Data source                   | /proc/&lt;pid&gt;  | getrusage() syscall         |
| Granularity                   | Per backend/PID    | Per query                   |
| CPU stats                     | Yes (per process)  | Yes (per query, cumulative) |
| Memory stats                  | Yes (RSS, virtual) | No                          |
| Physical I/O                  | No                 | Yes (reads/writes in bytes) |
| Works with pg_stat_statements | No                 | Yes (same queryid)          |
| Real-time                     | Yes                | Cumulative since last reset |
| OS dependency                 | Linux only (/proc) | Linux only                  |
