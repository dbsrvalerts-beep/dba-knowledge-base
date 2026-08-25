# New Self-Hosted PostgreSQL Instance — Onboarding Checklist

Use this checklist every time a new self-hosted PostgreSQL instance is deployed. Replace `{server_number}`, `{host_ip}`, and `{alias}` placeholders with the actual values for the new instance.

---

## 1. Grafana Data Sources

- [ ] Add new **Prometheus** data source
  - Name: `vm-psql-erp-prod-{server_number}`
- [ ] Add new **PostgreSQL** data source
  - Name: `vm-psql-erp-prod-{server_number}-pg`
  - Host URL: `{host_ip}`
  - Database: `postgres`
  - TLS/SSL mode: `disable`

## 2. Grafana Dashboards

- [ ] Add instance to **DBA-PG SELFHOSTED DASHBOARD-1/2/3/...n**
- [ ] Add to **SelfHosted Streaming Replication** dashboard *(if replication is applicable)*
- [ ] Add to **INSTANCES INFO {ORA-PG}** dashboard panels:
  - [ ] Total Live PostgreSQL Databases
  - [ ] Live PostgreSQL Databases
  - [ ] Live PostgreSQL Databases Names
- [ ] Add to **GINESYS PostgreSQL Dashboard → PGGDBA DAILY DATA RECORD**:
  - [ ] Add data source to PG Logical Slot panel
  - [ ] Create new dashboard panel for hourly WAL generation map
  - [ ] Add data source to ZZZ and PRODX Databases panel
  - [ ] Add new panel for Self-Hosted DB Size insertion
  - [ ] Add new panel for Self-Hosted DB Object/Segment insertion

## 3. PGGDBA Toolkit

- [ ] Add host mapping for the new instance
- [ ] DB Management → Add segment table (same name as hostname column in host mapping)
- [ ] PS Script Generator → generate all scripts including the new host
- [ ] **Note:** for the vacuum_analyze PowerShell script, manually remove the trailing comma after the last host entry in the `$instances` array, e.g.:

  ```powershell
  $instances = @(
      ...
      @{ Host = '{host_ip}'; Alias = '{alias}'; User = 'postgres'; LogDir = $logDirN; Password = 'postgres' }
  )
  ```

- [ ] `ginviewkill` PowerShell script generation is **deprecated** — skip (now handled by application team via `pg_cron`)

## 4. sql_exporter / Prometheus

- [ ] Add new job in `sql_exporter_postgres.yml`:
  ```
  C:\PGPAAS\UNDER_DEVELOPMENT[DO_NOT_TOUCH]\sql_exporter-0.19.1.windows-amd64\sql_exporter-0.19.1.windows-amd64\config\sql_exporter_postgres.yml
  ```
  ```yaml
  - job_name: postgres_selfhosted_{server_number}
      collectors: [postgres_metrics]
      static_configs:
        - targets:
            SELFHOSTED-{server_number}: 'postgresql://postgres:{password}@{host_ip}:5432/postgres?sslmode=disable'
  ```
- [ ] Restart the sql_exporter kit

### Decommissioning (if a client is deactivated)
- [ ] Remove entry from `sql_exporter_postgres.yml` (or `sql_exporter_oracle.yml` for Oracle clients)
- [ ] Remove disk monitoring entry from `prometheus.yml`:
  ```
  C:\PGPAAS\UNDER_DEVELOPMENT[DO_NOT_TOUCH]\prometheus-3.12.0.windows-amd64\prometheus-3.12.0.windows-amd64\prometheus.yml
  ```
- [ ] Delete the Prometheus data folder after removal (prevents deactivated clients piling up in Grafana instance lists):
  ```
  C:\PGPAAS\UNDER_DEVELOPMENT[DO_NOT_TOUCH]\prometheus-3.12.0.windows-amd64\prometheus-3.12.0.windows-amd64\data
  ```

## 5. PG Heartbeat

- [ ] Add new instance to PG Heartbeat config
- [ ] Restart the heartbeat task from Task Scheduler

## 6. PG Inactive Slot Monitoring

- [ ] Add new instance to PG Inactive Slot monitoring (Physical/Logical replication)
- [ ] Restart the PG Inactive Slot task from Task Scheduler

## 7. PG Tracker

- [ ] Add new instance to `hosts.json` for PGTRACKER
- [ ] Restart the PGTRACKER task from Task Scheduler

## 8. Grafana Alert Rules

- [ ] **Self-Hosted Alerts → Self-Hosted CPU Alerts** — add CPU busy alert
- [ ] **Self-Hosted Alerts → Self-Hosted Disk Alerts** — add disk usage alert
- [ ] **Self-Hosted Alerts → Self-Hosted MEMORY Alerts** — add memory usage alert
- [ ] **Self-Hosted Alerts → Self-Hosted Transaction Log Alerts** — add alert
- [ ] **Self-Hosted Alerts → Self-Hosted Replication Lag Alerts** — add alert *(if replication is applicable)*

---

*Last updated: manual — sync with PGGDBA/monitoring stack changes as they occur.*
