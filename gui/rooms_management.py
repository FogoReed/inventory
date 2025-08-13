import logging
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

class RoomsManagementPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing RoomsManagementPage")

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Управління кабінетами", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        select_frame = ctk.CTkFrame(self)
        select_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(select_frame, text="Вибрати кабінет:").pack(side="left", padx=5)
        self.combo = ctk.CTkComboBox(select_frame, values=self.db.get_all_rooms(), command=self.set_selected)
        self.combo.pack(side="left", expand=True, fill="x", padx=5)

        edit_frame = ctk.CTkFrame(self)
        edit_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(edit_frame, text="Нове ім'я:").pack(side="left", padx=5)
        self.name_entry = ctk.CTkEntry(edit_frame)
        self.name_entry.pack(side="left", expand=True, fill="x", padx=5)

        ctk.CTkLabel(edit_frame, text="Макс. місць:").pack(side="left", padx=5)
        self.seats_entry = ctk.CTkEntry(edit_frame, width=100)
        self.seats_entry.pack(side="left", padx=5)

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
        self.name_entry.delete(0, tk.END)
        self.seats_entry.delete(0, tk.END)
        self.name_entry.insert(0, value)
        max_seats = self.db.get_room_max_seats(value)
        self.seats_entry.insert(0, str(max_seats))

    def add_item(self):
        name = self.name_entry.get().strip()
        seats = self.seats_entry.get().strip()
        try:
            max_seats = int(seats) if seats else 0
            if max_seats < 0:
                self.status.configure(text="Кількість місць не може бути від'ємною")
                return
            if name:
                if self.db.add_room(name, max_seats):
                    self.status.configure(text="Кабінет додано")
                    self.local_refresh()
                    self.controller.refresh_pages()
                else:
                    self.status.configure(text="Кабінет вже існує")
            else:
                self.status.configure(text="Введіть назву кабінету")
        except ValueError:
            self.status.configure(text="Кількість місць має бути числом")
            logging.error("Invalid max_seats value in RoomsManagementPage.add_item")

    def update_item(self):
        old_name = self.combo.get()
        new_name = self.name_entry.get().strip()
        seats = self.seats_entry.get().strip()
        try:
            max_seats = int(seats) if seats else 0
            if max_seats < 0:
                self.status.configure(text="Кількість місць не може бути від'ємною")
                return
            if old_name and new_name:
                self.db.update_room(old_name, new_name, max_seats)
                self.status.configure(text="Кабінет оновлено")
                self.local_refresh()
                self.controller.refresh_pages()
            elif old_name == new_name and seats:
                self.db.update_room(old_name, new_name, max_seats)
                self.status.configure(text="Кількість місць оновлено")
                self.local_refresh()
                self.controller.refresh_pages()
            else:
                self.status.configure(text="Виберіть кабінет та введіть нове ім'я")
        except ValueError:
            self.status.configure(text="Кількість місць має бути числом")
            logging.error("Invalid max_seats value in RoomsManagementPage.update_item")

    def delete_item(self):
        selected = self.combo.get()
        if selected:
            self.db.delete_room(selected)
            self.status.configure(text="Кабінет видалено")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Виберіть кабінет")
        logging.debug(f"Room deletion attempted: {selected}")

    def local_refresh(self):
        self.combo.configure(values=self.db.get_all_rooms())
        self.name_entry.delete(0, tk.END)
        self.seats_entry.delete(0, tk.END)
        logging.debug("RoomsManagementPage refreshed")

    def refresh(self):
        self.local_refresh()