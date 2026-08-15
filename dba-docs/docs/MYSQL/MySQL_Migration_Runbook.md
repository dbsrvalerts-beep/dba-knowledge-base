# MySQL Migration Runbook

### Direct-from-Source mydumper/myloader Migration with Binlog Position-Based Data-In Replication
Source Platform: Azure Database for MySQL Flexible Server [Central India]
Target Platform: Azure Database for MySQL Flexible Server [Jio West]
This runbook dumps directly from the live source using mydumper (no intermediate replica, no read-lock required), and links replication into the Azure Flexible Server target using the binlog file + position captured in mydumper's own metadata file. This version incorporates production-run fixes for system-schema handling, large-table chunking, and long-query-guard behavior.
## Pre-migration Tasks

#### 1. Remove Duplicate Entries
Execute the following queries to check and remove duplicate entries:

```sql
SELECT *
FROM tenant_db_8432.pre_order_discounts
WHERE pre_order_id = '411618753';
DELETE FROM tenant_db_8432.pre_order_discounts
WHERE id = 460526312;
```

```sql
SELECT *
FROM tenant_db_8545.pre_order_discounts
WHERE pre_order_id = '2174466571';
DELETE FROM tenant_db_8545.pre_order_discounts
WHERE id = 1532931990;
```

#### 2. Database Table Cleanup Tasks
Perform the following cleanup operations on the source:
- **Clean up `primary_db`**: Truncate/remove old data from `queue_results` and `cron_history` tables.
- **Clean up `deleted_rows_primarydb`**: Truncate/remove logs from `btadapter_db.files_logs` table.
- **Tenant Cleanup**: Clean up archived tables matching `archived_skus_warehouses_*` from all tenant databases.

#### 3. Database Analysis
Once the data cleanup and truncate operations are complete, analyze the databases using the helper script below to optimize indexes and update statistics:


```bash
#!/bin/bash
#
# analyze_all_dbs.sh
# Runs ANALYZE TABLE (via mysqlcheck) across every database on an Azure MySQL Flexible Server.
# Prompts for password once, reuses it for all connections. Throttled with a delay between DBs.
# Logs overall start/end timestamps plus per-database start/end/duration.

set -euo pipefail

# ---- CONFIG ----
HOST="your-server-name.mysql.database.azure.com"
USER="your_admin_user"
SLEEP_SECONDS=2
LOG_FILE="analyze_all_$(date +%Y%m%d_%H%M%S).log"
# ----------------

SCRIPT_START_TS=$(date '+%Y-%m-%d %H:%M:%S')
SCRIPT_START_EPOCH=$(date +%s)

# Prompt for password once (hidden input), reused for every connection below
read -s -p "Enter MySQL password for ${USER}: " MYSQL_PWD
export MYSQL_PWD
echo ""

echo "Script started at: $SCRIPT_START_TS" | tee -a "$LOG_FILE"
echo "Fetching database list..." | tee -a "$LOG_FILE"

DATABASES=$(mysql -h "$HOST" -u "$USER" -N -e "SHOW DATABASES;" | \
    grep -vE "^(information_schema|performance_schema|mysql|sys)$")

TOTAL=$(echo "$DATABASES" | wc -l)
COUNT=0

echo "Found $TOTAL databases to analyze." | tee -a "$LOG_FILE"
echo "Logging to: $LOG_FILE"
echo "----------------------------------------" | tee -a "$LOG_FILE"

for db in $DATABASES; do
    COUNT=$((COUNT + 1))
    DB_START_TS=$(date '+%Y-%m-%d %H:%M:%S')
    DB_START_EPOCH=$(date +%s)

    echo "[$COUNT/$TOTAL] Analyzing: $db | Start: $DB_START_TS" | tee -a "$LOG_FILE"

    mysqlcheck -h "$HOST" -u "$USER" --analyze "$db" >> "$LOG_FILE" 2>&1
    DB_EXIT_CODE=$?

    DB_END_TS=$(date '+%Y-%m-%d %H:%M:%S')
    DB_END_EPOCH=$(date +%s)
    DB_DURATION=$((DB_END_EPOCH - DB_START_EPOCH))

    if [ $DB_EXIT_CODE -eq 0 ]; then
        echo "  -> OK | End: $DB_END_TS | Duration: ${DB_DURATION}s" | tee -a "$LOG_FILE"
    else
        echo "  -> FAILED | End: $DB_END_TS | Duration: ${DB_DURATION}s (see $LOG_FILE for details)" | tee -a "$LOG_FILE"
    fi

    sleep "$SLEEP_SECONDS"
done

# Unset password from environment once done
unset MYSQL_PWD

SCRIPT_END_TS=$(date '+%Y-%m-%d %H:%M:%S')
SCRIPT_END_EPOCH=$(date +%s)
TOTAL_DURATION=$((SCRIPT_END_EPOCH - SCRIPT_START_EPOCH))
TOTAL_DURATION_HMS=$(printf '%02d:%02d:%02d' $((TOTAL_DURATION/3600)) $((TOTAL_DURATION%3600/60)) $((TOTAL_DURATION%60)))

echo "----------------------------------------" | tee -a "$LOG_FILE"
echo "Script started at: $SCRIPT_START_TS" | tee -a "$LOG_FILE"
echo "Script ended at:   $SCRIPT_END_TS" | tee -a "$LOG_FILE"
echo "Total duration:    $TOTAL_DURATION_HMS (${TOTAL_DURATION}s)" | tee -a "$LOG_FILE"
echo "Done. $COUNT databases processed. Full log: $LOG_FILE"
```

## Step 1: Source Server Prerequisites
Confirm binary logging is enabled:
```sql
SHOW VARIABLES LIKE 'log_bin';
```
If OFF and the source is on-premises/VM with config-file access:
Note: It will be by default on in Azure Flexi Server server parameters. Below Steps works for On-prem VM
```ini
[mysqld]
log-bin=mysql-bin.log
```
```bash
sudo systemctl restart mysqld
```
Match case-sensitivity behavior to the Azure default (required for Data-in Replication to work correctly — commonly overlooked):

```sql
SET GLOBAL lower_case_table_names = 1;
```
Set binary log expiry on the Primary to control how long binlogs are retained:
```bash
binlog_expire_logs_seconds: 172800   -- 48 hours
```

## Step 2: Alter Existing Users and Create the Replication User
```sql
ALTER USER 'read_user'@'%' IDENTIFIED BY 'Ginesys@01';
ALTER USER 'btadmin'@'%' IDENTIFIED BY 'qs$3?j@*CA6!#Dy';
 
CREATE USER 'syncuser'@'%' IDENTIFIED BY 'yourpassword' REQUIRE SSL;
GRANT REPLICATION SLAVE ON *.* TO 'syncuser'@'%';
FLUSH PRIVILEGES;
```
REQUIRE SSL is recommended since this account can connect from any host (@'%').

## Step 3: Create the Flexible Server Target
Provision the Azure Database for MySQL Flexible Server instance that will act as the target before dumping anything. Manually recreate any required user accounts and privileges on it — Data-in Replication does not replicate user accounts.

## Step 4: Run the mydumper Backup Script Against the Live Source
Full production run script — backs up all tenants and all tables, excluding system schemas.
```bash
#!/bin/bash
############################################################
# Script Name : mydumper_backup.sh
# Purpose     : MySQL Full Backup using MyDumper
#               (Full production run — all tenants, all tables)
############################################################
 
# Variables
HOST="bt-26-jul-2026.mysql.database.azure.com"
USER="btadmin"
PASSWORD='qs$3?j@*CA6!#Dy'
OUTPUT_DIR="/u01/backup/mydump"
LOG_FILE="/u01/backup/dump.log"
DB_LIST_FILE="/u01/backup/db_list.txt"
THREADS=32
 
# Create backup directory
mkdir -p "${OUTPUT_DIR}"
 
# Function for timestamp
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}
 
echo "======================================================" | tee -a "${LOG_FILE}"
echo "Backup Started  : $(timestamp)" | tee -a "${LOG_FILE}"
echo "Host            : ${HOST}" | tee -a "${LOG_FILE}"
echo "Output Location : ${OUTPUT_DIR}" | tee -a "${LOG_FILE}"
echo "Threads         : ${THREADS}" | tee -a "${LOG_FILE}"
echo "======================================================" | tee -a "${LOG_FILE}"
 
# Generate explicit database list, excluding all system schemas
# (sys, mysql, performance_schema, information_schema).
mysql -h "${HOST}" -u "${USER}" -p"${PASSWORD}" -N -e \
  "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME NOT IN ('sys','mysql','performance_schema','information_schema');" \
  > "${DB_LIST_FILE}"
 
DB_LIST=$(paste -sd',' "${DB_LIST_FILE}")
 
echo "Databases to backup: $(wc -l < ${DB_LIST_FILE})" | tee -a "${LOG_FILE}"
echo "======================================================" | tee -a "${LOG_FILE}"
 
START_TIME=$(date +%s)
 
set +e
mydumper \
    --defaults-file=/etc/mydumper.cnf \
    --host="${HOST}" \
    --user="${USER}" \
    --password="${PASSWORD}" \
    -G -E -R \
    --database="${DB_LIST}" \
    --outputdir="${OUTPUT_DIR}" \
    --threads="${THREADS}" \
    --rows=1000000 \
    --build-empty-files \
    --complete-insert \
    --trx-tables \
    --chunk-filesize=100 \
    --kill-long-queries \
    --long-query-guard=10800 \
    --logfile="${LOG_FILE}" \
    -v 3
STATUS=$?
set -e
 
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
 
echo "======================================================" | tee -a "${LOG_FILE}"
if [ ${STATUS} -eq 0 ]; then
    echo "Backup Status   : SUCCESS" | tee -a "${LOG_FILE}"
else
    echo "Backup Status   : FAILED" | tee -a "${LOG_FILE}"
fi
echo "Backup Finished : $(timestamp)" | tee -a "${LOG_FILE}"
echo "Elapsed Time    : ${ELAPSED} seconds" | tee -a "${LOG_FILE}"
echo "Exit Code       : ${STATUS}" | tee -a "${LOG_FILE}"
echo "======================================================" | tee -a "${LOG_FILE}"
 
exit ${STATUS}
```

### Fixes Incorporated in This Version (Change Log)

| Fix / Parameter | Description / Impact |
| --- | --- |
| `--defaults-file=/etc/mydumper.cnf` | Picks up standard session variables (`max_execution_time=0`, etc.). |
| `--rows=1000000` | Forces explicit row-chunking on large tables. This fixed the infinite-spin stall previously seen on the `orders` table. |
| `--trx-tables` | The 0.18.1-correct replacement for the deprecated `--trx-consistency-only` / `--lock-all-tables` path. Still only a brief `FLUSH TABLES WITH READ LOCK` &rarr; snapshot &rarr; unlock; no sustained lock is held. |
| `--long-query-guard=10800` | Replaces the earlier bare `--kill-long-queries` (using an explicit value) — this fixed the repeating "SET SESSION LONG-QUERY-GUARD" log-spam loop. |
| `--database="${DB_LIST}"` | Replaces the earlier `--regex='^(?!(sys\.))'` approach. The regex only filtered table-level dumping, but `mydumper` still attempted schema-level operations (e.g. `SHOW EVENTS`) against `sys`, causing an "Access denied ... database 'sys'" failure and a non-zero exit code. An explicit `--database` list means `mydumper` never touches these schemas at all: no partial `sys` files, and no `myloader` `CREATE DATABASE sys` failure downstream either. |

> [!NOTE]
> **Consistency Mechanism Note**: `--trx-tables` takes a consistent InnoDB snapshot via a single transaction, which is what allows this to run safely against a live server without a sustained `FLUSH TABLES WITH READ LOCK` or setting `read_only=ON` — no production write-freeze and no intermediate replica required.

## Step 5: Read the Metadata File — the Consistency Anchor
```bash
cat /u01/backup/mydump/metadata
```
Expected contents:
[master]
Log_File = mysql-bin.000004
Pos = 15524
Executed_Gtid_Set =
For this runbook, only Log_File and Pos are used (binlog position-based reconnection). Copy this file somewhere safe before proceeding — these two values are required in Step 9 and must correspond exactly to the moment this dump was taken.

## Step 6: No Transfer Required — Single Jumpbox for Dump and Restore
A jumpbox VM is used to run both mydumper (Step 4) and myloader (Step 8) from the same machine, against the source and destination servers respectively over the network. Since the dump output already lands locally on this jumpbox, no rsync/file transfer step is required — myloader reads directly from the same directory mydumper wrote to.
Ensure the jumpbox has enough local storage to hold the full dump output, sized against the cluster's actual data volume.
Confirm the jumpbox has network connectivity to both the source and destination MySQL endpoints (firewall/NSG rules permitting outbound 3306 to both).

## Step 7: Set Binlog Expiry on the Destination Before Restore
Before running myloader, reduce the destination's binary log retention so the restore does not generate and retain an unnecessarily large volume of binlog data purely from the bulk import itself.
```sql
SET GLOBAL binlog_expire_logs_seconds = 3600;   -- 1 hour, restore-time only
Why this matters:
A full myloader restore writes every inserted row through the destination's own binary log (needed to eventually replicate onward / support PITR). At full data volume, this can generate a very large amount of binlog in a short window. A short retention window during the restore prevents this from accumulating and consuming excessive storage, since none of it needs to be kept for replication purposes yet — replication back to this destination is only established afterward, in Step 9.
Revert this to the intended steady-state production value once the restore completes and before Step 9 (linking replication) — leaving it this short permanently would undermine the destination's own future point-in-time recovery capability.
SET GLOBAL binlog_expire_logs_seconds = 172800;   -- restore to normal retention, e.g. 48 hours
```

## Step 8: Restore with myloader onto the Flexible Server Target
```bash
#!/bin/bash
############################################################
# Script Name : myloader_restore.sh
# Purpose     : Restore MyDumper export to Azure Database for
#               MySQL Flexible Server (Jio India West target)
############################################################
 
# Variables
HOST="browntape-03feb2025-staging-mig.mysql.database.azure.com"   # <-- target server FQDN
USER="btadmin"
PASSWORD='qs$3?j@*CA6!#Dy'                                     # <-- match target admin password
INPUT_DIR="/u01/backup/mydump"                             # <-- must match mydumper's OUTPUT_DIR
LOG_FILE="/u01/backup/restore.log"
THREADS=100
 
# Create log directory if needed
mkdir -p "$(dirname "${LOG_FILE}")"
 
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}
 
echo "======================================================" | tee -a "${LOG_FILE}"
echo "Restore Started : $(timestamp)" | tee -a "${LOG_FILE}"
echo "Target Host     : ${HOST}" | tee -a "${LOG_FILE}"
echo "Source Dir      : ${INPUT_DIR}" | tee -a "${LOG_FILE}"
echo "Threads         : ${THREADS}" | tee -a "${LOG_FILE}"
echo "======================================================" | tee -a "${LOG_FILE}"
 
START_TIME=$(date +%s)
 
############################################################
# RESTORE
############################################################
set +e
myloader \
    --defaults-file=/etc/mydumper.cnf \
    --host="${HOST}" \
    --user="${USER}" \
    --password="${PASSWORD}" \
    --directory="${INPUT_DIR}" \
    --threads="${THREADS}" \
    --innodb-optimize-keys \
    --overwrite-tables \
    --source-data=0 \
    --queries-per-transaction=50000 \
    --logfile="${LOG_FILE}" \
    -v 3
STATUS=$?
set -e
 
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
 
echo "======================================================" | tee -a "${LOG_FILE}"
if [ ${STATUS} -eq 0 ]; then
    echo "Restore Status  : SUCCESS" | tee -a "${LOG_FILE}"
else
    echo "Restore Status  : FAILED" | tee -a "${LOG_FILE}"
fi
echo "Restore Finished: $(timestamp)" | tee -a "${LOG_FILE}"
echo "Elapsed Time    : ${ELAPSED} seconds" | tee -a "${LOG_FILE}"
echo "Exit Code       : ${STATUS}" | tee -a "${LOG_FILE}"
echo "======================================================" | tee -a "${LOG_FILE}"
 
exit ${STATUS}
```

## Step 9: Link Replication Using the Binlog Position from Step 5
```sql
CALL mysql.az_replication_change_master(
  '<source_host>', 'syncuser', 'yourpassword', 3306,
  'mysql-bin.000004', 15524, ''
);
```

### Parameters, in order

| Parameter | Description |
| --- | --- |
| `<source_host>` | Hostname/FQDN of the source server. |
| `'syncuser'` | The replication user created in Step 2. |
| `'yourpassword'` | Its password. |
| `3306` | MySQL port. |
| `'mysql-bin.000004'` | The exact Log_File value from the Step 5 metadata file. |
| `15524` | The exact Pos value from the Step 5 metadata file. |
| `''` | Empty string for the SSL CA certificate parameter (leave blank if not using SSL for the replication link itself). |

Critical:
These two values must correspond exactly to the mydumper run in Step 4 — a mismatch here will either replay already-restored transactions (duplicate-key errors) or skip transactions (data loss/inconsistency).

## Step 10: Start Replication
```sql
CALL mysql.az_replication_start;
```

## Step 11: Verify Replication

### On Primary Server
```sql
SHOW MASTER STATUS;
```

### On Replica Server
```sql
SHOW REPLICA STATUS\G
Check:
Replica_IO_Running: Yes
Replica_SQL_Running: Yes
Seconds_Behind_Master counting down to 0
Last_IO_Error / Last_SQL_Error blank
```

## Step 12: Prove It End-to-End
-- on source insert some data 
-- on Flexible Server target check the inserted data
The row should appear on the target, confirming the restored snapshot plus everything replicated since Step 4 correctly stitched into one consistent dataset.

## Step 13: Cutover
Platform limitation:
SET GLOBAL read_only = ON will not be applicable on Azure Flexible Server due to missing superuser privileges. Application downtime must be ensured manually for this step.
-- on source
```sql
SET GLOBAL read_only = ON;
```
 
-- confirm zero lag on target, then:
```sql
CALL mysql.az_replication_stop;
```

## Step 14: Migrating Users and Grants (Post-Replication Stop)
> [!IMPORTANT]
> **Why this step is required**: During initial data migration (via MyDumper/MyLoader), the internal `mysql` system schema was skipped because it is already pre-created when the target Azure Database for MySQL Flexible Server is provisioned. However, the `mysql.user` and `mysql.db` tables inside this schema contain all custom database users, passwords, and access grants. 
>
> To ensure applications and databases can connect properly, we must manually extract, create, and grant permissions to these users on the target server.

### 1. Create Baseline Dependency Users
Some database users are dependent on the `data_manipulator` and `data_reader` baseline roles/users. Therefore, you must create these two baseline users on the target destination server first:
```sql
-- Execute on destination target
CREATE USER `data_manipulator`@`%` IDENTIFIED WITH 'mysql_native_password' REQUIRE NONE PASSWORD EXPIRE ACCOUNT LOCK PASSWORD HISTORY DEFAULT PASSWORD REUSE INTERVAL DEFAULT PASSWORD REQUIRE CURRENT DEFAULT;
CREATE USER `data_reader`@`%` IDENTIFIED WITH 'mysql_native_password' REQUIRE NONE PASSWORD EXPIRE ACCOUNT LOCK PASSWORD HISTORY DEFAULT PASSWORD REUSE INTERVAL DEFAULT PASSWORD REQUIRE CURRENT DEFAULT;
```

### 2. Generate and Execute User Creation Script
Extract the remaining user definitions from the source server (excluding default administrative and system users, as well as the manually created baseline users), then apply them to the target server:

* **On the Source Server (run on the jumpbox to generate `create_users_output1.sql`)**:
  ```bash
  mysql -h "bt-26-jul-2026.mysql.database.azure.com" \
    -u "btadmin" \
    -p'qs$3?j@*CA6!#Dy' \
    -N -e "SELECT CONCAT('SHOW CREATE USER \`', User, '\`@\`', Host, '\`;') FROM mysql.user WHERE User NOT IN ('btadmin','maxwell','azure_superuser','mysql.infoschema','mysql.session','mysql.sys','data_manipulator','data_reader');" \
    | mysql -h "bt-26-jul-2026.mysql.database.azure.com" \
    -u "btadmin" \
    -p'qs$3?j@*CA6!#Dy' \
    -N -B \
    | cut -f2- \
    | sed 's/$/;/' \
    > /u01/backup/create_users_output1.sql
  ```

* **On the Destination Server (run on the jumpbox to import `create_users_output1.sql`)**:
  ```bash
  mysql \
    -h "browntape-03feb2025-staging-mig.mysql.database.azure.com" \
    -u "btadmin" \
    -p'qs$3?j@*CA6!#Dy' \
    -P 3306 \
    < /u01/backup/create_users_output1.sql
  ```

### 3. Generate and Execute User Grants Script
Extract the privilege grants for the migrated users from the source server, and execute them on the target server:

* **On the Source Server (run on the jumpbox to generate `show_grants_output1.sql`)**:
  ```bash
  mysql \
    -h "bt-26-jul-2026.mysql.database.azure.com" \
    -u "btadmin" \
    -p'qs$3?j@*CA6!#Dy' \
    -N -e "SELECT CONCAT('SHOW GRANTS FOR \`', User, '\`@\`', Host, '\`;') FROM mysql.user WHERE User NOT IN ('btadmin','maxwell','azure_superuser','mysql.infoschema','mysql.session','mysql.sys','data_manipulator','data_reader');" \
    | mysql \
    -h "bt-26-jul-2026.mysql.database.azure.com" \
    -u "btadmin" \
    -p'qs$3?j@*CA6!#Dy' \
    -N -B \
    | sed 's/$/;/' \
    > /u01/backup/show_grants_output1.sql
  ```

* **On the Destination Server (run on the jumpbox to import `show_grants_output1.sql`)**:
  ```bash
  mysql \
    -h "browntape-03feb2025-staging-mig.mysql.database.azure.com" \
    -u "btadmin" \
    -p'qs$3?j@*CA6!#Dy' \
    -P 3306 \
    < /u01/backup/show_grants_output1.sql
  ```

### 4. Verify User Counts on Source and Destination
Run the query below on both the source and target databases to verify that the user migration is complete and counts are equal:
```sql
SELECT count(1) FROM mysql.user WHERE User NOT IN 
('btadmin','maxwell','azure_superuser','mysql.infoschema','mysql.session','mysql.sys')
ORDER BY User;
```

---

## Step 15: Run Final Cluster Validation
Before completing the cutover, run the comparison script below to validate data and schema parity between the source and target databases.

### Cluster Final Comparison Script
```bash
#!/bin/bash
# =============================================================
# final_compare_cluster.sh — Full Cluster Migration Validation (v2)
# Automatically discovers all user databases on the source.
# Compares each against the destination cluster with matching names.
#
# Validates:
#   - Database-level Character Sets & Collations
#   - Table, View, Procedure, Function, and Event Counts
#   - Table-wise row counts (with source/dest timings)
#   - Table-wise Index, PK, FK, Unique, Check, and Trigger counts
#
# Usage: ./final_compare_cluster.sh [optional_db_name]
# =============================================================

# ===============================
# CONNECTION SETTINGS
# ===============================
SRC_HOST="bt-26-jul-2026.mysql.database.azure.com"
SRC_USER="btadmin"
SRC_PASS='qs$3?j@*CA6!#Dy'

DEST_HOST="browntape-03feb2025-staging-mig.mysql.database.azure.com"
DEST_USER="btadmin"
DEST_PASS='qs$3?j@*CA6!#Dy'

BASE_ROOT="/u01/backup/compare_logs"
MAX_PARALLEL=25

# Space-separated list of databases to exclude from automatic validation
EXCLUDE_DBS=""

# ===============================
# GLOBAL CONSOLIDATED LOG SETUP
# ===============================
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BASE_ROOT"
GLOBAL_LOG="$BASE_ROOT/consolidated_compare_${TIMESTAMP}.log"
FAILURE_LOG="$BASE_ROOT/failures_${TIMESTAMP}.log"
SUMMARY_LOG="$BASE_ROOT/summary_${TIMESTAMP}.log"
exec > >(tee -ia "$GLOBAL_LOG") 2>&1

# Ensure all background logging writes flush before the script exits
cleanup_log() {
  exec 1>&- 2>&-
  wait
}
trap cleanup_log EXIT

# TRIGGER COMPARISON EXCLUSIONS
# ===============================
# No exclusions active. All tables and triggers will be validated.
TRIGGER_EXCLUDE_TABLES=""

# ===============================
# COLORS
# ===============================
RED="\033[1;31m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RESET="\033[0m"

# ===============================
# GLOBAL COUNTERS & STATUS TRACKING
# ===============================
TOTAL_DBS_COMPARED=0
TOTAL_DBS_PASSED=0
TOTAL_DBS_FAILED=0

TOTAL_TABLES_COMPARED=0
TOTAL_TABLES_MATCHED=0
TOTAL_TABLES_FAILED=0

GLOBAL_VIEWS_STATUS="PASS"
GLOBAL_PROCEDURES_STATUS="PASS"
GLOBAL_FUNCTIONS_STATUS="PASS"
GLOBAL_EVENTS_STATUS="PASS"
GLOBAL_INDEXES_STATUS="PASS"
GLOBAL_PKS_STATUS="PASS"
GLOBAL_FKS_STATUS="PASS"
GLOBAL_UNIQUES_STATUS="PASS"
GLOBAL_CHECKS_STATUS="PASS"
GLOBAL_TRIGGERS_STATUS="PASS"
GLOBAL_CHARSETS_STATUS="PASS"
GLOBAL_COLLATIONS_STATUS="PASS"

# Array to collect all failed or mismatched elements
MISMATCHES=()

# Declarations for live summary master tracking
declare -A DB_STATUSES
declare -A DB_ERRORS
declare -A DB_FAIL_DETAILS
START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
START_EPOCH=$(date +%s)

# ===============================
# FETCH DATABASE LIST
# ===============================
if [ -n "$1" ]; then
  DATABASES="$1"
  echo "Comparing single database provided as argument: $DATABASES"
else
  echo "Discovering user databases..."
  DB_ERR_FILE=$(mktemp)
  DATABASES=$(mysql \
    --host="$SRC_HOST" \
    --user="$SRC_USER" \
    --password="$SRC_PASS" \
    -N -e "
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name NOT IN
(
'mysql',
'information_schema',
'performance_schema',
'sys'
)
ORDER BY schema_name;" 2>"$DB_ERR_FILE")
  MYSQL_STATUS=$?

  if [ $MYSQL_STATUS -ne 0 ] || [ -z "$DATABASES" ]; then
    echo "ERROR: Database discovery failed or returned empty."
    if [ -f "$DB_ERR_FILE" ] && [ -s "$DB_ERR_FILE" ]; then
      echo "MySQL Error Details:"
      cat "$DB_ERR_FILE"
    fi
    rm -f "$DB_ERR_FILE"
    exit 1
  fi
  rm -f "$DB_ERR_FILE"

  # Filter out excluded databases from automatic discovery
  if [ -n "$EXCLUDE_DBS" ]; then
    # Support both comma-separated and space-separated databases
    clean_excludes=$(echo "$EXCLUDE_DBS" | tr ',' ' ')
    filtered_dbs=""
    for db in $DATABASES; do
      exclude=0
      for ex_db in $clean_excludes; do
        if [ "$db" = "$ex_db" ]; then
          exclude=1
          break
        fi
      done
      if [ $exclude -eq 0 ]; then
        filtered_dbs="$filtered_dbs $db"
      else
        echo "Excluding database: $db (defined in EXCLUDE_DBS)"
      fi
    done
    DATABASES=$(echo "$filtered_dbs" | xargs)
  fi
fi

TOTAL_DB_COUNT=$(echo "$DATABASES" | wc -w)
echo "Found $TOTAL_DB_COUNT database(s) to compare."
echo ""

# ===============================
# PER-DB COMPARISON FUNCTION
# ===============================
compare_database() {
  SOURCE_DB="$1"
  DEST_DB="$SOURCE_DB" # Same database name for full migration

  # ---- Log Setup — ONE file per DB ----
  DB_LOG_DIR="$BASE_ROOT/$SOURCE_DB"
  COMPARE_DIR="$DB_LOG_DIR/final_compare"
  mkdir -p "$COMPARE_DIR"

  # Initialize subshell stats and mismatches files
  rm -f "$COMPARE_DIR/subshell_stats.tmp"
  rm -f "$COMPARE_DIR/mismatches.tmp"
  log_mismatch() {
    echo "$1" >> "$COMPARE_DIR/mismatches.tmp"
  }

  DB_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  COMPARE_LOG="$COMPARE_DIR/compare_${DB_TIMESTAMP}.log"

  run_mysql_query() {
    local host=$1 user=$2 pass=$3 query=$4 label=$5
    local err_file="$COMPARE_DIR/mysql_temp_err.tmp"
    local res
    res=$(mysql --host="$host" --user="$user" --password="$pass" -N -e "$query" 2>"$err_file")
    local status=$?
    if [ $status -ne 0 ]; then
      local err_txt="MySQL Error"
      if [ -f "$err_file" ] && [ -s "$err_file" ]; then
        err_txt=$(cat "$err_file" | tr '\n' ' ')
      fi
      log_mismatch "[$SOURCE_DB] Query failed for $label: $err_txt (Exit Code: $status)"
      rm -f "$err_file"
      return 1
    fi
    rm -f "$err_file"
    echo "$res"
    return 0
  }

  echo "=============================================================" | tee -a "$COMPARE_LOG"
  echo " DATABASE COMPARISON: $SOURCE_DB  →  $DEST_DB" | tee -a "$COMPARE_LOG"
  echo "=============================================================" | tee -a "$COMPARE_LOG"
  echo "Run at : $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$COMPARE_LOG"
  echo "" | tee -a "$COMPARE_LOG"

  # ---- Fetch Character Set & Collation ----
  src_charset=$(run_mysql_query "$SRC_HOST" "$SRC_USER" "$SRC_PASS" "SELECT default_character_set_name FROM information_schema.schemata WHERE schema_name='$SOURCE_DB';" "src_charset")
  dest_charset=$(run_mysql_query "$DEST_HOST" "$DEST_USER" "$DEST_PASS" "SELECT default_character_set_name FROM information_schema.schemata WHERE schema_name='$DEST_DB';" "dest_charset")

  src_collation=$(run_mysql_query "$SRC_HOST" "$SRC_USER" "$SRC_PASS" "SELECT default_collation_name FROM information_schema.schemata WHERE schema_name='$SOURCE_DB';" "src_collation")
  dest_collation=$(run_mysql_query "$DEST_HOST" "$DEST_USER" "$DEST_PASS" "SELECT default_collation_name FROM information_schema.schemata WHERE schema_name='$DEST_DB';" "dest_collation")

  # ---- Fetch Object Counts ----
  src_table_cnt=$(run_mysql_query "$SRC_HOST" "$SRC_USER" "$SRC_PASS" "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$SOURCE_DB' AND table_type='BASE TABLE';" "src_table_cnt")
  dest_table_cnt=$(run_mysql_query "$DEST_HOST" "$DEST_USER" "$DEST_PASS" "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DEST_DB' AND table_type='BASE TABLE';" "dest_table_cnt")

  src_view_cnt=$(run_mysql_query "$SRC_HOST" "$SRC_USER" "$SRC_PASS" "SELECT COUNT(*) FROM information_schema.views WHERE table_schema='$SOURCE_DB';" "src_view_cnt")
  dest_view_cnt=$(run_mysql_query "$DEST_HOST" "$DEST_USER" "$DEST_PASS" "SELECT COUNT(*) FROM information_schema.views WHERE table_schema='$DEST_DB';" "dest_view_cnt")

  src_proc_cnt=$(run_mysql_query "$SRC_HOST" "$SRC_USER" "$SRC_PASS" "SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='$SOURCE_DB' AND routine_type='PROCEDURE';" "src_proc_cnt")
  dest_proc_cnt=$(run_mysql_query "$DEST_HOST" "$DEST_USER" "$DEST_PASS" "SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='$DEST_DB' AND routine_type='PROCEDURE';" "dest_proc_cnt")

  src_func_cnt=$(run_mysql_query "$SRC_HOST" "$SRC_USER" "$SRC_PASS" "SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='$SOURCE_DB' AND routine_type='FUNCTION';" "src_func_cnt")
  dest_func_cnt=$(run_mysql_query "$DEST_HOST" "$DEST_USER" "$DEST_PASS" "SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema='$DEST_DB' AND routine_type='FUNCTION';" "dest_func_cnt")

  src_event_cnt=$(run_mysql_query "$SRC_HOST" "$SRC_USER" "$SRC_PASS" "SELECT COUNT(*) FROM information_schema.events WHERE event_schema='$SOURCE_DB';" "src_event_cnt")
  dest_event_cnt=$(run_mysql_query "$DEST_HOST" "$DEST_USER" "$DEST_PASS" "SELECT COUNT(*) FROM information_schema.events WHERE event_schema='$DEST_DB';" "dest_event_cnt")

  src_charset=${src_charset:-N/A}
  dest_charset=${dest_charset:-N/A}
  src_collation=${src_collation:-N/A}
  dest_collation=${dest_collation:-N/A}

  src_table_cnt=${src_table_cnt:-0}
  dest_table_cnt=${dest_table_cnt:-0}
  src_view_cnt=${src_view_cnt:-0}
  dest_view_cnt=${dest_view_cnt:-0}
  src_proc_cnt=${src_proc_cnt:-0}
  dest_proc_cnt=${dest_proc_cnt:-0}
  src_func_cnt=${src_func_cnt:-0}
  dest_func_cnt=${dest_func_cnt:-0}
  src_event_cnt=${src_event_cnt:-0}
  dest_event_cnt=${dest_event_cnt:-0}

  # ---- Evaluate Database level matches ----
  local db_ok=1

  charset_status="MATCH"
  if [ "$src_charset" != "$dest_charset" ]; then
    charset_status="MISMATCH"
    GLOBAL_CHARSETS_STATUS="FAIL"
    db_ok=0
    log_mismatch "[$SOURCE_DB] Character Set: Source '$src_charset' vs Dest '$dest_charset'"
  fi

  collation_status="MATCH"
  if [ "$src_collation" != "$dest_collation" ]; then
    collation_status="MISMATCH"
    GLOBAL_COLLATIONS_STATUS="FAIL"
    db_ok=0
    log_mismatch "[$SOURCE_DB] Collation: Source '$src_collation' vs Dest '$dest_collation'"
  fi

  table_cnt_status="MATCH"
  if [ "$src_table_cnt" -ne "$dest_table_cnt" ]; then
    table_cnt_status="MISMATCH"
    db_ok=0
    log_mismatch "[$SOURCE_DB] Table Count: Source $src_table_cnt vs Dest $dest_table_cnt"
  fi

  view_status="MATCH"
  if [ "$src_view_cnt" -ne "$dest_view_cnt" ]; then
    view_status="MISMATCH"
    GLOBAL_VIEWS_STATUS="FAIL"
    db_ok=0
    log_mismatch "[$SOURCE_DB] View Count: Source $src_view_cnt vs Dest $dest_view_cnt"
  fi

  proc_status="MATCH"
  if [ "$src_proc_cnt" -ne "$dest_proc_cnt" ]; then
    proc_status="MISMATCH"
    GLOBAL_PROCEDURES_STATUS="FAIL"
    db_ok=0
    log_mismatch "[$SOURCE_DB] Procedure Count: Source $src_proc_cnt vs Dest $dest_proc_cnt"
  fi

  func_status="MATCH"
  if [ "$src_func_cnt" -ne "$dest_func_cnt" ]; then
    func_status="MISMATCH"
    GLOBAL_FUNCTIONS_STATUS="FAIL"
    db_ok=0
    log_mismatch "[$SOURCE_DB] Function Count: Source $src_func_cnt vs Dest $dest_func_cnt"
  fi

  event_status="MATCH"
  if [ "$src_event_cnt" -ne "$dest_event_cnt" ]; then
    event_status="MISMATCH"
    GLOBAL_EVENTS_STATUS="FAIL"
    db_ok=0
    log_mismatch "[$SOURCE_DB] Event Count: Source $src_event_cnt vs Dest $dest_event_cnt"
  fi

  # ---- Print Metadata Comparison ----
  {
    echo "-------------------------------------------------------------"
    echo "METADATA & SCHEMA OBJECT COUNTS:"
    echo "-------------------------------------------------------------"
    printf "%-20s %-30s %-30s %-10s\n" "Object Type" "Source" "Destination" "Status"
    printf "%-20s %-30s %-30s %-10s\n" "--------------------" "------------------------------" "------------------------------" "----------"
    printf "%-20s %-30s %-30s %-10s\n" "Character Set" "$src_charset" "$dest_charset" "$charset_status"
    printf "%-20s %-30s %-30s %-10s\n" "Collation" "$src_collation" "$dest_collation" "$collation_status"
    printf "%-20s %-30s %-30s %-10s\n" "Base Tables" "$src_table_cnt" "$dest_table_cnt" "$table_cnt_status"
    printf "%-20s %-30s %-30s %-10s\n" "Views" "$src_view_cnt" "$dest_view_cnt" "$view_status"
    printf "%-20s %-30s %-30s %-10s\n" "Procedures" "$src_proc_cnt" "$dest_proc_cnt" "$proc_status"
    printf "%-20s %-30s %-30s %-10s\n" "Functions" "$src_func_cnt" "$dest_func_cnt" "$func_status"
    printf "%-20s %-30s %-30s %-10s\n" "Events" "$src_event_cnt" "$dest_event_cnt" "$event_status"
    echo ""
  } | tee -a "$COMPARE_LOG"

  # ---- Fetch Table List ----
  TABLES=$(mysql \
    --host="$SRC_HOST" \
    --user="$SRC_USER" \
    --password="$SRC_PASS" \
    -N -e "SELECT table_name FROM information_schema.tables
           WHERE table_schema='$SOURCE_DB' AND table_type='BASE TABLE'
           ORDER BY table_name;" 2>/dev/null)

  if [ -z "$TABLES" ] && [ "$src_table_cnt" -gt 0 ]; then
    echo "  ERROR: Connection lost or failed to fetch tables for $SOURCE_DB." | tee -a "$COMPARE_LOG"
    return 1
  fi

  # Excluded Tables logic removed. All tables are compared.

  # ===============================
  # BLOCK 1: ROW COUNT COMPARISON
  # ===============================
  {
    echo "============================================================="
    echo " BLOCK 1: Row Count Comparison"
    echo " Source : $SRC_HOST / $SOURCE_DB"
    echo " Dest   : $DEST_HOST / $DEST_DB"
    echo " Run at : $(date '+%Y-%m-%d %H:%M:%S')"
    echo "============================================================="
    printf "%-45s %-15s %-15s %-10s %-20s\n" \
      "TableName" "Source" "Dest" "Diff" "Timing(S/D/T)"
    printf "%-45s %-15s %-15s %-10s %-20s\n" \
      "---------------------------------------------" \
      "---------------" "---------------" "----------" "--------------------"
  } | tee -a "$COMPARE_LOG"

  TOTAL_SRC_ROWS=0
  TOTAL_DEST_ROWS=0
  ROW_MISMATCH=0
  TABLES_ROW_OK=0
  DB_TABLES_COMPARED=0

  for tbl in $TABLES; do
    DB_TABLES_COMPARED=$((DB_TABLES_COMPARED + 1))
    TOTAL_TABLES_COMPARED=$((TOTAL_TABLES_COMPARED + 1))

     s_start=$(date +%s)
    src_count=$(mysql \
      --host="$SRC_HOST" \
      --user="$SRC_USER" \
      --password="$SRC_PASS" \
      -N -e "SELECT /*+ MAX_EXECUTION_TIME(6000000) */ COUNT(*) FROM \`${SOURCE_DB}\`.\`${tbl}\`;" 2>"$COMPARE_DIR/src_mysql_err.tmp")
    SRC_STATUS=$?
    s_end=$(date +%s)
    s_time=$((s_end - s_start))

    d_start=$(date +%s)
    dest_count=$(mysql \
      --host="$DEST_HOST" \
      --user="$DEST_USER" \
      --password="$DEST_PASS" \
      -N -e "SELECT /*+ MAX_EXECUTION_TIME(6000000) */ COUNT(*) FROM \`${DEST_DB}\`.\`${tbl}\`;" 2>"$COMPARE_DIR/dest_mysql_err.tmp")
    DEST_STATUS=$?
    d_end=$(date +%s)
    d_time=$((d_end - d_start))
    t_time=$((d_end - s_start))

    if [ $SRC_STATUS -ne 0 ] || [ $DEST_STATUS -ne 0 ]; then
      ROW_MISMATCH=$((ROW_MISMATCH + 1))
      TOTAL_TABLES_FAILED=$((TOTAL_TABLES_FAILED + 1))
      
      local err_msg="MySQL Error Details: "
      if [ $SRC_STATUS -ne 0 ] && [ -f "$COMPARE_DIR/src_mysql_err.tmp" ]; then
        err_msg="$err_msg [Source] $(cat "$COMPARE_DIR/src_mysql_err.tmp" | tr '\n' ' ')"
        src_count="ERROR"
      fi
      if [ $DEST_STATUS -ne 0 ] && [ -f "$COMPARE_DIR/dest_mysql_err.tmp" ]; then
        err_msg="$err_msg [Dest] $(cat "$COMPARE_DIR/dest_mysql_err.tmp" | tr '\n' ' ')"
        dest_count="ERROR"
      fi
      
      log_mismatch "[$SOURCE_DB] Query failed for table '$tbl' (Source status: $SRC_STATUS, Dest status: $DEST_STATUS). $err_msg"
      printf "${RED}%-45s %-15s %-15s %-10s [S:%ds D:%ds T:%ds] (QUERY ERROR)${RESET}\n" \
        "$tbl" "$src_count" "$dest_count" "N/A" \
        "$s_time" "$d_time" "$t_time" | tee -a "$COMPARE_LOG"
      db_ok=0
    else
      src_count=${src_count:-0}
      dest_count=${dest_count:-0}
      diff=$((src_count - dest_count))

      TOTAL_SRC_ROWS=$((TOTAL_SRC_ROWS + src_count))
      TOTAL_DEST_ROWS=$((TOTAL_DEST_ROWS + dest_count))

      if [ "$diff" -ne 0 ]; then
        ROW_MISMATCH=$((ROW_MISMATCH + 1))
        TOTAL_TABLES_FAILED=$((TOTAL_TABLES_FAILED + 1))
        log_mismatch "[$SOURCE_DB] Row Count mismatch in table '$tbl' (Source: $src_count, Dest: $dest_count, Diff: $diff)"
        printf "${RED}%-45s %-15s %-15s %-10s [S:%ds D:%ds T:%ds]${RESET}\n" \
          "$tbl" "$src_count" "$dest_count" "$diff" \
          "$s_time" "$d_time" "$t_time" | tee -a "$COMPARE_LOG"
        db_ok=0
      else
        TABLES_ROW_OK=$((TABLES_ROW_OK + 1))
        TOTAL_TABLES_MATCHED=$((TOTAL_TABLES_MATCHED + 1))
        printf "%-45s %-15s %-15s %-10s [S:%ds D:%ds T:%ds]\n" \
          "$tbl" "$src_count" "$dest_count" "$diff" \
          "$s_time" "$d_time" "$t_time" | tee -a "$COMPARE_LOG"
      fi
    fi
    rm -f "$COMPARE_DIR/src_mysql_err.tmp" "$COMPARE_DIR/dest_mysql_err.tmp"
  done

  {
    echo ""
    echo "--- ROW COUNT SUMMARY ---"
    printf "  %-30s : %s\n" "Total Tables"       "$DB_TABLES_COMPARED"
    printf "  %-30s : %s\n" "Tables MATCH"       "$TABLES_ROW_OK"
    printf "  %-30s : %s\n" "Tables MISMATCH"    "$ROW_MISMATCH"
    printf "  %-30s : %s\n" "Total Source Rows"  "$TOTAL_SRC_ROWS"
    printf "  %-30s : %s\n" "Total Dest Rows"    "$TOTAL_DEST_ROWS"
    if [ "$ROW_MISMATCH" -eq 0 ]; then
      printf "  %-30s : %s\n" "Status" "✅ ALL MATCH"
    else
      printf "  %-30s : %s\n" "Status" "❌ $ROW_MISMATCH TABLE(S) MISMATCH"
    fi
  } | tee -a "$COMPARE_LOG"

  # ===============================
  # BLOCK 2: SCHEMA OBJECTS COMPARISON
  # ===============================
  {
    echo ""
    echo "============================================================="
    echo " BLOCK 2: Schema Objects Comparison"
    echo " (Index / PK / FK / Unique / Check / Trigger)"
    echo " Run at : $(date '+%Y-%m-%d %H:%M:%S')"
    echo "============================================================="
    printf "%-45s %-10s %-10s %-10s %-10s %-10s %-10s %-8s\n" \
      "TableName" "Index" "PK" "FK" "Unique" "Check" "Trigger" "Diff?"
    printf "%-45s %-10s %-10s %-10s %-10s %-10s %-10s %-8s\n" \
      "---------------------------------------------" \
      "----------" "----------" "----------" "----------" "----------" "----------" "--------"
  } | tee -a "$COMPARE_LOG"

  SCHEMA_MISMATCH=0
  SCHEMA_OK=0

  get_schema_stats() {
    local host=$1 user=$2 pass=$3 schema=$4 table=$5 err_file=$6
    mysql --host="$host" --user="$user" --password="$pass" -N -e "
    SELECT IFNULL(i.index_count,0), IFNULL(c.pk_count,0), IFNULL(c.fk_count,0),
           IFNULL(c.uniq_count,0), IFNULL(c.chk_count,0), IFNULL(tr.trg_count,0)
    FROM (SELECT '$table' AS tbl) t
    LEFT JOIN (
        SELECT TABLE_NAME, COUNT(DISTINCT INDEX_NAME) AS index_count
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA='$schema' AND TABLE_NAME='$table'
        GROUP BY TABLE_NAME
    ) i ON i.TABLE_NAME = t.tbl
    LEFT JOIN (
        SELECT TABLE_NAME,
               SUM(CASE WHEN CONSTRAINT_TYPE='PRIMARY KEY' THEN 1 ELSE 0 END) AS pk_count,
               SUM(CASE WHEN CONSTRAINT_TYPE='FOREIGN KEY'  THEN 1 ELSE 0 END) AS fk_count,
               SUM(CASE WHEN CONSTRAINT_TYPE='UNIQUE'       THEN 1 ELSE 0 END) AS uniq_count,
               SUM(CASE WHEN CONSTRAINT_TYPE='CHECK'        THEN 1 ELSE 0 END) AS chk_count
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA='$schema' AND TABLE_NAME='$table'
        GROUP BY TABLE_NAME
    ) c ON c.TABLE_NAME = t.tbl
    LEFT JOIN (
        SELECT EVENT_OBJECT_TABLE, COUNT(*) AS trg_count
        FROM information_schema.TRIGGERS
        WHERE TRIGGER_SCHEMA='$schema' AND EVENT_OBJECT_TABLE='$table'
        GROUP BY EVENT_OBJECT_TABLE
    ) tr ON tr.EVENT_OBJECT_TABLE = t.tbl;" 2>"$err_file"
  }

  for tbl in $TABLES; do
    p_stats=$(get_schema_stats "$SRC_HOST"  "$SRC_USER"  "$SRC_PASS"  "$SOURCE_DB" "$tbl" "$COMPARE_DIR/src_schema_err.tmp")
    SRC_STATUS=$?
    s_stats=$(get_schema_stats "$DEST_HOST" "$DEST_USER" "$DEST_PASS" "$DEST_DB"   "$tbl" "$COMPARE_DIR/dest_schema_err.tmp")
    DEST_STATUS=$?

    if [ $SRC_STATUS -ne 0 ] || [ $DEST_STATUS -ne 0 ]; then
      SCHEMA_MISMATCH=$((SCHEMA_MISMATCH + 1))
      
      local err_msg="MySQL Error Details: "
      if [ $SRC_STATUS -ne 0 ] && [ -f "$COMPARE_DIR/src_schema_err.tmp" ]; then
        err_msg="$err_msg [Source] $(cat "$COMPARE_DIR/src_schema_err.tmp" | tr '\n' ' ')"
      fi
      if [ $DEST_STATUS -ne 0 ] && [ -f "$COMPARE_DIR/dest_schema_err.tmp" ]; then
        err_msg="$err_msg [Dest] $(cat "$COMPARE_DIR/dest_schema_err.tmp" | tr '\n' ' ')"
      fi
      
      log_mismatch "[$SOURCE_DB] Schema stats query failed for table '$tbl' (Source status: $SRC_STATUS, Dest status: $DEST_STATUS). $err_msg"
      printf "${RED}%-45s %-10s %-10s %-10s %-10s %-10s %-10s %-8s (QUERY ERROR)${RESET}\n" \
        "$tbl" "ERROR" "ERROR" "ERROR" "ERROR" "ERROR" "ERROR" "YES" | tee -a "$COMPARE_LOG"
      db_ok=0
    else
      p_idx=$(echo "$p_stats" | awk '{print $1}'); p_idx=${p_idx:-0}
      p_pk=$( echo "$p_stats" | awk '{print $2}'); p_pk=${p_pk:-0}
      p_fk=$( echo "$p_stats" | awk '{print $3}'); p_fk=${p_fk:-0}
      p_un=$( echo "$p_stats" | awk '{print $4}'); p_un=${p_un:-0}
      p_ch=$( echo "$p_stats" | awk '{print $5}'); p_ch=${p_ch:-0}
      p_tr=$( echo "$p_stats" | awk '{print $6}'); p_tr=${p_tr:-0}

      s_idx=$(echo "$s_stats" | awk '{print $1}'); s_idx=${s_idx:-0}
      s_pk=$( echo "$s_stats" | awk '{print $2}'); s_pk=${s_pk:-0}
      s_fk=$( echo "$s_stats" | awk '{print $3}'); s_fk=${s_fk:-0}
      s_un=$( echo "$s_stats" | awk '{print $4}'); s_un=${s_un:-0}
      s_ch=$( echo "$s_stats" | awk '{print $5}'); s_ch=${s_ch:-0}
      s_tr=$( echo "$s_stats" | awk '{print $6}'); s_tr=${s_tr:-0}

      # Track structural failures globally
      if [ "$p_idx" != "$s_idx" ]; then GLOBAL_INDEXES_STATUS="FAIL"; fi
      if [ "$p_pk" != "$s_pk" ];   then GLOBAL_PKS_STATUS="FAIL"; fi
      if [ "$p_fk" != "$s_fk" ];   then GLOBAL_FKS_STATUS="FAIL"; fi
      if [ "$p_un" != "$s_un" ];   then GLOBAL_UNIQUES_STATUS="FAIL"; fi
      if [ "$p_ch" != "$s_ch" ];   then GLOBAL_CHECKS_STATUS="FAIL"; fi
      if [ "$p_tr" != "$s_tr" ];   then GLOBAL_TRIGGERS_STATUS="FAIL"; fi

      if [ "$p_idx" != "$s_idx" ] || [ "$p_pk" != "$s_pk" ] || [ "$p_fk" != "$s_fk" ] || \
         [ "$p_un"  != "$s_un"  ] || [ "$p_ch" != "$s_ch" ] || [ "$p_tr" != "$s_tr" ]; then

        SCHEMA_MISMATCH=$((SCHEMA_MISMATCH + 1))
        local schema_mismatches=""
        [ "$p_idx" != "$s_idx" ] && schema_mismatches="$schema_mismatches Index($p_idx/$s_idx)"
        [ "$p_pk" != "$s_pk" ] && schema_mismatches="$schema_mismatches PK($p_pk/$s_pk)"
        [ "$p_fk" != "$s_fk" ] && schema_mismatches="$schema_mismatches FK($p_fk/$s_fk)"
        [ "$p_un" != "$s_un" ] && schema_mismatches="$schema_mismatches Unique($p_un/$s_un)"
        [ "$p_ch" != "$s_ch" ] && schema_mismatches="$schema_mismatches Check($p_ch/$s_ch)"
        [ "$p_tr" != "$s_tr" ] && schema_mismatches="$schema_mismatches Trigger($p_tr/$s_tr)"
        log_mismatch "[$SOURCE_DB] Schema mismatch in table '$tbl':$schema_mismatches"
        printf "${RED}%-45s %-10s %-10s %-10s %-10s %-10s %-10s %-8s${RESET}\n" \
          "$tbl" \
          "$p_idx/$s_idx" "$p_pk/$s_pk" "$p_fk/$s_fk" \
          "$p_un/$s_un"   "$p_ch/$s_ch" "$p_tr/$s_tr" "YES" | tee -a "$COMPARE_LOG"
        db_ok=0
      else
        SCHEMA_OK=$((SCHEMA_OK + 1))
        printf "%-45s %-10s %-10s %-10s %-10s %-10s %-10s %-8s\n" \
          "$tbl" \
          "$p_idx/$s_idx" "$p_pk/$s_pk" "$p_fk/$s_fk" \
          "$p_un/$s_un"   "$p_ch/$s_ch" "$p_tr/$s_tr" "NO" | tee -a "$COMPARE_LOG"
      fi
    fi
    rm -f "$COMPARE_DIR/src_schema_err.tmp" "$COMPARE_DIR/dest_schema_err.tmp"
  done

  {
    echo ""
    echo "--- SCHEMA OBJECTS SUMMARY ---"
    printf "  %-30s : %s\n" "Total Tables"     "$DB_TABLES_COMPARED"
    printf "  %-30s : %s\n" "Schema MATCH"     "$SCHEMA_OK"
    printf "  %-30s : %s\n" "Schema MISMATCH"  "$SCHEMA_MISMATCH"
    if [ "$SCHEMA_MISMATCH" -eq 0 ]; then
      printf "  %-30s : %s\n" "Status" "✅ ALL MATCH"
    else
      printf "  %-30s : %s\n" "Status" "❌ $SCHEMA_MISMATCH TABLE(S) MISMATCH"
    fi
    echo ""
    echo "============================================================="
    echo " Log : $COMPARE_LOG"
    echo "============================================================="
    echo ""
  } | tee -a "$COMPARE_LOG"

  # Dump statistics to a temporary file for the parent process to aggregate
  DB_STATS_FILE="$COMPARE_DIR/subshell_stats.tmp"
  {
    echo "db_ok=$db_ok"
    echo "db_tables_compared=$DB_TABLES_COMPARED"
    echo "db_tables_matched=$TABLES_ROW_OK"
    echo "db_tables_failed=$ROW_MISMATCH"
    echo "db_schema_matched=$SCHEMA_OK"
    echo "db_schema_failed=$SCHEMA_MISMATCH"
    echo "charsets_status=$GLOBAL_CHARSETS_STATUS"
    echo "collations_status=$GLOBAL_COLLATIONS_STATUS"
    echo "views_status=$GLOBAL_VIEWS_STATUS"
    echo "procedures_status=$GLOBAL_PROCEDURES_STATUS"
    echo "functions_status=$GLOBAL_FUNCTIONS_STATUS"
    echo "events_status=$GLOBAL_EVENTS_STATUS"
    echo "indexes_status=$GLOBAL_INDEXES_STATUS"
    echo "pks_status=$GLOBAL_PKS_STATUS"
    echo "fks_status=$GLOBAL_FKS_STATUS"
    echo "uniques_status=$GLOBAL_UNIQUES_STATUS"
    echo "checks_status=$GLOBAL_CHECKS_STATUS"
    echo "triggers_status=$GLOBAL_TRIGGERS_STATUS"
  } > "$DB_STATS_FILE"

  if [ "$db_ok" -eq 1 ]; then
    return 0
  else
    return 1
  fi
}

# Helper function to rewrite the Summary Master Log file
write_summary_master_log() {
  {
    echo "=============================================================="
    echo "MIGRATION VALIDATION SUMMARY (LIVE)"
    echo "=============================================================="
    echo "Start Time         : $START_TIME"
    if [ "$TOTAL_DBS_COMPARED" -eq "$TOTAL_DB_COUNT" ]; then
      local end_time=$(date '+%Y-%m-%d %H:%M:%S')
      local end_epoch=$(date +%s)
      local duration=$((end_epoch - START_EPOCH))
      local duration_str=""
      if [ $duration -ge 60 ]; then
        duration_str="$((duration / 60))m $((duration % 60))s"
      else
        duration_str="${duration}s"
      fi
      echo "End Time           : $end_time"
      echo "Elapsed Time       : $duration_str"
    fi
    echo "Source Server      : $SRC_HOST"
    echo "Destination Server : $DEST_HOST"
    echo ""
    echo "Databases Processed:"
    
    local idx=0
    for DB_NAME in $DATABASES; do
      idx=$((idx + 1))
      local status=${DB_STATUSES["$DB_NAME"]}
      local errors=${DB_ERRORS["$DB_NAME"]}
      if [ "$status" = "PENDING" ] || [ "$status" = "PENDING (Running...)" ]; then
        printf "  [%d/%d] DB: %-30s -> %s\n" "$idx" "$TOTAL_DB_COUNT" "$DB_NAME" "$status"
      elif [ "$status" = "SUCCESS" ]; then
        printf "  [%d/%d] DB: %-30s -> SUCCESS (0 errors)\n" "$idx" "$TOTAL_DB_COUNT" "$DB_NAME"
      else
        local details=${DB_FAIL_DETAILS["$DB_NAME"]}
        if [ -n "$details" ]; then
          printf "  [%d/%d] DB: %-30s -> FAILED (%d errors) [Details: %s]\n" "$idx" "$TOTAL_DB_COUNT" "$DB_NAME" "$errors" "$details"
        else
          printf "  [%d/%d] DB: %-30s -> FAILED (%d errors)\n" "$idx" "$TOTAL_DB_COUNT" "$DB_NAME" "$errors"
        fi
      fi
    done
    
    echo ""
    echo "--------------------------------------------------------------"
    echo "OVERALL SUMMARY:"
    echo "--------------------------------------------------------------"
    printf "Databases Compared : %s\n" "$TOTAL_DBS_COMPARED"
    printf "Databases Passed   : %s\n" "$TOTAL_DBS_PASSED"
    printf "Databases Failed   : %s\n" "$TOTAL_DBS_FAILED"
    echo ""
    printf "Tables Compared    : %s\n" "$TOTAL_TABLES_COMPARED"
    printf "Matched Tables     : %s\n" "$TOTAL_TABLES_MATCHED"
    printf "Failed Tables      : %s\n" "$TOTAL_TABLES_FAILED"
    echo ""
    if [ "$TOTAL_DBS_COMPARED" -eq "$TOTAL_DB_COUNT" ]; then
      if [ "$TOTAL_DBS_FAILED" -eq 0 ]; then
        echo "Validation Result  : SUCCESS"
      else
        echo "Validation Result  : FAILED"
      fi
    else
      echo "Validation Result  : RUNNING..."
    fi
    echo "=============================================================="
  } > "$SUMMARY_LOG"
}

# Pre-initialize status variables for all discovered databases
for DB_NAME in $DATABASES; do
  DB_STATUSES["$DB_NAME"]="PENDING"
  DB_ERRORS["$DB_NAME"]=0
done

# Write the initial state of the summary log (all pending)
write_summary_master_log

# Helper function to check for completed databases and update state in real-time
check_completed_dbs() {
  for DB_NAME in $DATABASES; do
    if [ "${DB_STATUSES["$DB_NAME"]}" = "PENDING (Running...)" ]; then
      local stats_file="$BASE_ROOT/$DB_NAME/final_compare/subshell_stats.tmp"
      if [ -f "$stats_file" ]; then
        db_ok=""
        db_tables_compared=0
        db_tables_matched=0
        db_tables_failed=0
        db_schema_matched=0
        db_schema_failed=0
        charsets_status="PASS"
        collations_status="PASS"
        views_status="PASS"
        procedures_status="PASS"
        functions_status="PASS"
        events_status="PASS"
        indexes_status="PASS"
        pks_status="PASS"
        fks_status="PASS"
        uniques_status="PASS"
        checks_status="PASS"
        triggers_status="PASS"

        # Source the subshell variables
        source "$stats_file"

        # Update global counters
        TOTAL_TABLES_COMPARED=$((TOTAL_TABLES_COMPARED + db_tables_compared))
        TOTAL_TABLES_MATCHED=$((TOTAL_TABLES_MATCHED + db_tables_matched))
        TOTAL_TABLES_FAILED=$((TOTAL_TABLES_FAILED + db_tables_failed))

        # Update global statuses (if any subshell fails, the global status fails)
        if [ "$charsets_status" = "FAIL" ];   then GLOBAL_CHARSETS_STATUS="FAIL"; fi
        if [ "$collations_status" = "FAIL" ]; then GLOBAL_COLLATIONS_STATUS="FAIL"; fi
        if [ "$views_status" = "FAIL" ];      then GLOBAL_VIEWS_STATUS="FAIL"; fi
        if [ "$procedures_status" = "FAIL" ]; then GLOBAL_PROCEDURES_STATUS="FAIL"; fi
        if [ "$functions_status" = "FAIL" ];  then GLOBAL_FUNCTIONS_STATUS="FAIL"; fi
        if [ "$events_status" = "FAIL" ];     then GLOBAL_EVENTS_STATUS="FAIL"; fi
        if [ "$indexes_status" = "FAIL" ];    then GLOBAL_INDEXES_STATUS="FAIL"; fi
        if [ "$pks_status" = "FAIL" ];        then GLOBAL_PKS_STATUS="FAIL"; fi
        if [ "$fks_status" = "FAIL" ];        then GLOBAL_FKS_STATUS="FAIL"; fi
        if [ "$uniques_status" = "FAIL" ];    then GLOBAL_UNIQUES_STATUS="FAIL"; fi
        if [ "$checks_status" = "FAIL" ];     then GLOBAL_CHECKS_STATUS="FAIL"; fi
        if [ "$triggers_status" = "FAIL" ];   then GLOBAL_TRIGGERS_STATUS="FAIL"; fi

        # Calculate total error count for this DB from mismatches file
        local db_errors=0
        local mismatch_file="$BASE_ROOT/$DB_NAME/final_compare/mismatches.tmp"
        if [ -f "$mismatch_file" ]; then
          while IFS= read -r line; do
            if [ -n "$line" ]; then
              MISMATCHES+=("$line")
              db_errors=$((db_errors + 1))
            fi
          done < "$mismatch_file"
          rm -f "$mismatch_file"
        fi

        DB_ERRORS["$DB_NAME"]=$db_errors
        TOTAL_DBS_COMPARED=$((TOTAL_DBS_COMPARED + 1))
        
        if [ "$db_ok" -eq 1 ]; then
          TOTAL_DBS_PASSED=$((TOTAL_DBS_PASSED + 1))
          DB_STATUSES["$DB_NAME"]="SUCCESS"
          echo -e "[${GREEN}SUCCESS${RESET}] $DB_NAME matches perfectly."
        else
          TOTAL_DBS_FAILED=$((TOTAL_DBS_FAILED + 1))
          DB_STATUSES["$DB_NAME"]="FAILED"
          
          # Build a failure details reason string
          local fail_reason=""
          [ "$charsets_status" = "FAIL" ] && fail_reason="$fail_reason Charset"
          [ "$collations_status" = "FAIL" ] && fail_reason="$fail_reason Collation"
          [ "$db_tables_compared" -ne "$db_tables_matched" ] && fail_reason="$fail_reason TablesRow($db_tables_matched/$db_tables_compared)"
          [ "$db_schema_matched" -ne "$db_tables_compared" ] && fail_reason="$fail_reason TablesSchema($db_schema_matched/$db_tables_compared)"
          [ "$views_status" = "FAIL" ] && fail_reason="$fail_reason Views"
          [ "$procedures_status" = "FAIL" ] && fail_reason="$fail_reason Procedures"
          [ "$functions_status" = "FAIL" ] && fail_reason="$fail_reason Functions"
          [ "$events_status" = "FAIL" ] && fail_reason="$fail_reason Events"
          [ "$indexes_status" = "FAIL" ] && fail_reason="$fail_reason Indexes"
          [ "$pks_status" = "FAIL" ] && fail_reason="$fail_reason PKs"
          [ "$fks_status" = "FAIL" ] && fail_reason="$fail_reason FKs"
          [ "$uniques_status" = "FAIL" ] && fail_reason="$fail_reason Uniques"
          [ "$checks_status" = "FAIL" ] && fail_reason="$fail_reason Checks"
          [ "$triggers_status" = "FAIL" ] && fail_reason="$fail_reason Triggers"

          DB_FAIL_DETAILS["$DB_NAME"]="${fail_reason# }"
          echo -e "[${RED}FAILED${RESET}] $DB_NAME has differences. Details: ${DB_FAIL_DETAILS["$DB_NAME"]}"
        fi
        rm -f "$stats_file"
        write_summary_master_log
      fi
    fi
  done
}

# ===============================
# LOOP THROUGH ALL DATABASES (PARALLEL EXECUTION)
# ===============================
echo "Starting parallel validation of databases (Max parallel: $MAX_PARALLEL)..."
echo "-------------------------------------------------------------"

for DB in $DATABASES; do
  # Concurrency limit check while also updating completed jobs in real-time
  while [ $(jobs -rp | wc -l) -ge $MAX_PARALLEL ]; do
    check_completed_dbs
    sleep 0.5
  done

  # Mark as running in terminal and update live master log
  echo "[RUNNING] Validation started for: $DB"
  DB_STATUSES["$DB"]="PENDING (Running...)"
  write_summary_master_log
  
  # Run compare_database in the background, silencing direct terminal output to prevent interleaving
  compare_database "$DB" >/dev/null 2>&1 &
done

# Wait for all background jobs to finish while continuing to update logs in real-time
echo "-------------------------------------------------------------"
echo "Waiting for all database validations to complete..."
while [ $(jobs -rp | wc -l) -gt 0 ]; do
  check_completed_dbs
  sleep 0.5
done

# Final scan to catch any late writes
check_completed_dbs

# Catch any databases that didn't generate a stats file (crashed)
for DB in $DATABASES; do
  if [ "${DB_STATUSES["$DB"]}" = "PENDING (Running...)" ] || [ "${DB_STATUSES["$DB"]}" = "PENDING" ]; then
    TOTAL_DBS_COMPARED=$((TOTAL_DBS_COMPARED + 1))
    TOTAL_DBS_FAILED=$((TOTAL_DBS_FAILED + 1))
    DB_STATUSES["$DB"]="FAILED"
    DB_ERRORS["$DB"]=1
    MISMATCHES+=("[$DB] Validation process terminated unexpectedly or failed to start")
    echo -e "[${RED}FAILED${RESET}] $DB crashed or terminated unexpectedly."
    write_summary_master_log
  fi
done

# ===============================
# OVERALL SUMMARY
# ===============================
echo ""
echo "=============================================================="
echo "OVERALL MIGRATION SUMMARY"
echo "=============================================================="
echo ""
printf "Source Server      : %s\n" "$SRC_HOST"
printf "Destination Server : %s\n" "$DEST_HOST"
echo ""
printf "Databases Compared : %s\n" "$TOTAL_DBS_COMPARED"
printf "Databases Passed   : %s\n" "$TOTAL_DBS_PASSED"
printf "Databases Failed   : %s\n" "$TOTAL_DBS_FAILED"
echo ""
echo "--------------------------------------------------------------"
echo ""
printf "Tables Compared    : %s\n" "$TOTAL_TABLES_COMPARED"
printf "Matched Tables     : %s\n" "$TOTAL_TABLES_MATCHED"
printf "Failed Tables      : %s\n" "$TOTAL_TABLES_FAILED"
echo ""
echo "--------------------------------------------------------------"
echo ""
printf "%-18s : %s\n" "Views" "$GLOBAL_VIEWS_STATUS"
printf "%-18s : %s\n" "Procedures" "$GLOBAL_PROCEDURES_STATUS"
printf "%-18s : %s\n" "Functions" "$GLOBAL_FUNCTIONS_STATUS"
printf "%-18s : %s\n" "Events" "$GLOBAL_EVENTS_STATUS"
printf "%-18s : %s\n" "Indexes" "$GLOBAL_INDEXES_STATUS"
printf "%-18s : %s\n" "Primary Keys" "$GLOBAL_PKS_STATUS"
printf "%-18s : %s\n" "Foreign Keys" "$GLOBAL_FKS_STATUS"
printf "%-18s : %s\n" "Unique Keys" "$GLOBAL_UNIQUES_STATUS"
printf "%-18s : %s\n" "Check Constraints" "$GLOBAL_CHECKS_STATUS"
printf "%-18s : %s\n" "Triggers" "$GLOBAL_TRIGGERS_STATUS"
printf "%-18s : %s\n" "Character Sets" "$GLOBAL_CHARSETS_STATUS"
printf "%-18s : %s\n" "Collations" "$GLOBAL_COLLATIONS_STATUS"
echo ""
echo "--------------------------------------------------------------"
echo ""
if [ ${#MISMATCHES[@]} -gt 0 ]; then
  # Write to dedicated mismatches/failures log file
  printf "%s\n" "${MISMATCHES[@]}" > "$FAILURE_LOG"

  echo "=============================================================="
  echo -e "${RED}DETAILED LIST OF MISMATCHES / FAILURES${RESET}"
  echo "=============================================================="
  for mismatch in "${MISMATCHES[@]}"; do
    echo -e "  $mismatch"
  done
  echo "=============================================================="
  echo ""
  echo "--------------------------------------------------------------"
  echo ""
fi
echo "Migration Validation Result"
echo ""
if [ "$TOTAL_DBS_FAILED" -eq 0 ]; then
  echo -e "${GREEN}SUCCESS${RESET}"
  echo ""
  echo "Ready for Cutover"
  EXIT_VAL=0
else
  echo -e "${RED}FAILED${RESET}"
  echo ""
  echo "Validation issues found. Do NOT proceed with cutover."
  EXIT_VAL=1
fi
echo ""
echo "=============================================================="
echo " Individual Logs : $BASE_ROOT/<db_name>/final_compare/"
echo " Consolidated Log: $GLOBAL_LOG"
if [ ${#MISMATCHES[@]} -gt 0 ]; then
  echo " Mismatches Only : $FAILURE_LOG"
else
  echo " Mismatches Only : None (All Matched!)"
fi
echo " Summary Master  : $SUMMARY_LOG"
echo "=============================================================="

# Final rewrite to ensure everything is marked completed
write_summary_master_log

exit $EXIT_VAL

Key Characteristics of This Approach
No intermediate/disposable replica is created — the dump runs directly against the live source.
No sustained FLUSH TABLES WITH READ LOCK or read_only=ON is required on the source, due to --trx-tables.
Consistency point is captured automatically by mydumper in the metadata file — no manual SHOW SLAVE STATUS/SHOW MASTER STATUS capture step needed.
Trade-off: the dump itself adds read load to the source for its full duration, since it is not offloaded to a separate replica. Size this against actual data volume and production traffic pattern before using this approach for a real cutover.
Reconnection uses binlog file + position (not GTID) — requires the Log_File/Pos values to be exact; a mismatch causes duplicate-key errors or data loss.
```

## Step 16: Complete Cutover (Remove Replication Master)
Once the validation script reports `SUCCESS` and you are ready to repoint applications, remove the master replication definition on the destination server and direct application traffic to the new Azure Flexible Server target:

```sql
CALL mysql.az_replication_remove_master;
```

Repoint the application to the Flexible Server target. `az_replication_stop` and `az_replication_remove_master` are fully self-service Data-in Replication stored procedures — no backend/support team dependency.

## Appendix: Additional Reference Queries

### Table Size Breakdown (Logical vs. File vs. Allocated)
SELECT
    t.table_name,
    ROUND((t.data_length + t.index_length) / 1024 / 1024/1024, 2) AS logical_size_gb,
    ROUND(ts.file_size / 1024 / 1024/1024 , 2) AS file_size_gb,
    ROUND(ts.allocated_size / 1024 / 1024/1024 , 2) AS allocated_size_gb
FROM information_schema.tables t
LEFT JOIN information_schema.innodb_tablespaces ts
    ON ts.name = CONCAT(t.table_schema, '/', t.table_name)
WHERE t.table_schema = 'primary_db'
  AND t.table_name = 'skus_warehouses'
ORDER BY allocated_size_gb DESC;

### Binary Log Inspection
```bash
mysql -h bt-26-jul-2026.mysql.database.azure.com -u btadmin -p
 
SHOW BINARY LOGS;
 
SHOW BINLOG EVENTS IN 'mysql-bin.755139' FROM 5686488 LIMIT 10;
 
SHOW BINLOG EVENTS IN 'mysql-bin.755139' LIMIT 50;
```

### Reference Links:
- [Configure Azure Database for MySQL Data-in Replication](https://learn.microsoft.com/en-us/azure/mysql/flexible-server/how-to-data-in-replication?tabs=bash%2Ccommand-line)
- [Migrate Large Databases to Azure Database for MySQL Using Mydumper/myloader](https://learn.microsoft.com/en-us/azure/mysql/migrate/concepts-migrate-mydumper-myloader)
- [Migrate Amazon RDS for MySQL Using Data-In Replication](https://learn.microsoft.com/en-us/azure/mysql/flexible-server/how-to-migrate-rds-mysql-data-in-replication)