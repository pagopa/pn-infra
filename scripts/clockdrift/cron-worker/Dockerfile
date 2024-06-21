FROM public.ecr.aws/docker/library/alpine:latest@sha256:b89d9c93e9ed3597455c90a0b88a8bbb5cb7188438f70953fede212a0c4394e0

# Upgrade and install the required packages
RUN apk update && apk add jq aws-cli

# Add our metrics script into a proper destination directory
RUN mkdir -p /opt/customscripts
COPY clockcheck.sh /opt/customscripts
RUN chmod +x /opt/customscripts/clockcheck.sh

# bash-4.4# crond --help
# BusyBox v1.35.0 (2022-11-19 10:13:10 UTC) multi-call binary.
# Usage: crond -fbS -l N -d N -L LOGFILE -c DIR
#        -f      Foreground
#        -b      Background (default)
#        -S      Log to syslog (default)
#        -l N    Set log level. Most verbose 0, default 8
#        -d N    Set log level, log to stderr
#        -L FILE Log to FILE
#        -c DIR  Cron dir. Default:/var/spool/cron/crontabs

# Setup our cron job
RUN crontab -l | { cat ; echo "*/10 * * * * /opt/customscripts/clockcheck.sh" ; } | crontab -

# Run cron daemon in foreground with loglevel 2
CMD [ "crond", "-l", "2", "-f" ]
