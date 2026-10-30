#!/usr/bin/env python3
#** *****************************************************************************
# *
# * If not stated otherwise in this file or this component's LICENSE file the
# * following copyright and licenses apply:
# *
# * Copyright 2025 RDK Management
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# * http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.
# *
#* ******************************************************************************

import tkinter as Tkinter
import tkinter.font as tkFont
import tkinter.ttk as ttk

class Picker(ttk.Frame):

    def __init__(self, master=None,activebackground='#b1dcfb',values=[],entry_wid=None,activeforeground='black', selectbackground='#003eff', selectforeground='white', command=None, borderwidth=1, relief="solid"):

        self._selected_item = None

        self._values = values

        self._entry_wid = entry_wid

        self._sel_bg = selectbackground
        self._sel_fg = selectforeground

        self._act_bg = activebackground
        self._act_fg = activeforeground

        self._command = command
        ttk.Frame.__init__(self, master, borderwidth=borderwidth, relief=relief)

        self.bind("<FocusIn>", lambda event:self.event_generate('<<PickerFocusIn>>'))
        self.bind("<FocusOut>", lambda event:self.event_generate('<<PickerFocusOut>>'))

        self._font = tkFont.Font()

        self.dict_checkbutton = {}
        self.dict_checkbutton_var = {}
        self.dict_intvar_item = {}

        for index,item in enumerate(self._values):

            self.dict_intvar_item[item] = Tkinter.IntVar()
            self.dict_checkbutton[item] = ttk.Checkbutton(self, text = item, variable=self.dict_intvar_item[item],command=lambda ITEM = item:self._command(ITEM))
            self.dict_checkbutton[item].grid(row=index, column=0, sticky=Tkinter.NSEW)
            self.dict_intvar_item[item].set(0)


class Combopicker(ttk.Entry, Picker):
    def __init__(self, master, values= [] ,entryvar=None, entrywidth=None, entrystyle=None, onselect=None, activebackground='#b1dcfb', activeforeground='black', selectbackground='#003eff', selectforeground='white', borderwidth=1, relief="solid"):

        if entryvar is not None:
            self.entry_var = entryvar
        else:
            self.entry_var = Tkinter.StringVar()

        entry_config = {}
        if entrywidth is not None:
            entry_config["width"] = entrywidth

        if entrystyle is not None:
            entry_config["style"] = entrystyle

        ttk.Entry.__init__(self, master, textvariable=self.entry_var, **entry_config, state = "readonly", font=("Segoe UI", 10))

        self._is_menuoptions_visible = False

        self.picker_frame = Picker(self.winfo_toplevel(), values=values,entry_wid = self.entry_var,activebackground=activebackground, activeforeground=activeforeground, selectbackground=selectbackground, selectforeground=selectforeground, command=self._on_selected_check)

        self.bind_all("<1>", self._on_click, "+")

        self.bind("<Escape>", lambda event: self.hide_picker())

    @property
    def get_selected_string(self):
        try:
            value = self.entry_var.get()
            return value
        except ValueError:
            return None

    def get_selected_list(self):
        value = []
        if self.entry_var.get() != "" and self.entry_var.get() != None:
            temp_value = self.entry_var.get()
            value = temp_value.split(",")
        return value

    #@current_value.setter
    #def current_value(self, INDEX):
    #    self.entry_var.set(values.index(INDEX))

    def _on_selected_check(self, SELECTED):
        value = []
        if self.entry_var.get() != "" and self.entry_var.get() != None:
            temp_value = self.entry_var.get()
            value = temp_value.split(",")

        if str(SELECTED) in value:
            value.remove(str(SELECTED))

        else:
            value.append(str(SELECTED))

        value.sort()

        temp_value = ""
        for index,item in enumerate(value):
            if item!= "":
                if index != 0:
                    temp_value += ","
                temp_value += str(item)

        self.entry_var.set(temp_value)

    def _on_click(self, event):
        str_widget = str(event.widget)

        if str_widget == str(self):
            if not self._is_menuoptions_visible:
                self.show_picker()
        else:
            if not str_widget.startswith(str(self.picker_frame)) and self._is_menuoptions_visible:
                self.hide_picker()

    def show_picker(self):
        if not self._is_menuoptions_visible:
            self.picker_frame.place(in_=self, relx=0, rely=1, relwidth=1 )
            self.picker_frame.lift()

        self._is_menuoptions_visible = True

    def hide_picker(self):
        if self._is_menuoptions_visible:
            self.picker_frame.place_forget()

        self._is_menuoptions_visible = False

if __name__ == "__main__":
    import sys

    try:
        from Tkinter import Tk, Frame, Label
    except ImportError:
        from tkinter import Tk, Frame, Label

    root = Tk()
    root.geometry("500x600")

    main =Frame(root, pady =15, padx=15)
    main.pack(expand=True, fill="both")

    Label(main, justify="left", text=__doc__).pack(anchor="w", pady=(0,15))

    COMBOPICKER1 = Combopicker(main, values = [1, 2, 3, 4, 5, 6, 7, 8])
    COMBOPICKER1.pack(anchor="w")

    if 'win' not in sys.platform:
        style = ttk.Style()
        style.theme_use('clam')

    root.mainloop()
