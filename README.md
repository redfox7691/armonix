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

## Configurazione della Launchkey

Il file `launchkey_config.json` controlla pad, pulsanti e potenziometri della Launchkey. È un oggetto JSON con tre sezioni principali:

- `SELECTOR_GROUPS`: definisce gruppi di selezione esclusiva con gli ID di gruppo e i colori da applicare quando un membro è attivo (`on_color`) o inattivo (`off_color`).
- `NOTE`: elenco di regole per i pad. Ogni voce specifica la nota, il canale e l'azione da inviare al Ketron.
- `CC`: elenco di regole per pulsanti e controlli che inviano Control Change.

Le regole nelle sezioni `NOTE` e `CC` possono includere il campo opzionale `group` per indicare l'appartenenza a uno dei gruppi definiti in `SELECTOR_GROUPS`. Quando un elemento di un gruppo viene attivato, il suo LED assume il colore `on_color` mentre gli altri membri vengono aggiornati con `off_color`.

Il campo `tabs_led` collega il LED di un controllo allo stato di un TAB del Ketron e accetta uno dei nomi presenti in `tabs_lookup.py` (ad esempio `MICRO` o `VOICE1`). Quando il TAB è disattivato viene usato `tabs_led_off_color`. L'opzione `colormode` determina l'animazione del LED e può essere `static`, `flashing` o `pulsing`.

## Adattamenti ad altri setup

La logica è suddivisa in moduli (gestione dello stato, filtro MIDI, listener per il tastierino), rendendo relativamente semplice l'estensione a strumenti o controller diversi. Basterà modificare le mappature e, se necessario, aggiungere nuovi filtri MIDI.

