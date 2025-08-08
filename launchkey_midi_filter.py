import mido


def filter_and_translate_launchkey_msg(msg, ketron_outport, state_manager, armonix_enabled=True, state="ready", verbose=False):
    if armonix_enabled:
        ketron_outport.send(msg)
        if verbose:
            print(f"[LAUNCHKEY-FILTER] Inviato inalterato: {msg}")
    elif verbose:
        print(f"[LAUNCHKEY-FILTER] Bloccato: {msg}")


def filter_and_translate_launchkey_daw_msg(msg, daw_outport, state_manager, verbose=False):
    """Filtro dedicato per la porta DAW del Launchkey."""
    if verbose:
        print(f"[LAUNCHKEY-DAW-FILTER] Ricevuto: {msg}")
