import sys
import argparse
from PyQt5 import QtWidgets
from ledbar import LedBar
from statemanager import StateManager

def main():
    parser = argparse.ArgumentParser(description="ArmonixNG - MIDI System Control")
    parser.add_argument('--verbose', action='store_true', help='Abilita il logging dettagliato')
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)

    # Lo StateManager gestisce tutto lo stato, i led, e il logging
    state_manager = StateManager(verbose=args.verbose)
    led_bar = LedBar(states_getter=state_manager.get_led_states)
    state_manager.set_ledbar(led_bar)
    led_bar.set_state_manager(state_manager)

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
