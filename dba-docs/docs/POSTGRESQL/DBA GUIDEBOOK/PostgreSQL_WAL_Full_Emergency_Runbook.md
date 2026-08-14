# PostgreSQL Emergency Runbook: Resolving pg_wal Disk Space Exhaustion

This runbook outlines the immediate diagnostics and mitigation steps when the PostgreSQL Write-Ahead Log (`pg_wal`) directory (formerly known as `pg_xlog` in PostgreSQL 9.6 and older) runs out of disk space, causing the database to crash and fail to start.

---

## 1. Symptoms of a Full pg_wal Directory

When the storage partition hosting `pg_wal` becomes 100% full, the PostgreSQL engine cannot write new WAL records and will automatically trigger a panic shutdown to prevent data corruption.

### Connection Failure Messages (When attempting to reconnect):
```text
psql: could not connect to server: No such file or directory
  Is the server running locally and accepting connections on Unix domain socket "/var/run/postgresql/.s.PGSQL.5432"?
```

### PostgreSQL System Log Messages (Critical Indicators):
```text
LOG: archiver process (PID 4103) exited with exit code 1
PANIC: could not write to file "pg_wal/waltemp.4111": No space left on device
LOG: server process (PID 4111) was terminated by signal 6: Aborted
FATAL: the database system is in recovery mode
LOG: database system was not properly shut down; automatic recovery in progress
LOG: redo starts at 29/8D242168
PANIC: could not write to file "pg_wal/waltemp.4920": No space left on device
LOG: startup process (PID 4920) was terminated by signal 6: Aborted
LOG: aborting startup due to startup process failure
```

---

## 2. Most Common Causes of pg_wal Accumulation

PostgreSQL accumulates `pg_wal` files when write-ahead log generation outpaces the database's ability to recycle or delete them. The most common causes are:

### Replication Bottlenecks
* **Stalled Replication Slots**: A standby server or a CDC tool (like Debezium) drops offline, but the replication slot remains active on the primary database. PostgreSQL will indefinitely retain all new WAL segments generated since the consumer went offline, waiting for it to reconnect and catch up.
* **Replication Lag**: High network latency, heavy read traffic bottlenecks on hot standbys, or underpowered replica hardware can cause the standby to fall too far behind the primary, delaying WAL recycling.
* **Excessive `wal_keep_size`**: Setting this parameter (or the older `wal_keep_segments`) too high forces the primary server to retain large amounts of WAL history for non-slot replicas, even if they are caught up.

### Archiving and Maintenance Failures
* **Failing `archive_command`**: If external archiving scripts fail (due to incorrect paths, network/VPN issues, or target storage exhaustion), Postgres blocks WAL deletion/recycling until files are safely archived.
* **Infrequent Checkpoints**: High `checkpoint_timeout` settings or large `max_wal_size` configurations cause PostgreSQL to wait longer before triggering checkpoints and recycling older WAL blocks.

### Workload Spikes
* **Heavy Write Activity**: Massive data loads, bulk inserts, or unoptimized batch jobs generate gigabytes of logs faster than background writers can process and clean them.
* **`full_page_writes` Overhead**: Heavy updates immediately following a checkpoint force Postgres to write full disk pages to the WAL, causing rapid volume expansion.

---

## 3. Troubleshooting & Resolution Steps (Reactive)

If your database has crashed and refuses to start due to a full disk, choose the most appropriate resolution strategy below.

> [!CAUTION]
> **NEVER delete active WAL files directly using `rm`.**
> Deleting arbitrary WAL files will cause data inconsistency and make the database unrecoverable. Follow the validated methods below.

---

### Method A: Resolve WAL Archiving Failures (If Applicable)
If WAL archiving (`archive_mode = on`) is configured, PostgreSQL will **not** remove or recycle WAL segments from `pg_wal` until they are successfully processed by the `archive_command`. If archiving fails or lags behind, WAL files will pile up indefinitely.

#### 1. Identify the Archiving Issue
Review the recent PostgreSQL log files for failed archive commands:
```text
LOG: archive command failed with exit code 1
DETAIL: The failed archive command was: gzip < pg_wal/0000000400000028000000CD > /archive/arc/0000000400000028000000CD
```

#### 2. Troubleshoot and Fix
* Check if the destination archive directory has run out of space.
* Verify that the `postgres` system user has proper write permissions on the archive path.
* Ensure the target mount point is active and accessible.

#### 3. Start the Database
Once the archiving path or command issue is fixed, start the PostgreSQL service:
```bash
pg_ctl start -D /path/to/pg_data
```
The database will recover, process the archived WAL logs, and automatically delete/recycle the obsolete files, reclaiming disk space.

---

### Method B: Temporary Relocation of `pg_wal` (Symlinking)
If you cannot add space to the partition immediately, you can move the entire WAL directory to a separate partition that has free space.

#### 1. Restrict Connections (Maintenance Mode)
Modify `pg_hba.conf` temporarily to prevent application connections while database maintenance is in progress:
```text
# Temporarily reject or restrict user connections
local   all             all                                     reject
host    all             all             0.0.0.0/0               reject
```

#### 2. Copy the WAL logs to the new location
Create a new directory on a partition with sufficient free space and copy the contents of `pg_wal` to it:
```bash
cp -rf /database/pgdata/pg_wal/* /mnt/new_disk/postgres/pg_wal/
```

#### 3. Backup and Remove the Original Directory
Rename the original directory:
```bash
mv /database/pgdata/pg_wal /database/pgdata/pg_wal_bkp
```

#### 4. Create the Symbolic Link
Create a symlink in the data directory pointing to the new WAL location:
```bash
ln -s /mnt/new_disk/postgres/pg_wal/ /database/pgdata/pg_wal
```

#### 5. Start the Database & Verify
Start the database service and verify that new WAL logs are being created in the new location:
```bash
pg_ctl start -D /database/pgdata
```
If PostgreSQL starts successfully and runs without errors, you can safely delete the backup:
```bash
rm -rf /database/pgdata/pg_wal_bkp
```

#### 6. Revert Maintenance Mode
Restore the original rules in `pg_hba.conf` and reload the configuration.

---

### Method C: Delete the Emergency Dummy File
If you previously followed proactive guidelines and pre-allocated an emergency space-reserve dummy file inside `pg_wal` (or on the same mount point), you can delete it to quickly reclaim space, start the database, and trigger a cleanup checkpoint.

#### 1. Delete the Reserve File
```bash
rm /database/pgdata/pg_wal/ONLY_DELETE_THIS_DUMMY_FILE_IN_A_POSTGRES_EMERGENCY
```

#### 2. Start PostgreSQL
```bash
pg_ctl start -D /database/pgdata
```

#### 3. Run a Checkpoint
Connect to the database and trigger a checkpoint to force PostgreSQL to immediately recycle unused WAL segments and free up space:
```bash
psql -d postgres -c "CHECKPOINT;"
```


### How to Configure Method C (Pre-allocation in Healthy State)
To configure this safeguard during a healthy database state (or to recreate it after recovering from an emergency), execute the following commands as the `postgres` user:

```bash
# Navigate to the pg_wal directory
cd /database/pgdata/pg_wal

# Pre-allocate a 300MB reserve file (block size 1MB, count 300)
dd if=/dev/zero of=ONLY_DELETE_THIS_DUMMY_FILE_IN_A_POSTGRES_EMERGENCY bs=1M count=300
```

This pre-allocates contiguous physical blocks on disk. If the database volume hits 100% usage and PostgreSQL halts, deleting this file instantly frees up 300MB of space, providing enough headroom for PostgreSQL to boot up and run a checkpoint to clean up the actual WAL files.

---

### Method D: Safe Manual WAL Cleanup using `pg_archivecleanup`
If you cannot start the database to perform a checkpoint, you must find which WAL files are older than the active checkpoint and delete only those.

#### 1. Identify the Latest Checkpoint REDO WAL File
Execute `pg_controldata` pointing to your data directory and locate the REDO WAL file name:
```bash
pg_controldata -D /database/pgdata
```
Look for this line in the output:
```text
Latest checkpoint's REDO WAL file:   000000010000000F00000026
```

#### 2. Run a Dry Run of the Cleanup
Use `pg_archivecleanup` with the `-n` flag to preview which files are older than the REDO WAL file and will be safely deleted:
```bash
pg_archivecleanup -n /database/pgdata/pg_wal 000000010000000F00000026
```

#### 3. Perform the Deletion
Once verified, execute the command with the `-d` (delete) flag to clean up the files:
```bash
pg_archivecleanup -d /database/pgdata/pg_wal 000000010000000F00000026
```

#### 4. Start the Database and Take a Backup
Start the PostgreSQL server. Once running, **take a fresh cluster backup** immediately to establish a clean recovery baseline.

---

## 4. Proactive Best Practices

To prevent `pg_wal` exhaustion in production, implement the following guardrails:

### 1. Monitor Disk Space and Alert Early
Set up disk usage monitoring for the PostgreSQL partitions. Configure email/SMS alerts to fire when disk usage hits **70%** (Warning) and **90%** (Critical).

### 2. Compress Archived WAL Logs
Reduce archive storage requirements by compressing WAL files inside your `archive_command`:
```ini
archive_command = 'gzip < %p > /archive_dir/%f'
```
*Note: If you compress files, your `restore_command` during recovery must decompress them:*
```ini
restore_command = 'gunzip < /archive_dir/%f > %p'
```

### 3. Pre-Allocate an Emergency Space-Reserve File
Create a `300MB` (or larger) dummy file in the `pg_wal` directory. This file does not serve any transactional purpose but acts as a space buffer that can be deleted to recover from a `disk full` shutdown scenario:
```bash
dd if=/dev/zero of=/database/pgdata/pg_wal/ONLY_DELETE_THIS_DUMMY_FILE_IN_A_POSTGRES_EMERGENCY bs=1MB count=300
```
