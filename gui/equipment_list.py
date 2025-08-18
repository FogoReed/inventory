import logging
import customtkinter as ctk
from tkinter import messagebox

class EquipmentListPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        self.current_room = None
        self.equipment_buttons = []  # Список для зберігання кнопок
        logging.debug("Initializing EquipmentListPage")
        self.create_widgets()
        logging.debug("Frame created: EquipmentListPage")

    def create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Список обладнання", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=10, padx=10, sticky="w")

        self.filter_frame = ctk.CTkFrame(self)
        self.filter_frame.grid(row=0, column=1, pady=10, padx=10, sticky="e")

        ctk.CTkLabel(self.filter_frame, text="Фільтр за кабінетом:").grid(row=0, column=0, padx=5)
        self.room_filter_var = ctk.StringVar(value="---")
        self.room_filter = ctk.CTkOptionMenu(self.filter_frame, variable=self.room_filter_var, values=["---"] + self.db.get_all_rooms(),
                                             command=self.update_list)
        self.room_filter.grid(row=0, column=1, padx=5)

        ctk.CTkLabel(self.filter_frame, text="Фільтр за власником:").grid(row=0, column=2, padx=5)
        self.owner_filter_var = ctk.StringVar(value="---")
        self.owner_filter = ctk.CTkOptionMenu(self.filter_frame, variable=self.owner_filter_var, values=["---"] + self.db.get_all_owners(),
                                              command=self.update_list)
        self.owner_filter.grid(row=0, column=3, padx=5)

        # Створюємо прокручуваний фрейм для кнопок
        self.scrollable_frame = ctk.CTkScrollableFrame(self, width=600, height=400)
        self.scrollable_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, columnspan=2, pady=10)

        self.view_button = ctk.CTkButton(self.button_frame, text="Переглянути", command=self.view_selected)
        self.view_button.grid(row=0, column=0, padx=5)

        self.edit_button = ctk.CTkButton(self.button_frame, text="Редагувати", command=self.edit_selected)
        self.edit_button.grid(row=0, column=1, padx=5)

        self.write_off_button = ctk.CTkButton(self.button_frame, text="Списати", command=self.write_off_selected)
        self.write_off_button.grid(row=0, column=2, padx=5)

        self.back_button = ctk.CTkButton(self.button_frame, text="Назад", command=lambda: self.controller.switch_page("MainMenu"))
        self.back_button.grid(row=0, column=3, padx=5)

        self.update_list()

    def set_filter(self, room=None):
        self.current_room = room
        self.room_filter_var.set(room if room else "---")
        self.update_list()

    def clear_filter(self):
        self.current_room = None
        self.room_filter_var.set("---")
        self.owner_filter_var.set("---")
        self.update_list()

    def update_list(self, *args):
        try:
            # Очищаємо попередні кнопки
            for button in self.equipment_buttons:
                button.destroy()
            self.equipment_buttons.clear()

            # Отримуємо список обладнання
            equipment = self.db.filter_equipment(room=self.current_room or self.room_filter_var.get(),
                                                 owner=self.owner_filter_var.get())
            
            # Створюємо кнопку для кожного елемента обладнання
            for index, item in enumerate(equipment):
                button_text = f"{item['inventory_number']} | {item['type']} | {item['name']} | {item['room']} | {item['owner']}"
                button = ctk.CTkButton(
                    master=self.scrollable_frame,
                    text=button_text,
                    command=lambda equip_id=item['id']: self.view_equipment(equip_id)
                )
                button.grid(row=index, column=0, padx=5, pady=5, sticky="ew")
                self.equipment_buttons.append(button)

            logging.debug("Equipment list updated")
        except Exception as e:
            logging.error(f"Error updating equipment list: {e}")

    def view_equipment(self, equip_id):
        """Функція для перегляду обладнання за ID"""
        try:
            self.controller.frames["EquipmentCardPage"].load_equipment(equip_id)
            self.controller.switch_page("EquipmentCardPage")
        except Exception as e:
            logging.error(f"Error in view_equipment: {e}")
            messagebox.showerror("Помилка", "Не вдалося відкрити картку обладнання")

    def view_selected(self):
        try:
            # Якщо потрібно підтримувати вибір через виділення, додайте логіку
            messagebox.showinfo("Інформація", "Вибір через кнопки, а не текст")
        except Exception as e:
            logging.error(f"Error in view_selected: {e}")
            messagebox.showerror("Помилка", "Оберіть обладнання зі списку")

    def edit_selected(self):
        try:
            # Аналогічно для редагування
            messagebox.showinfo("Інформація", "Виберіть обладнання через кнопку")
        except Exception as e:
            logging.error(f"Error in edit_selected: {e}")
            messagebox.showerror("Помилка", "Оберіть обладнання зі списку")

    def write_off_selected(self):
        try:
            # Аналогічно для списання
            messagebox.showinfo("Інформація", "Виберіть обладнання через кнопку")
        except Exception as e:
            logging.error(f"Error in write_off_selected: {e}")
            messagebox.showerror("Помилка", "Оберіть обладнання зі списку")

    def refresh(self):
        try:
            self.room_filter.configure(values=["---"] + self.db.get_all_rooms())
            self.owner_filter.configure(values=["---"] + self.db.get_all_owners())
            self.update_list()
            logging.debug("EquipmentListPage refreshed")
        except Exception as e:
            logging.error(f"Error refreshing EquipmentListPage: {e}")
            self.update_list()