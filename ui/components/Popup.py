from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from ui.components.RoundedComponents import RoundedHoverButton
from kivy.graphics import Color, RoundedRectangle


class PopupContainer(Popup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
