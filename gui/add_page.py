import logging
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

class AddPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing AddPage")

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Додавання нового обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=20, pady=10)

        self.entries = {}

        fields = [
            ("Інвентарний номер", "inventory_number", ctk.CTkEntry),
            ("Тип", "type", ctk.CTkComboBox),
            ("Назва", "name", ctk.CTkEntry),
            ("Модель", "model", ctk.CTkEntry),
            ("Серійний номер", "serial_number", ctk.CTkEntry),
            ("Кабінет", "room", ctk.CTkComboBox),
            ("Власник", "owner", ctk.CTkComboBox)
        ]

        for label_text, field_key, widget_class in fields:
            if field_key in ["type", "room", "owner"]:
                field_frame = ctk.CTkFrame(container)
                field_frame.pack(fill="x", pady=(5, 5))
                lbl = ctk.CTkLabel(field_frame, text=label_text)
                lbl.pack(side="left", padx=5)
                if widget_class == ctk.CTkComboBox:
                    if field_key == "type":
                        types = [''] + self.db.get_all_types()
                        ent = ctk.CTkComboBox(field_frame, values=types)
                        ent.set('')
                    elif field_key == "room":
                        rooms = [''] + self.db.get_all_rooms()
                        ent = ctk.CTkComboBox(field_frame, values=rooms)
                        ent.set('')
                    elif field_key == "owner":
                        owners = [''] + self.db.get_all_owners()
                        ent = ctk.CTkComboBox(field_frame, values=owners)
                        ent.set('')
                else:
                    ent = widget_class(field_frame)
                ent.pack(side="left", fill="x", expand=True)
                if field_key == "type":
                    page = "TypesManagementPage"
                elif field_key == "room":
                    page = "RoomsManagementPage"
                elif field_key == "owner":
                    page = "OwnersManagementPage"
                btn = ctk.CTkButton(field_frame, text="Керувати", width=100,
                                    command=lambda p=page: self.open_management_page(p))
                btn.pack(side="left", padx=5)
            else:
                lbl = ctk.CTkLabel(container, text=label_text)
                lbl.pack(anchor="w", pady=(5,0))
                ent = widget_class(container)
                ent.pack(fill="x")
            self.entries[field_key] = ent

        btn_add = ctk.CTkButton(self, text="Додати", command=self.add_equipment)
        btn_add.pack(pady=10)

        self.status = ctk.CTkLabel(self, text="")
        self.status.pack(pady=10)

    def open_management_page(self, page_name):
        try:
            self.controller.switch_page(page_name)
            logging.debug(f"Opened management page: {page_name}")
        except Exception as e:
            logging.error(f"Error opening management page {page_name}: {e}")
            self.status.configure(text=f"Помилка відкриття сторінки керування: {str(e)}")

    def add_equipment(self):
        try:
            data = {key: self.entries[key].get().strip() for key in self.entries}
            data['written_off'] = 0
            if data['inventory_number'] == "":
                self.status.configure(text="Інвентарний номер обов'язковий")
                logging.error("Empty inventory number in add_equipment")
                return
            try:
                if self.db.add_equipment(data):
                    self.status.configure(text="Обладнання додано")
                    self.controller.refresh_pages()
                    self.clear_form()
                    logging.debug("Equipment added successfully")
                else:
                    self.status.configure(text="Обладнання з таким інвентарним номером вже існує")
                    logging.error("Equipment with this inventory number already exists")
            except ValueError as e:
                self.status.configure(text=str(e))
                logging.error(f"ValueError in add_equipment: {e}")
        except Exception as e:
            logging.error(f"Error in add_equipment: {e}")
            self.status.configure(text=f"Помилка додавання обладнання: {str(e)}")

    def clear_form(self):
        try:
            for widget in self.entries.values():
                if isinstance(widget, ctk.CTkComboBox):
                    widget.set('')
                else:
                    widget.delete(0, tk.END)
            logging.debug("AddPage form cleared")
        except Exception as e:
            logging.error(f"Error in clear_form: {e}")
            self.status.configure(text=f"Помилка очищення форми: {str(e)}")

    def refresh(self):
        try:
            self.entries['type'].configure(values=[''] + self.db.get_all_types())
            self.entries['room'].configure(values=[''] + self.db.get_all_rooms())
            self.entries['owner'].configure(values=[''] + self.db.get_all_owners())
            logging.debug("AddPage refreshed")
        except Exception as e:
            logging.error(f"Error in refresh: {e}")
            self.status.configure(text=f"Помилка оновлення: {str(e)}")
