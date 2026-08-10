import re

filepath = r'd:\Github Development\dba-knowledge-base\dba-docs\docs\ORACLE\KNOWN ISSUES\Oracle Database Incarnation (ORA-19909).md'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace block 1
block1_old = """SQL> recover database using backup controlfile until cancel;

ORA-00283: recovery session canceled due to errors

ORA-19909: datafile 1 belongs to an orphan incarnation

ORA-01110: data file 1: '/u01/Oracle/oradata/GINESYS/system01.dbf'"""

block1_new = """```sql
SQL> recover database using backup controlfile until cancel;
ORA-00283: recovery session canceled due to errors
ORA-19909: datafile 1 belongs to an orphan incarnation
ORA-01110: data file 1: '/u01/Oracle/oradata/GINESYS/system01.dbf'
```"""
text = text.replace(block1_old, block1_new)

text = text.replace("RMAN> list incarnation of database;", "```sql\nRMAN> list incarnation of database;\n```")
text = text.replace("RMAN> reset database to incarnation 2;", "```sql\nRMAN> reset database to incarnation 2;\n```")
text = text.replace("SQL>recover database using backup controlfile until cancel;", "```sql\nSQL> recover database using backup controlfile until cancel;\n```")

# Block 2
block2_old = """SQL> alter database backup controlfile to trace as '/u01/control.txt';

<sub>Database altered</sub>

SQL> alter database backup controlfile to '/u01/control.ctl';

<sub>Database altered</sub>"""

block2_new = """```sql
SQL> alter database backup controlfile to trace as '/u01/control.txt';
Database altered
SQL> alter database backup controlfile to '/u01/control.ctl';
Database altered
```"""
text = text.replace(block2_old, block2_new)

# Block 3
block3_old = """SQL> shutdown immediate;

<sub>Database closed.</sub>

<sub>Database dismounted.</sub>

<sub>ORACLE instance shut down.</sub>

SQL> startup nomount;

<sub>ORACLE instance started.</sub>

<sub>Total System Global Area 627732480 bytes</sub>

<sub>Fixed Size 1346756 bytes</sub>

<sub>Variable Size 373293884 bytes</sub>

<sub>Database Buffers 247463936 bytes</sub>

<sub>Redo Buffers 5627904 bytes</sub>"""

block3_new = """```sql
SQL> shutdown immediate;
Database closed.
Database dismounted.
ORACLE instance shut down.
SQL> startup nomount;
ORACLE instance started.
Total System Global Area 627732480 bytes
Fixed Size 1346756 bytes
Variable Size 373293884 bytes
Database Buffers 247463936 bytes
Redo Buffers 5627904 bytes
```"""
text = text.replace(block3_old, block3_new)

# Block 4
block4_start = 'CREATE CONTROLFILE REUSE DATABASE "GINESYS" NORESETLOGS ARCHIVELOG'
block4_end = 'CHARACTER SET WE8MSWIN1252;'
start_idx = text.find(block4_start)
end_idx = text.find(block4_end) + len(block4_end)
if start_idx != -1 and end_idx != -1:
    block4_old = text[start_idx:end_idx]
    block4_new = "```sql\n" + block4_old.replace('\n\n', '\n') + "\n```"
    text = text.replace(block4_old, block4_new)

# Block 5
block5_old = """SQL> RECOVER DATABASE;

<sub>ORA-00283: recovery session canceled due to errors</sub>

<sub>ORA-00264: no recovery required</sub>"""

block5_new = """```sql
SQL> RECOVER DATABASE;
ORA-00283: recovery session canceled due to errors
ORA-00264: no recovery required
```"""
text = text.replace(block5_old, block5_new)

# Block 6
block6_old = """SQL> alter database open;

<sub>Database altered.</sub>"""

block6_new = """```sql
SQL> alter database open;
Database altered.
```"""
text = text.replace(block6_old, block6_new)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print("Formatting ORA-19909 complete")
