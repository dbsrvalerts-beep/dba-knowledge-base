# PGGDBA MONTHLY QUERIES

This document contains PostgreSQL queries used for monthly database size, growth analysis, and segment monitoring.

## Table Structures

* **Database Size**: `public.databasesize_information`
* **Objects Size**: `public.object_segment_{instance_name}`
* **monthly purge**: `public.monthly_purge_log`
* **walsize_monitor**: `public.walsize_monitor`

---

## 1. Database Size

```sql
SELECT INSTANCE_NAME,
       LOGDATE,
       DATABASE,
       SIZE_GB AS SIZE
FROM DATABASESIZE_INFORMATION
WHERE LOGDATE::date = CURRENT_DATE::date
  AND DATABASE like '%-PROD'
  AND DATABASE not like 'ZZZ%'
  AND instance_name='SELFHOSTED4'
ORDER BY SIZE_MB DESC;
```

---

## 2. Database Growth Comparison

```sql
SELECT 
    t."Instance_Name",
    t.database,
    MAX(t."NEWDATE") AS "NEWDATE",
    round(SUM(t.newsize)/1024,2) AS newsize, 
    MAX(t."OLDDATE") AS "OLDDATE",
    round(SUM(t.oldsize)/1024,2) AS oldsize, 
    round(SUM(t.newsize - t.oldsize)/1024,2) AS diff
FROM (
    SELECT 
        n.instance_name AS "Instance_Name",
        n.database,
        n.logdate::date AS "NEWDATE",
        NULL::date AS "OLDDATE",
        COALESCE(n.size_mb, 0) AS newsize,
        0 AS oldsize
    FROM public.databasesize_information AS n
    WHERE n.logdate::date = '2026-02-09'
      AND n.instance_name = 'EDB1'
UNION ALL
    SELECT 
        o.Instance_Name,
        o.database,
        NULL::date AS "NEWDATE",
        o.logdate::date AS "OLDDATE",
        0 AS newsize,
        COALESCE(o.size_mb, 0) AS oldsize
    FROM public.databasesize_information AS o
    WHERE o.logdate::date = '2025-12-19'
     AND o.instance_name = 'EDB1'
) t
WHERE t.database LIKE 'XPOSE-PROD'
GROUP BY t.database, t."Instance_Name"
HAVING SUM(t.newsize - t.oldsize) <> 0
ORDER BY diff DESC;
```

---

## 3. PG Top Size Consuming Segments

```sql
SELECT instance_name,
       logdate,
       "database_name",
       "schema_name",
       "object_name",
       "object_type",
       "object_size",
       "size_mb" 
FROM public.object_segment_selfhosted4 
WHERE logdate::date='2025-11-30' 
  AND "size_mb">1000 
ORDER BY "size_mb" DESC;
```

---

## 4. Object Growth Comparison

```sql
SELECT 
    t."Instance_Name",
    t."database_name",
    t."object_name",
    MAX(t."NEWDATE") AS "NEWDATE",
    SUM(t.newsize) AS newsize, 
    MAX(t."OLDDATE") AS "OLDDATE",
    SUM(t.oldsize) AS oldsize, 
    SUM(t.newsize - t.oldsize) AS diff
FROM (
    SELECT 
        n.instance_name AS "Instance_Name",
        n.database_name,
        n.object_name,
        n.logdate::date AS "NEWDATE",
        NULL::date AS "OLDDATE",
        COALESCE(n.size_mb, 0) AS newsize,
        0 AS oldsize
    FROM public.object_segment_edb1 AS n
    WHERE n.logdate::date = '2026-02-09'
      AND n.instance_name = 'EDB1'
UNION ALL
    SELECT 
        o.Instance_Name,
        o.database_name,
        o.object_name,
        NULL::date AS "NEWDATE",
        o.logdate::date AS "OLDDATE",
        0 AS newsize,
        COALESCE(o.size_mb, 0) AS oldsize
    FROM public.object_segment_edb1 AS o
    WHERE o.logdate::date = '2025-12-21'
     AND o.instance_name = 'EDB1'
) t
WHERE t.database_name LIKE 'XPOSE-PROD'
GROUP BY t.object_name, t."Instance_Name", t."database_name"
HAVING SUM(t.newsize - t.oldsize) <> 0
ORDER BY diff DESC;
```

---

## 5. Check Cleanup Log of `object_segment_{instance_name}` (Previous Month)

```sql
SELECT * FROM monthly_purge_log;
```

## 6. Check Wal Generation data [Base table]

```sql
select * from public.walsize_monitor;
```

## 7. Check Wal Generation data Frequncy Map [View]
```sql
SELECT * 
FROM public.wal_generation_frequency_map
where instance_name='PGPAAS1'
ORDER BY log_day DESC;
```


