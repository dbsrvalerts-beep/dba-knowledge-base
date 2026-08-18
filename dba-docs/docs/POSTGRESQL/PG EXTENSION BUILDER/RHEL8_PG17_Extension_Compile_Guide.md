# PostgreSQL 17 Extension Compile Guide for RHEL 8
**Target Environment:** RHEL 8 / AlmaLinux 8 / CentOS 8  
**PostgreSQL Version:** 17  
**Extension:** `pg_proctab` (or similar extensions built from source)

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
>    - **Shared library file (`.so`)**: to `/usr/pgsql-17/lib/`
>    - **Control (`.control`) and SQL (`.sql`) files**: to `/usr/pgsql-17/share/extension/`

> [!NOTE]
> **Example Extension Only:**
> The step-by-step commands below use the `pg_proctab` extension as a reference example. If you are building a different extension, you must substitute the download URLs, directory names, makefile patches (if any), and SQL/extension names with your own extension's source code and requirements.

---

## 3. End-to-End Implementation Steps

Below is the master step-by-step guide to downloading, compiling, and deploying the extension from source on your production server.

### Step 1: Install Development Tools
Install the compiler tools and the specific PostgreSQL 17 development headers needed to build the extension.
```bash
sudo dnf install -y gcc make postgresql17-devel unzip wget redhat-rpm-config
```

### Step 2: Download and Extract the Source Code
Download the code directly from the official repository and unzip it.
```bash
cd /tmp
wget https://github.com/markwkm/pg_proctab/archive/refs/heads/master.zip -O pg_proctab-main.zip
unzip pg_proctab-main.zip
cd pg_proctab-master
```

### Step 3: Patch the Makefile Bug (If applicable)
Apply this quick patch to fix a known duplicate file bug in the extension's Makefile, ensuring it doesn't crash during the installation phase.

> [!NOTE]
> This patch is specific to `pg_proctab` to resolve a bug where the Makefile wildcard patterns match overlapping files. For other extensions, this step is **not required** and should be skipped.

```bash
sed -i 's|DATA = \$(wildcard sql/\*--\*.sql) sql/\$(EXTENSION)--\$(EXTVERSION).sql|DATA = \$(sort \$(wildcard sql/\*--\*.sql) sql/\$(EXTENSION)--\$(EXTVERSION).sql)|' Makefile
```

### Step 4: Compile the Native Binary
Run the compilation process, explicitly telling it to use the PostgreSQL 17 configuration. This generates the `.so` binary file specifically for your OS and Postgres version.
```bash
make USE_PGXS=1 PG_CONFIG=/usr/pgsql-17/bin/pg_config
```

### Step 5: Install the Extension Files
Copy the compiled `.so` library, `.control`, and `.sql` files into the protected PostgreSQL system folders.
```bash
sudo make install USE_PGXS=1 PG_CONFIG=/usr/pgsql-17/bin/pg_config
```

### Step 6: Enable in Your Databases
Log into your PostgreSQL instance and enable it for your current databases. *(Adjust the port `-p 5433` if your database runs on the default `5432`)*

**For all existing databases at once (Automated Script):**
If you have many databases, you can use this quick bash script to loop through all of them and install the extension automatically:

```bash
# Loop through all non-template databases and install the extension
sudo -u postgres /usr/pgsql-17/bin/psql -p 5433 -t -c "SELECT datname FROM pg_database WHERE datistemplate = false;" | while read dbname; do
    if [ -n "$dbname" ]; then
        echo "Installing in database: $dbname"
        sudo -u postgres /usr/pgsql-17/bin/psql -p 5433 -d "$dbname" -c "CREATE EXTENSION IF NOT EXISTS pg_proctab;"
    fi
done
```

**For all future databases (Optional):**
If you want the extension to automatically exist in any new databases you create tomorrow, install it into the `template1` database blueprint:
```bash
sudo -u postgres /usr/pgsql-17/bin/psql -p 5433 -d template1 -c "CREATE EXTENSION IF NOT EXISTS pg_proctab;"
```
