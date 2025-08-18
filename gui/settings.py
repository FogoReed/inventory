import logging
import customtkinter as ctk
from tkinter import messagebox

class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        self.saved = False  # Flag to check if settings are saved
        self.original_settings = self.db.get_settings()  # Save original theme on init
        logging.debug("Initializing SettingsPage")
        self.create_widgets()
        logging.debug("Frame created: SettingsPage")

    def create_widgets(self):
        ctk.CTkLabel(self, text="Налаштування теми", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)

        # Вибір режиму відображення
        self.appearance_map = {
            "Світлий": "light",
            "Темний": "dark",
            "Системний": "system"
        }
        self.reverse_appearance_map = {v: k for k, v in self.appearance_map.items()}

        ctk.CTkLabel(self, text="Режим відображення").pack(pady=5, padx=10, anchor="w")
        current_appearance = self.db.get_settings()['appearance_mode']
        self.appearance_mode_var = ctk.StringVar(value=self.reverse_appearance_map.get(current_appearance, "Світлий"))
        self.appearance_mode_menu = ctk.CTkOptionMenu(
            self,
            values=list(self.appearance_map.keys()),
            variable=self.appearance_mode_var
        )
        self.appearance_mode_menu.pack(pady=5, padx=10, fill="x")

        # Вибір кольорової теми
        self.color_themes = [
            ("blue", "Синій"),
            ("dark-blue", "Темно-синій"),
            ("green", "Зелений")
        ]
        self.color_map = {name_ua: name_en for name_en, name_ua in self.color_themes}
        self.reverse_color_map = {v: k for k, v in self.color_map.items()}

        ctk.CTkLabel(self, text="Кольорова тема").pack(pady=5, padx=10, anchor="w")
        current_color = self.db.get_settings()['color_theme']
        self.color_theme_var = ctk.StringVar(value=self.reverse_color_map.get(current_color, "Синій"))
        self.color_theme_menu = ctk.CTkOptionMenu(
            self,
            values=[name_ua for _, name_ua in self.color_themes],
            variable=self.color_theme_var
        )
        self.color_theme_menu.pack(pady=5, padx=10, fill="x")

        # Кнопки
        ctk.CTkButton(self, text="Попередній перегляд", command=self.preview_theme).pack(pady=10)
        ctk.CTkButton(self, text="Зберегти", command=self.save_settings).pack(pady=10)
        ctk.CTkButton(self, text="Скасувати", command=self.cancel_changes).pack(pady=10)
        ctk.CTkButton(self, text="Назад", command=self.on_back).pack(pady=10)  # Changed to call on_back

    def on_back(self):
        if not self.saved:
            self.cancel_changes()
        self.controller.switch_page("MainMenu")

    def preview_theme(self):
        try:
            appearance_mode = self.appearance_map[self.appearance_mode_var.get()]
            color_theme = self.color_map[self.color_theme_var.get()]
            logging.debug(f"Preview theme: appearance_mode_var={self.appearance_mode_var.get()}, color_theme_var={self.color_theme_var.get()}")
            logging.debug(f"Mapped values: appearance_mode={appearance_mode}, color_theme={color_theme}")
            valid_appearance_modes = ["light", "dark", "system"]
            valid_color_themes = ["blue", "dark-blue", "green"]
            if appearance_mode not in valid_appearance_modes:
                messagebox.showerror("Помилка", f"Невалідний режим відображення: {appearance_mode}")
                return
            if color_theme not in valid_color_themes:
                messagebox.showerror("Помилка", f"Невалідна кольорова тема: {color_theme}")
                return
            
            # Застосовуємо нову тему для попереднього перегляду
            ctk.set_appearance_mode(appearance_mode)
            ctk.set_default_color_theme(color_theme)
            
            # Перестворюємо лише SettingsPage
            parent = self.master
            self.destroy()
            new_frame = self.controller._create_frame_by_name("SettingsPage", parent)
            self.controller.frames["SettingsPage"] = new_frame
            new_frame.tkraise()
            new_frame.appearance_mode_var.set(self.appearance_mode_var.get())
            new_frame.color_theme_var.set(self.color_theme_var.get())
            new_frame.saved = self.saved  # Copy flag
            
            logging.debug(f"Theme preview applied to SettingsPage: appearance_mode={appearance_mode}, color_theme={color_theme}")
        except Exception as e:
            logging.error(f"Error in preview_theme: {e}")
            messagebox.showerror("Помилка", f"Не вдалося виконати попередній перегляд: {str(e)}")

    def save_settings(self):
        try:
            appearance_mode = self.appearance_map[self.appearance_mode_var.get()]
            color_theme = self.color_map[self.color_theme_var.get()]
            logging.debug(f"Saving settings: appearance_mode={appearance_mode}, color_theme={color_theme}")
            valid_appearance_modes = ["light", "dark", "system"]
            valid_color_themes = ["blue", "dark-blue", "green"]
            if appearance_mode not in valid_appearance_modes:
                messagebox.showerror("Помилка", f"Невалідний режим відображення: {appearance_mode}")
                return
            if color_theme not in valid_color_themes:
                messagebox.showerror("Помилка", f"Невалідна кольорова тема: {color_theme}")
                return
            self.controller.show_progress_bar()
            ctk.set_appearance_mode(appearance_mode)
            ctk.set_default_color_theme(color_theme)
            self.controller.update_theme(appearance_mode, color_theme)
            self.saved = True
            self.controller.refresh_pages(preserve_page="SettingsPage", recreate=True)
            self.controller.hide_progress_bar()
            self.controller.switch_page("SettingsPage")  # Return to SettingsPage
            messagebox.showinfo("Успіх", "Налаштування теми збережено")
        except Exception as e:
            logging.error(f"Error saving settings: {e}")
            messagebox.showerror("Помилка", f"Не вдалося зберегти налаштування: {str(e)}")

    def cancel_changes(self):
        try:
            ctk.set_appearance_mode(self.original_settings['appearance_mode'])
            ctk.set_default_color_theme(self.original_settings['color_theme'])
            self.appearance_mode_var.set(self.reverse_appearance_map.get(self.original_settings['appearance_mode'], "Світлий"))
            self.color_theme_var.set(self.reverse_color_map.get(self.original_settings['color_theme'], "Синій"))
            self.controller.refresh_pages(preserve_page="SettingsPage", recreate=True)
            self.controller.switch_page("SettingsPage")  # Return to SettingsPage
            logging.debug("Theme changes cancelled")
        except Exception as e:
            logging.error(f"Error cancelling theme changes: {e}")
            messagebox.showerror("Помилка", f"Не вдалося скасувати зміни: {str(e)}")

    def update_widgets(self):
        """Оновлення всіх віджетів для відображення нової теми"""
        try:
            for widget in self.winfo_children():
                if isinstance(widget, (ctk.CTkButton, ctk.CTkOptionMenu, ctk.CTkLabel)):
                    widget.configure(fg_color='transparent', text_color='transparent')
                elif isinstance(widget, ctk.CTkFrame):
                    widget.configure(fg_color='transparent')
                widget.update()
            self.update()
            logging.debug("Widgets updated in SettingsPage")
        except Exception as e:
            logging.error(f"Error updating widgets: {e}")

    def refresh(self):
        try:
            settings = self.db.get_settings()
            self.appearance_mode_var.set(self.reverse_appearance_map.get(settings['appearance_mode'], "Світлий"))
            self.color_theme_var.set(self.reverse_color_map.get(settings['color_theme'], "Синій"))
            self.update_widgets()  # Оновлення віджетів при оновленні сторінки
            logging.debug("SettingsPage refreshed")
        except Exception as e:
            logging.error(f"Error refreshing SettingsPage: {e}")