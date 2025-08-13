import logging
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os

class MainMenu(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        logging.debug("Initializing MainMenu")

        label = ctk.CTkLabel(self, text="Головне меню", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=20)

        buttons = [
            ("Пошук", "SearchPage"),
            ("Список", "EquipmentListPage"),
            ("Склад", "EquipmentListPage"),
            ("Списані", "WrittenOffPage"),
            ("Додавання", "AddPage"),
            ("Налаштування теми", "SettingsPage")  # Нова кнопка
        ]
        for text, page_name in buttons:
            btn = ctk.CTkButton(self, text=text, width=200,
                                command=lambda pn=page_name, t=text: self.open_page(pn, t))
            btn.pack(pady=8)

    def open_page(self, page_name, btn_text):
        if page_name == "EquipmentListPage" and btn_text == "Склад":
            self.controller.frames["EquipmentListPage"].set_filter(room="Склад")
        else:
            if page_name == "EquipmentListPage":
                self.controller.frames["EquipmentListPage"].clear_filter()
        self.controller.switch_page(page_name)
        logging.debug(f"Opening page from MainMenu: {page_name}")

    def refresh(self):
        logging.debug("MainMenu refreshed")