from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, ListProperty
from kivy.graphics import Color, Line

class CircularProgressBar(object):
    bg_color = ListProperty([0,0,0,1])
    arc_color = ListProperty([1,1,1,1])
    circle_width = NumericProperty(4)
    value = NumericProperty(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        with self.canvas:
            self.bg_color_instruction = Color(self.bg_color)
            self.bg = Line(
                circle=self.get_bg_dimensions(),
                width=self.circle_width,
            )
            self.arc_color_instruction = Color(self.arc_color)
            self.arc = Line(
                circle=self.get_arc_dimensions(),
                width=self.circle_width,
                joint="round",
            )
        self.bind(
            value=self.update_value,
            pos=self.update_canvas,
            size=self.update_canvas,
            center=self.update_canvas,
            circle_width=self.update_circle_width,
            bg_color=self.update_bg_color,
            arc_color=self.update_arc_color
        )
        
    def get_bg_dimensions(self):
        return (self.center_x, self.center_y, min(self.size)/2)

    def get_arc_dimensions(self):
        return self.get_bg_dimensions() + (0, self.value*3.6)
    
    def update_value(self, *args):
        self.arc_color_instruction.a = 0 if self.value == 0 else 1
        self.arc.circle = self.get_arc_dimensions()
    
    def update_canvas(self, *args):
        self.bg.circle = self.get_bg_dimensions()
        self.arc.circle = self.get_arc_dimensions()
    
    def update_circle_width(self, *args):
        self.bg.width = self.circle_width
        self.arc.width = self.circle_width
    
    def update_bg_color(self, *args):
        self.bg_color_instruction.rgba = self.bg_color
    
    def update_arc_color(self, *args):
        self.arc_color_instruction.rgba = self.arc_color


class CircularProgressBarBoxLayout(CircularProgressBar, BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class CircularProgressBarWidget(CircularProgressBar, Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
