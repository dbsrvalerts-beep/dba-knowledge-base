# PostgreSQL AutoTune: Azure VM Scale Implementation

_Version 4.0 - Systemd ExecStartPre Architecture_

* **Script:** `pg_autotune_systemd.sh` &rarr; Deploy to `/u01/Gsl/pg_autotune_systemd.sh`
* **Log Directory:** `/u01/backup/logs/autotune/`

---

## 1. Overview

This document describes the design, workflow, and implementation of the Version 4 PostgreSQL Auto-Tuning solution for self-hosted PostgreSQL 16/17 on Azure Linux VMs (RHEL 8). When an Azure VM is scaled up or down, the script automatically detects the new hardware profile and applies optimized PostgreSQL parameters on startup - with zero manual intervention and zero double restarts.

The memory allocation formulas calculate `shared_buffers` at 26% and `effective_cache_size` at 76% of OS-visible physical RAM (`MemTotal`). It also uses the dynamically detected `PG_VERSION` for service restarts. In V4, the email functionality has been entirely removed to focus on reliable log tracing, and the CPU fallback formula for `max_parallel_workers_per_gather` was updated.

---

## 2. Key Architecture Design

### 2.1 Systemd ExecStartPre Hook

The script is registered as a privileged `ExecStartPre` hook on the PostgreSQL systemd unit. Systemd guarantees the hook completes before `ExecStart` launches the database engine. This means the script runs after the new hardware is visible to the OS, but before PostgreSQL starts - the database always boots with parameters matched to the current VM size.

### 2.2 Zero Double-Restart Design
The script does **NOT** call `pg_ctl stop/start`. The single PostgreSQL startup is performed natively by Systemd after the script exits. This eliminates the double-restart problem seen with cron-based V1 deployments.

### 2.3 Version Detection (No Running Service Required)
`PG_VERSION` is detected by calling the postgres binary with the `-V` flag. This reads the version string compiled into the binary - it does not require the PostgreSQL service to be running. This is safe in an `ExecStartPre` context where the database engine has not yet started.

```bash
PG_VERSION=$(postgres -V 2>/dev/null | awk '{print $NF}' | cut -d. -f1)
# Fallback 1: psql -V | Fallback 2: hardcoded "17"
```

---

## 3. V4 Memory and CPU Formulas

All memory parameters are calculated from `MemTotal` in `/proc/meminfo` - the total physical RAM visible to the OS kernel. This is slightly less than the Azure VM SKU spec (due to kernel reservations and hypervisor overhead) but is the correct value for PostgreSQL tuning.

> [!IMPORTANT]
> `MemTotal` is the right source. Do not use the Azure portal RAM spec - it includes overhead the OS cannot use. `MemTotal` reflects exactly what PostgreSQL can work with.

### 3.1 Parameter Reference Table

| Parameter | Formula / Source | Type | 64 GB RAM, 16 CPU Example |
| :--- | :--- | :--- | :--- |
| `shared_buffers` | `(RAM_MB * 26) / 100` | Calculated | 17039 MB (~16.6 GB) |
| `effective_cache_size` | `(RAM_MB * 76) / 100` | Calculated | 49807 MB (~48.6 GB) |
| `maintenance_work_mem` | `max(RAM_GB / 20, 1) * 1024 MB` | Calculated | 3072 MB (3 GB) |
| `work_mem` | Static: `WORK_MEM_MB` | User config | 500 MB |
| `wal_buffers` | Static: `WAL_BUFFERS_MB` | User config | 32 MB |
| `max_worker_processes` | API or `CPU_CORES` | API/Fallback | 16 |
| `max_parallel_workers` | API or `CPU_CORES` | API/Fallback | 16 |
| `max_parallel_workers_per_gather` | API or `min(4, CPU/2)` | API/Fallback | 4 |

### 3.2 RAM Integer Division Note
The shell variable `TOTAL_RAM_GB` is computed by integer division (`TOTAL_RAM_MB / 1024`). On a 32 GB VM this produces 31 (truncated), not 32. This affects `maintenance_work_mem` and the value passed to the `pgconfig.org` API. Memory parameters (`shared_buffers`, `effective_cache_size`) are calculated from `TOTAL_RAM_MB` which is accurate to the MB level.

### 3.3 Parallel Workers per Gather Fallback
If the `pgconfig.org` API is unreachable, the script uses local math to determine CPU-related parameters. For `max_parallel_workers_per_gather`, V4 updates the formula to `min(4, Total CPU Cores / 2)`. This safely limits parallel coordination overhead on large VMs while allowing up to 4 parallel workers.

---

## 4. User Configuration Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MAX_CONNECTIONS` | `5000` | Passed to pgconfig.org API for connection-aware CPU tuning. |
| `WORK_MEM_MB` | `500` | Static work_mem in MB - not auto-scaled (set deliberately per workload). |
| `WAL_BUFFERS_MB` | `32` | Static wal_buffers in MB. |
| `TEST_SLEEP_SECONDS` | `30` | Startup pause for testing ExecStartPre gap. Set to 0 in production. |

---

## 5. Project File Reference

| File | Status | Purpose |
| :--- | :--- | :--- |
| `pg_autotune_systemd.sh` | **CURRENT - deploy this** | V4 script. Deploy to `/u01/Gsl/pg_autotune_systemd.sh`. |
| `PostgreSQL_AutoTune_Azure_VM_Scale_Implementation.md` | **CURRENT** | This document - V4 specification & overview. |
| `pgautotune_workflow.md` | **CURRENT** | Mermaid process flowchart and logic breakdown. |
| `pgautotune_implementation_steps.md` | **CURRENT** | Step-by-step deployment guide. |
