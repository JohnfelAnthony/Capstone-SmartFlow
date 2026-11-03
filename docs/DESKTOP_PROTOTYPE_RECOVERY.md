# Desktop prototype: backups and startup recovery

This document describes the **unfinished Windows desktop prototype**. It is not an installation or release guide. Use synthetic data until packaged-app acceptance is complete.

## Backup before an update

1. Stop simulations, replay and training. Create a backup in **Backup & Restore** and keep a separate copy of the backup bundle in a safe location.
2. Record the application version, the active data location and the backup date. The data location can change after a restore; do not assume that the original folder is still active.
3. Verify the backup before changing application files. A database-only legacy backup does not include models or recordings; use a complete bundle for a full recovery.

The desktop restore action verifies a selected backup, stages a separate data root and attempts to start it. It keeps the previous data root. If starting the restored data fails, it attempts to restart the previous root. A successful verification alone does not activate restored data: use the desktop restore/activation action and confirm the resulting accounts, scenarios and artifacts afterwards. Restore and rollback have been exercised with synthetic data, but not yet in a packaged WebView2 release.

## Pre-start database snapshots

Before each desktop backend startup, SmartFlow saves an integrity-checked SQLite snapshot under the **active data root** in `data/pre-start-snapshots`. This captures committed SQLite write-ahead-log data and is taken before startup migrations. The snapshot contains the database only; it is **not** a complete backup of recordings, models, reviewed observations, evidence or the installation secret.

If startup says the snapshot could not be created, check the path shown in the message, available disk space and folder permissions. The backend stops before running migrations. The prototype currently keeps each pre-start snapshot, so monitor disk usage. There is no automatic retention policy or operator-facing snapshot restoration flow yet.

If startup or migration fails after a snapshot is created, keep the entire active data root, the snapshot and the backend log (`logs/backend.log` under that root). Do not replace a live database or remove its `-wal` and `-shm` files while SmartFlow or another SQLite process is running. Seek technical assistance to make a verified copy and select a compatible full backup. Replacing only the database may leave its references inconsistent with external files.

## Newer database warning

A desktop build with the schema guard refuses a database marked as requiring a newer schema version. Use the newer compatible application or a compatible full backup. A previous executable alone does not roll back the database. Prototype builds made before the guard do not check this marker and must not be used to open newer data.

## Limits

These steps do not prove upgrade, downgrade or disaster-recovery acceptance. Installer behavior, clean-machine operation, native WebView2 interactions and field validation remain unverified. Do not distribute the experimental bundle as a release.
