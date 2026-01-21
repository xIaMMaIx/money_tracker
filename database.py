# database.py
import sqlite3
import uuid
import calendar
from datetime import datetime, timedelta
from utils import parse_db_date

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.on_data_changed = None
        self.uuid_fixed = False

    def _notify(self):
        if self.on_data_changed:
            try: self.on_data_changed()
            except: pass
    
    def connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try: self.conn.execute("PRAGMA journal_mode=WAL;")
        except: pass
        
        self.create_tables()
        self.migrate_db()
        self.cleanup_duplicate_recurring()
        self.add_defaults()

    def create_tables(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY, type TEXT, item TEXT, amount REAL, category TEXT, date TIMESTAMP, payment_id INTEGER, is_deleted INTEGER DEFAULT 0, uuid TEXT UNIQUE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT, type TEXT, keywords TEXT, is_deleted INTEGER DEFAULT 0, uuid TEXT UNIQUE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS recurring_expenses (id INTEGER PRIMARY KEY, day INTEGER, item TEXT, amount REAL, category TEXT, payment_id INTEGER, auto_pay INTEGER, is_deleted INTEGER DEFAULT 0, uuid TEXT UNIQUE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS credit_cards (id INTEGER PRIMARY KEY, name TEXT, limit_amt REAL, closing_day INTEGER, color TEXT, is_deleted INTEGER DEFAULT 0, uuid TEXT UNIQUE)''')
        self.conn.commit()

    def migrate_db(self):
        self.uuid_fixed = False 
        c = self.conn.cursor()
        
        tables = {
            "transactions": ["is_deleted INTEGER DEFAULT 0", "payment_id INTEGER DEFAULT NULL", "uuid TEXT"],
            "recurring_expenses": ["is_deleted INTEGER DEFAULT 0", "payment_id INTEGER DEFAULT NULL", "auto_pay INTEGER DEFAULT 0", "uuid TEXT"],
            "categories": ["is_deleted INTEGER DEFAULT 0", "uuid TEXT"],
            "credit_cards": ["is_deleted INTEGER DEFAULT 0", "uuid TEXT"]
        }
        for table, cols in tables.items():
            for col_def in cols:
                col_name = col_def.split()[0]
                try: c.execute(f"SELECT {col_name} FROM {table} LIMIT 1")
                except: 
                    try: c.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                    except: pass
        self.conn.commit()
        
        for table in tables.keys():
            try:
                query = f"SELECT id FROM {table} WHERE uuid IS NULL OR uuid = '' OR length(uuid) < 32"
                rows = c.execute(query).fetchall()
                if rows:
                    print(f"Fixing UUIDs for {table}: {len(rows)} items...")
                    for r in rows:
                        new_uid = str(uuid.uuid4())
                        c.execute(f"UPDATE {table} SET uuid=? WHERE id=?", (new_uid, r[0]))
                    self.uuid_fixed = True
            except Exception as e: 
                print(f"Migration Error ({table}): {e}")
        self.conn.commit()

    def cleanup_duplicate_recurring(self):
        try:
            self.conn.execute("""
                UPDATE recurring_expenses 
                SET is_deleted = 1 
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM recurring_expenses
                    WHERE is_deleted = 0 OR is_deleted IS NULL
                    GROUP BY day, item, amount, category, payment_id
                )
                AND (is_deleted = 0 OR is_deleted IS NULL)
            """)
            self.conn.commit()
        except Exception as e:
            print(f"Cleanup Error: {e}")

    def purge_deleted_data(self):
        try:
            self.conn.execute("DELETE FROM transactions WHERE is_deleted = 1")
            self.conn.execute("DELETE FROM recurring_expenses WHERE is_deleted = 1")
            self.conn.execute("DELETE FROM categories WHERE is_deleted = 1")
            self.conn.execute("DELETE FROM credit_cards WHERE is_deleted = 1")
            self.conn.commit()
            old_isolation = self.conn.isolation_level
            self.conn.isolation_level = None
            self.conn.execute("VACUUM")
            self.conn.isolation_level = old_isolation
            self._notify()
            return True
        except Exception as e:
            try: self.conn.isolation_level = old_isolation
            except: pass
            return False

    def add_defaults(self):
        defaults = [
            ("อาหาร", "expense", "ข้าว,ก๋วยเตี๋ยว,food"), 
            ("เดินทาง", "expense", "รถเมล์,bts,mrt,taxi"), 
            ("เงินเดือน", "income", "salary,bonus"), 
            ("อื่นๆ", "expense", "other,general"), 
            ("อื่นๆ", "income", "other,general")
        ]
        for n, t, k in defaults:
            existing = self.conn.execute("SELECT id FROM categories WHERE name=? AND type=?", (n, t)).fetchone()
            if not existing:
                self.add_category(n, t, k)
            else:
                self.conn.execute("UPDATE categories SET is_deleted=0 WHERE id=?", (existing[0],))
        self.conn.commit()

    def get_id_by_uuid(self, table, uid):
        if not uid: return None
        try:
            r = self.conn.execute(f"SELECT id FROM {table} WHERE uuid=?", (uid,)).fetchone()
            return r[0] if r else None
        except: return None
    
    def get_uuid_by_id(self, table, tid):
        if not tid: return None
        try:
            r = self.conn.execute(f"SELECT uuid FROM {table} WHERE id=?", (tid,)).fetchone()
            return r[0] if r else None
        except: return None

    # --- Transactions ---
    def add_transaction(self, t_type, item, amount, category, date=None, payment_id=None):
        if not date: date = datetime.now()
        uid = str(uuid.uuid4())
        c = self.conn.execute("INSERT INTO transactions (type, item, amount, category, date, payment_id, is_deleted, uuid) VALUES (?,?,?,?,?,?,0,?)", (t_type, item, amount, category, date, payment_id, uid))
        self.conn.commit()
        last_id = c.lastrowid
        if item != "ยอดยกมา": self.recalculate_rollovers_from(date)
        self._notify()
        return last_id

    def delete_transaction(self, tid):
        check = self.conn.execute("SELECT item FROM transactions WHERE id=?", (tid,)).fetchone()
        if check and check[0] in ["ยอดยกมา", "Balance Forward"]:
            return  

        old_row = self.conn.execute("SELECT date FROM transactions WHERE id=?", (tid,)).fetchone()
        self.conn.execute("UPDATE transactions SET is_deleted=1 WHERE id=?", (tid,))
        self.conn.commit()
        if old_row: self.recalculate_rollovers_from(parse_db_date(old_row[0]))
        self._notify()

    def update_transaction(self, tid, item, amount, category, payment_id=None, date=None):
        check = self.conn.execute("SELECT item FROM transactions WHERE id=?", (tid,)).fetchone()
        if check and check[0] in ["ยอดยกมา", "Balance Forward"]:
            return 

        if date:
             self.conn.execute("UPDATE transactions SET item=?, amount=?, category=?, payment_id=?, date=?, is_deleted=0 WHERE id=?", (item, amount, category, payment_id, date, tid))
        else:
             self.conn.execute("UPDATE transactions SET item=?, amount=?, category=?, payment_id=?, is_deleted=0 WHERE id=?", (item, amount, category, payment_id, tid))
        self.conn.commit()
        if date: self.recalculate_rollovers_from(date)
        self._notify()
    
    def clear_all_transactions(self):
        self.conn.execute("DELETE FROM transactions")
        self.conn.commit()
        self._notify()

    def get_transactions(self, date_filter=None, month_filter=None):
        query = """
            SELECT t.id, t.type, t.item, t.amount, t.category, t.date, c.name 
            FROM transactions t
            LEFT JOIN credit_cards c ON t.payment_id = c.id
            WHERE (t.is_deleted IS NULL OR t.is_deleted = 0) 
        """
        params = []
        if date_filter:
            query += " AND date(t.date) = date(?)"
            params.append(date_filter)
        elif month_filter: 
            query += " AND strftime('%Y-%m', t.date) = ?"
            params.append(month_filter)
        query += " ORDER BY t.date DESC"
        return self.conn.execute(query, tuple(params)).fetchall()

    def search_transactions(self, keyword):
        query = """
            SELECT t.id, t.type, t.item, t.amount, t.category, t.date, c.name 
            FROM transactions t
            LEFT JOIN credit_cards c ON t.payment_id = c.id
            WHERE (t.is_deleted IS NULL OR t.is_deleted = 0)
            AND (t.item LIKE ? OR t.category LIKE ? OR CAST(t.amount AS TEXT) LIKE ?)
            ORDER BY t.date DESC
        """
        kw = f"%{keyword}%"
        return self.conn.execute(query, (kw, kw, kw)).fetchall()

    def get_summary(self, filter_str=None):
        base = """SELECT SUM(CASE WHEN type='income' THEN amount ELSE 0 END), SUM(CASE WHEN (type='expense' OR type='repayment') THEN amount ELSE 0 END) FROM transactions WHERE (payment_id IS NULL OR type='repayment') AND (is_deleted IS NULL OR is_deleted = 0)"""
        params = []
        if filter_str:
            if len(filter_str) == 7: base += " AND strftime('%Y-%m', date) = ?"; params.append(filter_str)
            else: base += " AND date(date) = date(?)"; params.append(filter_str)
        else: base += " AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now', 'localtime')"
        res = self.conn.execute(base, tuple(params)).fetchone()
        return (res[0] or 0), (res[1] or 0), (res[0] or 0) - (res[1] or 0)
    
    def get_month_balance(self, year, month):
        month_str = f"{year}-{month:02d}"
        q = "SELECT SUM(CASE WHEN type='income' THEN amount ELSE -amount END) FROM transactions WHERE type IN ('income', 'expense', 'repayment') AND (payment_id IS NULL OR type='repayment') AND strftime('%Y-%m', date) = ? AND (is_deleted IS NULL OR is_deleted = 0)"
        res = self.conn.execute(q, (month_str,)).fetchone()
        return res[0] if res and res[0] else 0.0
        
    def get_top_transactions(self, t_type, month_str):
        return self.conn.execute("SELECT item, amount FROM transactions WHERE type=? AND strftime('%Y-%m', date) = ? AND (is_deleted=0 OR is_deleted IS NULL) ORDER BY amount DESC LIMIT 10", (t_type, month_str)).fetchall()

    def get_active_days(self, month_str):
        q = "SELECT DISTINCT strftime('%d', date) FROM transactions WHERE strftime('%Y-%m', date) = ? AND (is_deleted=0 OR is_deleted IS NULL)"
        return {int(r[0]) for r in self.conn.execute(q, (month_str,)).fetchall()}

    # --- Recurring ---
    def add_recurring(self, day, item, amount, category, payment_id=None, auto_pay=0, force_id=None):
        check_q = "SELECT id FROM recurring_expenses WHERE day=? AND item=? AND amount=? AND category=? AND (is_deleted=0 OR is_deleted IS NULL)"
        params = [day, item, amount, category]
        if payment_id is not None: check_q += " AND payment_id=?"; params.append(payment_id)
        else: check_q += " AND payment_id IS NULL"

        existing = self.conn.execute(check_q, tuple(params)).fetchone()
        if existing: return 

        uid = str(uuid.uuid4())
        self.conn.execute("INSERT INTO recurring_expenses (day, item, amount, category, payment_id, auto_pay, is_deleted, uuid) VALUES (?,?,?,?,?,?,0,?)", (day, item, amount, category, payment_id, auto_pay, uid))
        self.conn.commit()
        self._notify()

    def get_recurring(self):
        return self.conn.execute("SELECT id, day, item, amount, category, payment_id, auto_pay FROM recurring_expenses WHERE (is_deleted IS NULL OR is_deleted=0) ORDER BY day").fetchall()

    def delete_recurring(self, rid):
        self.conn.execute("UPDATE recurring_expenses SET is_deleted=1 WHERE id=?", (rid,))
        self.conn.commit()
        self._notify()
        
    def clear_all_recurring(self):
        self.conn.execute("DELETE FROM recurring_expenses")
        self.conn.commit()
        self._notify()

    def is_recurring_paid_v2(self, item, amount, category, month_str, payment_id):
        q = "SELECT count(*) FROM transactions WHERE item=? AND amount=? AND category=? AND strftime('%Y-%m', date)=? AND (is_deleted=0 OR is_deleted IS NULL)"
        return self.conn.execute(q, (item, amount, category, month_str)).fetchone()[0] > 0

    # --- Categories & Cards ---
    def get_categories(self, t_type=None):
        if t_type: return self.conn.execute("SELECT id, name, type, keywords FROM categories WHERE type=? AND (is_deleted=0 OR is_deleted IS NULL)", (t_type,)).fetchall()
        return self.conn.execute("SELECT id, name, type, keywords FROM categories WHERE (is_deleted=0 OR is_deleted IS NULL)").fetchall()

    def add_category(self, name, t_type, keywords, specific_id=None, specific_uuid=None):
        clean_name = name.strip()
        existing_by_name = self.conn.execute("SELECT id FROM categories WHERE name=? AND type=?", (clean_name, t_type)).fetchone()
        
        if existing_by_name:
            cat_id = existing_by_name[0]
            if specific_uuid:
                self.conn.execute("UPDATE categories SET name=?, keywords=?, is_deleted=0, uuid=? WHERE id=?", (clean_name, keywords, specific_uuid, cat_id))
            else:
                self.conn.execute("UPDATE categories SET name=?, keywords=?, is_deleted=0 WHERE id=?", (clean_name, keywords, cat_id))
            self.conn.commit()
            self._notify()
            return cat_id

        final_uuid = specific_uuid if specific_uuid else str(uuid.uuid4())
        self.conn.execute("INSERT INTO categories (name, type, keywords, is_deleted, uuid) VALUES (?,?,?,0,?)", (clean_name, t_type, keywords, final_uuid))
        self.conn.commit()
        self._notify()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def update_category(self, cid, name, keywords):
        self.conn.execute("UPDATE categories SET name=?, keywords=?, is_deleted=0 WHERE id=?", (name, keywords, cid))
        self.conn.commit(); self._notify()

    def delete_category(self, cid):
        if self.conn.execute("SELECT name FROM categories WHERE id=?", (cid,)).fetchone()[0] == "อื่นๆ": return False
        self.conn.execute("UPDATE categories SET is_deleted=1 WHERE id=?", (cid,))
        self.conn.commit(); self._notify(); return True

    def clear_all_categories(self):
        self.conn.execute("DELETE FROM categories"); self.conn.commit(); self._notify()

    def add_card(self, name, limit, closing_day, color):
        uid = str(uuid.uuid4())
        self.conn.execute("INSERT INTO credit_cards (name, limit_amt, closing_day, color, is_deleted, uuid) VALUES (?,?,?,?,0,?)", (name, limit, closing_day, color, uid))
        self.conn.commit(); self._notify()

    def get_cards(self):
        return self.conn.execute("SELECT id, name, limit_amt, closing_day, color FROM credit_cards WHERE (is_deleted=0 OR is_deleted IS NULL)").fetchall()

    def update_card(self, cid, name, limit, closing_day, color):
        self.conn.execute("UPDATE credit_cards SET name=?, limit_amt=?, closing_day=?, color=?, is_deleted=0 WHERE id=?", (name, limit, closing_day, color, cid))
        self.conn.commit(); self._notify()

    def delete_card(self, cid):
        self.conn.execute("UPDATE transactions SET payment_id=NULL WHERE payment_id=?", (cid,))
        self.conn.execute("UPDATE credit_cards SET is_deleted=1 WHERE id=?", (cid,))
        self.conn.commit(); self._notify()

    def clear_all_cards(self):
        self.conn.execute("DELETE FROM credit_cards"); self.conn.commit(); self._notify()
    
    # [FIXED] Updated to support Billing Cycle Calculation for Accuracy
    def get_card_usage(self, card_id, month_filter=None):
        qs = "SELECT SUM(amount) FROM transactions WHERE payment_id=? AND type='expense' AND (is_deleted=0 OR is_deleted IS NULL)"
        qr = "SELECT SUM(amount) FROM transactions WHERE payment_id=? AND type='repayment' AND (is_deleted=0 OR is_deleted IS NULL)"
        qi = "SELECT SUM(amount) FROM transactions WHERE payment_id=? AND type='income' AND (is_deleted=0 OR is_deleted IS NULL)"
        
        # 1. Get Closing Day
        row = self.conn.execute("SELECT closing_day FROM credit_cards WHERE id=?", (card_id,)).fetchone()
        closing_day = row[0] if row else 0

        args = [card_id]
        if month_filter:
            try:
                y, m = map(int, month_filter.split('-'))
                
                if closing_day > 0:
                    # Calculate Cutoff Date based on Closing Day of the Filtered Month
                    # This ensures "January" view shows transactions only up to January's closing date
                    _, max_days = calendar.monthrange(y, m)
                    eff_day = min(closing_day, max_days)
                    cutoff_dt = datetime(y, m, eff_day, 23, 59, 59)
                    cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
                    
                    qs += " AND date <= ?"
                    qr += " AND date <= ?"
                    qi += " AND date <= ?"
                    args.append(cutoff_str)
                else:
                    # Fallback to standard calendar month logic (End of this month)
                    ny, nm = (y+1, 1) if m==12 else (y, m+1)
                    cutoff = f"{ny}-{nm:02d}-01"
                    qs += " AND date(date) < date(?)"
                    qr += " AND date(date) < date(?)"
                    qi += " AND date(date) < date(?)" 
                    args.append(cutoff)
            except Exception as e: 
                print(f"Error filtering card usage: {e}")
                pass
            
        s = self.conn.execute(qs, tuple(args)).fetchone()[0] or 0.0
        r = self.conn.execute(qr, tuple(args)).fetchone()[0] or 0.0
        i = self.conn.execute(qi, tuple(args)).fetchone()[0] or 0.0
        return s - r - i

    def get_card_transactions(self, card_id, month_str):
        # 1. Get Closing Day
        row = self.conn.execute("SELECT closing_day FROM credit_cards WHERE id=?", (card_id,)).fetchone()
        closing_day = row[0] if row else 0

        # Fallback to standard calendar month if no closing day set
        if not closing_day or closing_day < 1:
            return self.conn.execute("SELECT id, type, item, amount, category, date FROM transactions WHERE payment_id=? AND strftime('%Y-%m', date)=? AND (is_deleted=0 OR is_deleted IS NULL) ORDER BY date DESC", (card_id, month_str)).fetchall()

        # 2. Calculate Billing Cycle
        try:
            t_year, t_month = map(int, month_str.split('-'))

            # End Date = Closing Day of the selected month
            # Handle short months (e.g., Closing Day 31 but Feb has 28)
            _, max_days_curr = calendar.monthrange(t_year, t_month)
            eff_closing_day = min(closing_day, max_days_curr)
            
            end_date = datetime(t_year, t_month, eff_closing_day, 23, 59, 59)

            # Start Date = (Previous Month Closing Day) + 1 Day
            if t_month == 1:
                prev_year = t_year - 1
                prev_month = 12
            else:
                prev_year = t_year
                prev_month = t_month - 1
            
            _, max_days_prev = calendar.monthrange(prev_year, prev_month)
            eff_prev_closing_day = min(closing_day, max_days_prev)
            
            prev_closing_date = datetime(prev_year, prev_month, eff_prev_closing_day, 0, 0, 0)
            start_date = prev_closing_date + timedelta(days=1)

            # Convert to strings for SQL
            s_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
            e_str = end_date.strftime("%Y-%m-%d %H:%M:%S")

            # 3. Query with Date Range
            sql = """
                SELECT id, type, item, amount, category, date 
                FROM transactions 
                WHERE payment_id=? 
                AND date >= ? AND date <= ?
                AND (is_deleted=0 OR is_deleted IS NULL) 
                ORDER BY date DESC
            """
            return self.conn.execute(sql, (card_id, s_str, e_str)).fetchall()

        except Exception as e:
            print(f"Billing Cycle Calc Error: {e}")
            # Fallback
            return self.conn.execute("SELECT id, type, item, amount, category, date FROM transactions WHERE payment_id=? AND strftime('%Y-%m', date)=? AND (is_deleted=0 OR is_deleted IS NULL) ORDER BY date DESC", (card_id, month_str)).fetchall()

    def get_setting(self, key, default=""):
        res = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return res[0] if res else default
    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)); self.conn.commit()

    def check_and_rollover(self, cy, cm):
        pm = cm - 1; py = cy
        if pm == 0: pm = 12; py -= 1
        self.recalculate_rollovers_from(datetime(py, pm, 1))
        return True

    def recalculate_rollovers_from(self, start_date):
        cy, cm = start_date.year, start_date.month
        now = datetime.now()
        has_change = False
        
        while True:
            nm = cm + 1; ny = cy
            if nm > 12: nm = 1; ny += 1
            
            if (ny > now.year + 5): break 
            if (ny == now.year and nm > now.month + 1): break
            
            bal = self.get_month_balance(cy, cm)
            nms = f"{ny}-{nm:02d}"
            td = datetime(ny, nm, 1) 
            
            rows = self.conn.execute(
                "SELECT id, amount, is_deleted FROM transactions WHERE strftime('%Y-%m', date)=? AND (item='ยอดยกมา' OR item='Balance Forward') ORDER BY id", 
                (nms,)
            ).fetchall()
            
            exist = None
            if rows:
                exist = rows[0] 
                if len(rows) > 1:
                    for r_dup in rows[1:]:
                        if r_dup[2] == 0: 
                            self.conn.execute("UPDATE transactions SET is_deleted=1 WHERE id=?", (r_dup[0],))
                            has_change = True

            if bal > 0:
                if exist:
                    current_amt = exist[1]
                    current_status = exist[2]
                    if abs(current_amt - bal) > 0.01 or current_status == 1:
                        self.conn.execute("UPDATE transactions SET amount=?, is_deleted=0 WHERE id=?", (bal, exist[0]))
                        has_change = True
                else: 
                    uid = str(uuid.uuid4())
                    self.conn.execute(
                        "INSERT INTO transactions (type, item, amount, category, date, payment_id, is_deleted, uuid) VALUES (?,?,?,?,?,NULL,0,?)", 
                        ("income", "ยอดยกมา", bal, "Others", td, uid)
                    )
                    has_change = True
            else:
                if exist:
                    if exist[2] == 0:
                        self.conn.execute("UPDATE transactions SET is_deleted=1 WHERE id=?", (exist[0],))
                        has_change = True
            
            cm = nm; cy = ny
            
        if has_change:
            self.conn.commit()
            self._notify()