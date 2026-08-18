# PostgreSQL 16 Extension Compile Guide for RHEL 8
**Target OS:** Red Hat Enterprise Linux 8 / AlmaLinux 8 / Rocky Linux 8  
**PostgreSQL Version:** 16  
**Extension:** `pg_proctab` (or similar PGXS-based extensions built from source)

---

## 1. Do I need to install it in every single database?
**Yes.** In PostgreSQL, extensions are installed on a strictly **per-database** basis. The extension's functions will only be queryable inside the specific databases where you have executed `CREATE EXTENSION;`.

> **Pro-Tip for Future Databases:** If you want the extension to be automatically available in every brand new database you create in the future, you should install it into the `template1` database. PostgreSQL uses `template1` as the default blueprint for all new databases.

---

## 2. Portability & Compilation Environment Notes

> [!IMPORTANT]
> **OS & Architecture Dependency:** 
> Compiling extensions generates dynamic library files (`.so` binaries). These binaries are strictly compiled for the specific compiler version, OS kernel version, and CPU architecture of the host machine. Consequently, they are **strictly OS-dependent**. For example, you **cannot** copy a `.so` binary compiled on RHEL 8 to an instance running on Ubuntu or another incompatible OS.

> [!TIP]
> **Using a Development/Build Server:**
> If you are compiling the extension on a Development/Build server to avoid installing compiler tools (like `gcc`, `make`, and development headers) on the live production server:
> 1. The Development/Build server **must** run the exact same OS distribution, version, architecture, and PostgreSQL version as the Production server.
> 2. Once successfully built, copy the compiled files from the Dev server to the Production server at the **exact same paths**:
>    - **Shared library file (`.so`)**: to `/usr/pgsql-16/lib/`
>    - **Control (`.control`) and SQL (`.sql`) files**: to `/usr/pgsql-16/share/extension/`

> [!NOTE]
> **Example Extension Only:**
> The step-by-step commands below use the `pg_proctab` extension as a reference example. If you are building a different extension, you must substitute the download URLs, directory names, makefile patches (if any), SQL/extension names, and **any extension-specific prerequisite packages/libraries** with your own extension's source code and requirements.

---

## 3. End-to-End Compile and Install Steps

We use the example of `pg_proctab` below, but this workflow applies to any PGXS-supported extension.

### Step 1: Install Development Tools (Only on Compilation/Build Host)
Install compiler tools and the specific PostgreSQL 16 development headers needed to build the extension. *(If you are using a development/build server, run this step on that server only.)*
```bash
sudo dnf install -y gcc make postgresql16-devel redhat-rpm-config wget unzip
```

### Step 2: Download & Extract Source Code
```bash
cd /tmp
wget https://github.com/markwkm/pg_proctab/archive/refs/heads/master.zip -O pg_proctab-main.zip
unzip pg_proctab-main.zip
cd pg_proctab-master
```

### Step 3: Fix Makefile Wildcard Duplication (If applicable)
For `pg_proctab` specifically, apply a patch to prevent file duplication errors in the Makefile target:

> [!NOTE]
> This patch is specific to `pg_proctab` to resolve a bug where the Makefile wildcard patterns match overlapping files. For other extensions, this step is **not required** and should be skipped.

```bash
sed -i 's|DATA = \$(wildcard sql/\*--\*.sql) sql/\$(EXTENSION)--\$(EXTVERSION).sql|DATA = \$(sort \$(wildcard sql/\*--\*.sql) sql/\$(EXTENSION)--\$(EXTVERSION).sql)|' Makefile
```

### Step 4: Build the Extension
Compile the extension by pointing `PG_CONFIG` explicitly to the PostgreSQL 16 executable:
```bash
make USE_PGXS=1 PG_CONFIG=/usr/pgsql-16/bin/pg_config
```

### Step 5: Install the Compiled Extension
Install the resulting `.so` file, `.control` file, and `.sql` script files into the PostgreSQL 16 directories:
```bash
sudo make install USE_PGXS=1 PG_CONFIG=/usr/pgsql-16/bin/pg_config
```


###output files will be:###
/usr/pgsql-16/lib/pg_proctab.so
/usr/pgsql-16/share/extension/pg_proctab.control
/usr/pgsql-16/share/extension/pg_proctab--0.0.13.sql
/usr/pgsql-16/share/extension/pg_proctab--0.0.9--0.0.10.sql
/usr/pgsql-16/share/extension/pg_proctab--0.0.5--0.0.6.sql



---

## 4. Database Activation

After installation, activate the extension within your PostgreSQL instance.

### Step 1: Log in and Run SQL Commands
Connect to the database server using `psql` (adjust port if running on a custom port like 5433):
```bash
sudo -u postgres /usr/pgsql-16/bin/psql -p 5432 -d mydatabase -c "CREATE EXTENSION IF NOT EXISTS pg_proctab;"
```

### Step 2: Auto-Install in All Existing Databases
To enable the extension in all current user databases, run:
```bash
sudo -u postgres /usr/pgsql-16/bin/psql -p 5432 -t -c "SELECT datname FROM pg_database WHERE datistemplate = false;" | while read dbname; do
    if [ -n "$dbname" ]; then
        echo "Activating in: $dbname"
        sudo -u postgres /usr/pgsql-16/bin/psql -p 5432 -d "$dbname" -c "CREATE EXTENSION IF NOT EXISTS pg_proctab;"
    fi
done
```

### Step 3: Enable in Default Template Database (for all future DBs)
```bash
sudo -u postgres /usr/pgsql-16/bin/psql -p 5432 -d template1 -c "CREATE EXTENSION IF NOT EXISTS pg_proctab;"
```
