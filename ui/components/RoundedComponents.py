from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.popup import Popup
from kivy.properties import ListProperty
from kivy.animation import Animation
from .behaviors import HoverBehavior, RoundedBase


class RoundedBoxLayout(RoundedBase, BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class RoundedButton(RoundedBase, Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class RoundedHoverButton(HoverBehavior, RoundedBase, Button):
    bg_active = ListProperty([])
    bg_inactive = ListProperty([])
    show_shadow = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        self.animations = {}
        if self.bg_color:
            self.bg_inactive = self.bg_color
            self.bg_active = [min(x*1.2, 1) for x in self.bg_color]
        else:
            self.bg_color = self.bg_inactive
        self.animations["hover_in"] = Animation(bg_color=self.bg_active, duration=0.2, t="out_sine")
        self.animations["hover_out"] = Animation(bg_color=self.bg_inactive, duration=0.2, t="out_sine")

    def on_enter(self):
        self.animations["hover_in"].start(self)
    
    def on_leave(self):
        self.animations["hover_out"].start(self)
    
    def on_release(self):
        self.on_leave()

class RoundedToggleButton(RoundedBase, ToggleButton):
    bg_active = ListProperty([])
    bg_inactive = ListProperty([])
    text_active = ListProperty([])
    text_inactive = ListProperty([])
    show_shadow = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def on_kv_post(self, base_widget):
        self.on_state(self, self.state)

    def on_state(self, widget, value):
        if value == "down":
            self.color = self.text_active
            self.bg_color = self.bg_active
        else:
            self.color = self.text_inactive
            self.bg_color = self.bg_inactive
            

class RoundedPopup(RoundedBase, Popup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)