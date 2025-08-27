# Armonix

Armonix è un piccolo sistema di controllo MIDI pensato per pilotare un Ketron EVM sfruttando una tastiera midi (attualmente ci sono i driver per la Roland Fantom 07 e per la Novation Launchkey 88 [MK3]) e un tastierino USB meccanico. Il progetto è stato testato su Linux Mint 21/24 e può essere adattato con facilità ad altre configurazioni.

## Hardware consigliato

- **Ketron EVM**
- **Roland Fantom 07** (funziona anche con i modelli 06 e 08)
- **Novation Launchkey [MK3]** (testato con il modello 88 tasti)
- Tastierino USB con 12 tasti e 2 encoder
- Laptop Linux touchscreen (ad esempio Linux Mint) con server VNC per la console Ketron
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

## Test manuali

Per verificare il corretto filtraggio dei messaggi della Launchkey, è disponibile
uno script di test manuale:

```bash
python tests/manual_launchkey_filter.py
```

Questo script conferma che solo i messaggi sul canale 1 (canale 0 per mido)
vengono inoltrati al Ketron, mentre gli altri vengono scartati.

## Configurazione del tastierino

Il file `keypad_config.json` definisce la mappatura tra i tasti del tastierino e i messaggi Sysex o Footswitch da inviare al Ketron. È possibile modificare questo file per adattare i comandi alle proprie esigenze.

## Pulsanti CUSTOM con livelli di velocità

È possibile associare ai pad della Launchkey messaggi Sysex differenti a seconda della **velocity** ricevuta. Nel file
`custom_sysex_lookup.py` si definiscono più livelli tramite la chiave `levels`, specificando per ciascuno:

- intervallo di velocity (`min`/`max`)
- nome visualizzato
- colore opzionale del pad
- lista di messaggi Sysex da inviare

Esempio semplificato:

```python
"ARRA_A_BREAK": {
    "levels": [
        {
            "name": "ARRA_A_BREAK",
            "min": 100,
            "max": 127,
            "color": 23,
            "sysex": [ [0x26, 0x79, 0x03, 0x03, 0x7F] ]
        },
        {
            "name": "NOTE_A",
            "min": 1,
            "max": 99,
            "color": 5,
            "sysex": [ [0x26, 0x79, 0x03, 0x03, 0x7F] ]
        }
    ]
}
```

Nel `launchkey_config.json` basta poi mappare il pad con `"type": "CUSTOM"` e il relativo `name`:

```json
{ "note": 112, "channel": 0, "type": "CUSTOM", "name": "ARRA_A_BREAK", "group": 1, "color": 23, "colormode": "static" }
```

Se un livello definisce un colore, questo sovrascrive quello standard; in caso contrario viene usato il comportamento normale
del gruppo o quello indicato nella configurazione.

## Adattamenti ad altri setup

La logica è suddivisa in moduli (gestione dello stato, filtro MIDI, listener per il tastierino), rendendo relativamente semplice l'estensione a strumenti o controller diversi. Basterà modificare le mappature e, se necessario, aggiungere nuovi filtri MIDI.

