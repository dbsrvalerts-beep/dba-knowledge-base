# Oracle Datafile Corruption Issue (ORA-00600)

## Scenario:

The database team received a ticket concerning a datafile corruption issue in their database.

1. The database name is 'GINERS' and it is currently in NOARCHIVE mode.
2. Subsequent investigation revealed that certain data files were found to be missing from the database views but were present in Oradata.
3. After finding the datafile missing issue, perform the following step to recover the database :

### Step 1: At the initial stage, the database was already in open mode:-

```sql
SQL> SELECT NAME,OPEN_MODE FROM V\$DATABASE;

NAME OPEN_MODE

\--------- ----------

GINERS READ WRITE
```

### Step 2: Performing a database shutdown and subsequent restart to replicate the issue in the database.

```sql
SQL> SHUTDOWN IMMEDIATE;

Database closed.

Database dismounted.

ORACLE instance shut down.

SQL> STARTUP;

ORACLE instance started.

Total System Global Area 536870912 bytes

Fixed Size 1291652 bytes

Variable Size 436210300 bytes

Database Buffers 92274688 bytes

Redo Buffers 7094272 bytes

ORA-00600: internal error code, arguments: \[kccpb_sanity_check_2\], \[18844\],

\[18843\], \[0x0\], \[\], \[\], \[\], \[\]
```

**_Note:-_**_ORA-00600: This is an internal error message for Oracle program exceptions. It indicates that a process has met a low-level, unexpected condition._

Various causes of this message include:

- time-outs
- file corruption
- failed data checks in memory
- hardware, memory, or I/O errors
- incorrectly restored files

**Note:** Database started in no mount stage only and cannot be opened further.

### Step 3: Reconnect to the SYS user and create a backup of the parameter file

```sql
SQL> CONN SYS/SYSPWD AS SYSDBA

Connected.

SQL> CREATE PFILE FROM SPFILE;

File created.
```

### Step 4: Restart the database again in nomount stage to recreate the control file.

```sql
SQL> SHUT IMMEDIATE;

ORA-01507: Database not mounted

ORACLE instance shut down.

SQL> STARTUP NOMOUNT

ORACLE instance started.

Total System Global Area 536870912 bytes

Fixed Size 1291652 bytes

Variable Size 444598908 bytes

Database Buffers 83886080 bytes

Redo Buffers 7094272 bytes
```

### Step 5: Recreate control file

**_Note:_** You have to be in mount stage to create backup of existing control file to trace (backup of control file trace can help to rewrite the content of control file as per your need, but in this case database cannot be opened further from nomount stage so we have to manually write the control file creation command. Manual creation of control file require proper details related to datafiles, redo log files.

```sql
SQL> CREATE CONTROLFILE REUSE DATABASE "GINERS" NORESETLOGS NOARCHIVELOG

MAXLOGFILES 16

MAXLOGMEMBERS 3

MAXDATAFILES 100

MAXINSTANCES 8

MAXLOGHISTORY 709

LOGFILE

GROUP 1 ('D:\\ORACLE\\ORADATA\\GINERS\\REDO01.LOG',

'D:\\ORACLE\\ORADATA\\GINERS\\REDO01A.LOG') SIZE 100M,

GROUP 2 ('D:\\ORACLE\\ORADATA\\GINERS\\REDO02.LOG',

'D:\\ORACLE\\ORADATA\\GINERS\\REDO02A.LOG') SIZE 100M,

GROUP 3 ('D:\\ORACLE\\ORADATA\\GINERS\\REDO03.LOG',

'D:\\ORACLE\\ORADATA\\GINERS\\REDO03A.LOG') SIZE 100M,

GROUP 4 ('D:\\ORACLE\\ORADATA\\GINERS\\REDO04.LOG',

'D:\\ORACLE\\ORADATA\\GINERS\\REDO04A.LOG') SIZE 100M,

GROUP 5 ('D:\\ORACLE\\ORADATA\\GINERS\\REDO05.LOG',

'D:\\ORACLE\\ORADATA\\GINERS\\REDO05A.LOG') SIZE 100M,

GROUP 6 ('D:\\ORACLE\\ORADATA\\GINERS\\REDO06.LOG',

'D:\\ORACLE\\ORADATA\\GINERS\\REDO06A.LOG') SIZE 100M

\-- STANDBY LOGFILE

DATAFILE

'D:\\Oracle\\Oradata\\GINERS\\SYSTEM01.DBF',

'D:\\Oracle\\Oradata\\GINERS\\UNDOTBS01.DBF',

'D:\\Oracle\\Oradata\\GINERS\\SYSAUX01.DBF',

'D:\\Oracle\\Oradata\\GINERS\\USERS01.DBF',

'D:\\Oracle\\Oradata\\GINERS\\ERSSTAGING',

'D:\\Oracle\\Oradata\\GINERS\\ERSDATA',

'D:\\Oracle\\Oradata\\GINERS\\ERSREPORTS',

'D:\\Oracle\\Oradata\\GINERS\\ERSINDEX',

'D:\\Oracle\\Oradata\\GINERS\\INDX01.DBF'

CHARACTER SET WE8MSWIN1252;

control file created
```

### Step 6: After the creation of the control file the database automatically shifts to mount stage so open the database.

```sql
SQL> ALTER DATABASE OPEN;

ALTER DATABASE OPEN

ERROR at line 1:

ORA-01113: file 1 needs media recovery

ORA-01110: data file 1: 'D:\\ORACLE\\ORADATA\\GINERS\\SYSTEM01.DBF'
```

### Step 7: Database still requires recovery to open in a consistent stage.

```sql
SQL> RECOVER DATAFILE 1;

Media recovery complete.

SQL> ALTER DATABASE OPEN;

ERROR at line 1:

ORA-01113: file 2 needs media recovery

ORA-01110: data file 2: 'D:\\ORACLE\\ORADATA\\GINERS\\UNDOTBS01.DBF'

SQL> RECOVER DATAFILE 2;

Media recovery complete.

SQL> ALTER DATABASE OPEN;

ERROR at line 1:

ORA-01113: file 3 needs media recovery

ORA-01110: data file 3: 'D:\\ORACLE\\ORADATA\\GINERS\\SYSAUX01.DBF'

SQL> RECOVER DATAFILE 3;

Media recovery complete.

SQL> ALTER DATABASE OPEN;

ERROR at line 1:

ORA-01113: file 4 needs media recovery

ORA-01110: data file 4: 'D:\\ORACLE\\ORADATA\\GINERS\\INDX01.DBF'

SQL> RECOVER DATAFILE 4;

Media recovery complete.

SQL> ALTER DATABASE OPEN;

ERROR at line 1:

ORA-01113: file 5 needs media recovery

ORA-01110: data file 5: 'D:\\ORACLE\\ORADATA\\GINERS\\USERS01.DBF'

SQL> RECOVER DATAFILE 5;

Media recovery complete.

SQL> ALTER DATABASE OPEN;

ERROR at line 1:

ORA-01113: file 6 needs media recovery

ORA-01110: data file 6: 'D:\\ORACLE\\ORADATA\\GINERS\\ERSSTAGING'

SQL> RECOVER DATAFILE 6;

Media recovery complete.

SQL> ALTER DATABASE OPEN;

ERROR at line 1:

ORA-01113: file 7 needs media recovery

ORA-01110: data file 7: 'D:\\ORACLE\\ORADATA\\GINERS\\ERSDATA'

SQL> RECOVER DATAFILE 7;

Media recovery complete.

SQL> ALTER DATABASE OPEN;

ERROR at line 1:

ORA-01113: file 8 needs media recovery

ORA-01110: data file 8: 'D:\\ORACLE\\ORADATA\\GINERS\\ERSREPORTS'

SQL> RECOVER DATAFILE 8;

Media recovery complete.

SQL> ALTER DATABASE OPEN;

ERROR at line 1:

ORA-01113: file 9 needs media recovery

ORA-01110: data file 9: 'D:\\ORACLE\\ORADATA\\GINERS\\ERSINDEX'

SQL> RECOVER DATAFILE 9;

Media recovery complete.
```

_Step8: Open Database_

```sql
SQL> ALTER DATABASE OPEN;

Database altered.

NAME OPEN_MODE

\--------- ----------

GINERS READ WRITE
```

### Step 9: After opening the database, recreate all the temporary tablespaces

```sql
SQL> ALTER TABLESPACE TEMP ADD TEMPFILE 'D:\\ORACLE\\ORADATA\\GINERS\\TEMP01.DBF';

Tablespace altered.

SQL> ALTER TABLESPACE TEMP02 ADD TEMPFILE 'D:\\ORACLE\\ORADATA\\GINERS\\TEMP02' REUSE;

Tablespace altered.

SQL> ALTER TABLESPACE TEMP03 ADD TEMPFILE 'D:\\ORACLE\\ORADATA\\GINERS\\TEMP03' REUSE;

Tablespace altered.

SQL> ALTER TABLESPACE TEMP01 ADD TEMPFILE 'D:\\ORACLE\\ORADATA\\GINERS\\TEMP01' REUSE;

Tablespace altered.

SQL> ALTER TABLESPACE TEMP04 ADD TEMPFILE 'D:\\ORACLE\\ORADATA\\GINERS\\TEMP04' REUSE;

Tablespace altered.
```