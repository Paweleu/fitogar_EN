import os
from pathlib import Path
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.button import Button
from  kivy.graphics.boxshadow import BoxShadow  
from kivy.graphics import Color
from kivy.graphics.boxshadow import BoxShadow
from kivy.app import App

BASE_DIR = Path(__file__).parent

class StartScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        root_layout = RelativeLayout()
        
        # Application background
        bg_image = Image(source=str(BASE_DIR / 'assets' / 'images' / 'tlo4.png'), allow_stretch=True, keep_ratio=False)
        root_layout.add_widget(bg_image)
        # Content container
        content_layout = BoxLayout(orientation='vertical', padding=20, spacing=30, pos_hint={'center_x': 0.5, 'center_y': 0.5}, size_hint=(0.8, 0.8))
        # Pasek tytułowy tylko z wersją aplikacji
        title_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, padding=[10, 0, 10, 0], spacing=10)
        # title_bar.add_widget(Label(text="FiToGar v.0.1.0", font_size='20sp', bold=True, color=(0,0,0,1), halign='left', valign='middle'))
        content_layout.add_widget(title_bar)
        # Application title
        title_box = BoxLayout(orientation='vertical', size_hint_y=0.5)
        logo_path = BASE_DIR / 'assets' / 'images' / '_logo3.png'
        if logo_path.exists():
            title_box.add_widget(Image(source=str(logo_path), size_hint_y=0.7))
            #title_box.add_widget(Label(text="FiToGar", font_size='48sp', bold=True, color=(1,1,1,1)))
        content_layout.add_widget(title_box)
        # Buttons container
        buttons_layout = BoxLayout(orientation='vertical', spacing=15, size_hint_y=0.6)
        # Button to go to weighing
        class ShadowButton(Button):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                with self.canvas.before:
                    Color(rgba=(123, 63, 0, 0.3))
                    self.shadow = BoxShadow(
                        pos=self.pos,
                        size=self.size,
                        offset=(0, -5),
                        spread_radius=(-5, -5),
                        border_radius=(1, 1, 1, 1),
                        blur_radius=40 if self.state == "normal" else 25
                    )
                self.bind(pos=self.update_shadow, size=self.update_shadow, state=self.update_shadow)
            def update_shadow(self, *args):
                self.shadow.pos = self.pos
                self.shadow.size = self.size
                self.shadow.blur_radius = 80 if self.state == "normal" else 50
        # Usage:
        btn_weigh = ShadowButton(
            text="Weigh",
            font_size='20sp',
            size_hint=(1, 0.2),
            background_color=(0.2, 0.6, 0.3, 0.3),
            background_normal='',
        )
        btn_weigh.bind(on_release=lambda x: setattr(self.manager, 'current', 'weigh'))
        buttons_layout.add_widget(btn_weigh)
        # Button to go to scanning
        btn_scan = Button(
            text="Scan devices",
            font_size='20sp',
            size_hint=(1, 0.2),
            background_color=(1, 0.5, 0, 0.7),
            background_normal='',
            background_down=''
        )
        btn_scan.bind(on_release=lambda x: setattr(self.manager, 'current', 'scan'))
        buttons_layout.add_widget(btn_scan)
        # Button to go to configuration
        btn_config = Button(
            text="Configuration",
            font_size='20sp',
            size_hint=(1, 0.2),
            background_color=(0.3, 0.3, 0.3, 0.7),
            background_normal=''
        )
        btn_config.bind(on_release=lambda x: setattr(self.manager, 'current', 'config'))
        buttons_layout.add_widget(btn_config)
        # Button to exit the application
        btn_exit = Button(
            text="Exit",
            font_size='20sp',
            size_hint=(1, 0.2),
            background_color=(0.8, 0, 0, 0.7),
            background_normal=''
        )
        btn_exit.bind(on_release=lambda x: App.get_running_app().stop())
        buttons_layout.add_widget(btn_exit)
        content_layout.add_widget(buttons_layout)
        root_layout.add_widget(content_layout)
        self.add_widget(root_layout)
