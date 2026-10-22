from kivy.core.window import Window
from kivy.properties import ListProperty, NumericProperty, BooleanProperty
from kivy.graphics import Color, RoundedRectangle, BoxShadow, Line

class HoverBehavior(object):
    isHovering = BooleanProperty(False)

    def __init__(self, **kwargs):
        super(HoverBehavior, self).__init__(**kwargs)
        Window.bind(mouse_pos=self.on_mouseover)
    
    def on_mouseover(self, window, pos):
        if not self.get_root_window(): return
        inside = self.collide_point(*pos)

        if self.isHovering != inside:
            self.isHovering = inside
            if inside: self.on_enter()
            else: self.on_leave()
    
    def on_enter(self): pass
    def on_leave(self): pass

class RoundedBase(object):
    bg_color = ListProperty([])
    radius = NumericProperty(0)
    border_color = ListProperty([])
    border_width = NumericProperty(0)
    show_shadow = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if hasattr(self, "background_color"): self.background_color = (0,0,0,0)
        if hasattr(self, "background_normal"): self.background_normal = ""
        if hasattr(self, "background_down"): self.background_down = ""
        
        self.shadow = None
        self.border_rounded = None
       
        with self.canvas.before:
            self.bg_color_instruction = Color(rgba=self.bg_color)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])

            if self.show_shadow:
                self.shadow = BoxShadow(pos=self.pos, size=self.size, border_radius=[self.radius]*4, blur_radius=self.radius)

            if self.border_width>0:
                self.border_color_instruction = Color(rgba=self.border_color)
                self.border_rounded = Line(
                    rounded_rectangle=(*self.pos, *self.size, self.radius),
                    width=self.border_width
                )
        
        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            radius=self._update_canvas,
            border_width=self._update_canvas,
            show_shadow=self._update_canvas,
            bg_color=self._update_color,
            border_color=self._update_border_color,
        )
    
    def _update_canvas(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
        self.bg.radius = [self.radius]

        if self.shadow:
            self.shadow.pos = self.pos
            self.shadow.size = self.size
            self.shadow.border_radius = [self.radius]*4
            self.shadow.blur_radius = self.radius
        elif self.show_shadow:
            self.shadow = BoxShadow(pos=self.pos, size=self.size, border_radius=[self.radius]*4, blur_radius=self.radius)

        if self.border_rounded:
            self.border_rounded.rounded_rectangle = (*self.pos, *self.size, self.radius)
        elif self.border_width > 0:
            self.border_color_instruction = Color(rgba=self.border_color)
            self.border_rounded = Line(
                rounded_rectangle=(*self.pos, *self.size, self.radius),
                width=self.border_width
            )
    
    def _update_color(self, *args):
        self.bg_color_instruction.rgba = self.bg_color
    
    def _update_border_color(self, *args):
        self.border_color_instruction.rgba = self.border_color