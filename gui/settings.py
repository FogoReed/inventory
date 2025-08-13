import logging
import customtkinter as ctk
from tkinter import messagebox
import os

class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing SettingsPage")
        self.create_widgets()
        logging.debug("Frame created: SettingsPage")

    def create_widgets(self):
        ctk.CTkLabel(self, text="Налаштування теми", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)

        # Вибір режиму відображення
        ctk.CTkLabel(self, text="Режим відображення").pack(pady=5, padx=10, anchor="w")
        self.appearance_mode_var = ctk.StringVar(value=self.db.get_settings()['appearance_mode'])
        appearance_modes = ["light", "dark", "system"]
        self.appearance_mode_menu = ctk.CTkOptionMenu(self, values=["Світлий", "Темний", "Системний"],
                                                      variable=self.appearance_mode_var,
                                                      command=lambda choice: self.appearance_mode_var.set({"Світлий": "light", "Темний": "dark", "Системний": "system"}[choice]))
        self.appearance_mode_menu.pack(pady=5, padx=10, fill="x")

        # Вибір кольорової теми
        ctk.CTkLabel(self, text="Кольорова тема").pack(pady=5, padx=10, anchor="w")
        self.color_theme_var = ctk.StringVar(value=self.db.get_settings()['color_theme'])
        color_themes = [
            ("blue", "Синій"),
            ("dark-blue", "Темно-синій"),
            ("green", "Зелений"),
            ("red", "Червоний"),
            ("purple", "Фіолетовий"),
            ("orange", "Помаранчевий"),
            ("cyan", "Бірюзовий"),
            ("yellow", "Жовтий")
        ]
        self.color_theme_menu = ctk.CTkOptionMenu(
            self,
            values=[name for _, name in color_themes],
            variable=self.color_theme_var,
            command=lambda choice: self.color_theme_var.set([k for k, v in color_themes if v == choice][0])
        )
        self.color_theme_menu.pack(pady=5, padx=10, fill="x")

        # Кнопки
        ctk.CTkButton(self, text="Попередній перегляд", command=self.preview_theme).pack(pady=10)
        ctk.CTkButton(self, text="Зберегти", command=self.save_settings).pack(pady=10)
        ctk.CTkButton(self, text="Скасувати", command=self.cancel_changes).pack(pady=10)
        ctk.CTkButton(self, text="Назад", command=lambda: self.controller.switch_page("MainMenu")).pack(pady=10)

    def preview_theme(self):
        try:
            appearance_mode = self.appearance_mode_var.get()
            color_theme = self.color_theme_var.get()
            valid_appearance_modes = ["light", "dark", "system"]
            valid_color_themes = ["blue", "dark-blue", "green", "red", "purple", "orange", "cyan", "yellow"]
            built_in_themes = ["blue", "dark-blue", "green"]
            if appearance_mode not in valid_appearance_modes:
                messagebox.showerror("Помилка", "Невалідний режим відображення")
                return
            if color_theme not in valid_color_themes:
                messagebox.showerror("Помилка", "Невалідна кольорова тема")
                return
            ctk.set_appearance_mode(appearance_mode)
            if color_theme in built_in_themes:
                ctk.set_default_color_theme(color_theme)
            else:
                theme_path = f"utils/{color_theme}_theme.json"
                if not os.path.exists(theme_path):
                    messagebox.showerror("Помилка", f"Файл теми {theme_path} не знайдено")
                    return
                ctk.set_default_color_theme(theme_path)
            self.controller.refresh_pages()
            logging.debug(f"Theme preview: appearance_mode={appearance_mode}, color_theme={color_theme}")
        except Exception as e:
            logging.error(f"Error in preview_theme: {e}")
            messagebox.showerror("Помилка", f"Не вдалося виконати попередній перегляд: {str(e)}")

    def save_settings(self):
        try:
            appearance_mode = self.appearance_mode_var.get()
            color_theme = self.color_theme_var.get()
            valid_appearance_modes = ["light", "dark", "system"]
            valid_color_themes = ["blue", "dark-blue", "green", "red", "purple", "orange", "cyan", "yellow"]
            built_in_themes = ["blue", "dark-blue", "green"]
            if appearance_mode not in valid_appearance_modes:
                messagebox.showerror("Помилка", "Невалідний режим відображення")
                return
            if color_theme not in valid_color_themes:
                messagebox.showerror("Помилка", "Невалідна кольорова тема")
                return
            if color_theme not in built_in_themes:
                theme_path = f"utils/{color_theme}_theme.json"
                if not os.path.exists(theme_path):
                    messagebox.showerror("Помилка", f"Файл теми {theme_path} не знайдено")
                    return
                ctk.set_default_color_theme(theme_path)
            else:
                ctk.set_default_color_theme(color_theme)
            self.controller.update_theme(appearance_mode, color_theme)
            messagebox.showinfo("Успіх", "Налаштування теми збережено")
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            messagebox.showerror("Помилка", f"Не вдалося зберегти налаштування: {str(e)}")

    def cancel_changes(self):
        try:
            settings = self.db.get_settings()
            ctk.set_appearance_mode(settings['appearance_mode'])
            built_in_themes = ["blue", "dark-blue", "green"]
            if settings['color_theme'] in built_in_themes:
                ctk.set_default_color_theme(settings['color_theme'])
            else:
                theme_path = f"utils/{settings['color_theme']}_theme.json"
                if os.path.exists(theme_path):
                    ctk.set_default_color_theme(theme_path)
                else:
                    ctk.set_default_color_theme("blue")
            self.appearance_mode_var.set(settings['appearance_mode'])
            self.color_theme_var.set(settings['color_theme'])
            self.controller.refresh_pages()
            logging.debug("Theme changes cancelled")
        except Exception as e:
            logging.error(f"Error cancelling theme changes: {e}")
            messagebox.showerror("Помилка", f"Не вдалося скасувати зміни: {str(e)}")

    def refresh(self):
        settings = self.db.get_settings()
        self.appearance_mode_var.set(settings['appearance_mode'])
        self.color_theme_var.set(settings['color_theme'])
        self.appearance_mode_menu.configure(values=["Світлий", "Темний", "Системний"])
        color_themes = [
            ("blue", "Синій"),
            ("dark-blue", "Темно-синій"),
            ("green", "Зелений"),
            ("red", "Червоний"),
            ("purple", "Фіолетовий"),
            ("orange", "Помаранчевий"),
            ("cyan", "Бірюзовий"),
            ("yellow", "Жовтий")
        ]
        self.color_theme_menu.configure(values=[name for _, name in color_themes])
        logging.debug("SettingsPage refreshed")