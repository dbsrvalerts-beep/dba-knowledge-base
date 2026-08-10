# Oracle Moving Datafiles To Another Location

- **Scenario:** Over time, the database has grown substantially, and the current storage directory is running out of space, leading to performance issues. If the current directory runs out of space then database will shutdown To address this situation, we need to move the database's datafiles to a new storage location. In the following document, we will be moving 3 datafiles files from the D drive to the E drive.
## Steps to move Oracle datafiles to different locations:

**_Note:_** _Before starting the process make sure to stop all Ginesys application services_.

### Step 1: Stop/Shutdown Oracle database services. A graceful shutdown ensures that ongoing transactions are completed or rolled back, preventing data inconsistencies and potential corruption.

### Step 2: Make a proper directory structure at another location as per your requirement.

### Step 3: Using the operating system's file management tools, copy the datafiles from the current storage directory to the new disk array. This process involves careful verification of each file to ensure data integrity during the copy operation.

### Step 4: Startup Oracle database in the mount stage.

```sql
SQL> startup mount;
ORA-32004: obsolete or deprecated parameter(s) specified for RDBMS instance
ORACLE instance started.
Total System Global Area 5.3687E+10 bytes
Fixed Size 2939560 bytes
Variable Size 6039799128 bytes
Database Buffers 4.7513E+10 bytes
Redo Buffers 131276800 bytes
Database mounted.
```

### Step 5: Issue the following command to update Oracle metadata.

```sql
alter database rename file 'D:\Oracle\Database\oradata\GINESYS\USERS05.DBF' to 'E:\Oracle\Database\oradata\GINESYS\USERS05.DBF';
alter database rename file 'D:\Oracle\Database\oradata\GINESYS\USERS06.DBF' to 'E:\Oracle\Database\oradata\GINESYS\USERS06.DBF';
alter database rename file 'D:\Oracle\Database\oradata\GINESYS\USERS07.DBF' to 'E:\Oracle\Database\oradata\GINESYS\USERS07.DBF';
```

### Step 6: Open the database in read/write mode.

```sql
SQL> alter database open;
```

### Step 7: Verify if all datafiles have been moved properly and are accessible via Oracle Dynamic View v\$datafile

**_Note:_** _Once all steps have been successfully completed start Ginesys application services._