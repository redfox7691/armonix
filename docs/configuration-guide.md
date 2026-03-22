# Armonix — Guida alla configurazione

## File di configurazione

| File | Scopo |
|------|-------|
| `armonix.conf` | Impostazioni generali: tastiera master, porte MIDI, Pianoteq, pedali |
| `launchkey_config.json` | Mapping pad e pulsanti del Launchkey (NOTE e CC) |
| `keypad_config.json` | Mapping tasti del tastierino USB |
| `pedals_config.json` | Messaggi MIDI inviati per ogni pedale |

I file vengono cercati nell'ordine:

| Priorità | Percorso | Uso |
|----------|----------|-----|
| 1 | `~/.config/armonix/` | Override personali (più alta priorità) |
| 2 | `/etc/armonix/` | Default installati dal pacchetto |
| 3 | directory sorgente | Fallback per lo sviluppo |

Per personalizzare un file senza modificare i default di sistema:
```bash
mkdir -p ~/.config/armonix
cp /etc/armonix/launchkey_config.json ~/.config/armonix/
# modifica ~/.config/armonix/launchkey_config.json
```

---

## `armonix.conf` — sezioni principali

```ini
[midi]
master          = launchkey          ; oppure: fantom
master_keyword  = Launchkey          ; stringa cercata nei nomi delle porte ALSA
ketron_keyword  = Ketron             ; idem per l'EVM

[pianoteq]
executable      = /home/utente/Pianoteq 9/x86-64bit/Pianoteq 9
port_keyword    = Pianoteq           ; stringa cercata nelle porte ALSA
split_note      = 60                 ; C4 — nota di divisione mano sx/dx
jsonrpc_url     = http://127.0.0.1:8081/jsonrpc

[pedals]
port_keyword    = Arduino            ; stringa cercata nei nomi delle porte ALSA
```

---

## `launchkey_config.json` — tipi di azione

Ogni voce sotto `"NOTE"` o `"CC"` descrive cosa fa un pad o un pulsante.

### Campi comuni

| Campo | Obbligatorio | Descrizione |
|-------|-------------|-------------|
| `note` / `control` | sì | Numero MIDI del pad (NOTE) o del pulsante/potenziometro (CC) |
| `channel` | sì | Canale MIDI (0-based). I pulsanti usano solitamente `15` |
| `type` | sì | Tipo di azione (vedi tabella sotto) |
| `name` | dipende | Nome del comando (richiesto per FOOTSWITCH, CUSTOM, PIANOTEQ_PRESET, ecc.) |
| `color` | no | Colore LED a riposo (0 = spento) |
| `color_pressed` | no | Colore LED durante la pressione |
| `color_on` / `color_off` | no | Per comandi toggle (es. CUSTOM con stato on/off) |
| `colormode` | no | `"static"` (default), `"flash"`, `"pulse"` |
| `group` | no | ID gruppo SELECTOR: accende questo LED, spegne gli altri del gruppo |

### Tipi di azione

#### `FOOTSWITCH`
Invia un footswitch Ketron (dal lookup `footswitch_lookup.py`).
```json
{ "control": 77, "channel": 15, "type": "FOOTSWITCH", "name": "START/STOP" }
```

#### `TABS`
Invia una sequenza SysEx di selezione tab Ketron.
```json
{ "control": 51, "channel": 15, "type": "TABS", "name": "MICRO" }
```

#### `CC`
Rimappa un CC in arrivo su un CC diverso verso il Ketron.
```json
{ "control": 53, "channel": 15, "type": "CC", "newval": 104, "name": "Drum", "lcd_index": 80 }
```
- `newval` — numero CC di destinazione
- `lcd_index` — (opzionale) posizione sul display LCD del Launchkey

#### `CUSTOM`
Esegue un'azione personalizzata definita in `custom_sysex_lookup.py`.
Supporta livelli di velocity con colori diversi.
```json
{ "note": 113, "channel": 0, "type": "CUSTOM", "name": "ARR.B-BREAK", "group": 1, "color": 23, "colormode": "static" }
```

#### `NRPN`
Invia una sequenza NRPN al Ketron (preset microfono, ecc.).
Definito in `keypad_config.json` per il tastierino.
```json
"KEY_A": { "type": "NRPN", "ch": 2, "name": "MICRO_PRESET", "value": "Standard" }
```

#### `MOUSE`
Simula un clic del mouse tramite `xdotool` (richiede la GUI).
```json
{ "note": 112, "channel": 0, "type": "MOUSE", "X": 100, "Y": 50, "group": 1, "color": 23 }
```

---

## Pianoteq — comandi di routing

### `PIANOTEQ` — attiva/disattiva una modalità di routing

Premi per attivare, premi di nuovo per tornare alla modalità solo Ketron (**toggle**).

```json
{ "control": 40, "channel": 15, "type": "PIANOTEQ", "mode": "full", "color_on": 5, "color_off": 0 }
```

| Campo | Valore |
|-------|--------|
| `type` | `"PIANOTEQ"` |
| `mode` | `"full"` / `"full-solo"` / `"split"` / `"split-solo"` |
| `color_on` | colore LED quando la modalità è **attiva** |
| `color_off` | colore LED quando è **disattivata** (default: `0` = spento) |
| `color` | colore fisso alternativo a `color_on` (usato se `color_on` assente) |

**Tabella modalità:**

| Modalità | Mano destra (≥ split_note) | Mano sinistra (< split_note) |
|----------|---------------------------|------------------------------|
| `full` | Pianoteq + Ketron | Pianoteq + Ketron |
| `full-solo` | Solo Pianoteq | Solo Pianoteq |
| `split` | Pianoteq + Ketron | Solo Ketron |
| `split-solo` | Solo Pianoteq | Solo Ketron |

Pianoteq viene avviato automaticamente in modalità headless la prima volta che si attiva una modalità.
Il display LCD del Launchkey mostra la modalità attiva.

### `PIANOTEQ_PRESET` — seleziona uno strumento Pianoteq

Carica un preset Pianoteq tramite JSON-RPC. Il nome deve corrispondere **esattamente**
al nome del preset in Pianoteq.

```json
{ "note": 100, "channel": 0, "type": "PIANOTEQ_PRESET", "preset": "Steinway Model D", "color": 45 }
```

Anche questa può essere assegnata a un CC:
```json
{ "control": 45, "channel": 15, "type": "PIANOTEQ_PRESET", "preset": "Bechstein DG" }
```

---

## Colori LED (Launchkey MK3)

I colori sono numeri da 0 a 127. Valori utili:

| Colore | Valore |
|--------|--------|
| Spento | `0` |
| Rosso scuro | `3` |
| Rosso | `5` |
| Arancione | `9` |
| Giallo | `13` |
| Verde lime | `16` |
| Verde | `21` |
| Ciano | `31` |
| Azzurro | `37` |
| Blu | `45` |
| Viola | `52` |
| Magenta | `55` |
| Rosa | `57` |
| Bianco | `3` (canale 0 = static, canale 1 = flash, canale 2 = pulse) |

> Per trovare il numero esatto di un colore: consultare la **Launchkey MK3 Programmer's Reference Guide**
> (`docs/launchkey_mk3_programmer_s_reference_guide_v1_en.pdf`).

### `colormode`

| Valore | Effetto |
|--------|---------|
| `"static"` | LED fisso (default) |
| `"flash"` | LED lampeggiante |
| `"pulse"` | LED pulsante (respira) |

---

## `SELECTOR_GROUPS` — pulsanti a selezione esclusiva

Permette di avere un gruppo di pad in cui solo quello premuto rimane acceso.
Definiti all'inizio di `launchkey_config.json`:

```json
"SELECTOR_GROUPS": [
  { "group_id": 1, "on_color": 21, "off_color": 0 },
  { "group_id": 2, "on_color": 41, "off_color": 0 }
]
```

Ogni pad del gruppo specifica `"group": <group_id>`. Al press del pad:
- quel pad si accende con `on_color`
- tutti gli altri del gruppo si spengono con `off_color`

---

## `pedals_config.json` — messaggi pedaliera

Configura i messaggi MIDI inviati per ogni pedale (`right`/`center`/`left`)
verso EVM e Pianoteq separatamente.

> **Attenzione:** JSON non supporta valori esadecimali (`0x26`).
> Usare sempre decimali: `0x26` → `38`, `0x7F` → `127`, ecc.

### Tipo `CC`
```json
"right": {
  "evm":      { "type": "CC", "channel": 0, "control": 64 },
  "pianoteq": { "type": "CC", "channel": 0, "control": 64 }
}
```

### Tipo `SYSEX` (pedale on/off)
Byte senza `F0`/`F7` (aggiunti automaticamente):
```json
"center": {
  "evm": {
    "type": "SYSEX",
    "pressed":  [38, 121, 3, 2, 127],
    "released": [38, 121, 3, 2, 0]
  },
  "pianoteq": { "type": "CC", "channel": 0, "control": 66 }
}
```

### Tipo `SYSEX_VALUE` (sustain continuo 0–127)
Il valore del pedale viene aggiunto come ultimo byte al template:
```json
"right": {
  "evm": {
    "type": "SYSEX_VALUE",
    "template": [38, 121, 3, 0]
  }
}
```

---

## `keypad_config.json` — tastierino USB

Mappa i tasti fisici (`KEY_A`…`KEY_T`) a comandi Ketron o Pianoteq.
Supporta gli stessi tipi di `launchkey_config.json` più `PIANOTEQ` e `PIANOTEQ_PRESET`:

```json
"KEY_A": { "type": "NRPN", "ch": 2, "name": "MICRO_PRESET", "value": "Standard" },
"KEY_B": { "type": "FOOTSWITCH", "name": "START/STOP" },
"KEY_C": { "type": "PIANOTEQ", "mode": "split-solo" },
"KEY_D": { "type": "PIANOTEQ_PRESET", "preset": "Steinway Model D" }
```
