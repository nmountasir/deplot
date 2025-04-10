import customtkinter
from typing import Union, Callable

class FloatSpinbox(customtkinter.CTkFrame):
    def __init__(self, *args,
                 width: int = 100,
                 height: int = 32,
                 step_size: Union[int, float] = 1,
                 from_: Union[int, float] = float('-inf'),
                 to: Union[int, float] = float('inf'),
                 command: Callable = None,
                 textvariable: customtkinter.StringVar = None,
                 **kwargs):
        super().__init__(*args, width=width, height=height, **kwargs)

        self.step_size = step_size
        self.from_ = from_
        self.to = to
        self.command = command
        self.textvariable = textvariable

        self.configure(fg_color=("gray78", "gray28"))  # set frame color

        self.grid_columnconfigure((0, 2), weight=0)  # buttons don't expand
        self.grid_columnconfigure(1, weight=1)  # entry expands

        self.subtract_button = customtkinter.CTkButton(self, text="-", width=height-6, height=height-6,
                                                       command=self.subtract_button_callback)
        self.subtract_button.grid(row=0, column=0, padx=(3, 0), pady=3)

        self.entry = customtkinter.CTkEntry(self, width=width-(2*height), height=height-6, border_width=0, textvariable=self.textvariable, validate="key", validatecommand=(self.register(self.validate_entry), '%P'))
        self.entry.grid(row=0, column=1, columnspan=1, padx=3, pady=3, sticky="ew")

        self.add_button = customtkinter.CTkButton(self, text="+", width=height-6, height=height-6,
                                                  command=self.add_button_callback)
        self.add_button.grid(row=0, column=2, padx=(0, 3), pady=3)

        # Bind events
        self.entry.bind("<FocusOut>", self.on_focusout)
        self.entry.bind("<Return>", self.on_return)

        # default value
        if self.textvariable is None:
            self.entry.insert(0, "0.0")

    def validate_entry(self, value_if_allowed):
        if value_if_allowed == "":
            return True
        try:
            float(value_if_allowed)
            return True
        except ValueError:
            return False

    def add_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            value = float(self.entry.get()) + self.step_size
            if value <= self.to:
                self.entry.delete(0, "end")
                self.entry.insert(0, value)
        except ValueError:
            return

    def subtract_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            value = float(self.entry.get()) - self.step_size
            if value >= self.from_:
                self.entry.delete(0, "end")
                self.entry.insert(0, value)
        except ValueError:
            return

    def on_focusout(self, event):
        if self.command is not None:
            self.command()

    def on_return(self, event):
        if self.command is not None:
            self.command()

    def get(self) -> Union[float, None]:
        try:
            return float(self.entry.get())
        except ValueError:
            return None

    def set(self, value: float):
        if self.from_ <= value <= self.to:
            self.entry.delete(0, "end")
            self.entry.insert(0, str(float(value)))


class IntSpinbox(FloatSpinbox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            value = int(self.entry.get()) + int(self.step_size)
            if value <= self.to:
                self.entry.delete(0, "end")
                self.entry.insert(0, value)
        except ValueError:
            return

    def subtract_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            value = int(self.entry.get()) - int(self.step_size)
            if value >= self.from_:
                self.entry.delete(0, "end")
                self.entry.insert(0, value)
        except ValueError:
            return

    def get(self) -> Union[int, None]:
        try:
            return int(self.entry.get())
        except ValueError:
            return None

    def set(self, value: int):
        if self.from_ <= value <= self.to:
            self.entry.delete(0, "end")
            self.entry.insert(0, str(int(value)))
