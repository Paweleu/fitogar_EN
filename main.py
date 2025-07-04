import os
import sys
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager

# --- FiToGar ENGLISH VERSION ---
# Import all screens of your application
try:
    from start_screen import StartScreen
    from config_screen import ConfigScreen
    from scan_screen import ScanScreen
    from weigh_screen import WeighScreen
except ImportError as e:
    print(f"Import error: {e}. Make sure all screen files (start, config, scan, weigh) are in the main folder.")
    sys.exit()


class FiToGarApp(App):
    """
    Main application class (EN version).
    """
    def build(self):
        """
        Builds the user interface, loading all screens into the manager.
        """
        # On iOS do not set Window.size
        if not (os.environ.get('KIVY_BUILD') == 'ios' or os.environ.get('IOS') == '1'):
            Window.size = (600, 900)
        self.icon = 'assets/images/ico_mini.png'
        self.title = "FiToGar v.1.0.0 EN  pawel.eu"
        
        # Set up the screen manager
        sm = ScreenManager()
        sm.add_widget(StartScreen(name='start'))
        sm.add_widget(ConfigScreen(name='config'))
        sm.add_widget(ScanScreen(name='scan'))
        sm.add_widget(WeighScreen(name='weigh'))
        
        sm.current = 'start'
        return sm

    def on_stop(self):
        """
        Method called when closing the application.
        """
        # Usuń obsługę asyncio na iOS, bo nie jest wspierane
        pass

if __name__ == '__main__':
    # Na iOS używaj klasycznego run(), nie async_run
    FiToGarApp().run()
