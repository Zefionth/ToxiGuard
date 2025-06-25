import logging
from typing import Dict, Any, Optional, List
from .database import Database

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        self.db = Database()
        self.last_messages: Dict[str, Dict[str, Any]] = {}

    def get_group_settings(self, group_id: int) -> Dict[str, Any]:
        """Возвращает настройки группы"""
        return self.db.get_group_settings(group_id)

    def update_group_settings(self, group_id: int, settings: Dict[str, Any]) -> None:
        """Обновляет настройки группы"""
        self.db.update_group_settings(group_id, settings)

    def get_ban_words(self, group_id: int) -> List[str]:
        """Возвращает список запрещенных слов для группы"""
        return self.db.get_ban_words(group_id)

    def add_ban_word(self, group_id: int, word: str) -> None:
        """Добавляет слово в черный список группы"""
        self.db.add_ban_word(group_id, word)

    def remove_ban_word(self, group_id: int, word: str) -> None:
        """Удаляет слово из черного списка группы"""
        self.db.remove_ban_word(group_id, word)

    def get_user(self, group_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает данные пользователя в группе"""
        return self.db.get_user(group_id, user_id)

    def init_user(self, group_id: int, user_data: Dict[str, Any]) -> None:
        """Инициализирует данные нового пользователя"""
        self.db.init_user(group_id, user_data)

    def update_user_stats(self, group_id: int, user_id: int, updates: Dict[str, Any]) -> None:
        """Обновляет статистику пользователя"""
        self.db.update_user_stats(group_id, user_id, updates)

    def get_stats(self, group_id: int) -> Dict[str, int]:
        """Возвращает статистику модерации для группы"""
        return self.db.get_stats(group_id)

    def update_stats(self, group_id: int, updates: Dict[str, int]) -> None:
        """Обновляет статистику группы"""
        self.db.update_stats(group_id, updates)

    def add_last_message(self, user_id: str, text: str, time: float) -> None:
        """Сохраняет последнее сообщение пользователя"""
        self.last_messages[user_id] = {"text": text, "time": time}

    def get_last_message(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получает последнее сообщение пользователя"""
        return self.last_messages.get(user_id)