# PostgreSQL AutoTune: Implementation Steps

Follow these steps exactly to deploy and integrate the PostgreSQL systemd auto-tuner hook (v4) on your self-hosted RHEL 8 Linux VM:

---

### STEP 1: Copy the Script to the Server
Upload `pg_autotune_systemd.sh` to your server and place it in the `/u01/Gsl/` directory:
```bash
cp pg_autotune_systemd.sh /u01/Gsl/pg_autotune_systemd.sh
```

### STEP 2: Configure User Variables
Open the script and update the `USER CONFIGURATION` block at the top of the file:
```bash
MAX_CONNECTIONS=5000               # Passed to pgconfig.org API
WORK_MEM_MB=500                    # Static work_mem (MB)
WAL_BUFFERS_MB=32                  # Static wal_buffers (MB)
TEST_SLEEP_SECONDS=30              # Set to 0 in production!
```

### STEP 3: Make the Script Executable
```bash
sudo chmod +x /u01/Gsl/pg_autotune_systemd.sh
```

### STEP 4: Create the Log Directories
The script writes timestamped logs and config backups to `/u01/backup/logs/autotune/`:
```bash
sudo mkdir -p /u01/backup/logs/autotune/config_backup
```

### STEP 5: Fix SELinux Context (CRITICAL — Do NOT skip)
SELinux assigns a generic data label to files in `/u01/`. Systemd refuses to execute files without the official `bin_t` binary label.

**Command:**
```bash
sudo chcon -t bin_t /u01/Gsl/pg_autotune_systemd.sh
```

**Verify:**
```bash
ls -Z /u01/Gsl/pg_autotune_systemd.sh
# Should show: system_u:object_r:bin_t:s0
```
_Skipping this step causes "Permission denied" errors during ExecStartPre execution, even if chmod +x is set correctly._

### STEP 6: Add the Hook to the Systemd Service
Open the main PostgreSQL systemd service file directly using a text editor (like vi):
```bash
sudo vi /usr/lib/systemd/system/postgresql-16.service   # or postgresql-17.service
```

Find the `[Service]` block and insert this line right below it:
```ini
[Service]
ExecStartPre=+/u01/Gsl/pg_autotune_systemd.sh
```
> [!IMPORTANT]
> The `+` prefix is mandatory. It grants the script root execution privilege. Without `+`, the script runs as the postgresql service user and will fail.

### STEP 7: Apply the Changes
Reload systemd daemon to pick up the service file modification:
```bash
sudo systemctl daemon-reload
```

### STEP 8: Test the Integration
Stop and start PostgreSQL to trigger the hook:
```bash
sudo systemctl stop postgresql-16
sudo systemctl start postgresql-16
```

During startup, open a second terminal and watch the status. If `TEST_SLEEP_SECONDS=30`, you will see the service pause for 30 seconds:
```bash
systemctl status postgresql-16
```

After startup completes, check the log:
```bash
cat /u01/backup/logs/autotune/pg_autotune_*.log
```
You should see the tuning trace including:
- Hardware detection output
- "HARDWARE CHANGE DETECTED" block (first run always triggers)
- Before &rarr; After trace for each of the 8 parameters
- "Process complete. State saved inside script."

### STEP 9: Go to Production
After successful validation, disable the test sleep. Edit `/u01/Gsl/pg_autotune_systemd.sh` and set:
```bash
TEST_SLEEP_SECONDS=0
```
Then reload systemd daemon:
```bash
sudo systemctl daemon-reload
```

---

### Troubleshooting Checklist

* **Problem: PostgreSQL fails to start after hook is added**
  * *Fix:* Run: `sudo chcon -t bin_t /u01/Gsl/pg_autotune_systemd.sh` and verify context with `ls -Z`.
* **Problem: No log file in /u01/backup/logs/autotune/**
  * *Fix:* Run: `sudo mkdir -p /u01/backup/logs/autotune/config_backup` and check `journalctl -xe` for errors.
* **Problem: Script runs but no tuning happens (no parameter changes)**
  * *Fix:* `LAST_KNOWN_STATE` inside the script may already match. Edit `/u01/Gsl/pg_autotune_systemd.sh`, set `LAST_KNOWN_STATE="First Run"`, and restart.
* **Problem: API fallback math used every time**
  * *Fix:* Normal if the server has no outbound internet access. Fallback math is intentional.
