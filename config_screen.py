import os
import configparser
from pathlib import Path
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.uix.switch import Switch  # Dodaj import dla Switch

try:
    from dekodery import validate_ini_config
    from ui_components import InfoCard, SectionTitle
except ImportError as e:
    print(f"CRITICAL ERROR in config_screen.py: {e}. Make sure that 'dekodery.py' and 'ui_components.py' files exist.")
    exit()


BASE_DIR = Path(__file__).parent
INI_PATH = BASE_DIR / "config" / "waga.ini"

class ConfigScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize dictionary for TextInput controls
        self.inputs = {}
        # Initialize configparser parser
        self.parser = configparser.ConfigParser()
        root_layout = RelativeLayout()
        root_layout.add_widget(Image(source=str(BASE_DIR / 'assets' / 'images' / 'tlo3.png'), allow_stretch=True, keep_ratio=False))
        # Main container
        main_box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        # Screen title
        title_label = Label(text="Application Configuration", font_size='24sp', bold=True, size_hint_y=None, height=50)
        main_box.add_widget(title_label)
        # Container for config cards (total 60%)
        config_container = BoxLayout(orientation='vertical', spacing=10, size_hint_y=0.6)
        # PROGRAM section (30%)
        program_card = InfoCard(padding=10, spacing=5, size_hint_y=0.5)  # 50% of 60% = 30%
        program_card.add_widget(SectionTitle("Program Settings", "settings_icon.png"))
        # English variable descriptions for PROGRAM section
        program_grid = self.create_config_grid([
            ('port_aplikacji', 'App port'),
            ('nazwa_pliku_log', 'Log file name'),
            ('czas_nasluchu_ble', 'BLE listen time'),
            ('przerwij_po_pakiecie', 'Stop after packet')
        ], 'PROGRAM')
        program_card.add_widget(program_grid)
        config_container.add_widget(program_card)
        # GARMIN section (30%)
        garmin_card = InfoCard(padding=10, spacing=5, size_hint_y=0.5)  # 50% of 60% = 30%
        garmin_card.add_widget(SectionTitle("Garmin Settings", "garmin_icon.png"))
        # English variable descriptions for GARMIN section
        garmin_grid = self.create_config_grid([
            ('garmin_email', 'Garmin email'),
            ('garmin_password_hex', 'Garmin password (hex)'),
            ('tryb_wysylki', 'Send mode'),
            ('api_token', 'API token'),
            ('api_url', 'API URL')
        ], 'GARMIN')
        garmin_card.add_widget(garmin_grid)
        config_container.add_widget(garmin_card)
        main_box.add_widget(config_container)
        # Add spacer (Widget) - increased for better separation
        main_box.add_widget(Widget(size_hint_y=0.2))  # 20% space for spacer
        # Bottom buttons (20%)
        button_box = BoxLayout(size_hint_y=0.2, spacing=20, padding=[20, 10])
        save_btn = Button(text="Save", font_size='18sp', background_color=(0.2, 0.6, 0.3, 1), background_normal='')
        save_btn.bind(on_release=self.save_data)
        back_btn = Button(text='Back', font_size='18sp', background_color=(0.8, 0.2, 0.2, 1), background_normal='')
        back_btn.bind(on_release=lambda x: setattr(self.manager, 'current', 'start'))
        button_box.add_widget(save_btn)
        button_box.add_widget(back_btn)
        main_box.add_widget(button_box)
        root_layout.add_widget(main_box)
        self.add_widget(root_layout)

    def on_enter(self, *args):
        if not validate_ini_config(str(INI_PATH)):
            popup = Popup(title="Configuration Error", content=Label(text="The waga.ini file is invalid or missing.\nCheck the console for more information."), size_hint=(0.8, 0.4))
            popup.open()
        self.load_data()

    def create_config_grid(self, keys, section):
        grid = GridLayout(cols=2, spacing=10)
        for key in keys:
            if isinstance(key, tuple):
                key_name, key_label = key
            else:
                key_name = key_label = key
            # Etykieta wyrównana do prawej
            label = Label(text=f"{key_label}:", font_size='14sp', color=(0.9,0.9,0.9,1), halign='right', valign='middle')
            label.bind(size=lambda s, w: setattr(s, 'text_size', (s.width, None)))
            grid.add_widget(label)
            # Switch for the 'przerwij_po_pakiecie' option
            if key_name == 'przerwij_po_pakiecie':
                switch_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
                switch = Switch(active=False, size_hint_x=None, width=60)
                switch_layout.add_widget(Widget(size_hint_x=0.1))  # spacer
                switch_layout.add_widget(switch)
                switch_layout.add_widget(Label(text="Yes/No", size_hint_x=0.3))
                switch_layout.add_widget(Widget(size_hint_x=0.6))  # spacer
                self.inputs[f"{section}.{key_name}"] = switch
                grid.add_widget(switch_layout)
            # Password field with show button
            elif 'password' in key_name:
                password_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=5)
                text_input = TextInput(password=True, size_hint_x=0.8, multiline=False)
                # Show password button
                toggle_btn = Button(text="👁", size_hint_x=0.2, background_normal='', background_color=(0.3, 0.3, 0.3, 1))
                def toggle_password(btn, input_field):
                    input_field.password = not input_field.password
                    btn.text = "👁" if input_field.password else "👁‍🗨"
                toggle_btn.bind(on_release=lambda btn, input=text_input: toggle_password(btn, input))
                password_layout.add_widget(text_input)
                password_layout.add_widget(toggle_btn)
                self.inputs[f"{section}.{key_name}"] = text_input
                grid.add_widget(password_layout)
            # Regular text fields
            else:
                text_input = TextInput(size_hint_y=None, height=40, multiline=False, background_color=(1,1,1,0.9))
                self.inputs[f"{section}.{key_name}"] = text_input
                grid.add_widget(text_input)
        return grid

    def load_data(self):
        if not INI_PATH.exists():
            return
        self.parser.read(INI_PATH, encoding='utf-8')
        for key, input_widget in self.inputs.items():
            section, option = key.split('.')
            value = self.parser.get(section, option, fallback='')
            # Switch handling
            if isinstance(input_widget, Switch):
                input_widget.active = value.lower() in ('true', '1', 'yes', 'tak')
            # Password handling
            elif 'password' in option and value:
                try: 
                    input_widget.text = bytes.fromhex(value).decode('utf-8')
                except (ValueError, UnicodeDecodeError): 
                    input_widget.text = ''
            # Regular fields
            else:
                input_widget.text = value

    def save_data(self, instance):
        for key, input_widget in self.inputs.items():
            section, option = key.split('.')
            # Switch handling
            if isinstance(input_widget, Switch):
                value = str(input_widget.active)
            # Other fields
            else:
                value = input_widget.text.strip()
                if 'password' in option: 
                    value = value.encode('utf-8').hex()
            if not self.parser.has_section(section): 
                self.parser.add_section(section)
            self.parser.set(section, option, value)
        with open(INI_PATH, 'w', encoding='utf-8') as f: 
            self.parser.write(f)
        # Popup with OK button
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        content.add_widget(Label(text="Configuration saved successfully."))
        # Container for OK button - centered
        btn_container = BoxLayout(size_hint_y=None, height=50)
        btn_container.add_widget(Widget(size_hint_x=0.3))
        ok_btn = Button(
            text="OK", 
            size_hint=(None, None), 
            size=(100, 40),
            background_color=(0.2, 0.6, 0.3, 1),
            background_normal=''
        )
        ok_btn.bind(on_release=lambda x: popup.dismiss())
        btn_container.add_widget(ok_btn)
        btn_container.add_widget(Widget(size_hint_x=0.3))
        content.add_widget(btn_container)
        popup = Popup(title="Saved", content=content, size_hint=(0.7, 0.3), auto_dismiss=True)
        popup.open()
