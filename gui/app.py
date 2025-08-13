import logging
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
from gui.main_menu import MainMenu
from gui.equipment_list import EquipmentListPage
from gui.search_page import SearchPage
from gui.written_off import WrittenOffPage
from gui.equipment_card import EquipmentCardPage
from gui.add_page import AddPage
from gui.rooms_management import RoomsManagementPage
from gui.owners_management import OwnersManagementPage
from gui.types_management import TypesManagementPage
from gui.settings import SettingsPage
from database.database import Database
import os

class App(ctk.CTk):
    def __init__(self):
        try:
            super().__init__()
            # Ініціалізація теми з бази даних
            self.db = Database()
            settings = self.db.get_settings()
            ctk.set_appearance_mode(settings['appearance_mode'])
            color_theme = settings['color_theme']
            built_in_themes = ["blue", "dark-blue", "green"]
            if color_theme in built_in_themes:
                ctk.set_default_color_theme(color_theme)
            else:
                theme_path = f"utils/{color_theme}_theme.json"
                if os.path.exists(theme_path):
                    ctk.set_default_color_theme(theme_path)
                else:
                    logging.warning(f"Theme file {theme_path} not found, falling back to blue")
                    ctk.set_default_color_theme("blue")
            self.title("Inventory Manager")
            self.geometry("900x600")
            self.minsize(900, 600)
            logging.debug("Initializing App")

            menubar = tk.Menu(self)
            settings_menu = tk.Menu(menubar, tearoff=0)
            settings_menu.add_command(label="Імпорт з Excel", command=self.import_excel)
            settings_menu.add_command(label="Налаштування теми", command=lambda: self.switch_page("SettingsPage"))
            settings_menu.add_command(label="Керування кабінетами",
                                     command=lambda: self.switch_page("RoomsManagementPage"))
            settings_menu.add_command(label="Керування власниками",
                                     command=lambda: self.switch_page("OwnersManagementPage"))
            settings_menu.add_command(label="Керування типами",
                                     command=lambda: self.switch_page("TypesManagementPage"))
            settings_menu.add_separator()
            settings_menu.add_command(label="Вихід", command=self.quit)
            menubar.add_cascade(label="Налаштування", menu=settings_menu)

            help_menu = tk.Menu(menubar, tearoff=0)
            help_menu.add_command(label="Про програму", command=self.show_about)
            menubar.add_cascade(label="Довідка", menu=help_menu)

            account_menu = tk.Menu(menubar, tearoff=0)
            account_menu.add_command(label="Вийти", command=self.quit)
            menubar.add_cascade(label="Акаунт", menu=account_menu)

            self.config(menu=menubar)

            container = ctk.CTkFrame(self)
            container.pack(fill="both", expand=True)
            container.grid_rowconfigure(0, weight=1)
            container.grid_columnconfigure(0, weight=1)

            self.frames = {}
            page_classes = [
                MainMenu,
                SearchPage,
                EquipmentListPage,
                WrittenOffPage,
                EquipmentCardPage,
                AddPage,
                RoomsManagementPage,
                OwnersManagementPage,
                TypesManagementPage,
                SettingsPage
            ]
            for F in page_classes:
                page_name = F.__name__
                logging.debug(f"Initializing {page_name}")
                frame = F(parent=container, controller=self)
                frame.grid(row=0, column=0, sticky="nsew")
                self.frames[page_name] = frame
                logging.debug(f"Frame created: {page_name}")

            self.switch_page("MainMenu")
            logging.debug("App initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing App: {e}")
            messagebox.showerror("Помилка", f"Помилка ініціалізації програми: {str(e)}")

    def switch_page(self, page_name):
        try:
            logging.debug(f"Attempting to switch to page: {page_name}")
            if page_name not in self.frames:
                logging.error(f"Page not found: {page_name}")
                messagebox.showerror("Помилка", f"Сторінка {page_name} не знайдена")
                return
            frame = self.frames[page_name]
            frame.tkraise()
            if hasattr(frame, "refresh"):
                frame.refresh()
            logging.debug(f"Successfully switched to page: {page_name}")
        except Exception as e:
            logging.error(f"Error switching to page {page_name}: {e}")
            messagebox.showerror("Помилка", f"Не вдалося відкрити сторінку {page_name}: {str(e)}")

    def refresh_pages(self, pages=None):
        if pages is None:
            pages = self.frames.values()
        for frame in pages:
            if hasattr(frame, "refresh"):
                try:
                    frame.refresh()
                    logging.debug(f"Refreshed page: {frame.__class__.__name__}")
                except Exception as e:
                    logging.error(f"Error refreshing page {frame.__class__.__name__}: {e}")

    def import_excel(self):
        filepath = filedialog.askopenfilename(title="Оберіть Excel файл", filetypes=[("Excel files", "*.xlsx *.xls")])
        if not filepath:
            return
        def import_thread():
            try:
                imported = self.db.import_from_excel(filepath)
                messagebox.showinfo("Імпорт", f"Імпортовано записів: {imported}")
                self.refresh_pages()
                logging.debug(f"Excel import completed: {imported} records")
            except Exception as e:
                logging.error(f"Error in import_excel: {e}")
                messagebox.showerror("Помилка", f"Помилка імпорту: {e}")
        threading.Thread(target=import_thread).start()

    def show_about(self):
        messagebox.showinfo("Про програму", "Програма інвентаризації\nРеалізовано на customtkinter та SQLite")
        logging.debug("Show about dialog")

    def update_theme(self, appearance_mode, color_theme):
        try:
            valid_appearance_modes = ["light", "dark", "system"]
            valid_color_themes = ["blue", "dark-blue", "green", "red", "purple", "orange", "cyan", "yellow"]
            built_in_themes = ["blue", "dark-blue", "green"]
            if appearance_mode not in valid_appearance_modes:
                raise ValueError(f"Невалідний режим відображення: {appearance_mode}")
            if color_theme not in valid_color_themes:
                raise ValueError(f"Невалідна кольорова тема: {color_theme}")
            ctk.set_appearance_mode(appearance_mode)
            if color_theme in built_in_themes:
                ctk.set_default_color_theme(color_theme)
            else:
                theme_path = f"utils/{color_theme}_theme.json"
                if os.path.exists(theme_path):
                    ctk.set_default_color_theme(theme_path)
                else:
                    logging.warning(f"Theme file {theme_path} not found, falling back to blue")
                    ctk.set_default_color_theme("blue")
                    color_theme = "blue"
            self.db.update_settings(appearance_mode, color_theme)
            self.refresh_pages()
            logging.debug(f"Theme updated: appearance_mode={appearance_mode}, color_theme={color_theme}")
        except Exception as e:
            logging.error(f"Error updating theme: {e}")
            messagebox.showerror("Помилка", f"Не вдалося оновити тему: {str(e)}")
            raise

if __name__ == "__main__":
    logging.basicConfig(filename='inventory.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.debug("Starting application")
    app = App()
    app.mainloop()