from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.properties import ListProperty
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.label import Label
from kivy.properties import StringProperty, DictProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock, mainthread
from threading import Thread
from ui.components.RoundedComponents import RoundedHoverButton
from ANTSBackendService import ANTSBackendService

class ProjectSelectScreen(Screen):
    projects:list[str] = ListProperty([])
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def on_kv_post(self, base_widget):
        self.dropdown = DropDown()
        
        def handle_touch_down(widget, touch):
            if widget.collide_point(*touch.pos):
                touch.grab(widget)
                return True
        def handle_touch_up(widget, touch):
            if touch.grab_current is widget:
                self.dropdown.open(widget)
                self.input.input_widget.focus = True
                touch.ungrab(widget)
                return True
        
        self.dropdown_btn.bind(on_touch_down = handle_touch_down)
        self.dropdown_btn.bind(on_touch_up = handle_touch_up)
        self.dropdown.bind(on_select = lambda instance,value: self.select(value))
    
    def on_projects(self, instance, value):
        self.dropdown.clear_widgets()
        for project_name in self.projects:
            btn = Button(
                text=project_name,
                size_hint_y = None,
                height = 36,
                font_size = 16,
                bold = True,
                halign= "left",
                background_color= App.get_running_app().dropdown_color,
                color=App.get_running_app().text_primary,
            )
            btn.bind(on_release=lambda btn: self.dropdown.select(btn.text))
            self.dropdown.add_widget(btn)
    
    def on_enter(self, *args):
        project_response = App.get_running_app().backend.get_projects(App.get_running_app().userid)
        
        if project_response:
            site_ids = [item["SiteId"] for item in project_response]
            if self.projects != site_ids:
                self.projects = site_ids
            
    def select(self, item):
        App.get_running_app().project = item
        App.get_running_app().switch("log")

DTPARAM_DICT = {
    "Status": '',
    "RegionCode": "",
    "ProjectADPNameCode": "",
    "SiteClusterCode": "",
    "DriveRoundCode": "",
    "DeviceCode": "",
    "SLNO": "",
    "sitestatus": 0,
}

PYSTATUS_DICT = {
    "precheck": 0,
    "alarm": 0,
    "logupload": 0,
    "logdelete": 0,
    "logcheck": 0,
    "Sendscript": 0,
}

class LogUploadScreen(Screen):
    backend:ANTSBackendService
    site_details:GridLayout
    lbl_status:Label
    
    site_status = StringProperty("")
    dtparam:dict = DictProperty(DTPARAM_DICT.copy())
    pystatus:dict = DictProperty(PYSTATUS_DICT.copy())
    status = StringProperty("")
    
    def __init__(self, **kw):
        super().__init__(**kw)
        self.threads:list[Thread] = []
    
    def on_pre_leave(self, *args):
        for thread in self.threads:
            thread.join()
        App.get_running_app().backend.stop_logging_device_info()
    
    def on_leave(self, *args):
        self.container.clear_widgets()
        App.get_running_app().project = ""
    
    def on_kv_post(self, base_widget):
        self.device_display = None
        
        device_display_pos_hint = {"center_x": 0.75, "center_y": 0.5}
        self.no_device_label = Label(
            text = "No devices attached",
            color = (0.8,0,0,1),
            font_size= 18,
            size_hint = (0.4, None),
            pos_hint = device_display_pos_hint
        )
        self.no_device_label.height = self.no_device_label.texture_size[1]
        
        self.device_grid_scrollview = ScrollView(
            do_scroll_x= False,
            do_scroll_y= True,
            size_hint = (0.425, 0.6),
            pos_hint = device_display_pos_hint,
        )
        
        headers = ["Device Name", "Product Code", "IMEI Number"]
        row_height = 40
        self.device_grid = GridLayout(
            cols = len(headers),
            size_hint_y = None,
            spacing = 5,
            padding = 10,
            row_default_height = row_height,
        )
        self.device_grid.height = self.device_grid.minimum_height
        self.device_grid.bind(minimum_height=self.device_grid.setter('height'))
        
        self.device_grid_scrollview.add_widget(self.device_grid)
        
        self.device_grid.headers = []
        for header in headers:
            header_label = Label(
                text=header,
                bold=True,
                color=(0,0,0,0.8),
                size_hint_y=None,
                height=row_height,
                halign="center",
            )
            self.device_grid.headers.append(header_label)
            self.device_grid.add_widget(header_label)
    
    def on_dtparam(self, instance, value):
        self.site_details.clear_widgets()
        labels = [
            Label(
                text=(f"ADP Code: {self.dtparam['ProjectADPNameCode']}" if self.dtparam["ProjectADPNameCode"] else ""),
            ),
            Label(
                text=(f"Site ID: {self.dtparam['SiteClusterCode']}" if self.dtparam["SiteClusterCode"] else ""),
            ),
            Label(
                text=(f"Region Code: {self.dtparam['RegionCode']}" if self.dtparam["RegionCode"] else ""),
            ),
            Label(
                text=(f"Site Status: {'No sites in WIP' if self.dtparam['sitestatus']==0 else 'WIP' if self.dtparam['sitestatus'] else ""}"),
            )
        ]
        for lbl in labels:
            lbl.size_hint_y = None
            lbl.height = lbl.texture_size[1]
            lbl.padding = 4
            lbl.bind(texture_size=lbl.setter('size'))
            lbl.color = App.get_running_app().text_primary
            
            self.site_details.add_widget(lbl)
    
    def on_pre_enter(self, *args):
        user_id = App.get_running_app().userid
        selected_project = App.get_running_app().project
        cleaned_site_id = selected_project.replace('@R1', '')

        site_status_response = App.get_running_app().backend.get_site_status(user_id, cleaned_site_id)
        if site_status_response:
            self.site_status = site_status_response["STATUS"]
            self.dtparam, self.pystatus = App.get_running_app().backend.get_dtparam_and_status(user_id, cleaned_site_id)
            
            self.site_status = "1"
            self.pystatus["precheck"] = 0
            
            self.update_ui()
    
    @mainthread
    def update_ui(self): 
        self.container.clear_widgets()
        self.add_device_data()
        precheck = self.pystatus["precheck"]
        logupload = self.pystatus["logupload"]
        
        if self.site_status == "1":
            if precheck == 0:
                self.update_status("Pre-check not complete.")
                self.add_precheck_btn()
                
            elif precheck == 3 and logupload == 0:
                self.update_status(f"Pre-check failed. Please try again.")
                self.add_precheck_btn()
                
            elif precheck in [2,4]:
                self.add_logupload_btn()

        elif self.site_status == "0":
            self.add_logupload_btn()

    @mainthread
    def add_precheck_btn(self):
        self.precheck_button = RoundedHoverButton(
            text="Pre-Check",
            font_size="18sp",
            size_hint_y=None,
            height=60,
        )
        self.precheck_button.bind(on_release = self.on_precheck)
        self.container.add_widget(self.precheck_button)
    
    @mainthread
    def add_logupload_btn(self):
        if self.pystatus["logupload"] == 0:
            if self.pystatus["precheck"] == 4:
                self.update_status("The site is not in Work In Progress (WIP).")
            elif self.pystatus["precheck"] == 2:
                self.update_status("Pre-Check is complete!\nPlease contact your coordinator for approval.")
        else:
            self.update_status("Pre-Check is complete!\nProceed for log upload.")

        btn_row = BoxLayout(
            orientation="horizontal",
            size_hint_y = None,
            height=64,
            spacing=28,
        )
        
        self.logupload_btn = RoundedHoverButton(
            text="Upload Log",
            font_size="18sp",
            size_hint_y=None,
            height=60,
        )
        self.logupload_btn.bind(on_release=self.on_log_upload)
        
        self.download_btn = RoundedHoverButton(
            text="Download TI Script",
            font_size="18sp",
            size_hint_y=None,
            height=60,
        )
        self.download_btn.bind(on_release=self.on_download)
        
        btn_row.add_widget(self.logupload_btn)
        btn_row.add_widget(self.download_btn)
        
        self.container.add_widget(btn_row)
    
    @mainthread
    def update_status(self, value):
        self.status = value
    
    @mainthread
    def set_loader_visibility(self, visible:bool):
        self.loader.opacity = 1 if visible else 0
    
    def on_precheck(self, instance):
        self.precheck_button.disabled = True
        self.set_loader_visibility(True)
        thread = Thread(target=self._precheck, daemon=True)
        self.threads.append(thread)
        thread.start()
    
    def on_log_upload(self, instance):
        self.logupload_btn.disabled = True
        self.set_loader_visibility(True)
        self.update_status("Uploading log...")
        thread = Thread(target=self._upload_log, daemon=True)
        self.threads.append(thread)
        thread.start()
    
    def on_download(self, instance):
        self.download_btn.disabled = True
        self.set_loader_visibility(True)
        self.update_status("Downloading...")
        thread = Thread(target=self._download)
        self.threads.append(thread)
        thread.start()
    
    def _precheck(self):
        for update in App.get_running_app().backend.run_precheck():
            if update.get("status"): self.update_status(update["status"])
        precheck_data = update.get("data")
        
        data = {
            "ADP_NAME": self.dtparam["ProjectADPNameCode"],
            "SiteClusterCode": self.dtparam["SiteClusterCode"],
            "DriveRoundCode": self.dtparam["DriveRoundCode"],
            "value": precheck_data,
        }
        res = App.get_running_app().backend.upload_precheck_data(data)

        self.pystatus["precheck"] = 4 if res else 3
        
        self.precheck_button.disabled = False
        self.set_loader_visibility(False)
        self.update_ui()
    
    def _upload_log(self):
        App.get_running_app().backend.start_logging_device_info_to_server(self.dtparam["DriveRoundCode"], self.dtparam["DriveRoundCode"])
        
        def callback(monitor):
            self.update_status(f"{monitor.bytes_read / monitor.len * 100:0.0f}%")
            
        App.get_running_app().backend.upload_logs(self.dtparam, callback)
        self.update_status("Upload finished")
        
        response = App.get_running_app().backend.get_log_count(self.dtparam["SiteClusterCode"], self.dtparam["DriveRoundCode"])
        self.update_status(f"Logs Generated: {response.get("logs_generated")}\nLogs Uploaded: {response.get("logs_uploaded")}")
        
        self.logupload_btn.disabled = False
        self.set_loader_visibility(False)
    
    def _download(self):
        response = App.get_running_app().backend.get_file_download()
        self.update_status(response["details"])
        self.download_btn.disabled = False
        self.set_loader_visibility(False)
    
    def add_device_data(self):
        def clear_rows():
            current_rows = [child for child in self.device_grid.children if child not in self.device_grid.headers]
            self.device_grid.clear_widgets(current_rows)
        
        clear_rows()
        device_data = App.get_running_app().backend.get_all_device_status(["device_name", "model", "imei"])
        
        if self.device_display and self.device_display.parent: self.remove_widget(self.device_display)
        
        if len(device_data) == 0:
            self.device_display = self.no_device_label
            
        else:
            self.device_display = self.device_grid_scrollview
            clear_rows()
            
            for serial,data in device_data.items():
                for header in data:
                    label = Label(
                        text = data.get(header, "N/A"),
                        color = (0,0,0,1),
                        halign = "center",
                    )
                    label.text_size = (label.width, None)
                    self.device_grid.add_widget(label)
            
        self.add_widget(self.device_display)
    