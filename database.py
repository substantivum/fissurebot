import sqlite3
import logging
import time
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger('FissureBot')

class BotDatabase:
    def __init__(self, db_name: str = 'fissure.db'):
        """Инициализация базы данных"""
        self.conn = sqlite3.connect(db_name, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        logger.info("Database connection established")

    def _init_db(self) -> None:
        """Инициализация структуры базы данных"""
        tables = {
            'users': """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1,
                    experience INTEGER NOT NULL DEFAULT 0
                )
            """,
            'user_stats': """
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id TEXT PRIMARY KEY,
                    messages INTEGER DEFAULT 0,
                    daily_streak INTEGER DEFAULT 0,
                    last_daily REAL DEFAULT 0,
                    join_timestamp INTEGER,
                    credited_hours INTEGER DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """,
            'role_shop': """
                CREATE TABLE IF NOT EXISTS role_shop (
                    role_name TEXT PRIMARY KEY,
                    price INTEGER NOT NULL
                )
            """,
            'user_emojis': """
                CREATE TABLE IF NOT EXISTS user_emojis (
                    user_id TEXT,
                    emoji TEXT,
                    count INTEGER DEFAULT 1,
                    PRIMARY KEY (user_id, emoji),
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """,
            'user_words': """
                CREATE TABLE IF NOT EXISTS user_words (
                    user_id TEXT,
                    word TEXT,
                    count INTEGER DEFAULT 1,
                    PRIMARY KEY (user_id, word),
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """,
            'voice_activity': """
                CREATE TABLE IF NOT EXISTS voice_activity (
                    user_id TEXT PRIMARY KEY,
                    total_seconds INTEGER DEFAULT 0,
                    last_join_time INTEGER,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """,
            'command_cooldowns': """
                CREATE TABLE IF NOT EXISTS command_cooldowns (
                    user_id TEXT PRIMARY KEY,
                    last_coinflip REAL DEFAULT 0,
                    last_duel REAL DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """
        }

        with self.conn:
            for table, schema in tables.items():
                try:
                    self.conn.execute(schema)
                except sqlite3.Error as e:
                    logger.error(f"Error creating {table}: {e}")

    # User methods
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Получает данные пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return dict(cursor.fetchone()) if cursor.fetchone() else None
        except sqlite3.Error as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    def create_user(self, user_id: str) -> None:
        """Создает нового пользователя"""
        with self.conn:
            try:
                # Main user table
                self.conn.execute(
                    "INSERT OR IGNORE INTO users (user_id) VALUES (?)", 
                    (user_id,)
                )
                # Statistics
                self.conn.execute(
                    "INSERT OR IGNORE INTO user_stats (user_id, join_timestamp) VALUES (?, ?)",
                    (user_id, int(time.time()))
                )
                # Cooldowns
                self.conn.execute(
                    "INSERT OR IGNORE INTO command_cooldowns (user_id) VALUES (?)",
                    (user_id,)
                )
            except sqlite3.Error as e:
                logger.error(f"Error creating user {user_id}: {e}")

    def update_balance(self, user_id: str, amount: int) -> None:
        """Изменяет баланс пользователя"""
        with self.conn:
            try:
                self.conn.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
            except sqlite3.Error as e:
                logger.error(f"Error updating balance for {user_id}: {e}")

    def update_experience(self, user_id: str, amount: int) -> None:
        """Добавляет опыт пользователю"""
        with self.conn:
            try:
                self.conn.execute(
                    "UPDATE users SET experience = experience + ? WHERE user_id = ?",
                    (amount, user_id)
                )
            except sqlite3.Error as e:
                logger.error(f"Error updating XP for {user_id}: {e}")

    # Statistics methods
    def get_user_stats(self, user_id: str) -> Optional[Dict]:
        """Получает статистику пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
            return dict(cursor.fetchone()) if cursor.fetchone() else None
        except sqlite3.Error as e:
            logger.error(f"Error getting stats for {user_id}: {e}")
            return None

    def update_message_count(self, user_id: str) -> None:
        """Увеличивает счетчик сообщений"""
        with self.conn:
            try:
                self.conn.execute(
                    "UPDATE user_stats SET messages = messages + 1 WHERE user_id = ?",
                    (user_id,)
                )
            except sqlite3.Error as e:
                logger.error(f"Error updating message count for {user_id}: {e}")

    # Emoji and word tracking
    def track_emoji(self, user_id: str, emoji: str) -> None:
        """Отслеживает использование эмодзи"""
        if not emoji:
            return
            
        with self.conn:
            try:
                self.conn.execute(
                    """INSERT INTO user_emojis (user_id, emoji, count)
                       VALUES (?, ?, 1)
                       ON CONFLICT(user_id, emoji) DO UPDATE SET count = count + 1""",
                    (user_id, emoji)
                )
            except sqlite3.Error as e:
                logger.error(f"Error tracking emoji for {user_id}: {e}")

    def track_word(self, user_id: str, word: str) -> None:
        """Отслеживает использование слов"""
        if not word or len(word) < 4:
            return
            
        with self.conn:
            try:
                self.conn.execute(
                    """INSERT INTO user_words (user_id, word, count)
                       VALUES (?, ?, 1)
                       ON CONFLICT(user_id, word) DO UPDATE SET count = count + 1""",
                    (user_id, word)
                )
            except sqlite3.Error as e:
                logger.error(f"Error tracking word for {user_id}: {e}")

    # Voice activity methods
    def set_voice_join_time(self, user_id: str, timestamp: Optional[int]) -> None:
        """Устанавливает время входа в голосовой канал"""
        with self.conn:
            try:
                # Ensure user exists
                self.conn.execute(
                    "INSERT OR IGNORE INTO voice_activity (user_id) VALUES (?)",
                    (user_id,)
                )
                self.conn.execute(
                    "UPDATE voice_activity SET last_join_time = ? WHERE user_id = ?",
                    (timestamp, user_id)
                )
            except sqlite3.Error as e:
                logger.error(f"Error setting voice join time for {user_id}: {e}")

    def update_voice_time(self, user_id: str, seconds: int) -> None:
        """Обновляет общее время в голосовых каналах"""
        with self.conn:
            try:
                self.conn.execute(
                    "UPDATE voice_activity SET total_seconds = total_seconds + ? WHERE user_id = ?",
                    (seconds, user_id)
                )
            except sqlite3.Error as e:
                logger.error(f"Error updating voice time for {user_id}: {e}")

    def get_voice_join_time(self, user_id: str) -> int:
        """Получает время входа в голосовой канал"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT last_join_time FROM voice_activity WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0
        except sqlite3.Error as e:
            logger.error(f"Error getting voice join time for {user_id}: {e}")
            return 0

    # Command cooldowns
    def update_last_used(self, user_id: str, command_name: str) -> None:
        """Обновляет время последнего использования команды"""
        column = f"last_{command_name}"
        with self.conn:
            try:
                self.conn.execute(
                    f"""INSERT INTO command_cooldowns (user_id, {column})
                        VALUES (?, strftime('%s','now'))
                        ON CONFLICT(user_id) DO UPDATE SET {column} = strftime('%s','now')""",
                    (user_id,)
                )
            except sqlite3.Error as e:
                logger.error(f"Error updating {command_name} cooldown for {user_id}: {e}")

    def get_last_used(self, user_id: str, command_name: str) -> int:
        """Получает время последнего использования команды"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                f"SELECT last_{command_name} FROM command_cooldowns WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0
        except sqlite3.Error as e:
            logger.error(f"Error getting {command_name} cooldown for {user_id}: {e}")
            return 0

    def set_join_timestamp(self, user_id: str, timestamp: int) -> None:
        """Устанавливает время присоединения к серверу"""
        with self.conn:
            try:
                self.conn.execute(
                    "UPDATE user_stats SET join_timestamp = ? WHERE user_id = ?",
                    (timestamp, user_id)
                )
            except sqlite3.Error as e:
                logger.error(f"Error setting join timestamp for {user_id}: {e}")