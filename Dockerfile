FROM debian:bookworm-slim

# shell to start from Kitematic
ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash
ENV PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /root

COPY files/* /root/
COPY files/rspamd_config/* /root/rspamd_config/

# install software
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      cron \
      ca-certificates \
      gnupg \
      nano \
      python3 \
      python3-pip \
      python3-setuptools \
      rsyslog \
      spamassassin \
      spamc \
      unzip \
      wget \
      logrotate \
      unattended-upgrades && \


# install dependencies for pushtest
    python3 -m pip install --no-cache-dir --upgrade imapclient isbg && \


# download and install irsd
        cd /root && \
    wget -O irsd-master.zip https://codeberg.org/antispambox/IRSD/archive/master.zip && \
    unzip irsd-master.zip && \
    cd irsd && \
    pip install . && \
    cd .. ; \
    rm -Rf /root/irsd ; \
    rm /root/irsd-master.zip ; \


############################
# configure software
############################

# create folders
    mkdir /root/accounts ; \
    cd /root && \
#
# fix permissions
    chown -R debian-spamd:mail /var/spamassassin ; \
#
# configure cron configuration
    crontab /root/cron_configuration && rm /root/cron_configuration ; \
#
# copy logrotate configuration
    mv mailreport_logrotate /etc/logrotate.d/mailreport_logrotate ; \
#
# configure spamassassin
    sed -i 's/ENABLED=0/ENABLED=1/' /etc/default/spamassassin ; \
    sed -i 's/CRON=0/CRON=1/' /etc/default/spamassassin ; \
    sed -i 's/^OPTIONS=".*"/OPTIONS="--allow-tell --max-children 5 --helper-home-dir -u debian-spamd -x --virtual-config-dir=\/var\/spamassassin -s mail"/' /etc/default/spamassassin ; \
    echo "bayes_path /var/spamassassin/bayesdb/bayes" >> /etc/spamassassin/local.cf ; \
    cp /root/spamassassin_user_prefs /etc/spamassassin/user_prefs.cf ;\
#
# configure OS base
    echo "alias logger='/usr/bin/logger -e'" >> /etc/bash.bashrc ; \
    echo "LANG=en_US.UTF-8" > /etc/default/locale ; \
    unlink /etc/localtime ; \
    ln -s /usr/share/zoneinfo/Europe/Berlin /etc/localtime ; \
    unlink /etc/timezone ; \
    ln -s /usr/share/zoneinfo/Europe/Berlin /etc/timezone ; \
#
# install rspamd
    CODENAME=`lsb_release -c -s` ;\
    wget -O- https://rspamd.com/apt-stable/gpg.key | gpg --dearmor > /usr/share/keyrings/rspamd.gpg ;\
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/rspamd.gpg] http://rspamd.com/apt-stable/ $CODENAME main" > /etc/apt/sources.list.d/rspamd.list ;\
    echo "deb-src [arch=amd64 signed-by=/usr/share/keyrings/rspamd.gpg] http://rspamd.com/apt-stable/ $CODENAME main" >> /etc/apt/sources.list.d/rspamd.list ;\
    apt-get update ;\
    apt-get --no-install-recommends install -y rspamd redis-server ;\
    # configure rspamd
    #echo "backend = 'redis'" > /etc/rspamd/local.d/classifier-bayes.conf ;\
    #echo "new_schema = true;" >> /etc/rspamd/local.d/classifier-bayes.conf ;\
    #echo "expire = 8640000;" >> /etc/rspamd/local.d/classifier-bayes.conf ;\
    #echo "write_servers = 'localhost';" > /etc/rspamd/local.d/redis.conf ;\
    #echo "read_servers = 'localhost';" >> /etc/rspamd/local.d/redis.conf ;\
    sed -i 's+/var/lib/redis+/var/spamassassin/bayesdb+' /etc/redis/redis.conf ;\
    cp /root/rspamd_config/* /etc/rspamd/local.d/ ;\
    rm -r /root/rspamd_config ;\
#
# remove tools we don't need anymore
    apt-get remove -y wget python3-pip python3-setuptools unzip && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


# volumes
VOLUME /var/spamassassin/bayesdb
VOLUME /root/accounts

# EXPOSE 80/tcp
# EXPOSE 11334/tcp

CMD python3 /root/startup.py && tail -n 0 -F /var/log/*.log
