import logging
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

class OwnersManagementPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing OwnersManagementPage")

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Управління власниками", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        select_frame = ctk.CTkFrame(self)
        select_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(select_frame, text="Вибрати власника:").pack(side="left", padx=5)
        self.combo = ctk.CTkComboBox(select_frame, values=self.db.get_all_owners(), command=self.set_selected)
        self.combo.pack(side="left", expand=True, fill="x", padx=5)

        edit_frame = ctk.CTkFrame(self)
        edit_frame.pack(pady=10, padx=20, fill="x")

        self.entries = {}
        fields = [
            ("ПІБ", "full_name"),
            ("Посада", "position"),
            ("IP ПК", "pc_ip"),
            ("Ім'я ПК", "pc_name"),
            ("Телефон", "phone"),
            ("Email", "email")
        ]
        for label_text, field_key in fields:
            frame = ctk.CTkFrame(edit_frame)
            frame.pack(fill="x", pady=2)
            ctk.CTkLabel(frame, text=label_text).pack(side="left", padx=5)
            entry = ctk.CTkEntry(frame)
            entry.pack(side="left", expand=True, fill="x", padx=5)
            self.entries[field_key] = entry

        buttons_frame = ctk.CTkFrame(self)
        buttons_frame.pack(pady=10)

        btn_add = ctk.CTkButton(buttons_frame, text="Додати", command=self.add_item)
        btn_add.pack(side="left", padx=10)

        btn_update = ctk.CTkButton(buttons_frame, text="Оновити", command=self.update_item)
        btn_update.pack(side="left", padx=10)

        btn_delete = ctk.CTkButton(buttons_frame, text="Видалити", command=self.delete_item)
        btn_delete.pack(side="left", padx=10)

        self.status = ctk.CTkLabel(self, text="")
        self.status.pack(pady=10)

    def set_selected(self, value):
        for key in self.entries:
            self.entries[key].delete(0, tk.END)
        if value:
            details = self.db.get_owner_details(value)
            if details:
                for key in self.entries:
                    self.entries[key].insert(0, details[key] or '')

    def add_item(self):
        full_name = self.entries['full_name'].get().strip()
        if not full_name:
            self.status.configure(text="ПІБ обов'язкове")
            return
        position = self.entries['position'].get().strip()
        pc_ip = self.entries['pc_ip'].get().strip()
        pc_name = self.entries['pc_name'].get().strip()
        phone = self.entries['phone'].get().strip()
        email = self.entries['email'].get().strip()
        if self.db.add_owner(full_name, position, pc_ip, pc_name, phone, email):
            self.status.configure(text="Власника додано")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Власник з таким ПІБ вже існує")
        logging.debug(f"Owner addition attempted: {full_name}")

    def update_item(self):
        old_full_name = self.combo.get()
        new_full_name = self.entries['full_name'].get().strip()
        position = self.entries['position'].get().strip()
        pc_ip = self.entries['pc_ip'].get().strip()
        pc_name = self.entries['pc_name'].get().strip()
        phone = self.entries['phone'].get().strip()
        email = self.entries['email'].get().strip()
        if old_full_name and new_full_name:
            self.db.update_owner(old_full_name, new_full_name, position, pc_ip, pc_name, phone, email)
            self.status.configure(text="Власника оновлено")
            self.local_refresh()
            self.controller.refresh_pages()
        elif old_full_name == new_full_name:
            self.status.configure(text="Немає змін у ПІБ")
        else:
            self.status.configure(text="Виберіть власника та введіть нове ПІБ")
        logging.debug(f"Owner update attempted: {old_full_name} -> {new_full_name}")

    def delete_item(self):
        selected = self.combo.get()
        if selected:
            self.db.delete_owner(selected)
            self.status.configure(text="Власника видалено")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Виберіть власника")
        logging.debug(f"Owner deletion attempted: {selected}")

    def local_refresh(self):
        self.combo.configure(values=self.db.get_all_owners())
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        logging.debug("OwnersManagementPage refreshed")

    def refresh(self):
        self.local_refresh()