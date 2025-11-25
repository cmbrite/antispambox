# antispambox

Antispambox is a Dockerized mailbox filter that keeps IMAP inboxes clean by combining two mature engines—SpamAssassin (via ISBG) and Rspamd (via IRSD). It watches your IMAP inbox using IDLE, learns from ham/spam training folders, and automatically files junk so it never reaches your primary mail client.

## Project origins and credit
This project is forked from [rsmuc/antispambox](https://github.com/rsmuc/antispambox). The fork maintains the dual‑engine design (SpamAssassin + Rspamd) and IMAP automation introduced there while refreshing documentation and setup guidance.

## What the container does
- Monitors IMAP inboxes with IDLE/push support so messages are processed immediately.
- Classifies mail with **both** SpamAssassin and Rspamd to balance accuracy and speed.
- Learns from user-provided training folders (`SPAM_train` and `HAM_train`) to continuously improve detection.
- Files detected spam to your `JUNK` (or configured) folder; trains on messages you move into training folders.
- Persists SpamAssassin Bayes data and account configuration via Docker volumes for easy upgrades.

## Requirements
- Docker 20.10+ and Docker Compose
- IMAP credentials for the account you want to protect

## Quick start

### Using Docker Compose (Recommended)

1.  **Configure the `docker-compose.yml` (Optional)**
    The default configuration uses named volumes and exposes Rspamd UI on port 11334.

2.  **Build and Run**
    ```bash
    docker-compose up -d --build
    ```

### Using Portainer

1.  **Create a New Stack**
    -   Name: `antispambox`
    -   Build method: **Repository**
    -   Repository URL: (URL to this repository)
    -   Compose path: `docker-compose.yml`
    -   Click **Deploy the stack**.

2.  **Configure Accounts**
    -   Go to the **Containers** list and find `antispambox`.
    -   Click the **>_ Console** icon (Exec).
    -   Connect as `root` with `/bin/bash`.
    -   Edit the config file:
        ```bash
        nano /root/accounts/imap_accounts.json
        ```
    -   Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

3.  **Apply Configuration**
    -   Restart the container from the Portainer UI.

## Configure accounts
1. **Open a shell in the running container**
   ```bash
docker exec -it antispambox /bin/bash
```
2. **Edit account definitions** in `/root/accounts/imap_accounts.json`.
   - Set IMAP host, port, username, password, and folders for:
     - `INBOX` (watched with IMAP IDLE)
     - `JUNK` (where spam is delivered)
     - `SPAM_train` and `HAM_train` (user-managed training folders)
   - Leave `enabled` as `false` until initial training data is present.
3. **Seed training data**
   - Place at least ~200 ham and ~200 spam messages into the respective training folders. (Copy or move messages in your mail client.)
4. **Enable scanning**
   - Set `enabled` to `true` for each account in `imap_accounts.json` once training data exists.
5. **Restart the container** to pick up the configuration.
   ```bash
docker restart antispambox
```

## How it works in operation
- The container listens for new messages on `INBOX` via IMAP IDLE.
- Each message is evaluated by Rspamd (fast) and SpamAssassin (thorough). Their results are combined to decide whether to move mail to `JUNK`.
- Messages you move to `SPAM_train` or `HAM_train` are periodically fed back into both engines (SpamAssassin Bayes via ISBG; Rspamd via IRSD) to refine future decisions.
- Logs are written to `/var/log/antispambox.log` inside the container; use `docker logs antispambox` or inspect the file from a shell.

## Maintenance tips
- **Check learning stats**
  - SpamAssassin: `sa-learn --dump magic`
  - Rspamd: `spamc stat`
- **Upgrade safely**
  - Because Bayes and account data live on volumes, you can rebuild the image and restart the container without losing training state.
- **Multiple accounts**
  - Add more account objects to `imap_accounts.json` and restart the container; each can use its own training folders.

## Troubleshooting
- **No mail is being moved**: Verify `enabled: true` in `imap_accounts.json` and confirm the container has IMAP connectivity (ports/firewall).
- **Slow delivery**: Ensure training folders contain representative ham/spam samples so both engines can classify accurately; consider tuning IMAP polling interval if not using IDLE.
- **Permission errors on volumes**: Confirm volumes are attached with correct paths (`/var/spamassassin/bayesdb` and `/root/accounts`) and owned by root inside the container.

## License
MIT (see `LICENSE`).
