"""
Telegram-бот для автоматической модерации чатов с использованием OpenAI API.

Основные функции:
- Анализ сообщений на спам, токсичность и опасный контент
- Управление черным списком слов
- Система предупреждений и банов
- Гибкие настройки чувствительности
- Подробная статистика модерации
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext
)
from openai import OpenAI
from config import OPENAI_API_TOKEN, TELEGRAM_BOT_TOKEN

# Настройка системы логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('moderation_bot.log'),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)
logger = logging.getLogger(__name__)


class DataManager:
    """
    Класс для управления данными пользователей, настроек и статистики.
    Использует JSON-файл для хранения данных между сессиями.
    """
    
    # Файл для хранения данных
    DATA_FILE = 'user_data.json'
    
    def __init__(self):
        """Инициализирует менеджер данных и загружает информацию из файла"""
        self.settings: Dict[str, Any]  # Настройки модерации
        self.users: Dict[str, Any]     # Данные пользователей
        self.stats: Dict[str, Any]     # Статистика работы
        self._load_data()

    def _default_data(self) -> Dict[str, Any]:
        """
        Возвращает структуру данных по умолчанию.
        
        Returns:
            Словарь с начальными настройками, пустым списком пользователей
            и нулевой статистикой.
        """
        return {
            'settings': {
                'sensitivity': 70,  # Уровень чувствительности (1-100%)
                'ban_words': [      # Список запрещенных слов/фраз
                    'реклама', 'купить', 'http://', 
                    'telegram.me', 'оскорбление'
                ],
                'auto_delete': True,  # Автоматически удалять нарушения
                'warn_before_ban': 3  # Кол-во предупреждений до бана
            },
            'users': {},  # Данные пользователей
            'stats': {     # Статистика модерации
                'messages_checked': 0,
                'violations_found': 0,
                'deleted_messages': 0,
                'banned_users': 0
            }
        }

    def _load_data(self) -> None:
        """Загружает данные из JSON-файла или создает новый при отсутствии"""
        if not os.path.exists(self.DATA_FILE):
            self._create_default_data_file()
        
        try:
            with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Проверяем структуру загруженных данных
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
        """Создает новый файл данных с настройками по умолчанию"""
        try:
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._default_data(), f, ensure_ascii=False, indent=2)
            logger.info("Created new data file with default settings")
        except IOError as e:
            logger.critical(f"Failed to create data file: {e}")
            raise

    def save_data(self) -> None:
        """
        Сохраняет текущие данные в JSON-файл.
        
        Включает настройки, данные пользователей и статистику.
        """
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


class OpenAIAnalyzer:
    """
    Класс для анализа сообщений с помощью OpenAI API.
    Определяет уровень спама, токсичности и опасного контента.
    """
    
    # Шаблон для анализа сообщений
    ANALYSIS_PROMPT = """Ты профессиональный модератор чатов. Анализируй сообщения по критериям:

    1. Спам (0-100%):
    - Коммерческая реклама
    - Флуд и повторения
    - Подозрительные ссылки
    - Мошеннические предложения

    2. Токсичность (0-100%):
    - Явные оскорбления (мат, прямые унижения) - 80-100%
    - Скрытые оскорбления/насмешки - 50-80%
    - Грубость без оскорблений - 30-50%
    - Нейтральные высказывания - 0-30%

    3. Опасный контент (0-100%):
    - Фишинг и мошенничество
    - Призывы к насилию
    - Угрозы
    - Дискриминация

    Формат ответа ТОЛЬКО JSON:
    {
    "spam": 0-100,
    "toxic": 0-100,
    "danger": 0-100,
    "reason": "конкретная причина"
    }"""

    def __init__(self, api_key: str, base_url: str):
        """
        Инициализирует клиент OpenAI.
        
        Args:
            api_key: Ключ API OpenAI
            base_url: Базовый URL API (может быть прокси)
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.data_manager: Optional[DataManager] = None

    def set_data_manager(self, data_manager: DataManager) -> None:
        """Устанавливает DataManager для доступа к настройкам модерации"""
        self.data_manager = data_manager

    def _calculate_violation_score(self, spam: float, toxic: float, danger: float) -> float:
        """
        Вычисляет общий балл нарушения по комбинированной формуле.
        
        Формула:
        - Берется максимальное из значений (spam, toxic, danger)
        - Добавляется 50% от суммы остальных значений
        - Результат ограничивается 100%
        
        Args:
            spam: Оценка спама (0-100)
            toxic: Оценка токсичности (0-100)
            danger: Оценка опасности (0-100)
            
        Returns:
            Общий балл нарушения (0-100)
        """
        # Нормализация значений
        spam_norm = min(max(spam / 100, 0), 1)
        toxic_norm = min(max(toxic / 100, 0), 1)
        danger_norm = min(max(danger / 100, 0), 1)
        
        base_score = max(toxic_norm, danger_norm, spam_norm)
        additional_impact = 0.5 * (toxic_norm + danger_norm + spam_norm - base_score)
        return min(base_score + additional_impact, 1.0) * 100

    async def analyze_message(self, message_text: str) -> Dict[str, Any]:
        """
        Анализирует текст сообщения на нарушения.
        
        Args:
            message_text: Текст сообщения для анализа
            
        Returns:
            Словарь с результатами анализа:
            - spam: оценка спама (0-100)
            - toxic: оценка токсичности (0-100)
            - danger: оценка опасности (0-100)
            - reason: причина нарушения
            - violation_score: общий балл (0-100)
            - violation: является ли нарушением (bool)
        """
        if not self.data_manager:
            raise ValueError("DataManager not set!")
            
        try:
            logger.info(f"Analyzing message with sensitivity {self.data_manager.settings['sensitivity']}%")
            
            # Запрос к OpenAI API
            chat_completion = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.ANALYSIS_PROMPT},
                    {"role": "user", "content": message_text}
                ],
                temperature=0.3  # Низкая температура для большей детерминированности
            )
            
            # Парсинг результата
            result = json.loads(chat_completion.choices[0].message.content)
            
            # Расчет общего балла
            result['violation_score'] = self._calculate_violation_score(
                result['spam'],
                result['toxic'],
                result['danger']
            )
            
            # Проверка на нарушение с учетом чувствительности
            sensitivity_threshold = (1.01 - self.data_manager.settings['sensitivity']/100) * 100
            result['violation'] = result['violation_score'] >= sensitivity_threshold
            
            return result
        
        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            # Возвращаем безопасный результат при ошибке
            return {
                "spam": 0, "toxic": 0, "danger": 0,
                "violation_score": 0, "violation": False,
                "reason": "Ошибка анализа"
            }


class ModerationBot:
    """
    Основной класс бота-модератора.
    Обрабатывает команды, сообщения и управляет всей логикой модерации.
    """
    
    def __init__(self):
        """Инициализирует бота с DataManager и OpenAIAnalyzer"""
        self.data_manager = DataManager()
        self.analyzer = OpenAIAnalyzer(
            api_key=OPENAI_API_TOKEN,
            base_url="https://api.proxyapi.ru/openai/v1"
        )
        self.analyzer.set_data_manager(self.data_manager)
        self.application: Optional[Application] = None

    def setup_handlers(self) -> None:
        """Регистрирует обработчики команд и сообщений"""
        command_handlers = [
            ('start', self.start),
            ('commands', self.show_commands),
            ('settings', self.show_settings),
            ('set_sensitivity', self.set_sensitivity),
            ('add_ban_word', self.add_ban_word),
            ('remove_ban_word', self.remove_ban_word),
            ('ban_list', self.show_ban_list),
            ('stats', self.show_stats),
            ('user_info', self.show_user_info)
        ]

        # Регистрация обработчиков команд
        for cmd, handler in command_handlers:
            self.application.add_handler(CommandHandler(cmd, handler))

        # Обработчик текстовых сообщений (исключая команды)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /start - приветственное сообщение"""
        logger.info(f"Start command from user {update.effective_user.id}")
        await update.message.reply_text(
            "🛡️ Бот-модератор для Telegram\n\n"
            "Автоматически удаляет спам, оскорбления и нарушителей.\n"
            "Добавьте меня в группу с правами администратора!"
        )

    async def show_commands(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /commands - список доступных команд"""
        commands = [
            "/start - Информация о боте",
            "/commands - Список всех команд",
            "/settings - Текущие настройки",
            "/set_sensitivity <1-100> - Установить строгость",
            "/add_ban_word <слово> - Добавить запрещенное слово",
            "/remove_ban_word <слово> - Удалить слово из списка",
            "/ban_list - Показать запрещенные слова",
            "/stats - Статистика модерации",
            "/user_info <@username> - Информация о пользователе"
        ]
        await update.message.reply_text("📜 Доступные команды:\n\n" + "\n".join(commands))

    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /settings - показывает текущие настройки"""
        settings = self.data_manager.settings
        response = (
            "⚙️ Текущие настройки:\n\n"
            f"• Чувствительность: {settings['sensitivity']}%\n"
            f"• Автоудаление: {'включено' if settings['auto_delete'] else 'выключено'}\n"
            f"• Предупреждений до бана: {settings['warn_before_ban']}\n"
            f"• Всего запрещенных слов: {len(settings['ban_words'])}"
        )
        await update.message.reply_text(response)

    async def set_sensitivity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обрабатывает команду /set_sensitivity - устанавливает уровень чувствительности.
        
        Args:
            update: Объект Update от Telegram
            context: Контекст выполнения команды
        """
        if not context.args:
            await update.message.reply_text("Укажите уровень от 1 до 100")
            return
        
        try:
            level = int(context.args[0])
            if 1 <= level <= 100:
                self.data_manager.settings['sensitivity'] = level
                self.data_manager.save_data()
                await update.message.reply_text(f"✅ Чувствительность установлена на {level}%")
            else:
                await update.message.reply_text("Уровень должен быть от 1 до 100")
        except ValueError:
            await update.message.reply_text("Пожалуйста, укажите число от 1 до 100")

    async def add_ban_word(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /add_ban_word - добавляет слово в черный список"""
        if not context.args:
            await update.message.reply_text("Укажите слово для добавления")
            return
        
        word = ' '.join(context.args).lower()
        if word in self.data_manager.settings['ban_words']:
            await update.message.reply_text(f"❌ Слово '{word}' уже в списке")
        else:
            self.data_manager.settings['ban_words'].append(word)
            self.data_manager.save_data()
            await update.message.reply_text(f"✅ Слово '{word}' добавлено в черный список")

    async def remove_ban_word(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /remove_ban_word - удаляет слово из черного списка"""
        if not context.args:
            await update.message.reply_text("Укажите слово для удаления")
            return
        
        word = ' '.join(context.args).lower()
        if word not in self.data_manager.settings['ban_words']:
            await update.message.reply_text(f"❌ Слово '{word}' не найдено в списке")
        else:
            self.data_manager.settings['ban_words'].remove(word)
            self.data_manager.save_data()
            await update.message.reply_text(f"✅ Слово '{word}' удалено из черного списка")

    async def show_ban_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /ban_list - показывает список запрещенных слов"""
        ban_words = self.data_manager.settings['ban_words']
        if not ban_words:
            await update.message.reply_text("📭 Список запрещенных слов пуст")
        else:
            words_list = "\n".join(f"• {word}" for word in ban_words)
            await update.message.reply_text(f"📋 Запрещенные слова:\n\n{words_list}")

    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /stats - показывает статистику модерации"""
        stats = self.data_manager.stats
        response = (
            "📊 Статистика модерации:\n\n"
            f"• Проверено сообщений: {stats['messages_checked']}\n"
            f"• Нарушений найдено: {stats['violations_found']}\n"
            f"• Удалено сообщений: {stats['deleted_messages']}\n"
            f"• Забанено пользователей: {stats['banned_users']}"
        )
        await update.message.reply_text(response)

    async def show_user_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает команду /user_info - показывает информацию о пользователе"""
        if not context.args:
            await update.message.reply_text("Укажите ID или @username пользователя")
            return
        
        user_identifier = context.args[0].lstrip('@')
        user_data = None
        
        # Поиск пользователя по ID или username
        for uid, data in self.data_manager.users.items():
            if uid == user_identifier or data.get('username', '').lower() == user_identifier.lower():
                user_data = data
                break
        
        if user_data:
            response = (
                "👤 Информация о пользователе:\n\n"
                f"• Юзернейм: @{user_data.get('username', 'нет')}\n"
                f"• Имя: {user_data.get('first_name', '')} {user_data.get('last_name', '')}\n"
                f"• Сообщений: {user_data.get('messages', 0)}\n"
                f"• Нарушений: {user_data.get('warnings', 0)}\n"
            )
        else:
            response = "Пользователь не найден"
        
        await update.message.reply_text(response)

    async def handle_message(self, update: Update, context: CallbackContext) -> None:
        """
        Обрабатывает все входящие текстовые сообщения.
        Проверяет на нарушения и принимает соответствующие меры.
        """
        try:
            if not update.message or not update.message.text:
                return

            message = update.message
            user = message.from_user
            chat = message.chat

            logger.info(f"New message from {user.id} in chat {chat.id}")

            # Игнорируем сообщения от других ботов
            if user.is_bot:
                logger.debug("Ignoring message from bot")
                return

            user_id = str(user.id)
            
            # Регистрируем нового пользователя при необходимости
            if user_id not in self.data_manager.users:
                self._init_user_data(user)
                
            # Обновляем статистику
            self._update_user_stats(user_id)
            self.data_manager.stats['messages_checked'] += 1

            # Проверяем на запрещенные слова
            ban_word_violation = self._check_ban_words(message.text)
            
            # Если нет запрещенных слов - анализируем через OpenAI
            violation = (self._create_ban_word_violation() if ban_word_violation 
                        else await self.analyzer.analyze_message(message.text))

            # Обрабатываем нарушение, если оно обнаружено
            if violation['violation']:
                await self._process_violation(update, context, user, violation)

            self.data_manager.save_data()

        except Exception as e:
            logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
            if update.message:
                await update.message.reply_text("⚠️ Произошла ошибка при обработке сообщения")

    def _init_user_data(self, user: Any) -> None:
        """
        Инициализирует данные нового пользователя.
        
        Args:
            user: Объект пользователя Telegram
        """
        self.data_manager.users[str(user.id)] = {
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'warnings': 0,    # Количество предупреждений
            'messages': 0     # Общее количество сообщений
        }
        logger.info(f"New user registered: {user.id}")

    def _update_user_stats(self, user_id: str) -> None:
        """Увеличивает счетчик сообщений пользователя"""
        self.data_manager.users[user_id]['messages'] += 1

    def _check_ban_words(self, text: str) -> bool:
        """
        Проверяет текст на наличие запрещенных слов.
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если найдено запрещенное слово, иначе False
        """
        text_lower = text.lower()
        return any(word in text_lower for word in self.data_manager.settings['ban_words'])

    def _create_ban_word_violation(self) -> Dict[str, Any]:
        """
        Создает результат нарушения для запрещенных слов.
        
        Returns:
            Словарь с параметрами нарушения (аналогично OpenAI)
        """
        return {
            "spam": 90, "toxic": 40, "danger": 70,
            "violation_score": 90, "violation": True,
            "reason": "Запрещенное слово"
        }

    async def _process_violation(self, update: Update, context: CallbackContext, 
                               user: Any, violation: Dict[str, Any]) -> None:
        """
        Обрабатывает обнаруженное нарушение.
        
        Действия:
        1. Увеличивает счетчик нарушений
        2. Отправляет предупреждение
        3. Удаляет сообщение (если включено)
        4. Банит пользователя при превышении лимита предупреждений
        """
        self.data_manager.stats['violations_found'] += 1
        user_id = str(user.id)
        self.data_manager.users[user_id]['warnings'] += 1

        # Отправляем предупреждение
        warning_msg = await self._send_warning(update, context, user, violation)
        
        # Удаляем сообщение с нарушением (если включено)
        if self.data_manager.settings['auto_delete']:
            await self._delete_violation_message(update.message, context, warning_msg)

        # Бан при превышении лимита предупреждений
        if self.data_manager.users[user_id]['warnings'] >= self.data_manager.settings['warn_before_ban']:
            await self._ban_user(update, context, user, violation)

    async def _send_warning(self, update: Update, context: CallbackContext,
                          user: Any, violation: Dict[str, Any]) -> Any:
        """
        Отправляет предупреждение о нарушении.
        
        Args:
            update: Объект Update от Telegram
            context: Контекст выполнения
            user: Объект пользователя
            violation: Данные о нарушении
            
        Returns:
            Объект отправленного сообщения
        """
        warning_text = self._format_warning_text(user, violation)
        return await context.bot.send_message(
            update.message.chat.id,
            warning_text,
            reply_to_message_id=update.message.message_id
        )

    def _format_warning_text(self, user: Any, violation: Dict[str, Any]) -> str:
        """
        Форматирует текст предупреждения о нарушении.
        
        Args:
            user: Объект пользователя
            violation: Данные о нарушении
            
        Returns:
            Отформатированная строка с предупреждением
        """
        return (
            f"🚨 Нарушение правил!\n"
            f"▫️ Причина: {violation['reason']}\n"
            f"▫️ Общий балл: {violation['violation_score']}%\n"
            f"▫️ Спам: {violation['spam']}%\n"
            f"▫️ Токсичность: {violation['toxic']}%\n"
            f"▫️ Опасность: {violation['danger']}%\n\n"
            f"Предупреждение {self.data_manager.users[str(user.id)]['warnings']}/"
            f"{self.data_manager.settings['warn_before_ban']}"
        )

    async def _delete_violation_message(self, message: Any, 
                                      context: CallbackContext,
                                      warning_msg: Any) -> None:
        """
        Удаляет сообщение с нарушением.
        
        Args:
            message: Сообщение для удаления
            context: Контекст выполнения
            warning_msg: Сообщение с предупреждением (для редактирования в случае ошибки)
        """
        try:
            await message.delete()
            self.data_manager.stats['deleted_messages'] += 1
        except Exception as e:
            logger.error(f"Failed to delete message: {str(e)}")
            await warning_msg.edit_text(
                f"{warning_msg.text}\n\n⚠️ Не удалось удалить сообщение"
            )

    async def _ban_user(self, update: Update, context: CallbackContext,
                      user: Any, violation: Dict[str, Any]) -> None:
        """
        Блокирует пользователя за повторные нарушения.
        
        Args:
            update: Объект Update от Telegram
            context: Контекст выполнения
            user: Объект пользователя для бана
            violation: Данные о нарушении
        """
        try:
            await context.bot.ban_chat_member(update.message.chat.id, user.id)
            self.data_manager.stats['banned_users'] += 1
            await context.bot.send_message(
                update.message.chat.id,
                f"🚫 Пользователь @{user.username} забанен за повторные нарушения!"
            )
        except Exception as e:
            logger.error(f"Failed to ban user {user.id}: {str(e)}")
            raise

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик ошибок бота.
        Логирует ошибку и уведомляет пользователя (если возможно).
        """
        logger.error(f"Ошибка: {context.error}", exc_info=True)
        if update and update.message:
            await update.message.reply_text("❌ Произошла ошибка при обработке команды")

    def run(self) -> None:
        """
        Запускает бота в режиме long polling.
        Обрабатывает ошибки запуска и корректно логирует события.
        """
        try:
            self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            self.setup_handlers()
            logger.info("Starting moderation bot...")
            self.application.run_polling()
        except Exception as e:
            logger.critical(f"Bot crashed: {str(e)}", exc_info=True)
        finally:
            logger.info("Bot stopped")


if __name__ == '__main__':
    bot = ModerationBot()
    bot.run()