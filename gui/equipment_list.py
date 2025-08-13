import logging
import customtkinter as ctk
from tkinter import messagebox

class EquipmentListPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        self.current_room = None
        logging.debug("Initializing EquipmentListPage")
        self.create_widgets()
        logging.debug("Frame created: EquipmentListPage")

    def create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Список обладнання", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=10, padx=10, sticky="w")

        self.filter_frame = ctk.CTkFrame(self)
        self.filter_frame.grid(row=0, column=1, pady=10, padx=10, sticky="e")

        ctk.CTkLabel(self.filter_frame, text="Фільтр за кабінетом:").grid(row=0, column=0, padx=5)
        self.room_filter_var = ctk.StringVar(value="---")
        self.room_filter = ctk.CTkOptionMenu(self.filter_frame, variable=self.room_filter_var, values=["---"] + self.db.get_all_rooms(),
                                             command=self.update_list)
        self.room_filter.grid(row=0, column=1, padx=5)

        ctk.CTkLabel(self.filter_frame, text="Фільтр за власником:").grid(row=0, column=2, padx=5)
        self.owner_filter_var = ctk.StringVar(value="---")
        self.owner_filter = ctk.CTkOptionMenu(self.filter_frame, variable=self.owner_filter_var, values=["---"] + self.db.get_all_owners(),
                                              command=self.update_list)
        self.owner_filter.grid(row=0, column=3, padx=5)

        self.equipment_listbox = ctk.CTkTextbox(self, width=600, height=400)
        self.equipment_listbox.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, columnspan=2, pady=10)

        self.view_button = ctk.CTkButton(self.button_frame, text="Переглянути", command=self.view_selected)
        self.view_button.grid(row=0, column=0, padx=5)

        self.edit_button = ctk.CTkButton(self.button_frame, text="Редагувати", command=self.edit_selected)
        self.edit_button.grid(row=0, column=1, padx=5)

        self.write_off_button = ctk.CTkButton(self.button_frame, text="Списати", command=self.write_off_selected)
        self.write_off_button.grid(row=0, column=2, padx=5)

        self.back_button = ctk.CTkButton(self.button_frame, text="Назад", command=lambda: self.controller.switch_page("MainMenu"))
        self.back_button.grid(row=0, column=3, padx=5)

        self.update_list()

    def set_filter(self, room=None):
        self.current_room = room
        self.room_filter_var.set(room if room else "---")
        self.update_list()

    def clear_filter(self):
        self.current_room = None
        self.room_filter_var.set("---")
        self.owner_filter_var.set("---")
        self.update_list()

    def update_list(self, *args):
        try:
            self.equipment_listbox.delete("0.0", "end")
            equipment = self.db.filter_equipment(room=self.current_room or self.room_filter_var.get(),
                                                 owner=self.owner_filter_var.get())
            for item in equipment:
                text = f"ID: {item['id']} | {item['inventory_number']} | {item['type']} | {item['name']} | {item['room']} | {item['owner']}\n"
                self.equipment_listbox.insert("end", text)
            logging.debug("Equipment list updated")
        except Exception as e:
            logging.error(f"Error updating equipment list: {e}")

    def view_selected(self):
        try:
            selected = self.equipment_listbox.get("sel.first", "sel.last")
            equip_id = int(selected.split(" | ")[0].split(": ")[1])
            self.controller.frames["EquipmentCardPage"].load_equipment(equip_id)
            self.controller.switch_page("EquipmentCardPage")
        except Exception as e:
            logging.error(f"Error in view_selected: {e}")
            messagebox.showerror("Помилка", "Оберіть обладнання зі списку")

    def edit_selected(self):
        try:
            selected = self.equipment_listbox.get("sel.first", "sel.last")
            equip_id = int(selected.split(" | ")[0].split(": ")[1])
            self.controller.frames["AddPage"].load_equipment(equip_id)
            self.controller.switch_page("AddPage")
        except Exception as e:
            logging.error(f"Error in edit_selected: {e}")
            messagebox.showerror("Помилка", "Оберіть обладнання зі списку")

    def write_off_selected(self):
        try:
            selected = self.equipment_listbox.get("sel.first", "sel.last")
            equip_id = int(selected.split(" | ")[0].split(": ")[1])
            self.db.write_off_equipment(equip_id)
            self.update_list()
            messagebox.showinfo("Успіх", "Обладнання списано")
        except Exception as e:
            logging.error(f"Error in write_off_selected: {e}")
            messagebox.showerror("Помилка", "Оберіть обладнання зі списку")

    def refresh(self):
        try:
            self.room_filter.configure(values=["---"] + self.db.get_all_rooms())
            self.owner_filter.configure(values=["---"] + self.db.get_all_owners())
            self.update_list()
            logging.debug("EquipmentListPage refreshed")
        except Exception as e:
            logging.error(f"Error refreshing EquipmentListPage: {e}")
            self.update_list()