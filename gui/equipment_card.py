import logging
import customtkinter as ctk
from tkinter import messagebox

class EquipmentCardPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        self.current_id = None
        logging.debug("Initializing EquipmentCardPage")

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Картка обладнання", font=ctk.CTkFont(size=18, weight="bold"))
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
                        ent = ctk.CTkComboBox(field_frame, values=[''] + self.db.get_all_types())
                        ent.set('')
                    elif field_key == "room":
                        ent = ctk.CTkComboBox(field_frame, values=[''] + self.db.get_all_rooms())
                        ent.set('')
                    elif field_key == "owner":
                        ent = ctk.CTkComboBox(field_frame, values=[''] + self.db.get_all_owners())
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
                btn = ctk.CTkButton(field_frame, text="Керувати", width=100, command=lambda p=page: self.controller.switch_page(p))
                btn.pack(side="left", padx=5)
            else:
                lbl = ctk.CTkLabel(container, text=label_text)
                lbl.pack(anchor="w", pady=(5,0))
                ent = widget_class(container)
                ent.pack(fill="x")
            self.entries[field_key] = ent

        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", pady=15)

        self.btn_to_stock = ctk.CTkButton(bottom, text="На склад", command=self.move_to_stock)
        self.btn_to_stock.pack(side="left", expand=True, padx=20)

        self.btn_write_off = ctk.CTkButton(bottom, text="Списати", command=self.write_off)
        self.btn_write_off.pack(side="left", expand=True, padx=20)

        self.btn_save = ctk.CTkButton(bottom, text="Зберегти", command=self.save_equipment)
        self.btn_save.pack(side="left", expand=True, padx=20)

        self.status = ctk.CTkLabel(self, text="")
        self.status.pack(pady=10)

    def load_equipment(self, equip_id):
        self.current_id = equip_id
        row = self.db.get_equipment_by_id(equip_id)
        if not row:
            self.status.configure(text="Обладнання не знайдено")
            logging.error(f"Equipment not found: ID {equip_id}")
            return
        for key in self.entries:
            widget = self.entries[key]
            value = row[key] or ''
            if isinstance(widget, ctk.CTkComboBox):
                widget.set(value)
            else:
                widget.delete(0, tk.END)
                widget.insert(0, value)
        logging.debug(f"Equipment loaded: ID {equip_id}")

    def collect_data(self):
        data = {key: self.entries[key].get().strip() for key in self.entries}
        data['written_off'] = 0
        return data

    def save_equipment(self):
        if self.current_id is None:
            self.status.configure(text="Обладнання не вибрано")
            logging.error("No equipment selected for saving")
            return
        data = self.collect_data()
        if data['inventory_number'] == '':
            self.status.configure(text="Інвентарний номер не може бути порожнім")
            logging.error("Empty inventory number in save_equipment")
            return
        try:
            self.db.update_equipment(self.current_id, data)
            self.controller.refresh_pages()
            self.status.configure(text="Зміни збережено")
            logging.debug(f"Equipment saved: ID {self.current_id}")
        except ValueError as e:
            self.status.configure(text=str(e))
            logging.error(f"ValueError in save_equipment: {e}")

    def move_to_stock(self):
        if self.current_id is None:
            self.status.configure(text="Обладнання не вибрано")
            logging.error("No equipment selected for move_to_stock")
            return
        data = self.collect_data()
        data['room'] = "Склад"
        try:
            self.db.update_equipment(self.current_id, data)
            self.controller.refresh_pages()
            self.status.configure(text="Обладнання переміщено на склад")
            logging.debug(f"Equipment moved to stock: ID {self.current_id}")
        except ValueError as e:
            self.status.configure(text=str(e))
            logging.error(f"ValueError in move_to_stock: {e}")

    def write_off(self):
        if self.current_id is None:
            self.status.configure(text="Обладнання не вибрано")
            logging.error("No equipment selected for write_off")
            return
        self.db.write_off_equipment(self.current_id)
        self.controller.refresh_pages()
        self.status.configure(text="Обладнання списано")
        self.controller.switch_page("MainMenu")
        logging.debug(f"Equipment written off: ID {self.current_id}")

    def refresh(self):
        self.entries['type'].configure(values=[''] + self.db.get_all_types())
        self.entries['room'].configure(values=[''] + self.db.get_all_rooms())
        self.entries['owner'].configure(values=[''] + self.db.get_all_owners())
        if self.current_id:
            self.load_equipment(self.current_id)
        logging.debug("EquipmentCardPage refreshed")
