import sys
import argparse
import time

from statemanager import StateManager

def main():
    parser = argparse.ArgumentParser(description="ArmonixNG - MIDI System Control")
    parser.add_argument('--verbose', action='store_true', help='Abilita il logging dettagliato')
    parser.add_argument(
        '--master',
        choices=['fantom', 'launchkey'],
        default='fantom',
        help='Specifica la master keyboard collegata'
    )
    parser.add_argument(
        '--disable_realtime_display',
        action='store_true',
        help='Disabilita la visualizzazione dei messaggi di controllo in tempo reale'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Esegui senza GUI e senza dipendenze PyQt5'
    )
    args = parser.parse_args()

    if args.headless:
        # Lo StateManager gestisce tutto lo stato, i led, e il logging
        state_manager = StateManager(
            verbose=args.verbose,
            master=args.master,
            disable_realtime_display=args.disable_realtime_display,
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        from PyQt5 import QtWidgets
        from ledbar import LedBar

        app = QtWidgets.QApplication(sys.argv)
        state_manager = StateManager(
            verbose=args.verbose,
            master=args.master,
            disable_realtime_display=args.disable_realtime_display,
        )
        led_bar = LedBar(states_getter=state_manager.get_led_states)
        state_manager.set_ledbar(led_bar)
        led_bar.set_state_manager(state_manager)
        sys.exit(app.exec_())

if __name__ == '__main__':
    main()
