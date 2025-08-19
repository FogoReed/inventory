import logging
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import os
import socket
import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import FileMetadata
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
from config import DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN, DROPBOX_DB_PATH, LOCAL_DB_PATH
from datetime import datetime
import shutil

class App(ctk.CTk):
    def __init__(self):
        try:
            super().__init__()
            logging.debug("Initializing App")
            self.title("Inventory Manager")
            self.geometry("900x600")
            self.minsize(900, 600)

            # Ініціалізація Dropbox
            self.dropbox_client = None
            self.init_dropbox()

            # Перевірка та синхронізація бази даних при запуску
            self.download_from_dropbox()

            self.protocol("WM_DELETE_WINDOW", self.on_closing)

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

    def init_dropbox(self):
        try:
            self.dropbox_client = dropbox.Dropbox(
                app_key=DROPBOX_APP_KEY,
                app_secret=DROPBOX_APP_SECRET,
                oauth2_refresh_token=DROPBOX_REFRESH_TOKEN
            )
            account = self.dropbox_client.users_get_current_account()
            logging.debug(f"Dropbox client initialized successfully. Account: {account.email}")
            # Тестовий виклик для перевірки scope
            try:
                self.dropbox_client.files_get_metadata(DROPBOX_DB_PATH)
                logging.debug("Scope 'files.metadata.read' is available and file exists")
            except dropbox.exceptions.ApiError as api_err:
                if isinstance(api_err.error, dropbox.files.GetMetadataError) and api_err.error.is_path() and api_err.error.get_path().is_not_found():
                    logging.warning(f"File not found in Dropbox: {DROPBOX_DB_PATH}. Will create on first upload.")
                else:
                    logging.error(f"Scope test failed: {api_err}")
                    messagebox.showwarning("Попередження", "Не вдалося отримати метадані файлу в Dropbox. Перевірте шлях або дозволи.")
                    self.dropbox_client = None
                    return
        except dropbox.exceptions.AuthError as e:
            logging.error(f"Dropbox authentication failed: {e}")
            messagebox.showerror("Помилка", "Не вдалося підключитися до Dropbox. Перевірте конфігурацію.")
            self.dropbox_client = None
        except Exception as e:
            logging.error(f"Error initializing Dropbox: {e}")
            messagebox.showerror("Помилка", f"Помилка ініціалізації Dropbox: {str(e)}")
            self.dropbox_client = None

    def has_internet(self):
        """Перевірка наявності інтернет-з'єднання"""
        try:
            socket.create_connection(("www.google.com", 80), timeout=2)
            return True
        except OSError:
            logging.warning("No internet connection")
            return False

    def show_progress_bar(self, message="Виконання операції..."):
        """Показати прогрес-бар у головному потоці"""
        try:
            self.after(0, lambda: self._show_progress_bar(message))
        except Exception as e:
            logging.error(f"Error scheduling show progress bar: {e}")

    def _show_progress_bar(self, message):
        """Внутрішня функція для показу прогрес-бару"""
        try:
            if self.progress_frame is not None:
                self.progress_frame.destroy()  # Закриваємо попередній прогрес-бар, якщо існує
            self.progress_frame = ctk.CTkFrame(self, fg_color="gray50", corner_radius=10)
            self.progress_frame.place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(self.progress_frame, text=message, font=ctk.CTkFont(size=16)).pack(pady=10, padx=20)
            self.progress_bar = ctk.CTkProgressBar(self.progress_frame, mode="indeterminate")
            self.progress_bar.pack(pady=10, padx=20)
            self.progress_bar.start()
            logging.debug(f"Progress bar shown with message: {message}")
            self.update()
        except Exception as e:
            logging.error(f"Error showing progress bar: {e}")

    def hide_progress_bar(self):
        """Приховати прогрес-бар у головному потоці"""
        try:
            self.after(0, self._hide_progress_bar)
        except Exception as e:
            logging.error(f"Error scheduling hide progress bar: {e}")

    def _hide_progress_bar(self):
        """Внутрішня функція для приховування прогрес-бару"""
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

    def download_from_dropbox(self):
        if not self.has_internet() or not self.dropbox_client:
            logging.warning("Skipping Dropbox download: no internet or client not initialized")
            messagebox.showwarning("Попередження", "Немає підключення до Dropbox або Інтернету")
            return
        try:
            self.show_progress_bar("Завантаження з Dropbox...")
            metadata = self.dropbox_client.files_get_metadata(DROPBOX_DB_PATH)
            if not isinstance(metadata, FileMetadata):
                logging.warning(f"No file found at {DROPBOX_DB_PATH}")
                self.hide_progress_bar()
                return
            cloud_modified = metadata.client_modified
            local_path = LOCAL_DB_PATH
            if os.path.exists(local_path):
                local_modified = datetime.fromtimestamp(os.path.getmtime(local_path))
                if local_modified >= cloud_modified:
                    logging.debug("Local DB is newer or same as cloud DB, skipping download")
                    self.hide_progress_bar()
                    return
                # Створюємо бекап локальної бази
                backup_path = local_path + ".backup"
                shutil.copyfile(local_path, backup_path)
                logging.debug(f"Created backup of local DB at {backup_path}")
            # Завантажуємо хмарну базу
            self.dropbox_client.files_download_to_file(local_path, DROPBOX_DB_PATH)
            logging.debug(f"Downloaded DB from Dropbox to {local_path}")
            self.hide_progress_bar()
        except ApiError as e:
            logging.error(f"Dropbox API error during download: {e}")
            self.hide_progress_bar()
            messagebox.showerror("Помилка", f"Не вдалося завантажити базу з Dropbox: {str(e)}")
        except Exception as e:
            logging.error(f"Error downloading from Dropbox: {e}")
            self.hide_progress_bar()

    def upload_to_dropbox(self):
        if not self.has_internet() or not self.dropbox_client:
            logging.warning("Skipping Dropbox upload: no internet or client not initialized")
            messagebox.showwarning("Попередження", "Немає підключення до Dropbox або Інтернету")
            return
        try:
            logging.debug("Starting upload to Dropbox")
            self.show_progress_bar("Завантаження до Dropbox...")
            with open(LOCAL_DB_PATH, "rb") as f:
                self.dropbox_client.files_upload(f.read(), DROPBOX_DB_PATH, mode=dropbox.files.WriteMode("overwrite"))
            logging.debug("Database uploaded to Dropbox successfully")
        except Exception as e:
            logging.error(f"Error uploading to Dropbox: {e}")
            messagebox.showerror("Помилка", f"Не вдалося зберегти базу в Dropbox: {str(e)}")
        finally:
            self.hide_progress_bar()

    def __del__(self):
        try:
            logging.debug("Closing app, uploading to Dropbox...")
            self.upload_to_dropbox()
        except Exception as e:
            logging.error(f"Error uploading to Dropbox on close: {e}")
        super().__del__()

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
                        try:
                            if isinstance(child, (ctk.CTkLabel, ctk.CTkButton, ctk.CTkOptionMenu, ctk.CTkEntry)):
                                child.configure(fg_color='transparent', text_color=None)
                            elif isinstance(child, ctk.CTkFrame):
                                child.configure(fg_color='transparent')
                            child.update()
                        except Exception as e:
                            logging.error(f"Error updating widget {child}: {e}")
                widget.update()
            self.update()
            logging.debug("Widgets updated in App")
        except Exception as e:
            logging.error(f"Error updating widgets in App: {e}")

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
            self.show_progress_bar("Оновлення теми...")
            ctk.set_appearance_mode(appearance_mode)
            ctk.set_default_color_theme(color_theme)
            self.db.update_settings(appearance_mode, color_theme)
            self.refresh_pages(preserve_page="SettingsPage", recreate=True)
            self.hide_progress_bar()
            logging.debug(f"Theme updated: appearance_mode={appearance_mode}, color_theme={color_theme}")
        except Exception as e:
            logging.error(f"Error updating theme: {e}")
            messagebox.showerror("Помилка", f"Не вдалося оновити тему: {str(e)}")
            self.hide_progress_bar()

    def on_closing(self):
        self.upload_to_dropbox()
        self.destroy()

if __name__ == "__main__":
    logging.basicConfig(filename='inventory.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.debug("Starting application")
    app = App()
    app.mainloop()