import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import sqlite3
import threading
import pandas as pd
import os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DB_PATH = "inventory.db"

TYPE_UNIFY_MAP = {
    "?": "Невідомо",
    "chp": "Checkpoint",
    "fil": "Фільтр",
    "filter": "Фільтр",
    "key": "Клавіатура",
    "keyboard": "Клавіатура",
    "mon": "Монітор",
    "monitor": "Монітор",
    "mou": "Миша",
    "mouse": "Миша",
    "pc": "Комп'ютер",
    "pr": "Принтер",
    "rout": "Роутер",
    "scan": "Сканер",
    "sw": "Свіч",
    "web": "Вебкамера"
}

# --- Database Handler ---
class Database:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.create_additional_tables()  # Додаємо це
        self.populate_rooms_and_owners_from_equipment()

    def create_tables(self):
        c = self.conn.cursor()
        # Таблиця обладнання
        c.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_number TEXT UNIQUE,
            type TEXT,
            name TEXT,
            model TEXT,
            serial_number TEXT,
            room TEXT,
            owner TEXT,
            written_off INTEGER DEFAULT 0
        )
        ''')
        # Таблиця користувачів (проста)
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
        ''')
        # Таблиця типів обладнання
        c.execute('''
        CREATE TABLE IF NOT EXISTS equipment_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT UNIQUE
        )
        ''')
        self.conn.commit()

    def add_equipment(self, data):
        c = self.conn.cursor()
        try:
            c.execute('''
            INSERT INTO equipment (inventory_number, type, name, model, serial_number, room, owner, written_off)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['inventory_number'], data['type'], data['name'], data['model'], data['serial_number'],
                  data['room'], data['owner'], data.get('written_off',0)))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def update_equipment(self, equip_id, data):
        c = self.conn.cursor()
        c.execute('''
        UPDATE equipment SET inventory_number=?, type=?, name=?, model=?, serial_number=?, room=?, owner=?, written_off=?
        WHERE id=?
        ''', (data['inventory_number'], data['type'], data['name'], data['model'], data['serial_number'],
              data['room'], data['owner'], data.get('written_off',0), equip_id))
        self.conn.commit()

    def get_equipment_by_id(self, equip_id):
        c = self.conn.cursor()
        c.execute('SELECT * FROM equipment WHERE id=?', (equip_id,))
        return c.fetchone()

    def search_equipment(self, text):
        c = self.conn.cursor()
        text = f'%{text}%'
        c.execute('''
        SELECT * FROM equipment WHERE (inventory_number LIKE ? OR name LIKE ? OR model LIKE ? OR serial_number LIKE ?)
        AND written_off=0
        ''', (text,text,text,text))
        return c.fetchall()

    def filter_equipment(self, room=None, owner=None, show_written_off=False):
        c = self.conn.cursor()
        query = 'SELECT * FROM equipment WHERE 1=1 '
        params = []
        if not show_written_off:
            query += 'AND written_off=0 '
        if room:
            query += 'AND room LIKE ? '
            params.append(f'%{room}%')
        if owner:
            query += 'AND owner LIKE ? '
            params.append(f'%{owner}%')
        c.execute(query, params)
        return c.fetchall()

    def get_all_equipment(self, show_written_off=False):
        c = self.conn.cursor()
        if show_written_off:
            c.execute('SELECT * FROM equipment WHERE written_off=1')
        else:
            c.execute('SELECT * FROM equipment WHERE written_off=0')
        return c.fetchall()

    def get_all_owners(self):
        c = self.conn.cursor()
        c.execute('SELECT DISTINCT owner FROM equipment WHERE owner IS NOT NULL AND owner != ""')
        return [row['owner'] for row in c.fetchall()]

    def get_all_types(self):
        c = self.conn.cursor()
        c.execute('SELECT DISTINCT type FROM equipment WHERE type IS NOT NULL AND type != ""')
        return [row['type'] for row in c.fetchall()]

    def write_off_equipment(self, equip_id):
        c = self.conn.cursor()
        c.execute('UPDATE equipment SET written_off=1 WHERE id=?', (equip_id,))
        self.conn.commit()

    def import_from_excel(self, filepath):
        # Читаємо всі аркуші і додаємо/оновлюємо записи
        xls = pd.ExcelFile(filepath)
        c = self.conn.cursor()
        imported = 0
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            # Шукаємо потрібні колонки (будемо універсальні)
            df.columns = [col.strip() for col in df.columns]
            for _, row in df.iterrows():
                try:
                    # Підготовка даних по можливості
                    inv_num = str(row.get('Інвентарний номер') or row.get('Тип обладнення') or '').strip()
                    name = str(row.get('Назва обладнення') or row.get('Назва') or '').strip()
                    model = str(row.get('Модель') or '').strip()
                    serial = str(row.get('Серійний номер') or row.get('Серійний №') or '').strip()
                    owner = str(row.get('Власник') or '').strip()
                    # Якщо нема інвентарного номера, пропускаємо
                    if not inv_num:
                        continue
                    # Дивимось чи запис вже є
                    c.execute('SELECT id FROM equipment WHERE inventory_number=?', (inv_num,))
                    exist = c.fetchone()
                    if exist:
                        c.execute('''
                        UPDATE equipment SET name=?, model=?, serial_number=?, owner=?
                        WHERE inventory_number=?
                        ''', (name, model, serial, owner, inv_num))
                    else:
                        # Потрібно додати поле type — беремо з колонки 'Тип обладнення' або ставимо "?"
                        raw_type = str(row.get('Тип обладнення') or '?').strip().lower()
                        equip_type = TYPE_UNIFY_MAP.get(raw_type, "?")

                        c.execute('''
                        INSERT INTO equipment (inventory_number, type, name, model, serial_number, room, owner, written_off)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                        ''', (inv_num, equip_type, name, model, serial, '', owner))
                    imported += 1
                except Exception as e:
                    print(f"Помилка імпорту рядка: {e}")
            self.conn.commit()
        return imported
    
    def get_all_rooms(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT room FROM equipment WHERE room IS NOT NULL AND room != ''")
        return [row['room'] for row in cursor.fetchall()]

    def get_all_owners(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT owner FROM equipment WHERE owner IS NOT NULL AND owner != ''")
        return [row['owner'] for row in cursor.fetchall()]
    
    def unify_types_in_db(self):
        c = self.conn.cursor()
        for old_type, new_type in TYPE_UNIFY_MAP.items():
            c.execute('UPDATE equipment SET type=? WHERE LOWER(type)=?', (new_type, old_type))
        self.conn.commit()

    def add_type(self, type_name):
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO equipment_types (type_name) VALUES (?)", (type_name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_types(self):
        c = self.conn.cursor()
        c.execute("SELECT type_name FROM equipment_types ORDER BY type_name")
        rows = c.fetchall()
        return [row[0] for row in rows]

    def add_room(self, room_name):
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO rooms (room_name) VALUES (?)", (room_name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_rooms(self):
        c = self.conn.cursor()
        c.execute("SELECT room_name FROM rooms ORDER BY room_name")
        rows = c.fetchall()
        return [row[0] for row in rows]

    def add_owner(self, owner_name):
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO owners (owner_name) VALUES (?)", (owner_name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_owners(self):
        c = self.conn.cursor()
        c.execute("SELECT owner_name FROM owners ORDER BY owner_name")
        rows = c.fetchall()
        return [row[0] for row in rows]

    def populate_rooms_and_owners_from_equipment(self):
        c = self.conn.cursor()
        c.execute("SELECT DISTINCT room FROM equipment WHERE room != '' AND room IS NOT NULL")
        rooms = [row[0] for row in c.fetchall()]
        for room in rooms:
            try:
                c.execute("INSERT INTO rooms (room_name) VALUES (?)", (room,))
            except sqlite3.IntegrityError:
                pass
        c.execute("SELECT DISTINCT owner FROM equipment WHERE owner != '' AND owner IS NOT NULL")
        owners = [row[0] for row in c.fetchall()]
        for owner in owners:
            try:
                c.execute("INSERT INTO owners (owner_name) VALUES (?)", (owner,))
            except sqlite3.IntegrityError:
                pass
        self.conn.commit()

    def create_additional_tables(self):
        c = self.conn.cursor()
        c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_name TEXT UNIQUE NOT NULL
        )
        ''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_name TEXT UNIQUE NOT NULL
        )
        ''')
        self.conn.commit()


# --- Custom Widgets ---
class AutoCompleteEntry(ctk.CTkEntry):
    # Поле вводу з автодоповненням списку
    def __init__(self, master=None, completion_list=None, **kwargs):
        super().__init__(master, **kwargs)
        self.completion_list = completion_list or []
        self.listbox = None
        self.bind("<KeyRelease>", self.check_key)
        self.bind("<FocusOut>", self.hide_listbox)

    def check_key(self, event):
        typed = self.get().lower()
        if typed == '':
            self.hide_listbox()
            return
        matches = [x for x in self.completion_list if typed in x.lower()]
        if matches:
            if self.listbox is None:
                self.listbox = ctk.CTkListbox(self.master, height=100)
                self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)
            self.listbox.delete(0, tk.END)
            for m in matches:
                self.listbox.insert(tk.END, m)
            self.listbox.place(x=self.winfo_x(), y=self.winfo_y() + self.winfo_height())
        else:
            self.hide_listbox()

    def on_listbox_select(self, event):
        if self.listbox.curselection():
            value = self.listbox.get(self.listbox.curselection())
            self.delete(0, tk.END)
            self.insert(0, value)
        self.hide_listbox()

    def hide_listbox(self, event=None):
        if self.listbox:
            self.listbox.place_forget()


# --- Pages ---

class MainMenu(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        label = ctk.CTkLabel(self, text="Головне меню", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=20)

        buttons = [
            ("Пошук", "SearchPage"),
            ("Список", "EquipmentListPage"),
            ("Склад", "EquipmentListPage"),  # Фільтр по "Склад"
            ("Списані", "WrittenOffPage"),
            ("Додавання", "AddPage")
        ]
        for text, page_name in buttons:
            btn = ctk.CTkButton(self, text=text, width=200,
                                command=lambda pn=page_name, t=text: self.open_page(pn, t))
            btn.pack(pady=8)

    def open_page(self, page_name, btn_text):
        if page_name == "EquipmentListPage" and btn_text == "Склад":
            self.controller.frames["EquipmentListPage"].set_filter(room="Склад")
        else:
            self.controller.frames["EquipmentListPage"].clear_filter()
        self.controller.switch_page(page_name)


class SearchPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db

        lbl = ctk.CTkLabel(self, text="Пошук обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Введіть інвентарний номер або назву")
        self.search_entry.pack(pady=5, padx=20, fill="x")
        self.search_var.trace_add("write", self.on_text_change)

        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.pack(pady=10, fill="both", expand=True)

        self.results_list = ctk.CTkScrollableFrame(self.results_frame)
        self.results_list.pack(fill="both", expand=True)

        btn_back = ctk.CTkButton(self, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(pady=10)

        self.current_results = []

    def on_text_change(self, *args):
        text = self.search_var.get().strip()
        # Шукаємо по базі
        self.update_results(text)

    def update_results(self, text):
        # Чистимо список
        for widget in self.results_list.winfo_children():
            widget.destroy()
        if text == "":
            return
        rows = self.db.search_equipment(text)
        self.current_results = rows
        for r in rows:
            btn = ctk.CTkButton(self.results_list,
                                text=f"{r['inventory_number']} — {r['name']} ({r['type']})\n{r['room']} | {r['owner']}",
                                anchor="w",
                                height=60,
                                command=lambda rid=r['id']: self.open_equipment_card(rid))
            btn.pack(pady=5, padx=10, fill="x")

    def open_equipment_card(self, equip_id):
        eq_page = self.controller.frames["EquipmentCardPage"]
        eq_page.load_equipment(equip_id)
        self.controller.switch_page("EquipmentCardPage")

    def refresh(self):
        self.on_text_change()


class EquipmentListPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db

        lbl = ctk.CTkLabel(self, text="Список обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        filter_frame = ctk.CTkFrame(self)
        filter_frame.pack(fill="x", padx=10)

        print(self.db.get_all_rooms())  # Додай це в конструктор EquipmentListPage

        ctk.CTkLabel(filter_frame, text="Кабінет:").pack(side="left", padx=5)
        self.room_filter = ctk.CTkComboBox(filter_frame, values=self.db.get_all_rooms(), 
                                           width=150)
        self.room_filter.pack(side="left", padx=5)

        ctk.CTkLabel(filter_frame, text="Власник:").pack(side="left", padx=5)
        self.owner_filter = ctk.CTkComboBox(filter_frame, values=self.db.get_all_owners(), 
                                            width=150)
        self.owner_filter.pack(side="left", padx=5)

        btn_filter = ctk.CTkButton(filter_frame, text="Фільтрувати", command=self.apply_filter)
        btn_filter.pack(side="left", padx=5)

        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.pack(pady=10, fill="both", expand=True)

        self.results_list = ctk.CTkScrollableFrame(self.results_frame)
        self.results_list.pack(fill="both", expand=True)

        btn_back = ctk.CTkButton(self, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(pady=10)

        self.current_filter = {}

    def apply_filter(self):
        room = self.room_filter.get().strip()
        owner = self.owner_filter.get().strip()
        self.current_filter = {'room': room, 'owner': owner}
        self.refresh()

    def set_filter(self, room=None, owner=None):
        if room:
            self.room_filter.set(room)
        else:
            self.room_filter.set('')  # очищення
        if owner:
            self.owner_filter.set(owner)
        else:
            self.owner_filter.set('')  # очищення
        self.apply_filter()

    def clear_filter(self):
        self.room_filter.set('')
        self.owner_filter.set('')
        self.current_filter = {}
        self.refresh()


    def refresh(self):
        # Очищаємо список
        for widget in self.results_list.winfo_children():
            widget.destroy()
        room = self.current_filter.get('room') if self.current_filter else None
        owner = self.current_filter.get('owner') if self.current_filter else None
        rows = self.db.filter_equipment(room=room, owner=owner, show_written_off=False)
        for r in rows:
            btn = ctk.CTkButton(self.results_list,
                                text=f"{r['inventory_number']} — {r['name']} ({r['type']})\n{r['room']} | {r['owner']}",
                                anchor="w",
                                height=60,
                                command=lambda rid=r['id']: self.open_equipment_card(rid))
            btn.pack(pady=5, padx=10, fill="x")

    def open_equipment_card(self, equip_id):
        eq_page = self.controller.frames["EquipmentCardPage"]
        eq_page.load_equipment(equip_id)
        self.controller.switch_page("EquipmentCardPage")


class WrittenOffPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db

        lbl = ctk.CTkLabel(self, text="Списане обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.pack(pady=10, fill="both", expand=True)

        self.results_list = ctk.CTkScrollableFrame(self.results_frame)
        self.results_list.pack(fill="both", expand=True)

        btn_back = ctk.CTkButton(self, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(pady=10)

    def refresh(self):
        for widget in self.results_list.winfo_children():
            widget.destroy()
        rows = self.db.get_all_equipment(show_written_off=True)
        for r in rows:
            btn = ctk.CTkButton(self.results_list,
                                text=f"{r['inventory_number']} — {r['name']} ({r['type']})\n{r['room']} | {r['owner']}",
                                anchor="w",
                                height=60,
                                command=lambda rid=r['id']: self.open_equipment_card(rid))
            btn.pack(pady=5, padx=10, fill="x")

    def open_equipment_card(self, equip_id):
        eq_page = self.controller.frames["EquipmentCardPage"]
        eq_page.load_equipment(equip_id)
        self.controller.switch_page("EquipmentCardPage")


class EquipmentCardPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        self.current_id = None

        lbl = ctk.CTkLabel(self, text="Картка обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=20, pady=10)

        # Ліва колонка — основні поля обладнання
        left = ctk.CTkFrame(container)
        left.pack(side="left", fill="both", expand=True, padx=10)

        self.entries = {}

        fields = [("Інвентарний номер", "inventory_number"),
                  ("Тип", "type"),
                  ("Назва", "name"),
                  ("Модель", "model"),
                  ("Серійний номер", "serial_number"),
                  ("Кабінет", "room")]

        for label_text, field_key in fields:
            lbl = ctk.CTkLabel(left, text=label_text)
            lbl.pack(anchor="w", pady=(5,0))
            if field_key == "type":
                # Випадаючий список типів
                self.type_combobox = ctk.CTkComboBox(left, values=self.db.get_all_types())
                self.type_combobox.pack(fill="x")
                self.entries[field_key] = self.type_combobox
            else:
                ent = ctk.CTkEntry(left)
                ent.pack(fill="x")
                self.entries[field_key] = ent

        # Права колонка — власник + кнопки
        right = ctk.CTkFrame(container)
        right.pack(side="left", fill="both", expand=True, padx=10)

        lbl_owner = ctk.CTkLabel(right, text="Власник")
        lbl_owner.pack(anchor="w", pady=(5,0))

        # Поле з автодоповненням власника
        self.owner_autocomplete = AutoCompleteEntry(right, completion_list=self.db.get_all_owners())
        self.owner_autocomplete.pack(fill="x", pady=(0, 10))

        self.btn_edit_owner = ctk.CTkButton(right, text="Редагувати власника", command=self.enable_owner_edit)
        self.btn_edit_owner.pack(pady=5)

        self.btn_save_owner = ctk.CTkButton(right, text="Зберегти власника", command=self.save_owner)
        self.btn_save_owner.pack(pady=5)
        self.btn_save_owner.configure(state="disabled")

        # Кнопки знизу (по центру)
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", pady=15)

        self.btn_to_stock = ctk.CTkButton(bottom, text="На склад", command=self.move_to_stock)
        self.btn_to_stock.pack(side="left", expand=True, padx=20)

        self.btn_write_off = ctk.CTkButton(bottom, text="Списати", command=self.write_off)
        self.btn_write_off.pack(side="left", expand=True, padx=20)

        self.btn_save = ctk.CTkButton(bottom, text="Зберегти", command=self.save_equipment)
        self.btn_save.pack(side="left", expand=True, padx=20)

        self.disable_owner_edit()

    def enable_owner_edit(self):
        self.owner_autocomplete.configure(state="normal")
        self.btn_save_owner.configure(state="normal")
        self.btn_edit_owner.configure(state="disabled")

    def disable_owner_edit(self):
        self.owner_autocomplete.configure(state="disabled")
        self.btn_save_owner.configure(state="disabled")
        self.btn_edit_owner.configure(state="normal")

    def save_owner(self):
        if self.current_id is None:
            messagebox.showerror("Помилка", "Обладнання не вибрано")
            return
        new_owner = self.owner_autocomplete.get().strip()
        if new_owner == "":
            messagebox.showerror("Помилка", "Власник не може бути порожнім")
            return
        # Оновлюємо обладнання
        data = self.collect_data()
        data['owner'] = new_owner
        self.db.update_equipment(self.current_id, data)
        self.disable_owner_edit()
        self.controller.refresh_pages(["EquipmentListPage", "SearchPage", "WrittenOffPage"])
        messagebox.showinfo("Успіх", "Власника оновлено")

    def load_equipment(self, equip_id):
        self.current_id = equip_id
        row = self.db.get_equipment_by_id(equip_id)
        if not row:
            messagebox.showerror("Помилка", "Обладнання не знайдено")
            return
        self.entries["inventory_number"].delete(0, 'end')
        self.entries["inventory_number"].insert(0, row["inventory_number"])

        # Оновити список типів у випадаючому списку
        types = self.db.get_all_types()
        self.type_combobox.configure(values=types)
        if row["type"] in types:
            self.type_combobox.set(row["type"])
        else:
            self.type_combobox.set("")

        self.entries["name"].delete(0, 'end')
        self.entries["name"].insert(0, row["name"])

        self.entries["model"].delete(0, 'end')
        self.entries["model"].insert(0, row["model"])

        self.entries["serial_number"].delete(0, 'end')
        self.entries["serial_number"].insert(0, row["serial_number"])

        self.entries["room"].delete(0, 'end')
        self.entries["room"].insert(0, row["room"])

        self.owner_autocomplete.configure(state="normal")
        self.owner_autocomplete.delete(0, 'end')
        self.owner_autocomplete.insert(0, row["owner"])
        self.owner_autocomplete.configure(state="disabled")

        self.disable_owner_edit()

    def collect_data(self):
        data = {
            'inventory_number': self.entries["inventory_number"].get().strip(),
            'type': self.type_combobox.get().strip(),
            'name': self.entries["name"].get().strip(),
            'model': self.entries["model"].get().strip(),
            'serial_number': self.entries["serial_number"].get().strip(),
            'room': self.entries["room"].get().strip(),
            'owner': self.owner_autocomplete.get().strip(),
            'written_off': 0
        }
        return data

    def save_equipment(self):
        if self.current_id is None:
            messagebox.showerror("Помилка", "Обладнання не вибрано")
            return
        data = self.collect_data()
        # Перевірка
        if data['inventory_number'] == '':
            messagebox.showerror("Помилка", "Інвентарний номер не може бути порожнім")
            return
        self.db.update_equipment(self.current_id, data)
        self.controller.refresh_pages(["EquipmentListPage", "SearchPage", "WrittenOffPage"])
        messagebox.showinfo("Успіх", "Зміни збережено")

    def move_to_stock(self):
        if self.current_id is None:
            messagebox.showerror("Помилка", "Обладнання не вибрано")
            return
        data = self.collect_data()
        data['room'] = "Склад"
        self.db.update_equipment(self.current_id, data)
        self.controller.refresh_pages(["EquipmentListPage", "SearchPage", "WrittenOffPage"])
        messagebox.showinfo("Успіх", "Обладнання переміщено на склад")

    def write_off(self):
        if self.current_id is None:
            messagebox.showerror("Помилка", "Обладнання не вибрано")
            return
        self.db.write_off_equipment(self.current_id)
        self.controller.refresh_pages(["EquipmentListPage", "SearchPage", "WrittenOffPage"])
        messagebox.showinfo("Успіх", "Обладнання списано")
        self.controller.switch_page("MainMenu")


class AddPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db

        lbl = ctk.CTkLabel(self, text="Додавання нового обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=20, pady=10)

        self.entries = {}

        fields = [
            ("Інвентарний номер", "inventory_number"),
            ("Тип", "type"),
            ("Назва", "name"),
            ("Модель", "model"),
            ("Серійний номер", "serial_number"),
            ("Кабінет", "room"),
            ("Власник", "owner")
        ]

        for label_text, field_key in fields:
            lbl = ctk.CTkLabel(container, text=label_text)
            lbl.pack(anchor="w", pady=(5,0))

            if field_key == "type":
                self.type_combobox = ctk.CTkComboBox(container, values=self.db.get_all_types())
                self.type_combobox.pack(fill="x")

                # Кнопка для додавання нового типу
                btn_add_type = ctk.CTkButton(container, text="Додати новий тип", command=self.add_new_type_dialog)
                btn_add_type.pack(pady=(2,10))

                self.entries[field_key] = self.type_combobox

            elif field_key == "room":
                self.room_combobox = ctk.CTkComboBox(container, values=self.db.get_all_rooms())
                self.room_combobox.pack(fill="x")

                btn_add_room = ctk.CTkButton(container, text="Додати новий кабінет", command=self.add_new_room_dialog)
                btn_add_room.pack(pady=(2,10))

                self.entries[field_key] = self.room_combobox

            elif field_key == "owner":
                # Якщо є AutoCompleteEntry клас - використай, якщо ні — можна замінити на комбо
                self.owner_autocomplete = AutoCompleteEntry(container, completion_list=self.db.get_all_owners())
                self.owner_autocomplete.pack(fill="x", pady=(0,10))
                # Кнопка для додавання нового власника
                btn_add_owner = ctk.CTkButton(container, text="Додати нового власника", command=self.add_new_owner_dialog)
                btn_add_owner.pack(pady=(2,10))
                self.entries[field_key] = self.owner_autocomplete

            else:
                ent = ctk.CTkEntry(container)
                ent.pack(fill="x")
                self.entries[field_key] = ent

        btn_add = ctk.CTkButton(self, text="Додати", command=self.add_equipment)
        btn_add.pack(pady=10)

        btn_back = ctk.CTkButton(self, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack()

    def add_new_type_dialog(self):
        # Простий діалог вводу нового типу
        new_type = simpledialog.askstring("Новий тип", "Введіть назву нового типу обладнання:")
        if new_type:
            new_type = new_type.strip()
            if new_type and new_type not in self.db.get_all_types():
                self.db.add_type(new_type)
                self.type_combobox.configure(values=self.db.get_all_types())
                self.type_combobox.set(new_type)

    def add_new_room_dialog(self):
        new_room = simpledialog.askstring("Новий кабінет", "Введіть назву нового кабінету:")
        if new_room:
            new_room = new_room.strip()
            if new_room and new_room not in self.db.get_all_rooms():
                self.db.add_room(new_room)
                self.room_combobox.configure(values=self.db.get_all_rooms())
                self.room_combobox.set(new_room)

    def add_new_owner_dialog(self):
        new_owner = simpledialog.askstring("Новий власник", "Введіть ім'я нового власника:")
        if new_owner:
            new_owner = new_owner.strip()
            if new_owner and new_owner not in self.db.get_all_owners():
                self.db.add_owner(new_owner)
                self.owner_autocomplete.completion_list = self.db.get_all_owners()
                self.owner_autocomplete.delete(0, 'end')
                self.owner_autocomplete.insert(0, new_owner)

    def add_equipment(self):
        data = {
            'inventory_number': self.entries['inventory_number'].get().strip(),
            'type': self.entries['type'].get().strip(),
            'name': self.entries['name'].get().strip(),
            'model': self.entries['model'].get().strip(),
            'serial_number': self.entries['serial_number'].get().strip(),
            'room': self.entries['room'].get().strip(),
            'owner': self.entries['owner'].get().strip(),
            'written_off': 0
        }
        if data['inventory_number'] == "":
            messagebox.showerror("Помилка", "Інвентарний номер обов'язковий")
            return
        if self.db.add_equipment(data):
            messagebox.showinfo("Успіх", "Обладнання додано")
            self.controller.refresh_pages(["EquipmentListPage", "SearchPage", "WrittenOffPage", "AddPage"])
            self.clear_form()
        else:
            messagebox.showerror("Помилка", "Обладнання з таким інвентарним номером вже існує")

    def clear_form(self):
        for widget in self.entries.values():
            if isinstance(widget, ctk.CTkEntry):
                widget.delete(0, 'end')
            elif isinstance(widget, ctk.CTkComboBox):
                widget.set("")
        if hasattr(self.entries['owner'], 'delete'):
            self.entries['owner'].delete(0, 'end')

    def refresh(self):
        self.type_combobox.configure(values=self.db.get_all_types())
        self.room_combobox.configure(values=self.db.get_all_rooms())
        if hasattr(self.entries['owner'], 'completion_list'):
            self.entries['owner'].completion_list = self.db.get_all_owners()


# --- App Class ---

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Inventory Manager")
        self.geometry("900x600")

        # Меню бар
        menubar = tk.Menu(self)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Імпорт з Excel", command=self.import_excel)
        settings_menu.add_separator()
        settings_menu.add_command(label="Вихід", command=self.quit)
        menubar.add_cascade(label="Налаштування", menu=settings_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Про програму", command=self.show_about)
        menubar.add_cascade(label="Довідка", menu=help_menu)

        account_menu = tk.Menu(menubar, tearoff=0)
        account_menu.add_command(label="Вийти", command=self.quit)  # Можна додати логіку акаунта
        menubar.add_cascade(label="Акаунт", menu=account_menu)

        self.config(menu=menubar)

        self.db = Database()

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (MainMenu, SearchPage, EquipmentListPage, WrittenOffPage, EquipmentCardPage, AddPage):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames[page_name] = frame

        self.switch_page("MainMenu")

    def switch_page(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        if hasattr(frame, "refresh"):
            frame.refresh()

    def refresh_pages(self, pages=None):
        if pages is None:
            pages = self.frames.values()
        for page in pages:
            if hasattr(page, "refresh"):
                page.refresh()

    def import_excel(self):
        filepath = filedialog.askopenfilename(title="Оберіть Excel файл", filetypes=[("Excel files", "*.xlsx *.xls")])
        if not filepath:
            return
        # Імпорт в окремому потоці щоб не блокувати UI
        def import_thread():
            try:
                imported = self.db.import_from_excel(filepath)
                messagebox.showinfo("Імпорт", f"Імпортовано записів: {imported}")
                self.refresh_pages()
            except Exception as e:
                messagebox.showerror("Помилка", f"Помилка імпорту: {e}")
        threading.Thread(target=import_thread).start()

    def show_about(self):
        messagebox.showinfo("Про програму", "Програма інвентаризації\nРеалізовано на customtkinter та SQLite\nАвтор: Ваше ім'я")

if __name__ == "__main__":
    db = Database()
    db.unify_types_in_db()
    app = App()
    app.mainloop()
