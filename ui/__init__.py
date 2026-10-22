import os
from kivy.lang import Builder

kv_dir = os.path.join(os.path.dirname(__file__), "screens")

for file in os.listdir(kv_dir):
    if file.endswith(".kv"):
        Builder.load_file(os.path.join(kv_dir, file), rulesonly=True)

from .LoginScreen import *
from .NodeStatus import *
from .LogUpload import *