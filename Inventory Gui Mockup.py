import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
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
        self.populate_types()
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
        # Таблиця кабінетів
        c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_name TEXT UNIQUE NOT NULL
        )
        ''')
        # Таблиця власників
        c.execute('''
        CREATE TABLE IF NOT EXISTS owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_name TEXT UNIQUE NOT NULL
        )
        ''')
        self.conn.commit()

    def populate_types(self):
        for new_type in TYPE_UNIFY_MAP.values():
            self.add_type(new_type)

    def add_equipment(self, data):
        c = self.conn.cursor()
        try:
            self.ensure_type(data['type'])
            self.ensure_room(data['room'])
            self.ensure_owner(data['owner'])
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
        self.ensure_type(data['type'])
        self.ensure_room(data['room'])
        self.ensure_owner(data['owner'])
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
        if room and room != '---':
            query += 'AND room LIKE ? '
            params.append(f'%{room}%')
        if owner and owner != '---':
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

    def write_off_equipment(self, equip_id):
        c = self.conn.cursor()
        c.execute('UPDATE equipment SET written_off=1 WHERE id=?', (equip_id,))
        self.conn.commit()

    def import_from_excel(self, filepath):
        xls = pd.ExcelFile(filepath)
        c = self.conn.cursor()
        imported = 0
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df.columns = [col.strip() for col in df.columns]
            for _, row in df.iterrows():
                try:
                    inv_num = str(row.get('Інвентарний номер') or '').strip()
                    raw_type = str(row.get('Тип обладнення') or '?').strip().lower()
                    equip_type = TYPE_UNIFY_MAP.get(raw_type, "?")
                    name = str(row.get('Назва обладнення') or row.get('Назва') or '').strip()
                    model = str(row.get('Модель') or '').strip()
                    serial = str(row.get('Серійний номер') or row.get('Серійний №') or '').strip()
                    room = str(row.get('Кабінет') or '').strip()
                    owner = str(row.get('Власник') or '').strip()
                    if not inv_num:
                        continue
                    self.ensure_type(equip_type)
                    self.ensure_room(room)
                    self.ensure_owner(owner)
                    c.execute('SELECT id FROM equipment WHERE inventory_number=?', (inv_num,))
                    exist = c.fetchone()
                    if exist:
                        c.execute('''
                        UPDATE equipment SET type=?, name=?, model=?, serial_number=?, room=?, owner=?
                        WHERE inventory_number=?
                        ''', (equip_type, name, model, serial, room, owner, inv_num))
                    else:
                        c.execute('''
                        INSERT INTO equipment (inventory_number, type, name, model, serial_number, room, owner, written_off)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                        ''', (inv_num, equip_type, name, model, serial, room, owner))
                    imported += 1
                except Exception as e:
                    print(f"Помилка імпорту рядка: {e}")
            self.conn.commit()
        return imported
    
    def unify_types_in_db(self):
        c = self.conn.cursor()
        for old_type, new_type in TYPE_UNIFY_MAP.items():
            c.execute('UPDATE equipment SET type=? WHERE LOWER(type)=?', (new_type, old_type.lower()))
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
        try:
            c = self.conn.cursor()
            c.execute("SELECT type_name FROM equipment_types ORDER BY type_name")
            types = [row['type_name'] for row in c.fetchall()]
            print(f"Retrieved types: {types}")
            return types
        except Exception as e:
            print(f"Error in get_all_types: {str(e)}")
            return []

    def update_type(self, old_name, new_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET type=? WHERE type=?", (new_name, old_name))
        c.execute("UPDATE equipment_types SET type_name=? WHERE type_name=?", (new_name, old_name))
        self.conn.commit()

    def delete_type(self, type_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET type='?' WHERE type=?", (type_name,))
        c.execute("DELETE FROM equipment_types WHERE type_name=?", (type_name,))
        self.conn.commit()

    def add_room(self, room_name):
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO rooms (room_name) VALUES (?)", (room_name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_rooms(self):
        try:
            c = self.conn.cursor()
            c.execute("SELECT room_name FROM rooms ORDER BY room_name")
            rooms = [row['room_name'] for row in c.fetchall()]
            print(f"Retrieved rooms: {rooms}")
            return rooms
        except Exception as e:
            print(f"Error in get_all_rooms: {str(e)}")
            return []

    def update_room(self, old_name, new_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET room=? WHERE room=?", (new_name, old_name))
        c.execute("UPDATE rooms SET room_name=? WHERE room_name=?", (new_name, old_name))
        self.conn.commit()

    def delete_room(self, room_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET room='' WHERE room=?", (room_name,))
        c.execute("DELETE FROM rooms WHERE room_name=?", (room_name,))
        self.conn.commit()

    def add_owner(self, owner_name):
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO owners (owner_name) VALUES (?)", (owner_name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_owners(self):
        try:
            c = self.conn.cursor()
            c.execute("SELECT owner_name FROM owners ORDER BY owner_name")
            owners = [row['owner_name'] for row in c.fetchall()]
            print(f"Retrieved owners: {owners}")
            return owners
        except Exception as e:
            print(f"Error in get_all_owners: {str(e)}")
            return []

    def update_owner(self, old_name, new_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET owner=? WHERE owner=?", (new_name, old_name))
        c.execute("UPDATE owners SET owner_name=? WHERE owner_name=?", (new_name, old_name))
        self.conn.commit()

    def delete_owner(self, owner_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET owner='' WHERE owner=?", (owner_name,))
        c.execute("DELETE FROM owners WHERE owner_name=?", (owner_name,))
        self.conn.commit()

    def ensure_type(self, type_name):
        if type_name and type_name not in self.get_all_types():
            self.add_type(type_name)

    def ensure_room(self, room_name):
        if room_name and room_name not in self.get_all_rooms():
            self.add_room(room_name)

    def ensure_owner(self, owner_name):
        if owner_name and owner_name not in self.get_all_owners():
            self.add_owner(owner_name)

    def populate_rooms_and_owners_from_equipment(self):
        c = self.conn.cursor()
        c.execute("SELECT DISTINCT room FROM equipment WHERE room != '' AND room IS NOT NULL")
        rooms = [row['room'] for row in c.fetchall()]
        for room in rooms:
            self.ensure_room(room)
        c.execute("SELECT DISTINCT owner FROM equipment WHERE owner != '' AND owner IS NOT NULL")
        owners = [row['owner'] for row in c.fetchall()]
        for owner in owners:
            self.ensure_owner(owner)
        c.execute("SELECT DISTINCT type FROM equipment WHERE type != '' AND type IS NOT NULL")
        types = [row['type'] for row in c.fetchall()]
        for t in types:
            self.ensure_type(t)
        self.conn.commit()

# --- Management Pages ---
class RoomsManagementPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Управління кабінетами", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        select_frame = ctk.CTkFrame(self)
        select_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(select_frame, text="Вибрати кабінет:").pack(side="left", padx=5)
        self.combo = ctk.CTkComboBox(select_frame, values=self.db.get_all_rooms(), command=self.set_selected)
        self.combo.pack(side="left", expand=True, fill="x", padx=5)

        edit_frame = ctk.CTkFrame(self)
        edit_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(edit_frame, text="Нове ім'я:").pack(side="left", padx=5)
        self.entry = ctk.CTkEntry(edit_frame)
        self.entry.pack(side="left", expand=True, fill="x", padx=5)

        buttons_frame = ctk.CTkFrame(self)
        buttons_frame.pack(pady=10)

        btn_add = ctk.CTkButton(buttons_frame, text="Додати", command=self.add_item)
        btn_add.pack(side="left", padx=10)

        btn_update = ctk.CTkButton(buttons_frame, text="Оновити", command=self.update_item)
        btn_update.pack(side="left", padx=10)

        btn_delete = ctk.CTkButton(buttons_frame, text="Видалити", command=self.delete_item)
        btn_delete.pack(side="left", padx=10)

        self.status = ctk.CTkLabel(self, text="")
        self.status.pack(pady=10)

    def set_selected(self, value):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, value)

    def add_item(self):
        new = self.entry.get().strip()
        if new:
            if self.db.add_room(new):
                self.status.configure(text="Кабінет додано")
                self.local_refresh()
                self.controller.refresh_pages()
            else:
                self.status.configure(text="Кабінет вже існує")

    def update_item(self):
        old = self.combo.get()
        new = self.entry.get().strip()
        if old and new and old != new:
            self.db.update_room(old, new)
            self.status.configure(text="Кабінет оновлено")
            self.local_refresh()
            self.controller.refresh_pages()
        elif old == new:
            self.status.configure(text="Немає змін")
        else:
            self.status.configure(text="Виберіть кабінет та введіть нове ім'я")

    def delete_item(self):
        selected = self.combo.get()
        if selected:
            self.db.delete_room(selected)
            self.status.configure(text="Кабінет видалено")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Виберіть кабінет")

    def local_refresh(self):
        self.combo.configure(values=self.db.get_all_rooms())
        self.entry.delete(0, tk.END)

    def refresh(self):
        self.local_refresh()

class OwnersManagementPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Управління власниками", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        select_frame = ctk.CTkFrame(self)
        select_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(select_frame, text="Вибрати власника:").pack(side="left", padx=5)
        self.combo = ctk.CTkComboBox(select_frame, values=self.db.get_all_owners(), command=self.set_selected)
        self.combo.pack(side="left", expand=True, fill="x", padx=5)

        edit_frame = ctk.CTkFrame(self)
        edit_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(edit_frame, text="Нове ім'я:").pack(side="left", padx=5)
        self.entry = ctk.CTkEntry(edit_frame)
        self.entry.pack(side="left", expand=True, fill="x", padx=5)

        buttons_frame = ctk.CTkFrame(self)
        buttons_frame.pack(pady=10)

        btn_add = ctk.CTkButton(buttons_frame, text="Додати", command=self.add_item)
        btn_add.pack(side="left", padx=10)

        btn_update = ctk.CTkButton(buttons_frame, text="Оновити", command=self.update_item)
        btn_update.pack(side="left", padx=10)

        btn_delete = ctk.CTkButton(buttons_frame, text="Видалити", command=self.delete_item)
        btn_delete.pack(side="left", padx=10)

        self.status = ctk.CTkLabel(self, text="")
        self.status.pack(pady=10)

    def set_selected(self, value):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, value)

    def add_item(self):
        new = self.entry.get().strip()
        if new:
            if self.db.add_owner(new):
                self.status.configure(text="Власника додано")
                self.local_refresh()
                self.controller.refresh_pages()
            else:
                self.status.configure(text="Власник вже існує")

    def update_item(self):
        old = self.combo.get()
        new = self.entry.get().strip()
        if old and new and old != new:
            self.db.update_owner(old, new)
            self.status.configure(text="Власника оновлено")
            self.local_refresh()
            self.controller.refresh_pages()
        elif old == new:
            self.status.configure(text="Немає змін")
        else:
            self.status.configure(text="Виберіть власника та введіть нове ім'я")

    def delete_item(self):
        selected = self.combo.get()
        if selected:
            self.db.delete_owner(selected)
            self.status.configure(text="Власника видалено")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Виберіть власника")

    def local_refresh(self):
        self.combo.configure(values=self.db.get_all_owners())
        self.entry.delete(0, tk.END)

    def refresh(self):
        self.local_refresh()

class TypesManagementPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Управління типами обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        select_frame = ctk.CTkFrame(self)
        select_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(select_frame, text="Вибрати тип:").pack(side="left", padx=5)
        self.combo = ctk.CTkComboBox(select_frame, values=self.db.get_all_types(), command=self.set_selected)
        self.combo.pack(side="left", expand=True, fill="x", padx=5)

        edit_frame = ctk.CTkFrame(self)
        edit_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(edit_frame, text="Нове ім'я:").pack(side="left", padx=5)
        self.entry = ctk.CTkEntry(edit_frame)
        self.entry.pack(side="left", expand=True, fill="x", padx=5)

        buttons_frame = ctk.CTkFrame(self)
        buttons_frame.pack(pady=10)

        btn_add = ctk.CTkButton(buttons_frame, text="Додати", command=self.add_item)
        btn_add.pack(side="left", padx=10)

        btn_update = ctk.CTkButton(buttons_frame, text="Оновити", command=self.update_item)
        btn_update.pack(side="left", padx=10)

        btn_delete = ctk.CTkButton(buttons_frame, text="Видалити", command=self.delete_item)
        btn_delete.pack(side="left", padx=10)

        self.status = ctk.CTkLabel(self, text="")
        self.status.pack(pady=10)

    def set_selected(self, value):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, value)

    def add_item(self):
        new = self.entry.get().strip()
        if new:
            if self.db.add_type(new):
                self.status.configure(text="Тип додано")
                self.local_refresh()
                self.controller.refresh_pages()
            else:
                self.status.configure(text="Тип вже існує")

    def update_item(self):
        old = self.combo.get()
        new = self.entry.get().strip()
        if old and new and old != new:
            self.db.update_type(old, new)
            self.status.configure(text="Тип оновлено")
            self.local_refresh()
            self.controller.refresh_pages()
        elif old == new:
            self.status.configure(text="Немає змін")
        else:
            self.status.configure(text="Виберіть тип та введіть нове ім'я")

    def delete_item(self):
        selected = self.combo.get()
        if selected:
            self.db.delete_type(selected)
            self.status.configure(text="Тип видалено")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Виберіть тип")

    def local_refresh(self):
        self.combo.configure(values=self.db.get_all_types())
        self.entry.delete(0, tk.END)

    def refresh(self):
        self.local_refresh()

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
            ("Склад", "EquipmentListPage"),  
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
            if page_name == "EquipmentListPage":
                self.controller.frames["EquipmentListPage"].clear_filter()
        self.controller.switch_page(page_name)


class SearchPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

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

        self.current_results = []

    def on_text_change(self, *args):
        text = self.search_var.get().strip()
        self.update_results(text)

    def update_results(self, text):
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

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Список обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        filter_frame = ctk.CTkFrame(self)
        filter_frame.pack(fill="x", padx=10)

        ctk.CTkLabel(filter_frame, text="Кабінет:").pack(side="left", padx=5)
        self.room_filter = ctk.CTkComboBox(filter_frame, values=['---'] + self.db.get_all_rooms())
        self.room_filter.set('---')  # Встановлюємо початкове значення
        self.room_filter.pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkLabel(filter_frame, text="Власник:").pack(side="left", padx=5)
        self.owner_filter = ctk.CTkComboBox(filter_frame, values=['---'] + self.db.get_all_owners())
        self.owner_filter.set('---')  # Встановлюємо початкове значення
        self.owner_filter.pack(side="left", padx=5, fill="x", expand=True)

        btn_filter = ctk.CTkButton(filter_frame, text="Фільтрувати", command=self.apply_filter)
        btn_filter.pack(side="left", padx=5)

        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.pack(pady=10, fill="both", expand=True)

        self.results_list = ctk.CTkScrollableFrame(self.results_frame)
        self.results_list.pack(fill="both", expand=True)

        self.current_filter = {}

    def apply_filter(self):
        room = self.room_filter.get().strip()
        owner = self.owner_filter.get().strip()
        # Ігноруємо значення '---' для фільтрації
        self.current_filter = {
            'room': room if room != '---' else None,
            'owner': owner if owner != '---' else None
        }
        self.refresh()

    def set_filter(self, room=None, owner=None):
        self.room_filter.set(room if room else '---')
        self.owner_filter.set(owner if owner else '---')
        self.apply_filter()

    def clear_filter(self):
        self.room_filter.set('---')
        self.owner_filter.set('---')
        self.current_filter = {}
        self.refresh()

    def refresh(self):
        self.room_filter.configure(values=['---'] + self.db.get_all_rooms())
        self.owner_filter.configure(values=['---'] + self.db.get_all_owners())
        for widget in self.results_list.winfo_children():
            widget.destroy()
        room = self.current_filter.get('room')
        owner = self.current_filter.get('owner')
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

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Списане обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.pack(pady=10, fill="both", expand=True)

        self.results_list = ctk.CTkScrollableFrame(self.results_frame)
        self.results_list.pack(fill="both", expand=True)

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

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Картка обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=20, pady=10)

        self.entries = {}

        fields = [
            ("Інвентарний номер", "inventory_number", ctk.CTkEntry),
            ("Тип", "type", ctk.CTkComboBox),
            ("Назва", "name", ctk.CTkEntry),
            ("Модель", "model", ctk.CTkEntry),
            ("Серійний номер", "serial_number", ctk.CTkEntry),
            ("Кабінет", "room", ctk.CTkComboBox),
            ("Власник", "owner", ctk.CTkComboBox)
        ]

        for label_text, field_key, widget_class in fields:
            if field_key in ["type", "room", "owner"]:
                field_frame = ctk.CTkFrame(container)
                field_frame.pack(fill="x", pady=(5, 5))
                lbl = ctk.CTkLabel(field_frame, text=label_text)
                lbl.pack(side="left", padx=5)
                if widget_class == ctk.CTkComboBox:
                    if field_key == "type":
                        ent = ctk.CTkComboBox(field_frame, values=[''] + self.db.get_all_types())
                        ent.set('')
                    elif field_key == "room":
                        ent = ctk.CTkComboBox(field_frame, values=[''] + self.db.get_all_rooms())
                        ent.set('')
                    elif field_key == "owner":
                        ent = ctk.CTkComboBox(field_frame, values=[''] + self.db.get_all_owners())
                        ent.set('')
                else:
                    ent = widget_class(field_frame)
                ent.pack(side="left", fill="x", expand=True)
                if field_key == "type":
                    page = "TypesManagementPage"
                elif field_key == "room":
                    page = "RoomsManagementPage"
                elif field_key == "owner":
                    page = "OwnersManagementPage"
                btn = ctk.CTkButton(field_frame, text="Керувати", width=100, command=lambda p=page: self.controller.switch_page(p))
                btn.pack(side="left", padx=5)
            else:
                lbl = ctk.CTkLabel(container, text=label_text)
                lbl.pack(anchor="w", pady=(5,0))
                ent = widget_class(container)
                ent.pack(fill="x")
            self.entries[field_key] = ent

        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", pady=15)

        self.btn_to_stock = ctk.CTkButton(bottom, text="На склад", command=self.move_to_stock)
        self.btn_to_stock.pack(side="left", expand=True, padx=20)

        self.btn_write_off = ctk.CTkButton(bottom, text="Списати", command=self.write_off)
        self.btn_write_off.pack(side="left", expand=True, padx=20)

        self.btn_save = ctk.CTkButton(bottom, text="Зберегти", command=self.save_equipment)
        self.btn_save.pack(side="left", expand=True, padx=20)

        self.status = ctk.CTkLabel(self, text="")
        self.status.pack(pady=10)

    def load_equipment(self, equip_id):
        self.current_id = equip_id
        row = self.db.get_equipment_by_id(equip_id)
        if not row:
            self.status.configure(text="Обладнання не знайдено")
            return
        for key in self.entries:
            widget = self.entries[key]
            value = row[key] or ''
            if isinstance(widget, ctk.CTkComboBox):
                widget.set(value)
            else:
                widget.delete(0, tk.END)
                widget.insert(0, value)

    def collect_data(self):
        data = {key: self.entries[key].get().strip() for key in self.entries}
        data['written_off'] = 0
        return data

    def save_equipment(self):
        if self.current_id is None:
            self.status.configure(text="Обладнання не вибрано")
            return
        data = self.collect_data()
        if data['inventory_number'] == '':
            self.status.configure(text="Інвентарний номер не може бути порожнім")
            return
        self.db.update_equipment(self.current_id, data)
        self.controller.refresh_pages()
        self.status.configure(text="Зміни збережено")

    def move_to_stock(self):
        if self.current_id is None:
            self.status.configure(text="Обладнання не вибрано")
            return
        data = self.collect_data()
        data['room'] = "Склад"
        self.db.update_equipment(self.current_id, data)
        self.controller.refresh_pages()
        self.status.configure(text="Обладнання переміщено на склад")

    def write_off(self):
        if self.current_id is None:
            self.status.configure(text="Обладнання не вибрано")
            return
        self.db.write_off_equipment(self.current_id)
        self.controller.refresh_pages()
        self.status.configure(text="Обладнання списано")
        self.controller.switch_page("MainMenu")

    def refresh(self):
        self.entries['type'].configure(values=[''] + self.db.get_all_types())
        self.entries['room'].configure(values=[''] + self.db.get_all_rooms())
        self.entries['owner'].configure(values=[''] + self.db.get_all_owners())
        if self.current_id:
            self.load_equipment(self.current_id)


class AddPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        try:
            super().__init__(parent)
            self.controller = controller
            self.db = controller.db

            nav_frame = ctk.CTkFrame(self)
            nav_frame.pack(fill="x", pady=10)

            btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
            btn_back.pack(side="left", padx=20)

            btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
            btn_home.pack(side="left", padx=20)

            lbl = ctk.CTkLabel(self, text="Додавання нового обладнання", font=ctk.CTkFont(size=18, weight="bold"))
            lbl.pack(pady=10)

            container = ctk.CTkFrame(self)
            container.pack(fill="both", expand=True, padx=20, pady=10)

            self.entries = {}

            fields = [
                ("Інвентарний номер", "inventory_number", ctk.CTkEntry),
                ("Тип", "type", ctk.CTkComboBox),
                ("Назва", "name", ctk.CTkEntry),
                ("Модель", "model", ctk.CTkEntry),
                ("Серійний номер", "serial_number", ctk.CTkEntry),
                ("Кабінет", "room", ctk.CTkComboBox),
                ("Власник", "owner", ctk.CTkComboBox)
            ]

            for label_text, field_key, widget_class in fields:
                if field_key in ["type", "room", "owner"]:
                    field_frame = ctk.CTkFrame(container)
                    field_frame.pack(fill="x", pady=(5, 5))
                    lbl = ctk.CTkLabel(field_frame, text=label_text)
                    lbl.pack(side="left", padx=5)
                    if widget_class == ctk.CTkComboBox:
                        if field_key == "type":
                            types = [''] + self.db.get_all_types()
                            ent = ctk.CTkComboBox(field_frame, values=types)
                            ent.set('')
                        elif field_key == "room":
                            rooms = [''] + self.db.get_all_rooms()
                            ent = ctk.CTkComboBox(field_frame, values=rooms)
                            ent.set('')
                        elif field_key == "owner":
                            owners = [''] + self.db.get_all_owners()
                            ent = ctk.CTkComboBox(field_frame, values=owners)
                            ent.set('')
                    else:
                        ent = widget_class(field_frame)
                    ent.pack(side="left", fill="x", expand=True)
                    if field_key == "type":
                        page = "TypesManagementPage"
                    elif field_key == "room":
                        page = "RoomsManagementPage"
                    elif field_key == "owner":
                        page = "OwnersManagementPage"
                    btn = ctk.CTkButton(field_frame, text="Керувати", width=100, 
                                       command=lambda p=page: self.open_management_page(p))
                    btn.pack(side="left", padx=5)
                else:
                    lbl = ctk.CTkLabel(container, text=label_text)
                    lbl.pack(anchor="w", pady=(5,0))
                    ent = widget_class(container)
                    ent.pack(fill="x")
                self.entries[field_key] = ent

            btn_add = ctk.CTkButton(self, text="Додати", command=self.add_equipment)
            btn_add.pack(pady=10)

            self.status = ctk.CTkLabel(self, text="")
            self.status.pack(pady=10)

            print("AddPage initialized successfully")
        except Exception as e:
            print(f"Error initializing AddPage: {str(e)}")
            self.status = ctk.CTkLabel(self, text=f"Помилка ініціалізації: {str(e)}")
            self.status.pack(pady=10)

    def open_management_page(self, page_name):
        try:
            print(f"Opening management page: {page_name}")
            self.controller.switch_page(page_name)
        except Exception as e:
            print(f"Error opening management page {page_name}: {str(e)}")
            self.status.configure(text=f"Помилка відкриття сторінки керування: {str(e)}")

    def add_equipment(self):
        try:
            data = {key: self.entries[key].get().strip() for key in self.entries}
            data['written_off'] = 0
            if data['inventory_number'] == "":
                self.status.configure(text="Інвентарний номер обов'язковий")
                return
            if self.db.add_equipment(data):
                self.status.configure(text="Обладнання додано")
                self.controller.refresh_pages()
                self.clear_form()
                print("Equipment added successfully")
            else:
                self.status.configure(text="Обладнання з таким інвентарним номером вже існує")
        except Exception as e:
            print(f"Error in add_equipment: {str(e)}")
            self.status.configure(text=f"Помилка додавання обладнання: {str(e)}")

    def clear_form(self):
        try:
            for widget in self.entries.values():
                if isinstance(widget, ctk.CTkComboBox):
                    widget.set('')
                else:
                    widget.delete(0, tk.END)
            print("Form cleared")
        except Exception as e:
            print(f"Error in clear_form: {str(e)}")
            self.status.configure(text=f"Помилка очищення форми: {str(e)}")

    def refresh(self):
        try:
            self.entries['type'].configure(values=[''] + self.db.get_all_types())
            self.entries['room'].configure(values=[''] + self.db.get_all_rooms())
            self.entries['owner'].configure(values=[''] + self.db.get_all_owners())
            print("AddPage refreshed")
        except Exception as e:
            print(f"Error in refresh: {str(e)}")
            self.status.configure(text=f"Помилка оновлення: {str(e)}")

# --- App Class ---

class App(ctk.CTk):
    def __init__(self):
        try:
            super().__init__()
            self.title("Inventory Manager")
            self.geometry("900x600")
            self.minsize(900, 600)

            # Меню бар
            menubar = tk.Menu(self)
            settings_menu = tk.Menu(menubar, tearoff=0)
            settings_menu.add_command(label="Імпорт з Excel", command=self.import_excel)
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

            self.db = Database()

            container = ctk.CTkFrame(self)
            container.pack(fill="both", expand=True)
            container.grid_rowconfigure(0, weight=1)
            container.grid_columnconfigure(0, weight=1)

            self.frames = {}
            for F in (MainMenu, SearchPage, EquipmentListPage, WrittenOffPage, EquipmentCardPage, AddPage, 
                    RoomsManagementPage, OwnersManagementPage, TypesManagementPage):
                page_name = F.__name__
                frame = F(parent=container, controller=self)
                frame.grid(row=0, column=0, sticky="nsew")
                self.frames[page_name] = frame
                print(f"Frame {page_name} created")

            self.switch_page("MainMenu")
            print("App initialized successfully")
        except Exception as e:
            print(f"Error initializing App: {str(e)}")
            messagebox.showerror("Помилка", f"Помилка ініціалізації програми: {str(e)}")

    def switch_page(self, page_name):
        try:
            print(f"Attempting to switch to page: {page_name}")
            if page_name not in self.frames:
                print(f"Error: Page {page_name} not found in self.frames")
                messagebox.showerror("Помилка", f"Сторінка {page_name} не знайдена")
                return
            frame = self.frames[page_name]
            frame.tkraise()
            if hasattr(frame, "refresh"):
                print(f"Calling refresh for {page_name}")
                frame.refresh()
            print(f"Successfully switched to {page_name}")
        except Exception as e:
            print(f"Error switching to page {page_name}: {str(e)}")
            messagebox.showerror("Помилка", f"Не вдалося відкрити сторінку {page_name}: {str(e)}")

    def refresh_pages(self, pages=None):
        if pages is None:
            pages = self.frames.values()
        for frame in pages:
            if hasattr(frame, "refresh"):
                frame.refresh()

    def import_excel(self):
        filepath = filedialog.askopenfilename(title="Оберіть Excel файл", filetypes=[("Excel files", "*.xlsx *.xls")])
        if not filepath:
            return
        def import_thread():
            try:
                imported = self.db.import_from_excel(filepath)
                messagebox.showinfo("Імпорт", f"Імпортовано записів: {imported}")
                self.refresh_pages()
            except Exception as e:
                messagebox.showerror("Помилка", f"Помилка імпорту: {e}")
        threading.Thread(target=import_thread).start()

    def show_about(self):
        messagebox.showinfo("Про програму", "Програма інвентаризації\nРеалізовано на customtkinter та SQLite")

if __name__ == "__main__":
    db = Database()
    db.unify_types_in_db()
    app = App()
    app.mainloop()

'''
# Тут типу замітка на майбутнє :)
'''