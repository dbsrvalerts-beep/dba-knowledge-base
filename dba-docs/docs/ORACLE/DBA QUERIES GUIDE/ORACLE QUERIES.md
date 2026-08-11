# Oracle DBA Query Reference Guide

*Daily Monitoring, Performance & Maintenance Queries*

**DB Services Team (Ginesys)**  
**Compiled:** July 2026

---

## 1. Redo / Archive Log Monitoring

### Archive Log Sequence & Switch Time (last 24 hrs)

```sql
SELECT a.inst_id, b.recid, to_char(b.first_time, 'dd-mon-yy hh24:mi:ss') start_time,

a.recid, to_char(a.first_time, 'dd-mon-yy hh24:mi:ss') end_time,

round(((a.first_time - b.first_time) * 24) * 60, 2) minutes

FROM gv$log_history a, gv$log_history b

WHERE a.inst_id = b.inst_id

AND a.inst_id = 1

AND a.recid = b.recid + 1

AND a.first_time >= sysdate - 1

ORDER BY a.first_time DESC;
```

### Archive Generation - Hourly Size & Count (today)

```sql
SELECT TO_CHAR(FIRST_TIME, 'YYYY-MM-DD HH24') AS HOUR,

COUNT(*) AS NUM_ARCHIVES_GENERATED,

ROUND(SUM(BLOCKS * BLOCK_SIZE) / 1024 / 1024 / 1024, 2) AS ARCHIVE_SIZE_GB

FROM v$archived_log

WHERE TRUNC(FIRST_TIME) = TRUNC(SYSDATE)

GROUP BY TO_CHAR(FIRST_TIME, 'YYYY-MM-DD HH24')

ORDER BY 1 ASC;
```

### Archive Generation - Daily Size & Count

```sql
SELECT TO_CHAR(FIRST_TIME, 'YYYY-MM-DD') AS DAY,

COUNT(*) AS NUM_ARCHIVES_GENERATED,

ROUND(SUM(BLOCKS * BLOCK_SIZE) / 1024 / 1024 / 1024, 2) AS ARCHIVE_SIZE_GB

FROM v$archived_log

GROUP BY TO_CHAR(FIRST_TIME, 'YYYY-MM-DD')

ORDER BY 1 DESC;

-- add: FETCH FIRST 5 ROWS ONLY to limit to last 5 days
```

### High Redo Generation by Hour & Thread

```sql
SELECT trunc(COMPLETION_TIME, 'HH') Hour, thread#,

round(sum(BLOCKS * BLOCK_SIZE) / 1024 / 1024 / 1024) GB,

count(*) Archives

FROM v$archived_log

GROUP BY trunc(COMPLETION_TIME, 'HH'), thread#

ORDER BY 1;
```

### Archives Generated Today (Total GB)

```sql
SELECT round(sum(blocks * block_size) / 1024 / 1024 / 1024, 2) "Total_GB"

FROM v$archived_log

WHERE completion_time > trunc(sysdate);
```

### Sessions/Objects Generating High Redo (block changes)

```sql
SELECT s.sid, s.serial#, s.username, s.program, si.block_changes

FROM gv$session s, gv$sess_io si

WHERE s.sid = si.sid

ORDER BY 5 DESC;
```

### Objects Generating Redo - AWR History (by hour range)

```sql
SELECT to_char(begin_interval_time, 'YY-MM-DD HH24') snap_time,

dhso.object_name, dhso.owner,

sum(db_block_changes_delta) BLOCK_CHANGED

FROM dba_hist_seg_stat dhss,

dba_hist_seg_stat_obj dhso,

dba_hist_snapshot dhs

WHERE dhs.snap_id = dhss.snap_id

AND dhs.instance_number = dhss.instance_number

AND dhss.obj# = dhso.obj#

AND dhss.dataobj# = dhso.dataobj#

AND begin_interval_time BETWEEN to_date('<start_datetime>', 'YY-MM-DD HH24:MI')

AND to_date('<end_datetime>', 'YY-MM-DD HH24:MI')

GROUP BY to_char(begin_interval_time, 'YY-MM-DD HH24'), dhso.object_name, dhso.owner

HAVING sum(db_block_changes_delta) > 0

ORDER BY sum(db_block_changes_delta) DESC;
```

## 2. Memory Advisors (SGA / PGA)

### SGA Target Advice

```sql
SELECT * FROM v$sga_target_advice;
```

### PGA Target Advice

```sql
SELECT * FROM v$pga_target_advice;
```

### Total SGA Size by Component (GB)

```sql
SELECT sum(size_mb) FROM (

SELECT component, current_size / 1024 / 1024, current_size / 1024 / 1024 / 1024 AS size_gb

FROM v$sga_dynamic_components

);
```

## 3. Session Monitoring

### Long Running Queries (> 1 minute) - Summary

```sql
SELECT DISTINCT s.username, s.sid, s.serial#, s.last_call_et / 60 mins_running

FROM v$session s

JOIN v$sqltext_with_newlines q ON s.sql_address = q.address

WHERE status = 'ACTIVE'

AND type <> 'BACKGROUND'

AND last_call_et > 60

ORDER BY 4 DESC;
```

### Long Running Queries (> 1 minute) - Detailed

```sql
SELECT DISTINCT substr(s.username, 1, 10) username, substr(s.sid, 1, 5) SID,

substr(s.serial#, 1, 5) SERIAL#, s.last_call_et / 60 mins_running,

substr(s.PROGRAM, 1, 20) Program, substr(s.TERMINAL, 1, 15) Terminal,

substr(s.ACTION, 1, 20) Action, substr(s.EVENT, 1, 20) Event,

TO_CHAR(s.LOGON_TIME, 'DD-MON-YYYY') LOGON_TIME,

substr(s.WAIT_CLASS, 1, 15) Wait_Class, s.process

FROM v$session s

JOIN v$sqltext_with_newlines q ON s.sql_address = q.address

WHERE status = 'ACTIVE'

AND type <> 'BACKGROUND'

AND last_call_et > 60

ORDER BY 4 DESC;
```

### Program-wise Session Counts (Active / Inactive)

```sql
SELECT

substr(PROGRAM, 1, 35) "PROGRAM",

count(1) AS "TOTAL_SESSIONS",

COUNT(CASE WHEN STATUS = 'ACTIVE' THEN 1 ELSE NULL END) AS ACTIVE_SESSIONS,

COUNT(CASE WHEN STATUS = 'INACTIVE' THEN 1 ELSE NULL END) AS INACTIVE_SESSIONS

FROM v$session

WHERE type <> 'BACKGROUND'

GROUP BY PROGRAM

ORDER BY 3 DESC;
```

### Top 10 Sessions by CPU Usage

```sql
COLUMN program FORMAT A20

COLUMN ACTION FORMAT A20

COLUMN Wait_Class FORMAT A15

COLUMN TERMINAL FORMAT A10

SELECT ROWNUM AS RANK, a.*

FROM (

SELECT v.sid, sess.Serial#, SUBSTR(program, 1, 20) program,

ROUND(v.VALUE / (100 * 60), 2) CPUMins,

TO_CHAR(sess.LOGON_TIME, 'DD-MON-YYYY') LOGON_TIME,

sess.ACTION, SUBSTR(sess.EVENT, 1, 20) Event,

SUBSTR(sess.TERMINAL, 1, 10) Terminal, sess.WAIT_CLASS

FROM v$statname s, v$sesstat v, v$session sess

WHERE s.name = 'CPU used by this session'

AND sess.sid = v.sid

AND v.statistic# = s.statistic#

AND v.value > 0

ORDER BY v.value DESC

) a

WHERE rownum < 11;
```

### Sessions Using TEMP Tablespace

```sql
SELECT substr(S.sid || ',' || S.serial#, 1, 15) sid_serial, substr(S.username, 1, 15) username,

substr(S.osuser, 1, 20) osuser, substr(P.spid, 1, 9) spid, substr(S.module, 1, 25) module,

substr(P.program, 1, 15) program,

SUM(T.blocks) * TBS.block_size / 1024 / 1024 mb_used,

substr(T.tablespace, 1, 15) tablespace, substr(COUNT(*), 1, 10) statements

FROM v$sort_usage T, v$session S, dba_tablespaces TBS, v$process P

WHERE T.session_addr = S.saddr

AND S.paddr = P.addr

AND T.tablespace = TBS.tablespace_name

GROUP BY S.sid, S.serial#, S.username, S.osuser, P.spid, S.module, P.program, TBS.block_size, T.tablespace

ORDER BY sid_serial;
```

### Sessions Using UNDO (active transactions)

```sql
SELECT s.sid, s.serial#, s.username, s.osuser, s.program,

t.start_time, t.used_ublk * 8 / 1024 AS active_undo_size_in_mb

FROM v$session s

JOIN v$transaction t ON s.saddr = t.ses_addr

WHERE t.status = 'ACTIVE'

AND t.used_ublk > 0

ORDER BY t.start_time;
```

### Long-Running Operations Progress (V\$SESSION_LONGOPS)

```sql
SELECT sid, serial#, username, opname, target, start_time, message,

elapsed_seconds, sql_id, sofar, totalwork,

ROUND(SOFAR / TOTALWORK * 100, 2) "%_COMPLETE"

FROM V$SESSION_LONGOPS

WHERE TOTALWORK != 0

AND SOFAR <> TOTALWORK;
```

### Session Count by Status

```sql
SELECT count(1), status FROM v$session GROUP BY status;
```

### List All Sessions

```sql
SELECT * FROM v$session;
```

### Top SQL by Disk Reads per Execution

```sql
SELECT username users, round(DISK_READS / Executions) DReadsExec,

Executions Exec, DISK_READS DReads, sql_text

FROM gv$sqlarea a, dba_users b

WHERE a.parsing_user_id = b.user_id

AND Executions > 0

AND DISK_READS > 1

ORDER BY 2 DESC;
```

## 4. Killing / Disconnecting Sessions

### Disconnect a Specific Session

```sql
ALTER SYSTEM DISCONNECT SESSION '<sid>,<serial#>' IMMEDIATE;

-- Example: ALTER SYSTEM DISCONNECT SESSION '62,43641' IMMEDIATE;
```

### Generate Disconnect Statements for All Sessions Active > 1 Minute

```sql
SELECT DISTINCT

'ALTER SYSTEM DISCONNECT SESSION ''' || sid || ',' || serial# || ''' IMMEDIATE;'

FROM v$session S

JOIN V$SQLTEXT_WITH_NEWLINES Q ON S.SQL_ADDRESS = Q.ADDRESS

WHERE STATUS = 'ACTIVE'

AND TYPE <> 'BACKGROUND'

AND LAST_CALL_ET > 60;
```

### PL/SQL Block - Auto-Disconnect All Sessions Active > 1 Minute

```sql
DECLARE

V_STR VARCHAR2(200);

ERRCODE VARCHAR2(200);

CURSOR C1 IS

SELECT DISTINCT S.SID, S.SERIAL# SR

FROM V$SESSION S

JOIN V$SQLTEXT_WITH_NEWLINES Q ON S.SQL_ADDRESS = Q.ADDRESS

WHERE STATUS = 'ACTIVE' AND TYPE <> 'BACKGROUND' AND LAST_CALL_ET > 60;

BEGIN

FOR R1 IN C1 LOOP

V_STR := 'ALTER SYSTEM DISCONNECT SESSION ''' || R1.SID || ', ' || R1.SR || ''' IMMEDIATE;';

EXECUTE IMMEDIATE V_STR;

COMMIT;

END LOOP;

END;

/
```

## 5. Locking Sessions

### Identify Blocker / Blockee Pairs

```sql
SELECT

(SELECT username FROM v$session WHERE sid = a.sid) blocker,

a.sid,

' is blocking ',

(SELECT username FROM v$session WHERE sid = b.sid) blockee,

b.sid

FROM v$lock a, v$lock b

WHERE a.block = 1

AND b.request > 0

AND a.id1 = b.id1

AND a.id2 = b.id2;
```

### Blocker/Blockee - Full Session Detail

```sql
SELECT 'BLOCKEE', substr(sid, 1, 5) SID, substr(serial#, 1, 6) serial#,

substr(username, 1, 10) username, LOCKWAIT, status,

substr(osuser, 1, 15) osuser, substr(machine, 1, 15) Machine,

substr(terminal, 1, 10) terminal, substr(program, 1, 10) Program,

TO_CHAR(LOGON_TIME, 'DD-MON-YYYY') LOGON_TIME

FROM V$SESSION

WHERE SID IN (

SELECT GSID FROM (

SELECT (SELECT username FROM v$session WHERE sid = a.sid) blocker, a.sid,

' is blocking ', (SELECT username FROM v$session WHERE sid = b.sid) blockee, b.sid GSID

FROM v$lock a, v$lock b

WHERE a.block = 1 AND b.request > 0 AND a.id1 = b.id1 AND a.id2 = b.id2

)

)

UNION

SELECT 'BLOCKER', substr(sid, 1, 5) SID, substr(serial#, 1, 6) serial#,

substr(username, 1, 10) username, LOCKWAIT, status,

substr(osuser, 1, 15) osuser, substr(machine, 1, 15) Machine,

substr(terminal, 1, 10) terminal, substr(program, 1, 10) Program,

TO_CHAR(LOGON_TIME, 'DD-MON-YYYY') LOGON_TIME

FROM V$SESSION

WHERE SID IN (

SELECT SID FROM (

SELECT (SELECT username FROM v$session WHERE sid = a.sid) blocker, a.sid,

' is blocking ', (SELECT username FROM v$session WHERE sid = b.sid) blockee, b.sid GSID

FROM v$lock a, v$lock b

WHERE a.block = 1 AND b.request > 0 AND a.id1 = b.id1 AND a.id2 = b.id2

)

);
```

## 6. Tablespace: TEMP & UNDO

### TEMP Tablespace Usage Summary

```sql
SELECT A.tablespace_name tablespace, D.mb_total,

SUM(A.used_blocks * D.block_size) / 1024 / 1024 mb_used,

D.mb_total - SUM(A.used_blocks * D.block_size) / 1024 / 1024 mb_free

FROM v$sort_segment A,

(SELECT B.name, C.block_size, SUM(C.bytes) / 1024 / 1024 mb_total

FROM v$tablespace B, v$tempfile C

WHERE B.ts# = C.ts#

GROUP BY B.name, C.block_size) D

WHERE A.tablespace_name = D.name

GROUP BY A.tablespace_name, D.mb_total;
```

### UNDO Tablespace Size vs Usage

```sql
SELECT a.tablespace_name, SIZEMB, USAGEMB, (SIZEMB - USAGEMB) FREEMB

FROM (

SELECT SUM(maxbytes) / 1024 / 1024 SIZEMB, b.tablespace_name

FROM dba_data_files a, dba_tablespaces b

WHERE a.tablespace_name = b.tablespace_name

AND b.contents LIKE 'UNDO'

GROUP BY b.tablespace_name

) a,

(

SELECT c.tablespace_name, SUM(bytes) / 1024 / 1024 USAGEMB

FROM DBA_UNDO_EXTENTS c

GROUP BY c.tablespace_name

) b

WHERE a.tablespace_name = b.tablespace_name;
```

### UNDO Extents by Status (ACTIVE/EXPIRED/UNEXPIRED)

```sql
SELECT tablespace_name AS tablespace, status,

SUM(bytes) / 1024 / 1024 AS sum_in_mb, COUNT(*) AS counts

FROM dba_undo_extents

GROUP BY tablespace_name, status

ORDER BY tablespace_name, status;
```

### Datafile High Water Mark & Resizable Space

```sql
SELECT tablespace_name, file_id, file_name DATA_FILE_NAME,

Allocated_MBYTES, High_Water_Mark_MBYTES, FREE_MBYTES,

trunc((FREE_MBYTES / Allocated_MBYTES) * 100, 2) "% Free",

trunc(Allocated_MBYTES - High_Water_Mark_MBYTES, 2) Resizable

FROM (

SELECT ddf.tablespace_name tablespace_name, ddf.file_id file_id, ddf.file_name file_name,

ddf.bytes / 1024 / 1024 Allocated_MBYTES,

trunc((ex.hwm * (dt.block_size)) / 1024 / 1024, 2) High_Water_Mark_MBYTES,

FREE_MBYTES

FROM dba_data_files ddf,

dba_tablespaces dt,

(SELECT file_id, sum(bytes / 1024 / 1024) FREE_MBYTES FROM dba_free_space GROUP BY file_id) free,

(SELECT file_id, max(block_id + blocks) hwm FROM dba_extents GROUP BY file_id) ex

WHERE ddf.file_id = ex.file_id

AND ddf.tablespace_name = dt.tablespace_name

AND ddf.file_id = free.file_id (+)

ORDER BY ddf.tablespace_name, ddf.file_id

);
```

## 7. Object & Schema Sizing

### Schema Size (all owners, MB/GB)

```sql
SELECT substr(owner, 1, 20) owner,

ROUND(SUM(bytes) / 1024 / 1024, 2) schema_size_MB,

ROUND(SUM(bytes) / 1024 / 1024 / 1024, 2) schema_size_GB

FROM dba_segments

GROUP BY owner

ORDER BY 2 DESC;
```

### Segment Size for a Specific Table (with LOB info)

```sql
SELECT t.owner, t.SEGMENT_NAME, t.SEGMENT_TYPE, B.table_name, B.Column_name, t.TABLESPACE_NAME,

round(sum(t.bytes) / 1024 / 1024, 2) schema_size_MB,

round(sum(t.bytes) / 1024 / 1024 / 1024, 2) schema_size_gig

FROM dba_segments t

LEFT JOIN dba_lobs B ON t.segment_name = b.segment_name AND t.owner = B.OWNER

WHERE t.segment_name = '<table_name>'

GROUP BY t.owner, t.SEGMENT_NAME, t.SEGMENT_TYPE, t.TABLESPACE_NAME, B.table_name, B.COLUMN_name

ORDER BY 8 DESC;
```

### Segment Size with LOB Info - Top 100 Segments

```sql
SELECT t.owner, t.SEGMENT_NAME, t.SEGMENT_TYPE, B.table_name, B.Column_name, t.TABLESPACE_NAME,

round(sum(t.bytes) / 1024 / 1024, 2) schema_size_MB,

round(sum(t.bytes) / 1024 / 1024 / 1024, 2) schema_size_gig

FROM dba_segments t

LEFT JOIN dba_lobs B ON t.segment_name = b.segment_name AND t.owner = B.OWNER

GROUP BY t.owner, t.SEGMENT_NAME, t.SEGMENT_TYPE, t.TABLESPACE_NAME, B.table_name, B.COLUMN_name

ORDER BY 8 DESC

FETCH FIRST 100 ROWS ONLY;
```

### Table Size with Index Size and LOB Size Breakdown

```sql
SELECT

a.Owner,

a.SEGMENT_NAME AS Table_Name,

a.schema_size_MB AS Table_Size_MB,

NVL(index_data.index_size_MB, 0) AS Index_Size_MB,

NVL(lob_data.lob_size_MB, 0) AS LOB_Size_MB

FROM (

SELECT t.owner AS Owner, t.SEGMENT_NAME, t.SEGMENT_TYPE,

ROUND(SUM(t.bytes) / 1024 / 1024, 2) AS schema_size_MB

FROM dba_segments t

WHERE t.segment_name IN (<table_name_list>)

AND t.segment_type = 'TABLE'

GROUP BY t.owner, t.SEGMENT_NAME, t.SEGMENT_TYPE

) a

LEFT JOIN (

SELECT i.table_owner AS Owner, i.table_name AS Table_Name,

ROUND(SUM(s.bytes) / 1024 / 1024, 2) AS index_size_MB

FROM dba_indexes i

JOIN dba_segments s ON i.index_name = s.segment_name AND i.owner = s.owner

WHERE s.segment_type = 'INDEX'

AND i.table_name IN (<table_name_list>)

GROUP BY i.table_owner, i.table_name

) index_data ON a.Owner = index_data.Owner AND a.SEGMENT_NAME = index_data.Table_Name

LEFT JOIN (

SELECT l.owner AS Owner, l.table_name AS Table_Name,

ROUND(SUM(s.bytes) / 1024 / 1024, 2) AS lob_size_MB

FROM dba_lobs l

JOIN dba_segments s ON l.segment_name = s.segment_name AND l.owner = s.owner

WHERE s.segment_type = 'LOBSEGMENT'

AND l.table_name IN (<table_name_list>)

GROUP BY l.owner, l.table_name

) lob_data ON a.Owner = lob_data.Owner AND a.SEGMENT_NAME = lob_data.Table_Name;
```

### Index Count & Size per Table (for a given owner)

```sql
SELECT I.Owner, I.table_name, I.table_owner,

COUNT(I.index_name) AS Total_indx,

ROUND(SUM(T.bytes) / 1024 / 1024, 2) AS index_size_MB

FROM dba_indexes I

LEFT JOIN dba_segments T ON I.owner = T.Owner AND I.INDEX_name = T.SEGMENT_NAME

WHERE I.owner = '<schema_owner>'

GROUP BY I.Owner, I.table_name, I.table_owner;
```

## 8. Historical Object Size Tracking (Growth Comparison)

### Object Size Difference Between Two Snapshot Dates

```sql
SELECT

NEW.LOGDATE N_RUNDATE, NEW.OWNER NEW_OWNER, NEW.segment_name N_SEGNAME,

NEW.segment_type N_SEGTYPE, NEW.SCHEMA_SIZE_GIG N_SSIZE_GB, NEW.tablespace_name N_tablespace_name,

old.LOGDATE O_RUNDATE, OLD.OWNER OLD_OWNER, old.segment_name O_SEGNAME,

old.segment_type O_SEGTYPE, old.SCHEMA_SIZE_GIG O_SSIZE_GB,

round(NEW.SCHEMA_SIZE_GIG - old.SCHEMA_SIZE_GIG, 2) "DIFF_SIZE"

FROM (

SELECT A.LOGDATE, A.tablespace_name, A.segment_name, A.segment_type, A.SCHEMA_SIZE_MB, A.SCHEMA_SIZE_GIG, A.OWNER

FROM <owner>.object_segment A

WHERE to_char(logdate, 'DD-MON-YY') = '<old_date>'

) OLD,

(

SELECT B.LOGDATE, B.tablespace_name, B.segment_name, B.segment_type, B.SCHEMA_SIZE_MB, B.SCHEMA_SIZE_GIG, B.OWNER

FROM <owner>.object_segment B

WHERE to_char(logdate, 'DD-MON-YY') = '<new_date>'

) NEW

WHERE OLD.SEGMENT_NAME(+) = NEW.SEGMENT_NAME

AND OLD.SEGMENT_TYPE(+) = NEW.SEGMENT_TYPE

AND OLD.OWNER = NEW.OWNER

AND (OLD.SCHEMA_SIZE_GIG - new.SCHEMA_SIZE_GIG) >= 5

ORDER BY DIFF_SIZE DESC;
```

### Net Growth for a Tablespace Between Two Dates (sum of diffs)

```sql
SELECT sum(diff) FROM (

SELECT SEGMENT_NAME, SUM(newsize) newsize, SUM(oldsize) oldsize, SUM(newsize - oldsize) DIFF

FROM (

SELECT a.SEGMENT_NAME, NVL(a.SCHEMA_SIZE_MB, 0) newsize, 0 oldsize

FROM <owner>.object_segment a

WHERE TRUNC(logdate) = '<new_date>'

AND A.TABLESPACE_NAME = '<tablespace_name>'

UNION ALL

SELECT a.SEGMENT_NAME, 0, NVL(a.SCHEMA_SIZE_MB, 0) oldsize

FROM <owner>.object_segment a

WHERE TRUNC(logdate) = '<old_date>'

AND A.TABLESPACE_NAME = '<tablespace_name>'

)

GROUP BY SEGMENT_NAME

HAVING SUM(newsize - oldsize) <> 0

ORDER BY 4 DESC

);
```

## 9. Materialized Views

### Materialized View Last Refresh Time (all owners)

```sql
COLUMN OWNER FORMAT a15

COLUMN MVIEW_NAME FORMAT a30

SELECT OWNER, MVIEW_NAME, to_char(last_refresh_date, 'yyyy-mm-dd hh24:mi:ss') LAST_REFRESH_DATE

FROM all_mviews

WHERE owner IN (SELECT DISTINCT owner FROM all_mviews);
```

## 10. Statistics Gathering (DBMS_STATS)

### Gather Full Database Statistics

```sql
BEGIN

DBMS_STATS.GATHER_DATABASE_STATS(

cascade => DBMS_STATS.AUTO_CASCADE,

gather_sys => FALSE,

estimate_percent => NULL,

degree => NULL,

no_invalidate => DBMS_STATS.AUTO_INVALIDATE,

granularity => 'AUTO',

method_opt => 'FOR ALL COLUMNS SIZE AUTO',

options => 'GATHER'

);

END;

/
```

### Gather Statistics for a Single Table

```sql
BEGIN

DBMS_STATS.GATHER_TABLE_STATS(

ownname => '<schema_owner>',

tabname => '<table_name>',

estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,

method_opt => 'FOR ALL COLUMNS SIZE AUTO',

cascade => true

);

END;

/
```

### Gather Statistics for All Tables Listed in a Reference Table

```sql
BEGIN

FOR t IN (SELECT table_name FROM <control_schema>.<control_table>) LOOP

DBMS_STATS.GATHER_TABLE_STATS(

ownname => '<schema_owner>',

tabname => t.table_name,

estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,

method_opt => 'FOR ALL COLUMNS SIZE AUTO'

);

END LOOP;

END;

/
```

## 11. AWR / Diagnostic & Tuning Pack

### Enable Diagnostic + Tuning Pack (AWR)

```sql
ALTER SYSTEM SET CONTROL_MANAGEMENT_PACK_ACCESS = 'DIAGNOSTIC+TUNING' SCOPE = BOTH;

-- Also ensure STATISTICS_LEVEL = ALL (or TYPICAL)
```

### Disable Diagnostic + Tuning Pack (AWR)

```sql
ALTER SYSTEM SET CONTROL_MANAGEMENT_PACK_ACCESS = NONE SCOPE = BOTH;
```

## 12. LogMiner

### Start LogMiner Using Online Catalog

```sql
BEGIN

SYS.DBMS_LOGMNR.START_LOGMNR(options => SYS.DBMS_LOGMNR.DICT_FROM_ONLINE_CATALOG);

END;

/
```

### Add Archive Log Files & Start LogMiner

```sql
BEGIN

SYS.DBMS_LOGMNR.ADD_LOGFILE(logfilename => '<path_to_archive_1>', options => SYS.DBMS_LOGMNR.NEW);

SYS.DBMS_LOGMNR.ADD_LOGFILE(logfilename => '<path_to_archive_2>', options => SYS.DBMS_LOGMNR.ADDFILE);

SYS.DBMS_LOGMNR.ADD_LOGFILE(logfilename => '<path_to_archive_3>', options => SYS.DBMS_LOGMNR.ADDFILE);

SYS.DBMS_LOGMNR.START_LOGMNR(options => SYS.DBMS_LOGMNR.DICT_FROM_ONLINE_CATALOG);

END;

/
```

### Query Mined Redo Content

```sql
SELECT operation, seg_name, table_name, username, sql_redo, table_space

FROM v$logmnr_contents;
```

### Stop LogMiner

```sql
BEGIN

SYS.DBMS_LOGMNR.END_LOGMNR;

END;

/
```

## 13. Data Pump & Recycle Bin

### List Active Data Pump Jobs

```sql
SELECT owner_name, job_name, operation, job_mode, state, attached_sessions

FROM dba_datapump_jobs

WHERE job_name NOT LIKE 'BIN$%'

ORDER BY 1, 2;
```

### Purge the Recycle Bin

```sql
PURGE DBA_RECYCLEBIN;
```

## 14. Oracle GoldenGate

### Check Overall GoldenGate Health

```sql
INFO ALL
```

### Check Extract / Pump / Replicat Lag

```sql
LAG EXTRACT <extract_name>

LAG EXTRACT <pump_name>

LAG REPLICAT <replicat_name>
```

## 15. Ginesys ERP-Specific Checks

### Today's OLAP Cube Refresh Status

```sql
SELECT code, datacube_code, cube_code, start_time, end_time, run_duration,

substr(creator, 1, 20) Creator, substr(status, 1, 18) status,

substr(error_reason, 1, 40) error_reason

FROM RSBR.OLAP_CUBE_REFRESH_HISTORY

WHERE trunc(start_time) = trunc(sysdate)

ORDER BY 4 DESC;
```

### Daily Object-Size Record Health Check

```sql
SELECT substr(

CASE WHEN trunc(logdate) = trunc(CURRENT_DATE) THEN 'SUCCESS' ELSE 'FAILED' END

, 1, 20) AS object_record_status

FROM RSBR.object_segment

WHERE trunc(logdate) = trunc(sysdate)

FETCH FIRST 1 ROWS ONLY;
```

### PSite Event Backlog Check

```sql
SELECT count(1)

FROM rsbr.psite_event

WHERE admsite_code IN (SELECT code FROM rsbr.admsite WHERE ext = 'Y' AND ispos = 'Y')

AND dxsendid IS NULL

AND dxsend2id IS NULL;
```

##

##

##

### Tablespace Information

```sql
select substr(tablespace_name,1,20) tablespace_name,

TOTAL_MB,

TOTAL_MB - FREE_MB USED_MB,

FREE_MB,

tmaxsize,

round((round(TOTAL_MB)-round(FREE_MB))/round(TOTAL_MB)*100) "USED%"

from (

SELECT b.tablespace_name,

ROUND (tbs_size) TOTAL_MB,

ROUND (a.free_space) FREE_MB,

ROUND (b.tmaxsize) tmaxsize

FROM ( SELECT tablespace_name,

0 tmaxsize,

ROUND (SUM (bytes) / 1024 / 1024, 2) AS free_space

FROM dba_free_space

GROUP BY tablespace_name) a,

( SELECT tablespace_name,

SUM (MAXBYTES) / 1024 / 1024 tmaxsize,

SUM (bytes) / 1024 / 1024 AS tbs_size

FROM dba_data_files

GROUP BY tablespace_name

) b

WHERE a.tablespace_name(+) = b.tablespace_name

UNION ALL

SELECT Z.TABLESPACE,Z.TBS_SIZE,Z.FREE_SPACE,round(SUM (Y.MAXBYTES) / 1024 / 1024) tmaxsize

FROM

(SELECT A.tablespace_name tablespace, D.mb_total tbs_size,

D.mb_total - SUM (A.used_blocks * D.block_size) / 1024 / 1024 free_space

FROM v$sort_segment A,

(

SELECT B.name, C.block_size, SUM (C.bytes) / 1024 / 1024 mb_total

FROM v$tablespace B, v$tempfile C

WHERE B.ts#= C.ts#

GROUP BY B.name, C.block_size) D

WHERE A.tablespace_name = D.name

GROUP by A.tablespace_name, D.mb_total) Z,

dba_temp_files Y

WHERE Z.TABLESPACE=Y.TABLESPACE_NAME

GROUP BY Z.TABLESPACE,Z.TBS_SIZE,Z.FREE_SPACE

) ;
```

##

##

##

### Rman Backup Information

```sql
select command_id,to_char(start_time,'dd-MON-rr HH:mi:ss AM') start_time,time_taken_display,status,input_type,output_device_type,input_bytes_display,output_bytes_display

from (

select

substr(command_id,1, 20) command_id

, start_time

, substr(time_taken_display, 1, 20) time_taken_display

, substr(status, 1, 15) status

, input_type

, output_device_type

, substr(input_bytes_display, 1,20) input_bytes_display

, substr(output_bytes_display, 1,20) output_bytes_display

from v$rman_backup_job_details

order by start_time DESC,5 ) r

WHERE

rownum < 11

order by start_time DESC,5;
```

### Archive Space Information

```sql
SELECT substr(L.NAME,1,20) NAME,ROUND(L.SPACE_LIMIT/1024/1024/1024) SPACE_LIMIT,

ROUND(L.SPACE_USED/1024/1024/1024) SPACE_USED,

ROUND(L.SPACE_RECLAIMABLE/1024/1024/1024) SPACE_RECLIMABLE,

L.NUMBER_OF_FILES

FROM V$RECOVERY_FILE_DEST L;
```

### Log Switch Frequency Map Information

```sql
SELECT

SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH:MI:SS'),1,8) DAY

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'00',1,0)),1,3) H00

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'01',1,0)),1,3) H01

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'02',1,0)),1,3) H02

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'03',1,0)),1,3) H03

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'04',1,0)),1,3) H04

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'05',1,0)),1,3) H05

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'06',1,0)),1,3) H06

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'07',1,0)),1,3) H07

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'08',1,0)),1,3) H08

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'09',1,0)),1,3) H09

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'10',1,0)),1,3) H10

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'11',1,0)),1,3) H11

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'12',1,0)),1,3) H12

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'13',1,0)),1,3) H13

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'14',1,0)),1,3) H14

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'15',1,0)),1,3) H15

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'16',1,0)),1,3) H16

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'17',1,0)),1,3) H17

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'18',1,0)),1,3) H18

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'19',1,0)),1,3) H19

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'20',1,0)),1,3) H20

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'21',1,0)),1,3) H21

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'22',1,0)),1,3) H22

, SUBSTR(SUM(DECODE(SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH24:MI:SS'),10,2),'23',1,0)),1,3) H23

, COUNT(*) TOTAL

FROM

v$log_history a

GROUP BY SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH:MI:SS'),1,8)

ORDER BY SUBSTR(TO_CHAR(first_time, 'MM/DD/RR HH:MI:SS'),1,8)

/
```

