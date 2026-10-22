class EventHandler:
    def __init__(self, *args):
        self.connections:dict[str, list[function]] = dict.fromkeys(args, [])
    
    def dispatch(self, event, *args):
        for fn in self.connections[event]:
            fn(*args)
    
    def bind(self, **kwargs):
        for key, fn in kwargs.items():
            if key not in self.connections:
                raise Exception(f"No such event exists: {key}\nEvent list: {self.connections.keys()}")
            self.connections[key].append(fn)
    
    def unbind(self, *args):
        if args:
            for fn in args:
                for conn, connected_fns in self.connections.items():
                    if fn in connected_fns:
                        self.connections[conn].remove(fn)
        else:
            for key in self.connections.keys():
                self.connections[key].clear()