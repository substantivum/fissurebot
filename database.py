import sqlite3
import logging
import time
from utils import LEVEL_UP_EXPERIENCE  # Ensure this exists in utils.py

logger = logging.getLogger('FissureBot')

class BotDatabase:
    def __init__(self, db_name='fissure.db'):
        self.conn = sqlite3.connect(db_name)
        self._init_db()
        logger.info("Соединение с базой данных установлено")

    def _init_db(self):
        cursor = self.conn.cursor()
        # Users table
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                last_earn REAL DEFAULT 0,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0
            )
        """)

        # User statistics table
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id TEXT PRIMARY KEY,
                messages INTEGER DEFAULT 0,
                joined_at REAL DEFAULT 0,
                daily_streak INTEGER DEFAULT 0,
                last_daily REAL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        # Role shop table
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS role_shop (
                role_name TEXT PRIMARY KEY,
                price INTEGER
            )
        """)

        # Emoji usage table
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS user_emojis (
                user_id TEXT,
                emoji TEXT,
                count INTEGER,
                PRIMARY KEY (user_id, emoji),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        # Word usage table
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS user_words (
                user_id TEXT,
                word TEXT,
                count INTEGER,
                PRIMARY KEY (user_id, word),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        # Voice activity table
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS voice_activity (
                user_id TEXT PRIMARY KEY,
                total_seconds INTEGER DEFAULT 0,
                last_join_time INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

        # Initial roles in the shop
        cursor.executemany(
            "INSERT OR IGNORE INTO role_shop (role_name, price) VALUES (?, ?)",
            [("VIP", 500), ("Legend", 1000), ("Champion", 2000)]
        )

        self.conn.commit()
        logger.info("Структура БД инициализирована")

    # Methods to work with users
    def get_user(self, user_id: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'user_id': result[0],
                    'balance': result[1],
                    'last_earn': result[2],
                    'level': result[3],
                    'experience': result[4]
                        }
            return None
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при получении пользователя: {e}")
            return None

    def create_user(self, user_id: str):
        try:
            # Add user to the main table
            self.conn.execute(""" 
                INSERT OR IGNORE INTO users (user_id, balance, experience, level)
                VALUES (?, 0, 0, 1)
            """, (user_id,))

            # Add user statistics
            self.conn.execute(""" 
                INSERT OR IGNORE INTO user_stats (user_id, messages, last_daily, daily_streak, joined_at)
                VALUES (?, 0, 0, 0, ?)
            """, (user_id, int(time.time())))

            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при создании пользователя: {e}")

    def update_balance(self, user_id: str, amount: int):
        try:
            self.conn.execute(""" 
                UPDATE users SET balance = balance + ? WHERE user_id = ?
            """, (amount, user_id))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при обновлении баланса: {e}")

    def update_experience(self, user_id: str, amount: int):
        """Updates the user's experience"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(""" 
                UPDATE users SET experience = experience + ? WHERE user_id = ?
            """, (amount, user_id))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при обновлении опыта: {e}")
            
    def update_level_and_exp(self, user_id: str, level: int, experience: int):
        """Обновляет уровень и опыт пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        cursor.execute("""
            UPDATE users
            SET level = ?, experience = ?
            WHERE user_id = ?
        """, (level, experience, user_id))
        self.conn.commit()

    def get_level(self, user_id: str):
        """Gets the user's level and experience"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT level, experience FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        level, exp = result if result else (1, 0)
        return {
            "level": level,
            "experience": exp,
            "next_level_exp": level * LEVEL_UP_EXPERIENCE
        }

    # Methods for user statistics (messages, daily streaks, etc.)
    def update_message_count(self, user_id: str):
        try:
            self.conn.execute(""" 
                UPDATE user_stats
                SET messages = messages + 1
                WHERE user_id = ?
            """, (user_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при обновлении счетчика сообщений: {e}")

    def get_user_stats(self, user_id: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM user_stats WHERE user_id=?", (user_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'user_id': result[0],
                    'messages': result[1],
                    'last_daily': result[2],
                    'daily_streak': result[3],
                    'joined_at': result[4]
                }
            return None
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при получении статистики: {e}")
            return None

    # Methods for tracking emojis and words
    def track_emoji(self, user_id: str, emoji: str):
        if not emoji:
            logger.warning(f"[WARNING] Empty emoji for user {user_id}")
            return

        try:
            self.conn.execute(""" 
                INSERT INTO user_emojis (user_id, emoji, count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, emoji) DO UPDATE SET count = count + 1
            """, (user_id, emoji))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при отслеживании эмодзи: {e}")

    def track_word(self, user_id: str, word: str):
        if not word or len(word) < 4:
            logger.warning(f"[WARNING] Invalid word length or empty word for user {user_id}")
            return

        try:
            self.conn.execute(""" 
                INSERT INTO user_words (user_id, word, count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, word) DO UPDATE SET count = count + 1
            """, (user_id, word))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при отслеживании слов: {e}")

    def get_top_emojis(self, user_id: str, limit: int = 3):
        try:
            cursor = self.conn.cursor()
            cursor.execute(""" 
                SELECT emoji, count FROM user_emojis
                WHERE user_id = ?
                ORDER BY count DESC
                LIMIT ?
            """, (user_id, limit))
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при получении топ эмодзи: {e}")
            return []

    def get_top_words(self, user_id: str, limit: int = 5):
        try:
            cursor = self.conn.cursor()
            cursor.execute(""" 
                SELECT word, count FROM user_words
                WHERE user_id = ?
                ORDER BY count DESC
                LIMIT ?
            """, (user_id, limit))
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при получении топ слов: {e}")
            return []

    # Methods for voice activity

# Methods for voice activity
    def init_voice_user(self, user_id: str):
        """Initialize a user's voice activity record if it doesn't exist"""
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO voice_activity (user_id, total_seconds, last_join_time)
                VALUES (?, 0, NULL)
            """, (user_id,))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при инициализации пользователя для голосового трекинга: {e}")

    def set_voice_join_time(self, user_id: str, timestamp: int):
        """Set the time when user joined a voice channel"""
        try:
            self.init_voice_user(user_id)  # Ensure user exists
            self.conn.execute("""
                UPDATE voice_activity 
                SET last_join_time = ?
                WHERE user_id = ?
            """, (timestamp, user_id))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при установке времени входа: {e}")

    def update_voice_time(self, user_id: str, seconds: int):
        """Update the total time spent in voice channels"""
        try:
            self.init_voice_user(user_id)  # Ensure user exists
            self.conn.execute("""
                UPDATE voice_activity 
                SET total_seconds = total_seconds + ?
                WHERE user_id = ?
            """, (seconds, user_id))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при обновлении голосового времени: {e}")

    def get_voice_join_time(self, user_id: str) -> int:
        """Get the time when user joined voice channel"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT last_join_time FROM voice_activity WHERE user_id = ?
            """, (user_id,))
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при получении времени входа: {e}")
            return 0

    def get_voice_time(self, user_id: str) -> int:
        """Get total time spent in voice channels"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT total_seconds FROM voice_activity WHERE user_id = ?
            """, (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка при получении голосового времени: {e}")
            return 0