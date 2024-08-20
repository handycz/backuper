#!/usr/bin/env python

import json
import logging
import os
import subprocess
import sys

from datetime import datetime, timedelta, timezone
from pathlib import Path

MIN_SNAPSHOTS_PER_WEEK = 5

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

def usage():
    file = sys.argv[0]
    print(f"""Usage: {file} [OPERATION] [REPO_CONFIG_FILE] [PASSWORD_FILE] [SOURCE_CONFIG_FILE?]
Backs up the files given by the source configuration file to the repository given by the repo configuration file. Password file contains repo password.

Operations:
    backup              Creates a snapshot. Requires 3 more arguments: repo config, password file, source config.
    init                Initializes the repository. Requires 2 more arguments: repo config, password file.
    verify              Verifies the repo consistency and checks if there is at least 5 snapshots taken last week. Requires 2 arguments: repo config, password file.
    compile-dotenv      Prints the ENV variables from the repo config file in format that can be `source`d. Requires 1 argument: repo config.

Example:
    {file} /path/to/source/config.json /path/to/repo/config.json /path/to/password/file

"""
          
"""Source Config File:
{
    "dirs": [
        "/path/to/dir1",
        "/path/to/dir2",
        ...
    ],
    "exclude": [
        "/path/to/dir1/exclude1",
        "/path/to/dir1/exclude2",
        ...
    ]
}
          
Repo Config File:
{
    "url": "s3:s3.amazonaws.com/bucket_name",
    "env": {
        "AWS_ACCESS_KEY_ID": "id",
        "AWS_SECRET_ACCESS_KEY": "key"
    }
}
          
Password File:
password
""")

def _execute(command: str, repo_config, capture_output: bool = False) -> str:
    env = os.environ | repo_config.get("env", {})

    print("Running: ", command)
    result = subprocess.run(
        command,
        shell=True,
        env=env,
        check=True,
        capture_output=capture_output
    )

    if not capture_output:
        return ""

    if result.stdout:
        return result.stdout.decode("utf8")

    return ""


def backup(repo: Path, pwfile: Path, src: Path):
    logger.info(f"Reading config: {src}")
    src_config = json.loads(src.read_text())

    logger.info(f"Reading config: {repo}")
    repo_config = json.loads(repo.read_text())

    logger.info(f"Backing up files to {repo_config['url']}")
    for dir in src_config["dirs"]:
        logger.info(f"- {dir}")
    
    dirs = " ".join(src_config["dirs"])
    excludes = " ".join([f"--exclude {ex}" for ex in src_config.get("exclude", [])])

    cmd = f"restic -r {repo_config['url']} backup {dirs} {excludes} --password-file {pwfile} --tag autobackup"
    _execute(cmd, repo_config)


def init(repo: Path, pwfile: Path):
    logger.info(f"Reading config: {repo}")
    repo_config = json.loads(repo.read_text())

    cmd = f"restic -r {repo_config['url']} init --password-file {pwfile}"
    _execute(cmd, repo_config)


def verify(repo: Path, pwfile: Path):
    logger.info(f"Reading config: {repo}")
    repo_config = json.loads(repo.read_text())

    cmd = f"restic -r {repo_config['url']} check --read-data-subset=5% --password-file {pwfile}"
    
    try:
        _execute(cmd, repo_config)
        logger.info("Repo consistency OK")
    except:
        logger.error("Repo consistency check failed")
        return
    

    cmd = f"restic -r {repo_config['url']} snapshots --group-by path --password-file {pwfile} --tag autobackup --json"
    output = _execute(cmd, repo_config, capture_output=True)
    groups = json.loads(output)

    backups_ok = True

    for group in groups:
        logger.info(f"Group: {' '.join(group['group_key']['paths'])}")

        timestamps = [datetime.fromisoformat(snapshot["time"]) for snapshot in group["snapshots"]]
        last_week_snapshots = [timestamp for timestamp in timestamps if datetime.now(timezone.utc) - timestamp < timedelta(days=7)]
        logger.info(f"Last week snapshot count: {len(last_week_snapshots)}")
        if len(last_week_snapshots) < MIN_SNAPSHOTS_PER_WEEK:
            logger.error("Insufficient number of snapshots!")
            backups_ok = False

    if not backups_ok:
        logger.info("Not enough snapshots taken!")
        sys.exit(1)


def compile_dotenv(repo: Path):
    logger.info(f"Reading config: {repo}")
    repo_config = json.loads(repo.read_text())

    logger.info(f"In bash, you can source by running: source <(./backups.py compile-dotenv {str(repo)})")
    for name, value in repo_config.get("env", {}).items():
        print(f"export {name}={value}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        usage()
        sys.exit(1)
    elif sys.argv[1] == "backup":
        assert len(sys.argv) == 5, "`backup` needs 3 arguments"
        backup(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    elif sys.argv[1] == "init":
        assert len(sys.argv) == 4, "`init` needs 2 arguments"
        init(Path(sys.argv[2]), Path(sys.argv[3]))
    elif sys.argv[1] == "verify":
        assert len(sys.argv) == 4, "`verify` needs 2 arguments"
        verify(Path(sys.argv[2]), Path(sys.argv[3]))
    elif sys.argv[1] == "compile-dotenv": # For debugging
        assert len(sys.argv) == 3, "`compile-dotenv` needs 1 argument"
        compile_dotenv(Path(sys.argv[2]))
    else:
        print(f"Unknown argument: {sys.argv[1]}")
        sys.exit(1)
