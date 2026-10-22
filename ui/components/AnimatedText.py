from kivy.uix.label import Label 
from kivy.clock import Clock
from kivy.properties import StringProperty

class AnimatedText(Label):
    full_text = StringProperty("")
    index = 0

    def on_parent(self, *args):
        self.start_animation()
    
    def start_animation(self, *args):
        self.text = ""
        self.index = 0
        self._event = Clock.schedule_interval(self.type_text, 0.08)
    
    def type_text(self, dt):
        if self.index < len(self.full_text):
            self.text += self.full_text[self.index]
            self.index += 1
        else:
            self._event.cancel()
            Clock.schedule_once(self.start_animation, 3)
    
    def on_leave(self):
        self._event.cancel()