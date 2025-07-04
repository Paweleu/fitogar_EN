import os
import configparser
import threading
import time
import datetime
import asyncio
from pathlib import Path

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.clock import mainthread, Clock
from kivy.animation import Animation
from kivy.properties import DictProperty, ListProperty, StringProperty
from kivy.graphics import Rectangle 
from kivy.core.window import Window 
from kivy.graphics import Color, Line
from kivy.uix.widget import Widget

from bleak import BleakClient, BleakError

def check_for_bom(path):
    try:
        with open(path, "rb") as f:
            return f.read(3) == b'\xef\xbb\xbf'
    except Exception as e:
        print(f"Error while checking BOM: {e}")
        return False

try:
    import dekodery
    from ui_components import InfoCard, SectionTitle
except ImportError as e:
    print(f"CRITICAL ERROR: {e}. Make sure that 'dekodery.py' and 'ui_components.py' files exist.")
    exit()

BASE_DIR = Path(__file__).parent
INI_PATH = BASE_DIR / "config" / "waga.ini"
LOG_DIR = BASE_DIR / "src" / "app" / "data" / "log" 
FFB2_WEIGHT_UUID = "0000ffb2-0000-1000-8000-00805f9b34fb"
FFB3_BODY_COMP_UUID = "0000ffb3-0000-1000-8000-00805f9b34fb"
MIN_STABLE_COUNT = 29

class WeighScreen(Screen):
    """
    Main screen for the weighing process. Handles BLE communication, UI updates, and user interaction.
    """
    SESSION_LOG_PATH = LOG_DIR / f"ble_packets_{datetime.datetime.now():%Y%m%d_%H%M%S}.log"
    status_text = StringProperty("Press 'Start measurement' to begin")
    config_keys_to_display = ListProperty([
        'mac_address', 'name', 'manufacturer', 'model', 'serial_number', 
        'hardware_rev', 'firmware_rev', 'software_rev', 'system_rev' 
    ])

    def add_debug_border(self, widget, color=(1, 0, 0, 1), width=1):
        """Draws a debug border around the given widget."""
        with widget.canvas.after:
            Color(*color)
            widget.border_line = Line(rectangle=(widget.x, widget.y, widget.width, widget.height), width=width)
        widget.bind(pos=self._update_border, size=self._update_border)

    def _update_border(self, widget, *args):
        """Updates the debug border when the widget's position or size changes."""
        widget.border_line.rectangle = (widget.x, widget.y, widget.width, widget.height)

    
    
    
    
    
    
    
    def _update_param_grid_labels(self, instance, width):
        column_width = width / 2 - 20
        children = list(self.param_grid.children)[::-1]  # from top to bottom
        for i, child in enumerate(children):
            if isinstance(child, Label):
                child.text_size = (column_width, None)
                if i % 2 == 0:  # left column
                    child.halign = 'right'
                    child.valign = 'middle'
                else:  # right column
                    child.halign = 'left'
                    child.valign = 'top'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.measurement_task = None
        self.popup = None
        self.final_weight_to_send = None
        self.reset_state()
        self.build_ui()

    def reset_state(self):
        """Resets the internal measurement state."""
        self.ffb2_packets = []
        self.ffb3_packets = []
        self.stable_weight = None
        self.stable_ffb3_packet = None

    def build_ui(self):
        # 1. Draw background directly in this screen's canvas.before
        with self.canvas.before:
            self.bg_rect = Rectangle(source=str(BASE_DIR / 'assets' / 'images' / 'tlo3.png'),
                                     pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg_rect, size=self.update_bg_rect)

        # Pasek tytułowy tylko z wersją aplikacji (bez pawel.eu)
        title_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, padding=[10, 5, 10, 5])
        title_label = Label(text="FiToGar v.0.1.0", font_size='20sp', bold=True, color=(1,1,1,1), halign='left', valign='middle')
        title_label.bind(size=title_label.setter('text_size'))
        title_bar.add_widget(title_label)
        title_bar.add_widget(Widget(size_hint_x=1))
        # USUNIĘTO pawel.eu

        # 2. Main container for UI content (overlays the background)
        content_wrapper = BoxLayout(orientation='vertical', padding=5, spacing=5)
        
        # 3. Create and add UI sections
        weight_card = self.create_weight_section()
        analysis_card = self.create_analysis_section()
        params_card = self.create_params_section()

        # ***** Ustawienia proporcji wysokości *****
        weight_card.size_hint_y = 0.24 
        analysis_card.size_hint_y = 0.25 
        params_card.size_hint_y = 0.25
        
        content_wrapper.add_widget(weight_card)
        content_wrapper.add_widget(analysis_card)
        content_wrapper.add_widget(params_card)

        # Dodaj pusty odstęp PRZED przyciskami
        content_wrapper.add_widget(Widget(size_hint_y=0.07))

        # Panel statusu i przycisków
        status_and_buttons_box = BoxLayout(orientation='vertical', size_hint_y=0.15, spacing=10)
        bottom_panel = self.create_buttons()
        bottom_panel.size_hint_y = 0.7 
        status_and_buttons_box.add_widget(bottom_panel)

        content_wrapper.add_widget(status_and_buttons_box)
        
        # Dodaj pasek tytułowy i całą zawartość do ekranu
        main_layout = BoxLayout(orientation='vertical')
        main_layout.add_widget(title_bar)
        main_layout.add_widget(content_wrapper)
        self.add_widget(main_layout)
    
    def _update_param_grid_labels(self, instance, width):
        column_width = width / 2 - 20
        children = list(self.param_grid.children)[::-1]  # from top to bottom
        for i, child in enumerate(children):
            if isinstance(child, Label):
                child.text_size = (column_width, None)
                if i % 2 == 0:  # left column
                    child.halign = 'right'
                    child.valign = 'middle'
                else:  # right column
                    child.halign = 'left'
                    child.valign = 'top'

    def update_bg_rect(self, instance, value):
        """Updates the background image size and position."""
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def create_weight_section(self):
        center_card = InfoCard(padding=10, spacing=1)
        center_card.add_widget(SectionTitle("Weight", "kawa1.png"))

        vertical_box = BoxLayout(orientation='vertical', size_hint_y=1)
        vertical_box.add_widget(Widget(size_hint_y=1))  # top spacer

        # HORIZONTAL layout: weight and "kg" side by side, vertically centered
        weight_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=150)
        weight_row.add_widget(Widget(size_hint_x=1))

        self.weight_label = Label(
            text="0.00", font_size='90sp', bold=True, color=(1, 1, 1, 1),
            halign='right', valign='middle', size_hint_x=None, width=300  # increased from 250 to 300
        )
        self.weight_label.bind(size=self.weight_label.setter('text_size'))
        weight_row.add_widget(self.weight_label)
        
        # Add a larger spacer between value and unit
        weight_row.add_widget(Widget(size_hint_x=None, width=30))  # increased from 10 to 30
        
        unit_label = Label(
            text="kg", font_size='30sp', color=(0.8, 0.8, 0.8, 1),
            halign='left', valign='middle', size_hint_x=None, width=60
        )
        unit_label.bind(size=unit_label.setter('text_size'))
        weight_row.add_widget(unit_label)

        weight_row.add_widget(Widget(size_hint_x=1))
        vertical_box.add_widget(weight_row)

        vertical_box.add_widget(Widget(size_hint_y=1))  # spacer below weight

        # Status message below the weight
        self.status_label = Label(
            text=self.status_text, size_hint_y=None, height=30,
            font_size='16sp', color=(0.2, 0.6, 1, 1), bold=True,
            valign='middle', halign='center'
        )
        self.status_label.bind(size=self.status_label.setter('text_size'))
        self.bind(status_text=self.status_label.setter('text'))
        vertical_box.add_widget(self.status_label)

        center_card.add_widget(vertical_box)
        self.stability_bar = ProgressBar(max=MIN_STABLE_COUNT, value=0, size_hint_y=None, height=10, opacity=0)
        center_card.add_widget(self.stability_bar)
        return center_card

    def create_analysis_section(self):
        right_card = InfoCard(padding=10, spacing=5)
        right_card.add_widget(SectionTitle("Body analysis", "body_icon.png"))

        # Main container for 3 columns
        self.analysis_grid = BoxLayout(orientation='horizontal', spacing=5, size_hint_y=None, height=150)

        # First column (left)
        left_column = BoxLayout(orientation='vertical', size_hint_x=0.4)
        
        # Add top spacer
        left_column.add_widget(Widget(size_hint_y=1))
        
        left_grid = GridLayout(cols=2, spacing=5, size_hint_y=None, height=100)
        left_grid.bind(minimum_height=left_grid.setter('height'))
        first_params = ['Fat %', 'Water %', 'Muscle %']

        # Second column (middle) - replace Widget with BoxLayout for date/time
        middle_column = BoxLayout(orientation='vertical', size_hint_x=0.2)
        # Spacer at the top of the middle column
        middle_column.add_widget(Widget(size_hint_y=0.7))
        
        # Date and time label in the middle column
        self.datetime_label = Label(
            text="",
            font_size='12sp',
            color=(0.7, 0.7, 0.7, 1),
            halign='center',
            valign='bottom',
            size_hint_y=0.3
        )
        self.datetime_label.bind(size=lambda s, w: setattr(s, 'text_size', (s.width, None)))
        middle_column.add_widget(self.datetime_label)

        # Third column (right)
        right_column = BoxLayout(orientation='vertical', size_hint_x=0.4)
        
        # Add top spacer
        right_column.add_widget(Widget(size_hint_y=1))
        
        right_grid = GridLayout(cols=2, spacing=5, size_hint_y=None, height=100)
        right_grid.bind(minimum_height=right_grid.setter('height'))
        second_params = ['Bone %', 'BMI', 'BMR (kcal)']

        self.analysis_labels = {}

        # Add parameters to the left column
        for key in first_params:
            # Label (parameter name)
            param_label = Label(
                text=f"{key}:",
                font_size='14sp',
                color=(0.8, 0.8, 0.8, 1),
                halign='right',
                valign='middle',
                size_hint_x=1,
                size_hint_y=None,
                height=30
            )
            param_label.bind(size=lambda s, w: setattr(s, 'text_size', (s.width, None)))
            left_grid.add_widget(param_label)

            # Value (initially "-")
            value_label = Label(
                text="-",
                font_size='16sp',
                color=(1, 1, 1, 1),
                bold=True,
                halign='left',
                valign='middle',
                size_hint_x=1,
                size_hint_y=None,
                height=30
            )
            value_label.bind(size=lambda s, w: setattr(s, 'text_size', (s.width, None)))
            self.analysis_labels[key] = value_label
            left_grid.add_widget(value_label)

        # Add parameters to the right column
        for key in second_params:
            # Label (parameter name)
            param_label = Label(
                text=f"{key}:",
                font_size='14sp',
                color=(0.8, 0.8, 0.8, 1),
                halign='right',
                valign='middle',
                size_hint_x=1,
                size_hint_y=None,
                height=30
            )
            param_label.bind(size=lambda s, w: setattr(s, 'text_size', (s.width, None)))
            right_grid.add_widget(param_label)

            # Value (initially "-")
            value_label = Label(
                text="-",
                font_size='16sp',
                color=(1, 1, 1, 1),
                bold=True,
                halign='left',
                valign='middle',
                size_hint_x=1,
                size_hint_y=None,
                height=30
            )
            value_label.bind(size=lambda s, w: setattr(s, 'text_size', (s.width, None)))
            self.analysis_labels[key] = value_label
            right_grid.add_widget(value_label)

        # Add GridLayouts to the BoxLayout columns
        left_column.add_widget(left_grid)
        
        # Add bottom spacer
        left_column.add_widget(Widget(size_hint_y=1))
        
        right_column.add_widget(right_grid)
        
        # Add bottom spacer
        right_column.add_widget(Widget(size_hint_y=1))

        # Add columns to the main layout
        self.analysis_grid.add_widget(left_column)
        self.analysis_grid.add_widget(middle_column)  # Use our new column with date
        self.analysis_grid.add_widget(right_column)

        right_card.add_widget(self.analysis_grid)

        self.ffb3_progress_bar = ProgressBar(max=5, value=0, size_hint_y=None, height=10, opacity=0)
        right_card.add_widget(self.ffb3_progress_bar)
        return right_card
    
    def create_params_section(self):
        left_card = InfoCard(padding=10, spacing=5)
        left_card.add_widget(SectionTitle("Scale parameters", "settings_icon.png"))

        scroll = ScrollView(size_hint_y=1)
        
        self.param_grid = GridLayout(cols=2, spacing=5, size_hint_y=1.5, size_hint_x=1)
        self.param_grid.bind(minimum_height=self.param_grid.setter('height'))
        self.param_grid.bind(width=self._update_param_grid_labels)

        self.param_labels = {}
        for key in self.config_keys_to_display:
            # Left column – field name, right aligned
            key_label = Label(
                text=f"{key.replace('_', ' ').capitalize()}:",
                font_size='14sp',
                color=(0.8, 0.8, 0.8, 1),
                halign='right',
                valign='middle',
                size_hint_x=1,  # <-- this is key!
            )
            key_label.bind(size=lambda s, w: setattr(s, 'text_size', (s.width, None)))
            self.param_grid.add_widget(key_label)

            # Right column – value
            value_label = Label(
                text="-",
                font_size='14sp',
                color=(1, 1, 1, 1),
                bold=True,
                halign='left',
                valign='center'
            )
            value_label.bind(size=lambda s, w: setattr(s, 'text_size', (s.width, None)))
            self.param_labels[key] = value_label
            self.param_grid.add_widget(value_label)

        scroll.add_widget(self.param_grid)
        left_card.add_widget(scroll)
        return left_card



    def create_buttons(self):
        bottom_panel = BoxLayout(orientation='horizontal', size_hint_y=1, padding=5, spacing=20) 
        self.start_button = Button(text="Start measurement", font_size='18sp', bold=True, background_color=(0.2, 0.6, 0.3, 0.7), background_normal='')
        self.start_button.bind(on_press=self.toggle_measurement)
        back_button = Button(text="Back", font_size='18sp', background_color=(0.8, 0.2, 0.2, 0.7), background_normal='')
        back_button.bind(on_press=self.go_back)
        bottom_panel.add_widget(self.start_button)
        bottom_panel.add_widget(back_button)
        return bottom_panel

    def go_back(self, instance):
        self.stop_measurement()
        if self.manager: self.manager.current = 'start'

    def on_pre_enter(self, *args):
        self.load_config()

    def on_enter(self, *args):
        for key, label in self.param_labels.items():
            label.text = self.config_data.get(key, 'B/D')
        self.reset_ui_full()

    def log(self, message, level="INFO"):
        dekodery.loguj(message, dopisek=f"WeighScreen [{level}]", ini_path=str(INI_PATH))
        
    def log_packet(self, label, hex_data):
        try:
            with open(self.session_log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{label}] {hex_data}\n")
        except Exception as e:
            self.log(f"BLE packet write error: {e}", "ERROR")


    import datetime

    def load_config(self):
        if not INI_PATH.exists():
            self.status_text = "❌ Error: waga.ini file not found"
            self.config_data = {}
            return

        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # 📥 Loading data from the file
        parser = configparser.ConfigParser()
        parser.read(INI_PATH, encoding='utf-8')

        if 'URZADZENIE' in parser and parser.get('URZADZENIE', 'mac_address', fallback=''):
            self.config_data = dict(parser['URZADZENIE'])
            self.log("✅ Scale configuration loaded.")
            print(f"📋 DEVICE: {self.config_data}")

            # ⚠️ Warning if the file contains BOM
            if check_for_bom(INI_PATH):
                self.log("⚠️ INI file contains BOM – may cause errors!")
                self.status_text = "⚠️ BOM detected in INI file"

            # 🧾 Create BLE log path based on MAC
            mac_raw = self.config_data.get('mac_address', 'unknown')
            mac_clean = mac_raw.replace(":", "").lower()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"ble_{mac_clean}_{timestamp}.log"
            self.session_log_path = LOG_DIR / log_filename
            self.log(f"📁 Current BLE log: {self.session_log_path}")

        else:
            self.status_text = "❌ Error: MAC address missing in INI file"
            self.config_data = {}
    def toggle_measurement(self, instance):
        is_running = self.measurement_task and not self.measurement_task.done()
        if is_running: self.stop_measurement()
        else: self.start_measurement()
    def start_measurement(self):
        if not self.config_data.get('mac_address'):
            self.status_text = "Error: Set MAC address!"; return
        self.reset_ui_full()
        self.status_text = "Starting measurement..."
        self.start_button.text = "Stop measurement"
        self.measurement_task = asyncio.create_task(self.ble_measurement_logic())
    async def ble_measurement_logic(self):
        mac = self.config_data.get('mac_address')
        self.log(f"Attempting to connect to {mac}...")
        try:
            async with BleakClient(mac, timeout=15.0) as client:
                if client.is_connected:
                    self.status_text = "Connected to scale."
                    await client.start_notify(FFB2_WEIGHT_UUID, self.handle_ffb2_notification)
                    await client.start_notify(FFB3_BODY_COMP_UUID, self.handle_ffb3_notification)
                    
                    # Added a short delay and changed the message
                    await asyncio.sleep(1)
                    self.status_text = "Measurement started"  # CHANGE 2
                    
                    while True: await asyncio.sleep(1)
        except asyncio.CancelledError: self.log("Measurement task was cancelled.")
        except Exception as e:
            self.status_text = f"BLE error: {e}"; self.log(f"BLE error: {e}", "ERROR")
        finally:
            if self.measurement_task and not self.measurement_task.done(): self.stop_measurement()

    @mainthread
    def stop_measurement(self):
        if self.measurement_task:
            self.measurement_task.cancel(); self.measurement_task = None
        self.start_button.text = "Start measurement"
        self.status_text = "Measurement stopped."

    def handle_ffb2_notification(self, sender, data: bytearray):
        if self.stable_weight is not None:
            return
        hex_data = data.hex()
        self.ffb2_packets.append(hex_data)
        self.log(f"[FFB2] Packet received: {hex_data}")
        self.log_packet("FFB2", hex_data)
        dekodery.find_fitogar_weight(
            pakiety=self.ffb2_packets, 
            min_stable=MIN_STABLE_COUNT,
            on_update=self.update_weight_ui
        )


    def handle_ffb3_notification(self, sender, data: bytearray):
        hex_data = data.hex()
        self.ffb3_packets.append(hex_data)
        packet_num = len(self.ffb3_packets)
        
        self.log(f"[FFB3] Packet #{packet_num}: {hex_data}")
        self.log_packet("FFB3", hex_data)
        
        # Update progress bar
        self.ffb3_progress_bar.value = packet_num
        self.ffb3_progress_bar.opacity = 1
        
        # Analyze after receiving the 3rd packet
        if packet_num == 3:
            self.log(f"[FFB3] Decoding packet #{packet_num}")
            self.stable_ffb3_packet = hex_data  # Use the current packet
            self.display_final_analysis(self.stable_ffb3_packet)
            
        # Check after 5 packets (for compatibility)
        if packet_num == 5:
            if not self.stable_ffb3_packet:
                self.stable_ffb3_packet = self.ffb3_packets[2]  # Use the 3rd packet (index 2)
                self.display_final_analysis(self.stable_ffb3_packet)
            self.check_if_measurement_complete()


    @mainthread
    def update_weight_ui(self, weight, stability_counter, is_stable):
        self.weight_label.text = f"{weight:.2f}"
        self.stability_bar.value = stability_counter
        self.log(f"FFB2 packet: {self.ffb2_packets[-1]}, Weight: {weight}, Stability count: {stability_counter}/{MIN_STABLE_COUNT}, Stable: {is_stable}")

        if weight == 0.0:
            self.weight_label.color = (1,1,1,1); self.stability_bar.opacity = 0
        elif is_stable:
            self.weight_label.color = (0.1,1,0.1,1); self.stability_bar.opacity = 0
            if self.stable_weight is None:
                self.status_text = "Weight stabilized"
                self.log(f"Stable weight: {weight:.2f} kg"); self.stable_weight = weight
                self.check_if_measurement_complete()
        else:
            self.weight_label.color = (1,0.6,0,1); self.stability_bar.opacity = 1

    @mainthread
    def display_final_analysis(self, hex_packet):
        self.log(f"Attempting to decode FFB3 packet: {hex_packet}")
        
        # Update date and time of the measurement
        current_time = datetime.datetime.now().strftime("%d-%m-%Y\n%H:%M:%S")
        self.datetime_label.text = current_time
        
        # Actual decoding code
        results = dekodery.dekoduj_ffb3(hex_packet)
        if not results: 
            self.log(f"FFB3 decoding error: {hex_packet}", "ERROR")
            return
        
        self.log(f"FFB3 data decoded: {results}")
        
        # Assign values to labels
        for label_key, value_label in self.analysis_labels.items():
            if label_key in results:
                unit = "%" if '%' in label_key else "kcal" if 'kcal' in label_key else ""
                value_label.text = f"{results[label_key]} {unit}".strip()
                self.log(f"Assigned: {label_key} = {results[label_key]} {unit}")
            else:
                value_label.text = "-"
                self.log(f"Value not found for: {label_key}")
        
        # Directly set the opacity
        self.analysis_grid.opacity = 1

    def check_if_measurement_complete(self):
        if self.stable_weight is not None and self.stable_ffb3_packet is not None and not self.popup:
            self.log("Measurement finished, showing popup."); self.show_confirmation_popup()

    @mainthread
    def show_confirmation_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=15)
        label = Label(text=f"Weighed: [b]{self.stable_weight:.2f} kg[/b]", markup=True, font_size='20sp', halign='center')
        content.add_widget(label)
        content.add_widget(Label(text="Confirm or enter the correct weight:"))
        self.weight_input = TextInput(text=f"{self.stable_weight:.2f}", multiline=False, input_filter='float', size_hint=(0.5, None), height=40, pos_hint={'center_x': 0.5})
        content.add_widget(self.weight_input)
        
        buttons = BoxLayout(spacing=10, size_hint_y=None, height=50)
        confirm_btn = Button(text="Confirm weight", background_color=(0.2, 0.6, 0.3, 1), background_normal='')
        confirm_btn.bind(on_release=self.handle_weight_confirmation)
        cancel_btn = Button(text="Cancel", background_color=(0.8, 0.2, 0.2, 1), background_normal='')
        cancel_btn.bind(on_release=lambda x: self.popup.dismiss())
        buttons.add_widget(confirm_btn); buttons.add_widget(cancel_btn)
        content.add_widget(buttons)

        self.popup = Popup(title="Confirm weight", content=content, size_hint=(0.8, None), height=250, auto_dismiss=False)
        self.popup.bind(on_dismiss=self.on_popup_dismiss)
        self.popup.open()

    def handle_weight_confirmation(self, instance):
        try:
            self.final_weight_to_send = float(self.weight_input.text)
            self.status_text = "Weight confirmed"
            self.log(f"Weight confirmed by user: {self.final_weight_to_send} kg.")
        except (ValueError, TypeError) as e:
            self.log(f"Weight conversion error: {e}", "ERROR")
            self.final_weight_to_send = self.stable_weight 
        if self.popup: self.popup.dismiss()
        self.show_garmin_send_popup()

    @mainthread
    def show_garmin_send_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=f"Send result {self.final_weight_to_send:.2f} kg\nto Garmin Connect?", halign='center'))
        
        buttons = BoxLayout(spacing=10, size_hint_y=None, height=50)
        send_btn = Button(text="Yes, send", background_color=(0.2, 0.6, 0.3, 1), background_normal='')
        send_btn.bind(on_release=self.confirm_and_send)
        cancel_btn = Button(text="No", background_color=(0.8, 0.2, 0.2, 1), background_normal='')
        cancel_btn.bind(on_release=lambda x: self.popup.dismiss())
        buttons.add_widget(send_btn)
        buttons.add_widget(cancel_btn)
        content.add_widget(buttons)

        self.popup = Popup(title="Send to Garmin", content=content, size_hint=(0.8, None), height=180, auto_dismiss=False)
        self.popup.bind(on_dismiss=self.on_popup_dismiss)
        self.popup.open()

    def on_popup_dismiss(self, instance):
        if self.popup and self.popup.title == "Send to Garmin":
            self.status_text = "Sending to Garmin Connect cancelled"
        elif self.popup and self.popup.title == "Confirm weight":
            self.status_text = "Weight not confirmed"
        
        self.popup = None
        self.stop_measurement()

    def confirm_and_send(self, instance):
        if self.popup: self.popup.dismiss()
        self.execute_garmin_send(self.final_weight_to_send)
        
    def execute_garmin_send(self, weight):
        self.status_text = "Sending data to Garmin..."
        threading.Thread(target=self.send_to_garmin_thread, args=(weight,), daemon=True).start()

    def send_to_garmin_thread(self, weight):
        success = dekodery.send_to_garmin(weight, INI_PATH, self.stable_ffb3_packet)
        Clock.schedule_once(lambda dt: self.update_garmin_send_status(success), 0)
        self.log(f"Send to Garmin: {'success' if success else 'error'}", "INFO" if success else "ERROR")
        Clock.schedule_once(lambda dt: self.reset_ui_full(), 3)

    @mainthread
    def update_garmin_send_status(self, success):
        self.status_text = "Weight sent to Garmin" if success else "Error while sending to Garmin."

    @mainthread
    def reset_ui_full(self):
        self.status_text = "Press 'Start measurement' to begin"
        self.start_button.text = "Start measurement"
        self.weight_label.text = "0.00"; self.weight_label.color = (1, 1, 1, 1)
        self.stability_bar.opacity = 0; self.stability_bar.value = 0
        self.ffb3_progress_bar.opacity = 0; self.ffb3_progress_bar.value = 0
        for label in self.analysis_labels.values(): label.text = "-"
        self.datetime_label.text = ""
        self.reset_state()