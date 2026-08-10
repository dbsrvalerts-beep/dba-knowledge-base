# Oracle Datapump Slowness (Scenario 2)

- **Scenario:** The Data pump export job now takes more than one hour, whereas it used to be completed within 15 to 20 minutes previously.

Upon Inspection, all the specifications of the system and database parameters were as follows:

1. RAM: 120 GB (40 Gb assigned to database server and rest to application server via virtualization)
2. SGA_MAX_SIZE: 20 GB
3. SGA_TARGET_SIZE: 20 GB
4. PGA_AGGREGATE_LIMIT: 12 GB
5. PGA_AGGREGATE_TARGET: 11 GB
6. Tablespace Information

| **TABLESPACE NAME** | **FILE NAME**                                        | **TOTAL MB** |
| ------------------- | ---------------------------------------------------- | ------------ |
| GINOLAP             | /oracle/ora12cdb/oradata/GINESYS/GINOLAP01.DBF       | 32720        |
| GINOLAP             | /oracle/ora12cdb/oradata/GINESYS/GINOLAP02.DBF       | 32720        |
| GINOLAP             | /oracle/ora12cdb/oradata/GINESYS/GINOLAP03.DBF       | 32767.98438  |
| GINOLAP             | /oracle/ora12cdb/oradata/GINESYS/GINOLAP04.DBF       | 9216         |
| GIN_TS_NOLOGGING    | /oracle/ora12cdb/oradata/GINESYS/GIN_TS_NOLOGGING_01 | 2048         |
| GIN_TS_SUMMARY      | /oracle/ora12cdb/oradata/GINESYS/GIN_TS_SUMMARY_01   | 1024         |
| GIN_TS_TX_DATA      | /oracle/ora12cdb/oradata/GINESYS/GIN_TS_TX_DATA_01   | 2048         |
| INDX                | /oracle/ora12cdb/oradata/GINESYS/INDX01              | 32720        |
| INDX                | /oracle/ora12cdb/oradata/GINESYS/INDX02              | 32720        |
| INDX                | /oracle/ora12cdb/oradata/GINESYS/INDX03              | 32720        |
| INDX                | /oracle/ora12cdb/oradata/GINESYS/INDX04              | 29180        |
| INDX                | /oracle/ora12cdb/oradata/GINESYS/INDX05              | 8192         |
| SYSAUX              | /oracle/ora12cdb/oradata/GINESYS/sysaux01.dbf        | 10380        |
| SYSTEM              | /oracle/ora12cdb/oradata/GINESYS/system01.dbf        | 12020        |
| TEMP                | /oracle/ora12cdb/oradata/GINESYS/temp01.dbf          | 32767.98438  |
| TEMP                | /oracle/ora12cdb/oradata/GINESYS/temp02.dbf          | 30720        |
| UNDOTBS1            | /oracle/ora12cdb/oradata/GINESYS/undotbs01.dbf       | 25600        |
| USERS               | /oracle/ora12cdb/oradata/GINESYS/users01.dbf         | 32767.98438  |
| USERS               | /oracle/ora12cdb/oradata/GINESYS/users02.dbf         | 32720        |
| USERS               | /oracle/ora12cdb/oradata/GINESYS/users03.dbf         | 32720        |
| USERS               | /oracle/ora12cdb/oradata/GINESYS/users04.dbf         | 32767.98438  |
| USERS               | /oracle/ora12cdb/oradata/GINESYS/users05.dbf         | 32740        |
| USERS               | /oracle/ora12cdb/oradata/GINESYS/users06.dbf         | 19456        |

- **Solution:** While checking all aspects for database performance improvements, we subsequently discovered that the kernel parameter configuration of the Linux server had a SHMAX size defined at only 31 GB, despite the allocated RAM being 40 GB. Consequently, we increased the SHMAX size( from 31 Gb to 70 Gb) and also fine-tuned the SGA and PGA parameters as follows:

1. SGA_MAX_SIZE: 28 GB
2. SGA_TARGET_SIZE: 28 GB
3. PGA_AGGREGATE_LIMIT: 12 GB
4. PGA_AGGREGATE_TARGET: 8 GB

## Conclusion:

Through a comprehensive analysis of the system configuration, tablespaces, and memory parameters, along with essential adjustments, the issue of slowness in the Datapump Export job for the Client was effectively resolved. The pivotal changes encompassed increasing the SHMAX size and optimizing SGA and PGA memory allocations, resulting in a remarkable improvement in job completion time. Currently, the Datapump export job is completed within 15 to 20 minutes.