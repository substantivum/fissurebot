import sqlite3
import logging
import time  # Добавлено: используется в методах update_balance и update_experience
from utils import LEVEL_UP_EXPERIENCE  # Убедитесь, что utils.py существует и содержит LEVEL_UP_EXPERIENCE

logger = logging.getLogger('FissureBot')

class BotDatabase:
    def __init__(self):
        self.conn = sqlite3.connect("bot.db")
        self._init_db()
        logger.info("Соединение с базой данных установлено")
        
    def _init_db(self):
        cursor = self.conn.cursor()
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                last_earn REAL DEFAULT 0,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0
            )
        """)
        # Таблица статистики
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id TEXT PRIMARY KEY,
                messages INTEGER DEFAULT 0,
                joined_at REAL DEFAULT 0,
                daily_streak INTEGER DEFAULT 0,
                last_daily REAL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        # Проверка и добавление недостающих колонок
        for table, column, type_ in [
            ("user_stats", "messages", "INTEGER DEFAULT 0"),
            ("user_stats", "joined_at", "REAL DEFAULT 0"),
            ("users", "level", "INTEGER DEFAULT 1"),
            ("users", "experience", "INTEGER DEFAULT 0")
        ]:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_}")
            except sqlite3.OperationalError:
                pass
                
        # Таблица использования эмодзи
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emoji_usage (
                user_id TEXT,
                emoji TEXT,
                count INTEGER,
                PRIMARY KEY (user_id, emoji),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        # Магазин ролей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_shop (
                role_name TEXT PRIMARY KEY,
                price INTEGER
            )
        """)
        # Начальные роли
        cursor.executemany(
            "INSERT OR IGNORE INTO role_shop (role_name, price) VALUES (?, ?)",
            [("VIP", 500), ("Legend", 1000), ("Champion", 2000)]
        )
        self.conn.commit()
        logger.info("Структура БД инициализирована")
    
    def get_user(self, user_id: str):
        """Возвращает данные пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        if not result:
            cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            self.conn.commit()
            return {"user_id": user_id, "balance": 0, "last_earn": 0, "level": 1, "experience": 0}
        return {
            "user_id": result[0],
            "balance": result[1],
            "last_earn": result[2],
            "level": result[3],
            "experience": result[4]
        }
    
    def update_balance(self, user_id: str, amount: int):
        """Обновляет баланс пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        cursor.execute("""
            UPDATE users
            SET balance = balance + ?, last_earn = ?
            WHERE user_id = ?
        """, (amount, time.time(), user_id))
        self.conn.commit()
    
    def update_experience(self, user_id: str, amount: int):
        """Обновляет опыт пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        cursor.execute("""
            UPDATE users
            SET experience = experience + ?
            WHERE user_id = ?
        """, (amount, user_id))
        self.conn.commit()
    
    def get_level(self, user_id: str):
        """Возвращает уровень и опыт пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT level, experience FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        level, exp = result if result else (1, 0)
        return {
            "level": level,
            "experience": exp,
            "next_level_exp": level * LEVEL_UP_EXPERIENCE
        }
    
    def get_user_stats(self, user_id: str):
        """Возвращает статистику пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM user_stats WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        if not result:
            cursor.execute("""
                INSERT INTO user_stats (user_id, joined_at)
                VALUES (?, ?)
            """, (user_id, time.time()))
            self.conn.commit()
            return {
                "user_id": user_id,
                "messages": 0,
                "joined_at": time.time(),
                "daily_streak": 0,
                "last_daily": 0
            }
        return {
            "user_id": result[0],
            "messages": result[1],
            "joined_at": result[2],
            "daily_streak": result[3],
            "last_daily": result[4]
        }
    
    def update_message_count(self, user_id: str):
        """Увеличивает счётчик сообщений"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO user_stats (user_id, joined_at)
            VALUES (?, ?)
        """, (user_id, time.time()))
        cursor.execute("""
            UPDATE user_stats
            SET messages = messages + 1
            WHERE user_id = ?
        """, (user_id,))
        self.conn.commit()
    
    def update_emoji_usage(self, user_id: str, emoji: str):
        """Обновляет использование эмодзи"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO emoji_usage (user_id, emoji, count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, emoji)
            DO UPDATE SET count = count + 1
        """, (user_id, emoji))
        self.conn.commit()
    
    def get_top_users(self, limit=10):
        """Возвращает топ пользователей по балансу"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
        return cursor.fetchall()
    
    def get_top_activity(self, limit=10):
        """Возвращает топ по активности"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.user_id, u.experience, s.messages
            FROM users u
            LEFT JOIN user_stats s ON u.user_id = s.user_id
            ORDER BY u.experience + s.messages DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()