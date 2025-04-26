import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DataManager:
    DATA_FILE = 'user_data.json'
    
    def __init__(self):
        self.settings: Dict[str, Any]
        self.users: Dict[str, Any]
        self.stats: Dict[str, Any]
        self._load_data()

    def _default_data(self) -> Dict[str, Any]:
        return {
            'settings': {
                'sensitivity': 70,
                'ban_words': ['реклама', 'купить', 'http://', 'telegram.me', 'оскорбление'],
                'auto_delete': True,
                'warn_before_ban': 3
            },
            'users': {},
            'stats': {
                'messages_checked': 0,
                'violations_found': 0,
                'deleted_messages': 0,
                'banned_users': 0
            }
        }

    def _load_data(self) -> None:
        if not os.path.exists(self.DATA_FILE):
            self._create_default_data_file()
        
        try:
            with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not all(key in data for key in ['settings', 'users', 'stats']):
                raise ValueError("Invalid data structure")
                
            self.settings = data['settings']
            self.users = data['users']
            self.stats = data['stats']
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error loading data: {e}, creating new file")
            self._create_default_data_file()
            self._load_data()

    def _create_default_data_file(self) -> None:
        try:
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._default_data(), f, ensure_ascii=False, indent=2)
            logger.info("Created new data file with default settings")
        except IOError as e:
            logger.critical(f"Failed to create data file: {e}")
            raise

    def save_data(self) -> None:
        data = {
            'settings': self.settings,
            'users': self.users,
            'stats': self.stats
        }
        try:
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"Failed to save data: {e}")