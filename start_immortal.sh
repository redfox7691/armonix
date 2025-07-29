#!/bin/bash
LOG="/home/b0/armonix/armonix_watchdog.log"
while true; do
    flock -n /tmp/armonix.lock ~/armonix/venv/bin/python ~/armonix/main.py
    EXITCODE=$?
    echo "$(date) - Armonix terminato (exit $EXITCODE). Riparto tra 3 secondi." >> $LOG
    sleep 3
done
