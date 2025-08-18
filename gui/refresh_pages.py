import logging
import customtkinter as ctk
from tkinter import messagebox

class RefreshPages(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing RefreshPages")
        self.create_widgets()
        logging.debug("Frame created: RefreshPages")

    def create_widgets(self):
        ctk.CTkLabel(self, text="Оновлення сторінок", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)

        # Кнопка для ручного оновлення сторінок
        ctk.CTkButton(self, text="Оновити сторінки", command=self.refresh_pages).pack(pady=10)

        # Кнопка для перестворення сторінок
        ctk.CTkButton(self, text="Перестворити сторінки", command=self.recreate_pages).pack(pady=10)

        # Кнопка назад
        ctk.CTkButton(self, text="Назад", command=lambda: self.controller.switch_page("MainMenu")).pack(pady=10)

    def refresh_pages(self):
        try:
            self.controller.refresh_pages()
            messagebox.showinfo("Успіх", "Сторінки оновлено")
        except Exception as e:
            logging.error(f"Error refreshing pages: {e}")
            messagebox.showerror("Помилка", f"Не вдалося оновити сторінки: {str(e)}")

    def recreate_pages(self):
        try:
            self.controller.refresh_pages(recreate=True)
            messagebox.showinfo("Успіх", "Сторінки перестворено")
        except Exception as e:
            logging.error(f"Error recreating pages: {e}")
            messagebox.showerror("Помилка", f"Не вдалося перестворити сторінки: {str(e)}")

    def refresh(self):
        logging.debug("RefreshPages refreshed")