# Armonix

Armonix è un piccolo sistema di controllo MIDI pensato per pilotare un Ketron EVM sfruttando una tastiera Roland Fantom 07 e un tastierino USB meccanico. Il progetto è stato testato su Linux Mint 21/24 e può essere adattato con facilità ad altre configurazioni.

## Hardware consigliato

- **Ketron EVM**
- **Roland Fantom 07** (funziona anche con i modelli 06 e 08)
- Tastierino USB con 12 tasti e 2 encoder
- Laptop Linux (ad esempio Linux Mint) con server VNC per la console Ketron
- iPad collegato via **MIDI over BLE** per la visualizzazione degli spartiti

## Installazione

1. Installare Python 3 e creare un ambiente virtuale:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Installare le dipendenze principali:

   ```bash
   pip install mido python-rtmidi PyQt5 evdev
   ```

## Avvio

Il programma principale è `main.py` e mostra una piccola barra LED di stato. Per eseguirlo:

```bash
python main.py --verbose
```

Sono inclusi due script di utilità:

- `start_immortal.sh` esegue `main.py` in loop e riavvia automaticamente il programma in caso di uscita.
- `start-touchdesk.sh` prova a collegarsi via VNC al Ketron EVM quando viene rilevata la rete corretta.

### Opzione `--master`

Il programma accetta l'opzione `--master` per selezionare quale tastiera agisce da controller principale.
Le scelte disponibili sono `fantom` e `launchkey`; il valore predefinito è `fantom`.
Esempio d'uso:

```bash
python main.py --master launchkey
```

## Configurazione del tastierino

Il file `keypad_config.json` definisce la mappatura tra i tasti del tastierino e i messaggi Sysex o Footswitch da inviare al Ketron. È possibile modificare questo file per adattare i comandi alle proprie esigenze.

## Modulo Launchkey

Per utilizzare un controller Novation Launchkey come master, definire le mappature nel file `launchkey_config.json`.
Il file contiene l'associazione tra pad/manopole del Launchkey e i comandi da inviare al Ketron.
Una volta configurato, avviare il programma con:

```bash
python main.py --master launchkey
```

## Adattamenti ad altri setup

La logica è suddivisa in moduli (gestione dello stato, filtro MIDI, listener per il tastierino), rendendo relativamente semplice l'estensione a strumenti o controller diversi. Basterà modificare le mappature e, se necessario, aggiungere nuovi filtri MIDI.

