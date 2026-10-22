import psutil
import subprocess
from pathlib import Path
from datetime import datetime
from threading import Thread, Event, Lock
from concurrent.futures import ThreadPoolExecutor
from socket import create_connection as create_socket_connection, AddressFamily
from dataclasses import dataclass
import logging
import re
from requests import Session
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from configparser import ConfigParser
import platform
import win32com.shell.shell as shell # type: ignore
import win32event
import winsound
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import adb
from config import SERVER_URL, SERVER_NAME, SCRIPT_NAME, SCRIPT_VERSION, API_KEY, AUTHORIZATION_KEY

DEVICEIDID = "V1123"
DEVICE_TOKEN = "aafaffawqeqwwrfg123"
LOGFILE_EXTENSIONS = [".trp"]

def get_size_suffix(size:int, unit="",suffix="B") -> str:
    """Convert size as an integer to corresponding size with unit, returning the size as a string.\nExample: get_size_suffix(1024) = '1KB'"""
    units = ["", "K", "M", "G", "T", "P"]
    unit_index = units.index(unit)
    for unit in units[unit_index:]:
        if size < 1024:
            return f"{size:0.2f} {unit}{suffix}"
        size /= 1024
    return str(size)

class BackgroundThread():
    """Creates a daemon thread for tasks that need to be handled in the background"""
    def __init__(self, fn, interval:int|None=None):
        """
            `fn`: Function to be called by worker thread
            `interval`: Interval (in seconds) to be waited for in between each function call
        """
        self.thread = Thread(target=fn, daemon=True)
        self.event = Event()
        self.interval = interval
    
    def start(self):
        """Starts the worker thread"""
        if self.thread: self.thread.start()
    
    def stop(self):
        """Wait until worker thread terminates"""
        if self.thread: self.thread.join()

@dataclass(slots=True)
class DeviceInformation:
    """Data class to store local host device information"""
    device_id:str = ""
    mac:str = ""
    device_name:str = ""
    family:str = ""
    manufacturer:str = ""
    processor:str = ""
    physical_cores:str = ""
    total_cores:str = ""
    processor_hz:str = ""
    gpu:str = ""
    os:str = ""
    os_version:str = ""
    architecture:str = ""
    product_id:str = ""
    device_uuid:str = ""
    battery_full_capacity_int:int = 0
    battery_design_capacity_int:int = 0
    ram_total:str = ""
    ram_usable:str = ""
    ram_used:str = ""
    ram_used_percent:float = 0
    ram_sticks:str = ""
    storage_total_int:int = 0
    storage_total:str = ""
    storage_used_int:int = 0
    storage_used:str = ""
    storage_used_percent:float = 0
    storage_available_int:int = 0
    storage_available:str = ""
    storage_available_percent:float = 0
    battery:float = 0
    charging:bool = False
    battery_capacity:str = ""
    battery_design_capacity:str = ""
    battery_health:float = 0
    tems_status:bool = False
    
    @classmethod
    def fetch(cls):
        try:
            import win32com.client
            import pythoncom
            
            pythoncom.CoInitialize()
            try:
                WMI = win32com.client.GetObject("winmgmts:")
                ROOT_WMI = win32com.client.GetObject(r"winmgmts:\\.\root\wmi")
                
                BIOS = WMI.ExecQuery("SELECT SerialNumber From Win32_BIOS")[0]
                NETWORK_ADAPTER = WMI.ExecQuery("SELECT MACAddress FROM Win32_NetworkAdapterConfiguration WHERE IPEnabled=True")[0]
                COMP_SYSTEM = WMI.ExecQuery("SELECT Name, SystemFamily, Manufacturer FROM Win32_ComputerSystem")[0]
                OS = WMI.ExecQuery("SELECT Caption,Version,OSArchitecture,SerialNumber FROM Win32_OperatingSystem")[0]
                PROCESSOR = WMI.ExecQuery("SELECT Name,NumberOfCores,NumberOfLogicalProcessors FROM Win32_Processor")[0]
                GPU = WMI.ExecQuery("SELECT Name FROM Win32_VideoController")[0]
                COMPUTER_SYSTEM_PRODUCT = WMI.ExecQuery("SELECT UUID FROM Win32_ComputerSystemProduct")[0]
                PHYSICAL_MEMORY = WMI.ExecQuery("SELECT capacity FROM Win32_PhysicalMemory")
                # PRODUCTS = WMI.ExecQuery("SELECT * FROM Win32_Product")
                BATTERY_FULL_CAPACITY = ROOT_WMI.ExecQuery("SELECT FullChargedCapacity FROM BatteryFullChargedCapacity")[0].FullChargedCapacity
                BATTERY_DESIGN_CAPACITY = ROOT_WMI.ExecQuery("SELECT DesignedCapacity FROM BatteryStaticData")[0].DesignedCapacity
                
                ram_list = [int(ram.capacity) for ram in PHYSICAL_MEMORY]
                storage_total_int = sum([d.total for d in [psutil.disk_usage(part.device) for part in psutil.disk_partitions()]])
                # products = [p.name for p in PRODUCTS]
                battery_full_capacity_int = int(BATTERY_FULL_CAPACITY) / 1000
                battery_design_capacity_int = int(BATTERY_DESIGN_CAPACITY) / 1000
                ram_sticks_list = [get_size_suffix(ram) for ram in ram_list]
                
                return cls(
                    device_id = BIOS.SerialNumber,
                    mac = NETWORK_ADAPTER.MACAddress,
                    device_name = COMP_SYSTEM.Name,
                    family = COMP_SYSTEM.SystemFamily,
                    manufacturer = COMP_SYSTEM.Manufacturer,
                    processor = PROCESSOR.Name,
                    physical_cores = str(PROCESSOR.NumberOfCores),
                    total_cores = str(PROCESSOR.NumberOfLogicalProcessors),
                    processor_hz = f"{psutil.cpu_freq().max/1000:0.1f} GHz",
                    gpu = GPU.Name,
                    os = OS.Caption,
                    os_version = OS.Version,
                    architecture = OS.OSArchitecture,
                    product_id = OS.SerialNumber,
                    device_uuid = COMPUTER_SYSTEM_PRODUCT.UUID,
                    ram_total = get_size_suffix(sum(ram_list)),
                    ram_usable = get_size_suffix(psutil.virtual_memory().total),
                    ram_sticks = f"{len(ram_sticks_list)} x {ram_sticks_list}",
                    storage_total_int = storage_total_int,
                    storage_total = get_size_suffix(storage_total_int),
                    battery_capacity = f"{battery_full_capacity_int:0.2f} Wh",
                    battery_design_capacity = f"{battery_design_capacity_int:0.2f} Wh",
                    battery_health = battery_full_capacity_int / battery_design_capacity_int * 100,
                    # tems_status = "investigator" in products and "mediator" in products and "udp" in products,
                )
            
            except Exception as e: print(f"Error while loading device information\n{e}")
            finally:
                pythoncom.CoUninitialize()
        except Exception as e: print(f"Error: {e}\nThis app only works on Windows systems.")

class ANTSBackendService:
    """
    Backend Service class for ANTS. Manages all communication between server and device, as well as logging device information.
    """
    
    def _load_paths(self):
        """
        Checks for the correct file structure, creating it if necessary. Loads required path variables inside `self.paths`
        """
        TEMS_LOGS_PATH  = Path("C:/LOGFILES")
        TILOGS_PATH     = TEMS_LOGS_PATH / "TILogs"
        BACKUP_PATH     = TEMS_LOGS_PATH / "Backup"
        TISCRIPTS_PATH  = TEMS_LOGS_PATH / "TIScripts" 
        TILOGS_UPLOAD_PATH  = TILOGS_PATH / "upload"
        TO_BE_UPLOADED_PATH = BACKUP_PATH / "to_be_uploaded"

        TEMS_PROGRAM_DATA_PATH  = Path("C:/ProgramData/TEMS")
        ANTS_DATA_PATH = Path("C:/Python/ANTS")
        ANTS_LOGS_PATH = ANTS_DATA_PATH / "Logs"
        NETWORK_LOGS_PATH = ANTS_LOGS_PATH / "Network"
        SYSINFO_LOGS_PATH = ANTS_LOGS_PATH / "Sysinfo"

        SYSTEMINFORMATION_PATH = Path.home() / "Systeminformation"
        STATUS_MAPPER_PATH = SYSTEMINFORMATION_PATH / "status_mapper"
        CONFIG_PATH        = SYSTEMINFORMATION_PATH / "config.ini"
        
        dirs = [
            TEMS_LOGS_PATH,
                TILOGS_PATH, BACKUP_PATH, TISCRIPTS_PATH,
                    TILOGS_UPLOAD_PATH, TO_BE_UPLOADED_PATH,
            TEMS_PROGRAM_DATA_PATH,
            ANTS_DATA_PATH, ANTS_LOGS_PATH,
                NETWORK_LOGS_PATH,
                SYSINFO_LOGS_PATH,
            SYSTEMINFORMATION_PATH,
        ]
        for folder in dirs:
            if not folder.exists(): folder.mkdir()
        
        paths = {
            "config": CONFIG_PATH,
            "ti_logs": TILOGS_UPLOAD_PATH,
            "ti_scripts": TISCRIPTS_PATH,
            "network": NETWORK_LOGS_PATH,
            "sysinfo_logs": SYSINFO_LOGS_PATH,
        }
        try:
            TEMS_DATA_PATH  = next(TEMS_PROGRAM_DATA_PATH.iterdir())
            TEMS_ODM_PATH   = TEMS_DATA_PATH / "Update" / "ODM"
            ODM_APK_VERSIONS_PATH       = TEMS_ODM_PATH / "ODM2" / "ApkVersions.xml"
            ODM_ODM2_APK_VERSIONS_PATH  = TEMS_ODM_PATH / "ODM2" / "ODM2ApkVersions.xml"
            ODM_ODM_APK_VERSIONS_PATH   = TEMS_ODM_PATH / "ODM" / "ODMApkVersions.xml"
            
            paths["odm_apk"] = ODM_APK_VERSIONS_PATH
            paths["odm_odm2_apk"] = ODM_ODM2_APK_VERSIONS_PATH
            paths["odm_odm_apk"] = ODM_ODM_APK_VERSIONS_PATH
        except:
            print(" TEMS data folder not found ".center(60, "="))
        finally:
            self.paths = paths
    
    def _read_config(self):
        config = ConfigParser()
        config.read(self.paths["config"])
        self.server_url:str = config["DEFAULT"].get("Server_Url") or SERVER_URL
        self.server_name:str = config["DEFAULT"].get("Server_Name") or SERVER_NAME
    
    def get_logger(self, task_name:str, file_name:str|None=None):
        if not file_name:
            if path := self.paths.get(task_name):
                file_name = f"{path}/Log_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f") + ".log"
            else:
                raise Exception(f"No file name provided and no path by name '{task_name}' exists")
        
        logger = logging.getLogger(task_name)
        logger.propagate = False
        handler = logging.FileHandler(file_name, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)-8s]: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        if task_name == "precheck":
            def log(message:str, log_type="info", title=False, report=False):
                if report: 
                    message = "REPORT-GENERATION-" + message
                if title or report:
                    message = f" {message.upper()} ".center(60, "=")
                getattr(logger, log_type)(message)
            logger.log = log
        
        def stop():
            logger.removeHandler(handler)
            handler.close()
        logger.stop = stop
        
        self.loggers[task_name] = logger
        return logger
    
    def __init__(self):
        """
        Initialize the backend service. This also creates and starts `ADBDeviceManager` stored in `self.device_manager`.
        """
        self.is_running = Event()
        self.host_info_loaded = Event()
        self.is_tracking = Event()
        
        self.thread_executor = ThreadPoolExecutor(thread_name_prefix="ants_")
        self._load_paths()
        self._read_config()
        
        self.loggers:dict[str, logging.Logger] = {}
        self.get_logger("network")
        
        self.get_apis()
        
        self.session:Session = Session()
        self.session.verify = False
        
        self.host_device:DeviceInformation|None = None
        self.device_serial_number:str = ""
        self.device_manager = adb.ADBDeviceManager()
        self.device_data = {}
        
        self.repeating_threads:dict[str, BackgroundThread] = {}
        self.repeating_threads["internet"]= BackgroundThread(self._run_internet_connectivity_test, 10)
        for thread in self.repeating_threads.values(): thread.start()
    
    def stop(self, shutdown=False):
        """Stop the backend service and wait until background threads are terminated"""
        self.is_tracking.set()
        self.device_manager.stop()
        
        if shutdown:
            self.is_running.set()
            self.session.close()
        
        self.stop_logging_device_info()
        for thread in self.repeating_threads.values():
            thread.stop()
        self.repeating_threads.clear()
        self.thread_executor.shutdown()
        
        for _,logger in self.loggers.items():
            logger.stop()
        self.is_running.clear()
    
    def load_host_info(self):
        if self.host_info_loaded.is_set(): return
        
        def worker():
            self.host_device = DeviceInformation.fetch()
            self.device_serial_number = self.host_device.device_id
            self.host_info_loaded.set()
        
        Thread(target=worker, daemon=True).start()
    
    def on_host_info_loaded(self, callback):
        self.host_info_loaded.wait()
        callback()
    
    def get_host_info(self):
        self.load_host_info()
        self.host_info_loaded.wait()
        return self.host_device
    
    def start_device_manager(self):
        """Starts tracking devices, storing their data in `self.device_data` when devices are connected
            and clearing their keys when they are removed
        """
        if self.is_tracking.is_set(): return
        self.is_tracking.set()
        self.device_data.clear()
        
        def device_connected(serial, device):
            def convert_size_str(size_in_str:str):
                pat = re.compile(r"(\d+)\s?(\w)b", re.IGNORECASE)
                mat = re.match(pat, size_in_str)
                if mat:
                    size, unit = mat.groups()
                    return get_size_suffix(int(size), unit.upper())
            
            status = device.data
            for k,v in status.items():
                if type(v) == str and v.endswith("kB"):
                    status[k] = convert_size_str(v).upper()
            self.device_data[serial] = status
        
        def device_disconnected(serial, device):
            self.device_data.pop(serial)
        
        self.device_manager.bind(on_connect=device_connected , on_disconnect=device_disconnected)
        self.device_manager.start()
    
    def _run_internet_connectivity_test(self):
        def check_internet_connectivity() -> bool:
            try:
                create_socket_connection(("8.8.8.8", 53), timeout=2)
                return True
            except (OSError) as e:
                return False
        
        while self.is_running.is_set():
            if check_internet_connectivity():
                if not self.repeating_threads["internet"].event.is_set():
                    self.repeating_threads["internet"].event.set()
            else:
                if self.repeating_threads["internet"].event.is_set():
                    self.repeating_threads["internet"].event.clear()
            if self.is_running.wait(timeout=10): break
    
    def get_device_status(self, serial, keys=[]):
        """Get device data for provided device serial with an optional list of the data keys to return"""
        if keys: return {k:v for k,v in self.device_data[serial].items() if k in keys}
        return self.device_data[serial]

    def get_all_device_status(self, keys=[]):
        """Get device data for all connected devices with an optional list of the data keys to return"""
        if keys: return {serial:self.get_device_status(serial, keys) for serial in self.device_data}
        return self.device_data
        
    def get_apis(self):
        """Stores API details in `self.apis`"""
        def get_api(url:str, headers:dict|None=None, payload_keys:list=[]):
            def get_headers(with_authorization:bool=False, authorization_with_bearer:bool=False) -> dict[str,str]:
                headers = {
                    "XApiKey": API_KEY,
                    "Content-Type": "application/json"
                }
                if with_authorization:
                    if authorization_with_bearer: headers["Authorization"] = f"Bearer {AUTHORIZATION_KEY}"
                    else: headers["Authorization"] = AUTHORIZATION_KEY
                return headers
            
            return {
                "url": url,
                "headers": get_headers(headers.get("authorization"), headers.get("bearer")) if headers else get_headers(),
                "payload_keys": payload_keys,
            }
        
        def get_url(api:str, pyapi=False) -> str:
            if pyapi:
                return f"{self.server_url}/pyapi/api/{api}"
            else:
                return f"{self.server_url}/antsapi/api/{api}"
        
        self.apis = {}
        self.apis["login"] = get_api(
            get_url("auth/login"),
            payload_keys=["UserName", "Password", "Deviceidid", "devicetoken", "LoginTime", "AppType"]
        )
        
        self.apis["get_projects"] = get_api(
            get_url("site/GetSitesOfAllProjects"),
            {"authorization":True},
            ["loginid"]
        )
        
        self.apis["get_project_status"] = get_api(
            get_url("python/insertNucDetails"),
            {"authorization":True, "bearer":True},
            ["empid", "SERIALNO", "LSERIALNO", "date", "status", "precheck", "SiteCode"]
        )
        
        self.apis["dtparam"] = get_api(
            get_url("python/GetDtparam"),
            payload_keys= ["SERIALNO", "empid", "sitecode"]
        )
        
        self.apis["pystatus"] = get_api(
            get_url("python/Getpystatus"),
            {"authorization": True},
            ["siteid", "round", "SERIALNO"]
        )
        
        self.apis["get_version"] = get_api(
            get_url("python/getPythonScriptVersion"),
            {"authorization":True},
            ["ScriptName"]
        )
        
        self.apis["upload_deviceinfo"] = get_api(
            get_url("python/deviceinfo?"),
            {"authorization":True},
            ["d_status", "d_id", "d_siteid", "d_serial_num", "d_description", "d_internet_status", "Computer_Name",
            "Computer_Serial_No", "IMEI", "round_id"]
        )
        
        self.apis["upload_precheck"] = get_api(
            get_url("python/PRECHECK?"),
            {"authorization":True},
            ['ADP_NAME', 'SiteClusterCode', 'DriveRoundCode', 'value']
        )
        
        self.apis["script_download"] = get_api(
            get_url("Python/GetscriptList", pyapi=True),
            {"authorization":True},
            ["EMPID", "SLNO"]
        )
        
        self.apis["log_logfile"] = get_api(
            get_url("log/logfile"),
            {"authorization":True},
            ["DATE", "FileSize", "LOGFILE", "MACID", "ROUNDCODE", "SITECODE", "App_Version", "DeviceId"]
        )
        
        self.apis["log_upload"] = get_api(
            get_url("Site/upload", pyapi=True),
            {"authorization":True},
        )
        
        self.apis["count_logs"] = get_api(
            get_url("log/Countlogs", pyapi=True),
            {"authorization": True},
            ["ROUNDCODE", "SITECODE"]
        )
        
        self.apis["count_logs_processed"] = get_api(
            get_url("log/Countlogsprocessed", pyapi=True),
            {"authorization":True},
            ["ROUNDCODE", "SITECODE"]
        )
    
    def call_api(self, api_name:str, /, data=None, values:list|None=None) -> dict|None:
        """Call API from server with provided data.\n
        Available APIs:
            `login`,
            `get_projects`,
            `get_project_status`,
            `dtparam`,
            `pystatus`,
            `get_version`,
            `upload_deviceinfo`,
            `upload_precheck`,
            `script_download`,
            `log_logfile`,
            `log_upload`,
            `count_logs`,
            `count_logs_processed`,
        """
        if api_name not in self.apis:
            print("Invalid API:", api_name)
            return
        
        api = self.apis[api_name]
        if not data:
            if values:
                data = dict(zip(api["payload_keys"], values))
            else:
                print(f"No payload data provided while calling API {api_name}")
                return
        
        try:
            if type(data) == dict:
                response = self.session.post(url=api["url"], headers=api["headers"], json=data)
            else:
                response = self.session.post(url=api["url"], headers=api["headers"], data=data)
            
            if response.status_code == 200:
                self.loggers["network"].info(f"Request sent successfully to {api["url"]} with data: {data}")
                self.loggers["network"].info(f"Response: {response.text}")
                res = response.json()
                res["status"] = "success"
                return res
            else:
                if response.status_code == 400:
                    return {"status": "invalid"}
                self.loggers["network"].error(f"Status Code: {response.status_code}\tBody: {response.text}")
                raise Exception(response.text)
        except Exception as e:
            self.loggers["network"].error(e)
            print(e)
    
    def call_api_async(self, *args, **kwargs) -> dict|None:
        future = self.thread_executor.submit(self.call_api, *args, **kwargs)
        return future.result()
    
    def login(self, username:str, password:str):
        """POST a log-in request with provided user credentials, returning the response text if successful"""
        current_time = datetime.now()
        values = [username, password, DEVICEIDID, DEVICE_TOKEN, str(current_time), "Python"]
        return self.call_api("login", values=values)
    
    def get_projects(self, username:str):
        """Gets all project sites for provided user id"""
        values = [username]
        return self.call_api_async("get_projects", values=values)
    
    def get_site_status(self, userid:str, site_id:str):
        """Gets status of a project provided its site id"""
        date = datetime.now().date()
        values = [userid, self.device_serial_number, self.device_serial_number, str(date), 1, 4, site_id]
        return self.call_api_async("get_project_status", values=values)

    def get_dtparam(self, emp_id:str, site_id:str):
        """Gets DT Params of a site"""
        values = [self.device_serial_number, emp_id, site_id]
        return self.call_api_async("dtparam", values=values)
    
    def get_pystatus(self, site_id:str, drive_round_code:str):
        """Gets status of a site"""
        values = [site_id, drive_round_code, self.device_serial_number]
        return self.call_api_async("pystatus", values=values)
    
    def get_dtparam_and_status(self, emp_id:str, site_id:str):
        """Gets DT Param and status of site, returning it as a tuple of the two responses"""
        dtparam = self.get_dtparam(emp_id, site_id)
        status = self.get_pystatus(site_id, dtparam.get("DriveRoundCode"))
        return (dtparam, status)
    
    def check_version(self):
        """Checks if the version of script is matching"""
        values = [SCRIPT_NAME]
        data = self.call_api_async("get_version", values=values)
        return data["version"] == SCRIPT_VERSION or data["new_version"] == SCRIPT_VERSION
    
    def run_precheck(self):
        """Runs pre-check tests on local device as well as connected mobile handset devices."""
        logger = self.get_logger(task_name="precheck", file_name=f"{self.paths["sysinfo_logs"]}/Log_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f") + ".log")
        
        def log_host_device_info():
            logger.log(f"Computer Name: {self.host_device.device_name}")
            logger.log(f"Computer Serial No.: {self.host_device.device_id}")
            logger.log(f"MAC Address :: {self.host_device.mac}")
            
            uname = platform.uname()
            boot_timestamp = psutil.boot_time()
            system_data = {
                "System": uname.system,
                "Node Name":  self.host_device.device_name,
                "Release": uname.release,
                "Version": uname.version,
                "Machine": uname.machine,
                "Processor": self.host_device.processor,
                "Boot Time": datetime.fromtimestamp(boot_timestamp),
            }
            
            cpufreq = psutil.cpu_freq()
            cpu_usage = {}
            for i,percentage in enumerate(psutil.cpu_percent(percpu=True, interval=1)): cpu_usage[f"Core {i}"] = f"{percentage}%"
            cpu_data = {
                "Physical Cores": self.host_device.physical_cores,
                "Total Cores": self.host_device.total_cores,
                "Max Frequency": f"{cpufreq.max:0.2f} MHz",
                "Min Frequency": f"{cpufreq.min:0.2f} MHz",
                "Current Frequency": f"{cpufreq.current:0.2f} MHz",
                "CPU Usage per Core": cpu_usage,
                "Total CPU Usage": f"{psutil.cpu_percent()}%",
            }
            
            mem = psutil.virtual_memory()
            mem_data = {
                "RAM Total": self.host_device.ram_total,
                "RAM Usable": self.host_device.ram_usable,
                "RAM Used": get_size_suffix(mem.used),
                "RAM Used %": f"{mem.percent}%",
            }
            self.host_device.ram_used = mem_data["RAM Used"]
            
            swap_mem = psutil.swap_memory()
            swap_data = {
                "Total": get_size_suffix(swap_mem.total),
                "Free": get_size_suffix(swap_mem.free),
                "Used": get_size_suffix(swap_mem.used),
                "Used %": f"{swap_mem.percent}%",
            }
            
            disk_data = {}
            partitions = psutil.disk_partitions()
            partition_usages = {partition : psutil.disk_usage(partition.mountpoint) for partition in partitions}
            total,free,used = 0,0,0
            c_drive_available = False
            for partition, partition_use in partition_usages.items():
                if partition.device == "C:\\": c_drive_available = True
                total += partition_use.total
                free += partition_use.free
                used += partition_use.used
                partition_data = {
                    "Mountpoint": partition.mountpoint,
                    "File System Type": partition.fstype,
                    "Size": get_size_suffix(partition_use.total),
                    "Free": get_size_suffix(partition_use.free),
                    "Used": get_size_suffix(partition_use.used),
                    "Used %": f"{partition_use.percent}%",
                }
                disk_data[f"Partition {partition.device}"] = partition_data
            
            if not c_drive_available: disk_data["C:\\"] = "C Drive not available"
            self.host_device.storage_total_int = total
            self.host_device.storage_available_int = free
            self.host_device.storage_used_int = used
            
            self.host_device.storage_total = disk_data["Total Disk Size"] = get_size_suffix(total)
            self.host_device.storage_available = disk_data["Total Disk Free"] = get_size_suffix(free)
            self.host_device.storage_used = disk_data["Total Disk Used"] = get_size_suffix(used)

            disk_io = psutil.disk_io_counters()
            disk_io_data = {
                "Total Read": get_size_suffix(disk_io.read_bytes),
                "Total Write": get_size_suffix(disk_io.write_bytes)
            }
            
            net_data = []
            if_addrs = psutil.net_if_addrs()
            for interface_name, interface_addresses in if_addrs.items():
                for address in interface_addresses:
                    interface_data = {"Interface": interface_name}
                    if address.family == AddressFamily.AF_INET:
                        interface_data["IPv4"] = address.address
                    elif address.family == AddressFamily.AF_INET6:
                        interface_data["IPv6"] = address.address
                    elif address.family == psutil.AF_LINK:
                        interface_data["MAC"] = address.address
                    if address.broadcast: interface_data["Broadcast"] = address.broadcast
                    if address.netmask: interface_data["Netmask"] = address.netmask
                    net_data.append(interface_data)
            
            net_io = psutil.net_io_counters()
            net_io_data = {
                "Total bytes sent": get_size_suffix(net_io.bytes_sent),
                "Total bytes received": get_size_suffix(net_io.bytes_recv),
            }
            
            device_data = {
                "System Information": system_data,
                "CPU Info": cpu_data,
                "Memory Information": mem_data,
                "Swap Memory Information": swap_data,
                "Disk Information": disk_data,
                "Disk I/O Information": disk_io_data,
                "Network Information": net_data,
                "Network I/O Information": net_io_data,
            }
            
            def log_dict_data(data:dict):
                # Helper function to log data in dictionary
                for k,v in data.items():
                    if type(v) == dict:
                        logger.log(f"== {k} ==")
                        log_dict_data(v)
                        logger.log("==========")
                    else:
                        logger.log(f"{k}: {v}")
            
            logger.log("DEVICE BASIC INFORMATION", title=True)
            for header, data in device_data.items():
                logger.log(header, title=True)
                if type(data) == str:
                    logger.log(data)
                elif type(data) == dict:
                    log_dict_data(data)
                elif type(data) == list:
                    for entry in data:
                        log_dict_data(entry)
            logger.log("DEVICE BASIC INFORMATION END", title=True)
            
            return {
                "SYSTEM": system_data["System"],
                "NODE_NAME": self.host_device.device_name,
                "Computer_Serial_No": self.host_device.device_id,
                "PROCESSOR": self.host_device.processor,
                "PHYSICAL_CORE": self.host_device.physical_cores,
                "TOTAL_CORE": self.host_device.total_cores,
                "MAC_ADDRESS": self.host_device.mac,
                "RAM": {
                    "TOTAL": self.host_device.ram_total,
                    "AVAILABLE": self.host_device.ram_usable,
                    "USED": self.host_device.ram_used,
                },
                "DISK": {
                    "TOTAL": self.host_device.storage_total,
                    "AVAILABLE": self.host_device.storage_available,
                    "USED": self.host_device.storage_used,
                }
            }
        
        def log_test(test_name, fn, *args, **kwargs):
            logger.log(f"{test_name}-Test", report=True)
            res = fn(*args, **kwargs)
            logger.log(f"{test_name}-Test-Complete", report=True)
            return res
    
        def log_host_device_tests():
            def check_tems_installation():
                if self.host_device.tems_status:
                    logger.info("Tems is installed")
                else:
                    logger.error("Tems installation missing")
                    print("Tems installation missing")
            
            def disable_firewall():
                try:
                    subprocess.check_call("netsh advfirewall set allprofiles state off")
                    logger.log("Firewall is turned off.")
                    return True
                except:
                    logger.log("Firewall driver not found.")
                    return False
            
            def disable_defender():
                try:
                    services = subprocess.check_output("net start", text=True).strip()
                    if "defender" in services.lower():
                        logger.log("Windows Defender is running. Please turn it off.")
                        return False
                    else:
                        logger.log("Windows Defender is not running.")
                        return True
                except:
                    logger.log("Services not available")
                    return False
            
            def delete_temp_files():
                temp_dir = r"C:\Windows\Temp"
                try:
                    subprocess.check_call(f"del /S /Q /F {temp_dir}\\*.*", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                    logger.log("Success: Cleaned Windows Temp folder.")
                    return True
                except:
                    logger.log("Failed: Unable to clean Windows Temp folder.")
                    return False
            
            def delete_prefetch_files():
                prefetch_dir = r"C:\Windows\Prefetch"
                try:
                    subprocess.check_call(f"del /S /Q /F {prefetch_dir}\\*.*", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                    logger.log("Success: Cleaned Windows Prefetch folder.")
                    return True
                except:
                    logger.log("Failed: Unable to clean Windows Prefetch folder.")
                    return False
            
            def check_device_volume():
                try:
                    logger.log("Playing sound from device. Please check for sound and volume.")
                    
                    winsound.PlaySound("SystemExit", winsound.SND_ALIAS)
                    winsound.PlaySound("*", winsound.SND_ALIAS)
                    
                    logger.log("Speaker driver is working.")
                    return True
                
                except:
                    logger.log("Speaker driver missing.")
                    return False
            
            def disable_uac():
                uac_path = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
                uac_value = subprocess.check_output(rf"reg query {uac_path} /v EnableLUA").strip().split()[-1]
                if uac_value == b'0x0':
                    uac_value = subprocess.check_output(rf"reg query {uac_path} /v EnableLUA").strip().split()[-1]
                    if uac_value == b'0x0':
                        logger.log("Success: UAC is disabled")
                        return True
                    else:
                        logger.log(f"Device UAC Failed: {e}")
                        return False
                    
                try:
                    command1 = rf"reg delete {uac_path} /v EnableLUA /f"
                    proc1 = shell.ShellExecuteEx(lpVerb="runas", lpFile="cmd.exe", lpParameters="/c " + command1, nShow=1)
                    hProc1 = proc1.get("hProcess")
                    if hProc1:
                        win32event.WaitForSingleObject(hProc1, -1)
                    else:
                        logger.log("No valid handle returned for command 1", log_type="warning")
                    
                    command2 = rf"reg add {uac_path} /v EnableLUA /t REG_DWORD /d 0 /f"
                    proc2 = shell.ShellExecuteEx(lpVerb="runas", lpFile="cmd.exe", lpParameters="/c " + command2, nShow=1)
                    hProc2 = proc2.get("hProcess")
                    if hProc2:
                        win32event.WaitForSingleObject(hProc2, -1)
                    else:
                        logger.log("No valid handle returned for command 2", log_type="warning")
                    
                    uac_value = subprocess.check_output(rf"reg query {uac_path} /v EnableLUA").strip().split()[-1]
                    if uac_value == b'0x0':
                        logger.log("Success: UAC is disabled")
                        return True
                    else:
                        logger.log("Fail: UAC is not disabled")
                        return False
                
                except Exception as e:
                    logger.log(f"Error while disabling UAC. Error: {e}")
                    return False
            
            logger.log("LAPTOP DEVICE TEST STARTED", title=True)
            tests = {}
            yield {"status": "Checking TEMS installation"}
            tests["TEMS"] = log_test("TEMS-Files", check_tems_installation)
            
            yield {"status": "Disabling Windows Firewall"}
            tests["Firewall"] = log_test("Windows-Firewall", disable_firewall)
            
            yield {"status": "Disabling Windows Defender"}
            tests["Windows Defender"] = log_test("Windows-Defender", disable_defender)
            
            yield {"status": "Deleting Windows temp files"}
            tests["Temp Folder"] = log_test("Temp-Files-Delete", delete_temp_files)
            
            yield {"status": "Deleting prefetch files"}
            tests["Prefetch Folder"] = log_test("Prefetch-Files-Delete", delete_prefetch_files)
            
            yield {"status": "Playing sound from device. Please check for sound and volume"}
            tests["Laptop Volume"] = log_test("Laptop-Volume-Check", check_device_volume)
            
            yield {"status": "Disabling UAC"}
            tests["UAC"] = log_test("Disable-UAC", disable_uac)
            
            logger.log("LAPTOP TESTS COMPLETED", title=True)
            
            logger.log("Laptop : TEST RESULTS", title=True)
            for test, success in tests.items():
                logger.log(f"TEST :: {test} : {'Success' if success else 'Fail'}")
            logger.log("LAPTOP DEVICE TEST DONE", title=True)
        
        def log_mobile_devices():
            prev_devices = log_test("adb kill-server", self.device_manager.kill_server)
            log_test("adb start-server", self.device_manager.start_server, prev_devices)
            
            devices = self.device_manager.devices

            handset_info = []
            if len(devices) > 0:
                logger.log("Mobile Device Report", title=True)
                for serial,device in devices.items():
                    handset_info.append({
                        "SERIAL NUMBER": serial,
                        "PRODUCT CODE": device.data["model"],
                        "IMEI NUMBER": device.data["imei"],
                    })
                    logger.log(f"DEVICE [{serial}] LOG")
                    logger.log(f"MOBILE {serial} DEVICE TEST STARTED")
                    
                    test_results = device.run_tests()
                    for name, result in test_results.items():
                        logger.log(f"{name}: {result}")
                    logger.log(f"MOBILE {serial} DEVICE TEST DONE")

                logger.log("Mobile Device Report Finished", title=True)
            else:
                logger.log("No mobile devices connected", title=True)
            
            return handset_info
        
        yield {"status": "Logging host device info"}
        laptop_config = log_host_device_info()
        
        yield {"status": "Running host device tests"}
        updates = log_host_device_tests()
        for upd in updates: yield upd
        
        yield {"status": "Running mobile device tests"}
        handset_config = {"ALL_HANDSET_VALUE": log_mobile_devices()}
        
        precheck_data = {
            #"TEMS_INVESTIGATION": TEMS_INVESTIGATION,
            #"TEMS_MEDIATOR": TEMS_MEDIATOR,
            #"TEMS_UDP": TEMS_UDP,
            "LAPTOP_CONFIGURATION": laptop_config,
            "HANDSET_CONFIGURATION": handset_config,
            # "ODM":odm_list
        }
        
        logger.log("Pre-check completed, preparing to upload data.")
        logger.log("To check upload status see the network log")
        logger.stop()
        yield {"status": "Precheck finished", "data": precheck_data}
    
    def upload_precheck_data(self, data:dict):
        """Uploads pre-check data to server
        \n`data` must be a dict with keys 'ADP_NAME', 'SiteClusterCode', 'DriveRoundCode', and 'value'. Pre-check data should be stored under\
        the 'value' key."""
        self.loggers["network"].info(f"Uploading data: {data}")
        res = self.call_api("upload_precheck", data=data)
        return res

    def get_host_status(self):
        """Get local host device status"""
        self.load_host_info()
        ram = psutil.virtual_memory()
        self.host_device.ram_used = get_size_suffix(ram.used)
        self.host_device.ram_used_percent = ram.percent

        partitions = psutil.disk_partitions()
        disk_usages = [psutil.disk_usage(p.device) for p in partitions]
        if not hasattr(self.host_device, "storage_total_int"):
            self.host_device.storage_total_int = sum([d.total for d in disk_usages])
        self.host_device.storage_used_int = sum([d.used for d in disk_usages])
        self.host_device.storage_available_int = sum([d.free for d in disk_usages])
        
        self.host_device.storage_used = get_size_suffix(self.host_device.storage_used_int)
        self.host_device.storage_available = get_size_suffix(self.host_device.storage_available_int)
        self.host_device.storage_available_percent = self.host_device.storage_available_int / self.host_device.storage_total_int * 100
        self.host_device.storage_used_percent = self.host_device.storage_used_int / self.host_device.storage_total_int * 100
        
        battery_info = psutil.sensors_battery()
        self.host_device.battery = battery_info.percent
        self.host_device.charging = battery_info.power_plugged
        
        return self.host_device
    
    def get_file_download(self):
        """Get TI Script file download"""
        values = [self.device_serial_number, self.device_serial_number]
        resp = self.call_api("script_download", values=values)
        
        if resp:
            filepath = resp["FilePath"]
            filename = resp["FileName"]
            
            url_check = self.session.head(filepath, allow_redirects=True, verify=False)

            if url_check.status_code != 200:
                return {"status": "Error", "details": f"URL not accessible: {filepath}"}
            
            file_data = self.session.get(filepath).content
            newfile_path = self.paths["ti_scripts"].joinpath(filename)
            with open(newfile_path, "wb") as f:
                f.write(file_data)
            
            return {"status": "Success", "details": f"Downloaded: {filename}"}
        
        else:
            return {"status": "Error", "details": "No file available to download"}

    def upload_logs(self, dtparam:dict, callback):
        """Upload TI Logs to server"""
        if not self.paths["ti_logs"].exists() or not any(self.paths["ti_logs"].iterdir()):
            return
        
        server_dir = Path("Quarantine").joinpath(dtparam["RegionCode"], dtparam["ProjectADPNameCode"], "MFOLDER",
                        f"{dtparam["SiteClusterCode"]}_{dtparam["DriveRoundCode"]}")
        
        date = datetime.now().strftime("%Y-%m-%d")
        for file in self.paths["ti_logs"].iterdir():
            if file.suffix not in LOGFILE_EXTENSIONS: continue
            file_size = file.stat().st_size
            
            values = [date, file_size, file.name, self.host_device.mac, dtparam["DriveRoundCode"],
                        dtparam["SiteClusterCode"], SCRIPT_VERSION, self.device_serial_number]
            reg_resp = self.call_api("log_logfile", values=values)
            
            if reg_resp and reg_resp.get("status") == "success":
                upload_path = server_dir.joinpath(file.name)
                
                with open(file, "rb") as f:
                    encoder = MultipartEncoder(
                        fields={
                            "despathh": str(upload_path),
                            "file": (file.name, f, "application/octet-stream")
                        }
                    )
                    monitor = MultipartEncoderMonitor(encoder, callback)
                    
                    self.apis["log_upload"]["headers"]["Content-Type"] = monitor.content_type
                    log_resp = self.call_api("log_upload", data=monitor)
                    
                    #yield log_resp

    def get_log_count(self, site_code, round_code) -> dict:
        """Get total count of logs processed and uploaded. Returned as a dictionary with keys `logs_generated` and
        `logs_uploaded`"""
        values = [round_code, site_code]
        resp_generated = self.call_api("count_logs", values=values)
        resp_uploaded = self.call_api("count_logs_processed", values=values)
        
        logs_generated = resp_generated.get("count")
        logs_uploaded = resp_uploaded.get("count")
        return {"logs_generated":logs_generated, "logs_uploaded":logs_uploaded}
    
    def upload_device_info(self, serial:str, device:adb.ADBDevice, d_status, d_id, round_id):
        """
        Upload mobile device information to server.\n
        Arguments
        \t`d_status`: "0" for disconnected device, "1" for connected device
        \t`d_id`: Site ID
        \t`round_id`: Drive Round Code
        """
        
        device_internet_connection = device.check_internet_connection() if d_status == "1" else "0"
        device_description = f"Serial_Number: {serial}\nMobile_Imei: {device.data["imei"]}\nModel: {device.data["model"]}\n"\
        f"Device: {device.data["device"]}\nBrand: {device.data["brand"]}\nAndroid_OS: {device.data["os_version"]}\n"\
        f"Internet: {device_internet_connection}"
        
        data = {
            "d_status": d_status,
            "d_id": d_id,
            "d_siteid": d_id,
            "d_serial_num": serial,
            "d_description": device_description,
            "d_internet_status": device_internet_connection,
            "Computer_Name": self.host_device.device_name,
            "Computer_Serial_No": self.host_device.device_id,
            "IMEI": device.data["imei"],
            "round_id": round_id
        }
        print(f"Uploading data: {data}")
        self.call_api("upload_deviceinfo", data=data)
    
    def start_logging_device_info_to_server(self, site_id, round_id):
        """
        Bind to device_manager's `on_connected` and `on_disconnected`, to log device information.
        """
        self.upload_connected_device_info = lambda serial, device: self.upload_device_info(serial, device, d_status="1", d_id=site_id, round_id=round_id)
        self.upload_disconnected_device_info = lambda serial, device: self.upload_device_info(serial, device, d_status="0", d_id=site_id, round_id=round_id)
        for serial,device in self.device_manager.devices.items():
            self.upload_connected_device_info(serial, device)
        self.device_manager.bind(on_connect=self.upload_connected_device_info, on_disconnect=self.upload_disconnected_device_info)        

    def stop_logging_device_info(self):
        if hasattr(self, "upload_connected_device_info"):
            self.device_manager.unbind(self.upload_connected_device_info, self.upload_disconnected_device_info)
        self.upload_connected_device_info, self.upload_disconnected_device_info = None, None
    

if __name__ == "__main__": ANTSBackendService()