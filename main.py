from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.uix.togglebutton import ToggleButton
from ANTSBackendService import ANTSBackendService
import ui
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

Window.size = (1000,650)
Window.minimum_width, Window.minimum_height = 850,600
KV_FILE = "ui\\main.kv"

class Topbar(BoxLayout):
    home_btn:ToggleButton

class RootLayout(BoxLayout):
    orientation = "vertical"
    
    sm:ScreenManager
    topbar:Topbar
    topbar_visible:bool = BooleanProperty(False)
        
    def on_kv_post(self, base_widget) -> None: self.update_layout()

    def on_topbar_visible(self, instance, value) -> None: self.update_layout()
    
    def update_layout(self) -> None:
        if hasattr(self, "topbar") and self.topbar in self.children:
            self.remove_widget(self.topbar)
        
        if self.topbar_visible:
            self.add_widget(self.topbar, index=1)
    
    def switch(self, screen, direction="left", duration=0.25):
        if self.sm.current == screen: return
        
        self.sm.transition = SlideTransition(direction=direction, duration=duration)
        self.sm.current = screen
        
        if screen=="home":
            for btn in ToggleButton.get_widgets(self.topbar.home_btn.group):
                btn.state = "normal"
            self.topbar.home_btn.state = "down"

def to_rgba(r:int,g:int,b:int,a:float=1): return [r/255,g/255,b/255,a]

class ANTS(App):
    backend:ANTSBackendService
    root:RootLayout
    
    selected_screen = StringProperty("")
    device_id = StringProperty("")
    userid = StringProperty("")
    project = StringProperty("")
    
    background_color = to_rgba(200,200,200)#, a=0.8)
    background_color2 = to_rgba(220,220,220)#, a=0.8)
    popup_color = to_rgba(220,220,220)
    dropdown_color = to_rgba(220,220,220)
    light = to_rgba(235,235,235)
    text_primary = to_rgba(0,0,0)
    text_secondary = to_rgba(20,20,20)
    button_inactive = to_rgba(51,51,198,0.8)
    button_active = to_rgba(74,74,214,0.8)
    toggle_active = to_rgba(220,220,220)
    arc_color = to_rgba(75,75,230)
    scroll_bar = to_rgba(140,140,140)
    scroll_bar_inactive = to_rgba(180,180,180)
    
    def switch(self, *args, **kwargs): self.root.switch(*args, **kwargs)

    def build(self):
        self.icon = "assets/images/logo-a-dark.png"
        self.backend = ANTSBackendService()
        self.backend.load_host_info()
        self.device_id = self.backend.get_host_info().device_id
        return Builder.load_file(KV_FILE)

    def on_stop(self): self.backend.stop(shutdown=True)

if __name__ == "__main__": ANTS().run()