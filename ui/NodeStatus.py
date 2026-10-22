from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock, mainthread
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty, DictProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle
from ui.components.RoundedComponents import RoundedBoxLayout, RoundedHoverButton, RoundedToggleButton
import ui.components.CircularProgressBar
import ui.components.Loaders

class Indicator(Widget): indicator_color = ListProperty([])

class StatusBox(RoundedBoxLayout):
    source = StringProperty("")
    title = StringProperty("")
    body1 = StringProperty("")
    body2 = StringProperty("")
    body3 = StringProperty("")
                
class DetailsWidget(BoxLayout):
    title = StringProperty("")
    body = StringProperty("")

STATUS_DICT = {
    "device_id": "",
    "device_name": "OFFLINE DEVICE",
    "product_id": "",
    "device_uuid": "",
    "manufacturer": "",
    "processor": "",
    "gpu": "",
    "architecture": "",
    "storage_total": "",
    "storage_used": "",
    "storage_available": "",
    "storage_available_percent": 0,
    "storage_used_percent": 0,
    "ram_total": "",
    "ram_usable": "",
    "ram_used": "",
    "sim1": "",
    "sim2": "",
    "processor": "",
    "processor_hz": "",
    "battery": 0,
    "battery_capacity": "",
    "battery_health": 0,
    "charging": False,
}

class DetailsCard(RoundedBoxLayout): status = DictProperty(STATUS_DICT.copy())
class NodeListButton(RoundedToggleButton): serial = StringProperty("")

BATTERY_THRESHOLD = 30

class HomeScreen(Screen):
    nodes = DictProperty({})
    selected_device = StringProperty("")
    status = DictProperty(STATUS_DICT.copy())
    
    def on_kv_post(self, base_widget):
        self.backend = App.get_running_app().backend
        self.buttons = {}
    
    def on_enter(self, *args):
        self.backend.start_device_manager()
        self.backend.device_manager.bind(on_connect=self.update_nodes, on_disconnect=self.update_nodes)
        if not self.backend.host_info_loaded.set():
            self.loader_host_info.opacity = 1
        self.backend.on_host_info_loaded(self.on_host_info_loaded)
    
    def on_host_info_loaded(self):
        self.loader_host_info.opacity = 0
        self.selected_device = "host"
        self.add_nonodes()
        self.update_nodes()
        self._event = Clock.schedule_interval(self.update_status, 60)
        
    
    def on_leave(self, *args):
        self.backend.device_manager.unbind(self.update_nodes)
        self._event.cancel()
    
    def select_device(self, serial):
        if serial == self.selected_device:
            self.selected_device = "host"
        else:
            self.selected_device = serial
    
    @mainthread
    def add_nonodes(self):
        self.nodelist.clear_widgets(self.buttons.values())
        lbl = Label(
            size_hint_y=None,
            text="No Nodes detected",
            font_size=16,
            color=App.get_running_app().text_primary,
        )
        lbl.height = lbl.texture_size[1]
        self.nodelist.add_widget(lbl)
        self.buttons["nonode"] = lbl
    
    @mainthread
    def on_nodes(self, instance, value):
        self.nodelist.clear_widgets(self.buttons.values())
        self.buttons.clear()
        
        if len(self.nodes) > 0:
            for serial,status in self.nodes.items():
                btn = NodeListButton(
                    text=f"{serial} ({status.get("battery")}%)",
                    group="nodes",
                    padding = 10,
                )
                btn.serial = serial
                btn.bind(on_release=lambda w: self.select_device(w.serial))
                self.nodelist.add_widget(btn)
                self.buttons[serial] = btn
        else:
            self.add_nonodes()
        self.update_status()

    def update_nodes(self, *args):
        self.nodes = self.backend.device_data
    
    def get_mobile_status(self, serial:str): return self.backend.get_device_status(serial)

    def on_selected_device(self, instance, value): self.update_status()

    def update_status(self, *args):
        status = STATUS_DICT.copy()
        
        if self.selected_device == "host":
            device_status = self.backend.get_host_status()
        else:
            serial = self.selected_device
            device_status = self.get_mobile_status(serial)
            if not device_status: return
            
            device_status["device_id"] = device_status["serialno"]
            device_status["device_uuid"] = device_status["serialno"]
            device_status["product_id"] = device_status["model"]
            device_status["sim1"] = device_status["cells"][0]["operator"]
            device_status["sim2"] = device_status["cells"][1]["operator"]
        
        for k in status:
            if hasattr(device_status, k):
                status[k] = getattr(device_status, k)
        
        self.status = status
        
        self.low_battery_shown = False
        
        for serial, btn in self.buttons.items():
            if serial == "nonode": continue
            device_status = self.get_mobile_status(serial)
            if "battery" not in device_status: continue

            btn.text = f"{serial} ({device_status["battery"]}%)"
            
            if device_status["battery"]<BATTERY_THRESHOLD and not device_status["charging"] and not self.low_battery_shown:
                self.show_popup("battery")
                self.low_battery_shown = True
        
    def show_popup(self, popuptype):
        if hasattr(self, "popup") and self.popup and self.popup.parent: self.popup.dismiss()
        content = BoxLayout(orientation="vertical", spacing=10, padding=20)
        title = "Popup"
        if popuptype == "battery":
            title = "Battery Low"
            message_text = "Device battery is low. Plug in the charger."
        elif popuptype == "data_sent":
            title = "Data Sent"
            message_text = "Data has been delivered successfully."
        elif popuptype == "data_fail":
            title = "Fail"
            message_text = "Data failed to be sent."
        elif popuptype == "data_error":
            title = "Error"
            message_text = "Error while sending data. Check console for logs."

        msg = Label(
            text=message_text,
            color=(1,1,1,1),
            size_hint = (1,0.7),
            font_size=17,
        )
        ok_btn = RoundedHoverButton(
            text= "OK",
            size_hint = (1,0.3),
            font_size=18,
        )
        content.add_widget(msg)
        content.add_widget(ok_btn)
        self.popup = Popup(
            title=title,
            title_size=20,
            content= content,
            size_hint=(None,None),
            size= (400,300),
            auto_dismiss = False,
            separator_color=App.get_running_app().button_active,
            background_color=(0,0,0,0),
        )
        ok_btn.bind(on_press=self.popup.dismiss)
        with self.popup.canvas.before:
            Color(*App.get_running_app().background_color2)
            self.popup.bg = RoundedRectangle(radius=[self.popup.height/6])
        def update_bg(widget, *args):
            self.popup.bg.pos = widget.pos
            self.popup.bg.size = widget.size
            self.popup.bg.radius = [widget.height/6]
        self.popup.bind(pos=update_bg, size=update_bg)
        self.popup.open()

    def refresh(self):
        btn = self.details.refresh
        loader = self.details.loader
        btn.disabled = True
        loader.opacity = 1
        btn.bg_color = App.get_running_app().button_inactive
        def toggle(*args):
            btn.disabled = False
            loader.opacity = 0
        Clock.schedule_once(toggle,1.5)
        Clock.schedule_once(self.update_status, 0)