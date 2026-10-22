import threading
import subprocess
import re
from EventHandler import EventHandler

MAPS = {
    "SOC": {
        "SM8650": "Snapdragon 8 Gen 3",
        "SM8550": "Snapdragon 8 Gen 2",
        "SM8450": "Snapdragon 8 Gen 1",
        "SM8350": "Snapdragon 888",

        "MT6983": "Dimensity 9000",
        "MT6895": "Dimensity 9000",

        "Exynos 2200": "Exynos 2200",
    },
    "ARCHITECTURE": {
        "arm64-v8a": "64-bit ARM",
        "armeabi-v7a": "32-bit ARM",
        "x86": "Emulator",
    },
    "CALL_STATE": {
        "0": "Idle",
        "1": "Ringing",
        "2": "In Call",
    },
    "BINARY": {
        "0": "Off",
        "1": "On",
    },
}

def adb(*args):
    command_list = ["adb"]
    command_list.extend(args)
    try: 
        return subprocess.check_output(command_list, text=True).strip()
    except subprocess.CalledProcessError as e:
        return f"{e.returncode}: {e.output}"

def get_value(line:str, key:str) -> str:
    if not line or not key:  raise Exception("Invalid arguments")
    pat = re.compile(rf"\w*{key}[:=]\s*(\w+(\s?\wb)?)(?:\b|\s)", re.IGNORECASE)
    mat = re.search(pat, line)
    if mat:
        return mat.groups()[0]
    return ""

def get_numeric_size_from_str(line:str) -> int:
    pat = re.compile(r"\d+")
    mat = re.search(pat, line)
    if mat:
        return int(mat.group())
    return -1

def get_ip_from_serial(serial:str):
    pat = re.compile(r"(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(?P<port>\d+))?")
    mat = re.search(pat, serial)
    if mat:
        return mat.group("ip")

class ADBDevice:
    COMMANDS = {
        "device_name": ("settings", "get", "global", "device_name"),
        "prop": ("getprop",),
        "memory": ("cat", "/proc/meminfo"),
        "storage": ("df", "/data"),
        "battery": ("dumpsys", "battery"),
        "imei": ("service", "call", "iphonesubinfo", "1", "s16", "com.android.shell"),
        "gpu": ("dumpsys", "SurfaceFlinger"),
        "call_state": ("dumpsys", "telephony.registry"),
        "flight_mode": ("settings", "get", "global", "airplane_mode_on"),
        "internet": ("ping", "-c 1", "www.google.com"),
        "mute": ("input", "keyevent 164"),
        "rotation_mode": ("settings", "get", "system", "accelerometer_rotation"),
        "signal": ("dumpsys", "telephony.registry"),
    }
      
    def _base_cmd(self):
        cmd = ["adb"]
        if self.serial:
            cmd.extend(["-s", self.serial])
        return cmd

    def _run(self, *args, **kwargs):
        cmd = self._base_cmd() + list(args)
        try:
            return subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True, shell=True, **kwargs).strip()
        except subprocess.CalledProcessError as e:
            print(f"Error while running {cmd}\nError Code: {e.returncode}\t{e.output}")
            return None
    
    def shell(self, keys:str|list=[]) -> dict[str, str]:
        command_list = []
        DELIMITER = "__SECTION__"
        
        if type(keys) == str:
            if keys == "all":
                keys = list(self.COMMANDS.values())
            elif keys == "status":
                keys = ["device_name", "prop", "memory", "storage", "battery", "imei", "gpu", "signal"]
            elif keys == "update":
                keys = ["memory", "storage", "battery", "signal"]
            elif keys == "tests":
                keys = ["call_state", "flight_mode", "internet", "mute", "rotation_mode"]
            else:
                keys = [keys]

        for key in keys:
            if key not in self.COMMANDS.keys():
                raise Exception(f"Invalid key.\tValid keys: {self.COMMANDS.keys()}")
            
            command_list.extend(["echo", f"{DELIMITER}{key};"])
            command_list.extend(self.COMMANDS[key] + (";",))
        
        output = self._run("shell", *command_list) or ""
        
        sections = {}
        for part in output.split(DELIMITER):
            if not part.strip(): continue
            
            lines = part.splitlines()
            key = lines[0].strip()
            sections[key] = "\n".join(lines[1:]).strip()
        
        return sections
    
    def __init__(self, serial=""):
        self.serial = serial
        self.data = {}
        
        output = self.shell("status")
        self.parse_output(output)
    
    def parse_output(self, output:dict):
        def parse_props(properties:str):
            props:dict = {}
            for line in properties.splitlines():
                if not line.strip(): continue
                try:
                    key,value = line[1:-1].split("]: [", 1)
                    props[key] = value
                except: continue
            
            self.data["model"] = props.get("ro.product.model")
            self.data["serialno"] = (
                props.get("ro.serialno") or
                props.get("ro.boot.serialno")
            )
            
            self.data["device"] = (
                props.get("ro.product.device") or
                props.get("ro.product.system.device") or
                "Unknown"
            )
            
            self.data["manufacturer"] = (
                props.get("ro.product.manufacturer") or
                props.get("ro.product.system.manufacturer") or
                props.get("ro.product.vendor.manufacturer") or
                "Unknown"
            ).upper()
            
            self.data["brand"] = props.get("ro.product.brand") or props.get("ro.product.system.brand") or "Unknown"
            self.data["os_version"] = props.get("ro.build.version.sdk") or props.get("ro.product.first_api_level")
            
            is_emulator = props.get("ro.kernel.qemu") == "1"
            soc_model:str = props.get("ro.soc.model", "").lower()
            model_platform = props.get("ro.board.platform", "").lower()
            hardware = props.get("ro.hardware", "").lower()
            processor = "Unknown SoC"
            
            if is_emulator: processor = "Emulator CPU"
            elif soc_model and soc_model in MAPS["SOC"]: processor = MAPS["SOC"][soc_model]
            elif soc_model.startswith("s5e"): processor = f"Exynos {soc_model}"
            elif model_platform:
                if "sdm" in model_platform or "sm" in model_platform or "msm" in model_platform:
                    processor = f"Snapdragon ({model_platform})"
                elif "mt" in model_platform:
                    processor = f"MediaTek ({model_platform})"
                elif "exynos" in model_platform:
                    processor = f"Exynos ({model_platform})"
            elif hardware:
                if "qcom" in hardware:
                    processor = f"Snapdragon({hardware})"
                elif "mtk" in hardware:
                    processor = f"Mediatek ({hardware})"
            self.data["processor"] = processor
            
            architecture:str = (
                props.get("ro.product.cpu.abilist") or
                props.get("ro.product.cpu.abi") or
                ""
            ).lower()
            for arch in MAPS["ARCHITECTURE"].keys():
                if arch in architecture:
                    self.data["architecture"] = MAPS["ARCHITECTURE"][arch]
                    break
            else:
                self.data["architecture"] = "Unknown Architecture"
        
        def parse_ram(mem:str):
            self.data["ram_total"] = get_value(mem, "MemTotal")
            self.data["ram_usable"] = get_value(mem, "MemAvailable")
            
            self.data["ram_total_int"] = get_numeric_size_from_str(self.data["ram_total"])
            self.data["ram_usable_int"] = get_numeric_size_from_str(self.data["ram_usable"])
            self.data["ram_used_int"] = self.data["ram_total_int"] - self.data["ram_usable_int"]
            
            self.data["ram_used"] = f"{self.data["ram_total_int"] - self.data["ram_usable_int"]} kB"
            self.data["ram_used%"] = self.data["ram_used_int"] / self.data["ram_total_int"] * 100
            self.data["ram_usable%"] = self.data["ram_usable_int"] / self.data["ram_total_int"] * 100
        
        def parse_storage(storage_str:str):
            storage = storage_str.splitlines()[1].split()
            self.data["storage_total_int"] = int(storage[1])
            self.data["storage_used_int"] = int(storage[2])
            self.data["storage_available_int"] = int(storage[3])
            
            self.data["storage_total"] = f"{self.data['storage_total_int']} kB"
            self.data["storage_used"] = f"{self.data['storage_used_int']} kB"
            self.data["storage_available"] = f"{self.data['storage_available_int']} kB"
            self.data["storage_used%"] = float(storage[4][:-1])
            self.data["storage_available%"] = 100 - self.data["storage_used%"]

        def parse_battery(battery):
            try: self.data["battery"] = int(get_value(battery, "level"))
            except: self.data["battery"] = 0
            
            self.data["charging"] = get_value(battery, "AC powered")=="true" or get_value(battery,"USB powered")=="true" or\
                get_value(battery,"Wireless powered")=="true" or get_value(battery, "Dock powered")=="true"
                
            try: self.data["battery_capacity"] = f"{int(get_value(battery, "Charge counter"))/1000:0.0f} mAh"
            except: self.data["battery_capacity"] = "NA"
            
            try: self.data["battery_health"] = int(get_value(battery, "mSavedBatteryBsoh"))
            except: self.data["battery_health"] = 0

        def parse_imei(string):
            hex = re.findall(r"'(.*?)'", string)
            digits = re.findall(r"\d", ''.join(hex))
            imei = ''.join(digits)
            self.data["imei"] = imei if len(imei) >= 14 else "Invalid IMEI"

        def parse_gpu(gpu_str:str):
            search_str = '\n'.join([line for line in gpu_str.splitlines() if "GLES" in line])
            pat = re.compile(r"GLES: (?P<gpu>.*OpenGL ES \d+\.\d+)")
            mat = re.search(pat, search_str)
            if mat:
                self.data["gpu"] = mat.group("gpu")
        
        def parse_signal(output_string:str):                
            def parse_kv_block(block:str) -> dict[str,int]:
                pairs = re.findall(r"(\w+)\s*=\s*(-?\d+)", block)
                return {k:int(v) for k,v in pairs if int(v) != 2147483647}
            
            def detect_metric(key:str) -> str|None:
                key = key.lower()
                if "rsrp" in key:
                    return "rsrp"
                if "rsrq" in key:
                    return "rsrq"
                if "snr" in key or "sinr" in key:
                    return "sinr"
                return None
            
            def interpret_rsrp(rsrp:int) -> str:
                if rsrp >= -80:
                    return "Excellent"
                elif rsrp >= -90:
                    return "Good"
                elif rsrp >= -100:
                    return "Average"
                elif rsrp >= -110:
                    return "Poor"
                return "Very Poor"
            
            def interpret_rsrq(rsrq:int) -> str:
                if rsrq >= -10:
                    return "Good"
                elif rsrq >= -15:
                    return "Average"
                elif rsrq >= -20:
                    return "Poor"
                return "Very Poor"

            def interpret_sinr(sinr:int) -> str:
                if sinr >= 20:
                    return "Excellent"
                elif sinr >= 13:
                    return "Good"
                elif sinr >= 0:
                    return "Average"
                return "Poor"
            
            all_cell_data = {}
            lines = output_string.splitlines()
            index,n = 1, len(lines)
            currentphoneid = None
            while index < n:
                line = lines[index].strip()
                if line.startswith("Phone Id"):
                    currentphoneid = line.rsplit("=",1)[-1]
                    all_cell_data[currentphoneid] = {}
                if line.startswith("mSignalStrength"):
                    if currentphoneid not in all_cell_data: continue
                    all_cell_data[currentphoneid]["SignalStrength"] = line
                if line.startswith("mCellIdentity"):
                    if currentphoneid not in all_cell_data: continue
                    all_cell_data[currentphoneid]["CellIdentity"] = line
                if "local logs" in line: break
                index += 1
            
            self.data["cells"] = []
            for phoneid, data in all_cell_data.items():
                cell_data = {"phoneid":phoneid, "rsrp":None, "rsrq":None, "sinr":None, "bars":None, "operator":None}
                signal_strength = data["SignalStrength"]
                for k,v in parse_kv_block(signal_strength).items():
                    if metric := detect_metric(k):
                        cell_data[metric] = v
                if cell_data["rsrp"]: cell_data["Signal strength"] = interpret_rsrp(cell_data["rsrp"])
                if cell_data["rsrq"]: cell_data["Signal quality"] = interpret_rsrq(cell_data["rsrq"])
                if cell_data["sinr"]: cell_data["Signal clarity"] = interpret_sinr(cell_data["sinr"])
                if bars := re.search(r"SignalBarInfo{ \w*Level=(\d+) }", signal_strength): cell_data["bars"] = bars.groups()[0]
                
                cell_identity = data["CellIdentity"]
                if mAlpha := re.search(r"mAlphaLong\s*=\s*(?P<alpha>.+)(?=\smAlphaShort)", cell_identity): cell_data["operator"] = mAlpha.group("alpha")
                
                self.data["cells"].append(cell_data)
        
        parsers = {
            "prop": parse_props,
            "memory": parse_ram,
            "storage": parse_storage,
            "battery": parse_battery,
            "imei": parse_imei,
            "gpu": parse_gpu,
            "signal": parse_signal
        }    
        for k,v in output.items():
            if k == "device_name":
                self.data["device_name"] = v
            else:
                parsers[k](v)
        
    def update_status(self):
        output = self.shell("update")
        self.parse_output(output)
        return self.data

    def check_internet_connection(self):
        if "ping: unknown host" in self.shell("internet"):
            return "0"
        return "1"

    def run_tests(self):
        test_results = self.shell("tests")
        test_data = {}
    
        call_state = get_value(test_results["call_state"], "mCallState")
        test_data["Call State"] = MAPS["CALL_STATE"].get(call_state)

        test_data["Flight Mode"] = MAPS["BINARY"].get(test_results.get("flight_mode"))
        test_data["Internet Connection"] = "Disconnected" if ("ping: unknown host" in test_results.get("internet")) else "Connected"
        test_data["Volume"] = "Muted"
        test_data["Rotation Mode"] = MAPS["BINARY"].get(test_results.get("rotation_mode"))
        
        return test_data

class ADBDevices(dict):
    def __getitem__(self, key):
        try: return super().__getitem__(key)
        except:
            try:
                return ADBDevice(key)
            except:
                raise Exception(f"Device with serial {key} is not connected")

class ADBDeviceTracker(EventHandler):
    def __init__(self):
        super().__init__("on_connect", "on_disconnect")
        self.connected_devices = set()
        self.proc:subprocess.Popen = None
        self.thread = None
        self.stop_event = threading.Event()

    def start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def _run(self):
        while not self.stop_event.is_set():
            try:
                self.proc = subprocess.Popen(
                    ["adb", "track-devices"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                while not self.stop_event.is_set():
                    header = self.proc.stdout.read(4)
                    if not header: continue
                    size = int(header, 16)
                    
                    payload:str = self.proc.stdout.read(size)
                    if not payload: continue
                    
                    for line in payload.splitlines():
                        if not line.strip(): continue
                        serial,status = line.split("\t", 1)\
                        
                        if status == "device":
                            if serial not in self.connected_devices:
                                self.connected_devices.add(serial)
                                self.dispatch("on_connect", serial)

                        elif status == "offline":
                            if serial in self.connected_devices:
                                self.connected_devices.remove(serial)
                                self.dispatch("on_disconnect", serial)

            except Exception as e: print(f"Tracker stopped: {e}")
            
            finally:
                if self.proc:
                    self.proc.kill()
                    self.proc = None
                
                if not self.stop_event.is_set():
                    self.stop_event.wait()
    
    def stop(self):
        self.stop_event.set()
        self.connected_devices.clear()
        self.unbind()
        if self.proc:
            self.proc.kill()
        if self.thread:
            self.thread.join()

class ADBDeviceManager(EventHandler):
    def __init__(self):
        super().__init__("on_connect", "on_disconnect")
        self.devices = ADBDevices()
        self.tracker = ADBDeviceTracker()
    
    def device_connected(self, serial):
        if serial in self.devices: return
        
        self.devices[serial] = ADBDevice(serial)
        self.dispatch("on_connect", serial, self.devices[serial])
    
    def device_disconnected(self, serial):
        if serial not in self.devices: return
        
        self.dispatch("on_disconnect", serial, self.devices[serial])
        self.devices.pop(serial)
    
    def start(self):
        self.devices.clear()
        self.tracker.bind(on_connect=self.device_connected, on_disconnect=self.device_disconnected)
        self.tracker.start()
    
    def stop(self):
        self.devices.clear()
        self.unbind()
        self.tracker.stop()

    def start_server(self, device_list:list=[]):
        """
        Starts adb server with an optional list device_list of known connected devices
        """
        adb("start-server")
        self.start()
        
        for serial in device_list:
            ip = get_ip_from_serial(serial)
            if ip: adb("connect", ip)
        
        for serial in self.get_connected_devices():
            self.device_connected(serial)
        
    def kill_server(self):
        """
        Kills adb server and returns list of connected devices before server was killed.
        """
        connected_devices = list(self.tracker.connected_devices)
        self.tracker.stop()
        adb("kill-server")
        self.devices.clear()
        return connected_devices

    def get_connected_devices(self):
        out = adb("devices").splitlines()[1:]
        return {serial:status for serial,status in [line.split() for line in out]} if out else {}