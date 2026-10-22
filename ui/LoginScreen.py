from kivy.uix.screenmanager import Screen
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.togglebutton import ToggleButton

import ui.components.AnimatedText
import ui.components.IconTextInput
from ui.components.RoundedComponents import RoundedPopup, RoundedHoverButton

from config import SERVER_URL#, USERNAME, PASSWORD

class LoginScreen(Screen):    
    def validate(self, username:str, password:str):
        if not username:
            self.show_popup("Username required", "Please enter your username.")
            return False
        if not password:
            self.show_popup("Password required", "Please enter your password.")
            return False
        
        response = App.get_running_app().backend.login(username, password)
        if response:
            status = response.get("status")
            
            if status == "invalid":
                self.show_popup("Invalid Credentials", "Please check credentials and try again.")
                return False
            
            user_name_login = response.get("UserName")
            user_id = response["UserId"]
            
            App.get_running_app().userid = user_name_login
            return True
        else:
            self.show_popup("No response from server", "Please try again later.")
            return False
    
    def login(self):
        username = self.ids.username.text #or USERNAME
        password = self.ids.password.text #or PASSWORD
        
        if not self.validate(username, password): return
        
        App.get_running_app().switch("home")
    
    def logout(self):
        App.get_running_app().switch("login", direction="right")
     
    def show_popup(self, title, body):
        if hasattr(self, "popup") and self.popup and self.popup.parent: self.popup.dismiss()
        content = BoxLayout(orientation="vertical", spacing=10, padding=20)

        msg = Label(
            text=body,
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
        self.popup = RoundedPopup(
            title=title,
            title_size=20,
            content= content,
            size_hint=(None,None),
            size= (400,300),
            auto_dismiss = False,
            separator_color=App.get_running_app().button_active,
            background_color=(0,0,0,0),
            bg_color=App.get_running_app().popup_color
        )
        ok_btn.bind(on_press=self.popup.dismiss)
        self.popup.open()
    
    def on_pre_enter(self, *args):
        if App.get_running_app().root: App.get_running_app().root.topbar_visible = False
    
    def on_pre_leave(self, *args):
        App.get_running_app().root.topbar_visible = True