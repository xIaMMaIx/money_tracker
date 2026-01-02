# database.py
import sqlite3
from datetime import datetime
from utils import parse_db_date

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL;")
        except Exception as e:
            print(f"Warning: Could not set WAL mode: {e}")
        self.create_tables()
        self.migrate_db()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY, type TEXT, item TEXT, amount REAL, category TEXT, date TIMESTAMP, payment_id INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT, type TEXT, keywords TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS recurring_expenses (id INTEGER PRIMARY KEY, day INTEGER, item TEXT, amount REAL, category TEXT, payment_id INTEGER, auto_pay INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS credit_cards (id INTEGER PRIMARY KEY, name TEXT, limit_amt REAL, closing_day INTEGER, color TEXT)''')
        
        if cursor.execute("SELECT count(*) FROM categories").fetchone()[0] == 0:
            self.add_defaults(cursor)
        self.conn.commit()

    def migrate_db(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT payment_id FROM transactions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE transactions ADD COLUMN payment_id INTEGER DEFAULT NULL")
        try:
            cursor.execute("SELECT payment_id FROM recurring_expenses LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE recurring_expenses ADD COLUMN payment_id INTEGER DEFAULT NULL")
            cursor.execute("ALTER TABLE recurring_expenses ADD COLUMN auto_pay INTEGER DEFAULT 0")
        self.conn.commit()

    def add_defaults(self, cursor):
        defaults = [
            ("อาหาร", "expense", "ข้าว,ก๋วยเตี๋ยว"), 
            ("เดินทาง", "expense", "รถเมล์,bts"), 
            ("เงินเดือน", "income", "salary"), 
            ("ช้อปปิ้ง", "expense", "shop"), 
            ("อื่นๆ", "expense", "other"), 
            ("อื่นๆ", "income", "other")
        ]
        for n, t, k in defaults:
            cursor.execute("INSERT INTO categories (name, type, keywords) VALUES (?,?,?)", (n, t, k))

    def add_transaction(self, t_type, item, amount, category, date=None, payment_id=None):
        if not date: date = datetime.now()
        if isinstance(date, str):
             try: date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f")
             except: pass

        cursor = self.conn.execute("INSERT INTO transactions (type, item, amount, category, date, payment_id) VALUES (?,?,?,?,?,?)", (t_type, item, amount, category, date, payment_id))
        self.conn.commit()
        last_id = cursor.lastrowid
        
        if item != "ยอดยกมา" and item != "Balance Forward":
            self.recalculate_rollovers_from(date)
        return last_id

    # [UPDATED] รองรับการแก้ไขวันที่ (date parameter)
    def update_transaction(self, tid, item, amount, category, payment_id=None, date=None):
        if date:
             self.conn.execute("UPDATE transactions SET item=?, amount=?, category=?, payment_id=?, date=? WHERE id=?", (item, amount, category, payment_id, date, tid))
        else:
             self.conn.execute("UPDATE transactions SET item=?, amount=?, category=?, payment_id=? WHERE id=?", (item, amount, category, payment_id, tid))
        
        self.conn.commit()
        
        # คำนวณยอดยกมาใหม่ โดยใช้วันที่ของรายการนั้น
        current_date_row = self.conn.execute("SELECT date FROM transactions WHERE id=?", (tid,)).fetchone()
        if current_date_row:
             dt = parse_db_date(current_date_row[0])
             self.recalculate_rollovers_from(dt)

    def delete_transaction(self, tid):
        old_row = self.conn.execute("SELECT date FROM transactions WHERE id=?", (tid,)).fetchone()
        self.conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
        self.conn.commit()
        if old_row:
             dt = parse_db_date(old_row[0])
             self.recalculate_rollovers_from(dt)
    
    def clear_all_transactions(self):
        self.conn.execute("DELETE FROM transactions")
        self.conn.commit()

    def get_transactions(self, date_filter=None, month_filter=None):
        query = """
            SELECT t.id, t.type, t.item, t.amount, t.category, t.date, c.name 
            FROM transactions t
            LEFT JOIN credit_cards c ON t.payment_id = c.id
        """
        params = []
        conditions = []
        if date_filter:
            conditions.append("date(t.date) = date(?)")
            params.append(date_filter)
        elif month_filter: 
            conditions.append("strftime('%Y-%m', t.date) = ?")
            params.append(month_filter)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY t.date DESC"
        return self.conn.execute(query, tuple(params)).fetchall()

    def get_summary(self, filter_str=None):
        base = """
            SELECT 
                SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 
                SUM(CASE WHEN (type='expense' OR type='repayment') THEN amount ELSE 0 END) 
            FROM transactions 
            WHERE (payment_id IS NULL OR type='repayment')
        """
        params = []
        if filter_str:
            if len(filter_str) == 7:
                base += " AND strftime('%Y-%m', date) = ?"
            else:
                base += " AND date(date) = date(?)"
            params.append(filter_str)
        else:
            base += " AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now', 'localtime')"
            
        res = self.conn.execute(base, tuple(params)).fetchone()
        inc, exp = (res[0] or 0), (res[1] or 0)
        bal = inc - exp
        return inc, exp, bal
    
    def get_month_balance(self, year, month):
        month_str = f"{year}-{month:02d}"
        query = """
            SELECT SUM(CASE WHEN type='income' THEN amount ELSE -amount END) 
            FROM transactions 
            WHERE type IN ('income', 'expense', 'repayment') 
            AND (payment_id IS NULL OR type='repayment') 
            AND strftime('%Y-%m', date) = ?
        """
        res = self.conn.execute(query, (month_str,)).fetchone()
        return res[0] if res and res[0] else 0.0
        
    def get_top_transactions(self, t_type, month_str):
        return self.conn.execute("SELECT item, amount FROM transactions WHERE type=? AND strftime('%Y-%m', date) = ? ORDER BY amount DESC LIMIT 10", (t_type, month_str)).fetchall()

    def get_active_days(self, month_str):
        query = "SELECT DISTINCT strftime('%d', date) FROM transactions WHERE strftime('%Y-%m', date) = ?"
        rows = self.conn.execute(query, (month_str,)).fetchall()
        return {int(r[0]) for r in rows}

    def add_recurring(self, day, item, amount, category, payment_id=None, auto_pay=0, force_id=None):
        if force_id:
            self.conn.execute("INSERT OR REPLACE INTO recurring_expenses (id, day, item, amount, category, payment_id, auto_pay) VALUES (?,?,?,?,?,?,?)", (force_id, day, item, amount, category, payment_id, auto_pay))
        else:
            self.conn.execute("INSERT INTO recurring_expenses (day, item, amount, category, payment_id, auto_pay) VALUES (?,?,?,?,?,?)", (day, item, amount, category, payment_id, auto_pay))
        self.conn.commit()

    def get_recurring(self):
        return self.conn.execute("SELECT id, day, item, amount, category, payment_id, auto_pay FROM recurring_expenses ORDER BY day").fetchall()

    def delete_recurring(self, rid):
        self.conn.execute("DELETE FROM recurring_expenses WHERE id=?", (rid,))
        self.conn.commit()
        
    def clear_all_recurring(self):
        self.conn.execute("DELETE FROM recurring_expenses")
        self.conn.commit()

    def is_recurring_paid(self, item, amount, category, month_str):
        c = self.conn.execute("SELECT count(*) FROM transactions WHERE item=? AND amount=? AND category=? AND strftime('%Y-%m', date)=?", (item, amount, category, month_str)).fetchone()[0]
        return c > 0
    
    # [UPDATED] เอาเงื่อนไข payment_id ออก เพื่อให้ยืดหยุ่น (จ่ายด้วยอะไรก็ถือว่าจ่ายแล้ว)
    def is_recurring_paid_v2(self, item, amount, category, month_str, payment_id):
        query = "SELECT count(*) FROM transactions WHERE item=? AND amount=? AND category=? AND strftime('%Y-%m', date)=?"
        args = (item, amount, category, month_str)
        c = self.conn.execute(query, args).fetchone()[0]
        return c > 0

    def get_categories(self, t_type=None):
        if t_type: return self.conn.execute("SELECT id, name, type, keywords FROM categories WHERE type=?", (t_type,)).fetchall()
        return self.conn.execute("SELECT id, name, type, keywords FROM categories").fetchall()

    def add_category(self, name, t_type, keywords, force_id=None):
        if force_id:
            self.conn.execute("INSERT OR REPLACE INTO categories (id, name, type, keywords) VALUES (?,?,?,?)", (force_id, name, t_type, keywords))
        else:
            self.conn.execute("INSERT INTO categories (name, type, keywords) VALUES (?,?,?)", (name, t_type, keywords))
        self.conn.commit()

    def update_category(self, cid, name, keywords):
        self.conn.execute("UPDATE categories SET name=?, keywords=? WHERE id=?", (name, keywords, cid))
        self.conn.commit()

    def delete_category(self, cid):
        curr = self.conn.execute("SELECT name FROM categories WHERE id=?", (cid,)).fetchone()
        if curr and curr[0] == "อื่นๆ": return False 
        self.conn.execute("DELETE FROM categories WHERE id=?", (cid,))
        self.conn.commit()
        return True 
        
    def clear_all_categories(self):
        self.conn.execute("DELETE FROM categories")
        self.conn.commit()

    def add_card(self, name, limit, closing_day, color, force_id=None):
        if force_id:
            self.conn.execute("INSERT OR REPLACE INTO credit_cards (id, name, limit_amt, closing_day, color) VALUES (?,?,?,?,?)", (force_id, name, limit, closing_day, color))
        else:
            self.conn.execute("INSERT INTO credit_cards (name, limit_amt, closing_day, color) VALUES (?,?,?,?)", (name, limit, closing_day, color))
        self.conn.commit()

    def get_cards(self):
        return self.conn.execute("SELECT id, name, limit_amt, closing_day, color FROM credit_cards").fetchall()
    
    def get_card_name(self, cid):
        if not cid: return None
        res = self.conn.execute("SELECT name FROM credit_cards WHERE id=?", (cid,)).fetchone()
        return res[0] if res else None

    def update_card(self, cid, name, limit, closing_day, color):
        self.conn.execute("UPDATE credit_cards SET name=?, limit_amt=?, closing_day=?, color=? WHERE id=?", (name, limit, closing_day, color, cid))
        self.conn.commit()

    def delete_card(self, cid):
        self.conn.execute("UPDATE transactions SET payment_id=NULL WHERE payment_id=?", (cid,))
        self.conn.execute("DELETE FROM credit_cards WHERE id=?", (cid,))
        self.conn.commit()
    
    def clear_all_cards(self):
        self.conn.execute("DELETE FROM credit_cards")
        self.conn.commit()

    def get_card_usage(self, card_id, month_filter=None):
        query_spent = "SELECT SUM(amount) FROM transactions WHERE payment_id=? AND type='expense'"
        query_repaid = "SELECT SUM(amount) FROM transactions WHERE payment_id=? AND type='repayment'"
        args = [card_id]
        
        if month_filter:
            try:
                y, m = map(int, month_filter.split('-'))
                if m == 12: ny, nm = y + 1, 1
                else: ny, nm = y, m + 1
                cutoff_date = f"{ny}-{nm:02d}-01"
                query_spent += " AND date(date) < date(?)"
                query_repaid += " AND date(date) < date(?)"
                args.append(cutoff_date)
            except: pass
            
        spent = self.conn.execute(query_spent, tuple(args)).fetchone()[0] or 0.0
        repaid = self.conn.execute(query_repaid, tuple(args)).fetchone()[0] or 0.0
        return spent - repaid
    
    def get_card_transactions(self, card_id, month_str):
        query = """
            SELECT id, type, item, amount, category, date 
            FROM transactions 
            WHERE payment_id=? AND strftime('%Y-%m', date)=? 
            ORDER BY date DESC
        """
        return self.conn.execute(query, (card_id, month_str)).fetchall()

    def get_setting(self, key, default=""):
        res = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return res[0] if res else default

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def check_and_rollover(self, current_year, current_month):
        prev_month = current_month - 1
        prev_year = current_year
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1
        start_dt = datetime(prev_year, prev_month, 1)
        self.recalculate_rollovers_from(start_dt)
        return True

    def recalculate_rollovers_from(self, start_date):
        curr_year, curr_month = start_date.year, start_date.month
        now = datetime.now()
        
        while True:
            next_month = curr_month + 1
            next_year = curr_year
            if next_month > 12:
                next_month = 1
                next_year += 1
            
            if (next_year > now.year) or (next_year == now.year and next_month > now.month):
                break
            if next_year > now.year + 5: break 

            balance = self.get_month_balance(curr_year, curr_month)
            next_month_str = f"{next_year}-{next_month:02d}"
            target_date = datetime(next_year, next_month, 1)
            
            existing = self.conn.execute("SELECT id FROM transactions WHERE strftime('%Y-%m', date)=? AND (item='ยอดยกมา' OR item='Balance Forward')", (next_month_str,)).fetchone()
            
            if balance > 0:
                if existing:
                    self.conn.execute("UPDATE transactions SET amount=? WHERE id=?", (balance, existing[0]))
                else:
                    self.conn.execute("INSERT INTO transactions (type, item, amount, category, date, payment_id) VALUES (?,?,?,?,?,NULL)", ("income", "ยอดยกมา", balance, "Others", target_date))
            else:
                if existing:
                    self.conn.execute("DELETE FROM transactions WHERE id=?", (existing[0],))
            
            self.conn.commit()
            curr_month = next_month
            curr_year = next_year