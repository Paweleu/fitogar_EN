import os
from pathlib import Path
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle

BASE_DIR = Path(__file__).parent

class SectionTitle(BoxLayout):
    """Custom widget for section title with icon."""
    def __init__(self, text, icon_source, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 40
        self.spacing = 10
        icon_path = BASE_DIR / 'assets' / 'images' / icon_source
        if icon_path.exists():
            self.add_widget(Image(source=str(icon_path), size_hint_x=None, width=24))
        self.add_widget(Label(text=text, font_size='18sp', bold=True, color=(1,1,1,1), halign='left', valign='middle'))

class InfoCard(BoxLayout):
    """Custom 'card' widget with rounded background."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        with self.canvas.before:
            Color(0.15, 0.15, 0.2, 0.7) # Darker, more stylish background
            self.rect = RoundedRectangle(radius=[15,])
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
