from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Rectangle, Line, PushMatrix, PopMatrix, Rotate
from kivy.clock import Clock
from kivy.properties import NumericProperty, ListProperty, BooleanProperty
from kivy.graphics.texture import Texture


class CircularLoader(Widget):
    angle = NumericProperty(0)
    radius = NumericProperty(8)
    width = NumericProperty(2)
    color = ListProperty([1,1,1,1])
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        with self.canvas:
            PushMatrix()
            self.rot = Rotate(origin=self.center, axis=(0,0,-1))
            
            self.color_instruction = Color(*self.color)
            self.arc = Line(
                circle= self.get_dimensions(),
                width= self.width,
                cap='round',
            )
            PopMatrix()
        
        self.bind(pos=self.update_canvas, size=self.update_canvas, color=self.update_color)
        self._event = None
        self.bind(opacity=self.on_loader_visible)
    
    def get_dimensions(self):
        return (self.center_x, self.center_y, self.radius, self.angle, self.angle+210)
    
    def start(self):
        self._event = Clock.schedule_interval(self.update, 1/60)
    
    def stop(self):
        if self._event: self._event.cancel()
        self.reset()
    
    def on_loader_visible(self, instance, value):
        if value > 0: self.start()
        else: self.stop()
    
    def update_canvas(self, *args):
        self.rot.origin = self.center
        self.arc.circle = self.get_dimensions()
    
    def update_color(self, *args):
        self.color_instruction.rgba = self.color
    
    def update(self, dt):
        self.angle += 5
        self.rot.angle = self.angle
    
    def reset(self):
        self.angle = 0
        self.rot.angle = self.angle

class LoadingOverlay(FloatLayout):
    visible = BooleanProperty(False)
    
    size_hint= (None, None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        with self.canvas.before:
            self.bg_color = Color(0,0,0,0.5)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg)
        
        self.loader = CircularLoader(
            size_hint= (None,None),
            size=(120,120),
            pos_hint={"center_x":0.5, "center_y":0.5}
        )
        self.add_widget(self.loader)
        self.opacity = 0
    
    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
    
    def show(self):
        self.visible = True
        self.opacity = 1
    
    def hide(self):
        self.visible = False
        self.opacity = 0
