# Installazione di Armonix su macOS (Apple Silicon / Intel)

Questa guida descrive come installare Armonix su un Mac (M1/M2/M3 o Intel)
senza GUI del sistema operativo dedicata (es. Mac Mini come appliance).

> **Nota per gli utenti Linux**: il percorso `make deb` non è in alcun modo
> influenzato da queste istruzioni.  Tutti i file macOS sono in
> `packaging/macos/` e non vengono inclusi nel pacchetto Debian.

---

## Prerequisiti

### Xcode Command Line Tools

```bash
xcode-select --install
```

### Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Su Apple Silicon aggiungere Homebrew al PATH (se non già fatto):

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### Python 3.12+

```bash
brew install python@3.12
```

### Dipendenze Python

```bash
pip3 install mido python-rtmidi PyQt5 pynput
```

> `evdev` **non va installato** su macOS — viene usata automaticamente
> l'alternativa `keypadlistener_macos.py` basata su `pynput`.

Verifica che tutto sia a posto:

```bash
make -f packaging/macos/Makefile.macos check
```

---

## Differenze rispetto a Linux

| Aspetto | Linux | macOS |
|---------|-------|-------|
| Keypad USB | `evdev` (`/dev/input/`) | `pynput` (eventi globali) |
| Config utente | `~/.config/armonix/` | `~/Library/Application Support/armonix/` |
| Config sistema | `/etc/armonix/` | `/Library/Application Support/armonix/` |
| Autoavvio | systemd user service | launchd LaunchAgent |
| Audio/MIDI | ALSA + rtmidi | CoreMIDI + rtmidi (trasparente) |
| Mouse IPC | `xdotool` | non supportato (vedi sotto) |

### Tastierino USB su macOS

Su macOS `pynput` intercetta **tutti** gli eventi tastiera (non solo quelli
del tastierino USB dedicato) e richiede il permesso **Accessibilità**:

1. Aprire **Preferenze di Sistema → Privacy e Sicurezza → Accessibilità**
2. Aggiungere il terminale (o l'app) che esegue Armonix

> Se si usa un tastierino USB dedicato (es. per i comandi Ketron) è
> fortemente consigliato che sia l'**unica** tastiera collegata al Mac
> durante l'utilizzo di Armonix, per evitare che eventi della tastiera
> principale vengano intercettati.

Il parametro `keypad_device` in `armonix.conf` è **ignorato** su macOS.

### Mouse IPC

`mouse_ipc.py` usa `xdotool` che è Linux-only.  Su macOS il server IPC
si avvia ma non esegue azioni (i comandi vengono ignorati con un warning
nel log).  Funzionalità non supportata nella versione corrente.

### Porta MIDI virtuale "Armonix"

Su macOS il backend MIDI è **CoreMIDI** (gestito automaticamente da
`python-rtmidi`).  La porta virtuale "Armonix" appare in tutti i software
MIDI del Mac (GarageBand, Logic, Pianoteq, ecc.) esattamente come su Linux.

---

## Installazione

### Modalità headless (solo motore MIDI, senza GUI)

Consigliata per Mac Mini usato come appliance MIDI senza schermo:

```bash
git clone https://github.com/redfox7691/armonix.git
cd armonix
make -f packaging/macos/Makefile.macos install
```

Questo:
- Copia i moduli Python in `/usr/local/lib/armonix/`
- Installa gli script in `/usr/local/bin/`
- Copia i file di configurazione in `~/Library/Application Support/armonix/`
  (solo se non esistono già — non sovrascrive configurazioni esistenti)
- Installa e avvia il LaunchAgent `com.armonix.engine`

### Modalità GUI (barra LED + VNC)

```bash
make -f packaging/macos/Makefile.macos install-gui
```

> Richiede una sessione grafica attiva.  Per l'avvio automatico senza
> login manuale, abilitare il **login automatico** nelle Preferenze di
> Sistema (vedi sezione Autoavvio).

---

## Configurazione

I file di configurazione si trovano in:

```
~/Library/Application Support/armonix/
├── armonix.conf
├── launchkey_config.json
├── keypad_config.json
└── pedals_config.json
```

La struttura e i parametri sono identici alla versione Linux.
Vedi `docs/configuration-guide.md` per la documentazione completa.

### Percorso eseguibile Pianoteq

Su macOS Pianoteq è tipicamente installato in `/Applications/`:

```ini
[pianoteq]
executable = /Applications/Pianoteq 9/Pianoteq 9.app/Contents/MacOS/Pianoteq 9
options    = --headless
```

Se il percorso contiene spazi, usare un link simbolico:

```bash
ln -s "/Applications/Pianoteq 9/Pianoteq 9.app/Contents/MacOS/Pianoteq 9" \
      ~/bin/pianoteq9
```

```ini
executable = /Users/tuonome/bin/pianoteq9
```

---

## Autoavvio

### Login automatico (per Mac Mini kiosk/appliance)

1. **Preferenze di Sistema → Utenti e Gruppi → Login automatico**
2. Selezionare l'utente e impostare la password

Una volta fatto il login automatico, il LaunchAgent installato da
`make install` si avvia automaticamente ad ogni boot.

### Gestione manuale del servizio

```bash
# Avvia
launchctl load ~/Library/LaunchAgents/com.armonix.engine.plist

# Ferma
launchctl unload ~/Library/LaunchAgents/com.armonix.engine.plist

# Riavvia
launchctl unload ~/Library/LaunchAgents/com.armonix.engine.plist
launchctl load   ~/Library/LaunchAgents/com.armonix.engine.plist

# Log in tempo reale
tail -f /tmp/armonix-engine.log
```

Per la GUI, sostituire `engine` con `gui`.

### Headless senza login (non raccomandato su macOS)

A differenza di Linux (dove `loginctl enable-linger` permette l'avvio
senza login), su macOS i LaunchAgent richiedono una sessione utente attiva.
Per uso headless senza login, valutare un LaunchDaemon di sistema
(più complesso, richiede SIP disabilitato o certificato sviluppatore).
La soluzione più semplice rimane il **login automatico**.

---

## Disinstallazione

```bash
make -f packaging/macos/Makefile.macos uninstall
```

La configurazione in `~/Library/Application Support/armonix/` **non viene
rimossa** automaticamente per preservare le impostazioni personalizzate.
Per rimuoverla completamente:

```bash
rm -rf ~/Library/"Application Support"/armonix
```

---

## Aggiornamento

```bash
cd armonix
git pull
make -f packaging/macos/Makefile.macos uninstall
make -f packaging/macos/Makefile.macos install        # o install-gui
```

I file di configurazione esistenti non vengono sovrascritti.
