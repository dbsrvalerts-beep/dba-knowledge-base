# 1. Cloud Database Management Tasks

### Introduction

This document provides a detailed explanation of the tasks performed for managing Cloud databases. The DBA team plays a crucial role in ensuring the smooth operation of these databases.

The tasks listed below cover various aspects of database management, configuration, monitoring, optimization and on-demand.

---

### RMAN Configuration for Newly Added Cloud Database

For any newly added Cloud database, the Database team performs RMAN configuration to set up and manage the backup and recovery process. This includes defining RMAN backup policies and setting up the database in archive mode to obtain minimum data loss.

---

### GDBA Database

GDBA is a centralized and resilient database, functioning as a grid that proficiently manages to link with all cloud databases.

- Within GDBA, comprehensive data from all databases is meticulously stored, promoting optimal efficiency, scalability, and a unified approach to data management.
- The DBA team creates procedures and views in the GDBA database to facilitate data gathering and reporting for all Cloud databases efficiently.
- Information of all cloud databases is recorded in the GDBA database on a daily basis.

These records are gathered using various PROCEDURES that execute on their scheduled time using a database link.

---

### Gathering Information of All Cloud Databases into GDBA

This task involves collecting information about:

- FULL DATABASE BACKUP
- TABLESPACE
- SEGMENTS INFORMATION
- MATERIALIZED VIEW
- ARCHIVE GENERATION
- HIGHWATER_MARK
- SPECIFIC SEGMENT SIZE INFO
- GATHER INFORMATION OF TABLE COUNT RECORDS for the BA Team (1st Date of every month)
- GATHER INFORMATION OF RESTORE_DRILL ACTIVITIES
- STATISTICS GATHER INFORMATION
- LONG RUNNING SESSIONS INFORMATION
- INSTANCE PARAMETER INFORMATION
- REDO LOG STATUS INFORMATION
- SOFTWARE VERSION INFORMATION
- DISK UTILIZATION INFORMATION
---

### Monitoring Information for All Cloud Databases

The DBA team monitors full database backup information daily for all Cloud databases to ensure that backups are completed successfully and on schedule. In case of any backup failure or delay, the corrective measure steps include investigating backup failures and informing the Cloud Team about the status and resolution.

- The DBA team monitors the tablespace usage daily across all Cloud databases. The cloud team is notified in case any tablespace is approaching its storage limits or requires resizing to accommodate data growth. To manage data growth, the DBA team periodically adds data files to tablespaces that are running out of space. A proper retention period is set up to avoid any performance issues.

- The DBA team monitors the overall size growth of each Cloud database to plan for capacity upgrades or optimizations as needed.

- The DBA team monitors the size and growth of segments in all Cloud databases. It alerts the team of any abnormal growth or space-related issues.

- The DBA team monitors materialized views of all Cloud databases, including their refresh schedules and last refresh times. If any materialized views have outdated refresh times or fail to refresh, corrective measures and steps have been taken.

- The DBA team monitors the hourly/daily archive generation of all cloud databases to identify any spikes or abnormal patterns. If high archive generation is observed, they investigate the root cause and take necessary actions to resolve the issue.

- The DBA team monitors the HIGHWATERMARK information for each Cloud database. The HIGHWATERMARK represents the highest extent used within a tablespace, and it is critical for managing space allocation and growth. High watermark info is generated twice a month.

- Collecting the record counts for specific tables (`INVITEM`, `INVSTOCK`, `PSITE_POSBILLITEM`, `PSITE_POSBILL`, `AUD_EVENTS`, `SALCSMAIN`, `EX_REPORT_MASTER`) from each Cloud database and storing them in the GDBA database. The table count is generated once a month. The report is then provided to the BA team for analysis.

- The DBA team monitors specific segments that require clearing (deletion, truncation, etc.) from each Cloud database. The data is stored in the GDBA database for further action.

- The DBA team stores and monitors information of the restore drill activities of all cloud databases on the GDBA database to simulate database recovery scenarios. All cloud databases are restored twice a month. In case any issues are encountered during the restore drill activities, the DBA team takes appropriate measures to resolve them promptly and informs the Cloud team of the outcomes.

- The DBA team monitors (as per required) long-running queries of cloud databases that may impact performance. They identify problematic queries and work with the respective teams to optimize them.

- The DBA team monitors (as per required) database locking in Cloud databases to identify any blocking or contention issues and take corrective actions to resolve such issues and optimize database concurrency.

The DBA team gathers full database statistics for all cloud databases, once every month.

The DBA team gathers statistics for highly modified tables on regular basis. (as soon as stats for highly modified tables are outdated).

---

### Database Cleanup Activities

To manage database space efficiently, the DBA team identifies and performs data deletion activities on various segments, unused or obsolete data is removed to free up storage space both at the database level and the operating system level.

Removing events of extinct sites from all cloud databases to optimize performance at the Application level.

Performing cleanup activity for GINARCHIVE schema's junk/obsolete tables.

---

### Performing Point-in-Time (PITR) and Restore Activity

As per requirement the DBA team performs point-in-time recovery and restore activities for various clients to validate the recoverability of their databases.

---

### Crash Recovery Activity

In case of database crashes, the DBA team performs crash recovery activities to restore databases to the last consistent state.

---

### Share Database Monthly Report to Cloud Team

The DBA team prepares and shares report on database size growth and object growth, Backup Time taken and Backup Size Info with the Cloud Team to assist with capacity planning and resource allocation.

---

### Share Other Info to Cloud Team

As part of regular updates and communication, the DBA team shares relevant information, insights, and recommendations with the Cloud Team to ensure transparency and collaboration.

---

### Other Miscellaneous Cloud Database Activities

Apart from the regular tasks, the DBA team performs other activities as needed, such as setting the NOARCHIVE database mode, handling tenant code changes and addressing any specific database-related requests from the Cloud Team. These activities ensure Cloud databases' smooth operation and alignment with changing business needs.

---

### On-Demand

- The DBA team promptly addresses any reported slowness issues, recognizing the imperative of a responsive database system to restore optimal performance.

- The DBA team also oversees the migration activities of on-premises databases to the cloud environment.

- Tuning Oracle parameters to match performance with the application.

- The DBA team actively addresses reported slowness issues for Applications. The team meticulously examines the application's performance to identify underlying issues that might be contributing to the reported slowdown by the cloud team or R&D team. This approach ensures that any performance concerns are promptly addressed, maintaining the application's optimal functionality and meeting the high standards expected by both the Cloud and R&D teams.

---

### Conclusion

This document outlines the various tasks performed by the DBA team to manage, configure, monitor, and optimize Cloud databases. By implementing these tasks, the team ensures the reliability, availability, and performance of Cloud databases while proactively resolving any issues that may arise. The centralization of information in the GDBA database facilitates efficient management and reporting, supporting the Cloud Team in delivering a reliable and robust cloud database service.
