# Armonix

Armonix è un sistema di controllo MIDI compatto progettato per pilotare un
Ketron EVM tramite una tastiera MIDI e un piccolo tastierino USB.  I driver
sono disponibili per il Roland Fantom 07 e il Novation Launchkey 88 [MK3].
Il progetto è stato testato su Linux Mint 21/24.

## Hardware consigliato

* **Ketron EVM**
* **Roland Fantom 07** (compatibile anche con i modelli 06 e 08)
* **Novation Launchkey [MK3]** (testato con il modello a 88 tasti)
* Tastierino USB con 12 tasti e 2 encoder
* **Pedaliera MIDI DIY** — Studiologic VFP3-10 collegata a un Arduino Leonardo
  (ATmega32U4) via USB.  Invia sustain (CC 64, continuo 0–127), sostenuto
  (CC 66) e sordina/una corda (CC 67) al Ketron EVM e a Pianoteq.
* Laptop Linux con touchscreen e server VNC per la console Ketron
* iPad collegato via **MIDI over BLE** per la visualizzazione dello spartito

## Architettura

Armonix gira come **servizio utente systemd** (`systemctl --user`), sotto
lo stesso utente della sessione grafica.  Questo permette di accedere
al display, lanciare Pianoteq, client VNC e qualsiasi altro software
audio/MIDI senza vincoli di permessi.

I file di configurazione vengono cercati nell'ordine:

| Priorità | Percorso | Uso |
|----------|----------|-----|
| 1 | `~/.config/armonix/` | Override personali (più alta priorità) |
| 2 | `/etc/armonix/` | Default installati dal pacchetto |
| 3 | `/usr/lib/armonix/` | Fallback sorgente |

## Installazione dal pacchetto Debian

```bash
make deb
sudo dpkg -i build/deb/armonix_3.0.4.deb
```

Il pacchetto installa i moduli Python in `/usr/lib/armonix/`, i default di
configurazione in `/etc/armonix/` e abilita automaticamente il servizio utente
`armonix-gui.service` per l'utente corrente.

Per personalizzare la configurazione senza toccare i file di sistema:

```bash
mkdir -p ~/.config/armonix
cp /etc/armonix/armonix.conf ~/.config/armonix/
# modifica ~/.config/armonix/armonix.conf
```

### Gestione del servizio

```bash
systemctl --user status armonix-gui
systemctl --user restart armonix-gui
systemctl --user stop armonix-gui
systemctl --user start armonix-gui

# Log in tempo reale:
journalctl --user -u armonix-gui -f
```

## Sviluppo (senza pacchetto)

```bash
# Prima volta: crea il virtualenv
python3 -m venv venv && source venv/bin/activate
pip install mido python-rtmidi evdev PyQt5

# Avvia il motore headless
python armonix_service.py --verbose

# Avvia con barra LED grafica
python armonix_gui_service.py --gui --verbose

# Flag principali
--master [fantom|launchkey]
--config <percorso>
--disable_realtime_display / --enable_realtime_display
```

I file di configurazione nella directory sorgente hanno precedenza sui file
di sistema durante lo sviluppo.

## Configurazione

Vedere `docs/configuration-guide.md` per la documentazione completa di tutti
i file di configurazione.

## Integrazione Pianoteq

Armonix può instradare le note MIDI verso [Pianoteq](https://www.modartt.com/pianoteq)
in parallelo o in sostituzione del Ketron EVM.  Quattro modalità di routing:

| Modalità | Mano destra (≥ split note) | Mano sinistra (< split note) |
|----------|---------------------------|------------------------------|
| `full` | Pianoteq + Ketron | Pianoteq + Ketron |
| `full-solo` | Solo Pianoteq | Solo Pianoteq |
| `split` | Pianoteq + Ketron | Solo Ketron |
| `split-solo` | Solo Pianoteq | Solo Ketron |

Poiché Armonix gira come utente della sessione grafica, Pianoteq può essere
avviato direttamente senza problemi di permessi.  Configurazione in `armonix.conf`:

```ini
[pianoteq]
executable  = /home/utente/Pianoteq 9/x86-64bit/Pianoteq 9
port_keyword = Pianoteq
split_note  = 60
jsonrpc_url = http://127.0.0.1:8081/jsonrpc
```

Premere lo stesso tasto di modalità una seconda volta disattiva Pianoteq e
torna al routing solo Ketron (toggle).  Il display LCD del Launchkey mostra
sempre la modalità attiva.

## Pedaliera MIDI (DIY)

Armonix supporta una pedaliera a tre pedali basata su **Studiologic VFP3-10**
collegata a un **Arduino Leonardo (ATmega32U4)** via USB MIDI.

Il firmware Arduino invia CC MIDI standard:

| CC | Pedale | Tipo |
|----|--------|------|
| 64 | Destro (sustain) | Continuo 0–127 |
| 66 | Centro (sostenuto) | Binario 0/127 |
| 67 | Sinistro (sordina) | Binario 0/127 |

La pedaliera viene rilevata automaticamente tramite keyword sulla porta ALSA.
Può essere scollegata e ricollegata senza riavviare il servizio.

Configurazione in `armonix.conf`:

```ini
[pedals]
port_keyword = Arduino
```

### Messaggi MIDI per pedale

Il messaggio inviato per ogni pedale e ogni destinazione (EVM / Pianoteq)
è configurabile in `pedals_config.json`.  Tre tipi supportati:

| Tipo | Descrizione |
|------|-------------|
| `CC` | Control Change standard |
| `SYSEX` | SysEx on/off — array `pressed` e `released` (senza F0/F7) |
| `SYSEX_VALUE` | SysEx continuo — template con il valore del pedale come ultimo byte |

> I byte SysEx usano valori **decimali** (JSON non supporta hex):
> `0x26` → `38`, `0x79` → `121`, `0x7F` → `127`, ecc.

```json
{
  "right":  { "evm": { "type": "CC", "control": 64 },
              "pianoteq": { "type": "CC", "control": 64 } },
  "center": { "evm": { "type": "SYSEX",
                        "pressed":  [38, 121, 3, 2, 127],
                        "released": [38, 121, 3, 2, 0] },
              "pianoteq": { "type": "CC", "control": 66 } },
  "left":   { "evm": { "type": "SYSEX",
                        "pressed":  [38, 121, 3, 1, 127],
                        "released": [38, 121, 3, 1, 0] },
              "pianoteq": { "type": "CC", "control": 67 } }
}
```

## Porta MIDI virtuale "Armonix"

Quando una modalità Pianoteq è attiva, Armonix crea automaticamente una porta
MIDI virtuale chiamata **Armonix** (visibile in `aconnect -l`).  Pianoteq deve
essere configurato per connettersi a questa porta invece di connettersi
direttamente alla tastiera master.

**Configurazione una-tantum in Pianoteq:**

1. Avvia Pianoteq con la GUI (senza `--headless`)
2. Vai in **Edit → MIDI Settings**
3. Nella lista dei dispositivi di **input**, seleziona **Armonix** e deseleziona
   tutti gli altri (in particolare la Launchkey/Fantom)
4. Salva — Pianoteq ricorderà la scelta anche in modalità headless

In questo modo le note arrivano a Pianoteq **solo** quando Armonix attiva la
modalità di routing, e i pedali vengono instradati correttamente.

## Avvio automatico all'accensione

Armonix gira come **servizio utente systemd** e si avvia automaticamente dopo
il login grafico.  Su macchine senza tastiera (touchscreen, kiosk) è necessario
abilitare il **login automatico** nel display manager.

### LightDM (Linux Mint / Ubuntu)

```bash
sudo nano /etc/lightdm/lightdm.conf
```

Aggiungere o modificare nella sezione `[Seat:*]`:

```ini
[Seat:*]
autologin-user=b0
autologin-user-timeout=0
```

Poi riavviare:

```bash
sudo systemctl restart lightdm
```

### GDM (Ubuntu con GNOME)

```bash
sudo nano /etc/gdm3/custom.conf
```

```ini
[daemon]
AutomaticLoginEnable=true
AutomaticLogin=b0
```

Una volta effettuato l'autologin, systemd avvierà automaticamente
`armonix-gui.service` e tutti i servizi con `WantedBy=graphical-session.target`.

## Shutdown da touchscreen

Quando il Ketron EVM è **disconnesso**, toccare uno qualsiasi dei cinque LED
nella barra grafica apre un dialogo di conferma:

* **SI** — ferma il servizio e chiude la GUI
* **NO** — chiude il dialogo senza fare nulla

Questo gesto è disabilitato quando il Ketron è connesso.

## Test manuali

```bash
python tests/manual_launchkey_filter.py
```

## Configurazione keypad

`keypad_config.json` definisce la mappatura tra i tasti fisici e i comandi
inviati al Ketron.  Vedere `docs/configuration-guide.md` per tutti i tipi
di azione disponibili.
