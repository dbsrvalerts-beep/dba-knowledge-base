# GoldenGate -> HEARTBEAT Monitoring

Sep 30, 2026 · @mighty master of 7 galaxies

Two changes to the GINESYS → REPDB replication: stop replicating trigger DDL, and add heartbeat tables for end-to-end lag monitoring. Both are applied with a single EXT1/REP1 restart.

## Current setup

| Item | Value |
| --- | --- |
| GoldenGate | 19.1.0.0.4, classic |
| Database | Oracle 12.1.0.2 SE |
| GG home | /u02/Oracle/GG (host prd) |
| Processes | EXT1 (source GINESYS) → REP1 (target REPDB), unidirectional |
| GG schema | goldengate |

Current `dirprm/ext1.prm`:

```
EXTRACT ext1
USERID goldengate@GINESYS, PASSWORD <pwd>
EXTTRAIL ./dirdat/aa
DDL INCLUDE MAPPED
TABLE RSBR.INVITEM;
```

`DDL INCLUDE MAPPED` replicates DDL for every mapped object, including `CREATE TRIGGER` on those tables. There is no lag history today, so lag incidents such as 29 Sep 2026 (13:20–13:45 IST) cannot be traced after the fact.

## Change 1: Exclude trigger DDL

Add `EXCLUDE OBJTYPE 'TRIGGER'` so triggers created on source tables are no longer created on the target. Replicated triggers fire again when REP1 applies rows, which duplicates work and slows apply.

New `dirprm/ext1.prm`:

```
EXTRACT ext1
USERIDALIAS gg_src
EXTTRAIL ./dirdat/aa
DDL INCLUDE MAPPED, EXCLUDE OBJTYPE 'TRIGGER'
TABLE RSBR.INVITEM;
```

Notes:

- All other DDL on mapped objects (ALTER TABLE, CREATE INDEX) still replicates.
- After the restart, check the DDL clause was accepted: `VIEW REPORT ext1` and look for the DDL line with no warnings.
- Recommended in the same change: replace the plain-text password with a credential store alias (`ADD CREDENTIALSTORE`, then `ALTER CREDENTIALSTORE ADD USER goldengate@GINESYS PASSWORD <pwd> ALIAS gg_src`).
- Triggers that already exist on the target are not removed. List them with `SELECT owner, trigger_name, table_name, status FROM dba_triggers WHERE owner = 'RSBRREP';` and decide separately.

Apply together with Change 2; the restart steps are at the end of Change 2.

## Change 2: Heartbeat tables

A scheduler job on the source updates a heartbeat row every 60 s; it flows through EXT1 and REP1, and the target records end-to-end lag with 30 days of history.

Prerequisite: `GLOBALS` in the GG home must set the schema, otherwise `ADD HEARTBEATTABLE` fails with OGG-14036.

```
GGSCI> EDIT PARAMS ./GLOBALS
```

Add the line `GGSCHEMA goldengate`, then save and close the editor. The file must be `GLOBALS` in the GG home (/u02/Oracle/GG), uppercase, no extension.

Exit and reopen GGSCI after creating it.

1. Source (GINESYS): full heartbeat, including the 60 s update job.

   ```
   GGSCI> DBLOGIN USERID goldengate@GINESYS, PASSWORD <pwd>
   GGSCI> ADD HEARTBEATTABLE
   GGSCI> INFO HEARTBEATTABLE
   ```
2. Target (REPDB): receive-only, since replication is one-way.

   ```
   GGSCI> DBLOGIN USERID goldengate@<target_tns>, PASSWORD <pwd>
   GGSCI> ADD HEARTBEATTABLE, TARGETONLY
   GGSCI> INFO HEARTBEATTABLE
   ```
3. Restart once to apply Change 1 and Change 2. Both processes resume from their checkpoints.

   ```
   GGSCI> STOP EXTRACT ext1
   GGSCI> STOP REPLICAT rep1
   GGSCI> START EXTRACT ext1
   GGSCI> START REPLICAT rep1
   GGSCI> INFO ALL
   ```
4. Verify on the target after 2–3 minutes: `SELECT * FROM goldengate.gg_lag;` returns one row, path `EXT1 ==> REP1`, lag of a few seconds.

Defaults: frequency 60 s, retention 30 days, purge daily. Heartbeat timestamps are stored in UTC (IST = UTC + 5:30).

## Monitoring queries

Lag is measured and stored on the target, so most checks run there. The source only needs its heartbeat job checked.

| # | Check | Run on |
| --- | --- | --- |
| 1 | Process status and checkpoint lag | GGSCI |
| 2 | Current lag and status | Target (REPDB) |
| 3 | Lag history for a time window | Target (REPDB) |
| 4 | Extract vs replicat lag | Target (REPDB) |
| 5 | Daily lag summary | Target (REPDB) |
| 6 | Heartbeat job health | Source (GINESYS) |

**1. Process status (GGSCI)**

```
GGSCI> INFO ALL
GGSCI> DBLOGIN USERID goldengate@<target_tns>, PASSWORD <pwd>
GGSCI> LAG REPLICAT rep1
```

**2. Current lag and status (Target)**

```sql
SELECT incoming_path,
       ROUND(incoming_lag)           lag_sec,
       ROUND(incoming_heartbeat_age) hb_age_sec,
       CASE WHEN incoming_heartbeat_age > 300 THEN 'STALLED'
            WHEN incoming_lag > 900           THEN 'CRITICAL'
            WHEN incoming_lag > 300           THEN 'WARNING'
            ELSE 'OK' END status
FROM   goldengate.gg_lag;
```

`lag_sec` = source commit to target apply. `hb_age_sec` = time since the last heartbeat; if it keeps growing, replication is stalled.

**3. Lag history for a time window (Target)**

Enter the window in IST; the query converts to UTC.

```sql
SELECT TO_CHAR(FROM_TZ(heartbeat_received_ts,'UTC') AT TIME ZONE 'Asia/Kolkata','DD-MON HH24:MI:SS') received_ist,
       ROUND(incoming_lag,1) lag_sec
FROM   goldengate.gg_lag_history
WHERE  heartbeat_received_ts BETWEEN TIMESTAMP '2026-10-01 13:00:00' - INTERVAL '0 05:30:00' DAY TO SECOND
                                 AND TIMESTAMP '2026-10-01 14:00:00' - INTERVAL '0 05:30:00' DAY TO SECOND
ORDER  BY heartbeat_received_ts;
```

**4. Extract vs replicat lag (Target)**

Shows which side caused the lag in the same window.

```sql
SELECT TO_CHAR(FROM_TZ(heartbeat_received_ts,'UTC') AT TIME ZONE 'Asia/Kolkata','DD-MON HH24:MI:SS') received_ist,
       ROUND((CAST(incoming_extract_ts  AS DATE) - CAST(incoming_heartbeat_ts AS DATE))*86400) extract_lag_sec,
       ROUND((CAST(incoming_replicat_ts AS DATE) - CAST(incoming_extract_ts   AS DATE))*86400) replicat_lag_sec
FROM   goldengate.gg_heartbeat_history
WHERE  heartbeat_received_ts BETWEEN TIMESTAMP '2026-10-01 13:00:00' - INTERVAL '0 05:30:00' DAY TO SECOND
                                 AND TIMESTAMP '2026-10-01 14:00:00' - INTERVAL '0 05:30:00' DAY TO SECOND
ORDER  BY heartbeat_received_ts;
```

High `extract_lag_sec` = EXT1 behind reading source redo. High `replicat_lag_sec` = REP1 slow applying on the target.

**5. Daily lag summary, last 30 days (Target)**

```sql
SELECT TO_CHAR(TRUNC(CAST(FROM_TZ(heartbeat_received_ts,'UTC') AT TIME ZONE 'Asia/Kolkata' AS DATE)),'DD-MON-YYYY') day_ist,
       ROUND(MAX(incoming_lag))   max_lag_sec,
       ROUND(AVG(incoming_lag),1) avg_lag_sec,
       SUM(CASE WHEN incoming_lag > 300 THEN 1 ELSE 0 END) min_over_5m
FROM   goldengate.gg_lag_history
GROUP  BY TRUNC(CAST(FROM_TZ(heartbeat_received_ts,'UTC') AT TIME ZONE 'Asia/Kolkata' AS DATE))
ORDER  BY TRUNC(CAST(FROM_TZ(heartbeat_received_ts,'UTC') AT TIME ZONE 'Asia/Kolkata' AS DATE));
```

**6. Heartbeat job health (Source)**

```sql
SELECT job_name, enabled, state, failure_count,
       TO_CHAR(last_start_date,'DD-MON HH24:MI:SS') last_run
FROM   dba_scheduler_jobs
WHERE  owner = 'GOLDENGATE' AND job_name LIKE 'GG%';
```

If this job stops, `hb_age_sec` on the target grows even though replication is fine; check it before raising a lag alarm.

## More monitoring queries

Deeper analysis: history, incidents, patterns, housekeeping and Grafana output. Create the two helper views first; they convert UTC to IST and intervals to seconds, and every query below uses them.

| Query | Run on |
| --- | --- |
| A1 Helper views (one-time) | Target |
| A2–A9 Lag history, incidents, hops, stalls, patterns | Target |
| A10–A11 Job failures, seed row | Source |
| A12–A13 Housekeeping | Target |
| A14 Grafana / Prometheus output | Target |

**A1. Helper views, one-time (Target)**

```sql
CREATE OR REPLACE VIEW goldengate.v_hb_lag AS
SELECT CAST(FROM_TZ(heartbeat_received_ts,'UTC') AT TIME ZONE 'Asia/Kolkata' AS TIMESTAMP) received_ist,
       heartbeat_received_ts received_utc,
       incoming_path,
       incoming_lag lag_sec
FROM   goldengate.gg_lag_history;

CREATE OR REPLACE VIEW goldengate.v_hb_hops AS
SELECT CAST(FROM_TZ(received_ts,'UTC') AT TIME ZONE 'Asia/Kolkata' AS TIMESTAMP) received_ist,
       received_ts received_utc, incoming_extract, incoming_replicat,
       EXTRACT(DAY FROM e)*86400 + EXTRACT(HOUR FROM e)*3600 + EXTRACT(MINUTE FROM e)*60 + EXTRACT(SECOND FROM e) extract_lag_sec,
       EXTRACT(DAY FROM r)*86400 + EXTRACT(HOUR FROM r)*3600 + EXTRACT(MINUTE FROM r)*60 + EXTRACT(SECOND FROM r) replicat_lag_sec,
       EXTRACT(DAY FROM t)*86400 + EXTRACT(HOUR FROM t)*3600 + EXTRACT(MINUTE FROM t)*60 + EXTRACT(SECOND FROM t) total_lag_sec
FROM (
  SELECT heartbeat_received_ts received_ts, incoming_extract, incoming_replicat,
         incoming_extract_ts  - incoming_heartbeat_ts e,
         incoming_replicat_ts - incoming_extract_ts   r,
         incoming_replicat_ts - incoming_heartbeat_ts t
  FROM   goldengate.gg_heartbeat_history
);
```

**A2. Last 1 hour, per heartbeat (Target)**

```sql
SELECT TO_CHAR(received_ist,'DD-MON HH24:MI:SS') received_ist, ROUND(lag_sec,1) lag_sec
FROM   goldengate.v_hb_lag
WHERE  received_ist > SYSTIMESTAMP - INTERVAL '1' HOUR
ORDER  BY received_ist;
```

**A3. Last 24 hours, hourly max / avg / p95 (Target)**

```sql
SELECT TO_CHAR(TRUNC(received_ist,'HH24'),'DD-MON HH24":00"') hour_ist,
       ROUND(MAX(lag_sec)) max_lag_sec,
       ROUND(AVG(lag_sec),1) avg_lag_sec,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY lag_sec),1) p95_lag_sec,
       COUNT(*) heartbeats
FROM   goldengate.v_hb_lag
WHERE  received_ist > SYSTIMESTAMP - INTERVAL '24' HOUR
GROUP  BY TRUNC(received_ist,'HH24')
ORDER  BY 1;
```

**A4. Top 20 worst minutes, last 30 days (Target)**

```sql
SELECT TO_CHAR(received_ist,'DD-MON HH24:MI') received_ist, ROUND(lag_sec) lag_sec
FROM   goldengate.v_hb_lag
ORDER  BY lag_sec DESC
FETCH FIRST 20 ROWS ONLY;
```

**A5. Lag incidents, last 7 days: lag over 60 s for 3+ consecutive heartbeats (Target)**

```sql
WITH x AS (
  SELECT received_ist, lag_sec, CASE WHEN lag_sec > 60 THEN 1 ELSE 0 END bad
  FROM   goldengate.v_hb_lag
  WHERE  received_ist > SYSTIMESTAMP - INTERVAL '7' DAY
), g AS (
  SELECT x.*, ROW_NUMBER() OVER (ORDER BY received_ist)
            - ROW_NUMBER() OVER (PARTITION BY bad ORDER BY received_ist) grp
  FROM   x
)
SELECT TO_CHAR(MIN(received_ist),'DD-MON HH24:MI') start_ist,
       TO_CHAR(MAX(received_ist),'DD-MON HH24:MI') end_ist,
       COUNT(*) heartbeats,
       ROUND(MAX(lag_sec)) peak_lag_sec,
       ROUND(AVG(lag_sec)) avg_lag_sec
FROM   g
WHERE  bad = 1
GROUP  BY grp
HAVING COUNT(*) >= 3
ORDER  BY MIN(received_ist) DESC;
```

**A6. Hourly extract vs replicat, last 24 hours (Target)**

```sql
SELECT TO_CHAR(TRUNC(received_ist,'HH24'),'DD-MON HH24":00"') hour_ist,
       ROUND(MAX(extract_lag_sec))  max_extract_sec,
       ROUND(MAX(replicat_lag_sec)) max_replicat_sec,
       ROUND(AVG(extract_lag_sec),1)  avg_extract_sec,
       ROUND(AVG(replicat_lag_sec),1) avg_replicat_sec
FROM   goldengate.v_hb_hops
WHERE  received_ist > SYSTIMESTAMP - INTERVAL '24' HOUR
GROUP  BY TRUNC(received_ist,'HH24')
ORDER  BY 1;
```

**A7. Bottleneck verdict for an incident window, IST (Target)**

```sql
SELECT ROUND(MAX(extract_lag_sec))  peak_extract_sec,
       ROUND(MAX(replicat_lag_sec)) peak_replicat_sec,
       CASE WHEN MAX(extract_lag_sec) > MAX(replicat_lag_sec)
            THEN 'EXTRACT bottleneck (source redo / capture)'
            ELSE 'REPLICAT bottleneck (target apply)' END verdict
FROM   goldengate.v_hb_hops
WHERE  received_ist BETWEEN TIMESTAMP '2026-10-01 13:00:00' AND TIMESTAMP '2026-10-01 14:00:00';
```

**A8. Gaps over 150 s between heartbeats, last 7 days (Target)**

A gap means a process was down or stuck.

```sql
SELECT TO_CHAR(prev_ist,'DD-MON HH24:MI:SS') gap_from_ist,
       TO_CHAR(received_ist,'DD-MON HH24:MI:SS') gap_to_ist,
       ROUND((CAST(received_ist AS DATE) - CAST(prev_ist AS DATE))*86400) gap_sec
FROM (
  SELECT received_ist, LAG(received_ist) OVER (ORDER BY received_ist) prev_ist
  FROM   goldengate.v_hb_lag
  WHERE  received_ist > SYSTIMESTAMP - INTERVAL '7' DAY
)
WHERE  (CAST(received_ist AS DATE) - CAST(prev_ist AS DATE))*86400 > 150
ORDER  BY received_ist DESC;
```

**A9. Lag by hour of day and by weekday, last 30 days (Target)**

Finds recurring batch windows such as the 13:00 load on 29 Sep.

```sql
SELECT TO_CHAR(received_ist,'HH24') hour_of_day,
       ROUND(AVG(lag_sec),1) avg_lag_sec,
       ROUND(MAX(lag_sec))   max_lag_sec,
       SUM(CASE WHEN lag_sec > 60 THEN 1 ELSE 0 END) min_over_1m
FROM   goldengate.v_hb_lag
WHERE  received_ist > SYSTIMESTAMP - INTERVAL '30' DAY
GROUP  BY TO_CHAR(received_ist,'HH24')
ORDER  BY 1;

SELECT TO_CHAR(received_ist,'DY') weekday,
       ROUND(AVG(lag_sec),1) avg_lag_sec,
       ROUND(MAX(lag_sec))   max_lag_sec
FROM   goldengate.v_hb_lag
WHERE  received_ist > SYSTIMESTAMP - INTERVAL '30' DAY
GROUP  BY TO_CHAR(received_ist,'DY'), TO_CHAR(received_ist,'D')
ORDER  BY TO_CHAR(received_ist,'D');
```

**A10. Heartbeat job failures (Source)**

```sql
SELECT job_name, status, error#,
       TO_CHAR(actual_start_date,'DD-MON HH24:MI:SS') started, additional_info
FROM   dba_scheduler_job_run_details
WHERE  owner = 'GOLDENGATE' AND job_name LIKE 'GG%' AND status <> 'SUCCEEDED'
ORDER  BY actual_start_date DESC
FETCH FIRST 20 ROWS ONLY;
```

**A11. Seed row, timestamp should move every 60 s (Source)**

```sql
SELECT * FROM goldengate.gg_heartbeat_seed;
```

**A12. History volume and range (Target)**

```sql
SELECT COUNT(*) rows_kept,
       TO_CHAR(MIN(received_ist),'DD-MON-YYYY HH24:MI') oldest_ist,
       TO_CHAR(MAX(received_ist),'DD-MON-YYYY HH24:MI') newest_ist
FROM   goldengate.v_hb_lag;
```

**A13. Heartbeat segment sizes (Target)**

```sql
SELECT segment_name, ROUND(SUM(bytes)/1024/1024,1) size_mb
FROM   dba_segments
WHERE  owner = 'GOLDENGATE' AND segment_name LIKE 'GG_HEARTBEAT%'
GROUP  BY segment_name;
```

**A14. Prometheus output for the textfile collector (Target)**

```sql
SELECT 'ogg_heartbeat_lag_seconds{path="'||incoming_path||'"} '||ROUND(NVL(incoming_lag,-1),1) FROM goldengate.gg_lag
UNION ALL
SELECT 'ogg_heartbeat_age_seconds{path="'||incoming_path||'"} '||ROUND(NVL(incoming_heartbeat_age,-1),1) FROM goldengate.gg_lag;

SELECT 'ogg_extract_lag_seconds '||ROUND(extract_lag_sec,1)
       ||CHR(10)||'ogg_replicat_lag_seconds '||ROUND(replicat_lag_sec,1)
FROM   goldengate.v_hb_hops
ORDER  BY received_utc DESC
FETCH FIRST 1 ROWS ONLY;
```

## Performance enhancements

The 29 Sep lag was an EXT1 bottleneck: about 5 million source row changes in 26 minutes, mostly non-replicated GININTG integration updates, which EXT1 had to read and discard. These items reduce the chance of a repeat.

| # | Action | Owner | Effort |
| --- | --- | --- | --- |
| 1 | Exclude trigger DDL (Change 1) | DBA | Low |
| 2 | Heartbeat monitoring (Change 2) | DBA | Low |
| 3 | Resize online redo logs from 100 MB to 1–2 GB to cut log switches under load | DBA | Medium |
| 4 | Raise cache on hot sequences in GININTG / RSBR (367k SEQ$ updates in 26 min) | DBA | Low |
| 5 | Add manager lag reporting: `LAGREPORTMINUTES 5`, `LAGINFOMINUTES 5`, `LAGCRITICALMINUTES 15` in mgr.prm | DBA | Low |
| 6 | Schedule or throttle bulk item integration (GININTG) off-peak, not alongside bank integration | App team | Medium |

Find low-cache sequences for item 4 (Source):

```sql
SELECT sequence_owner, sequence_name, cache_size
FROM   dba_sequences
WHERE  sequence_owner IN ('GININTG','RSBR') AND cache_size <= 20
ORDER  BY last_number DESC FETCH FIRST 20 ROWS ONLY;
```

## References

- [DDL parameter reference](https://docs.oracle.com/en/database/goldengate/core/26/reference/ddl.html#valid-for)
- [ADD HEARTBEATTABLE](https://docs.oracle.com/en/database/goldengate/core/26/gclir/add-heartbeattable.html)

Both links are the 26ai documentation; this environment runs GoldenGate 19c, so confirm syntax against the 19c reference before applying.
