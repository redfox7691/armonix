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

## Configurazione del tastierino

Il file `keypad_config.json` definisce la mappatura tra i tasti del tastierino e i messaggi Sysex o Footswitch da inviare al Ketron. È possibile modificare questo file per adattare i comandi alle proprie esigenze.

## Configurazione della Launchkey

Il file `launchkey_config.json` permette di associare i messaggi MIDI generati dalla Novation Launchkey ai comandi del Ketron. La struttura è la seguente:

```
{
  "footswitch": {"<nota>": "<nome FOOTSWITCH>"},
  "tabs": {"<nota>": "<nome TABS>"},
  "program_change": {"MSB,LSB,PC": <azione>}
}
```

Le stringhe devono corrispondere ai simboli definiti in `footswitch_lookup.py` e `tabs_lookup.py`. Le triple `MSB,LSB,PC` identificano un Program Change che il filtro MIDI può tradurre in un'azione specifica.

## Adattamenti ad altri setup

La logica è suddivisa in moduli (gestione dello stato, filtro MIDI, listener per il tastierino), rendendo relativamente semplice l'estensione a strumenti o controller diversi. Basterà modificare le mappature e, se necessario, aggiungere nuovi filtri MIDI.

