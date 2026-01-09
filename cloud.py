# cloud.py
import json
import requests
import time
import threading
from datetime import datetime

class CloudManager:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.base_url = config.get("firebase_url", "").rstrip('/') if config else ""
        self.secret_key = config.get("cloud_key", "") if config else ""
        
        # cache
        self.cat_map = {}
        self.card_map = {}

    def _request(self, method, path, data=None, params=None):
        if not self.base_url: return None
        url = f"{self.base_url}/{path}.json"
        
        req_params = {}
        if self.secret_key: req_params["auth"] = self.secret_key
        if params: req_params.update(params)
        
        try:
            if method == "GET":
                resp = requests.get(url, params=req_params, timeout=10)
            else:
                resp = requests.put(url, json=data, params=req_params, timeout=10)
            
            if resp.status_code == 200:
                return resp.json()
            else:
                raise Exception(f"Cloud Error {resp.status_code}: {resp.text}")
        except Exception as e:
            raise e

    def _ensure_dict(self, data):
        if data is None: return {}
        if isinstance(data, list):
            new_dict = {}
            for i, item in enumerate(data):
                if item is not None:
                    if isinstance(item, dict) and 'uuid' in item: new_dict[item['uuid']] = item
                    else: new_dict[str(i)] = item
            return new_dict
        return data

    # [NEW] ฟังก์ชันสำหรับรวมข้อมูลโดยให้ความสำคัญกับ status ที่ถูกลบ (Delete Wins)
    def _merge_with_priority(self, cloud_data, local_data):
        merged = cloud_data.copy()
        
        for uid, local_item in local_data.items():
            if uid not in merged:
                # ถ้า Cloud ไม่มี, ให้ใช้ของ Local (เป็นข้อมูลใหม่ที่เพิ่งสร้างในเครื่อง)
                merged[uid] = local_item
            else:
                # ถ้ามีทั้งคู่ ต้องเช็ค Conflict
                cloud_item = merged[uid]
                
                # ดึงค่า is_deleted (แปลงเป็น int เพื่อความชัวร์)
                c_del = int(cloud_item.get('is_deleted', 0))
                l_del = int(local_item.get('is_deleted', 0))
                
                if c_del == 1:
                    # CASE 1: Cloud บอกว่าลบไปแล้ว -> ให้ยึดตาม Cloud (แม้ Local จะยังอยู่ ก็ถือว่า Local ล้าหลัง)
                    merged[uid] = cloud_item
                elif l_del == 1:
                    # CASE 2: Local บอกว่าลบ (และ Cloud ยังไม่ลบ) -> ให้ยึด Local เพื่อส่งสถานะลบขึ้น Cloud
                    merged[uid] = local_item
                else:
                    # CASE 3: ยังอยู่ทั้งคู่ -> ให้ยึด Local (ถือว่าเป็นการแก้ไขข้อมูลล่าสุดจากเครื่องนี้)
                    merged[uid] = local_item
                    
        return merged

    # --- Manual Actions for Settings UI ---

    def test_connection(self):
        try:
            self._request("GET", "last_update")
            return True, "Connection OK"
        except Exception as e:
            return False, str(e)

    def force_push(self, callback=None):
        """ส่งข้อมูลจากเครื่องขึ้น Cloud (ทับของเก่า)"""
        try:
            if callback: callback("Pushing: Reading Local Data...")
            local_cats = self._get_local_categories_dict()
            local_cards = self._get_local_cards_dict()
            local_trans = self._get_local_transactions_dict()
            local_recs = self._get_local_recurring_dict()

            payload = {
                "categories": local_cats,
                "cards": local_cards,
                "transactions": local_trans,
                "recurring": local_recs,
                "last_update": time.time()
            }
            
            if callback: callback("Pushing: Uploading...")
            self._request("PUT", "", payload)
            if callback: callback("Push Success!", "green")
        except Exception as e:
            if callback: callback(f"Error: {e}", "red")

    def force_pull(self, callback=None):
        """ดึงข้อมูลจาก Cloud ลงเครื่อง (ทับของเก่า)"""
        try:
            if callback: callback("Pulling: Fetching Cloud Data...")
            cloud_data = self._request("GET", "") or {}
            
            cloud_cats = self._ensure_dict(cloud_data.get("categories"))
            cloud_cards = self._ensure_dict(cloud_data.get("cards"))
            cloud_trans = self._ensure_dict(cloud_data.get("transactions"))
            cloud_recs = self._ensure_dict(cloud_data.get("recurring"))

            if callback: callback("Pulling: Overwriting Local DB...")
            
            # ปิด Listener ชั่วคราว
            old_notify = self.db.on_data_changed
            self.db.on_data_changed = None
            
            try:
                # 1. ล้างข้อมูลเก่า
                self.db.clear_all_transactions()
                self.db.clear_all_recurring()
                self.db.clear_all_cards()
                self.db.clear_all_categories()
                
                # 2. ลงข้อมูลใหม่ (Cards & Cats ก่อน เพื่อสร้าง Map)
                self._apply_categories_to_local(cloud_cats)
                self._apply_cards_to_local(cloud_cards)
                
                self._refresh_mappings()
                
                # 3. ลง Transaction & Recurring
                self._apply_transactions_to_local(cloud_trans)
                self._apply_recurring_to_local(cloud_recs)
                
            finally:
                self.db.on_data_changed = old_notify

            if callback: callback("Pull Success!", "green")
        except Exception as e:
            if callback: callback(f"Error: {e}", "red")

    def compare_data(self):
        """เปรียบเทียบจำนวนข้อมูล Local vs Cloud"""
        try:
            cloud_data = self._request("GET", "") or {}
            
            c_trans = len(self._ensure_dict(cloud_data.get("transactions")))
            c_cards = len(self._ensure_dict(cloud_data.get("cards")))
            c_cats = len(self._ensure_dict(cloud_data.get("categories")))
            c_recs = len(self._ensure_dict(cloud_data.get("recurring")))
            
            l_trans = len(self._get_local_transactions_dict())
            l_cards = len(self._get_local_cards_dict())
            l_cats = len(self._get_local_categories_dict())
            l_recs = len(self._get_local_recurring_dict())
            
            return (f"Transactions: Local={l_trans} / Cloud={c_trans}\n"
                    f"Cards: Local={l_cards} / Cloud={c_cards}\n"
                    f"Categories: Local={l_cats} / Cloud={c_cats}\n"
                    f"Recurring: Local={l_recs} / Cloud={c_recs}")
        except Exception as e:
            return f"Error Comparing: {e}"

    # --- Sync Logic (Auto) ---
    def sync_data(self, callback=None):
        if self.config:
            self.base_url = self.config.get("firebase_url", "").rstrip('/')
            self.secret_key = self.config.get("cloud_key", "")

        if not self.base_url:
            if callback: callback("No Firebase URL configured")
            return

        def process():
            try:
                if callback: callback("Syncing...")
                cloud_data = self._request("GET", "") or {}
                
                cloud_cats = self._ensure_dict(cloud_data.get("categories"))
                cloud_cards = self._ensure_dict(cloud_data.get("cards"))
                cloud_trans = self._ensure_dict(cloud_data.get("transactions"))
                cloud_recs = self._ensure_dict(cloud_data.get("recurring"))

                local_cats = self._get_local_categories_dict()
                local_cards = self._get_local_cards_dict()
                local_trans = self._get_local_transactions_dict()
                local_recs = self._get_local_recurring_dict()

                # [FIX] ใช้ฟังก์ชัน _merge_with_priority แทนการรวม Dict ธรรมดา
                merged_cats = self._merge_with_priority(cloud_cats, local_cats)
                merged_cards = self._merge_with_priority(cloud_cards, local_cards)
                merged_trans = self._merge_with_priority(cloud_trans, local_trans)
                merged_recs = self._merge_with_priority(cloud_recs, local_recs)

                full_payload = {
                    "categories": merged_cats, "cards": merged_cards,
                    "transactions": merged_trans, "recurring": merged_recs,
                    "last_update": time.time()
                }
                
                # 1. Update Cloud (Push ผสม)
                self._request("PUT", "", full_payload)

                if self.db:
                    old_notify = self.db.on_data_changed
                    self.db.on_data_changed = None
                    try:
                        # 2. Update Local (Apply ผสมลง DB)
                        self._apply_categories_to_local(merged_cats)
                        self._apply_cards_to_local(merged_cards)
                        self._refresh_mappings()
                        self._apply_transactions_to_local(merged_trans)
                        self._apply_recurring_to_local(merged_recs)
                        
                        # ลบข้อมูลขยะจริง ๆ ออกจาก DB (Vacuum)
                        self.db.purge_deleted_data()
                    finally:
                        self.db.on_data_changed = old_notify

                if callback: callback("Sync Complete!")
            except Exception as e:
                import traceback
                traceback.print_exc()
                if callback: callback(f"Error: {str(e)}")

        threading.Thread(target=process, daemon=True).start()

    # --- Helpers ---
    def _get_local_categories_dict(self):
        c = self.db.conn.cursor()
        rows = c.execute("SELECT uuid, name, type, keywords, is_deleted FROM categories WHERE uuid IS NOT NULL").fetchall()
        data = {}
        for r in rows: data[r[0]] = {"name": r[1], "type": r[2], "keywords": r[3], "is_deleted": r[4], "uuid": r[0]}
        return data

    def _get_local_cards_dict(self):
        c = self.db.conn.cursor()
        rows = c.execute("SELECT uuid, name, limit_amt, closing_day, color, is_deleted FROM credit_cards WHERE uuid IS NOT NULL").fetchall()
        data = {}
        for r in rows: data[r[0]] = {"name": r[1], "limit_amt": r[2], "closing_day": r[3], "color": r[4], "is_deleted": r[5], "uuid": r[0]}
        return data

    def _get_local_transactions_dict(self):
        c = self.db.conn.cursor()
        rows = c.execute("SELECT t.uuid, t.type, t.item, t.amount, t.category, t.date, t.is_deleted, c.uuid FROM transactions t LEFT JOIN credit_cards c ON t.payment_id = c.id WHERE t.uuid IS NOT NULL").fetchall()
        data = {}
        for r in rows: data[r[0]] = {"type": r[1], "item": r[2], "amount": r[3], "category": r[4], "date": str(r[5]), "is_deleted": r[6], "payment_uuid": r[7], "uuid": r[0]}
        return data

    def _get_local_recurring_dict(self):
        c = self.db.conn.cursor()
        rows = c.execute("SELECT t.uuid, t.day, t.item, t.amount, t.category, t.auto_pay, t.is_deleted, c.uuid FROM recurring_expenses t LEFT JOIN credit_cards c ON t.payment_id = c.id WHERE t.uuid IS NOT NULL").fetchall()
        data = {}
        for r in rows: data[r[0]] = {"day": r[1], "item": r[2], "amount": r[3], "category": r[4], "auto_pay": r[5], "is_deleted": r[6], "payment_uuid": r[7], "uuid": r[0]}
        return data

    def _refresh_mappings(self):
        self.cat_map = {} 
        self.card_map = {}
        rows = self.db.conn.execute("SELECT uuid, id FROM credit_cards").fetchall()
        for r in rows: self.card_map[r[0]] = r[1]

    def _apply_categories_to_local(self, data_dict):
        for uid, val in data_dict.items():
            exist_id = self.db.get_id_by_uuid("categories", uid)
            is_del = val.get("is_deleted", 0)
            
            if exist_id:
                # กรณีมี UUID นี้อยู่แล้ว: อัปเดตข้อมูลตามปกติ
                if is_del == 1:
                    self.db.conn.execute("UPDATE categories SET is_deleted=1 WHERE id=?", (exist_id,))
                else:
                    self.db.conn.execute("UPDATE categories SET name=?, type=?, keywords=?, is_deleted=0 WHERE id=?", 
                                         (val['name'], val['type'], val.get('keywords', ''), exist_id))
            else:
                # กรณีไม่มี UUID นี้: (เช็คก่อนว่ามีชื่อซ้ำไหม)
                if is_del == 0:
                    # [FIX] ป้องกันชื่อซ้ำ: ค้นหาว่ามีหมวดหมู่ชื่อเดียวกัน Type เดียวกันอยู่แล้วหรือไม่?
                    # (เช็คทั้งที่ Active และที่ถูกลบไปแล้ว เพื่อกู้คืนกลับมาใช้ UUID ใหม่)
                    collision = self.db.conn.execute(
                        "SELECT id FROM categories WHERE name=? AND type=?", 
                        (val['name'], val['type'])
                    ).fetchone()
                    
                    if collision:
                        # เจอชื่อซ้ำ! ให้ Merge โดยการอัปเดต UUID ของตัวเก่าในเครื่อง ให้ตรงกับ Cloud
                        local_id = collision[0]
                        self.db.conn.execute(
                            "UPDATE categories SET uuid=?, keywords=?, is_deleted=0 WHERE id=?", 
                            (uid, val.get('keywords', ''), local_id)
                        )
                    else:
                        # ไม่ซ้ำ -> สร้างใหม่ตามปกติ
                        self.db.conn.execute(
                            "INSERT INTO categories (name, type, keywords, is_deleted, uuid) VALUES (?,?,?,0,?)",
                            (val['name'], val['type'], val.get('keywords', ''), uid)
                        )
        self.db.conn.commit()

    def _apply_cards_to_local(self, data_dict):
        for uid, val in data_dict.items():
            exist_id = self.db.get_id_by_uuid("credit_cards", uid)
            is_del = val.get("is_deleted", 0)

            if exist_id:
                if is_del == 1:
                    self.db.conn.execute("UPDATE credit_cards SET is_deleted=1 WHERE id=?", (exist_id,))
                else:
                    self.db.conn.execute("UPDATE credit_cards SET name=?, limit_amt=?, closing_day=?, color=?, is_deleted=0 WHERE id=?",
                                         (val['name'], val['limit_amt'], val['closing_day'], val['color'], exist_id))
            else:
                if is_del == 0:
                    # [FIX] ป้องกันบัตรชื่อซ้ำ:
                    collision = self.db.conn.execute(
                        "SELECT id FROM credit_cards WHERE name=?", 
                        (val['name'],)
                    ).fetchone()
                    
                    if collision:
                        # เจอชื่อซ้ำ! Merge เข้าตัวเดิม
                        local_id = collision[0]
                        self.db.conn.execute(
                            "UPDATE credit_cards SET uuid=?, limit_amt=?, closing_day=?, color=?, is_deleted=0 WHERE id=?",
                            (uid, val['limit_amt'], val['closing_day'], val['color'], local_id)
                        )
                    else:
                        # ไม่ซ้ำ -> สร้างใหม่
                        self.db.conn.execute(
                            "INSERT INTO credit_cards (name, limit_amt, closing_day, color, is_deleted, uuid) VALUES (?,?,?,?,0,?)",
                            (val['name'], val['limit_amt'], val['closing_day'], val['color'], uid)
                        )
        self.db.conn.commit()

    def _apply_transactions_to_local(self, data_dict):
        for uid, val in data_dict.items():
            pid = self.card_map.get(val.get('payment_uuid'))
            exist_id = self.db.get_id_by_uuid("transactions", uid)
            if exist_id:
                if val.get('is_deleted', 0) == 1: self.db.conn.execute("UPDATE transactions SET is_deleted=1 WHERE id=?", (exist_id,))
                else: self.db.conn.execute("UPDATE transactions SET type=?, item=?, amount=?, category=?, date=?, payment_id=?, is_deleted=0 WHERE id=?", (val['type'], val['item'], val['amount'], val['category'], val['date'], pid, exist_id))
            else:
                if val.get('is_deleted', 0) == 0: self.db.conn.execute("INSERT INTO transactions (type, item, amount, category, date, payment_id, is_deleted, uuid) VALUES (?,?,?,?,?,?,0,?)", (val['type'], val['item'], val['amount'], val['category'], val['date'], pid, uid))
        self.db.conn.commit()

    def _apply_recurring_to_local(self, data_dict):
        for uid, val in data_dict.items():
            pid = self.card_map.get(val.get('payment_uuid'))
            exist_id = self.db.get_id_by_uuid("recurring_expenses", uid)
            if exist_id:
                if val.get('is_deleted', 0) == 1: self.db.conn.execute("UPDATE recurring_expenses SET is_deleted=1 WHERE id=?", (exist_id,))
                else: self.db.conn.execute("UPDATE recurring_expenses SET day=?, item=?, amount=?, category=?, payment_id=?, auto_pay=?, is_deleted=0 WHERE id=?", (val['day'], val['item'], val['amount'], val['category'], pid, val.get('auto_pay',0), exist_id))
            else:
                if val.get('is_deleted', 0) == 0: self.db.conn.execute("INSERT INTO recurring_expenses (day, item, amount, category, payment_id, auto_pay, is_deleted, uuid) VALUES (?,?,?,?,?,?,0,?)", (val['day'], val['item'], val['amount'], val['category'], pid, val.get('auto_pay',0), uid))
        self.db.conn.commit()