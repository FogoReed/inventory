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

class App(ctk.CTk):
    def __init__(self):
        try:
            super().__init__()
            logging.debug("Initializing App")
            self.title("Inventory Manager")
            self.geometry("900x600")
            self.minsize(900, 600)

            # Ініціалізація бази даних і теми
            self.db = Database()
            settings = self.db.get_settings()
            ctk.set_appearance_mode(settings['appearance_mode'])
            color_theme = settings['color_theme']
            valid_color_themes = ["blue", "dark-blue", "green"]
            if color_theme not in valid_color_themes:
                color_theme = "blue"
                logging.warning(f"Invalid color theme {color_theme}, falling back to blue")
            ctk.set_default_color_theme(color_theme)

            # Налаштування меню
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

            # Створення контейнера
            try:
                container = ctk.CTkFrame(self)
                container.pack(fill="both", expand=True)
                container.grid_rowconfigure(0, weight=1)
                container.grid_columnconfigure(0, weight=1)
            except Exception as e:
                logging.error(f"Error creating container frame: {e}")
                raise

            # Ініціалізація прогрес-бару
            self.progress_frame = None
            self.progress_bar = None

            # Ініціалізація фреймів
            self.frames = {}
            self.page_classes = {
                MainMenu.__name__: MainMenu,
                SearchPage.__name__: SearchPage,
                EquipmentListPage.__name__: EquipmentListPage,
                WrittenOffPage.__name__: WrittenOffPage,
                EquipmentCardPage.__name__: EquipmentCardPage,
                AddPage.__name__: AddPage,
                RoomsManagementPage.__name__: RoomsManagementPage,
                OwnersManagementPage.__name__: OwnersManagementPage,
                TypesManagementPage.__name__: TypesManagementPage,
                SettingsPage.__name__: SettingsPage,
            }

            for page_name, cls in self.page_classes.items():
                logging.debug(f"Creating frame for {page_name}")
                try:
                    frame = cls(parent=container, controller=self)
                    frame.grid(row=0, column=0, sticky="nsew")
                    self.frames[page_name] = frame
                    logging.debug(f"Frame created: {page_name}")
                except Exception as e:
                    logging.error(f"Error creating frame {page_name}: {e}")
                    raise

            # Перемикання на головну сторінку
            self.switch_page("MainMenu")
            logging.debug("App initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing App: {e}")
            messagebox.showerror("Помилка", f"Помилка ініціалізації програми: {str(e)}")
            raise

    def _create_frame_by_name(self, name: str, parent):
        try:
            cls = self.page_classes.get(name)
            if cls is None:
                raise KeyError(f"Unknown page name: {name}")
            frame = cls(parent=parent, controller=self)
            frame.grid(row=0, column=0, sticky="nsew")
            logging.debug(f"Frame created (recreated): {name}")
            return frame
        except Exception as e:
            logging.error(f"Error creating frame {name}: {e}")
            raise

    def switch_page(self, page_name):
        try:
            logging.debug(f"Attempting to switch to page: {page_name}")
            if not hasattr(self, 'frames') or page_name not in self.frames:
                logging.error(f"Page not found or frames not initialized: {page_name}")
                messagebox.showerror("Помилка", f"Сторінка {page_name} не знайдена або програма не ініціалізована")
                return
            frame = self.frames[page_name]
            frame.tkraise()
            if hasattr(frame, "refresh"):
                frame.refresh()
            logging.debug(f"Successfully switched to page: {page_name}")
        except Exception as e:
            logging.error(f"Error switching to page {page_name}: {e}")
            messagebox.showerror("Помилка", f"Не вдалося відкрити сторінку {page_name}: {str(e)}")

    def show_progress_bar(self):
        """Показати прогрес-бар"""
        try:
            if self.progress_frame is None:
                self.progress_frame = ctk.CTkFrame(self, fg_color="gray50", corner_radius=10)
                self.progress_frame.place(relx=0.5, rely=0.5, anchor="center")
                ctk.CTkLabel(self.progress_frame, text="Оновлення теми...", font=ctk.CTkFont(size=16)).pack(pady=10, padx=20)
                self.progress_bar = ctk.CTkProgressBar(self.progress_frame, mode="indeterminate")
                self.progress_bar.pack(pady=10, padx=20)
                self.progress_bar.start()
                logging.debug("Progress bar shown")
                self.update()
        except Exception as e:
            logging.error(f"Error showing progress bar: {e}")

    def hide_progress_bar(self):
        """Приховати прогрес-бар"""
        try:
            if self.progress_frame is not None:
                self.progress_bar.stop()
                self.progress_frame.destroy()
                self.progress_frame = None
                self.progress_bar = None
                logging.debug("Progress bar hidden")
                self.update()
        except Exception as e:
            logging.error(f"Error hiding progress bar: {e}")

    def refresh_pages(self, preserve_page: str | None = None, recreate: bool = False):
        try:
            if not hasattr(self, 'frames'):
                logging.error("Frames not initialized in refresh_pages")
                return
            # Зберігаємо поточну сторінку
            current_page = None
            for name, frame in self.frames.items():
                if frame.winfo_viewable():
                    current_page = name
                    break
            
            if not recreate:
                for name, frame in list(self.frames.items()):
                    if preserve_page and (name == preserve_page or type(frame).__name__ == preserve_page):
                        if hasattr(frame, "refresh"):
                            try:
                                frame.refresh()
                                logging.debug(f"Refreshed page: {name}")
                            except Exception as e:
                                logging.error(f"Failed to refresh page {name}: {e}")
                        continue
                    if hasattr(frame, "refresh"):
                        try:
                            frame.refresh()
                            logging.debug(f"Refreshed page: {name}")
                        except Exception as e:
                            logging.error(f"Failed to refresh page {name}: {e}")
            else:
                for name, frame in list(self.frames.items()):
                    if preserve_page and (name == preserve_page or type(frame).__name__ == preserve_page):
                        if hasattr(frame, "refresh"):
                            try:
                                frame.refresh()
                                logging.debug(f"Refreshed page: {name}")
                            except Exception as e:
                                logging.error(f"Failed to refresh page {name}: {e}")
                        continue
                    parent = frame.master
                    try:
                        frame.grid_remove()  # Приховуємо сторінку перед перестворенням
                        new_frame = self._create_frame_by_name(name, parent)
                        frame.destroy()
                        self.frames[name] = new_frame
                        logging.debug(f"Recreated page: {name}")
                    except Exception as e:
                        logging.error(f"Failed to recreate page {name}: {e}")
            
            # Відновлюємо відображення лише поточної сторінки
            if current_page:
                self.frames[current_page].tkraise()
            
            self.update_widgets()
        except Exception as e:
            logging.error(f"Error in refresh_pages: {e}")

    def update_widgets(self):
        """Оновлення всіх віджетів у головному вікні"""
        try:
            for widget in self.winfo_children():
                if isinstance(widget, ctk.CTkFrame):
                    for child in widget.winfo_children():
                        if isinstance(child, (ctk.CTkLabel, ctk.CTkButton, ctk.CTkOptionMenu, ctk.CTkEntry)):
                            child.configure(fg_color='transparent', text_color=None)
                        elif isinstance(child, ctk.CTkFrame):
                            child.configure(fg_color=None)
                        child.update()
                widget.update()
            self.update()
            logging.debug("Widgets updated in App")
        except Exception as e:
            logging.error(f"Error updating widgets in App: {e}")

    def import_excel(self):
        try:
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
        except Exception as e:
            logging.error(f"Error in import_excel: {e}")
            messagebox.showerror("Помилка", f"Помилка імпорту: {str(e)}")

    def show_about(self):
        try:
            messagebox.showinfo("Про програму", "Програма інвентаризації\nРеалізовано на customtkinter та SQLite")
            logging.debug("Show about dialog")
        except Exception as e:
            logging.error(f"Error in show_about: {e}")
            messagebox.showerror("Помилка", f"Помилка відображення інформації: {str(e)}")

    def update_theme(self, appearance_mode: str, color_theme: str):
        try:
            valid_appearance_modes = ["light", "dark", "system"]
            valid_color_themes = ["blue", "dark-blue", "green"]
            if appearance_mode not in valid_appearance_modes:
                raise ValueError(f"Невалідний режим відображення: {appearance_mode}")
            if color_theme not in valid_color_themes:
                raise ValueError(f"Невалідна кольорова тема: {color_theme}")
            ctk.set_appearance_mode(appearance_mode)
            ctk.set_default_color_theme(color_theme)
            self.db.update_settings(appearance_mode, color_theme)
            self.refresh_pages(preserve_page="SettingsPage", recreate=True)
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