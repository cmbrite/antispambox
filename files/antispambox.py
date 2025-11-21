# Open a connection in IDLE mode and wait for notifications from the
# server.

from __future__ import annotations

import json
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from imapclient import IMAPClient
import subprocess


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("Antispambox")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = TimedRotatingFileHandler(
            "/var/log/antispambox.log", when="H", interval=24, backupCount=5
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.addHandler(logging.StreamHandler())
    return logger


logger = configure_logging()


def _require(config: Mapping[str, Any], keys: Iterable[str]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    cursor: Mapping[str, Any] = config
    for key in keys:
        if not isinstance(cursor, Mapping) or key not in cursor:
            raise KeyError(key)
        cursor = cursor[key]  # type: ignore[index]
    if not isinstance(cursor, Mapping):
        raise ValueError("Expected mapping at end of configuration path")
    for field in (
        "server",
        "user",
        "password",
        "junk_folder",
        "inbox_folder",
        "ham_train_folder",
        "spam_train_folder",
        "spam_train_folder2",
    ):
        value = cursor.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Configuration field '{field}' missing or invalid")
        values[field] = value
    return values


def load_account_configuration(path: Path) -> Dict[str, str]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        account = _require(data, ["antispambox", "account"])
        return account
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.error("Unable to load IMAP configuration: %s", exc)
        sys.exit(1)


CONFIG = load_account_configuration(Path("/root/accounts/imap_accounts.json"))
HOST = CONFIG["server"]
USERNAME = CONFIG["user"]
PASSWORD = CONFIG["password"]
JUNK = CONFIG["junk_folder"]
INPUT = CONFIG["inbox_folder"]
HAMTRAIN = CONFIG["ham_train_folder"]
SPAMTRAIN = CONFIG["spam_train_folder"]
SPAMTRAIN2 = CONFIG["spam_train_folder2"]
CACHEPATH = "rspamd"


def scan_spam():
    logger.info("Scanning for SPAM with rspamd")
    rspamd_args = [
        "/usr/local/bin/irsd",
        "--imaphost",
        HOST,
        "--imapuser",
        USERNAME,
        "--imappasswd",
        PASSWORD,
        "--spaminbox",
        JUNK,
        "--imapinbox",
        INPUT,
        "--learnhambox",
        HAMTRAIN,
        "--learnspambox",
        SPAMTRAIN2,
        "--cachepath",
        CACHEPATH,
        "--delete",
        "--expunge",
        "--partialrun",
        "500",
    ]
    run_result = subprocess.run(
        rspamd_args,
        check=False,
        capture_output=True,
        text=True,
    )
    if run_result.stdout:
        logger.info(run_result.stdout.strip())
    if run_result.stderr:
        logger.warning(run_result.stderr.strip())
    if run_result.returncode != 0:
        logger.warning("rspamd scan exited with %s", run_result.returncode)

    logger.info("Scanning for SPAM with spamassassin")
    spamassassin_args = [
        "/usr/local/bin/isbg",
        "--spamc",
        "--imaphost",
        HOST,
        "--imapuser",
        USERNAME,
        "--imappasswd",
        PASSWORD,
        "--spaminbox",
        JUNK,
        "--imapinbox",
        INPUT,
        "--learnhambox",
        HAMTRAIN,
        "--learnspambox",
        SPAMTRAIN,
        "--delete",
        "--expunge",
        "--partialrun",
        "500",
    ]
    run_result = subprocess.run(
        spamassassin_args,
        check=False,
        capture_output=True,
        text=True,
    )
    if run_result.stdout:
        logger.info(run_result.stdout.strip())
    if run_result.stderr:
        logger.warning(run_result.stderr.strip())
    if run_result.returncode != 0:
        logger.warning("spamassassin scan exited with %s", run_result.returncode)


def login():
    # login to server
    while True:
        try:
            server = IMAPClient(HOST)
            server.login(USERNAME, PASSWORD)
            server.select_folder('INBOX')
            # Start IDLE mode
            server.idle()
            logger.info("Connection is now in IDLE mode")
        except Exception as e:
            logger.warning("Failed to connect - try again: %s", e)
            continue
        return server


def logoff(server):
    server.idle_done()
    logger.info("\nIDLE mode done")
    server.logout()


def pushing(server):
    """run IMAP idle until an exception (like no response) happens"""
    count = 0
    while True:
        try:
            # Wait for up to 30 seconds for an IDLE response
            responses = server.idle_check(timeout=29)

            if responses:
                logger.info(responses)
                
            else:
                logger.info("Response: nothing")
                count = count + 1
             
            if count > 5:
                logger.info("No responses from Server - Scan for Spam, then Restart")
                scan_spam()
                count = 0
                raise Exception("No response")

            for response in responses:
                count = 0
                if response[1].decode('UTF-8') == "RECENT" or response[1].decode('UTF-8') == "EXISTS":
                    scan_spam()

        except KeyboardInterrupt:
            break

        except Exception as e:
            logger.warning("Push error: %s", e)
            count = 0
            break


def main():
    server = None
    scan_spam()

    while True:
        try:
            logger.info("Login to IMAP")
            server = login()
            logger.info("Start IAMP IDLE")
            pushing(server)
            logger.info("Logoff from IMAP")
            logoff(server)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.warning("Exception in Mainloop: %s", e)

    if server is not None:
        try:
            logoff(server)
        except Exception:
            logger.info("Pushtest exited before server connection established")
    logger.info("Pushtest exited")


if __name__ == "__main__":
    main()
