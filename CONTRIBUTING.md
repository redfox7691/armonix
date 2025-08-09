# Contributing Guidelines — Launchkey MK3 (DAW Mode)

> Questo progetto controlla Novation Launchkey MK3 via MIDI. **Tutto ciò che riguarda LED, display e superficie di controllo deve passare dalla porta _DAW In/Out_** e **richiede il DAW mode attivo**. Su Linux, i nomi delle porte MIDI sono:
>
> - **MIDI normale**: `Launchkey MK3 88 LKMK3 MIDI In`
> - **DAW mode**: `Launchkey MK3 88 LKMK3 DAW In`

---

## 1) Porte MIDI & modalità

- **Usa sempre la porta DAW** (`Launchkey MK3 88 LKMK3 DAW Out` per inviare, `Launchkey MK3 88 LKMK3 DAW In` per ricevere) per controllare LED, display e superficie.
- **Entra/Esci dal DAW mode** all’avvio/chiusura dell’app:
  - **Enable**: `Note On` ch **16**, note **12**, vel **127** (hex `9F 0C 7F`).
  - **Disable**: `Note On` ch **16**, note **12**, vel **0** (hex `9F 0C 00`).
- Opzioni DAW (facoltative):
  - Touch CC: `Note On` ch 16, note 11, vel 127/0.
  - Pot Pickup: `Note On` ch 16, note 10, vel 127/0.

> **Nota mido**: i canali in mido sono 0–15. Quindi ch16 ⇒ `channel=15`.

---

## 2) Regole colore LED (Pads & Pulsanti)

Per **tutti i controlli (tranne Drum mode)** puoi inviare **Note On** _oppure_ **Control Change_** con lo **stesso indice** del controllo. Il **modo colore** è determinato dal canale MIDI:

| Colormode | Canale (umano) | `mido.channel` |
|---|---:|---:|
| `stationary` | 1 | 0 |
| `flashing`   | 2 | 1 |
| `pulsing`    | 3 | 2 |
| `grayscale` (solo controlli CC) | 16 | 15 |

- Il **colore** è nel **Velocity** (Note On) o nel **Value** (CC): range 0–127 (palette Launchkey). 
- **Drum mode (pads)** usa i canali 10/11/12 (mido 9/10/11) per stationary/flashing/pulsing.
- **Pulsanti senza LED** ignorano qualunque colore (vedi lista più sotto). 
- **LED bianchi** mostrano solo **scale di grigi**.

### Convenzioni nel codice

- In configurazione usa `colormode ∈ {stationary|flashing|pulsing}`; mappa a `channel` come sopra.
- Per i pulsanti mappati a **CC** (es. sotto i fader), inviare **Control Change** con lo **stesso CC number**.
- Per i **Pads** in Session/Device/Navigation usa **Note On** con la **nota** indicizzata dal layout corrente.

Esempio (Python/mido):

```python
MODE_TO_CH = {"stationary": 0, "flashing": 1, "pulsing": 2}  # mido 0-based

# NOTE (pad)
outport.send(mido.Message("note_on", channel=MODE_TO_CH[mode], note=pid & 0x7F, velocity=color & 0x7F))

# CC (pulsanti sotto i fader)
outport.send(mido.Message("control_change", channel=MODE_TO_CH[mode], control=pid & 0x7F, value=color & 0x7F))
```

### Pulsanti con LED bianchi (grayscale)
- **Device Lock**
- **Arm/Select** (Launchkey 49/61/88)

### Pulsanti **senza** LED (non si colorano)
- Capture MIDI, Quantise, Click, Undo, Play, Stop, Record, Loop, Track Left/Right, Device Select, Shift

---

## 3) Pad / Pot / Fader — selezione e report dei *mode*

Questi messaggi sono su **ch 16 (mido 15)** come CC.

- **Pad mode**: CC **3** (valori: Drum/Session/Scale Chords/User Chords/Custom/Device Select/Navigation…)
- **Pot mode**: CC **9** (valori: Volume/Device/Pan/SendA/SendB/Custom…)
- **Fader mode** (49/61/88): CC **10** (valori: Volume/Device/SendA/SendB/Custom…)

All’ingresso nel DAW mode i default sono:
- **Pads**: Session
- **Pots**: Pan
- **Faders**: Volume (solo 49/61/88)

Quando l’utente cambia mode dal pannello, la tastiera invia i **report**: intercettali e sincronizza lo stato interno.

---

## 4) Controllo LCD (16×2) via SysEx

- **Header SysEx**: `F0 00 20 29 02 0F ... F7` (Launchkey 25/49/61) — per 88 usare `... 02 12 ...`.
- **Default display** (bassa priorità):
  - Set row: `F0 00 20 29 02 0F 04 <row> <chars…> F7`
  - Clear:   `F0 00 20 29 02 0F 06 F7`
- **Temporary display (5s)** per Pots/Faders:
  - **Parameter name** (riga alta): `F0 00 20 29 02 0F 07 <idx> <chars…> F7`
  - **Parameter value** (riga bassa): `F0 00 20 29 02 0F 08 <idx> <chars…> F7`
- **Indici**:
  - Pots: `0x38–0x3F` (56–63)
  - Faders: `0x50–0x58` (80–88)
- **Charset**: ASCII 0x20–0x7E; supporto parziale ISO-8859-2 con prefisso `0x11`.

> Priorità display: **Menu** > **Temporary** > **Default**. Un messaggio può non apparire finché una priorità più alta è attiva.

---

## 5) Feature MIDI (rapido)

- **Arpeggiatore** (ch 1, CC 110–93): on/off, tipo, rate, ottave, latch, gate, swing, rhythm, mutate, deviate.
- **Scale mode** (ch 16): CC 14 (on/off), CC 15 (tipo), CC 16 (tonica).
- **Velocity curve** (SysEx): target Keys/Pads, curve Soft/Medium/Hard/Fixed.
- **Start-up animation** (SysEx): sequenza di step RGB (0–127) con intervallo base.

---

## 6) Linee guida progetto

1. **Sempre** abilita/disabilita DAW mode all’avvio/uscita.
2. Normalizza `colormode` → canale via mappa (`stationary|flashing|pulsing`).
3. Per pulsanti mappati a CC invia **Control Change**; per pad invia **Note On**.
4. Clamp 0–127 per note/cc/velocity/value; canali mido 0–15.
5. Non tentare di colorare tasti senza LED; per LED bianchi usa valori alti (grigi visibili).
6. Mantieni una **tabella di compatibilità** per i layout pad correnti (Session/Drum/Device Select) se dipendi dalla nota.
7. Aggiungi test manuali: entra DAW, set colore statico su una manciata di pad/pulsanti, verifica flash/pulse con MIDI Clock.

---

## 7) Snippet di inizializzazione consigliato (Python/mido)

```python
# Abilita DAW mode (una volta)
outport.send(mido.Message("note_on", channel=15, note=12, velocity=127))

MODE_TO_CH = {"stationary": 0, "flashing": 1, "pulsing": 2}

for section, ch_map in LAUNCHKEY_FILTERS.items():
    for _, id_map in ch_map.items():
        for pid, meta in id_map.items():
            color = meta.get("color")
            if color is None:
                continue
            mode = meta.get("colormode", "stationary")
            ch   = MODE_TO_CH.get(mode, 0)
            idx  = int(pid) & 0x7F
            val  = max(0, min(int(color), 127))

            if section == "NOTE":
                msg = mido.Message("note_on", channel=ch, note=idx, velocity=val)
            else:  # "CC"
                msg = mido.Message("control_change", channel=ch, control=idx, value=val)
            outport.send(msg)
```

---

## 8) Checklist PR

- [ ] Usi la porta **DAW** (`Launchkey MK3 88 LKMK3 DAW Out`).
- [ ] Entri/esci dal **DAW mode** correttamente.
- [ ] `colormode` → canale mappato come da tabella.
- [ ] Pads via **Note On**, pulsanti CC via **Control Change**.
- [ ] Nessun tentativo di colorare pulsanti senza LED; LED bianchi gestiti come grigi.
- [ ] Display aggiornato via SysEx rispettando priorità.
- [ ] Commenti e costanti esplicativi per indici, canali, palette.

Grazie per contribuire! ✨
