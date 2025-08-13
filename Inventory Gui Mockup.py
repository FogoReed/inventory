# Лише частина коду для TypesManagementPage, решта залишається без змін
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import sqlite3
import threading
import pandas as pd
import os
import logging

# Налаштування логування
logging.basicConfig(level=logging.DEBUG, filename='inventory.log', format='%(asctime)s - %(levelname)s - %(message)s')

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DB_PATH = "inventory.db"

# --- Database Handler ---
class Database:
    def __init__(self, db_path=DB_PATH):
        logging.debug("Initializing Database")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.populate_types()
        self.populate_synonyms()
        self.populate_rooms_and_owners_from_equipment()
        logging.debug("Database initialized successfully")

    def create_tables(self):
        c = self.conn.cursor()
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
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
        ''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS equipment_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT UNIQUE
        )
        ''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_name TEXT UNIQUE NOT NULL,
            max_seats INTEGER DEFAULT 0
        )
        ''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT UNIQUE NOT NULL,
            position TEXT,
            pc_ip TEXT,
            pc_name TEXT,
            phone TEXT,
            email TEXT
        )
        ''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS type_synonyms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            synonym TEXT NOT NULL,
            main_type TEXT NOT NULL REFERENCES equipment_types(type_name)
        )
        ''')
        self.conn.commit()
        logging.debug("Tables created successfully")

    def populate_synonyms(self):
        c = self.conn.cursor()
        synonyms = [
            ("?", "Невідомо"),
            ("chp", "Checkpoint"),
            ("fil", "Фільтр"),
            ("filter", "Фільтр"),
            ("key", "Клавіатура"),
            ("keyboard", "Клавіатура"),
            ("mon", "Монітор"),
            ("monitor", "Монітор"),
            ("mou", "Миша"),
            ("mouse", "Миша"),
            ("pc", "Комп'ютер"),
            ("pr", "Принтер"),
            ("rout", "Роутер"),
            ("scan", "Сканер"),
            ("sw", "Свіч"),
            ("web", "Вебкамера"),
            ("ups", "Джерело безперебійного живлення"),
            ("uninterruptible power supply", "Джерело безперебійного живлення")
        ]
        for synonym, main_type in synonyms:
            self.ensure_type(main_type)
            c.execute("SELECT synonym FROM type_synonyms WHERE synonym=? AND main_type=?", (synonym, main_type))
            if not c.fetchone():
                c.execute("INSERT INTO type_synonyms (synonym, main_type) VALUES (?, ?)", (synonym, main_type))
                logging.debug(f"Added synonym: {synonym} -> {main_type}")
        self.conn.commit()

    def populate_types(self):
        c = self.conn.cursor()
        c.execute("SELECT DISTINCT main_type FROM type_synonyms")
        types = [row['main_type'] for row in c.fetchall()]
        for t in types:
            self.ensure_type(t)
        self.conn.commit()

    def add_equipment(self, data):
        c = self.conn.cursor()
        try:
            equip_type = self.get_main_type(data['type'].lower()) or "Невідомо"
            if data['room'] and not self.check_room_capacity(data['room']):
                raise ValueError(f"Кабінет {data['room']} перевищує максимальну кількість місць")
            self.ensure_type(equip_type)
            self.ensure_room(data['room'])
            self.ensure_owner(data['owner'])
            c.execute('''
            INSERT INTO equipment (inventory_number, type, name, model, serial_number, room, owner, written_off)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['inventory_number'], equip_type, data['name'], data['model'], data['serial_number'],
                  data['room'], data['owner'], data.get('written_off', 0)))
            self.conn.commit()
            self.unify_types_in_db()
            logging.debug(f"Equipment added: {data['inventory_number']} with type: {equip_type}")
            return True
        except sqlite3.IntegrityError as e:
            logging.error(f"IntegrityError in add_equipment: {e}")
            return False
        except ValueError as e:
            logging.error(f"ValueError in add_equipment: {e}")
            raise e

    def update_equipment(self, equip_id, data):
        c = self.conn.cursor()
        try:
            equip_type = self.get_main_type(data['type'].lower()) or data['type']
            if data['room'] and not self.check_room_capacity(data['room']):
                raise ValueError(f"Кабінет {data['room']} перевищує максимальну кількість місць")
            self.ensure_type(equip_type)
            self.ensure_room(data['room'])
            self.ensure_owner(data['owner'])
            c.execute('''
            UPDATE equipment SET inventory_number=?, type=?, name=?, model=?, serial_number=?, room=?, owner=?, written_off=?
            WHERE id=?
            ''', (data['inventory_number'], equip_type, data['name'], data['model'], data['serial_number'],
                  data['room'], data['owner'], data.get('written_off', 0), equip_id))
            self.conn.commit()
            logging.debug(f"Equipment updated: ID {equip_id}")
        except ValueError as e:
            logging.error(f"ValueError in update_equipment: {e}")
            raise e

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
        ''', (text, text, text, text))
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
        logging.debug(f"Equipment written off: ID {equip_id}")

    def import_from_excel(self, filepath):
        xls = pd.ExcelFile(filepath)
        c = self.conn.cursor()
        imported = 0
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df.columns = [col.strip() for col in df.columns]
            logging.debug(f"Excel columns: {list(df.columns)}")  # Логування назв стовпців
            for _, row in df.iterrows():
                try:
                    inv_num = str(row.get('Інвентарний номер') or '').strip()
                    raw_type = str(row.get('Тип обладнення') or '?').strip().lower()
                    logging.debug(f"Raw type from Excel for inv_num {inv_num}: {raw_type}")
                    equip_type = self.get_main_type(raw_type) or "Невідомо"
                    name = str(row.get('Назва обладнання') or row.get('Назва') or '').strip()
                    model = str(row.get('Модель') or '').strip()
                    serial = str(row.get('Серійний номер') or row.get('Серійний №') or '').strip()
                    room = str(row.get('Кабінет') or '').strip()
                    owner = str(row.get('Власник') or '').strip()
                    if not inv_num:
                        continue
                    if room and not self.check_room_capacity(room):
                        raise ValueError(f"Кабінет {room} перевищує максимальну кількість місць")
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
                    logging.debug(f"Imported equipment: {inv_num} with type: {equip_type}")
                except ValueError as e:
                    logging.error(f"ValueError in import_from_excel: {e}")
                except Exception as e:
                    logging.error(f"Error in import_from_excel: {e}")
            self.conn.commit()
        self.unify_types_in_db()
        logging.debug(f"Imported {imported} records from Excel")
        return imported

    def unify_types_in_db(self):
        c = self.conn.cursor()
        c.execute("SELECT synonym, main_type FROM type_synonyms")
        for row in c.fetchall():
            c.execute('UPDATE equipment SET type=? WHERE LOWER(type)=?', (row['main_type'], row['synonym'].lower()))
        self.conn.commit()
        logging.debug("Types unified in database")

    def add_type(self, type_name):
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO equipment_types (type_name) VALUES (?)", (type_name,))
            self.conn.commit()
            logging.debug(f"Type added: {type_name}")
            return True
        except sqlite3.IntegrityError:
            logging.error(f"Type already exists: {type_name}")
            return False

    def get_all_types(self):
        try:
            c = self.conn.cursor()
            c.execute("SELECT type_name FROM equipment_types ORDER BY type_name")
            types = [row['type_name'] for row in c.fetchall()]
            return types
        except Exception as e:
            logging.error(f"Error in get_all_types: {e}")
            return []

    def update_type(self, old_name, new_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET type=? WHERE type=?", (new_name, old_name))
        c.execute("UPDATE equipment_types SET type_name=? WHERE type_name=?", (new_name, old_name))
        c.execute("UPDATE type_synonyms SET main_type=? WHERE main_type=?", (new_name, old_name))
        self.conn.commit()
        logging.debug(f"Type updated: {old_name} -> {new_name}")

    def delete_type(self, type_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET type='?' WHERE type=?", (type_name,))
        c.execute("DELETE FROM equipment_types WHERE type_name=?", (type_name,))
        c.execute("DELETE FROM type_synonyms WHERE main_type=?", (type_name,))
        self.conn.commit()
        logging.debug(f"Type deleted: {type_name}")

    def add_room(self, room_name, max_seats=0):
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO rooms (room_name, max_seats) VALUES (?, ?)", (room_name, max_seats))
            self.conn.commit()
            logging.debug(f"Room added: {room_name}")
            return True
        except sqlite3.IntegrityError:
            logging.error(f"Room already exists: {room_name}")
            return False

    def get_all_rooms(self):
        try:
            c = self.conn.cursor()
            c.execute("SELECT room_name FROM rooms ORDER BY room_name")
            rooms = [row['room_name'] for row in c.fetchall()]
            return rooms
        except Exception as e:
            logging.error(f"Error in get_all_rooms: {e}")
            return []

    def update_room(self, old_name, new_name, max_seats=None):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET room=? WHERE room=?", (new_name, old_name))
        query = "UPDATE rooms SET room_name=?"
        params = [new_name]
        if max_seats is not None:
            query += ", max_seats=?"
            params.append(max_seats)
        query += " WHERE room_name=?"
        params.append(old_name)
        c.execute(query, params)
        self.conn.commit()
        logging.debug(f"Room updated: {old_name} -> {new_name}")

    def delete_room(self, room_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET room='' WHERE room=?", (room_name,))
        c.execute("DELETE FROM rooms WHERE room_name=?", (room_name,))
        self.conn.commit()
        logging.debug(f"Room deleted: {room_name}")

    def add_owner(self, full_name, position='', pc_ip='', pc_name='', phone='', email=''):
        c = self.conn.cursor()
        try:
            c.execute('''
            INSERT INTO owners (full_name, position, pc_ip, pc_name, phone, email)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (full_name, position, pc_ip, pc_name, phone, email))
            self.conn.commit()
            logging.debug(f"Owner added: {full_name}")
            return True
        except sqlite3.IntegrityError:
            logging.error(f"Owner already exists: {full_name}")
            return False

    def get_all_owners(self):
        try:
            c = self.conn.cursor()
            c.execute("SELECT full_name FROM owners ORDER BY full_name")
            owners = [row['full_name'] for row in c.fetchall()]
            return owners
        except Exception as e:
            logging.error(f"Error in get_all_owners: {e}")
            return []

    def update_owner(self, old_full_name, new_full_name, position=None, pc_ip=None, pc_name=None, phone=None, email=None):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET owner=? WHERE owner=?", (new_full_name, old_full_name))
        query = "UPDATE owners SET full_name=?"
        params = [new_full_name]
        if position is not None:
            query += ", position=?"
            params.append(position)
        if pc_ip is not None:
            query += ", pc_ip=?"
            params.append(pc_ip)
        if pc_name is not None:
            query += ", pc_name=?"
            params.append(pc_name)
        if phone is not None:
            query += ", phone=?"
            params.append(phone)
        if email is not None:
            query += ", email=?"
            params.append(email)
        query += " WHERE full_name=?"
        params.append(old_full_name)
        c.execute(query, params)
        self.conn.commit()
        logging.debug(f"Owner updated: {old_full_name} -> {new_full_name}")

    def delete_owner(self, full_name):
        c = self.conn.cursor()
        c.execute("UPDATE equipment SET owner='' WHERE owner=?", (full_name,))
        c.execute("DELETE FROM owners WHERE full_name=?", (full_name,))
        self.conn.commit()
        logging.debug(f"Owner deleted: {full_name}")

    def get_owner_details(self, full_name):
        c = self.conn.cursor()
        c.execute("SELECT * FROM owners WHERE full_name=?", (full_name,))
        return c.fetchone()

    def ensure_type(self, type_name):
        if type_name and type_name not in self.get_all_types():
            self.add_type(type_name)

    def ensure_room(self, room_name):
        if room_name and room_name not in self.get_all_rooms():
            self.add_room(room_name)

    def ensure_owner(self, full_name):
        if full_name and full_name not in self.get_all_owners():
            self.add_owner(full_name)

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
        logging.debug("Populated rooms and owners from equipment")

    def get_room_max_seats(self, room_name):
        c = self.conn.cursor()
        c.execute("SELECT max_seats FROM rooms WHERE room_name=?", (room_name,))
        row = c.fetchone()
        return row['max_seats'] if row else 0

    def check_room_capacity(self, room_name):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) as count FROM equipment WHERE room=? AND written_off=0", (room_name,))
        current_count = c.fetchone()['count']
        max_seats = self.get_room_max_seats(room_name)
        return current_count < max_seats if max_seats > 0 else True

    def add_synonym(self, synonym, main_type):
        c = self.conn.cursor()
        try:
            self.ensure_type(main_type)
            c.execute("INSERT INTO type_synonyms (synonym, main_type) VALUES (?, ?)", (synonym, main_type))
            self.conn.commit()
            logging.debug(f"Synonym added: {synonym} -> {main_type}")
            return True
        except sqlite3.IntegrityError:
            logging.error(f"Synonym already exists: {synonym} -> {main_type}")
            return False

    def get_main_type(self, synonym):
        c = self.conn.cursor()
        c.execute("SELECT main_type FROM type_synonyms WHERE synonym=?", (synonym.lower(),))
        row = c.fetchone()
        main_type = row['main_type'] if row else None
        logging.debug(f"get_main_type: {synonym} -> {main_type}")
        return main_type

    def delete_synonym(self, synonym):
        c = self.conn.cursor()
        c.execute("DELETE FROM type_synonyms WHERE synonym=?", (synonym,))
        self.conn.commit()
        logging.debug(f"Synonym deleted: {synonym}")

    def get_synonyms_for_type(self, main_type):
        c = self.conn.cursor()
        c.execute("SELECT synonym FROM type_synonyms WHERE main_type=?", (main_type,))
        return [row['synonym'] for row in c.fetchall()]

# --- TypesManagementPage (Оновлена версія) ---
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

# Решта класів (без змін)
class RoomsManagementPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing RoomsManagementPage")

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
        self.name_entry = ctk.CTkEntry(edit_frame)
        self.name_entry.pack(side="left", expand=True, fill="x", padx=5)

        ctk.CTkLabel(edit_frame, text="Макс. місць:").pack(side="left", padx=5)
        self.seats_entry = ctk.CTkEntry(edit_frame, width=100)
        self.seats_entry.pack(side="left", padx=5)

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
        self.name_entry.delete(0, tk.END)
        self.seats_entry.delete(0, tk.END)
        self.name_entry.insert(0, value)
        max_seats = self.db.get_room_max_seats(value)
        self.seats_entry.insert(0, str(max_seats))

    def add_item(self):
        name = self.name_entry.get().strip()
        seats = self.seats_entry.get().strip()
        try:
            max_seats = int(seats) if seats else 0
            if max_seats < 0:
                self.status.configure(text="Кількість місць не може бути від'ємною")
                return
            if name:
                if self.db.add_room(name, max_seats):
                    self.status.configure(text="Кабінет додано")
                    self.local_refresh()
                    self.controller.refresh_pages()
                else:
                    self.status.configure(text="Кабінет вже існує")
            else:
                self.status.configure(text="Введіть назву кабінету")
        except ValueError:
            self.status.configure(text="Кількість місць має бути числом")
            logging.error("Invalid max_seats value in RoomsManagementPage.add_item")

    def update_item(self):
        old_name = self.combo.get()
        new_name = self.name_entry.get().strip()
        seats = self.seats_entry.get().strip()
        try:
            max_seats = int(seats) if seats else 0
            if max_seats < 0:
                self.status.configure(text="Кількість місць не може бути від'ємною")
                return
            if old_name and new_name:
                self.db.update_room(old_name, new_name, max_seats)
                self.status.configure(text="Кабінет оновлено")
                self.local_refresh()
                self.controller.refresh_pages()
            elif old_name == new_name and seats:
                self.db.update_room(old_name, new_name, max_seats)
                self.status.configure(text="Кількість місць оновлено")
                self.local_refresh()
                self.controller.refresh_pages()
            else:
                self.status.configure(text="Виберіть кабінет та введіть нове ім'я")
        except ValueError:
            self.status.configure(text="Кількість місць має бути числом")
            logging.error("Invalid max_seats value in RoomsManagementPage.update_item")

    def delete_item(self):
        selected = self.combo.get()
        if selected:
            self.db.delete_room(selected)
            self.status.configure(text="Кабінет видалено")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Виберіть кабінет")
        logging.debug(f"Room deletion attempted: {selected}")

    def local_refresh(self):
        self.combo.configure(values=self.db.get_all_rooms())
        self.name_entry.delete(0, tk.END)
        self.seats_entry.delete(0, tk.END)
        logging.debug("RoomsManagementPage refreshed")

    def refresh(self):
        self.local_refresh()

class OwnersManagementPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing OwnersManagementPage")

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

        self.entries = {}
        fields = [
            ("ПІБ", "full_name"),
            ("Посада", "position"),
            ("IP ПК", "pc_ip"),
            ("Ім'я ПК", "pc_name"),
            ("Телефон", "phone"),
            ("Email", "email")
        ]
        for label_text, field_key in fields:
            frame = ctk.CTkFrame(edit_frame)
            frame.pack(fill="x", pady=2)
            ctk.CTkLabel(frame, text=label_text).pack(side="left", padx=5)
            entry = ctk.CTkEntry(frame)
            entry.pack(side="left", expand=True, fill="x", padx=5)
            self.entries[field_key] = entry

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
        for key in self.entries:
            self.entries[key].delete(0, tk.END)
        if value:
            details = self.db.get_owner_details(value)
            if details:
                for key in self.entries:
                    self.entries[key].insert(0, details[key] or '')

    def add_item(self):
        full_name = self.entries['full_name'].get().strip()
        if not full_name:
            self.status.configure(text="ПІБ обов'язкове")
            return
        position = self.entries['position'].get().strip()
        pc_ip = self.entries['pc_ip'].get().strip()
        pc_name = self.entries['pc_name'].get().strip()
        phone = self.entries['phone'].get().strip()
        email = self.entries['email'].get().strip()
        if self.db.add_owner(full_name, position, pc_ip, pc_name, phone, email):
            self.status.configure(text="Власника додано")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Власник з таким ПІБ вже існує")
        logging.debug(f"Owner addition attempted: {full_name}")

    def update_item(self):
        old_full_name = self.combo.get()
        new_full_name = self.entries['full_name'].get().strip()
        position = self.entries['position'].get().strip()
        pc_ip = self.entries['pc_ip'].get().strip()
        pc_name = self.entries['pc_name'].get().strip()
        phone = self.entries['phone'].get().strip()
        email = self.entries['email'].get().strip()
        if old_full_name and new_full_name:
            self.db.update_owner(old_full_name, new_full_name, position, pc_ip, pc_name, phone, email)
            self.status.configure(text="Власника оновлено")
            self.local_refresh()
            self.controller.refresh_pages()
        elif old_full_name == new_full_name:
            self.status.configure(text="Немає змін у ПІБ")
        else:
            self.status.configure(text="Виберіть власника та введіть нове ПІБ")
        logging.debug(f"Owner update attempted: {old_full_name} -> {new_full_name}")

    def delete_item(self):
        selected = self.combo.get()
        if selected:
            self.db.delete_owner(selected)
            self.status.configure(text="Власника видалено")
            self.local_refresh()
            self.controller.refresh_pages()
        else:
            self.status.configure(text="Виберіть власника")
        logging.debug(f"Owner deletion attempted: {selected}")

    def local_refresh(self):
        self.combo.configure(values=self.db.get_all_owners())
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        logging.debug("OwnersManagementPage refreshed")

    def refresh(self):
        self.local_refresh()

class MainMenu(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        logging.debug("Initializing MainMenu")

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
        logging.debug(f"Opening page from MainMenu: {page_name}")

class SearchPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing SearchPage")

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
        logging.debug(f"Opening EquipmentCardPage for equipment ID: {equip_id}")

    def refresh(self):
        self.on_text_change()
        logging.debug("SearchPage refreshed")

class EquipmentListPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing EquipmentListPage")

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
        self.room_filter.set('---')
        self.room_filter.pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkLabel(filter_frame, text="Власник:").pack(side="left", padx=5)
        self.owner_filter = ctk.CTkComboBox(filter_frame, values=['---'] + self.db.get_all_owners())
        self.owner_filter.set('---')
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
        self.current_filter = {
            'room': room if room != '---' else None,
            'owner': owner if owner != '---' else None
        }
        self.refresh()
        logging.debug(f"Filter applied: room={room}, owner={owner}")

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
        logging.debug("EquipmentListPage refreshed")

    def open_equipment_card(self, equip_id):
        eq_page = self.controller.frames["EquipmentCardPage"]
        eq_page.load_equipment(equip_id)
        self.controller.switch_page("EquipmentCardPage")
        logging.debug(f"Opening EquipmentCardPage for equipment ID: {equip_id}")

class WrittenOffPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing WrittenOffPage")

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
        logging.debug("WrittenOffPage refreshed")

    def open_equipment_card(self, equip_id):
        eq_page = self.controller.frames["EquipmentCardPage"]
        eq_page.load_equipment(equip_id)
        self.controller.switch_page("EquipmentCardPage")
        logging.debug(f"Opening EquipmentCardPage for equipment ID: {equip_id}")

class EquipmentCardPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        self.current_id = None
        logging.debug("Initializing EquipmentCardPage")

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
            logging.error(f"Equipment not found: ID {equip_id}")
            return
        for key in self.entries:
            widget = self.entries[key]
            value = row[key] or ''
            if isinstance(widget, ctk.CTkComboBox):
                widget.set(value)
            else:
                widget.delete(0, tk.END)
                widget.insert(0, value)
        logging.debug(f"Equipment loaded: ID {equip_id}")

    def collect_data(self):
        data = {key: self.entries[key].get().strip() for key in self.entries}
        data['written_off'] = 0
        return data

    def save_equipment(self):
        if self.current_id is None:
            self.status.configure(text="Обладнання не вибрано")
            logging.error("No equipment selected for saving")
            return
        data = self.collect_data()
        if data['inventory_number'] == '':
            self.status.configure(text="Інвентарний номер не може бути порожнім")
            logging.error("Empty inventory number in save_equipment")
            return
        try:
            self.db.update_equipment(self.current_id, data)
            self.controller.refresh_pages()
            self.status.configure(text="Зміни збережено")
            logging.debug(f"Equipment saved: ID {self.current_id}")
        except ValueError as e:
            self.status.configure(text=str(e))
            logging.error(f"ValueError in save_equipment: {e}")

    def move_to_stock(self):
        if self.current_id is None:
            self.status.configure(text="Обладнання не вибрано")
            logging.error("No equipment selected for move_to_stock")
            return
        data = self.collect_data()
        data['room'] = "Склад"
        try:
            self.db.update_equipment(self.current_id, data)
            self.controller.refresh_pages()
            self.status.configure(text="Обладнання переміщено на склад")
            logging.debug(f"Equipment moved to stock: ID {self.current_id}")
        except ValueError as e:
            self.status.configure(text=str(e))
            logging.error(f"ValueError in move_to_stock: {e}")

    def write_off(self):
        if self.current_id is None:
            self.status.configure(text="Обладнання не вибрано")
            logging.error("No equipment selected for write_off")
            return
        self.db.write_off_equipment(self.current_id)
        self.controller.refresh_pages()
        self.status.configure(text="Обладнання списано")
        self.controller.switch_page("MainMenu")
        logging.debug(f"Equipment written off: ID {self.current_id}")

    def refresh(self):
        self.entries['type'].configure(values=[''] + self.db.get_all_types())
        self.entries['room'].configure(values=[''] + self.db.get_all_rooms())
        self.entries['owner'].configure(values=[''] + self.db.get_all_owners())
        if self.current_id:
            self.load_equipment(self.current_id)
        logging.debug("EquipmentCardPage refreshed")

class AddPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing AddPage")

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

    def open_management_page(self, page_name):
        try:
            self.controller.switch_page(page_name)
            logging.debug(f"Opened management page: {page_name}")
        except Exception as e:
            logging.error(f"Error opening management page {page_name}: {e}")
            self.status.configure(text=f"Помилка відкриття сторінки керування: {str(e)}")

    def add_equipment(self):
        try:
            data = {key: self.entries[key].get().strip() for key in self.entries}
            data['written_off'] = 0
            if data['inventory_number'] == "":
                self.status.configure(text="Інвентарний номер обов'язковий")
                logging.error("Empty inventory number in add_equipment")
                return
            try:
                if self.db.add_equipment(data):
                    self.status.configure(text="Обладнання додано")
                    self.controller.refresh_pages()
                    self.clear_form()
                    logging.debug("Equipment added successfully")
                else:
                    self.status.configure(text="Обладнання з таким інвентарним номером вже існує")
                    logging.error("Equipment with this inventory number already exists")
            except ValueError as e:
                self.status.configure(text=str(e))
                logging.error(f"ValueError in add_equipment: {e}")
        except Exception as e:
            logging.error(f"Error in add_equipment: {e}")
            self.status.configure(text=f"Помилка додавання обладнання: {str(e)}")

    def clear_form(self):
        try:
            for widget in self.entries.values():
                if isinstance(widget, ctk.CTkComboBox):
                    widget.set('')
                else:
                    widget.delete(0, tk.END)
            logging.debug("AddPage form cleared")
        except Exception as e:
            logging.error(f"Error in clear_form: {e}")
            self.status.configure(text=f"Помилка очищення форми: {str(e)}")

    def refresh(self):
        try:
            self.entries['type'].configure(values=[''] + self.db.get_all_types())
            self.entries['room'].configure(values=[''] + self.db.get_all_rooms())
            self.entries['owner'].configure(values=[''] + self.db.get_all_owners())
            logging.debug("AddPage refreshed")
        except Exception as e:
            logging.error(f"Error in refresh: {e}")
            self.status.configure(text=f"Помилка оновлення: {str(e)}")

class App(ctk.CTk):
    def __init__(self):
        try:
            super().__init__()
            self.title("Inventory Manager")
            self.geometry("900x600")
            self.minsize(900, 600)
            logging.debug("Initializing App")

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
            page_classes = [
                MainMenu,
                SearchPage,
                EquipmentListPage,
                WrittenOffPage,
                EquipmentCardPage,
                AddPage,
                RoomsManagementPage,
                OwnersManagementPage,
                TypesManagementPage
            ]
            for F in page_classes:
                page_name = F.__name__
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

if __name__ == "__main__":
    db = Database()
    db.unify_types_in_db()
    app = App()
    app.mainloop()