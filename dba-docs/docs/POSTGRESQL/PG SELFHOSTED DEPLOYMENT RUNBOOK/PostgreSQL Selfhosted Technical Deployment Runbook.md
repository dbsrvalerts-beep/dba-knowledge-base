# PostgreSQL Selfhosted Technical Deployment Runbook

This runbook describes the end-to-end installation, tuning, configuration, and Business Continuity Planning (BCP) setup for a self-hosted PostgreSQL database cluster on Azure's Red Hat Enterprise Linux (RHEL) 8 VM.

---

## 1. Runbook Overview

### Why Self-Hosted PostgreSQL (SH PG)?
While managed cloud databases (such as Azure Database for PostgreSQL Flexible Server) offer convenience, a self-hosted deployment on a virtual machine (VM) provides:
- **Deeper Hardware Control:** Direct tuning of the file system, disk configurations (LVM), and kernel/memory optimizations.
- **Customized Extensions & Versioning:** Integration of specialized packages (e.g., custom builds of `pg_proctab` or `pg_stat_monitor`) that might be restricted or unsupported on PaaS.
- **Advanced Hook Scripts:** Capability to run custom script triggers, such as dynamically tuning configuration parameters during system boot based on the actual allocated VM size.
- **Cost & Network Topology Control:** Custom BCP pipelines utilizing utilities like `azcopy` integrated directly with local backup policies, bypassing cloud-managed vendor storage lock-ins.
- **Public IP Requirements:** Accommodates tools like Qlik which require public IP endpoints, whereas managed Azure instances typically restrict endpoints to private IPs.
- **Read Replica Access:** Fulfills strict customer demands for direct access to read replicas.
- **Performance Isolation:** Isolates larger databases on dedicated VMs to avoid "noisy neighbor" latency issues common in shared PaaS environments.

---

## 2. Prerequisites & Assumptions

Before starting the deployment, verify the following prerequisites are met:
1. **VM Provisioning:** A VM provisioned from a RHEL 8 base/clone template containing:
   - Core operating system installed (Red Hat Enterprise Linux 8).
   - Minimal PostgreSQL configuration files and binaries installed.
   - Primary OS hard disk (`/dev/<os_disk>` or equivalent, 64 GB).
   - Secondary hard disk allocated for PostgreSQL data storage (`/dev/<pg_data_disk>` or equivalent).
2. **Environment Variables:** The `postgres` user must have `$PGDATA` configured pointing to the data directory (typically `/u01/pgsql/<version>/data`).
3. **Permissions:** Root access (`sudo`) is required for OS level adjustments.

---

## 3. Phase 1: Operating System Configuration

### 3.1 Cron Job Suspend (Pre-configuration Safety)
To prevent legacy background scripts from executing during VM setup:
1. Log in to the server.
2. Open the `postgres` user's crontab editor:
   ```bash
   sudo -u postgres crontab -e
   ```
3. Update and comment out/disable the `postgres` user's cron entries as follows:
   - **Update the verification script entry**:
     Change from: `*/1 * * * * sh /u01/Gsl/ARCNAME.sh`
     To: `# */1 * * * * sh /u01/Gsl/ARCNAME.sh >/dev/null 2>&1`
   - **Update the times of these 3 backup/housekeeping cron entries**:
     ```cron
     # 05 00 * * * sh /u01/Gsl/BASEBKP.sh
     # 01 00 * * * sh /u01/Gsl/DELBASEBKP.sh
     # 00 23 * * * sh /u01/Gsl/DEL_AZCOPY_LOG.sh
     ```
   - **Append and comment out these new load analysis monitoring setup cron entries**:
     ```cron
     # */1 * * * * /u01/Gsl/collect_stmts.sh >> /u01/backup/logs/pgmon/stmts.log 2>&1
     # * * * * * /u01/Gsl/collect_sessions.sh >> /u01/backup/logs/pgmon/sessions.log 2>&1
     # * * * * * sleep 30; /u01/Gsl/collect_sessions.sh >> /u01/backup/logs/pgmon/sessions.log 2>&1
     # * * * * * /u01/Gsl/collect_db.sh >> /u01/backup/logs/pgmon/db.log 2>&1
     # 33 18 * * * /u01/Gsl/purge_monitoring.sh >> /u01/backup/logs/pgmon/purge.log 2>&1
     ```
4. **Final Suspended Crontab Look**:
   Verify that the `postgres` user's crontab matches this state:
   ```cron
   # */1 * * * * sh /u01/Gsl/ARCNAME.sh >/dev/null 2>&1
   # 05 00 * * * sh /u01/Gsl/BASEBKP.sh
   # 01 00 * * * sh /u01/Gsl/DELBASEBKP.sh
   # 00 23 * * * sh /u01/Gsl/DEL_AZCOPY_LOG.sh
   # */30 * * * * sh /u01/Gsl/Disk_usage.sh
   # */30 * * * * sh /u01/Gsl/LONG_QUERY.sh
   # */1 * * * * /u01/Gsl/collect_stmts.sh >> /u01/backup/logs/pgmon/stmts.log 2>&1
   # * * * * * /u01/Gsl/collect_sessions.sh >> /u01/backup/logs/pgmon/sessions.log 2>&1
   # * * * * * sleep 30; /u01/Gsl/collect_sessions.sh >> /u01/backup/logs/pgmon/sessions.log 2>&1
   # * * * * * /u01/Gsl/collect_db.sh >> /u01/backup/logs/pgmon/db.log 2>&1
   # 33 18 * * * /u01/Gsl/purge_monitoring.sh >> /u01/backup/logs/pgmon/purge.log 2>&1
   ```

### 3.2 LVM Partition Extension (PGDATA Disk Expansion)
#### Theory: Logical Volume Management (LVM)
LVM abstracts physical storage devices, allowing the operating system to resize storage volumes dynamically without shutting down services. It consists of:
- **Physical Volume (PV):** The raw hard disk partition (e.g., `/dev/<pg_data_disk>`).
- **Volume Group (VG):** A storage pool combining multiple PVs.
- **Logical Volume (LV):** The virtual partition carved from the VG, which hosts the filesystem (e.g., ext4, xfs).

#### Commands [To Be Executed as Root User only]:
To extend the volume hosting `/u01/pgsql/<version>/data` to use newly allocated VM storage:

1. Scan and detect the newly allocated disk space:
   ```bash
   # Resize the physical volume to match the virtual disk capacity
     pvresize /dev/{filesystem_device}
   ```
   *(Replace `{filesystem_device}` with your actual device name, e.g., `sdb` or `nvme0n1`)*.

2. Extend the logical volume and resize the underlying filesystem concurrently:
   ```bash
      lvextend -L +[Size]G -r /dev/[vg_name]/[lv_name]
   ```
   *Note: The `-r` flag triggers an online resize of the filesystem (XFS or EXT4) automatically.*

### 3.3 Hostname and Network Configuration
1. Update the hostname to reflect the environment naming conventions (e.g., `vm-psql-erp-prod-02`):
   ```bash
   sudo vi /etc/hostname
   # Enter the new hostname, save, and exit (Esc, :wq)

   or

   hostnamectl set-hostname vm-erpdb-psql-prod-09 [set hostname without system reboot]
   ```

### 3.4 System Timezone Configuration
Configure the system timezone to Asia/Kolkata (IST):

1. Check Current Timezone Settings:
   View the current active timezone and system clock parameters:
   ```bash
   timedatectl
   ```

2. Set the New Timezone:
   Change the system timezone to Asia/Kolkata (IST):
   ```bash
   sudo timedatectl set-timezone Asia/Kolkata
   ```

3. Verify the Clock Update:
   Verify the change immediately using the `timedatectl` or `date` commands:
   ```bash
   date
   ```
   *Expected Output: Thu Aug 20 13:06:02 IST 2026 (You will see the current timestamp as per your execution time)*

### 3.5 Cleanup of Legacy PostgreSQL Directories
If the VM template was provisioned with an older PostgreSQL version (e.g., version 16), remove its leftover data directory to avoid conflicts:
```bash
# Navigate to the postgres home directory
cd /var/lib/pgsql

# Remove the old version directory
rm -rf 16
```


2. Validate CPU, memory, and disk allocations:
   ```bash
   df -h / lsblk      # Check filesystem capacity
   free -m    # Validate RAM size
   lscpu      # Validate CPU core count
   ```
3. Restart the virtual machine to apply OS-level configurations:
   ```bash
   sudo reboot
   ```

---

## 4. Phase 2: PostgreSQL Systemd Auto-Tuning Configuration

### 4.1 Theory: Dynamic Tuning on VM Boot
PostgreSQL does not natively adjust its memory/CPU parameters when host system specifications change (such as adding/Reducing RAM or CPU cores to a VM).
To resolve this, we configure a systemd `ExecStartPre` hook. This script executes prior to the engine startup, analyzing the current VM hardware resources, dynamically tuning PostgreSQL configuration variables, and writing them to `postgresql.conf`.

### 4.2 Deploying the Auto-Tune Script
Create the directory structure for backups and logs, and create the auto-tune script:
```bash
sudo mkdir -p /u01/backup/logs/autotune
sudo mkdir -p /u01/backup/logs/autotune/config_backup
sudo mkdir -p /u01/Gsl
sudo vi /u01/Gsl/pg_autotune_systemd.sh
```

Insert the following script content (`pg_autotune_systemd.sh` v4):

```bash
#!/bin/bash
# pg_autotune_systemd.sh — Version 7
# Detects hardware changes, modifies postgresql.conf, and prepares the OS so the
# Linux OOM killer does not take PostgreSQL down.
# Designed to be run via Systemd ExecStartPre hook:
#     ExecStartPre=+/u01/Gsl/pg_autotune_systemd.sh
# Manual health check at any time (as root):
#     /u01/Gsl/pg_autotune_systemd.sh --verify
#
# V7 Changes:
#   - max_parallel_workers_per_gather is fixed in USER CONFIGURATION
#     (no longer taken from the pgconfig.org API or the min(4, CPU/2) fallback formula)
# V6 Changes:
#   - Kernel memory reserve managed here (check, add if missing, apply, verify):
#       vm.min_free_kbytes        = 0.4% of RAM, kept between 256 MB and 2 GB
#       vm.watermark_scale_factor = 200
#     Written to /etc/sysctl.d/90-postgres-memory.conf and applied live.
#   - Transparent Huge Pages managed here (check, fix, persist, verify):
#     runtime enabled/defrag = madvise, kernel cmdline transparent_hugepage=madvise.
#   - huge_pages = on set in postgresql.conf if missing (check + verify).
#   - Warns when postgresql.auto.conf overrides a parameter autotune manages.
#   - Checks (does not change) the service OOM settings: -1000 / backends 0.
#   - PASS / WARN / FAIL line for every step + a PRE-START SUMMARY.
#   - After every start, a background check waits for PostgreSQL and verifies
#     everything on the running server (VERIFY SUMMARY in the same log,
#     also sent to syslog/journal with tag pg_autotune).
#   - New --verify mode for a manual health check; changes nothing.
#   - Steps 1-10 run on every start; only the parameter retune (step 4-7)
#     depends on a hardware change.
# V5 Changes:
#   - Huge pages sizing on EVERY start: reads shared_memory_size_in_huge_pages
#     from the stopped server, adds 2%, reserves vm.nr_hugepages live.
#     Not kept in sysctl files (safe on scale-down). Falls back to
#     huge_pages = try if pages are short; restores 'on' automatically.
#   - PostgreSQL version read from PGDATA/PG_VERSION. TEST_SLEEP_SECONDS = 0.
# V4 Changes:
#   - max_parallel_workers_per_gather fallback formula updated to: min(4, CPU/2)
#   - Email functionality removed entirely
# V3 Changes from V2:
#   - shared_buffers      : 25% → 26% of RAM
#   - effective_cache_size: 75% → 76% of RAM
#   - systemctl log message now uses dynamic PG_VERSION (no hardcoded '16')

# --- USER CONFIGURATION ---
MAX_CONNECTIONS=5000
WORK_MEM_MB=500
WAL_BUFFERS_MB=32
MAX_PARALLEL_WORKERS_PER_GATHER=4      # fixed value (not from pgconfig.org, not calculated); keep <= max_parallel_workers
TEST_SLEEP_SECONDS=0
# --------------------------

# --- OOM HARDENING CONFIGURATION (V6) ---
HUGEPAGES_ENABLE=1                 # 1 = set huge_pages = on and size vm.nr_hugepages
HUGEPAGES_MARGIN_PCT=2             # pages = PostgreSQL's need + 2%
HUGEPAGES_MAX_PCT=70               # never reserve more than this % of RAM
KERNEL_RESERVE_ENABLE=1            # 1 = manage vm.min_free_kbytes / vm.watermark_scale_factor
MIN_FREE_PER_MILLE=4               # min_free_kbytes = 0.4% of RAM ...
MIN_FREE_MIN_KB=262144             # ... but at least 256 MB
MIN_FREE_MAX_KB=2097152            # ... and at most 2 GB
WATERMARK_SCALE_FACTOR=200
THP_ENABLE=1                       # 1 = keep Transparent Huge Pages at madvise
VERIFY_AFTER_START=1               # 1 = check the running server after every start
VERIFY_TIMEOUT_SECONDS=900         # how long the post-start check waits for PostgreSQL
SYSCTL_FILE="/etc/sysctl.d/90-postgres-memory.conf"
THP_DIR="/sys/kernel/mm/transparent_hugepage"
# -----------------------------------------

# --- MODE ---
MODE="start"                       # start = ExecStartPre (default)
case "${1:-}" in
    --verify)             MODE="verify" ;;
    --verify-after-start) MODE="verify-after-start" ;;
esac

# --- LOGGING CONFIGURATION ---
LOG_DIR="/u01/backup/logs/autotune"
if [ "$MODE" = "verify-after-start" ] && [ -n "${2:-}" ]; then
    LOG_FILE="$2"                                      # append to the start's own log
elif [ "$MODE" = "verify" ]; then
    LOG_FILE="${LOG_DIR}/pg_autotune_verify_$(date +'%Y%m%d_%H%M%S').log"
else
    LOG_FILE="${LOG_DIR}/pg_autotune_$(date +'%Y%m%d_%H%M%S').log"
fi

# Auto-create log directory if it does not exist
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR" 2>/dev/null
fi
mkdir -p "${LOG_DIR}/config_backup" 2>/dev/null

# Create the log file first: with --verify, tee creates it in the background,
# so the existence check below could run before the file exists.
touch "$LOG_FILE" 2>/dev/null

# Redirect all output to the log file (manual --verify also prints to the screen)
if [ "$MODE" = "verify" ] && [ -t 1 ]; then
    exec > >(tee -a "$LOG_FILE") 2>&1
else
    exec >> "$LOG_FILE" 2>&1
fi

# Verify the log file was actually created (exec fails silently if dir is unwritable)
if [ ! -f "$LOG_FILE" ]; then
    # Fall back to stderr — visible via: journalctl -u postgresql-PG_VERSION
    exec >&2
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] CRITICAL: Cannot write to log file: $LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] CRITICAL: Check that $LOG_DIR exists and is writable by root."
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] CRITICAL: Continuing — all output will appear in journalctl."
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# --- CHECK RESULT HELPERS ----------------------------------------------------
N_PASS=0; N_WARN=0; N_FAIL=0; FAIL_LIST=""
pass() { N_PASS=$((N_PASS + 1)); log "  [PASS] $*"; }
warn() { N_WARN=$((N_WARN + 1)); log "  [WARN] $*"; }
fail() { N_FAIL=$((N_FAIL + 1)); FAIL_LIST="${FAIL_LIST}; $*"; log "  [FAIL] $*"; }
summary() {   # $1 = title
    local result="PASS"
    [ "$N_WARN" -gt 0 ] && result="PASS WITH WARNINGS"
    [ "$N_FAIL" -gt 0 ] && result="FAIL"
    log "-----------------------------------------------------------------"
    log "$1: ${result}   (pass=${N_PASS} warn=${N_WARN} fail=${N_FAIL})"
    [ "$N_FAIL" -gt 0 ] && log "Failed checks:${FAIL_LIST#;}"
    log "-----------------------------------------------------------------"
    if [ "$N_FAIL" -gt 0 ]; then
        logger -t pg_autotune -p daemon.err "$1: FAIL (${N_FAIL} failed) on $(hostname) - see $LOG_FILE" 2>/dev/null
    else
        logger -t pg_autotune -p daemon.notice "$1: ${result} on $(hostname) - see $LOG_FILE" 2>/dev/null
    fi
}
reset_counts() { N_PASS=0; N_WARN=0; N_FAIL=0; FAIL_LIST=""; }

meminfo_kb() { awk -v k="$1:" '$1==k{print $2}' /proc/meminfo; }
thp_mode()   { sed -n 's/.*\[\(.*\)\].*/\1/p' "${THP_DIR}/$1" 2>/dev/null; }

# --- FUNCTIONS -----------------------------------------------------------------

# Direct File Modification Function
# Logs a before-and-after trace for every parameter change.
set_pg_param() {
    local key=$1
    local val=$2
    local prev_val
    if grep -qE "^\s*#?\s*${key}\s*=" "$PG_CONF"; then
        prev_val=$(grep -E "^\s*#?\s*${key}\s*=" "$PG_CONF" | head -n 1)
        sed -i -E "s/^\s*#?\s*${key}\s*=.*/${key} = ${val}/g" "$PG_CONF"
        log "Updated parameter:  [${prev_val}]   --->   [${key} = ${val}]"
    else
        echo "${key} = ${val}" >> "$PG_CONF"
        log "Added NEW parameter:   [${key} = ${val}]"
    fi
}

# Effective value of a parameter (postgresql.conf + postgresql.auto.conf), server stopped
pg_effective() {
    runuser -u postgres -- "/usr/pgsql-${PG_VERSION}/bin/postgres" -D "$PGDATA_DIR" -C "$1" 2>/dev/null
}

# Locate PGDATA / postgresql.conf and the PostgreSQL major version
discover() {
    log "Locating postgresql.conf dynamically using PGDATA..."
    if [ -n "$PGDATA" ] && [ -f "$PGDATA/postgresql.conf" ]; then
        PG_CONF="$PGDATA/postgresql.conf"
        PGDATA_DIR="$PGDATA"
    else
        # Attempt to load the postgres user's environment variables (useful if running from root crontab)
        PGDATA_ENV=$(su - postgres -c 'echo $PGDATA' 2>/dev/null | grep -v '^\s*$' | tail -n 1)
        if [ -n "$PGDATA_ENV" ] && [ -f "$PGDATA_ENV/postgresql.conf" ]; then
            PG_CONF="$PGDATA_ENV/postgresql.conf"
            PGDATA_DIR="$PGDATA_ENV"
        else
            log "CRITICAL: \$PGDATA environment variable is not set or postgresql.conf not found inside it."
            log "Please ensure \$PGDATA is exported, or set PG_CONF manually."
            exit 1
        fi
    fi
    PGDATA_DIR="${PGDATA_DIR%/}"
    PG_AUTO_CONF="${PGDATA_DIR}/postgresql.auto.conf"
    log "Found PostgreSQL Configuration: $PG_CONF"

    # systemd PATH does not include /usr/pgsql-NN/bin, so `postgres -V` can fail there.
    # The data directory's own PG_VERSION file is authoritative for the major version.
    PG_VERSION=""
    if [ -f "${PGDATA_DIR}/PG_VERSION" ]; then
        PG_VERSION=$(cut -d. -f1 "${PGDATA_DIR}/PG_VERSION")
    fi
    if [ -z "$PG_VERSION" ]; then
        PG_VERSION=$(postgres -V 2>/dev/null | awk '{print $NF}' | cut -d. -f1)
    fi
    if [ -z "$PG_VERSION" ]; then
        PG_VERSION=$(psql -V 2>/dev/null | awk '{print $3}' | cut -d. -f1)
    fi
    if [ -z "$PG_VERSION" ]; then
        PG_VERSION="17" # Fallback
    fi
    PG_BIN="/usr/pgsql-${PG_VERSION}/bin"
    log "Detected PostgreSQL Version: $PG_VERSION"
}

min_free_target_kb() {
    local mem_kb t
    mem_kb=$(meminfo_kb MemTotal)
    t=$(( mem_kb * MIN_FREE_PER_MILLE / 1000 ))
    [ "$t" -lt "$MIN_FREE_MIN_KB" ] && t=$MIN_FREE_MIN_KB
    [ "$t" -gt "$MIN_FREE_MAX_KB" ] && t=$MIN_FREE_MAX_KB
    echo "$t"
}

# STEP A: kernel free-memory reserve (check, add if missing, apply live, verify)
ensure_kernel_reserve() {
    log "STEP A: Kernel memory reserve"
    [ "$KERNEL_RESERVE_ENABLE" -eq 1 ] || { warn "Kernel reserve management disabled in script configuration"; return 0; }

    local mf wsf want cur_mf cur_wsf f
    mf=$(min_free_target_kb)
    wsf=$WATERMARK_SCALE_FACTOR
    want=$(printf '# Managed by pg_autotune_systemd.sh - do not edit by hand\n# vm.nr_hugepages is set by pg_autotune_systemd.sh at every PostgreSQL start\nvm.min_free_kbytes = %s\nvm.watermark_scale_factor = %s\n' "$mf" "$wsf")

    # 1. persistent file
    if [ -f "$SYSCTL_FILE" ] && [ "$(cat "$SYSCTL_FILE")" = "$want" ]; then
        log "  $SYSCTL_FILE already correct."
    else
        [ -f "$SYSCTL_FILE" ] && cp -p "$SYSCTL_FILE" "${LOG_DIR}/config_backup/$(basename "$SYSCTL_FILE").backup.$(date +%Y%m%d_%H%M%S)"
        printf '%s\n' "$want" > "$SYSCTL_FILE"
        log "  Wrote $SYSCTL_FILE (min_free_kbytes=${mf}, watermark_scale_factor=${wsf})."
    fi

    # 2. live values
    cur_mf=$(cat /proc/sys/vm/min_free_kbytes)
    cur_wsf=$(cat /proc/sys/vm/watermark_scale_factor)
    if [ "$cur_mf" != "$mf" ];   then sysctl -q -w vm.min_free_kbytes="$mf";          log "  vm.min_free_kbytes ${cur_mf} -> ${mf}"; fi
    if [ "$cur_wsf" != "$wsf" ]; then sysctl -q -w vm.watermark_scale_factor="$wsf";  log "  vm.watermark_scale_factor ${cur_wsf} -> ${wsf}"; fi

    # 3. verify
    [ "$(cat /proc/sys/vm/min_free_kbytes)" = "$mf" ] \
        && pass "vm.min_free_kbytes = ${mf} ($((mf / 1024)) MB)" \
        || fail "vm.min_free_kbytes is $(cat /proc/sys/vm/min_free_kbytes), expected ${mf}"
    [ "$(cat /proc/sys/vm/watermark_scale_factor)" = "$wsf" ] \
        && pass "vm.watermark_scale_factor = ${wsf}" \
        || fail "vm.watermark_scale_factor is $(cat /proc/sys/vm/watermark_scale_factor), expected ${wsf}"
    grep -q "^vm.min_free_kbytes = ${mf}$" "$SYSCTL_FILE" 2>/dev/null \
        && pass "Persisted in $SYSCTL_FILE" || fail "Not persisted in $SYSCTL_FILE"

    # 4. other files that also set these keys
    for f in /etc/sysctl.conf /etc/sysctl.d/*.conf /run/sysctl.d/*.conf /usr/lib/sysctl.d/*.conf; do
        [ -f "$f" ] && [ "$f" != "$SYSCTL_FILE" ] || continue
        if grep -qE '^\s*vm\.(min_free_kbytes|watermark_scale_factor)\s*=' "$f"; then
            warn "$f also sets min_free_kbytes/watermark_scale_factor (this script re-applies its values at every start)"
        fi
    done
    return 0
}

# STEP B: Transparent Huge Pages = madvise (runtime now + kernel cmdline for boot)
ensure_thp() {
    log "STEP B: Transparent Huge Pages"
    [ "$THP_ENABLE" -eq 1 ] || { warn "THP management disabled in script configuration"; return 0; }
    if [ ! -f "${THP_DIR}/enabled" ]; then
        warn "${THP_DIR} not found - THP not available on this kernel, nothing to do"
        return 0
    fi

    local k m args
    for k in enabled defrag; do
        m=$(thp_mode "$k")
        if [ "$m" = "always" ]; then
            echo madvise > "${THP_DIR}/$k" 2>/dev/null
            log "  THP $k: always -> madvise"
        fi
        m=$(thp_mode "$k")
        case "$m" in
            madvise|never) pass "THP $k = $m" ;;
            *)             fail "THP $k = $m (expected madvise)" ;;
        esac
    done

    # persist for next boot
    if command -v grubby >/dev/null 2>&1; then
        args=$(grubby --info=DEFAULT 2>/dev/null | sed -n 's/^args=//p')
        if echo "$args" | grep -qE 'transparent_hugepage=(madvise|never)'; then
            pass "Kernel cmdline persisted ($(echo "$args" | grep -oE 'transparent_hugepage=[a-z]+'))"
        else
            grubby --update-kernel=ALL --remove-args="transparent_hugepage" >/dev/null 2>&1
            grubby --update-kernel=ALL --args="transparent_hugepage=madvise" >/dev/null 2>&1
            args=$(grubby --info=DEFAULT 2>/dev/null | sed -n 's/^args=//p')
            echo "$args" | grep -q 'transparent_hugepage=madvise' \
                && pass "Kernel cmdline updated: transparent_hugepage=madvise (from next boot)" \
                || fail "Could not add transparent_hugepage=madvise with grubby"
        fi
    else
        warn "grubby not found - THP is fixed at every start by this script, but not on the kernel cmdline"
    fi
    return 0
}

# STEP C: huge_pages = on in postgresql.conf (check, set if missing, verify effective value)
ensure_huge_pages_on() {
    log "STEP C: huge_pages parameter"
    [ "$HUGEPAGES_ENABLE" -eq 1 ] || { warn "Huge pages management disabled in script configuration"; return 0; }

    local line eff
    line=$(grep -E '^\s*huge_pages\s*=' "$PG_CONF" | tail -n 1)
    if echo "$line" | grep -q 'autotune-fallback'; then
        log "  postgresql.conf has the autotune fallback (try); STEP D restores 'on' when pages are available."
    elif ! echo "$line" | grep -qE "^\s*huge_pages\s*=\s*'?on'?\s*(#.*)?$"; then
        set_pg_param "huge_pages" "on"
    else
        log "  huge_pages = on already in postgresql.conf."
    fi

    eff=$(pg_effective huge_pages)
    case "$eff" in
        on)  pass "huge_pages effective value = on" ;;
        try) if grep -qE '^\s*huge_pages\s*=.*autotune-fallback' "$PG_CONF"; then
                 warn "huge_pages effective value = try (autotune fallback active)"
             else
                 fail "huge_pages effective value = try - postgresql.auto.conf overrides it (run: ALTER SYSTEM RESET huge_pages)"
             fi ;;
        *)   fail "huge_pages effective value = '${eff}' - check postgresql.auto.conf (ALTER SYSTEM RESET huge_pages)" ;;
    esac
    return 0
}

# Parameters autotune manages that postgresql.auto.conf (ALTER SYSTEM) would override
check_overrides() {
    log "STEP E: Overrides in postgresql.auto.conf"
    local p found=0
    [ -f "$PG_AUTO_CONF" ] || { pass "No postgresql.auto.conf"; return 0; }
    for p in shared_buffers effective_cache_size maintenance_work_mem work_mem wal_buffers \
             max_worker_processes max_parallel_workers max_parallel_workers_per_gather huge_pages; do
        if grep -qE "^\s*${p}\s*=" "$PG_AUTO_CONF"; then
            warn "${p} is set in postgresql.auto.conf and overrides autotune (run: ALTER SYSTEM RESET ${p})"
            found=1
        fi
    done
    [ "$found" -eq 0 ] && pass "No autotune parameter is overridden by postgresql.auto.conf"
    return 0
}

# Service OOM settings: CHECK ONLY. OOMScoreAdjust applies to ExecStartPre too,
# so this script's own value shows what the postmaster will get.
check_oom_service() {
    log "STEP F: OOM protection in the service (check only, not changed)"
    local self_adj
    self_adj=$(cat /proc/self/oom_score_adj 2>/dev/null)
    [ "$self_adj" = "-1000" ] \
        && pass "Service OOMScoreAdjust = -1000 (postmaster will be protected)" \
        || warn "Service OOMScoreAdjust is ${self_adj}, expected -1000 (check postgresql-${PG_VERSION}.service)"
    if [ -n "$PG_OOM_ADJUST_FILE" ] && [ "${PG_OOM_ADJUST_VALUE:-0}" = "0" ]; then
        pass "PG_OOM_ADJUST_FILE set, PG_OOM_ADJUST_VALUE = ${PG_OOM_ADJUST_VALUE:-0} (backends killable)"
    else
        warn "PG_OOM_ADJUST_FILE='${PG_OOM_ADJUST_FILE}' PG_OOM_ADJUST_VALUE='${PG_OOM_ADJUST_VALUE}' - expected file set and value 0"
    fi
    return 0
}

# STEP D: Huge pages sizing. Runs while PostgreSQL is stopped.
# Never blocks the start: every failure path logs and returns 0.
tune_hugepages() {
    log "STEP D: Huge pages sizing"
    [ "$HUGEPAGES_ENABLE" -eq 1 ] || { warn "Huge pages management disabled in script configuration"; return 0; }

    local hp_mode need margin target have mem_kb hp_kb max_pages f active=0
    if [ ! -x "${PG_BIN}/postgres" ]; then
        fail "${PG_BIN}/postgres not found - huge pages not sized"
        return 0
    fi

    hp_mode=$(pg_effective huge_pages)
    if [ "$hp_mode" = "off" ]; then
        warn "huge_pages = off - huge pages not sized"
        return 0
    fi

    need=$(pg_effective shared_memory_size_in_huge_pages)
    case "$need" in
        ''|*[!0-9]*) fail "Could not read shared_memory_size_in_huge_pages (got '${need}')"; return 0 ;;
    esac
    if [ "$need" -le 0 ]; then
        warn "PostgreSQL reports 0 huge pages needed"
        return 0
    fi

    margin=$(( (need * HUGEPAGES_MARGIN_PCT + 99) / 100 ))
    target=$(( need + margin ))
    have=$(meminfo_kb HugePages_Total)
    log "  huge_pages=${hp_mode}  needed=${need}  target=${target} (+${HUGEPAGES_MARGIN_PCT}%)  reserved_now=${have}"

    # Safety: never reserve more than HUGEPAGES_MAX_PCT of RAM
    mem_kb=$(meminfo_kb MemTotal)
    hp_kb=$(meminfo_kb Hugepagesize)
    max_pages=$(( mem_kb * HUGEPAGES_MAX_PCT / 100 / hp_kb ))
    if [ "$target" -gt "$max_pages" ]; then
        fail "Target ${target} pages is more than ${HUGEPAGES_MAX_PCT}% of RAM (max ${max_pages}) - not reserving, check shared_buffers"
        target=0
    fi

    # vm.nr_hugepages must not live in sysctl files (an old value could over-reserve after a scale-down)
    for f in /etc/sysctl.conf /etc/sysctl.d/*.conf; do
        [ -f "$f" ] || continue
        if grep -qE '^\s*vm\.nr_hugepages\s*=' "$f"; then
            sed -i -E 's/^(\s*vm\.nr_hugepages\s*=.*)/# \1   # disabled: managed by pg_autotune_systemd.sh/' "$f"
            log "  Commented out vm.nr_hugepages in $f (this script manages it)."
        fi
    done
    for f in /etc/sysctl.conf /etc/sysctl.d/*.conf; do
        [ -f "$f" ] && grep -qE '^\s*vm\.nr_hugepages\s*=' "$f" && active=1
    done
    [ "$active" -eq 0 ] && pass "No active vm.nr_hugepages line in sysctl files" \
                        || fail "An active vm.nr_hugepages line is still in a sysctl file"

    if [ "$have" -ne "$target" ]; then
        # Growing on a running system needs contiguous 2 MB blocks: compact first
        if [ "$target" -gt "$have" ]; then
            echo 1 > /proc/sys/vm/compact_memory 2>/dev/null
        fi
        sysctl -q -w vm.nr_hugepages="$target"
        have=$(meminfo_kb HugePages_Total)
        log "  vm.nr_hugepages set to ${target}, kernel reserved ${have}."
    else
        log "  Already reserved, no change."
    fi

    if [ "$have" -ge "$need" ]; then
        pass "Huge pages reserved: ${have} (needed ${need}, $(( have * hp_kb / 1024 )) MB)"
        if grep -qE '^\s*huge_pages\s*=.*autotune-fallback' "$PG_CONF"; then
            # An earlier start fell back to 'try'; pages are available again -> restore 'on'
            set_pg_param "huge_pages" "on"
            pass "huge_pages restored to 'on' after an earlier fallback"
        fi
    else
        warn "Only ${have} of ${need} huge pages could be reserved"
        if [ "$hp_mode" = "on" ]; then
            set_pg_param "huge_pages" "try   # autotune-fallback"
            warn "huge_pages set to 'try' so PostgreSQL starts WITHOUT huge pages. ACTION: reboot the VM in a window; 'on' is restored automatically."
        fi
    fi
    return 0
}

# Checks on the RUNNING server. Used by --verify and by the post-start check.
verify_running() {
    reset_counts
    log "================================================================="
    log "VERIFY: checking the running PostgreSQL ${PG_VERSION} server"
    local pidfile pm port sock exe cg adj total bad c tot fre rsv used k m args f active=0 mf

    pidfile="${PGDATA_DIR}/postmaster.pid"
    pm=$(head -n 1 "$pidfile" 2>/dev/null)
    exe=$(readlink "/proc/${pm}/exe" 2>/dev/null); exe=${exe% (deleted)}
    if [ -z "$pm" ] || [ "$exe" != "${PG_BIN}/postgres" ]; then
        fail "PostgreSQL is not running (no live postmaster in ${pidfile})"
        summary "VERIFY SUMMARY"
        return 0
    fi
    port=$(sed -n 4p "$pidfile"); sock=$(sed -n 5p "$pidfile")

    # 1. accepting connections
    if "${PG_BIN}/pg_isready" -q -h "${sock:-/tmp}" -p "${port:-5432}" -t 10; then
        pass "PostgreSQL accepting connections (port ${port})"
    else
        fail "PostgreSQL not accepting connections (port ${port})"
    fi

    # 2. running under the service
    cg=$(grep -E ':memory:|^0::' "/proc/${pm}/cgroup" | head -n 1)
    echo "$cg" | grep -q "postgresql-${PG_VERSION}.service" \
        && pass "Postmaster ${pm} runs under postgresql-${PG_VERSION}.service" \
        || fail "Postmaster ${pm} is NOT under postgresql-${PG_VERSION}.service (${cg}) - started by hand?"

    # 3. OOM protection
    adj=$(cat "/proc/${pm}/oom_score_adj")
    [ "$adj" = "-1000" ] && pass "Postmaster oom_score_adj = -1000" \
                         || fail "Postmaster oom_score_adj = ${adj} (expected -1000)"
    total=0; bad=0
    for c in $(pgrep -P "$pm"); do
        total=$((total + 1))
        [ "$(cat "/proc/${c}/oom_score_adj" 2>/dev/null)" = "0" ] || bad=$((bad + 1))
    done
    [ "$bad" -eq 0 ] && pass "All ${total} child processes oom_score_adj = 0" \
                     || fail "${bad} of ${total} child processes not at oom_score_adj 0"

    # 4. huge pages in use
    tot=$(meminfo_kb HugePages_Total); fre=$(meminfo_kb HugePages_Free); rsv=$(meminfo_kb HugePages_Rsvd)
    used=$(( tot - fre + rsv ))
    if [ "$tot" -gt 0 ] && [ "$used" -gt 0 ]; then
        pass "PostgreSQL is using huge pages (${used} of ${tot} reserved)"
    elif [ "$tot" -gt 0 ]; then
        fail "${tot} huge pages reserved but PostgreSQL is not using them"
    else
        fail "No huge pages reserved"
    fi
    if grep -qE '^\s*huge_pages\s*=.*autotune-fallback' "$PG_CONF"; then
        warn "huge_pages fallback (try) is active - reboot the VM in a window"
    fi
    log "  PageTables = $(( $(meminfo_kb PageTables) / 1024 )) MB"

    # 5. kernel reserve
    if [ "$KERNEL_RESERVE_ENABLE" -eq 1 ]; then
        mf=$(min_free_target_kb)
        [ "$(cat /proc/sys/vm/min_free_kbytes)" = "$mf" ] && pass "vm.min_free_kbytes = ${mf}" \
            || fail "vm.min_free_kbytes = $(cat /proc/sys/vm/min_free_kbytes) (expected ${mf})"
        [ "$(cat /proc/sys/vm/watermark_scale_factor)" = "$WATERMARK_SCALE_FACTOR" ] && pass "vm.watermark_scale_factor = ${WATERMARK_SCALE_FACTOR}" \
            || fail "vm.watermark_scale_factor = $(cat /proc/sys/vm/watermark_scale_factor) (expected ${WATERMARK_SCALE_FACTOR})"
    fi

    # 6. THP
    if [ "$THP_ENABLE" -eq 1 ] && [ -f "${THP_DIR}/enabled" ]; then
        for k in enabled defrag; do
            m=$(thp_mode "$k")
            case "$m" in madvise|never) pass "THP ${k} = ${m}" ;; *) fail "THP ${k} = ${m} (expected madvise)" ;; esac
        done
        if command -v grubby >/dev/null 2>&1; then
            args=$(grubby --info=DEFAULT 2>/dev/null | sed -n 's/^args=//p')
            echo "$args" | grep -qE 'transparent_hugepage=(madvise|never)' \
                && pass "THP persisted on kernel cmdline" || warn "THP not on kernel cmdline"
        fi
    fi

    # 7. no nr_hugepages in sysctl files
    for f in /etc/sysctl.conf /etc/sysctl.d/*.conf; do
        [ -f "$f" ] && grep -qE '^\s*vm\.nr_hugepages\s*=' "$f" && active=1
    done
    [ "$active" -eq 0 ] && pass "No active vm.nr_hugepages line in sysctl files" \
                        || fail "Active vm.nr_hugepages line found in a sysctl file"

    # 8. autostart
    [ "$(systemctl is-enabled "postgresql-${PG_VERSION}" 2>/dev/null)" = "enabled" ] \
        && pass "postgresql-${PG_VERSION} enabled at boot" \
        || warn "postgresql-${PG_VERSION} is not enabled at boot (systemctl enable postgresql-${PG_VERSION})"

    summary "VERIFY SUMMARY"
    return 0
}

# Wait for the server started by systemd, then verify (runs in the background)
verify_after_start() {
    echo 0 > /proc/self/oom_score_adj 2>/dev/null      # this checker must stay killable
    local waited=0 pm exe port sock
    log "================================================================="
    log "POST-START CHECK: waiting up to ${VERIFY_TIMEOUT_SECONDS}s for PostgreSQL to accept connections..."
    sleep 10
    while [ "$waited" -lt "$VERIFY_TIMEOUT_SECONDS" ]; do
        pm=$(head -n 1 "${PGDATA_DIR}/postmaster.pid" 2>/dev/null)
        exe=$(readlink "/proc/${pm}/exe" 2>/dev/null); exe=${exe% (deleted)}
        if [ -n "$pm" ] && [ "$exe" = "${PG_BIN}/postgres" ]; then
            port=$(sed -n 4p "${PGDATA_DIR}/postmaster.pid"); sock=$(sed -n 5p "${PGDATA_DIR}/postmaster.pid")
            "${PG_BIN}/pg_isready" -q -h "${sock:-/tmp}" -p "${port:-5432}" -t 5 && break
        fi
        sleep 10; waited=$((waited + 10))
    done
    sleep 5   # let autovacuum launcher / background workers come up
    verify_running
}

start_background_verify() {
    [ "$VERIFY_AFTER_START" -eq 1 ] || return 0
    local self
    self=$(readlink -f "$0")
    setsid nohup "$self" --verify-after-start "$LOG_FILE" >/dev/null 2>&1 < /dev/null &
    log "Post-start check scheduled in the background (results will be appended to this log)."
}
# -------------------------------------------------------------------------------

# --- INTERNAL STATE (Do not modify manually) ---
LAST_KNOWN_STATE="63883MB_RAM-8_CPUS"
# -----------------------------------------------

# ===============================================================================
# VERIFY MODES (change nothing)
# ===============================================================================
if [ "$MODE" = "verify" ] || [ "$MODE" = "verify-after-start" ]; then
    if [ "$(id -u)" -ne 0 ]; then
        log "NOTE: not running as root - run 'sudo $0 --verify' for complete results (grubby needs root)."
    fi
    discover
    if [ "$MODE" = "verify-after-start" ]; then verify_after_start; else verify_running; fi
    exit 0
fi

# ===============================================================================
# START MODE (ExecStartPre, PostgreSQL is stopped)
# ===============================================================================
log "================================================================="
log "Executing PostgreSQL Auto-Tune Hook  (v7)"

# 1. Dynamically Locate postgresql.conf + version
discover

# 2. Detect Hardware
# Note: MemTotal includes reserved huge pages, so reserving them does NOT look like a hardware change.
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))
TOTAL_RAM_GB=$((TOTAL_RAM_MB / 1024))
CPU_CORES=$(nproc)

log "Detected Hardware: ${TOTAL_RAM_MB}MB RAM  |  ${CPU_CORES} CPU Cores"

CURRENT_STATE="${TOTAL_RAM_MB}MB_RAM-${CPU_CORES}_CPUS"

# 3. Hardware Change Validation (Self-contained)
HW_CHANGED=1
if [ "$CURRENT_STATE" == "$LAST_KNOWN_STATE" ]; then
    log "Hardware unchanged ($CURRENT_STATE). Skipping parameter retune."
    HW_CHANGED=0
fi

if [ "$HW_CHANGED" -eq 1 ]; then
    log "================================================================="
    log "HARDWARE CHANGE DETECTED!"
    log "Previous Hardware: $LAST_KNOWN_STATE"
    log "New Hardware:      $CURRENT_STATE"
    log "================================================================="

    # 4. Memory Parameters (Local Math)
    # shared_buffers      = 26% of OS-visible physical RAM (MemTotal)
    # effective_cache_size= 76% of OS-visible physical RAM (MemTotal)  [planner hint only]
    # maintenance_work_mem= 5% of RAM (RAM_GB / 20), minimum 1 GB
    SHARED_BUFFERS_MB=$(( (TOTAL_RAM_MB * 26) / 100 ))
    EFFECTIVE_CACHE_MB=$(( (TOTAL_RAM_MB * 76) / 100 ))

    MAINT_WORK_MEM_GB=$((TOTAL_RAM_GB / 20))
    if [ "$MAINT_WORK_MEM_GB" -lt 1 ]; then MAINT_WORK_MEM_GB=1; fi
    MAINT_WORK_MEM_MB=$((MAINT_WORK_MEM_GB * 1024))

    # work_mem, wal_buffers and max_parallel_workers_per_gather are static —
    # set via the USER CONFIGURATION block above

    # 5. CPU/Parallel Parameters (API with Local Fallback)
    #    max_worker_processes and max_parallel_workers only;
    #    max_parallel_workers_per_gather is fixed in USER CONFIGURATION.
    API_URL="https://api.pgconfig.org/v1/tuning/get-config?format=conf&max_connections=${MAX_CONNECTIONS}&pg_version=${PG_VERSION}&environment_name=OLTP&total_ram=${TOTAL_RAM_GB}&cpus=${CPU_CORES}&drive_type=SSD&arch=x86-64&os_type=linux"
    log "Calling pgconfig.org API for CPU/parallel parameters..."
    API_CONF=$(curl -s --max-time 5 "$API_URL" 2>/dev/null)

    if [ -n "$API_CONF" ] && echo "$API_CONF" | grep -q "max_parallel_workers"; then
        log "API call succeeded. Parsing CPU parameters from response."
        MAX_WORKER_PROCESSES=$(echo "$API_CONF" | grep "^max_worker_processes" | awk '{print $3}')
        MAX_PARALLEL_WORKERS=$(echo "$API_CONF" | grep "^max_parallel_workers " | awk '{print $3}')
    else
        log "API call failed or timed out. Using local fallback math for CPU parameters."
        MAX_WORKER_PROCESSES=$CPU_CORES
        MAX_PARALLEL_WORKERS=$CPU_CORES
    fi
    log "max_parallel_workers_per_gather fixed at ${MAX_PARALLEL_WORKERS_PER_GATHER} (USER CONFIGURATION)."

    # 6. Backup the Configuration
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_PATH="/u01/backup/logs/autotune/config_backup/postgresql.conf.backup.${TIMESTAMP}"
    cp "$PG_CONF" "$BACKUP_PATH"
    log "Backed up $PG_CONF to $BACKUP_PATH"

    # 7. Apply parameters
    log "Applying optimized configurations to postgresql.conf..."
    set_pg_param "shared_buffers"               "'${SHARED_BUFFERS_MB}MB'"
    set_pg_param "effective_cache_size"         "'${EFFECTIVE_CACHE_MB}MB'"
    set_pg_param "maintenance_work_mem"         "'${MAINT_WORK_MEM_MB}MB'"
    set_pg_param "work_mem"                     "'${WORK_MEM_MB}MB'"
    set_pg_param "wal_buffers"                  "'${WAL_BUFFERS_MB}MB'"
    set_pg_param "max_worker_processes"         "$MAX_WORKER_PROCESSES"
    set_pg_param "max_parallel_workers"         "$MAX_PARALLEL_WORKERS"
    set_pg_param "max_parallel_workers_per_gather" "$MAX_PARALLEL_WORKERS_PER_GATHER"
fi

# 8. OOM hardening + checks (EVERY start)
log "================================================================="
log "OOM HARDENING (every start)"
# Backup once per start before huge_pages may be changed
if [ "$HW_CHANGED" -eq 0 ]; then
    cp "$PG_CONF" "/u01/backup/logs/autotune/config_backup/postgresql.conf.backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null
fi
ensure_kernel_reserve
ensure_thp
ensure_huge_pages_on
check_overrides
tune_hugepages
check_oom_service
summary "PRE-START SUMMARY"

# 9. Update Self-Contained State
if [ "$HW_CHANGED" -eq 1 ]; then
    SCRIPT_PATH=$(readlink -f "$0")
    sed -i -E "s/^LAST_KNOWN_STATE=.*/LAST_KNOWN_STATE=\"$CURRENT_STATE\"/" "$SCRIPT_PATH"
    log "Process complete. State saved inside script."
fi

# 10. Post-start verification in the background (results appended to this log)
start_background_verify

# 11. Testing Gap (set TEST_SLEEP_SECONDS=0 in production)
if [ "$TEST_SLEEP_SECONDS" -gt 0 ]; then
    log "TESTING MODE: Sleeping for ${TEST_SLEEP_SECONDS} seconds to demonstrate ExecStartPre gap."
    log "You can check 'systemctl status postgresql-${PG_VERSION}' in another terminal now."
    log "The database engine will not start until this sleep finishes."
    sleep "$TEST_SLEEP_SECONDS"
    log "Sleep finished. Handing control back to systemd native auto-startup..."
fi

log "Handing control back to systemd."
exit 0
```

### 4.3 Script Permissions & SELinux Configuration
#### Theory: SELinux Policies on Custom Services
SELinux (Security-Enhanced Linux) enforces Mandatory Access Control. When systemd attempts to run a script located in custom mounts (like `/u01/`), SELinux blocks execution unless the script is assigned the standard system binary domain context (`bin_t`).

```bash
# Grant execution permissions
sudo chmod +x /u01/Gsl/pg_autotune_systemd.sh

# Apply SELinux binary execution labeling
sudo chcon -t bin_t /u01/Gsl/pg_autotune_systemd.sh

# Ensure the postgres user owns the entire /u01 directory tree
sudo chown -R postgres:postgres /u01
```


### 4.4 Hooking Script into PostgreSQL Systemd Unit
1. Edit the systemd service file for the PostgreSQL engine:
   ```bash
   sudo vi /usr/lib/systemd/system/postgresql-<version>.service
   ```
2. Locate the line beginning with `ExecStartPre=`.
3. Add the custom hook execution rule **directly above** the default directory check line:
   ```ini
   # Add this line (the '+' instructs systemd to execute it with root permissions):
   ExecStartPre=+/u01/Gsl/pg_autotune_systemd.sh
   
   # Just above:
   ExecStartPre=/usr/pgsql-<version>/bin/postgresql-<version>-check-db-dir ${PGDATA}
   ```
4. Reload the systemd daemon to pick up configuration changes:
   ```bash
   sudo systemctl daemon-reload
   ```

---

### 4.5 Zstd backup process preparation packages
1. Install gcc and make libraries via root user
```bash
dnf install -y gcc make
```
```bash
dnf install -y gcc make --disablerepo=pgdg12 --disablerepo=pgdg13
```
```bash
dnf install -y zstd
```

2. Move to /u01 directory and download zstd tar file
cd /u01

```bash
curl -LO https://github.com/facebook/zstd/releases/download/v1.5.6/zstd-1.5.6.tar.gz
curl -LO https://github.com/facebook/zstd/releases/download/v1.5.6/zstd-1.5.6.tar.gz.sha256
sha256sum -c zstd-1.5.6.tar.gz.sha256          # must print: OK
```

3. Extract compile and install the new zstd library
```bash
tar xzf zstd-1.5.6.tar.gz && cd zstd-1.5.6
make -C lib -j4 lib-mt                         # multithreaded shared library
make -C lib PREFIX=/opt/zstd install
```

4. verify the packages
```bash
ls -l /opt/zstd/lib/
ldd /opt/zstd/lib/libzstd.so.1 | grep pthread  # must show libpthread = MT build
```



## 5. Phase 3: Database Engine Parameter Tuning

### 5.1 Downloading & Installing Extension Packages (YUM/RPM)
> [!IMPORTANT]
> PostgreSQL configuration parameters like `shared_preload_libraries` require the corresponding extension library files to exist on the disk *before* changing the parameters. Changing these parameters without pre-installing the extensions will cause the PostgreSQL database engine to fail to start. Therefore, we download and install the required extensions first.

Run the following commands as the `root` user to fetch matching versions of extensions from the PGDG Yum repository:

```bash
# 1. Download extension packages (Ensure version matches PostgreSQL main engine)
wget https://ftp.postgresql.org/pub/repos/yum/<version>/redhat/rhel-8-x86_64/pgaudit_<version>-17.1-1PGDG.rhel8.x86_64.rpm
wget https://ftp.postgresql.org/pub/repos/yum/<version>/redhat/rhel-8-x86_64/pg_cron_<version>-1.6.7-1PGDG.rhel8.x86_64.rpm
wget https://download.postgresql.org/pub/repos/yum/<version>/redhat/rhel-8-x86_64/pg_stat_kcache_<version>-2.3.1-1PGDG.rhel8.x86_64.rpm

# 2. Local RPM package installation
sudo rpm -ivh pgaudit_<version>-17.1-1PGDG.rhel8.x86_64.rpm
sudo rpm -ivh pg_cron_<version>-1.6.7-1PGDG.rhel8.x86_64.rpm
sudo rpm -ivh pg_stat_kcache_<version>-2.3.1-1PGDG.rhel8.x86_64.rpm
```

#### Non-Standard Extension Setup (`pg_proctab`)
For the `pg_proctab` extension, there is no standard RPM package download. Instead, it must be compiled from source on a compatible build environment.
1. Refer to the [RHEL8_PG17_Extension_Compile_Guide.md](file:///d:/Github%20Development/dba-knowledge-base/dba-docs/docs/POSTGRESQL/PG%20EXTENSION%20BUILDER/RHEL8_PG17_Extension_Compile_Guide.md) runbook for instructions on compiling the extension.
2. Once compiled, copy the resulting files to the destination server and place them in the following paths (replace `<version>` with the actual PostgreSQL version e.g., `16` or `17`):
   - `/usr/pgsql-<version>/lib/pg_proctab.so`
   - `/usr/pgsql-<version>/share/extension/pg_proctab.control`
   - `/usr/pgsql-<version>/share/extension/pg_proctab--0.0.13.sql`
   - `/usr/pgsql-<version>/share/extension/pg_proctab--0.0.9--0.0.10.sql`
   - `/usr/pgsql-<version>/share/extension/pg_proctab--0.0.5--0.0.6.sql`
3. Grant `755` permissions to the copied `.so` library file:
   ```bash
   sudo chmod 755 /usr/pgsql-<version>/lib/pg_proctab.so
   ```
> [!NOTE]
> Alternatively, you can copy these pre-compiled extension files from an existing PostgreSQL 17 production server and place them in the exact same path locations in your newly deployed server. Make sure to apply the same `chmod 755` permission to the `.so` file.

### 5.2 Theory: Key Parameter Tuning in PostgreSQL
By default, PostgreSQL installation configurations are very conservative (designed for low-resource environments). For large, high-capacity databases, adjusting parameters optimizes CPU cycle distribution, memory usage, write traffic, and vacuum behavior:

- **Memory Settings (`work_mem`, `shared_buffers`):** Determines the maximum RAM allocated for internal sort operations, hash tables, and database caching.
- **Autovacuum Optimization:** In high-write environments, default values fail to keep up with dead tuple generation, leading to table bloat. Reducing scale factors triggers autovacuuming much faster.
- **Logical Replication (For Insightx Sync):** Configures logical replication parameters, allowing external consumers to stream data changes (CDC) from WAL logs.

#### Configuration Management Breakdown
The following table outlines the total parameters modified in this deployment and specifies whether they are handled dynamically by the auto-tune hook script or manually during deployment in `postgresql.conf`:

| Parameter                               | Managed By           | Description                                                |
|-----------------------------------------|----------------------|------------------------------------------------------------|
| `shared_buffers`                        | `pgautotune.sh`      | RAM allocated for database caching.                        |
| `effective_cache_size`                  | `pgautotune.sh`      | Planner hint for disk cache size.                          |
| `maintenance_work_mem`                  | `pgautotune.sh`      | Memory for indexes/maintenance (vacuum).                   |
| `work_mem`                              | `pgautotune.sh`      | Memory limit for sorting/joins.                            |
| `wal_buffers`                           | `pgautotune.sh`      | Memory allocation for WAL data.                            |
| `max_worker_processes`                  | `pgautotune.sh`      | Upper limit on concurrent background workers.              |
| `max_parallel_workers`                  | `pgautotune.sh`      | Limit on active parallel query workers.                    |
| `max_parallel_workers_per_gather`       | `pgautotune.sh`      | Parallel workers allowed per execution query.              |
| `track_io_timing`                       | Manual (Section 5.3) | Collect stats on read/write latency.                       |
| `compute_query_id`                     | Manual (Section 5.3) | Calculate query identifiers (required for pg_stat_statements).|
| `track_activity_query_size`             | Manual (Section 5.3) | Allocate larger buffer for SQL query logging.              |
| `temp_buffers`                          | Manual (Section 5.3) | Cache size allocated for temporary tables.                 |
| `effective_io_concurrency`              | Manual (Section 5.3) | Number of concurrent disk operations (for SSDs).           |
| `random_page_cost`                      | Manual (Section 5.3) | Relative index disk read cost estimate.                    |
| `seq_page_cost`                         | Manual (Section 5.3) | Relative sequential page access cost.                      |
| `autovacuum_max_workers`                | Manual (Section 5.3) | Max concurrent autovacuum processes.                       |
| `autovacuum_vacuum_scale_factor`        | Manual (Section 5.3) | Clean dead tuples after % rows change limit.               |
| `autovacuum_vacuum_insert_scale_factor` | Manual (Section 5.3) | Clean tables after % inserts limit.                        |
| `autovacuum_vacuum_cost_delay`          | Manual (Section 5.3) | Sleep time limit when vacuum reaches limit.                |
| `log_autovacuum_min_duration`           | Manual (Section 5.3) | Log autovacuum runs taking longer than limit.              |
| `max_prepared_transactions`             | Manual (Section 5.3) | Support for concurrent prepared/2PC transactions.          |
| `max_connections`                       | Manual (Section 5.3) | Concurrent connection capacity limit.                      |
| `shared_preload_libraries`              | Manual (Section 5.3) | Preload extension libraries.                               |
| `cron.database_name`                    | Manual (Section 5.3) | Target database for pg_cron extension.                     |
| `cron.timezone`                         | Manual (Section 5.3) | Timezone configured for pg_cron jobs.                      |
| `cron.max_running_jobs`                 | Manual (Section 5.3) | Maximum concurrent pg_cron jobs allowed.                   |
| `wal_level`                             | Manual (Section 5.3) | Enable CDC logical replication streams.                    |
| `max_replication_slots`                 | Manual (Section 5.3) | Concurrent replication stream connections limit.           |
| `max_wal_senders`                       | Manual (Section 5.3) | Senders running parallel logical transactions.             |
| `sync_replication_slots`                | Manual (Section 5.3) | Sync replication slot details across restarts.             |
| `min_wal_size` / `max_wal_size`         | Manual (Section 5.3) | Sizing limits for WAL segments.                            |
| `archive_mode`                          | Post-Migration       | Enable continuous WAL archiving for PITR.                  |
| `archive_command`                       | Post-Migration       | Shell command (`BLOB.sh`) to transfer WAL segments.        |
| `archive_timeout`                       | Post-Migration       | Force WAL rotation after timeout (120s).                   |
| `pg_stat_statements.track`             | Manual (Section 5.3 - Bottom of postgresql.conf) | Control which statements are tracked (top/all/none).       |
| `pg_stat_statements.track_planning`    | Manual (Section 5.3 - Bottom of postgresql.conf) | Enable tracking of query planning duration.                |
| `pg_stat_statements.max`               | Manual (Section 5.3 - Bottom of postgresql.conf) | Maximum number of statements tracked.                      |
| `pg_stat_statements.save`              | Manual (Section 5.3 - Bottom of postgresql.conf) | Save statement statistics across server restarts.          |
| `pg_stat_statements.track_utility`     | Manual (Section 5.3 - Bottom of postgresql.conf) | Track utility commands (like DDL) in statistics.           |

> **Note:** Point-in-Time Recovery (PITR) parameters (`archive_mode`, `archive_command`, and `archive_timeout`) are documented here for completeness, but they must be **manually enabled post-migration** to avoid heavy archiving operations during the initial bulk data migration.

### 5.3 Modifying parameters in `postgresql.conf`
Open the PostgreSQL configuration file:
```bash
sudo vi $PGDATA/postgresql.conf
```
Update or append the following values:

```ini
# --- Performance & Resource Configurations ---
track_io_timing = on                    # Collect stats on read/write latency
compute_query_id = on                   # Calculate query identifiers (required for pg_stat_statements)
track_activity_query_size = 102400       # Allocate larger buffer for SQL query logging
temp_buffers = '1GB'                    # Cache size allocated for temporary tables
effective_io_concurrency = 100          # Number of concurrent disk operations (for SSDs)
random_page_cost = 1.1                  # Relative index disk read cost estimate (1.1 for SSD)
seq_page_cost = 2.0                     # Relative sequential page access cost

# --- Autovacuum Tuning (Reduce Bloat) ---
autovacuum_max_workers = 6               # Max concurrent autovacuum processes
autovacuum_vacuum_scale_factor = 0.05    # Clean dead tuples after 5% of rows change (default 20%)
autovacuum_vacuum_insert_scale_factor = 0.05 # Clean tables after 5% of inserts
autovacuum_vacuum_cost_delay = 1         # Sleep time limit (ms) when vacuum reaches limit
log_autovacuum_min_duration = 60000     # Log autovacuum runs taking longer than 60s

# --- System-Wide Limits ---
max_prepared_transactions = 1750        # Support up to 1750 concurrent prepared/2PC transactions
max_connections = 5000                   # Concurrent connection capacity limit

# --- Extensions preloading ---
shared_preload_libraries = 'pg_cron,pgaudit,pg_stat_statements,pg_proctab,pg_stat_kcache'

# --- pg_cron Extension Settings ---
cron.database_name = 'postgres'
cron.timezone = 'Asia/Kolkata'
cron.max_running_jobs = 100

# --- Insightx / Replication Configurations ---
wal_level = replica                     # Enable CDC logical replication streams
max_replication_slots = 100             # Allow up to 100 concurrent replication stream connections
max_wal_senders = 100                   # Senders running parallel logical transactions
sync_replication_slots = true           # Sync replication slot details to prevent loss
min_wal_size = '1GB'
max_wal_size = '10GB'

# --- Point-in-Time Recovery (PITR) / Archiving ---
# NOTE: Enable these parameters MANUALLY POST-MIGRATION to avoid excessive wal accumulation and server storage exhaustion
# archive generation during initial bulk data loads.
 archive_mode = on
 archive_command = '/u01/Gsl/BLOB.sh %p %f'
 archive_timeout = 120

# --- pg_stat_statements Configurations ---
pg_stat_statements.track = top
pg_stat_statements.track_planning = on
pg_stat_statements.max = 5000
pg_stat_statements.save = on
pg_stat_statements.track_utility = on

# --- Disabling postgresql log activity during migration ---
#--- before migration ---
ALTER SYSTEM SET log_min_messages = 'fatal';
ALTER SYSTEM SET log_min_error_statement = 'panic';
SELECT pg_reload_conf();


# --- After migration ---
ALTER SYSTEM RESET log_min_messages;
ALTER SYSTEM RESET log_min_error_statement;
SELECT pg_reload_conf();

```

> [!NOTE]
> Add the `pg_stat_statements` configurations block shown above to the very bottom of your `postgresql.conf` configuration file.

Restart the PostgreSQL service to apply the values:
```bash
sudo systemctl restart postgresql-<version>
```

---

## 6. Phase 4: PostgreSQL Extensions Setup

### 6.1 Theoretical Overview of Selected Extensions
- **pg_cron:** A cron job scheduler that runs directly inside the database, enabling `VACUUM` scheduling or operational SQL tasks.
- **pg_stat_statements:** Tracks runtime statistics of all queries run on the database (essential for database performance diagnostics).
- **pgaudit:** Provides structured logging of select operations (DML/DDL) for security auditing.
- **pg_stat_kcache:** Gathers statistics about physical I/O and CPU usage of queries.

### 6.2 Creating Extensions inside Database
Log in to PostgreSQL using the `psql` console as a superuser:
```bash
psql -U postgres -d postgres
```
Run the following DDL statements to load the extensions:
```sql
-- Core extensions setup
CREATE EXTENSION DICT_INT;
CREATE EXTENSION DBLINK;
CREATE EXTENSION FUZZYSTRMATCH;
CREATE EXTENSION PG_BUFFERCACHE;
CREATE EXTENSION PG_CRON;
CREATE EXTENSION PG_STAT_STATEMENTS;
CREATE EXTENSION PGAUDIT;
CREATE EXTENSION PGCRYPTO;
CREATE EXTENSION PGSTATTUPLE;        
CREATE EXTENSION POSTGRES_FDW;
CREATE EXTENSION PG_STAT_KCACHE;
CREATE EXTENSION PG_PROCTAB;

alter role postgres with password 'postgres';
```

---

## 7. Phase 5: Backup & Business Continuity (BCP) Setup

### 7.1 Theory: Backup Architecture
The BCP setup is divided into:
1. **WAL Archiving:** Copying transaction logs (WALs) continuously to Azure Blob Storage using `azcopy`.
2. **Physical Backups (`pg_basebackup`):** Generating a full physical snapshot of the database cluster on a schedule, copying it to cloud storage, and verifying backups.
3. **Log & Agent Housekeeping:** System health validation scripts and automated retention cleanups.

### 7.2 Directory Configuration [login with postgres user]
Create the operational hierarchy:
```bash
mkdir -p /u01/Gsl/SQL
mkdir -p /u01/backup/logs/arc_sync
mkdir -p /u01/backup/logs/list_delete_selfhosted
mkdir -p /u01/backup/logs/long_query
mkdir -p /u01/backup/logs/AZCOPY_DEL
mkdir -p /u01/backup/logs/MONITOR_AGENT
mkdir -p /u01/backup/logs/pgmon
mkdir -p /u01/backup/logs/Disk_Usage
mkdir -p /u01/backup/logs/autotune
mkdir -p /u01/backup/logs/autotune/config_bakup
mkdir -p /u01/backup/logs/arc_list
mkdir -p /u01/backup/PG
mkdir -p /u01/backup/arc_tmp
```

---

### 7.3 BCP Script Deployment [login as postgres user]

Create all scripts under the `/u01/Gsl/` directory.

#### Script 0: Centealized Environment shell (`/u01/Gsl/gsl_env.sh`)
**Purpose:** Central inventory for managing all environment variables/paths from single place rather than seperately in every single shell.
```bash
vi /u01/Gsl/gsl_env.sh
```
```bash
# --- Azure Blob Storage ---
BASE_URL="https://storageerpdbbkpprodjiw.blob.core.windows.net/pgdbbackup"
VM_HOSTNAME="vm_hostname"
SAS_TOKEN="sp=racwdli&st=2026-08-21T08:24:52Z&se=2027-06-29T16:39:52Z&sv=2026-02-06&sr=c&sig=NtkshBDN8AFqAZCGz9pJs7hH7y%2FefDeB7cojgTSaBzg%3D"

# --- PostgreSQL ---
PG_VERSION="17"
PGUSER="postgres"
PGPASSWORD="postgres"
export PGUSER PGPASSWORD

# --- Alerting / SMTP ---
ALERT_TO="dbsrvalerts@gsl.in"
ALERT_FROM="dbsrvalerts@gsl.in"
SMTP_SERVER="smtp.gmail.com:587"
SMTP_APP_PASSWORD="oegmwnlfdtdpmvix"

# --- Shared paths ---
PG_BACKUP_DIR="/u01/backup/PG"
PG_LOG_BASE="/u01/backup/logs"
PGDATA_BASE="/u01/pgsql"
AZCOPY_BIN="/usr/bin/azcopy"
CMD_M=mailx

# --- WAL compression (used by BLOB.sh) ---
ZSTD_BIN="/usr/bin/zstd"
ARC_TMP_DIR="/u01/backup/arc_tmp"
export LD_LIBRARY_PATH="/opt/zstd/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# --- Backup housekeeping (used by DELBASEBKP.sh) ---
PG_BACKUP_DIRS="/u01/backup/PG /backup/PG"   # all locations; ones that don't exist on a VM are skipped
BKP_RETENTION_MIN=1440                        # delete backups older than 1 day
BKP_KEEP_MIN=1                                # always keep the newest real backup per location
```

```bash
chmod 777 /u01/Gsl/gsl_env.sh
```

#### Script 1: WAL Archiving (`/u01/Gsl/BLOB.sh`)
**Purpose:** Copy transaction log files (WAL) to Azure Blob Storage as they are filled or timeout.
```bash
vi /u01/Gsl/BLOB.sh
```
```bash
#!/bin/bash
# BLOB.sh - compress one WAL file with zstd and archive it to Azure Blob
# Called from archive_command:  /u01/Gsl/BLOB.sh "%p" "%f"
# All settings come from gsl_env.sh (same folder as this script):
#   BASE_URL, VM_HOSTNAME, SAS_TOKEN, AZCOPY_BIN, PG_LOG_BASE, ZSTD_BIN, ARC_TMP_DIR
source "$(dirname "$(readlink -f "$0")")/gsl_env.sh"

date_dir=$(date +%Y_%m_%d)
WAL_FILE_PATH=$1          # %p
WAL_FILE_NAME=$2          # %f
logdir="${PG_LOG_BASE}/arc_sync"
mkdir -p "$logdir"

log() { echo "$(date '+%F %T') $*" >> "${logdir}/blob_archive.log"; }

# Every required setting must be present in gsl_env.sh
for v in BASE_URL VM_HOSTNAME SAS_TOKEN AZCOPY_BIN PG_LOG_BASE ZSTD_BIN ARC_TMP_DIR; do
    if [ -z "${!v}" ]; then log "ERROR $v is not set in gsl_env.sh"; exit 1; fi
done
if [ -z "$WAL_FILE_PATH" ] || [ -z "$WAL_FILE_NAME" ]; then
    log "ERROR missing arguments (expected %p %f)"; exit 1
fi

tmpfile="${ARC_TMP_DIR}/${WAL_FILE_NAME}.zst"
mkdir -p "$ARC_TMP_DIR"

# 1. Compress (level 3, single thread; -f replaces a leftover from a failed attempt)
if ! "$ZSTD_BIN" -q -3 -f "$WAL_FILE_PATH" -o "$tmpfile"; then
    log "ERROR zstd failed: $WAL_FILE_NAME"; rm -f "$tmpfile"; exit 1
fi

# 2. Verify the compressed file before upload
if ! "$ZSTD_BIN" -q -t "$tmpfile"; then
    log "ERROR zstd test failed: $WAL_FILE_NAME"; rm -f "$tmpfile"; exit 1
fi

# 3. Upload with .zst extension
BLOB_STORAGE_URL="${BASE_URL}/self-hosted/${VM_HOSTNAME}/archive/${date_dir}/${WAL_FILE_NAME}.zst?${SAS_TOKEN}"
if ! "$AZCOPY_BIN" copy "$tmpfile" "$BLOB_STORAGE_URL" --log-level ERROR --overwrite=true \
        >> "${logdir}/blob_archive.log" 2>&1; then
    log "ERROR upload failed: $WAL_FILE_NAME"; rm -f "$tmpfile"; exit 1
fi

rm -f "$tmpfile"
exit 0
```
```bash
chmod 777 /u01/Gsl/BLOB.sh
```

#### Script 2: Base Physical Backup (`/u01/Gsl/BASEBKP.sh`)
**Purpose:** Create a physical backup snapshot, sync files to Azure container, and send success/fail alert email.
```bash
vi /u01/Gsl/BASEBKP.sh
```
```bash
#!/bin/bash
# BASEBKP.sh - Database physical base backup
source /u01/Gsl/gsl_env.sh
export LD_LIBRARY_PATH=/opt/zstd/lib

yy=$(date +%Y)
mm=$(date +%m)
dd=$(date +%d)
MYDATE="${yy}_${mm}_${dd}"
MYTIME="$(date +%H%M%S)"
DD=$(date +%d%m%y)

PG_BASEBACKUP_LOG="$PG_LOG_BASE"
Azure_Log="$PG_BASEBACKUP_LOG/GINESYS_backuplog.log"
POSTGRESQL_BIN="/usr/pgsql-${PG_VERSION}/bin"

mkdir -p "$PG_BASEBACKUP_LOG"

start_time=$(date +%s)
start_time_human=$(date '+%Y-%m-%d %H:%M:%S')

echo "Starting Pg_basebackup at $start_time_human" >> "$PG_BASEBACKUP_LOG/pg_basebackup_${MYDATE}_${MYTIME}.log"
echo "Running pg_basebackup command..." >> "$PG_BASEBACKUP_LOG/pg_basebackup_${MYDATE}_${MYTIME}.log"

$POSTGRESQL_BIN/pg_basebackup -D "${PG_BACKUP_DIR}/$MYDATE" -Ft -Z server-zstd:9 -P -Xs >> "$PG_BASEBACKUP_LOG/pg_basebackup_${MYDATE}_${MYTIME}.log" 2>&1

end_time=$(date +%s)
end_time_human=$(date '+%Y-%m-%d %H:%M:%S')
elapsed_time=$((end_time - start_time))
elapsed_time_human=$(date -ud @${elapsed_time} +'%H:%M:%S')

echo "Ending Pg_basebackup at $end_time_human" >> "$PG_BASEBACKUP_LOG/pg_basebackup_${MYDATE}_${MYTIME}.log"
echo "Elapsed time: $elapsed_time_human" >> "$PG_BASEBACKUP_LOG/pg_basebackup_${MYDATE}_${MYTIME}.log"

echo "---------------------------------" >> "$Azure_Log"
echo "Syncing files to Azure storage" >> "$Azure_Log"
echo "---------------------------------" >> "$Azure_Log"

sourcePath="$PG_BACKUP_DIR"
destinationUrl="${BASE_URL}/self-hosted/${VM_HOSTNAME}/fullbackup/?${SAS_TOKEN}"

$AZCOPY_BIN sync "$sourcePath" "$destinationUrl" --put-md5 --delete-destination=false >> "$Azure_Log" 2>&1

echo "${VM_HOSTNAME} STANDALONE: PG BASE BACKUP" | $CMD_M -a $PG_BASEBACKUP_LOG/pg_basebackup_${MYDATE}_${MYTIME}.log -v -r "$ALERT_FROM" -s "${VM_HOSTNAME} STANDALONE: PG BASEBACKUP INFORMATION ${DD}" -S smtp="$SMTP_SERVER" -S smtp-use-starttls -S smtp-auth=login -S smtp-auth-user="$ALERT_FROM" -S smtp-auth-password="$SMTP_APP_PASSWORD" -S ssl-verify=ignore $ALERT_TO
```
```bash
chmod 777 /u01/Gsl/BASEBKP.sh
```

#### Script 3: Old Backup Deletion (`/u01/Gsl/DELBASEBKP.sh`)
**Purpose:** Delete local backups older than 24 hours (1440 mins) to prevent disk space exhaustion.
```bash
vi /u01/Gsl/DELBASEBKP.sh
```
```bash
#!/bin/bash
# DELBASEBKP.sh - Housekeeping: delete old pg_basebackup folders
#
# Settings from gsl_env.sh:
#   PG_BACKUP_DIRS   space-separated backup locations, e.g. "/u01/backup/PG /backup/PG"
#                    (falls back to PG_BACKUP_DIR if PG_BACKUP_DIRS is not set)
#   BKP_RETENTION_MIN  delete backups older than this many minutes (default 1440 = 1 day)
#   BKP_KEEP_MIN       always keep at least this many newest backups per location (default 1)
#   PG_LOG_BASE, VM_HOSTNAME, ALERT_*, SMTP_*, CMD_M
source "$(dirname "$(readlink -f "$0")")/gsl_env.sh"

BKP_DIRS="${PG_BACKUP_DIRS:-$PG_BACKUP_DIR}"
RETENTION_MIN="${BKP_RETENTION_MIN:-1440}"
KEEP_MIN="${BKP_KEEP_MIN:-1}"

DD=$(date +%d%m%y)
LOG_DIR="${PG_LOG_BASE}/list_delete_selfhosted"
LOG_FILE="${LOG_DIR}/list_delete_selfhosted_$(date +%Y-%m-%d_%H_%M).log"
mkdir -p "$LOG_DIR" || { echo "Error: cannot create $LOG_DIR"; exit 1; }

STATUS="SUCCESS"
DELETED=0

{
echo "Host            : ${VM_HOSTNAME}"
echo "Run time        : $(date '+%Y-%m-%d %H:%M:%S')"
echo "Backup locations: ${BKP_DIRS:-<none>}"
echo "Retention       : older than ${RETENTION_MIN} min, keep at least ${KEEP_MIN} newest per location"
echo ""
} > "$LOG_FILE"

if [ -z "$BKP_DIRS" ]; then
    echo "ERROR: PG_BACKUP_DIRS / PG_BACKUP_DIR not set in gsl_env.sh - nothing done." >> "$LOG_FILE"
    STATUS="FAILED"
fi

for dir in $BKP_DIRS; do
    dir="${dir%/}"
    echo "=================================================================" >> "$LOG_FILE"
    echo "LOCATION: $dir" >> "$LOG_FILE"

    # Safety: never run on an empty, root or non-absolute path
    case "$dir" in
        ""|"/"|[!/]*) echo "SKIPPED: unsafe path '$dir'" >> "$LOG_FILE"; STATUS="FAILED"; continue ;;
    esac
    if [ ! -d "$dir" ]; then
        echo "SKIPPED: directory does not exist on this VM" >> "$LOG_FILE"
        continue
    fi

    echo "" >> "$LOG_FILE"
    echo "Size before deletion:" >> "$LOG_FILE"
    df -h "$dir" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    # Top-level entries only (each backup = one dated folder), newest first
    mapfile -t entries < <(find "$dir" -mindepth 1 -maxdepth 1 -printf '%T@ %p\n' | sort -rn | cut -d' ' -f2-)
    total=${#entries[@]}
    echo "Backups found: $total" >> "$LOG_FILE"

    echo "THE LIST OF THE BACKUP FILES THAT ARE DELETED" >> "$LOG_FILE"
    echo "*********************************************" >> "$LOG_FILE"
    n=0; here=0
    for path in "${entries[@]}"; do
        # Only non-empty backups count as "kept" (an empty folder = failed backup, not a safe copy)
        if [ -d "$path" ] && [ -z "$(find "$path" -type f -size +0 -print -quit)" ]; then
            nonempty=0
        elif [ -f "$path" ] && [ ! -s "$path" ]; then
            nonempty=0
        else
            nonempty=1
        fi
        if [ "$nonempty" -eq 1 ]; then
            n=$((n + 1))
            [ "$n" -le "$KEEP_MIN" ] && continue                   # always keep the newest real backups
        fi
        # older than retention?
        if [ -n "$(find "$path" -maxdepth 0 -mmin +"$RETENTION_MIN")" ]; then
            size=$(du -sh "$path" 2>/dev/null | cut -f1)
            if rm -rf -- "$path"; then
                echo "DELETED  $path  ($size)" >> "$LOG_FILE"
                here=$((here + 1))
            else
                echo "FAILED   $path" >> "$LOG_FILE"
                STATUS="FAILED"
            fi
        fi
    done
    [ "$here" -eq 0 ] && echo "(nothing older than retention)" >> "$LOG_FILE"
    DELETED=$((DELETED + here))

    echo "" >> "$LOG_FILE"
    echo "Size after deletion:" >> "$LOG_FILE"
    df -h "$dir" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
done

echo "=================================================================" >> "$LOG_FILE"
echo "RESULT: ${STATUS}, ${DELETED} backup(s) deleted" >> "$LOG_FILE"

SUBJECT="${VM_HOSTNAME} STANDALONE: OLD PG BASEBACKUP DELETION ${STATUS} ${DD}"
echo "${VM_HOSTNAME} STANDALONE: OLD PG BASE BACKUP DELETION - ${STATUS}, ${DELETED} deleted" | \
    $CMD_M -a "$LOG_FILE" -v -r "$ALERT_FROM" -s "$SUBJECT" \
        -S smtp="$SMTP_SERVER" -S smtp-use-starttls -S smtp-auth=login \
        -S smtp-auth-user="$ALERT_FROM" -S smtp-auth-password="$SMTP_APP_PASSWORD" \
        -S ssl-verify=ignore "$ALERT_TO" > /dev/null 2>&1

echo "${STATUS}: ${DELETED} backup(s) deleted. Log: $LOG_FILE"
[ "$STATUS" = "SUCCESS" ] && exit 0 || exit 1
```
```bash
chmod 777 /u01/Gsl/DELBASEBKP.sh
```

#### Script 4: Remote Archive Verification (`/u01/Gsl/ARCNAME.sh`)
**Purpose:** Verify files stored in Azure against internal Postgres database state using `pg_split_walfile_name`.
```bash
vi /u01/Gsl/ARCNAME.sh
```
```bash
#!/bin/bash
# ARCNAME.sh - Compare remote storage logs with database segment logs
# Lists today's archived WAL files in Azure Blob, records each new one with its
# pg_split_walfile_name() output, then uploads the log next to the WAL files.
source "$(dirname "$(readlink -f "$0")")/gsl_env.sh"

date_dir=$(date +%Y_%m_%d)
log_dir="${PG_LOG_BASE}/arc_list"
log_file="${log_dir}/arcname_${date_dir}.log"
mkdir -p "$log_dir"
touch "$log_file"                     # first run of the day: grep needs the file to exist

AZ_LIST_URL="${BASE_URL}/self-hosted/${VM_HOSTNAME}/archive/${date_dir}/?${SAS_TOKEN}"

# Names only; works with and without the "INFO: " prefix of older AzCopy versions
files=$("$AZCOPY_BIN" list "$AZ_LIST_URL" 2>/dev/null | sed 's/^INFO: //' | cut -d';' -f1 | sed 's/[[:space:]]*$//')

while IFS= read -r file; do
    [[ -z "$file" ]] && continue

    # Only WAL segments: 24 hex chars, optionally .zst (skips arcname_*.log, .history, .backup, .partial)
    [[ "$file" =~ ^[0-9A-F]{24}(\.zst)?$ ]] || continue

    # Already recorded? (exact name match, not a substring)
    grep -qF -- "] ${file} ||" "$log_file" && continue

    wal_name="${file%.zst}"          # pg_split_walfile_name() needs the bare WAL name
    output=$(psql -X -A -t -U "${PGUSER:-postgres}" -d postgres \
                  -c "SELECT pg_split_walfile_name('${wal_name}');" 2>&1)

    file_creation_time_utc=$(TZ='UTC' date '+%Y-%m-%d %H:%M:%S')
    file_creation_time_ist=$(TZ='Asia/Kolkata' date '+%Y-%m-%d %H:%M:%S')

    echo "[$file_creation_time_utc UTC | $file_creation_time_ist IST] ${file} || ${output}" >> "$log_file"
done <<< "$files"

AZ_COPY_URL="${BASE_URL}/self-hosted/${VM_HOSTNAME}/archive/${date_dir}/?${SAS_TOKEN}"
"$AZCOPY_BIN" copy "$log_file" "$AZ_COPY_URL" --overwrite=true --log-level=ERROR --output-level=essential
```
```bash
chmod 777 /u01/Gsl/ARCNAME.sh
```

#### Script 5: Long Query & System Performance Analysis (`/u01/Gsl/LONG_QUERY.sh`)
**Purpose:** Record daily active SQL operations, OS load averages, and disk metrics, and email details to the admin team.
```bash
vi /u01/Gsl/LONG_QUERY.sh
```
```bash
#!/bin/bash
# LONG_QUERY.sh - System diagnostics and active SQL monitor
source /u01/Gsl/gsl_env.sh

yy=$(date +%Y)
mm=$(date +%m)
dd=$(date +%d)
MYDATE="${yy}_${mm}_${dd}"
MYTIME="$(date +%H%M%S)"
LOGFILE="${PG_LOG_BASE}/long_query/Long_Query_${MYDATE}_${MYTIME}.log"
DD=$(date +%d%m%y)

echo "PRODUCTION SERVER DISK SPACE START
***********************************************************************************************************************" >> ${LOGFILE}
df -h >> $LOGFILE
echo "PRODUCTION SERVER DISK SPACE END
***********************************************************************************************************************" >> ${LOGFILE}

echo "SYSTEM TOP LOAD PROCESSES
***********************************************************************************************************************" >> ${LOGFILE}
top -b -n 1 | head -n 20 >> $LOGFILE

psql -h localhost -U postgres -d postgres -f /u01/Gsl/SQL/daily_query.sql >> "$LOGFILE" 2>&1

echo "${VM_HOSTNAME} STANDALONE: PG LONG QUERY INFO" | $CMD_M -a $LOGFILE -v -r "$ALERT_FROM" -s "${VM_HOSTNAME} STANDALONE: PG LONG QUERY INFORMATION ${DD}" -S smtp="$SMTP_SERVER" -S smtp-use-starttls -S smtp-auth=login -S smtp-auth-user="$ALERT_FROM" -S smtp-auth-password="$SMTP_APP_PASSWORD" -S ssl-verify=ignore $ALERT_TO

exit 0
```
*(Ensure that `/u01/Gsl/SQL/daily_query.sql` exists and contains performance checking SQL statements).*
```bash
chmod 777 /u01/Gsl/LONG_QUERY.sh
```

#### Script 6: AzCopy Execution Logs Purge (`/u01/Gsl/DEL_AZCOPY_LOG.sh`)
**Purpose:** Remove historical log output created by `azcopy` runs older than 1 day to prevent file index exhaustion inside `/var/lib/pgsql/.azcopy/`.
```bash
vi /u01/Gsl/DEL_AZCOPY_LOG.sh
```
```bash
#!/bin/bash
# DEL_AZCOPY_LOG.sh - Clean up AzCopy run directory logs

export LOG_DIR=/u01/backup/logs/AZCOPY_DEL
export LOG_FILE=$LOG_DIR/list_delete_azcopy_logs_$(date +%Y-%m-%d_%H_%M).log

SEARCH_DIR="/var/lib/pgsql/.azcopy/"

echo "/.azcopy size before deletion" > ${LOG_FILE}
du -sh $SEARCH_DIR >> ${LOG_FILE}

find $SEARCH_DIR -type f -mtime +1 -exec rm -f {} \; -exec echo "Removed file: {}" >> $LOG_FILE \;

echo "/.azcopy size after deletion" >> ${LOG_FILE}
du -sh $SEARCH_DIR >> ${LOG_FILE}

echo "File listing completed and saved to $LOG_FILE"
```
```bash
chmod 777 /u01/Gsl/DEL_AZCOPY_LOG.sh
```

#### Script 7: Azure Monitor Agent Log Purge (`/u01/Gsl/DEL_MONITOR_AGENT.sh`)
**Purpose:** Purge event metrics (.sst) generated by Azure Monitor Agent older than 14 days.
```bash
vi /u01/Gsl/DEL_MONITOR_AGENT.sh
```
```bash
#!/bin/bash
# DEL_MONITOR_AGENT.sh - Clean old SST telemetry files

LOG_DIR="/u01/backup/logs/MONITOR_AGENT"
mkdir -p $LOG_DIR
LOG_FILE=$LOG_DIR/list_delete_sst_logs_$(date +%Y-%m-%d_%H_%M).log
SEARCH_DIR="/var/opt/microsoft/azuremonitoragent/events"

{
echo "===================================================="
echo " SST CLEANUP SCRIPT LOG - $(date)"
echo "===================================================="
echo "[1] $SEARCH_DIR size BEFORE deletion:"
du -sh "$SEARCH_DIR"
echo ""
echo "[2] Files to be deleted (older than 14 days):"
find "$SEARCH_DIR" -type f -name "*.sst" -mtime +14 -path "*/c*/*" -ls
} >> "$LOG_FILE"

find "$SEARCH_DIR" -type f -name "*.sst" -mtime +14 -path "*/c*/*" -exec rm -f {} \; >> "$LOG_FILE" 2>&1

{
echo "[3] $SEARCH_DIR size AFTER deletion:"
du -sh "$SEARCH_DIR"
echo ""
echo "Cleanup completed at $(date)"
echo "===================================================="
} >> "$LOG_FILE"
```
```bash
sudo chmod +x /u01/Gsl/DEL_MONITOR_AGENT.sh
```

#### Script 8: Statements Monitoring Collection (`/u01/Gsl/collect_stmts.sh`)
**Purpose:** Collect statement snapshot metrics using `pg_stat_statements` and `pg_stat_kcache` and load them into database.
```bash
vi /u01/Gsl/collect_stmts.sh
```
```bash
#!/bin/bash

PSQL="psql -h localhost -U postgres -v ON_ERROR_STOP=1"

$PSQL <<'SQL'
INSERT INTO monitoring.stmt_snapshots (
    dbname, query_id, query_text, calls, total_exec_time, mean_exec_time,
    rows, shared_blks_hit, shared_blks_read, temp_blks_written, wal_bytes,
    blk_read_time, blk_write_time, cpu_ms_est,
    cpu_user_ms, cpu_sys_ms, cpu_total_ms,
    phys_read_bytes, phys_write_bytes, exec_minflts, exec_majflts
)
SELECT
    d.datname,
    s.queryid,
    s.query,
    s.calls,
    s.total_exec_time,
    s.mean_exec_time,
    s.rows,
    s.shared_blks_hit,
    s.shared_blks_read,
    s.temp_blks_written,
    s.wal_bytes,
    s.blk_read_time,
    s.blk_write_time,
    s.total_exec_time - s.blk_read_time - s.blk_write_time,
    k.exec_user_time*1000,
    k.exec_system_time*1000,
    (k.exec_user_time+k.exec_system_time)*1000,
    k.exec_reads,
    k.exec_writes,
    k.exec_minflts,
    k.exec_majflts
FROM pg_stat_statements s
JOIN pg_database d
ON d.oid=s.dbid
LEFT JOIN pg_stat_kcache() k
ON k.queryid=s.queryid
AND k.dbid=s.dbid
AND k.userid=s.userid
AND k.top IS TRUE
WHERE s.calls>0;
SQL
```
```bash
chmod 777 /u01/Gsl/collect_stmts.sh
```

#### Script 9: Session & Process Monitoring Collection (`/u01/Gsl/collect_sessions.sh`)
**Purpose:** Collect active sessions, process resource details, and lock statuses.
```bash
vi /u01/Gsl/collect_sessions.sh
```
```bash
#!/bin/bash

PSQL="psql -h localhost -U postgres -v ON_ERROR_STOP=1"

$PSQL <<'SQL'

INSERT INTO monitoring.session_snapshots
(pid,dbname,application_name,state,wait_event_type,wait_event,
query_start,duration_secs,query_id)
SELECT
pid,
datname,
application_name,
state,
wait_event_type,
wait_event,
query_start,
EXTRACT(EPOCH FROM (NOW()-query_start)),
query_id
FROM pg_stat_activity
WHERE state='active'
AND pid<>pg_backend_pid();

INSERT INTO monitoring.process_snapshots
(application_name,dbname,pid,comm,fullcomm,state,ppid,pgrp,
session,tty_nr,tpgid,flags,minflt,cminflt,majflt,cmajflt,
utime,stime,cutime,cstime,priority,nice,num_threads,
itrealvalue,starttime,vsize,rss,exit_signal,processor,
rt_priority,policy,delayacct_blkio_ticks,uid,username,
rchar,wchar,syscr,syscw,reads,writes,cwrites)
SELECT
COALESCE(NULLIF(sa.application_name,''),
CASE WHEN sa.pid IS NULL THEN pt.fullcomm ELSE 'unknown' END),
sa.datname,
pt.*
FROM pg_proctab() pt
LEFT JOIN pg_stat_activity sa
ON sa.pid=pt.pid
WHERE pt.username='postgres';

INSERT INTO monitoring.lock_snapshots
(waiting_pid,waiting_app,blocking_pid,blocking_app,
lock_type,relation,wait_secs)
SELECT
w.pid,
w.application_name,
b.pid,
b.application_name,
lw.locktype,
c.relname,
EXTRACT(EPOCH FROM (NOW()-w.query_start))
FROM pg_stat_activity w
JOIN pg_locks lw
ON lw.pid=w.pid
AND NOT lw.granted
JOIN pg_locks lb
ON lb.locktype=lw.locktype
AND lb.granted
AND lb.relation IS NOT DISTINCT FROM lw.relation
JOIN pg_stat_activity b
ON b.pid=lb.pid
LEFT JOIN pg_class c
ON c.oid=lw.relation
WHERE w.wait_event_type='Lock';

SQL
```
```bash
chmod 777 /u01/Gsl/collect_sessions.sh
```

#### Script 10: Database-Level Stats Collection (`/u01/Gsl/collect_db.sh`)
**Purpose:** Collect database transaction commits, rollbacks, and block hits/reads metrics.
```bash
vi /u01/Gsl/collect_db.sh
```
```bash
#!/bin/bash

PSQL="psql -h localhost -U postgres -v ON_ERROR_STOP=1"

$PSQL <<'SQL'
INSERT INTO monitoring.db_snapshots
(dbname,numbackends,xact_commit,xact_rollback,
blks_hit,blks_read,tup_returned,tup_fetched)

SELECT
datname,
numbackends,
xact_commit,
xact_rollback,
blks_hit,
blks_read,
tup_returned,
tup_fetched
FROM pg_stat_database
WHERE datname NOT IN ('template0','template1');
SQL
```
```bash
chmod 777 /u01/Gsl/collect_db.sh
```

#### Script 11: Monitoring Logs Purge (`/u01/Gsl/purge_monitoring.sh`)
**Purpose:** Purge snapshots data older than 2 days and clean tables to reclaim space.
```bash
vi /u01/Gsl/purge_monitoring.sh
```
```bash
#!/bin/bash

PSQL="psql -h localhost -U postgres -v ON_ERROR_STOP=1"

$PSQL <<'SQL'

DELETE FROM monitoring.stmt_snapshots
WHERE captured_at < NOW() - INTERVAL '2 days';

DELETE FROM monitoring.session_snapshots
WHERE captured_at < NOW() - INTERVAL '2 days';

DELETE FROM monitoring.process_snapshots
WHERE captured_at < NOW() - INTERVAL '2 days';

DELETE FROM monitoring.lock_snapshots
WHERE captured_at < NOW() - INTERVAL '2 days';

DELETE FROM monitoring.db_snapshots
WHERE captured_at < NOW() - INTERVAL '2 days';

VACUUM FULL monitoring.stmt_snapshots;
VACUUM FULL monitoring.session_snapshots;
VACUUM FULL monitoring.process_snapshots;
VACUUM FULL monitoring.lock_snapshots;
VACUUM FULL monitoring.db_snapshots;

SQL
```
```bash
chmod 777 /u01/Gsl/purge_monitoring.sh
```

#### Script 12: Disk & System Resource Usage Monitor (`/u01/Gsl/Disk_usage.sh`)
**Purpose:** Collect OS filesystem usage details, PostgreSQL directory sizes, and top system processes, and email details to the admin team.
```bash
vi /u01/Gsl/Disk_usage.sh
```
```bash
#!/bin/bash
# Disk_usage.sh - Disk and PostgreSQL directory usage report
source /u01/Gsl/gsl_env.sh

yy=$(date +%Y)
mm=$(date +%m)
dd=$(date +%d)
MYDATE="${yy}_${mm}_${dd}"

CUR_HH=$(date +%H)
CUR_NN=$(date +%M)
CUR_SS=$(date +%S)
MYTIME="${CUR_HH}${CUR_NN}${CUR_SS}"

LOGDIR="${PG_LOG_BASE}/Disk_Usage"
mkdir -p "$LOGDIR"
LOGFILE="${LOGDIR}/Disk_Usage_${MYDATE}_${MYTIME}.log"

SUBJECT="Disk Usage Report - ${MYDATE} ${MYTIME}"
DD=$(date +%d%m%y)

PGDATA="${PGDATA_BASE}/${PG_VERSION}/data"
PGWAL="${PGDATA}/pg_wal"
PGTMP="${PGDATA}/base/pgsql_tmp"
PGBACKUP="$PG_BACKUP_DIR"

{
    echo "===================================="
    echo "Disk Usage Report - $(date)"
    echo "===================================="
    echo ""

    echo ">>> Filesystem Usage for /u01 and /var:"
    echo ""
    df -h | egrep "Mounted|/u01|/var"
    echo ""
    echo "===================================="
    echo ">>> PostgreSQL Data Directory Sizes:"
    echo ""

    if [ -d "$PGDATA" ]; then
        echo "--- PostgreSQL Data Directory Size ---"
        du -sh "$PGDATA"
    else
        echo "❌ Directory not found: $PGDATA"
    fi

    echo ""

    if [ -d "$PGWAL" ]; then
        echo "--- PostgreSQL pg_wal Size ---"
        du -sh "$PGWAL"
    else
        echo "❌ Directory not found: $PGWAL"
    fi

    echo ""

    if [ -d "$PGTMP" ]; then
        echo "--- PostgreSQL Temp Size ---"
        du -sh "$PGTMP"
    else
        echo "❌ Directory not found: $PGTMP"
    fi

    echo ""
    echo "===================================="
    echo ">>> PostgreSQL Backup Directory Sizes:"
    echo ""

    if [ -d "$PGBACKUP" ]; then
        du -sh "$PGBACKUP"
        echo ""
        echo "Detailed backup folders:"
        du -sh "$PGBACKUP"/* 2>/dev/null | sort -hr
    else
        echo "❌ Directory not found: $PGBACKUP"
    fi

    echo ""
    echo "===================================="
    echo ">>> Top Process Snapshot:"
    echo ""

    top -b -n 1 -c

    echo ""
    echo "===================================="
    echo ""
    echo "===================================="
} > "$LOGFILE"

echo "✅ Disk usage report generated at: $LOGFILE"

echo "${VM_HOSTNAME} STANDALONE: PG Disk Usage INFO" | $CMD_M -a $LOGFILE -v -r "$ALERT_FROM" -s "${VM_HOSTNAME} STANDALONE: PG Disk Usage INFORMATION ${DD}" -S smtp="$SMTP_SERVER" -S smtp-use-starttls -S smtp-auth=login -S smtp-auth-user="$ALERT_FROM" -S smtp-auth-password="$SMTP_APP_PASSWORD" -S ssl-verify=ignore $ALERT_TO

exit 0
```
```bash
chmod 777 /u01/Gsl/Disk_usage.sh
```


### 7.4 Database Load Monitoring Tables Setup
To store metrics gathered by the load monitoring scripts, set up the monitoring schema and tracking tables in the destination database.
1. Log in with the `postgres` user to the `postgres` database:
   ```bash
   psql -U postgres -d postgres
   ```
2. Execute the following SQL DDL statements:
   ```sql
   CREATE SCHEMA IF NOT EXISTS monitoring;

   CREATE TABLE IF NOT EXISTS monitoring.stmt_snapshots (
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

   CREATE INDEX IF NOT EXISTS idx_stmt_snap_captured_at ON monitoring.stmt_snapshots (captured_at);
   CREATE INDEX IF NOT EXISTS idx_stmt_snap_query_id ON monitoring.stmt_snapshots (query_id);

   CREATE TABLE IF NOT EXISTS monitoring.session_snapshots (
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

   CREATE INDEX IF NOT EXISTS idx_session_snap_captured_at ON monitoring.session_snapshots (captured_at);
   CREATE INDEX IF NOT EXISTS idx_session_snap_query_id ON monitoring.session_snapshots (query_id);

   CREATE TABLE IF NOT EXISTS monitoring.process_snapshots (
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

   CREATE INDEX IF NOT EXISTS idx_process_snap_captured_app ON monitoring.process_snapshots (captured_at, application_name);
   CREATE INDEX IF NOT EXISTS idx_process_snap_pid ON monitoring.process_snapshots (pid);

   CREATE TABLE IF NOT EXISTS monitoring.lock_snapshots (
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

   CREATE INDEX IF NOT EXISTS idx_lock_snap_captured_at ON monitoring.lock_snapshots (captured_at);

   CREATE TABLE IF NOT EXISTS monitoring.db_snapshots (
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

   CREATE INDEX IF NOT EXISTS idx_db_snap_captured_dbname ON monitoring.db_snapshots (captured_at, dbname);
   ```

---

## 8. Phase 6: Automated Operations Setup (Cron Jobs)

We configure the cron scheduler to trigger our scripts.

### 8.1 Postgres User Crontab Setup
Open the postgres user crontab editor:
```bash
sudo -u postgres crontab -e
```
Insert the following schedule entries (uncomment when deployment goes active):
```cron
# Trigger database backup every day at 00:05 (12:05 AM)
05 00 * * * sh /u01/Gsl/BASEBKP.sh

# Run local backup housekeeping cleanups at 00:01 (12:01 AM)
01 00 * * * sh /u01/Gsl/DELBASEBKP.sh

# Run active long query diagnostics execution every 30 minutes
*/30 * * * * sh /u01/Gsl/LONG_QUERY.sh

# Run verification of remote archived files against postgres database state every minute
*/1 * * * * sh /u01/Gsl/ARCNAME.sh >/dev/null 2>&1

# Purge old AzCopy logs every night at 23:00 (11:00 PM)
00 23 * * * sh /u01/Gsl/DEL_AZCOPY_LOG.sh

# Track storage and disk spaces every 30 minutes
*/30 * * * * sh /u01/Gsl/Disk_usage.sh

# --- Load Analysis Monitoring Setup ---
# Collect statements statistics every minute
*/1 * * * * /u01/Gsl/collect_stmts.sh >> /u01/backup/logs/pgmon/stmts.log 2>&1

# Collect session details every minute (run at 0s and 30s offsets)
* * * * * /u01/Gsl/collect_sessions.sh >> /u01/backup/logs/pgmon/sessions.log 2>&1
* * * * * sleep 30; /u01/Gsl/collect_sessions.sh >> /u01/backup/logs/pgmon/sessions.log 2>&1

# Collect database-level stats every minute
* * * * * /u01/Gsl/collect_db.sh >> /u01/backup/logs/pgmon/db.log 2>&1

# Purge old monitoring log files daily at 18:33 (6:33 PM)
33 18 * * * /u01/Gsl/purge_monitoring.sh >> /u01/backup/logs/pgmon/purge.log 2>&1
```

### 8.2 Root User Crontab Setup
Open the root user crontab editor:
```bash
sudo crontab -e
```
Insert the following scheduling policy:
```cron
# Clean Azure Monitor Agent events folder every evening at 20:05 (8:05 PM)
05 20 * * * sh /u01/Gsl/DEL_MONITOR_AGENT.sh
```

---

## 9. Phase 7: Exporter & Monitoring Service Verification

Since monitoring agents are pre-installed via the initial VM template, this phase verifies that the necessary telemetry services are active and running correctly before handing over to operations.

### 9.1 Verify Node Exporter
Ensure the Node Exporter service (for OS-level metrics) is active and listening:
```bash
sudo systemctl status node_exporter
# Output should show "active (running)"
```

### 9.2 Verify PostgreSQL Exporter
1. Ensure the PostgreSQL Exporter service (for database-level metrics) is active:
   ```bash
   sudo systemctl status postgres_exporter
   # Output should show "active (running)"
   ```

2. Check if the `postgres_exporter` database user exists in the database.
   Log in to the `postgres` database using the `postgres` user:
   ```bash
   psql -U postgres -d postgres
   ```
   Check for the user:
   ```sql
   SELECT usename FROM pg_catalog.pg_user WHERE usename = 'postgres_exporter';
   ```

3. If the user does not exist, create the `postgres_exporter` user and grant execution privileges on `pg_ls_waldir()`:
   ```sql
   CREATE USER postgres_exporter WITH PASSWORD 'Ginesys@01';
   GRANT EXECUTE ON FUNCTION pg_ls_waldir() TO postgres_exporter;
   ```

### 9.3 Verify Prometheus Service
Ensure the Prometheus time-series database is active:
```bash
sudo systemctl status prometheus
# Output should show "active (running)"
```

---

## 10. Phase 8: Post-Migration WAL Archiving Activation

### 10.1 Theory: Point In Time Recovery (PITR)
To achieve data durability, transaction records (WAL files) must be continuously archived. By setting `archive_mode = on` and configuring `archive_command` to execute our `BLOB.sh` script, PostgreSQL ensures every transaction log segment is copied to remote cloud storage before it is recycled locally. This enables recovering the database up to the exact millisecond of a failure.

### 10.2 Activation Process (Post Oracle Migration)
1. Complete migration data verification checkouts.
2. Edit `postgresql.conf`:
   ```bash
   sudo vi $PGDATA/postgresql.conf
   ```
3. Update the parameters to enable the pipeline:
   ```ini
   archive_mode = on
   archive_command = '/u01/Gsl/BLOB.sh %p %f'
   archive_timeout = 120
   ```
4. Restart the database engine to start logging to Azure Storage:
   ```bash
   sudo systemctl restart postgresql-<version>
   ```
5. Verify archives are successfully transferring to cloud container storage by checking:
   - `/u01/backup/logs/arc_sync/blob_archive.log`
   - Remote Azure Storage container path `/archive/`.

---
## Additional Configuration
> *   **PGGDBA Configuration:** To configure the `pggdba` database for tracking historical size and growth data, please refer to the independent **PGGDBA Runbook Documentation**.
> *   **Grafana Configuration:** To configure Grafana for live monitoring of the new instance, please refer to the independent **Grafana Dashboard Runbook Documentation**.



## 11. Phase 9: Setting up Physical Streaming Replication after go-Live [OPTIONAL]

### 11.1 Streaming Replication Theory
- WAL record chunks are streamed by database servers to keep data in sync.
- The standby server connects to the master to receive the WAL chunks.
- The WAL records are streamed as they are generated.
- The streaming of WAL records need not wait for the WAL file to be filled.
- This allows a standby server to stay more up-to-date than is possible with file-based log shipping.
- By default, streaming replication is asynchronous even though it also supports synchronous replication.

### 11.2 Replication Parameters

| Parameter             | Value       | Description                                                                                  |
|-----------------------|-------------|----------------------------------------------------------------------------------------------|
| `wal_level`           | `replica`   | Level of info written to WAL; `replica` supports archiving and read-only queries on standby. |
| `wal_log_hints`       | `on`        | Required for `pg_rewind` capability when standby goes out of sync with master.               |
| `max_wal_senders`     | `integer`   | Max concurrent running WAL sender processes (default 10; 0 disables replication).            |
| `wal_keep_segments`   | `integer`   | Min number of past log file segments kept in the `pg_wal` directory for standby fetch.       |
| `hot_standby`         | `on`        | Enables read-only connection on the node when it is in standby role.                         |

### 11.3 Replication Slots
- A replication slot is used to retain the WAL files when the standby goes offline or disconnected.
- The master server uses replication slots to keep track of how much the standby lags and retain the WAL files it needs until the standby reconnects again.
- Replication slots came in with PostgreSQL 9.4, before that the `wal_keep_segments` parameter used to govern how many wal files need to be maintained.
- Replication slots have to be created manually and the default value is 10.
- PostgreSQL Replication slots are of two types:
  - Physical replication slots
  - Logical replication slots

### 11.4 Streaming Replication Setup Steps

**On Master Node:**
**Step 1:** Setup the following postgres config in `postgresql.conf`:
```ini
listen_addresses = '*'
wal_level = replica
hot_standby = on
```

**Step 2:** Create or alter a user to use replication encrypted password:
```sql
ALTER USER postgres WITH REPLICATION ENCRYPTED PASSWORD '<password>';
```

**Step 3:** Modify `pg_hba.conf` to allow replication connections. Add the IP addresses of both master and standby with the `md5` method:
```text
host    replication    postgres    <primary_ip>/32      md5
host    replication    postgres    <standby_ip>/32      md5
```

**Step 4:** Reload/restart the configuration.
```bash
sudo systemctl reload postgresql-<version>
```

**On Standby Node:**
**Step 5:** Stop the postgresql service on the standby node.
```bash
sudo systemctl stop postgresql-<version>
```

**Step 6:** Delete all the files under the data directory.
```bash
rm -rf /u01/pgsql/<version>/data/*
```

**Step 7:** Run `pg_basebackup` to clone the standby instance:
```bash
pg_basebackup -h <primary_ip> -U postgres -p 5432 -D /u01/pgsql/<version>/data -Fp -Xs -P -R -C -S pgstandby
```
> **Note:** Here `-S pgstandby` represents a replication slot.

**Step 8:** Start the postgresql service on the standby node.
```bash
sudo systemctl start postgresql-<version>
```

**Step 9:** Test replication by creating a table in primary and checking standby.

### 11.5 Monitoring Primary and Standby Streaming Replication

**On Primary:**
- Check stream replication slots information:
```sql
SELECT * FROM pg_replication_slots;
```

- Check PG replication status:
```sql
SELECT * FROM pg_stat_replication;
```
> **Note:** 0 lag indicates no gap between primary and secondary.

**On Standby:**
- Check if secondary cluster is in recovery mode or not:
```sql
SELECT pg_is_in_recovery();
```
