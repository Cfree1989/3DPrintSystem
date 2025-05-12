# Maintenance Procedures

This document outlines the maintenance procedures for the 3D Print System.

## Automated Maintenance

The system includes automated maintenance tasks that run on a schedule:

1. **Daily Cleanup (2 AM)**
   - Removes stale uploads (files in UPLOADED status older than 7 days)
   - Archives completed jobs older than 30 days
   - Logs all actions to `/app/logs/maintenance.log`

2. **Disk Space Monitoring (Every 6 hours)**
   - Checks available disk space
   - Alerts if usage exceeds 90% threshold
   - Logs to `/app/logs/disk_space.log`

### Configuration

The maintenance schedule can be modified by editing the cron configuration in `/etc/cron.d/maintenance-cron`.

Current schedule:
```
# Run maintenance tasks daily at 2 AM
0 2 * * * /usr/local/bin/python /app/maintenance/cleanup.py

# Check disk space every 6 hours
0 */6 * * * /usr/local/bin/python -c "from app.maintenance.cleanup import check_disk_space; check_disk_space('/app/uploads')"
```

### Thresholds

Default thresholds can be adjusted in `app/maintenance/cleanup.py`:
- Stale uploads: 7 days
- Completed jobs archival: 30 days
- Disk space warning: 90%

## Manual Maintenance

### Log Rotation

Log files are stored in `/app/logs/`. While the system uses Python's logging module with rotation, it's recommended to:
1. Periodically check log file sizes
2. Archive or delete old log files
3. Ensure sufficient disk space for logs

### Database Maintenance

1. **Backup**
   ```bash
   # Using SQLite backup command
   sqlite3 instance/app.db ".backup '/path/to/backup/app_YYYYMMDD.db'"
   ```

2. **Vacuum**
   ```bash
   # Optimize database and reclaim space
   sqlite3 instance/app.db "VACUUM;"
   ```

### File System Maintenance

1. **Check Upload Directory Structure**
   ```bash
   ls -l /app/uploads/
   ```
   Should show:
   - uploaded/
   - pending/
   - printing/
   - completed/
   - archive/

2. **Manual Cleanup**
   ```bash
   # Remove temporary files
   find /app/uploads -name "*.tmp" -type f -delete
   
   # List large files
   find /app/uploads -type f -size +100M
   ```

### Monitoring

1. **Check Logs**
   ```bash
   # View recent maintenance logs
   tail -f /app/logs/maintenance.log
   
   # View disk space check logs
   tail -f /app/logs/disk_space.log
   ```

2. **Check Disk Usage**
   ```bash
   # Overall disk usage
   df -h /app/uploads
   
   # Usage by directory
   du -sh /app/uploads/*
   ```

3. **Check Database Size**
   ```bash
   ls -lh instance/app.db
   ```

## Troubleshooting

### Common Issues

1. **Disk Space Alerts**
   - Check largest files: `find /app/uploads -type f -exec du -h {} + | sort -rh | head -n 10`
   - Review and archive old completed jobs
   - Consider increasing storage capacity

2. **Stale Files**
   - Manually run cleanup: `python /app/maintenance/cleanup.py`
   - Check job status in database
   - Verify file system permissions

3. **Cron Job Issues**
   - Check cron logs: `grep CRON /var/log/syslog`
   - Verify cron service: `service cron status`
   - Check job schedule: `crontab -l`

### Emergency Procedures

1. **Critical Disk Space**
   ```bash
   # Quick space recovery
   find /app/uploads/completed -type f -mtime +30 -exec mv {} /app/uploads/archive/ \;
   ```

2. **Database Issues**
   ```bash
   # Create emergency backup
   cp instance/app.db instance/app.db.backup
   
   # Check database integrity
   sqlite3 instance/app.db "PRAGMA integrity_check;"
   ```

## Monitoring Stack Integration

The maintenance system can be integrated with external monitoring solutions:

1. **Prometheus Integration**
   - Disk space metrics
   - Job status counts
   - Cleanup operation metrics

2. **Alert Integration**
   - Email notifications
   - Slack/Teams integration
   - SMS alerts for critical issues

## Maintenance Schedule

Recommended periodic maintenance schedule:

- **Daily**
  - Review maintenance logs
  - Check disk space alerts

- **Weekly**
  - Review job status distribution
  - Check database size
  - Verify backup integrity

- **Monthly**
  - Review archived jobs
  - Update maintenance thresholds if needed
  - Check system performance

- **Quarterly**
  - Full system audit
  - Review and update maintenance procedures
  - Capacity planning 