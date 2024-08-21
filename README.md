# backuper
Simple wrapper around `restic` with `systemd` services to run backups and check regularly.

## Installation
1. Clone the repo
2. link systemd services
```
systemctl link $PWD/check-backup\@.timer
systemctl link $PWD/check-backup\@.service
systemctl link $PWD/backup\@.service
systemctl link $PWD/backup\@.timer
```
3. Configure (see output of `./backuper.py`)
4. If you want to use `check-backup`, configure `matrix-commander`
4. Enable systemd services for each target repo as `systemctl enable backup@<REPO>.timer` and `systemctl enable check-backup@<REPO>.timer`
