"""
Модуль работы с базой данных.
Содержит класс для взаимодействия с SQLite.
"""

import sqlite3
from typing import Dict, Any, Optional, List


class Database:
    """Класс для работы с базой данных бота."""

    def __init__(self, db_path: str = 'moderation_bot.db') -> None:
        """Инициализирует соединение с базой данных."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Инициализирует структуру базы данных."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица групп
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    group_id INTEGER PRIMARY KEY,
                    sensitivity INTEGER DEFAULT 70,
                    auto_delete INTEGER DEFAULT 1,
                    warn_before_ban INTEGER DEFAULT 3
                )
            ''')
            
            # Таблица запрещенных слов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ban_words (
                    group_id INTEGER,
                    word TEXT,
                    PRIMARY KEY (group_id, word),
                    FOREIGN KEY (group_id) REFERENCES groups (group_id)
                )
            ''')
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER,
                    group_id INTEGER,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    warnings INTEGER DEFAULT 0,
                    messages INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, group_id),
                    FOREIGN KEY (group_id) REFERENCES groups (group_id)
                )
            ''')
            
            # Таблица статистики
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    group_id INTEGER PRIMARY KEY,
                    messages_checked INTEGER DEFAULT 0,
                    violations_found INTEGER DEFAULT 0,
                    deleted_messages INTEGER DEFAULT 0,
                    banned_users INTEGER DEFAULT 0,
                    FOREIGN KEY (group_id) REFERENCES groups (group_id)
                )
            ''')
            
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Возвращает соединение с базой данных."""
        return sqlite3.connect(self.db_path)

    def get_group_settings(self, group_id: int) -> Dict[str, Any]:
        """Возвращает настройки группы."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups WHERE group_id = ?', (group_id,))
            result = cursor.fetchone()
            
            if not result:
                self._init_default_group_settings(group_id, cursor)
                conn.commit()
                return {
                    'sensitivity': 70,
                    'auto_delete': True,
                    'warn_before_ban': 3
                }
            
            return {
                'sensitivity': result[1],
                'auto_delete': bool(result[2]),
                'warn_before_ban': result[3]
            }

    def _init_default_group_settings(self, group_id: int, cursor: sqlite3.Cursor) -> None:
        """Инициализирует настройки группы по умолчанию."""
        cursor.execute('INSERT INTO groups (group_id) VALUES (?)', (group_id,))
        cursor.execute('INSERT INTO stats (group_id) VALUES (?)', (group_id,))

    def update_group_settings(self, group_id: int, settings: Dict[str, Any]) -> None:
        """Обновляет настройки группы."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE groups 
                SET sensitivity = ?, auto_delete = ?, warn_before_ban = ?
                WHERE group_id = ?
            ''', (
                settings.get('sensitivity', 70),
                int(settings.get('auto_delete', True)),
                settings.get('warn_before_ban', 3),
                group_id
            ))
            conn.commit()

    def get_ban_words(self, group_id: int) -> List[str]:
        """Возвращает список запрещенных слов для группы."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT word FROM ban_words WHERE group_id = ?', (group_id,))
            return [row[0] for row in cursor.fetchall()]

    def add_ban_word(self, group_id: int, word: str) -> None:
        """Добавляет слово в черный список группы."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO ban_words (group_id, word) VALUES (?, ?)', 
                             (group_id, word.lower()))
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # Слово уже существует

    def remove_ban_word(self, group_id: int, word: str) -> None:
        """Удаляет слово из черного списка группы."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ban_words WHERE group_id = ? AND word = ?',
                         (group_id, word.lower()))
            conn.commit()

    def get_user(self, group_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает данные пользователя в группе."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users 
                WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            result = cursor.fetchone()
            
            if not result:
                return None
                
            return {
                'username': result[2],
                'first_name': result[3],
                'last_name': result[4],
                'warnings': result[5],
                'messages': result[6]
            }

    def init_user(self, group_id: int, user_data: Dict[str, Any]) -> None:
        """Инициализирует данные нового пользователя."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, group_id, username, first_name, last_name, warnings, messages)
                VALUES (?, ?, ?, ?, ?, 0, 0)
            ''', (
                user_data['id'],
                group_id,
                user_data.get('username'),
                user_data.get('first_name'),
                user_data.get('last_name')
            ))
            conn.commit()

    def update_user_stats(self, group_id: int, user_id: int, updates: Dict[str, Any]) -> None:
        """Обновляет статистику пользователя."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for field, value in updates.items():
                cursor.execute(f'''
                    UPDATE users 
                    SET {field} = ?
                    WHERE group_id = ? AND user_id = ?
                ''', (value, group_id, user_id))
            conn.commit()

    def get_stats(self, group_id: int) -> Dict[str, int]:
        """Возвращает статистику модерации для группы."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM stats WHERE group_id = ?', (group_id,))
            result = cursor.fetchone()
            
            if not result:
                return {
                    'messages_checked': 0,
                    'violations_found': 0,
                    'deleted_messages': 0,
                    'banned_users': 0
                }
                
            return {
                'messages_checked': result[1],
                'violations_found': result[2],
                'deleted_messages': result[3],
                'banned_users': result[4]
            }

    def update_stats(self, group_id: int, updates: Dict[str, int]) -> None:
        """Обновляет статистику группы."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for field, value in updates.items():
                cursor.execute(f'''
                    UPDATE stats 
                    SET {field} = {field} + ?
                    WHERE group_id = ?
                ''', (value, group_id))
            conn.commit()