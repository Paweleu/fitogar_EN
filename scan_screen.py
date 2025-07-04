import asyncio
import configparser
from pathlib import Path

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.clock import mainthread

from bleak import BleakScanner, BleakClient

try:
    import dekodery
except ImportError as e:
    print(f"Błąd krytyczny: {e}")
    exit()

CURRENT_DIR = Path(__file__).parent
INI_PATH = CURRENT_DIR / "config" / "waga.ini"

DIS_CHARACTERISTICS = {
    "00002a29-0000-1000-8000-00805f9b34fb": "manufacturer",
    "00002a24-0000-1000-8000-00805f9b34fb": "model",
    "00002a25-0000-1000-8000-00805f9b34fb": "serial_number",
    "00002a27-0000-1000-8000-00805f9b34fb": "hardware_rev",
    "00002a26-0000-1000-8000-00805f9b34fb": "firmware_rev",
    "00002a28-0000-1000-8000-00805f9b34fb": "software_rev",
    "00002a23-0000-1000-8000-00805f9b34fb": "system_id",
}

GAS_CHARACTERISTICS = {
    "00002a00-0000-1000-8000-00805f9b34fb": "device_name",
    "00002a01-0000-1000-8000-00805f9b34fb": "appearance",
    "00002a04-0000-1000-8000-00805f9b34fb": "ppcp",
    "00002aa6-0000-1000-8000-00805f9b34fb": "car",
    "00002ac9-0000-1000-8000-00805f9b34fb": "rpa_only",
}

def ble_parse_special_fields(key, value):
    if key == "system_id":
        try:
            return f"{value.hex()} (Device/System ID)"
        except:
            return str(value)
    if key == "car":
        try:
            val = int.from_bytes(value, byteorder='little')
            return f"{val} (supports central address resolution)" if val else f"{val} (not supported)"
        except:
            return str(value)
    return value.decode('utf-8', errors='ignore').strip() if isinstance(value, (bytes, bytearray)) else str(value)

class ScanScreen(Screen):
    status_text = StringProperty("Press 'Scan' to start.")
    selected_device_info = StringProperty("No device selected.")
    found_devices = ListProperty([])
    progress_value = NumericProperty(0)
    progress_max = NumericProperty(100)

       
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scan_task = None
        self.read_task = None
        self.selected_device = None
        self.config = configparser.ConfigParser()
        self.last_selected_button = None
        self.build_ui()
        
    def on_back_pressed(self, _):
        if self.scan_task:
            self.scan_task.cancel()
            self.scan_task = None
        if self.read_task:
            self.read_task.cancel()
            self.read_task = None
        self.selected_device = None
        self.selected_device_info = "No device selected."
        self.status_text = "Press 'Scan' to start."
        self.found_devices = []
        self.devices_grid.clear_widgets()
        self.progress.opacity = 0
        self.progress_value = 0
        self.save_button.disabled = True
        if self.last_selected_button:
            self.last_selected_button.background_color = (0.1, 0.4, 0.6, 1)
            self.last_selected_button = None
        if self.manager:
            self.manager.current = 'start'


    def build_ui(self):
        with self.canvas.before:
            self.bg = Rectangle(source="assets/images/tlo3a.png", pos=self.pos, size=self.size)

        root = BoxLayout(orientation='vertical', spacing=10, padding=15)

        self.status_box = BoxLayout(size_hint_y=0.1, padding=10)
        with self.status_box.canvas.before:
            Color(1, 1, 1, 0.25)
            self.status_rect = Rectangle()
        self.status_label = Label(text=self.status_text, color=(0, 0, 0, 1))
        self.bind(status_text=self.status_label.setter('text'))
        self.status_box.add_widget(self.status_label)
        root.add_widget(self.status_box)

        self.device_box = BoxLayout(size_hint_y=0.1, orientation='vertical', padding=10)
        with self.device_box.canvas.before:
            Color(1, 1, 1, 0.25)
            self.device_rect = Rectangle()
        self.device_label = Label(text=self.selected_device_info, color=(0, 0, 0, 1))
        self.bind(selected_device_info=self.device_label.setter('text'))
        self.progress = ProgressBar(max=self.progress_max, value=self.progress_value, size_hint_y=None, height=10, opacity=0)
        self.bind(progress_value=self.progress.setter('value'))
        self.device_box.add_widget(self.device_label)
        self.device_box.add_widget(self.progress)
        root.add_widget(self.device_box)

        self.scroll = ScrollView(size_hint_y=0.7)
        with self.scroll.canvas.before:
            Color(1, 1, 1, 0.2)
            self.scroll_rect = Rectangle()
        self.scroll.bind(pos=self.update_scroll_rect, size=self.update_scroll_rect)

        self.devices_grid = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.devices_grid.bind(minimum_height=self.devices_grid.setter('height'))
        self.scroll.add_widget(self.devices_grid)
        root.add_widget(self.scroll)

        self.buttons_box = BoxLayout(size_hint_y=0.1, spacing=15, padding=[10, 10])
        with self.buttons_box.canvas.before:
            Color(1, 1, 1, 0.2)
            self.buttons_rect = Rectangle()

        self.scan_button = Button(text="Scan", background_color=(0.2, 0.6, 0.3, 1), background_normal='')
        self.scan_button.bind(on_press=self.toggle_scan)

        self.save_button = Button(text="Save parameters", disabled=True, background_color=(0.1, 0.5, 0.8, 1), background_normal='')
        self.save_button.bind(on_press=self.save_selected_device)

        self.back_button = Button(text="Back", background_color=(0.8, 0.2, 0.2, 1), background_normal='')
        self.back_button.bind(on_press=self.on_back_pressed)

        self.buttons_box.add_widget(self.scan_button)
        self.buttons_box.add_widget(self.save_button)
        self.buttons_box.add_widget(self.back_button)
        root.add_widget(self.buttons_box)

        self.add_widget(root)
        self.bind(pos=self.update_rects, size=self.update_rects)
        self.bind(found_devices=self.update_device_list)

    def update_rects(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
        self.status_rect.pos = self.status_box.pos
        self.status_rect.size = self.status_box.size
        self.device_rect.pos = self.device_box.pos
        self.device_rect.size = self.device_box.size
        self.scroll_rect.pos = self.scroll.pos
        self.scroll_rect.size = self.scroll.size
        self.buttons_rect.pos = self.buttons_box.pos
        self.buttons_rect.size = self.buttons_box.size

    def update_scroll_rect(self, instance, value):
        self.scroll_rect.pos = instance.pos
        self.scroll_rect.size = instance.size

    def toggle_scan(self, _):
        if self.scan_task and not self.scan_task.done():
            self.scan_task.cancel()
            self.status_text = "Scan cancelled."
            self.scan_button.text = "Scan"
        else:
            self.status_text = "Scanning BLE..."
            self.found_devices = []
            self.scan_button.text = "Stop"
            self.scan_task = asyncio.create_task(self.perform_scan())

    async def perform_scan(self):
        try:
            devices = await BleakScanner.discover(timeout=15)
            self.found_devices = [d for d in devices if d.address]
            self.status_text = f"Found {len(self.found_devices)} devices." if self.found_devices else "No BLE devices found."
        except Exception as e:
            self.status_text = f"Scan error: {e}"
        finally:
            self.scan_button.text = "Scan"

    @mainthread
    def update_device_list(self, _, devices):
        self.devices_grid.clear_widgets()
        for dev in devices:
            b = Button(text=f"{dev.name or 'No name'}\n{dev.address}", size_hint_y=None, height=60,
                       background_color=(0.1, 0.4, 0.6, 1), background_normal='')
            b.bind(on_press=lambda btn, d=dev: self.select_device(d, btn))
            self.devices_grid.add_widget(b)

    def select_device(self, device, btn):
        self.selected_device = device
        self.selected_device_info = f"Name: {device.name or 'None'}\nAddress: {device.address}"
        self.save_button.disabled = False
        if self.last_selected_button:
            self.last_selected_button.background_color = (0.1, 0.4, 0.6, 1)
        self.last_selected_button = btn
        btn.background_color = (0.3, 0.7, 0.3, 1)

    def save_selected_device(self, _):
        self.save_button.disabled = True
        self.progress.opacity = 1
        self.status_text = "Reading details..."
        self.read_task = asyncio.create_task(self.read_and_save())

    async def read_and_save(self):
        try:
            from bleak import BleakClient
            dekodery.loguj(f"🟡 Attempting to connect to {self.selected_device.address}", ini_path=str(INI_PATH))
            client = BleakClient(self.selected_device.address)

            connected = await client.connect()
            if not connected:
                self.status_text = "❌ Could not connect to device."
                dekodery.loguj("🔴 Connection failed.", ini_path=str(INI_PATH))
                return

            dekodery.loguj(f"🟢 Connected to {self.selected_device.name or 'no_name'} ({self.selected_device.address})", ini_path=str(INI_PATH))

            services = client.services
            if not services:
                self.status_text = "⚠️ Device does not provide services."
                dekodery.loguj("⚠️ No services after connect()", ini_path=str(INI_PATH))
                return

            self.config.read(INI_PATH, encoding='utf-8')
            info = {"mac_address": self.selected_device.address, "name": self.selected_device.name}
            log_attempts = []

            for uuid_map, zbior in [(GAS_CHARACTERISTICS, "GAS"), (DIS_CHARACTERISTICS, "DIS")]:
                for uuid, key in uuid_map.items():
                    char_list = [
                        char
                        for svc in client.services
                        for char in svc.characteristics
                        if char.uuid == uuid
                    ]
                    if not char_list:
                        info[key] = "---"
                        log_attempts.append(f"[{zbior}] {key} ({uuid}): no characteristics.")
                        continue

                    for i, char in enumerate(char_list):
                        log_attempts.append(f"[{zbior}] {key} | char#{i+1} | handle={char.handle} | props={char.properties}")

                    char = next((c for c in char_list if 'read' in c.properties), None)
                    if char:
                        try:
                            val = await client.read_gatt_char(char)
                            try:
                                decoded = val.decode("utf-8", errors="replace").strip("\x00")
                                if key == "system_id" and len(val) >= 6:
                                    parts = [f"{b:02X}" for b in val]
                                    system_id_fmt = ":".join(parts)
                                    info[key] = system_id_fmt
                                elif key == "ppcp" and len(val) == 8:
                                    min_int = int.from_bytes(val[0:2], 'little') * 1.25
                                    max_int = int.from_bytes(val[2:4], 'little') * 1.25
                                    latency = int.from_bytes(val[4:6], 'little')
                                    timeout = int.from_bytes(val[6:8], 'little') * 10
                                    info[key] = f"min={min_int:.1f}ms, max={max_int:.1f}ms, latency={latency}, timeout={timeout}ms"
                                elif key == "car" and len(val) == 1:
                                    info[key] = "enabled" if val[0] == 1 else "disabled"
                                else:
                                    info[key] = decoded

                                log_attempts.append(f"✔️ Read {key}: {decoded}")
                            except:
                                info[key] = val.hex()
                                log_attempts.append(f"✔️ Read {key}: {val.hex()} (hex fallback)")
                        except Exception as e:
                            info[key] = "---"
                            log_attempts.append(f"❌ Read error {key}: {e}")
                    elif any('notify' in c.properties for c in char_list):
                        info[key] = "[notify only]"
                        log_attempts.append(f"ℹ️ {key}: notify only — skip read.")
                    else:
                        info[key] = "---"
                        log_attempts.append(f"⚠️ {key}: no 'read'/'notify'.")

            if 'URZADZENIE' not in self.config:
                self.config['URZADZENIE'] = {}
            for k, v in info.items():
                self.config['URZADZENIE'][k] = str(v)

            # 🆕 Dodaj sekcję [USŁUGI] z charakterystykami
            self.config['USŁUGI'] = {}
            for svc in services:
                uuid_uslugi = str(svc.uuid)
                linie = []
                for char in svc.characteristics:
                    props = ", ".join(char.properties)
                    linie.append(f"{char.uuid} [{props}]")
                multiline = "\n    ".join(linie)  # każda linia zaczyna się od spacji
                
                self.config['USŁUGI'][uuid_uslugi] = f"\n    {multiline}"  # \n na początku wartości

            lines = ["📦 BLE service structure:"]
            for svc in services:
                lines.append(f"- Service: {svc.uuid} ({svc.description or 'no description'})")
                for char in svc.characteristics:
                    props = ', '.join(char.properties)
                    lines.append(f"    ↳ Char: {char.uuid} | handle={char.handle} | props=[{props}]")
            dekodery.loguj("\n".join(lines), dopisek="ScanScreen", ini_path=str(INI_PATH))
            dekodery.loguj("📝 Read attempts details:\n" + "\n".join(log_attempts), dopisek="BLE_IO", ini_path=str(INI_PATH))

            INI_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(INI_PATH, 'w', encoding='utf-8') as f:
                self.config.write(f)

            self.status_text = "✅ Data saved to waga.ini and log"

        except Exception as e:
            self.status_text = f"❌ Error: {e}"
            dekodery.loguj(f"❌ General exception: {e}", ini_path=str(INI_PATH))
        finally:
            self.progress.opacity = 0
            self.save_button.disabled = False

    def on_back_pressed(self, _):
        if self.scan_task:
            self.scan_task.cancel()
            self.scan_task = None
        if self.read_task:
            self.read_task.cancel()
            self.read_task = None
        self.selected_device = None
        self.selected_device_info = "No device selected."
        self.status_text = "Press 'Scan' to start."
        self.found_devices = []
        self.devices_grid.clear_widgets()
        self.progress.opacity = 0
        self.progress_value = 0
        self.save_button.disabled = True
        if self.last_selected_button:
            self.last_selected_button.background_color = (0.1, 0.4, 0.6, 1)
            self.last_selected_button = None
        if self.manager:
            self.manager.current = 'start'
