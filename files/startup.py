from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from shutil import copyfile


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AntispamboxStartup")


def cleanup_file(filename):
    """If file exists, delete it"""
    if os.path.isfile(filename):
        os.remove(filename)
    else:
        logger.warning("%s does not exist", filename)


def copy_file_if_not_exists(src, dest):
    """Copy the file if it does not exist at the destination"""
    if os.path.isfile(dest):
        logger.info("%s does already exist - do nothing", dest)
    else:
        copyfile(src, dest)
        logger.info("%s copied", dest)


def start_service(servicename):
    """Start a Linux service"""
    logger.info("startup service %s", servicename)
    result = subprocess.run(
        ['/usr/sbin/service', servicename, 'start'],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("startup of service %s failed: %s", servicename, result.stderr)


def check_imap_configuration():
    """ check if the IMAP account has already been configured"""
    try:
        config = Path("/root/accounts/imap_accounts.json").read_text(encoding="utf-8")
        datastore = json.loads(config)
        enabled = datastore.get("antispambox", {}).get("enabled")
        host = datastore.get("antispambox", {}).get("account", {}).get("server")
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("ERROR: was not able to read imap_accounts.json: %s", exc)
        sys.exit(1)

    if enabled != "True":
        logger.error("ERROR: Antispambox configuration is not set to enabled - end the service")
        sys.exit(1)

    if not host or host == "imap.example.net":
        logger.error(
            "ERROR: no accounts in imap_accounts.json configured - please configure and restart"
        )
        sys.exit(1)


def fix_permissions():
    """ fix the permissions of the bayes folders"""
    for command in (
        ['chown', '-R', 'debian-spamd:mail', '/var/spamassassin'],
        ['chmod', 'a+wr', '/var/spamassassin', '-R'],
    ):
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error(
                "%s failed: %s", " ".join(command), result.stderr or result.stdout
            )


def download_spamassassin_rules():
    """download the spamassassin rules"""
    for args in (
        ['/usr/bin/sa-update', '--no-gpg', '-v', '--channelfile', '/root/sa-channels'],
        ['/usr/bin/sa-update', '--no-gpg', '-v'],
    ):
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if result.returncode not in (0, 1):
            logger.error("ERROR: sa-update failed: %s", result.stderr or result.stdout)


def start_imap_idle():
    result = subprocess.run(
        ['python3', '/root/antispambox.py'],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error(
            "ERROR: IMAPIDLE / PUSH / antispambox failed: %s",
            result.stderr or result.stdout,
        )


logger.info(" ******* STARTUP ANTISPAMBOX ******* ")

logger.info(" *** delete lock files if still existing")
cleanup_file("/var/spamassassin/scan_lock")
cleanup_file("/root/.cache/isbg/lock")
cleanup_file("/root/.cache/irsd/lock")

logger.info(" *** copy imap_accounts.json file")
copy_file_if_not_exists("/root/imap_accounts.json", "/root/accounts/imap_accounts.json")

logger.info(" *** fixing permissions")
fix_permissions()

logger.info(" *** updating spamassassin rules")
download_spamassassin_rules()

logger.info(" *** start the services")
start_service("rsyslog")
start_service("redis-server")
start_service("rspamd")
start_service("spamassassin")
start_service("cron")

logger.info(" *** check if the imap account configuration is available and active")
check_imap_configuration()

logger.info(" *** start of IMAPIDLE / PUSH")
start_imap_idle()
