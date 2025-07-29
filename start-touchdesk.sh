#!/bin/bash

LOGFILE="/home/b0/armonix/start-touchdesk.log"
TARGET_SSID="EVM_Bizzarri"
VNC_COMMAND="/usr/bin/vncviewer 192.168.5.1"
VNC_COMMAND="/usr/bin/vncviewer -UseLocalCursor=0 -Quality=Medium -FullColor=0 -PreferredEncoding=ZRLE -AutoReconnect=1 -Shared=1 192.168.5.1"
VNC_COMMAND="/usr/bin/remmina -k --enable-fullscreen --enable-extra-hardening -c /home/b0/.local/share/remmina/group_vnc_ketron-evm_192-168-5-1.remmina"
VNC_RETRY=5   # Secondi di attesa tra un tentativo e l'altro

# Lancia la finestra di stato sempre (parte solo una volta!)
#xfce4-terminal --geometry=80x1+410+720 --hide-menubar --hide-scrollbar --title="Armonix Status" --command="/home/b0/armonix/start_immortal.sh" &
/home/b0/armonix/start_immortal.sh &

echo "=== $(date) === Script avviato, log in $LOGFILE" >> $LOGFILE

while true; do
    ssid=$(iwgetid -r)
    if [[ "$ssid" == "$TARGET_SSID" ]]; then
        notify-send "VNC" "Connesso a $TARGET_SSID: provo a lanciare VNC..."
        echo "$(date) - Connesso a $TARGET_SSID, avvio VNC." >> $LOGFILE

        export DISPLAY=:0
        # Lancia VNC e aspetta che termini (anche se va in errore)
        $VNC_COMMAND >> $LOGFILE 2>&1

        # Quando VNC chiude (crash o chiusura manuale), logga e riprova dopo X secondi
        #notify-send "VNC" "Connessione terminata o fallita, riprovo tra $VNC_RETRY secondi..."
        #echo "$(date) - VNC chiuso o fallito, attendo $VNC_RETRY sec e riprovo..." >> $LOGFILE
        #sleep $VNC_RETRY
	exit
    else
        notify-send "VNC" "In attesa di collegarti a $TARGET_SSID..."
        echo "$(date) - SSID attuale: $ssid - attendo rete giusta..." >> $LOGFILE
        sleep $VNC_RETRY
    fi
done
