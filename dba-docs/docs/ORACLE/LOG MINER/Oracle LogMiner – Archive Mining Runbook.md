# Oracle LogMiner – 12c

Oct 14, 2026 · @mighty master of 7 galaxies

LogMiner reads archived redo and returns the SQL that changed the data (`SQL_REDO`) and the SQL that reverses it (`SQL_UNDO`). Three ways to load archives are covered: by time, by sequence range, and manually file by file. Tested pattern for Oracle 12c SE.

## 1. Prerequisites

Minimal supplemental logging must be on, otherwise UPDATE/DELETE redo is missing column values. It only applies to redo generated after it is enabled.

```sql
SELECT supplemental_log_data_min FROM v$database;   -- want YES or IMPLICIT
ALTER DATABASE ADD SUPPLEMENTAL LOG DATA;
```

Privileges if not running as SYS:

```sql
GRANT LOGMINING, EXECUTE_CATALOG_ROLE, SELECT ANY TRANSACTION TO <user>;
```

Session settings for readable output:

```sql
ALTER SESSION SET NLS_DATE_FORMAT = 'DD-MON-YYYY HH24:MI:SS';
SET LINES 300 PAGES 200 LONG 20000
COL sql_redo FOR A120
COL sql_undo FOR A120
```

Key `START_LOGMNR` options used below:

| Option | What it does |
| --- | --- |
| `DICT_FROM_ONLINE_CATALOG` | Uses the live data dictionary to turn object IDs into table/column names |
| `COMMITTED_DATA_ONLY` | Returns only committed transactions, grouped by transaction |
| `CONTINUOUS_MINE` | Oracle picks the archives itself from the control file (12c only; desupported in 19c) |
| `PRINT_PRETTY_SQL` | Formats `SQL_REDO`/`SQL_UNDO` over multiple lines (optional) |

## 2. Process 1 – Mine by time window

Use when you know when the change happened but not which archives hold it. Run `ALTER SYSTEM ARCHIVE LOG CURRENT;` first if the window reaches into the last few minutes.

**Option A: CONTINUOUS\_MINE (12c only).** Oracle looks up the archives in `V$ARCHIVED_LOG` and loads them; files must still be registered and present at the recorded path.

```sql
BEGIN
  DBMS_LOGMNR.START_LOGMNR(
    STARTTIME => TO_DATE('14-OCT-2026 10:00:00','DD-MON-YYYY HH24:MI:SS'),
    ENDTIME   => TO_DATE('14-OCT-2026 11:00:00','DD-MON-YYYY HH24:MI:SS'),
    OPTIONS   => DBMS_LOGMNR.DICT_FROM_ONLINE_CATALOG
               + DBMS_LOGMNR.CONTINUOUS_MINE
               + DBMS_LOGMNR.COMMITTED_DATA_ONLY);
END;
/
```

**Option B: auto-add from V$ARCHIVED\_LOG (any version, incl. 19c).**

```sql
DECLARE
  v_start DATE := TO_DATE('14-OCT-2026 10:00:00','DD-MON-YYYY HH24:MI:SS');
  v_end   DATE := TO_DATE('14-OCT-2026 11:00:00','DD-MON-YYYY HH24:MI:SS');
  v_first BOOLEAN := TRUE;
BEGIN
  FOR r IN (SELECT name FROM v$archived_log
            WHERE dest_id = 1 AND name IS NOT NULL
              AND deleted = 'NO' AND status = 'A'
              AND next_time > v_start AND first_time < v_end
            ORDER BY thread#, sequence#) LOOP
    DBMS_LOGMNR.ADD_LOGFILE(r.name,
      CASE WHEN v_first THEN DBMS_LOGMNR.NEW ELSE DBMS_LOGMNR.ADDFILE END);
    v_first := FALSE;
  END LOOP;

  DBMS_LOGMNR.START_LOGMNR(
    STARTTIME => v_start,
    ENDTIME   => v_end,
    OPTIONS   => DBMS_LOGMNR.DICT_FROM_ONLINE_CATALOG
               + DBMS_LOGMNR.COMMITTED_DATA_ONLY);
END;
/
```

`dest_id = 1` stops the same sequence being added twice when there are multiple archive destinations.

## 3. Process 2 – Mine by sequence range

Use when you know the archive sequence numbers (from the alert log, RMAN, or a backup report). No STARTTIME/ENDTIME, so every change in the loaded files is returned.

```sql
DECLARE
  v_thread NUMBER := 1;        -- RAC: run per thread
  v_from   NUMBER := 45210;
  v_to     NUMBER := 45230;
  v_first  BOOLEAN := TRUE;
BEGIN
  FOR r IN (SELECT name FROM v$archived_log
            WHERE dest_id = 1 AND thread# = v_thread
              AND sequence# BETWEEN v_from AND v_to
              AND name IS NOT NULL AND deleted = 'NO' AND status = 'A'
            ORDER BY sequence#) LOOP
    DBMS_LOGMNR.ADD_LOGFILE(r.name,
      CASE WHEN v_first THEN DBMS_LOGMNR.NEW ELSE DBMS_LOGMNR.ADDFILE END);
    v_first := FALSE;
  END LOOP;

  DBMS_LOGMNR.START_LOGMNR(
    OPTIONS => DBMS_LOGMNR.DICT_FROM_ONLINE_CATALOG
             + DBMS_LOGMNR.COMMITTED_DATA_ONLY);
END;
/
```

**Archives not in the control file** (restored to another directory or copied from another server): build the paths from `log_archive_format`.

```sql
SHOW PARAMETER log_archive_format   -- e.g. %t_%s_%r.dbf
SELECT resetlogs_id FROM v$database_incarnation WHERE status = 'CURRENT';
```

```sql
DECLARE
  v_dir  VARCHAR2(200) := '/u01/restore/arch/';
  v_rlid NUMBER        := 1023456789;   -- resetlogs_id
BEGIN
  FOR s IN 45210 .. 45230 LOOP
    DBMS_LOGMNR.ADD_LOGFILE(
      v_dir || '1_' || s || '_' || v_rlid || '.dbf',
      CASE WHEN s = 45210 THEN DBMS_LOGMNR.NEW ELSE DBMS_LOGMNR.ADDFILE END);
  END LOOP;
  DBMS_LOGMNR.START_LOGMNR(OPTIONS => DBMS_LOGMNR.DICT_FROM_ONLINE_CATALOG
                                    + DBMS_LOGMNR.COMMITTED_DATA_ONLY);
END;
/
```

A missing file raises ORA-01284 and stops the loop; check with `ls` first. Alternative: register them with RMAN `CATALOG START WITH '/u01/restore/arch/';` and use the first block.

## 4. Process 3 – Manual, one archive at a time

Use for a handful of files or when you want full control over exactly what is loaded. `NEW` starts a fresh list (clears earlier files); `ADDFILE` appends.

Find the file names:

```sql
COL name FOR A90
SELECT sequence#, name, first_time, next_time
FROM   v$archived_log
WHERE  dest_id = 1 AND thread# = 1
AND    sequence# BETWEEN 45210 AND 45215
ORDER  BY sequence#;
```

Add them one by one:

```sql
EXEC DBMS_LOGMNR.ADD_LOGFILE(LOGFILENAME => '/u01/arch/1_45210_1023456789.dbf', OPTIONS => DBMS_LOGMNR.NEW);
EXEC DBMS_LOGMNR.ADD_LOGFILE(LOGFILENAME => '/u01/arch/1_45211_1023456789.dbf', OPTIONS => DBMS_LOGMNR.ADDFILE);
EXEC DBMS_LOGMNR.ADD_LOGFILE(LOGFILENAME => '/u01/arch/1_45212_1023456789.dbf', OPTIONS => DBMS_LOGMNR.ADDFILE);

-- remove a wrong file
EXEC DBMS_LOGMNR.REMOVE_LOGFILE(LOGFILENAME => '/u01/arch/1_45212_1023456789.dbf');

EXEC DBMS_LOGMNR.START_LOGMNR(OPTIONS => DBMS_LOGMNR.DICT_FROM_ONLINE_CATALOG + DBMS_LOGMNR.COMMITTED_DATA_ONLY);
```

Generate the EXEC lines instead of typing them; spool, review, run:

```sql
SET HEAD OFF FEED OFF LINES 300 PAGES 0
SPOOL /tmp/lm_add.sql
SELECT 'EXEC DBMS_LOGMNR.ADD_LOGFILE(LOGFILENAME => ''' || name || ''', OPTIONS => DBMS_LOGMNR.'
       || CASE WHEN ROWNUM = 1 THEN 'NEW' ELSE 'ADDFILE' END || ');'
FROM  (SELECT name FROM v$archived_log
       WHERE dest_id = 1 AND thread# = 1 AND sequence# BETWEEN 45210 AND 45230
       ORDER BY sequence#);
SPOOL OFF
@/tmp/lm_add.sql
```

## 5. Verify, save output, end session

Check what is loaded before querying. `LOG_ID` is the sequence number, so a jump means a gap and silently missing changes.

```sql
SELECT log_id, filename, low_scn, high_scn, low_time, high_time
FROM   v$logmnr_logs ORDER BY log_id;
```

`V$LOGMNR_CONTENTS` is private to the session and re-reads every archive on each query. Copy it to a table once, then run all checks against that table:

```sql
CREATE TABLE lm_out AS
SELECT scn, timestamp, commit_timestamp, xid, username, os_username,
       machine_name, session_info, operation, seg_owner, seg_name,
       table_name, row_id, rollback, sql_redo, sql_undo
FROM   v$logmnr_contents;

EXEC DBMS_LOGMNR.END_LOGMNR;
```

Always call `END_LOGMNR` when done; it frees the session's PGA and the file handles. Drop `lm_out` after the investigation.

## 6. Query catalogue

All queries run against `lm_out`. Swap in `v$logmnr_contents` if you skipped the copy (slower, session must still be open).

**Overview: what kind of activity is in the window**

```sql
SELECT operation, COUNT(*) cnt
FROM   lm_out GROUP BY operation ORDER BY cnt DESC;
```

**Busiest tables**

```sql
SELECT seg_owner, table_name, operation, COUNT(*) cnt
FROM   lm_out
WHERE  operation IN ('INSERT','UPDATE','DELETE')
AND    seg_owner NOT IN ('SYS','SYSTEM')
GROUP  BY seg_owner, table_name, operation
ORDER  BY cnt DESC FETCH FIRST 20 ROWS ONLY;
```

**All DML on one table, with redo and undo**

```sql
SELECT scn, timestamp, username, operation, sql_redo, sql_undo
FROM   lm_out
WHERE  seg_owner = 'SCOTT' AND table_name = 'EMP'
AND    operation IN ('INSERT','UPDATE','DELETE')
ORDER  BY scn;
```

**DDL (create, alter, drop, truncate, grants)**

```sql
SELECT timestamp, username, os_username, machine_name, seg_owner, sql_redo
FROM   lm_out
WHERE  operation = 'DDL'
ORDER  BY scn;

-- truncates only
SELECT timestamp, username, sql_redo FROM lm_out
WHERE  operation = 'DDL' AND UPPER(sql_redo) LIKE 'TRUNCATE%';
```

**Who did it: activity by user, OS user, machine**

```sql
SELECT username, os_username, machine_name, operation, COUNT(*) cnt
FROM   lm_out
WHERE  operation IN ('INSERT','UPDATE','DELETE','DDL')
GROUP  BY username, os_username, machine_name, operation
ORDER  BY cnt DESC;
```

`USERNAME`, `OS_USERNAME` and `MACHINE_NAME` are only populated when supplemental logging was on at the time.

**Recover deleted rows: generate the undo script**

```sql
SELECT sql_undo || ';'
FROM   lm_out
WHERE  seg_owner = 'SCOTT' AND table_name = 'EMP'
AND    operation = 'DELETE'
ORDER  BY scn;
```

Run the undo in reverse SCN order (`ORDER BY scn DESC`) when reversing a mix of operations.

**Find a specific value in the changes**

```sql
SELECT scn, timestamp, username, operation, sql_redo
FROM   lm_out
WHERE  table_name = 'EMP'
AND    sql_redo LIKE '%"EMPNO" = ''7369''%';
```

**One transaction end to end (by XID)**

```sql
SELECT xid, COUNT(*) ops, MIN(timestamp) started, MAX(commit_timestamp) committed
FROM   lm_out
WHERE  operation IN ('INSERT','UPDATE','DELETE')
GROUP  BY xid ORDER BY ops DESC;

SELECT scn, operation, table_name, sql_redo
FROM   lm_out WHERE xid = HEXTORAW('0A001B00E4120000') ORDER BY scn;
```

**Rolled-back changes** (needs a session started without `COMMITTED_DATA_ONLY`)

```sql
SELECT timestamp, username, table_name, operation, sql_redo
FROM   lm_out WHERE rollback = 1;

SELECT operation, COUNT(*) FROM lm_out
WHERE operation IN ('START','COMMIT','ROLLBACK') GROUP BY operation;
```

**Activity per minute (spot the spike)**

```sql
SELECT TRUNC(timestamp,'MI') minute, operation, COUNT(*) cnt
FROM   lm_out
WHERE  operation IN ('INSERT','UPDATE','DELETE')
GROUP  BY TRUNC(timestamp,'MI'), operation
ORDER  BY minute;
```

**Things LogMiner could not decode**

```sql
SELECT operation, seg_owner, seg_name, COUNT(*) cnt
FROM   lm_out
WHERE  operation IN ('UNSUPPORTED','INTERNAL') OR seg_name LIKE 'OBJ#%'
GROUP  BY operation, seg_owner, seg_name;
```

## 7. Gotchas

| Symptom | Cause | Fix |
| --- | --- | --- |
| `OBJ# 12345` or `HEXTORAW(...)` instead of names | Table dropped/altered since the redo; online catalog no longer matches | Use a dictionary in redo: `DBMS_LOGMNR_D.BUILD(OPTIONS => DBMS_LOGMNR_D.STORE_IN_REDO_LOGS)` built before the change, then start with `DICT_FROM_REDO_LOGS` |
| UPDATE shows only ROWID, no column values | Supplemental logging was off when redo was generated | Enable it; old redo cannot be fixed |
| ORA-01291 missing logfile | Gap in the sequence range or file not at the registered path | Check `v$logmnr_logs`, restore the missing archive |
| ORA-01284 file cannot be opened | Wrong path or permissions on a manually added file | `ls -l` the path; file must be readable by the oracle user |
| Last few minutes missing | Changes still in online redo | `ALTER SYSTEM ARCHIVE LOG CURRENT;` before starting |
| Transaction partly missing | Started before `STARTTIME` with `COMMITTED_DATA_ONLY` | Widen the start time |
| Duplicate rows in output | Same sequence added from two destinations | Filter `dest_id = 1` |
| ORA-01323 / CONTINUOUS\_MINE errors on 19c | Option desupported | Use Process 1 Option B or Process 2 |
| Queries very slow | Every query on `v$logmnr_contents` re-reads all archives | Copy to `lm_out` once (section 5) |
