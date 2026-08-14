# Azure Linux VM Timezone Configuration Guide

This document outlines the procedure for changing the timezone of Azure Linux VMs from the default UTC to Indian Standard Time (IST - `Asia/Kolkata`) and mitigating a common bug where system schedulers and logging services lag behind the change.

---

## 1. Standard Timezone Modification Steps

By default, newly provisioned Azure VMs are set to the **UTC** timezone. Follow these steps to change it without requiring a server reboot:

### Step 1: List Available Timezones (Optional)
To verify the exact identifier for your target timezone, you can list the system's available timezones:
```bash
timedatectl list-timezones | grep Kolkata
```

### Step 2: Check Current Timezone Settings
View the current active timezone and system clock parameters:
```bash
timedatectl
```

### Step 3: Set the New Timezone
Change the system timezone to `Asia/Kolkata` (IST):
```bash
sudo timedatectl set-timezone Asia/Kolkata
```

### Step 4: Verify the Clock Update
Verify the change immediately using the `timedatectl` or `date` commands:
```bash
date
```
*Expected Output:*
`Fri Aug 14 00:58:30 IST 2026` [u will see current timestamp as per your execution time]

---

## 2. Critical Bug: Lagging System Services

> [!WARNING]
> **Issue**: Even though the `date` command and `timedatectl` report the correct timezone (IST) immediately, some active background system services (specifically `crond` and `rsyslog`) will **not** pick up the change immediately. They will continue executing and logging in the old **UTC** timezone.
>
> **Impact**: This timezone mismatch will break your cron job execution schedules (executing tasks at incorrect times) and desynchronize server audit logs.

### Example Diagnostic Log:
Here is an example showing the discrepancy:
```bash
# Check current system date (updated to IST):
[root@vm-psql-erp-prod-01 ~]# date
Fri Aug 14 00:58:30 IST 2026

# Check recent cron execution logs (still logging in UTC):
[root@vm-psql-erp-prod-01 ~]# tail -10 /var/log/cron
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT (Total Number of Transfers: 1)
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT (Number of File Transfers Completed: 1)
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT (Number of Folder Transfers Completed: 0)
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT (Number of File Transfers Failed: 0)
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT (Number of Folder Transfers Failed: 0)
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT (Number of File Transfers Skipped: 0)
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT (Number of Folder Transfers Skipped: 0)
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT (Total Number of Bytes Transferred: 159853)
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT (Final Job Status: Completed)
Aug 13 19:28:06 vm-psql-erp-prod-01 CROND[3499137]: (postgres) CMDOUT ()
```
*Note that the `date` command shows August 14th, while the cron log entries are still generated with August 13th timestamps.*

---

## 3. Mitigation Options

To ensure all background schedulers and logging systems sync with the new timezone, you must apply one of the following two mitigation options:

### Option A: Restart the Server (Recommended & Safest)
If a maintenance window allows, rebooting the VM will guarantee that all system and application services reload and register the new timezone settings:
```bash
sudo reboot
```

### Option B: Restart Services (Zero Downtime)
If you cannot afford a server reboot or database downtime at the moment, execute the following commands as the `root` user (or with `sudo`) to restart the cron daemon and logging systems manually:

```bash
sudo systemctl restart crond
sudo systemctl restart rsyslog
```

---

## 4. Final Verification

Once the services are restarted, verify that the logs are matching the new timezone:
```bash
tail -10 /var/log/cron
```
All new cron task entries should now print timestamps corresponding with the active **IST** timezone.
