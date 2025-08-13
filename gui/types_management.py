import logging
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog

class TypesManagementPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing TypesManagementPage")

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Управління типами обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        # Вкладки для типів і синонімів
        tabview = ctk.CTkTabview(self)
        tabview.pack(fill="both", expand=True, padx=20, pady=10)
        tabview.add("Типи")
        tabview.add("Синоніми")

        # Вкладка "Типи"
        types_frame = tabview.tab("Типи")

        ctk.CTkLabel(types_frame, text="Вибрати тип:").pack(pady=5)
        self.type_combo = ctk.CTkComboBox(types_frame, values=self.db.get_all_types(), command=self.set_selected_type)
        self.type_combo.pack(pady=5, padx=20, fill="x")

        ctk.CTkLabel(types_frame, text="Назва типу:").pack(pady=5)
        self.type_entry = ctk.CTkEntry(types_frame, placeholder_text="Введіть назву типу")
        self.type_entry.pack(pady=5, padx=20, fill="x")

        types_buttons_frame = ctk.CTkFrame(types_frame)
        types_buttons_frame.pack(pady=10)

        btn_add_type = ctk.CTkButton(types_buttons_frame, text="Додати тип", command=self.add_item)
        btn_add_type.pack(side="left", padx=10)

        btn_update_type = ctk.CTkButton(types_buttons_frame, text="Оновити тип", command=self.update_item)
        btn_update_type.pack(side="left", padx=10)

        btn_delete_type = ctk.CTkButton(types_buttons_frame, text="Видалити тип", command=self.delete_item)
        btn_delete_type.pack(side="left", padx=10)

        # Вкладка "Синоніми"
        synonyms_frame = tabview.tab("Синоніми")

        ctk.CTkLabel(synonyms_frame, text="Вибрати тип:").pack(pady=5)
        self.synonym_type_combo = ctk.CTkComboBox(synonyms_frame, values=self.db.get_all_types(), command=self.set_selected_synonym_type)
        self.synonym_type_combo.pack(pady=5, padx=20, fill="x")

        ctk.CTkLabel(synonyms_frame, text="Новий синонім:").pack(pady=5)
        self.synonym_entry = ctk.CTkEntry(synonyms_frame, placeholder_text="Введіть синонім")
        self.synonym_entry.pack(pady=5, padx=20, fill="x")

        ctk.CTkLabel(synonyms_frame, text="Синоніми для типу:").pack(pady=5)
        self.synonym_listbox = tk.Listbox(synonyms_frame, height=5)
        self.synonym_listbox.pack(pady=5, padx=20, fill="x")

        synonyms_buttons_frame = ctk.CTkFrame(synonyms_frame)
        synonyms_buttons_frame.pack(pady=10)

        btn_add_synonym = ctk.CTkButton(synonyms_buttons_frame, text="Додати синонім", command=self.add_synonym)
        btn_add_synonym.pack(side="left", padx=10)

        btn_delete_synonym = ctk.CTkButton(synonyms_buttons_frame, text="Видалити синонім", command=self.delete_synonym)
        btn_delete_synonym.pack(side="left", padx=10)

        self.status = ctk.CTkLabel(self, text="")
        self.status.pack(pady=10)

    def set_selected_type(self, value):
        self.type_entry.delete(0, tk.END)
        self.type_entry.insert(0, value)
        logging.debug(f"Selected type: {value}")

    def set_selected_synonym_type(self, value):
        self.synonym_listbox.delete(0, tk.END)
        synonyms = self.db.get_synonyms_for_type(value)
        for synonym in synonyms:
            self.synonym_listbox.insert(tk.END, synonym)
        logging.debug(f"Selected synonym type: {value}")

    def add_item(self):
        new_type = self.type_entry.get().strip()
        if new_type:
            if self.db.add_type(new_type):
                self.status.configure(text="Тип додано")
                self.local_refresh()
                self.controller.refresh_pages()
            else:
                self.status.configure(text="Тип вже існує")
        else:
            self.status.configure(text="Введіть назву типу")
        logging.debug(f"Type addition attempted: {new_type}")

    def update_item(self):
        old_type = self.type_combo.get()
        new_type = self.type_entry.get().strip()
        if old_type and new_type and old_type != new_type:
            self.db.update_type(old_type, new_type)
            self.status.configure(text="Тип оновлено")
            self.local_refresh()
            self.controller.refresh_pages()
        elif old_type == new_type:
            self.status.configure(text="Немає змін")
        else:
            self.status.configure(text="Виберіть тип та введіть нове ім'я")
        logging.debug(f"Type update attempted: {old_type} -> {new_type}")

    def delete_item(self):
        selected = self.type_combo.get()
        if selected:
            self.db.delete_type(selected)
            self.status.configure(text="Тип видалено")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Виберіть тип")
        logging.debug(f"Type deletion attempted: {selected}")

    def add_synonym(self):
        synonym = self.synonym_entry.get().strip()
        main_type = self.synonym_type_combo.get()
        if synonym and main_type:
            if self.db.add_synonym(synonym, main_type):
                self.status.configure(text="Синонім додано")
                self.local_refresh()
                self.set_selected_synonym_type(main_type)
            else:
                self.status.configure(text="Синонім вже існує")
        else:
            self.status.configure(text="Введіть синонім та виберіть тип")
        logging.debug(f"Synonym addition attempted: {synonym} -> {main_type}")

    def delete_synonym(self):
        selected = self.synonym_listbox.get(tk.ACTIVE)
        if selected:
            self.db.delete_synonym(selected)
            self.status.configure(text="Синонім видалено")
            self.set_selected_synonym_type(self.synonym_type_combo.get())
        else:
            self.status.configure(text="Виберіть синонім для видалення")
        logging.debug(f"Synonym deletion attempted: {selected}")

    def local_refresh(self):
        self.type_combo.configure(values=self.db.get_all_types())
        self.synonym_type_combo.configure(values=self.db.get_all_types())
        self.type_entry.delete(0, tk.END)
        self.synonym_entry.delete(0, tk.END)
        self.synonym_type_combo.set('')
        self.synonym_listbox.delete(0, tk.END)
        logging.debug("TypesManagementPage refreshed")

    def refresh(self):
        self.local_refresh()