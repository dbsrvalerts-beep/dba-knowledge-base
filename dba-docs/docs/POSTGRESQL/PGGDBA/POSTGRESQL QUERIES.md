**PostgreSQL**

**DBA Query Reference Guide**

_Daily Monitoring, Performance & Maintenance Queries_

DB Services Team

Ginesys

Compiled: July 2026

# Table of Contents

[Table of Contents 1](#_Toc233819272)

[1\. Server & Cluster Overview 1](#_Toc233819273)

[Server Start Time / Uptime 1](#_Toc233819274)

[Uptime Duration 1](#_Toc233819275)

[Database Count (Total & Prod) 1](#_Toc233819276)

[Total Cluster Size 1](#_Toc233819277)

[Individual Database Sizes 1](#_Toc233819278)

[Total Cluster Connections (Used vs Max) 1](#_Toc233819279)

[Connections by State 1](#_Toc233819280)

[Connections by User / Database / Client 1](#_Toc233819281)

[User Connections Ratio (% of max_connections used) 1](#_Toc233819282)

[Check Key Configuration Parameters 1](#_Toc233819283)

[List Installed Extensions 1](#_Toc233819284)

[2\. Session & Query Monitoring 1](#_Toc233819285)

[Long Running Sessions (> 1 minute) 1](#_Toc233819286)

[Long Running Queries (> 2 minutes) 1](#_Toc233819287)

[Long Running Queries (> 9 seconds) 1](#_Toc233819288)

[Active Connections Excluding Current Query 1](#_Toc233819289)

[Sessions Waiting on an Event 1](#_Toc233819290)

[Session Count by Wait Event Type 1](#_Toc233819291)

[Idle-in-Transaction / Aborted Sessions 1](#_Toc233819292)

[Ginview Sessions Running > 30 Minutes (per database) 1](#_Toc233819293)

[Blocking Sessions - Detailed (lock/relation view) 1](#_Toc233819294)

[Identify Root Blocking Sessions (simple) 1](#_Toc233819295)

[Waiting Connections Count for a Lock 1](#_Toc233819296)

[3\. Killing / Terminating Sessions 1](#_Toc233819297)

[Cancel a Running Query (graceful) 1](#_Toc233819298)

[Terminate a Specific Session 1](#_Toc233819299)

[Kill Only Root Blocking Sessions (Best Practice) 1](#_Toc233819300)

[Kill All Idle Sessions 1](#_Toc233819301)

[Kill All Idle-in-Transaction Sessions 1](#_Toc233819302)

[Kill Sessions Idle Beyond a Time Threshold 1](#_Toc233819303)

[Kill All Active Connections to a Database 1](#_Toc233819304)

[Kill All Connections to a Database Except Current Session 1](#_Toc233819305)

[Terminate All Connections Across All Databases (Except Current) 1](#_Toc233819306)

[Generate Cancel Statements for Active / Idle-in-Transaction Sessions 1](#_Toc233819307)

[4\. Cache & Buffer Analysis 1](#_Toc233819308)

[Cluster-wide Heap Cache Hit Ratio 1](#_Toc233819309)

[Cache Hit Ratio per Database 1](#_Toc233819310)

[Index Cache Hit Ratio 1](#_Toc233819311)

[Overall Cache Hit Ratio (target > 90%) 1](#_Toc233819312)

[Shared Buffer Usage per Database (block count) 1](#_Toc233819313)

[Shared Buffer Status (dirty / clean / empty, in MB) 1](#_Toc233819314)

[Top Tables Cached in Current Database (by buffer count) 1](#_Toc233819315)

[How Much of a Table/Index is Buffered (% of relation & shared_buffers) 1](#_Toc233819316)

[Buffer Usage-Count Distribution (hotness of pages) 1](#_Toc233819317)

[% of Relation Cached and % Hot (usagecount > 3) 1](#_Toc233819318)

[Pre-warm a Table into Shared Buffers (pg_prewarm) 1](#_Toc233819319)

[Check Blocks of a Specific Table in Buffer Cache 1](#_Toc233819320)

[Dirty Page / Background Writer Stats 1](#_Toc233819321)

[Requested vs Timed Checkpoints (health check) 1](#_Toc233819322)

[5\. Autovacuum & Table Bloat 1](#_Toc233819323)

[Autovacuum & Track-Counts Enabled? 1](#_Toc233819324)

[Autovacuum-Related Configuration Parameters 1](#_Toc233819325)

[Dead/Live Tuple Counts & Last Vacuum/Analyze Times 1](#_Toc233819326)

[Tables With ≥ 50% Dead Tuples (bloat candidates) 1](#_Toc233819327)

[Tables Currently Qualifying for Autovacuum 1](#_Toc233819328)

[Check Progress of a Running VACUUM 1](#_Toc233819329)

[Run VACUUM Manually 1](#_Toc233819330)

[Table-Level Autovacuum Overrides 1](#_Toc233819331)

[Transaction ID Wraparound Monitoring 1](#_Toc233819332)

[Database Age (Transaction ID Age per Database) 1](#_Toc233819333)

[Object Age per Database (relfrozenxid) 1](#_Toc233819334)

[Row Insert / Update / Delete Distribution per Table 1](#_Toc233819335)

[HOT Update Percentage per Table (should be close to 100%) 1](#_Toc233819336)

[6\. Index Monitoring 1](#_Toc233819337)

[List All Indexes in a Schema 1](#_Toc233819338)

[Indexes with Primary/Unique Key Flags 1](#_Toc233819339)

[Get Indexes with Column Names 1](#_Toc233819340)

[Unused Indexes (idx_scan = 0) 1](#_Toc233819341)

[Rarely-Used Indexes (idx_scan < 100) 1](#_Toc233819342)

[Duplicate Indexes 1](#_Toc233819343)

[Index Leaf Fragmentation ≥ 40% (Bloat Check) 1](#_Toc233819344)

[Index Usage % vs Sequential Scans 1](#_Toc233819345)

[Index Scan % per Table (alternate) 1](#_Toc233819346)

[Detect Tables Possibly Missing an Index 1](#_Toc233819347)

[Average Rows Read per Sequential Scan (potential missing index) 1](#_Toc233819348)

[Average Tuples Read per Index Scan 1](#_Toc233819349)

[How Much Index Data is in Cache 1](#_Toc233819350)

[7\. Object, Table & Schema Sizing 1](#_Toc233819351)

[Table Size Excluding Indexes (per database) 1](#_Toc233819352)

[Table Size Including Indexes (per database) 1](#_Toc233819353)

[Single Table Size (excl./incl. index) 1](#_Toc233819354)

[Top Table Sizes with Index Breakdown 1](#_Toc233819355)

[Object Sizes with TOAST Info 1](#_Toc233819356)

[Object Size - All Objects, Simplified 1](#_Toc233819357)

[Schema Size (% of Total Database) 1](#_Toc233819358)

[Object Counts - Tables 1](#_Toc233819359)

[Object Counts - Primary Keys 1](#_Toc233819360)

[Object Counts - Views 1](#_Toc233819361)

[Object Counts - Triggers 1](#_Toc233819362)

[Object Counts - Sequences 1](#_Toc233819363)

[Object Counts - Functions 1](#_Toc233819364)

[Useful Sizing Functions - Quick Reference 1](#_Toc233819365)

[8\. Query Performance (pg_stat_statements) 1](#_Toc233819366)

[Top 5 Queries by Mean Execution Time 1](#_Toc233819367)

[Top 5 Queries by Total Execution Time 1](#_Toc233819368)

[Top 10 Queries by Total Time with % CPU Share 1](#_Toc233819369)

[Queries with Highest I/O Wait Time 1](#_Toc233819370)

[Top Time-Consuming Queries (full breakdown) 1](#_Toc233819371)

[Queries with High Memory / Shared Buffer Usage 1](#_Toc233819372)

[Queries Doing the Most Buffer Writes 1](#_Toc233819373)

[Queries with the Highest Block Read Time 1](#_Toc233819374)

[Average Statement Execution Time (cluster-wide) 1](#_Toc233819375)

[Reset pg_stat_statements 1](#_Toc233819376)

[9\. Replication & WAL 1](#_Toc233819377)

[Replication Status 1](#_Toc233819378)

[Replication Lag in Seconds 1](#_Toc233819379)

[Replication Slot Information 1](#_Toc233819380)

[Logical Replication Slot Lag Detail 1](#_Toc233819381)

[WAL Directory Size (MB) 1](#_Toc233819382)

[WAL Archiver Status 1](#_Toc233819383)

[WAL Archiving Gap (current vs last archived) 1](#_Toc233819384)

[10\. pg_cron Jobs 1](#_Toc233819385)

[Cron Job Counts per Database 1](#_Toc233819386)

[Today's Cron Job Run Status per Database 1](#_Toc233819387)

[11\. Prepared Transactions 1](#_Toc233819388)

[List Prepared/Orphaned Transactions 1](#_Toc233819389)

[Find Locks Held by Prepared Transactions 1](#_Toc233819390)

[Resolve a Prepared Transaction 1](#_Toc233819391)

[12\. Maintenance Commands 1](#_Toc233819392)

[Reindex a Database 1](#_Toc233819393)

[Reload Configuration (without restart) 1](#_Toc233819394)

[Query Store Views (if enabled) 1](#_Toc233819395)

[13\. psql Meta-Command Quick Reference 1](#_Toc233819396)

[Common \\-Commands 1](#_Toc233819397)

[14\. PGGDBA - Historical Trend Queries 1](#_Toc233819398)

[Historical Database Size (for a given day) 1](#_Toc233819399)

[Database Growth Comparison (two dates) 1](#_Toc233819400)

[Top Size-Consuming Segments (historical, > 1000 MB) 1](#_Toc233819401)

[Object Growth Comparison (two dates) 1](#_Toc233819402)

# 1\. Server & Cluster Overview

## Server Start Time / Uptime

SELECT pg_postmaster_start_time()::TIMESTAMP(0) AS server_start_time;

## Uptime Duration

SELECT date_trunc('second', current_timestamp - pg_postmaster_start_time()) AS "Uptime"

FROM pg_postmaster_start_time();

## Database Count (Total & Prod)

WITH db_counts AS (

SELECT

COUNT(\*) AS "TOTAL_DB",

SUM(CASE WHEN datname ILIKE '%prod%' AND datname NOT LIKE 'ZZZ%' THEN 1 ELSE 0 END) AS "PROD_DB"

FROM pg_database

WHERE datistemplate = false

AND datname NOT ILIKE 'ZZZ%'

AND datname NOT ILIKE '%prodx'

)

SELECT \* FROM db_counts;

## Total Cluster Size

SELECT

SUM(size_gb) AS "Total Size (GB)"

FROM

(SELECT

pg_database.datname AS database,

pg_database_size(pg_database.datname) / (1024.0 \* 1024 \* 1024) AS size_gb

FROM pg_database

WHERE datistemplate = false

AND pg_database_size(pg_database.datname) > 0) AS subquery;

## Individual Database Sizes

SELECT

pg_database.datname AS database,

pg_size_pretty(pg_database_size(pg_database.datname)) AS size

FROM pg_database

WHERE datistemplate = false

AND pg_database_size(pg_database.datname) > 0

ORDER BY pg_database_size(pg_database.datname)::numeric DESC;

## Total Cluster Connections (Used vs Max)

SELECT

(SELECT setting AS max_connections FROM pg_settings WHERE name = 'max_connections') AS max_connections,

count(\*) AS used_connections

FROM pg_stat_activity;

## Connections by State

SELECT

COALESCE(state, 'background') AS state,

COUNT(\*)

FROM pg_stat_activity

GROUP BY state

ORDER BY 1;

## Connections by User / Database / Client

SELECT client_addr, usename, datname, count(\*)

FROM pg_stat_activity

GROUP BY 1,2,3

ORDER BY 4 DESC;

## User Connections Ratio (% of max_connections used)

SELECT count(\*) \* 100 / (SELECT current_setting('max_connections')::int)

FROM pg_stat_activity;

## Check Key Configuration Parameters

SELECT \* FROM pg_settings

WHERE name IN (

'shared_buffers','work_mem','maintenance_work_mem','temp_buffers','max_connections',

'max_wal_size','min_wal_size','search_path','timezone','max_prepared_transaction',

'autovacuum_max_workers','autovacuum_vacuum_scale_factor','autovacuum_vacuum_insert_scale_factor',

'autovacuum_vacuum_cost_delay','max_parallel_workers_per_gather','track_activity_query_size',

'cron.max_running_jobs','wal_level','max_replication_slots','max_wal_senders',

'sync_replication_slots','max_worker_processes'

);

## List Installed Extensions

SELECT \* FROM pg_available_extensions WHERE installed_version IS NOT NULL;

# 2\. Session & Query Monitoring

## Long Running Sessions (> 1 minute)

SELECT pid, usename, datname, application_name, now() - xact_start AS duration, query_id, query

FROM pg_stat_activity

WHERE pid <> pg_backend_pid()

AND state IN ('idle in transaction', 'active')

AND now() - xact_start > INTERVAL '1 minute'

ORDER BY duration DESC;

## Long Running Queries (> 2 minutes)

SELECT now() - query_start AS runtime, usename, datname, state, query

FROM pg_stat_activity

WHERE now() - query_start > '2 minutes'::interval

ORDER BY runtime DESC;

## Long Running Queries (> 9 seconds)

SELECT now() - query_start AS runtime, usename, datname, state, query

FROM pg_stat_activity

WHERE now() - query_start > '9 seconds'::interval

ORDER BY runtime DESC;

## Active Connections Excluding Current Query

SELECT age(clock_timestamp(), query_start), usename, datname, query

FROM pg_stat_activity

WHERE state != 'idle'

AND query NOT ILIKE '%pg_stat_activity%'

ORDER BY age DESC;

## Sessions Waiting on an Event

SELECT usename, datname, query, wait_event_type, wait_event

FROM pg_stat_activity

WHERE state != 'idle'

AND wait_event IS NOT NULL;

## Session Count by Wait Event Type

SELECT

COALESCE(wait_event_type, 'None') AS wait_type,

COUNT(\*) AS session_count

FROM pg_stat_activity

WHERE backend_type = 'client backend'

GROUP BY wait_type;

## Idle-in-Transaction / Aborted Sessions

SELECT \* FROM pg_stat_activity

WHERE state IN ('idle in transaction', 'idle in transaction (aborted)');

## Ginview Sessions Running > 30 Minutes (per database)

SELECT DISTINCT

current_timestamp AS logdate,

a.pid, a.usename, a.datname, a.application_name,

n.nspname AS schema_name, a.state,

TO_CHAR(now() - a.xact_start, 'HH24:MI') AS duration,

a.query_id,

regexp_replace(a.query, '\\s+', ' ', 'g') AS query

FROM pg_stat_activity a

JOIN pg_locks l ON a.pid = l.pid

JOIN pg_class c ON l.relation = c.oid

JOIN pg_namespace n ON c.relnamespace = n.oid

JOIN pg_database d ON a.datname = d.datname

WHERE a.state = 'active'

AND a.application_name = 'w3wp.exe'

AND a.query_start < NOW() - INTERVAL '30 minutes'

AND a.query LIKE '%ginview.%'

AND a.datname = current_database()

AND n.nspname = 'ginview'

ORDER BY a.query_start;

## Blocking Sessions - Detailed (lock/relation view)

SELECT

d.datname AS database_name,

a.pid AS blocked_pid,

l.mode AS lock_mode,

l.locktype,

l.relation::regclass AS locked_relation,

bl.pid AS blocking_pid

FROM pg_stat_activity AS a

JOIN pg_locks AS l ON a.pid = l.pid

JOIN pg_locks AS bl ON l.locktype = bl.locktype

AND l.relation = bl.relation AND l.pid != bl.pid

JOIN pg_database AS d ON a.datid = d.oid

WHERE l.mode <> 'AccessShareLock'

AND bl.mode <> 'AccessShareLock'

ORDER BY d.datname, a.pid;

## Identify Root Blocking Sessions (simple)

## Step 1: Identify Blocking Sessions

SELECT pid, usename, state, wait_event, query  
FROM pg_stat_activity  
WHERE pid IN (  
SELECT unnest(pg_blocking_pids(pid))  
FROM pg_stat_activity  
);  
<br/>Step 2: Kill Only Blocking Sessions (Best Practice)  
SELECT pg_terminate_backend(pid)  
FROM pg_stat_activity  
WHERE pid IN (  
SELECT unnest(pg_blocking_pids(pid))  
FROM pg_stat_activity);

## Waiting Connections Count for a Lock

SELECT count(DISTINCT pid) FROM pg_locks WHERE granted = false;

# 3\. Killing / Terminating Sessions

## Cancel a Running Query (graceful)

SELECT pg_cancel_backend(&lt;pid&gt;);

\-- Example: SELECT pg_cancel_backend(27735);

## Terminate a Specific Session

SELECT pg_terminate_backend(&lt;pid&gt;);

## Kill Only Root Blocking Sessions (Best Practice)

SELECT pg_terminate_backend(pid)

FROM pg_stat_activity

WHERE pid IN (

SELECT unnest(pg_blocking_pids(pid))

FROM pg_stat_activity

);

## Kill All Idle Sessions

SELECT pg_terminate_backend(pg_stat_activity.pid)

FROM pg_stat_activity

WHERE pid <> pg_backend_pid()

AND state = 'idle';

## Kill All Idle-in-Transaction Sessions

SELECT pg_terminate_backend(pid)

FROM pg_stat_activity

WHERE datname = '&lt;db_name&gt;'

AND state = 'idle in transaction';

## Kill Sessions Idle Beyond a Time Threshold

SELECT pg_terminate_backend(pid)

FROM pg_stat_activity

WHERE datname = '&lt;db_name&gt;'

AND pid <> pg_backend_pid()

AND state IN ('idle', 'idle in transaction', 'idle in transaction (aborted)', 'disabled')

AND state_change < current_timestamp - INTERVAL '15 minutes';

## Kill All Active Connections to a Database

SELECT pg_terminate_backend(pid)

FROM pg_stat_activity

WHERE datname = '&lt;db_name&gt;'

AND leader_pid IS NULL;

## Kill All Connections to a Database Except Current Session

SELECT pg_terminate_backend(pid)

FROM pg_stat_activity

WHERE datname = '&lt;db_name&gt;'

AND pid != pg_backend_pid()

AND leader_pid IS NULL;

## Terminate All Connections Across All Databases (Except Current)

SELECT pg_terminate_backend(pid)

FROM pg_stat_activity

WHERE pid != pg_backend_pid()

AND datname IS NOT NULL

AND leader_pid IS NULL;

## Generate Cancel Statements for Active / Idle-in-Transaction Sessions

SELECT 'SELECT pg_cancel_backend(' || pid || ');'

FROM pg_stat_activity

WHERE pid <> pg_backend_pid()

AND state IN ('idle in transaction', 'active');

# 4\. Cache & Buffer Analysis

## Cluster-wide Heap Cache Hit Ratio

SELECT

SUM(heap_blks_read) AS "Heap Read",

SUM(heap_blks_hit) AS "Heap Hit",

ROUND((SUM(heap_blks_hit) \* 100.0) / NULLIF((SUM(heap_blks_hit) + SUM(heap_blks_read)), 0), 2) AS "Hit Ratio Percentage"

FROM pg_statio_user_tables;

## Cache Hit Ratio per Database

SELECT datname AS "Database", blks_hit, blks_read,

round(blks_hit / (blks_hit + blks_read + 0.00001) \* 100, 2) AS "cache hit ratio"

FROM pg_stat_database

WHERE datname IS NOT NULL

ORDER BY 4 ASC;

## Index Cache Hit Ratio

SELECT

sum(idx_blks_read) AS idx_read,

sum(idx_blks_hit) AS idx_hit,

(sum(idx_blks_hit) - sum(idx_blks_read)) / sum(idx_blks_hit) AS ratio

FROM pg_statio_user_indexes;

## Overall Cache Hit Ratio (target > 90%)

SELECT sum(blks_hit) \* 100 / sum(blks_hit + blks_read) AS hit_ratio

FROM pg_stat_database;

## Shared Buffer Usage per Database (block count)

SELECT

CASE WHEN c.reldatabase IS NULL THEN ''

WHEN c.reldatabase = 0 THEN ''

ELSE d.datname END AS database,

count(\*) AS cached_blocks

FROM pg_buffercache AS c

LEFT JOIN pg_database AS d ON c.reldatabase = d.oid

GROUP BY d.datname, c.reldatabase

ORDER BY 2 DESC;

## Shared Buffer Status (dirty / clean / empty, in MB)

SELECT buffer_status, round(sum(count) \* 8 / 1024) AS "Size(MB)"

FROM (

SELECT CASE isdirty WHEN true THEN 'dirty' WHEN false THEN 'clean' ELSE 'empty' END AS buffer_status,

count(\*) AS count

FROM pg_buffercache

GROUP BY buffer_status

UNION ALL

SELECT \* FROM (VALUES ('dirty', 0), ('clean', 0), ('empty', 0)) AS tab2(buffer_status, count)

) tab1

GROUP BY buffer_status;

## Top Tables Cached in Current Database (by buffer count)

SELECT n.nspname, c.relname, count(\*) AS buffers

FROM pg_buffercache b

JOIN pg_class c ON b.relfilenode = pg_relation_filenode(c.oid)

AND b.reldatabase IN (0, (SELECT oid FROM pg_database WHERE datname = current_database()))

JOIN pg_namespace n ON n.oid = c.relnamespace

GROUP BY n.nspname, c.relname

ORDER BY 3 DESC

LIMIT 10;

## How Much of a Table/Index is Buffered (% of relation & shared_buffers)

SELECT

c.relname,

pg_size_pretty(count(\*) \* 8192) AS buffered,

round(100.0 \* count(\*) / (SELECT setting FROM pg_settings WHERE name = 'shared_buffers')::integer, 1) AS buffers_percent,

round(100.0 \* count(\*) \* 8192 / pg_table_size(c.oid), 1) AS percent_of_relation

FROM pg_class c

INNER JOIN pg_buffercache b ON b.relfilenode = c.relfilenode

INNER JOIN pg_database d ON (b.reldatabase = d.oid AND d.datname = current_database())

GROUP BY c.oid, c.relname

ORDER BY 3 DESC

LIMIT 10;

## Buffer Usage-Count Distribution (hotness of pages)

SELECT usagecount, count(\*)

FROM pg_buffercache

GROUP BY usagecount

ORDER BY usagecount;

## % of Relation Cached and % Hot (usagecount > 3)

SELECT c.relname,

count(\*) blocks,

round(100.0 \* 8192 \* count(\*) / pg_table_size(c.oid)) AS "% of rel",

round(100.0 \* 8192 \* count(\*) FILTER (WHERE b.usagecount > 3) / pg_table_size(c.oid)) AS "% hot"

FROM pg_buffercache b

JOIN pg_class c ON pg_relation_filenode(c.oid) = b.relfilenode

WHERE b.reldatabase IN (0, (SELECT oid FROM pg_database WHERE datname = current_database()))

AND b.usagecount IS NOT NULL

GROUP BY c.relname, c.oid

ORDER BY 2 DESC

LIMIT 10;

## Pre-warm a Table into Shared Buffers (pg_prewarm)

\-- Check page count first

SELECT oid::regclass AS tbl, relpages FROM pg_class WHERE relname = '&lt;table_name&gt;';

\-- Load table into cache

SELECT \* FROM pg_prewarm('&lt;table_name&gt;');

## Check Blocks of a Specific Table in Buffer Cache

SELECT count(\*) FROM pg_buffercache

WHERE relfilenode = pg_relation_filenode('&lt;table_name&gt;'::regclass);

## Dirty Page / Background Writer Stats

SELECT buffers_clean, maxwritten_clean, buffers_backend_fsync

FROM pg_stat_bgwriter;

\-- maxwritten_clean and buffers_backend_fsync should ideally be 0

## Requested vs Timed Checkpoints (health check)

SELECT 'bad' AS checkpoints

FROM pg_stat_bgwriter

WHERE checkpoints_req > checkpoints_timed;

# 5\. Autovacuum & Table Bloat

## Autovacuum & Track-Counts Enabled?

SELECT name, setting FROM pg_settings WHERE name IN ('autovacuum', 'track_counts');

## Autovacuum-Related Configuration Parameters

SELECT \* FROM pg_settings WHERE category LIKE 'Autovacuum%';

## Dead/Live Tuple Counts & Last Vacuum/Analyze Times

SELECT schemaname, relname, n_live_tup, n_dead_tup,

round(n_dead_tup::float / n_live_tup::float \* 100) AS dead_pct,

autovacuum_count, last_vacuum, last_analyze, last_autovacuum, last_autoanalyze

FROM pg_stat_all_tables

WHERE n_live_tup > 0

ORDER BY n_dead_tup DESC;

## Tables With ≥ 50% Dead Tuples (bloat candidates)

SELECT \* FROM (

SELECT schemaname, relname, n_live_tup, n_dead_tup,

round(n_dead_tup::float / n_live_tup::float \* 100) dead_pct,

autovacuum_count, last_vacuum, last_analyze, last_autovacuum, last_autoanalyze

FROM pg_stat_all_tables

WHERE n_live_tup > 10

ORDER BY n_dead_tup DESC

) sub

WHERE dead_pct >= 50

ORDER BY dead_pct DESC;

## Tables Currently Qualifying for Autovacuum

SELECT \*,

n_dead_tup > av_threshold AS av_needed,

CASE WHEN reltuples > 0 THEN round(100.0 \* n_dead_tup / reltuples) ELSE 0 END AS pct_dead

FROM (

SELECT N.nspname, C.relname,

pg_stat_get_tuples_inserted(C.oid) AS n_tup_ins,

pg_stat_get_tuples_updated(C.oid) AS n_tup_upd,

pg_stat_get_tuples_deleted(C.oid) AS n_tup_del,

pg_stat_get_live_tuples(C.oid) AS n_live_tup,

pg_stat_get_dead_tuples(C.oid) AS n_dead_tup,

C.reltuples AS reltuples,

round(current_setting('autovacuum_vacuum_threshold')::INTEGER

\+ current_setting('autovacuum_vacuum_scale_factor')::NUMERIC \* C.reltuples) AS av_threshold,

date_trunc('minute', greatest(pg_stat_get_last_vacuum_time(C.oid), pg_stat_get_last_autovacuum_time(C.oid))) AS last_vacuum,

date_trunc('minute', greatest(pg_stat_get_last_analyze_time(C.oid), pg_stat_get_last_autoanalyze_time(C.oid))) AS last_analyze

FROM pg_class C

LEFT JOIN pg_namespace N ON (N.oid = C.relnamespace)

WHERE C.relkind IN ('r', 't')

AND N.nspname NOT IN ('pg_catalog', 'information_schema')

AND N.nspname !~ '^pg_toast'

) AS av

ORDER BY av_needed DESC, n_dead_tup DESC;

## Check Progress of a Running VACUUM

SELECT \* FROM pg_stat_progress_vacuum;

## Run VACUUM Manually

VACUUM (VERBOSE, ANALYZE);

## Table-Level Autovacuum Overrides

SELECT reloptions FROM pg_class WHERE relname = '&lt;table_name&gt;';

## Transaction ID Wraparound Monitoring

WITH max_age AS (

SELECT 2000000000 AS max_old_xid, setting AS autovacuum_freeze_max_age

FROM pg_catalog.pg_settings

WHERE name = 'autovacuum_freeze_max_age'

), per_database_stats AS (

SELECT datname, m.max_old_xid::int, m.autovacuum_freeze_max_age::int,

age(d.datfrozenxid) AS oldest_current_xid

FROM pg_catalog.pg_database d

JOIN max_age m ON (true)

WHERE d.datallowconn

)

SELECT max(oldest_current_xid) AS oldest_current_xid,

max(ROUND(100 \* (oldest_current_xid / max_old_xid::float))) AS percent_towards_wraparound,

max(ROUND(100 \* (oldest_current_xid / autovacuum_freeze_max_age::float))) AS percent_towards_emergency_autovac

FROM per_database_stats;

## Database Age (Transaction ID Age per Database)

SELECT datname, age(datfrozenxid), current_setting('autovacuum_freeze_max_age')

FROM pg_database

ORDER BY 2 DESC;

## Object Age per Database (relfrozenxid)

SELECT c.oid::regclass, age(c.relfrozenxid), pg_size_pretty(pg_total_relation_size(c.oid))

FROM pg_class c

JOIN pg_namespace n ON c.relnamespace = n.oid

WHERE relkind IN ('r', 't', 'm')

AND n.nspname NOT IN ('pg_toast')

ORDER BY 2 DESC;

## Row Insert / Update / Delete Distribution per Table

SELECT relname,

cast(n_tup_ins AS numeric) / (n_tup_ins + n_tup_upd + n_tup_del) AS ins_pct,

cast(n_tup_upd AS numeric) / (n_tup_ins + n_tup_upd + n_tup_del) AS upd_pct,

cast(n_tup_del AS numeric) / (n_tup_ins + n_tup_upd + n_tup_del) AS del_pct

FROM pg_stat_user_tables

ORDER BY relname;

## HOT Update Percentage per Table (should be close to 100%)

SELECT relname, n_tup_upd, n_tup_hot_upd,

cast(n_tup_hot_upd AS numeric) / n_tup_upd AS hot_pct

FROM pg_stat_user_tables

WHERE n_tup_upd > 0

ORDER BY hot_pct;

# 6\. Index Monitoring

## List All Indexes in a Schema

SELECT tablename AS "TableName", indexname AS "Index Name", indexdef AS "Index script"

FROM pg_indexes

WHERE schemaname = '&lt;schema_name&gt;'

ORDER BY tablename, indexname;

## Indexes with Primary/Unique Key Flags

SELECT

c.relnamespace::regnamespace AS schema_name,

c.relname AS table_name,

i.indexrelid::regclass AS index_name,

i.indisprimary AS is_pk,

i.indisunique AS is_unique

FROM pg_index i

JOIN pg_class c ON c.oid = i.indrelid

WHERE c.relname = '&lt;table_name&gt;';

## Get Indexes with Column Names

SELECT t.relname AS table_name, i.relname AS index_name,

string_agg(a.attname, ',') AS column_name

FROM pg_class t, pg_class i, pg_index ix, pg_attribute a

WHERE t.oid = ix.indrelid

AND i.oid = ix.indexrelid

AND a.attrelid = t.oid

AND a.attnum = ANY(ix.indkey)

AND t.relkind = 'r'

AND t.relname NOT LIKE 'pg_%'

GROUP BY t.relname, i.relname

ORDER BY t.relname, i.relname;

## Unused Indexes (idx_scan = 0)

SELECT \* FROM pg_stat_all_indexes WHERE idx_scan = 0 AND schemaname = '&lt;schema_name&gt;';

## Rarely-Used Indexes (idx_scan < 100)

SELECT

relname AS table_name, indexrelname AS index_name,

pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,

idx_scan AS index_scan_count

FROM pg_stat_user_indexes

WHERE idx_scan < 100

ORDER BY index_scan_count ASC, pg_relation_size(indexrelid) DESC;

## Duplicate Indexes

SELECT ni.nspname || '.' || ct.relname AS "table",

ci.relname AS "dup index",

pg_get_indexdef(i.indexrelid) AS "dup index definition",

i.indkey AS "dup index attributes",

cii.relname AS "encompassing index",

pg_get_indexdef(ii.indexrelid) AS "encompassing index definition",

ii.indkey AS "enc index attributes"

FROM pg_index i

JOIN pg_class ct ON i.indrelid = ct.oid

JOIN pg_class ci ON i.indexrelid = ci.oid

JOIN pg_namespace ni ON ci.relnamespace = ni.oid

JOIN pg_index ii ON ii.indrelid = i.indrelid

AND ii.indexrelid != i.indexrelid

AND (array_to_string(ii.indkey, ' ') || ' ') LIKE (array_to_string(i.indkey, ' ') || ' %')

AND (array_to_string(ii.indcollation, ' ') || ' ') LIKE (array_to_string(i.indcollation, ' ') || ' %')

AND (array_to_string(ii.indclass, ' ') || ' ') LIKE (array_to_string(i.indclass, ' ') || ' %')

AND (array_to_string(ii.indoption, ' ') || ' ') LIKE (array_to_string(i.indoption, ' ') || ' %')

AND NOT (ii.indkey::integer\[\] @> ARRAY\[0\])

AND NOT (i.indkey::integer\[\] @> ARRAY\[0\])

AND i.indpred IS NULL AND ii.indpred IS NULL

AND CASE WHEN i.indisunique THEN ii.indisunique

AND array_to_string(ii.indkey, ' ') = array_to_string(i.indkey, ' ') ELSE true END

JOIN pg_class ctii ON ii.indrelid = ctii.oid

JOIN pg_class cii ON ii.indexrelid = cii.oid

WHERE ct.relname NOT LIKE 'pg_%'

AND NOT i.indisprimary

ORDER BY 1, 2, 3;

## Index Leaf Fragmentation ≥ 40% (Bloat Check)

SELECT \* FROM (

SELECT

current_database() AS database_name,

i.indexname, i.tablename,

pg_size_pretty(pg_relation_size(c.oid)) AS index_size,

pg_relation_size(c.oid) AS index_size_bytes,

COALESCE(NULLIF((SELECT avg_leaf_density FROM pgstatindex(c.oid)), 'NaN'::float), 0) AS avg_leaf_density,

COALESCE(NULLIF((SELECT leaf_fragmentation FROM pgstatindex(c.oid)), 'NaN'::float), 0) AS leaf_fragmentation,

COALESCE(s.idx_scan, 0) AS index_scan_count,

'REINDEX INDEX ' || i.indexname || ';' AS statement

FROM pg_indexes i

JOIN pg_class c ON c.relname = i.indexname

JOIN pg_namespace n ON n.oid = c.relnamespace

LEFT JOIN pg_stat_user_indexes s ON s.indexrelid = c.oid

WHERE n.nspname = '&lt;schema_name&gt;'

) sub

WHERE leaf_fragmentation >= 40

AND index_scan_count >= 100

ORDER BY leaf_fragmentation DESC, index_size_bytes DESC;

## Index Usage % vs Sequential Scans

SELECT relname, 100 \* idx_scan / (seq_scan + idx_scan) AS percent_of_times_index_used,

n_live_tup AS rows_in_table

FROM pg_stat_user_tables

WHERE (seq_scan + idx_scan) > 0

ORDER BY n_live_tup DESC;

## Index Scan % per Table (alternate)

SELECT schemaname, relname, seq_scan, idx_scan,

cast(idx_scan AS numeric) / (idx_scan + seq_scan) AS idx_scan_pct

FROM pg_stat_user_tables

WHERE (idx_scan + seq_scan) > 0

ORDER BY idx_scan_pct;

## Detect Tables Possibly Missing an Index

SELECT relname, seq_scan - idx_scan AS too_much_seq,

CASE WHEN seq_scan - idx_scan > 0 THEN 'Missing/Ineff Index' ELSE 'OK' END,

pg_relation_size(relname::regclass) AS rel_size, seq_scan, idx_scan

FROM pg_stat_all_tables

WHERE schemaname = '&lt;schema_name&gt;'

AND pg_relation_size(relname::regclass) > 80000

ORDER BY too_much_seq DESC;

## Average Rows Read per Sequential Scan (potential missing index)

SELECT schemaname, relname, seq_scan, seq_tup_read,

seq_tup_read / seq_scan AS avg, idx_scan

FROM pg_stat_user_tables

WHERE seq_scan > 0

ORDER BY seq_tup_read DESC

LIMIT 25;

## Average Tuples Read per Index Scan

SELECT indexrelname,

cast(idx_tup_read AS numeric) / idx_scan AS avg_tuples,

idx_scan, idx_tup_read

FROM pg_stat_user_indexes

WHERE idx_scan > 0;

## How Much Index Data is in Cache

SELECT sum(idx_blks_read) AS idx_read, sum(idx_blks_hit) AS idx_hit

FROM pg_statio_user_indexes;

# 7\. Object, Table & Schema Sizing

## Table Size Excluding Indexes (per database)

SELECT table_name, pg_size_pretty(pg_relation_size(quote_ident(table_name))) AS table_size

FROM information_schema.tables

WHERE table_schema NOT IN ('pg_catalog', 'information_schema')

ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC;

## Table Size Including Indexes (per database)

SELECT table_name, pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS table_size

FROM information_schema.tables

WHERE table_schema NOT IN ('pg_catalog', 'information_schema')

ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC;

## Single Table Size (excl./incl. index)

SELECT pg_size_pretty(pg_relation_size('&lt;schema&gt;.&lt;table&gt;')) AS table_size_excl_index;

SELECT pg_size_pretty(pg_total_relation_size('&lt;schema&gt;.&lt;table&gt;')) AS table_size_incl_index;

## Top Table Sizes with Index Breakdown

SELECT relname,

pg_size_pretty(pg_total_relation_size(relname::regclass)) AS full_size,

pg_size_pretty(pg_relation_size(relname::regclass)) AS table_size,

pg_size_pretty(pg_total_relation_size(relname::regclass) - pg_relation_size(relname::regclass)) AS index_size

FROM pg_stat_user_tables

ORDER BY pg_total_relation_size(relname::regclass) DESC

LIMIT 10;

## Object Sizes with TOAST Info

WITH toast_map AS (

SELECT r.oid AS parent_oid, r.relname AS parent_table, r.relnamespace AS parent_schema_oid,

t.oid AS toast_oid, t.relname AS toast_table, i.relname AS toast_index

FROM pg_class r

JOIN pg_class t ON t.oid = r.reltoastrelid

JOIN pg_index d ON d.indrelid = t.oid

JOIN pg_class i ON i.oid = d.indexrelid

)

SELECT

current_timestamp AS logdate,

current_database() AS "Database",

n.nspname AS "Schema",

c.relname AS "Object Name",

CASE c.relkind

WHEN 'r' THEN 'table' WHEN 'i' THEN 'index' WHEN 'S' THEN 'sequence'

WHEN 'v' THEN 'view' WHEN 'm' THEN 'materialized view' WHEN 'c' THEN 'composite type'

WHEN 't' THEN 'TOAST table' WHEN 'f' THEN 'foreign table' ELSE 'other'

END AS "Object Type",

tm.parent_table AS "Parent Table",

pg_size_pretty(pg_total_relation_size(c.oid)) AS "Total Size",

ROUND(pg_total_relation_size(c.oid) / (1024.0 \* 1024), 2) AS "Total Size (MB)",

tm.toast_table AS "TOAST Table",

tm.toast_index AS "TOAST Index"

FROM pg_class c

JOIN pg_namespace n ON c.relnamespace = n.oid

LEFT JOIN toast_map tm ON tm.toast_oid = c.oid

ORDER BY pg_total_relation_size(c.oid) DESC;

## Object Size - All Objects, Simplified

SELECT

pg_namespace.nspname AS "Schema", pg_class.relname AS "Object Name",

CASE relkind

WHEN 'r' THEN 'table' WHEN 'i' THEN 'index' WHEN 'S' THEN 'sequence'

WHEN 'v' THEN 'view' WHEN 'm' THEN 'materialized view' WHEN 'c' THEN 'composite type'

WHEN 't' THEN 'TOAST table' WHEN 'f' THEN 'foreign table' ELSE 'other'

END AS "Object Type",

pg_size_pretty(pg_total_relation_size(pg_class.oid)) AS "Total Size"

FROM pg_catalog.pg_class

INNER JOIN pg_catalog.pg_namespace ON pg_class.relnamespace = pg_namespace.oid

WHERE relname NOT LIKE 'pg_%'

AND relkind <> 'd'

ORDER BY pg_total_relation_size(pg_class.oid) DESC;

## Schema Size (% of Total Database)

SELECT schemaname,

pg_size_pretty(sum(table_size)::bigint) AS schema_size,

(sum(table_size) / pg_database_size(current_database())) \* 100 AS percentage_of_total_db

FROM (

SELECT pg_catalog.pg_namespace.nspname AS schemaname,

pg_relation_size(pg_catalog.pg_class.oid) AS table_size

FROM pg_catalog.pg_class

JOIN pg_catalog.pg_namespace ON relnamespace = pg_catalog.pg_namespace.oid

) t

GROUP BY schemaname

ORDER BY 3 DESC;

## Object Counts - Tables

SELECT table_name

FROM information_schema.tables

WHERE table_schema IN ('main', 'ginarchive', 'ginview', 'gateway')

AND table_type IN ('FOREIGN', 'BASE TABLE')

ORDER BY table_name;

## Object Counts - Primary Keys

SELECT c.table_schema, c.table_name, c.constraint_name

FROM information_schema.table_constraints c

WHERE c.constraint_type = 'PRIMARY KEY'

AND c.table_schema IN ('main', 'ginview', 'ginarchive', 'gateway')

ORDER BY c.table_name;

## Object Counts - Views

SELECT table_name

FROM information_schema.views

WHERE table_schema IN ('main', 'ginarchive', 'gateway', 'ginview')

ORDER BY table_name;

## Object Counts - Triggers

SELECT trigger_name, event_manipulation AS event, event_object_table AS table_name,

action_statement AS trigger_body, action_timing AS trigger_timing

FROM information_schema.triggers

WHERE trigger_schema IN ('main', 'ginarchive', 'ginview', 'gateway')

ORDER BY trigger_name;

## Object Counts - Sequences

SELECT sequence_name

FROM information_schema.sequences

WHERE sequence_schema IN ('main', 'ginview', 'gateway', 'ginarchive')

ORDER BY sequence_name;

## Object Counts - Functions

SELECT routine_name

FROM information_schema.routines

WHERE routine_type = 'FUNCTION'

AND routine_schema IN ('main', 'ginview', 'gateway', 'ginarchive');

## Useful Sizing Functions - Quick Reference

\-- pg_size_pretty() formats byte sizes as human readable

\-- pg_relation_size() size of a table/index (no TOAST/index)

\-- pg_total_relation_size() total size incl. indexes and TOAST

\-- pg_database_size() size of a database

\-- pg_indexes_size() total size of all indexes on a table

\-- pg_tablespace_size() size of a tablespace

\-- pg_column_size() size of a value of a specific column/type

# 8\. Query Performance (pg_stat_statements)

## Top 5 Queries by Mean Execution Time

SELECT userid::regrole, dbid, mean_exec_time, query

FROM pg_stat_statements

ORDER BY mean_exec_time DESC

LIMIT 5;

## Top 5 Queries by Total Execution Time

SELECT userid::regrole, dbid, query

FROM pg_stat_statements

ORDER BY total_exec_time DESC

LIMIT 5;

## Top 10 Queries by Total Time with % CPU Share

SELECT substring(query, 1, 200) AS query,

round((100 \* total_exec_time / sum(total_exec_time) OVER ())::numeric, 2) AS percent,

round(total_exec_time::numeric, 2) AS total,

calls,

round(mean_exec_time::numeric, 2) AS mean

FROM pg_stat_statements

ORDER BY total_exec_time DESC

LIMIT 10;

## Queries with Highest I/O Wait Time

SELECT userid::regrole, dbid, query, queryid, mean_exec_time / 1000 AS mean_time_seconds

FROM pg_stat_statements

ORDER BY (blk_read_time + blk_write_time) DESC

LIMIT 10;

## Top Time-Consuming Queries (full breakdown)

SELECT userid::regrole, dbid, query, calls,

total_exec_time / 1000 AS total_time_seconds,

min_exec_time / 1000 AS min_time_seconds,

max_exec_time / 1000 AS max_time_seconds,

mean_exec_time / 1000 AS mean_time_seconds

FROM pg_stat_statements

ORDER BY mean_exec_time DESC

LIMIT 10;

## Queries with High Memory / Shared Buffer Usage

SELECT userid::regrole, dbid, queryid, query

FROM pg_stat_statements

ORDER BY (shared_blks_hit + shared_blks_dirtied) DESC

LIMIT 10;

## Queries Doing the Most Buffer Writes

SELECT query, shared_blks_dirtied

FROM pg_stat_statements

WHERE shared_blks_dirtied > 0

ORDER BY 2 DESC;

## Queries with the Highest Block Read Time

SELECT \* FROM pg_stat_statements

WHERE blk_read_time <> 0

ORDER BY blk_read_time DESC;

## Average Statement Execution Time (cluster-wide)

SELECT (sum(total_exec_time) / sum(calls))::numeric(6,3)

FROM pg_stat_statements;

## Reset pg_stat_statements

SELECT pg_stat_statements_reset();

SELECT count(\*) FROM pg_stat_statements;

# 9\. Replication & WAL

## Replication Status

SELECT \* FROM pg_stat_replication;

## Replication Lag in Seconds

SELECT ROUND(EXTRACT(EPOCH FROM replay_lag)) AS lag_seconds

FROM pg_stat_replication

WHERE application_name = 'walreceiver';

## Replication Slot Information

SELECT \* FROM pg_replication_slots;

## Logical Replication Slot Lag Detail

SELECT

s.slot_name, s.active,

ROUND(pg_wal_lsn_diff(pg_current_wal_lsn(), s.restart_lsn) / 1048576.0, 2) || ' MB' AS slot_lag_size,

pg_wal_lsn_diff(pg_current_wal_lsn(), s.restart_lsn) AS slot_lag_bytes,

ROUND(pg_wal_lsn_diff(pg_current_wal_lsn(), s.confirmed_flush_lsn) / 1048576.0, 2) || ' MB' AS consumer_lag_size,

pg_wal_lsn_diff(pg_current_wal_lsn(), s.confirmed_flush_lsn) AS consumer_lag_bytes,

s.slot_type, s.database, r.replay_lag, r.write_lag, r.flush_lag

FROM pg_replication_slots s

LEFT JOIN pg_stat_replication r ON s.active_pid = r.pid

WHERE s.slot_type = 'logical'

ORDER BY slot_lag_bytes DESC NULLS LAST;

## WAL Directory Size (MB)

SELECT (sum(size))::BIGINT / 1024 / 1024 AS wal_size_mb FROM pg_ls_waldir();

## WAL Archiver Status

SELECT \* FROM pg_stat_archiver;

## WAL Archiving Gap (current vs last archived)

SELECT pg_walfile_name(pg_current_wal_lsn()), last_archived_wal, last_failed_wal,

('x' || substring(pg_walfile_name(pg_current_wal_lsn()), 9, 8))::bit(32)::int \* 256

\+ ('x' || substring(pg_walfile_name(pg_current_wal_lsn()), 17))::bit(32)::int

\- ('x' || substring(last_archived_wal, 9, 8))::bit(32)::int \* 256

\- ('x' || substring(last_archived_wal, 17))::bit(32)::int AS diff

FROM pg_stat_archiver;

# 10\. pg_cron Jobs

## Cron Job Counts per Database

SELECT database, count(jobid) FROM cron.job GROUP BY database;

## Today's Cron Job Run Status per Database

SELECT database, status, count(status)

FROM cron.job_run_details

WHERE end_time::DATE = CURRENT_DATE::DATE

GROUP BY database, status;

# 11\. Prepared Transactions

## List Prepared/Orphaned Transactions

SELECT gid, prepared, owner, database, transaction

FROM pg_prepared_xacts

ORDER BY age(transaction) DESC;

## Find Locks Held by Prepared Transactions

SELECT px.gid, px.owner, px.prepared, l.locktype, l.mode, l.granted, c.relname AS object_name

FROM pg_prepared_xacts px

JOIN pg_locks l ON px.transaction = l.transactionid

LEFT JOIN pg_class c ON l.relation = c.oid;

## Resolve a Prepared Transaction

COMMIT PREPARED '&lt;gid&gt;';

\-- or

ROLLBACK PREPARED '&lt;gid&gt;';

# 12\. Maintenance Commands

## Reindex a Database

REINDEX (VERBOSE) DATABASE &lt;database_name&gt;;

## Reload Configuration (without restart)

SELECT pg_reload_conf();

## Query Store Views (if enabled)

SELECT \* FROM query_store.qs_view;

SELECT \* FROM query_store.pgms_wait_sampling_view;

SELECT \* FROM query_store.query_texts_view;

SELECT \* FROM query_store.query_plans_view;

# 13\. psql Meta-Command Quick Reference

## Common \\-Commands

\\c dbname Switch connection to a database

\\l / \\l+ List databases (with extra info)

\\dt List tables

\\d table_name Describe a table

\\dn List schemas

\\df List functions

\\dv List views

\\du List users/roles

\\ds List sequences

\\g Execute previous command

\\s Command history

\\s filename Save command history to file

\\? Help on psql commands

\\timing Toggle query execution timing

\\e Edit statement in external editor

\\ef Edit function in external editor

\\a Toggle aligned/non-aligned output

\\H Toggle HTML output format

\\conninfo Show current connection info

\\db List tablespaces

\\x Toggle expanded display

\\q Quit psql

\\! cls Clear terminal (Windows)

\\! clear Clear terminal (Linux)

\\! df -h Run an OS-level command (e.g. disk usage)

# 14\. PGGDBA - Historical Trend Queries

## Historical Database Size (for a given day)

SELECT INSTANCE_NAME, LOGDATE, DATABASE, SIZE_GB AS SIZE

FROM DATABASESIZE_INFORMATION

WHERE LOGDATE::date = CURRENT_DATE::date

AND DATABASE LIKE '%-PROD'

AND DATABASE NOT LIKE 'ZZZ%'

AND instance_name = '&lt;instance_name&gt;'

ORDER BY SIZE_GB DESC;

## Database Growth Comparison (two dates)

SELECT

t."Instance_Name", t.database,

MAX(t."NEWDATE") AS "NEWDATE", round(SUM(t.newsize) / 1024, 2) AS newsize,

MAX(t."OLDDATE") AS "OLDDATE", round(SUM(t.oldsize) / 1024, 2) AS oldsize,

round(SUM(t.newsize - t.oldsize) / 1024, 2) AS diff

FROM (

SELECT n.instance_name AS "Instance_Name", n.database,

n.logdate::date AS "NEWDATE", NULL::date AS "OLDDATE",

COALESCE(n.size_mb, 0) AS newsize, 0 AS oldsize

FROM public.databasesize_information AS n

WHERE n.logdate::date = '&lt;new_date&gt;' AND n.instance_name = '&lt;instance_name&gt;'

UNION ALL

SELECT o.instance_name, o.database,

NULL::date AS "NEWDATE", o.logdate::date AS "OLDDATE",

0 AS newsize, COALESCE(o.size_mb, 0) AS oldsize

FROM public.databasesize_information AS o

WHERE o.logdate::date = '&lt;old_date&gt;' AND o.instance_name = '&lt;instance_name&gt;'

) t

WHERE t.database LIKE '&lt;database_name&gt;'

GROUP BY t.database, t."Instance_Name"

HAVING SUM(t.newsize - t.oldsize) <> 0

ORDER BY diff DESC;

## Top Size-Consuming Segments (historical, > 1000 MB)

SELECT instance_name, logdate, database_name, schema_name, object_name, object_type, object_size, size_mb

FROM public.object_segment_selfhosted4

WHERE logdate::date = '&lt;log_date&gt;'

AND size_mb > 1000

ORDER BY size_mb DESC;

## Object Growth Comparison (two dates)

SELECT

t."Instance_Name", t."database_name", t."object_name",

MAX(t."NEWDATE") AS "NEWDATE", SUM(t.newsize) AS newsize,

MAX(t."OLDDATE") AS "OLDDATE", SUM(t.oldsize) AS oldsize,

SUM(t.newsize - t.oldsize) AS diff

FROM (

SELECT n.instance_name AS "Instance_Name", n.database_name, n.object_name,

n.logdate::date AS "NEWDATE", NULL::date AS "OLDDATE",

COALESCE(n.size_mb, 0) AS newsize, 0 AS oldsize

FROM public.object_segment_edb1 AS n

WHERE n.logdate::date = '&lt;new_date&gt;' AND n.instance_name = '&lt;instance_name&gt;'

UNION ALL

SELECT o.instance_name, o.database_name, o.object_name,

NULL::date AS "NEWDATE", o.logdate::date AS "OLDDATE",

0 AS newsize, COALESCE(o.size_mb, 0) AS oldsize

FROM public.object_segment_edb1 AS o

WHERE o.logdate::date = '&lt;old_date&gt;' AND o.instance_name = '&lt;instance_name&gt;'

) t

WHERE t.database_name LIKE '&lt;database_name&gt;'

GROUP BY t.object_name, t."Instance_Name", t."database_name"

HAVING SUM(t.newsize - t.oldsize) <> 0

ORDER BY diff DESC;