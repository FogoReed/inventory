import sqlite3
import logging
import pandas as pd

DB_PATH = "inventory.db"

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
        c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appearance_mode TEXT DEFAULT 'system',
            color_theme TEXT DEFAULT 'blue'
        )
        ''')
        c.execute("SELECT COUNT(*) FROM settings")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO settings (appearance_mode, color_theme) VALUES (?, ?)", ('system', 'blue'))
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
            logging.debug(f"Excel columns: {list(df.columns)}")
            for _, row in df.iterrows():
                try:
                    inv_num = str(row.get('Інвентарний номер') or '').strip()
                    raw_type = str(row.get('Тип обладнання') or '?').strip().lower()
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
                        UPDATE equipment SET type=?, name=?, model?, serial_number=?, room=?, owner=?
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

    def get_settings(self):
        c = self.conn.cursor()
        c.execute("SELECT appearance_mode, color_theme FROM settings WHERE id=1")
        row = c.fetchone()
        return {'appearance_mode': row['appearance_mode'], 'color_theme': row['color_theme']} if row else {'appearance_mode': 'system', 'color_theme': 'blue'}

    def update_settings(self, appearance_mode, color_theme):
        valid_appearance_modes = ["light", "dark", "system"]
        valid_color_themes = ["blue", "dark-blue", "green", "red", "purple", "orange", "cyan", "yellow"]
        if appearance_mode not in valid_appearance_modes:
            logging.error(f"Invalid appearance_mode: {appearance_mode}")
            raise ValueError(f"Невалідний режим відображення: {appearance_mode}")
        if color_theme not in valid_color_themes:
            logging.error(f"Invalid color_theme: {color_theme}")
            raise ValueError(f"Невалідна кольорова тема: {color_theme}")
        c = self.conn.cursor()
        c.execute("UPDATE settings SET appearance_mode=?, color_theme=? WHERE id=1", (appearance_mode, color_theme))
        self.conn.commit()
        logging.debug(f"Settings updated: appearance_mode={appearance_mode}, color_theme={color_theme}")