from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty

class IconTextInput(BoxLayout):
    input_widget = ObjectProperty(None)
    icon_source = StringProperty("")
    text = StringProperty("")
    hint_text = StringProperty("")
    password = BooleanProperty(False)
    show_password = BooleanProperty(False)
    focused = BooleanProperty(False)