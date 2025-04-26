import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackContext
from typing import Any, Dict, List
from src.data.manager import DataManager
from src.services.analyzer import OpenAIAnalyzer

logger = logging.getLogger(__name__)

class Handlers:
    def __init__(self, data_manager: DataManager, analyzer: OpenAIAnalyzer):
        self.data_manager = data_manager
        self.analyzer = analyzer

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        logger.info(f"Start command from user {update.effective_user.id}")
        await update.message.reply_text(
            "🛡️ Бот-модератор для Telegram\n\n"
            "Автоматически удаляет спам, оскорбления и нарушителей.\n"
            "Добавьте меня в группу с правами администратора!"
        )

    async def show_commands(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает список всех команд"""
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
        """Показывает текущие настройки"""
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
        """Устанавливает уровень чувствительности"""
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
        """Добавляет слово в черный список"""
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
        """Удаляет слово из черного списка"""
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
        """Показывает список запрещенных слов"""
        ban_words = self.data_manager.settings['ban_words']
        if not ban_words:
            await update.message.reply_text("📭 Список запрещенных слов пуст")
        else:
            words_list = "\n".join(f"• {word}" for word in ban_words)
            await update.message.reply_text(f"📋 Запрещенные слова:\n\n{words_list}")

    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает статистику модерации"""
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
        """Показывает информацию о пользователе"""
        if not context.args:
            await update.message.reply_text("Укажите ID или @username пользователя")
            return
        
        user_identifier = context.args[0].lstrip('@')
        user_data = None
        
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
        """Обрабатывает все входящие сообщения"""
        try:
            if not update.message or not update.message.text:
                return

            message = update.message
            user = message.from_user
            chat = message.chat

            logger.info(f"New message from {user.id} in chat {chat.id}")

            if user.is_bot:
                logger.debug("Ignoring message from bot")
                return

            user_id = str(user.id)
            
            if user_id not in self.data_manager.users:
                self._init_user_data(user)
                
            self._update_user_stats(user_id)
            self.data_manager.stats['messages_checked'] += 1

            ban_word_violation = self._check_ban_words(message.text)
            
            violation = (self._create_ban_word_violation() if ban_word_violation 
                        else await self.analyzer.analyze_message(message.text))

            if violation['violation']:
                await self._process_violation(update, context, user, violation)

            self.data_manager.save_data()

        except Exception as e:
            logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
            if update.message:
                await update.message.reply_text("⚠️ Произошла ошибка при обработке сообщения")

    def _init_user_data(self, user: Any) -> None:
        """Инициализирует данные нового пользователя"""
        self.data_manager.users[str(user.id)] = {
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'warnings': 0,
            'messages': 0,
        }

    def _update_user_stats(self, user_id: str) -> None:
        """Обновляет статистику пользователя"""
        self.data_manager.users[user_id]['messages'] += 1

    def _check_ban_words(self, text: str) -> bool:
        """Проверяет наличие запрещенных слов"""
        return any(word in text.lower() for word in self.data_manager.settings['ban_words'])

    def _create_ban_word_violation(self) -> Dict[str, Any]:
        """Создает результат нарушения для запрещенных слов"""
        return {
            "spam": 90, "toxic": 40, "danger": 70,
            "violation_score": 90, "violation": True,
            "reason": "Запрещенное слово"
        }

    async def _process_violation(self, update: Update, context: CallbackContext, 
                               user: Any, violation: Dict[str, Any]) -> None:
        """Обрабатывает обнаруженное нарушение"""
        self.data_manager.stats['violations_found'] += 1
        user_id = str(user.id)
        self.data_manager.users[user_id]['warnings'] += 1

        warning_msg = await self._send_warning(update, context, user, violation)
        
        if self.data_manager.settings['auto_delete']:
            await self._delete_violation_message(update.message, context, warning_msg)

        if self.data_manager.users[user_id]['warnings'] >= self.data_manager.settings['warn_before_ban']:
            await self._ban_user(update, context, user, violation)

    async def _send_warning(self, update: Update, context: CallbackContext,
                          user: Any, violation: Dict[str, Any]) -> Any:
        """Отправляет предупреждение пользователю"""
        warning_text = (
            f"🚨 Нарушение правил!\n"
            f"▫️ Причина: {violation['reason']}\n"
            f"▫️ Общий балл: {violation['violation_score']}%\n"
            f"▫️ Спам: {violation['spam']}%\n"
            f"▫️ Токсичность: {violation['toxic']}%\n"
            f"▫️ Опасность: {violation['danger']}%\n\n"
            f"Предупреждение {self.data_manager.users[str(user.id)]['warnings']}/"
            f"{self.data_manager.settings['warn_before_ban']}"
        )
        return await context.bot.send_message(
            update.message.chat.id,
            warning_text,
            reply_to_message_id=update.message.message_id
        )

    async def _delete_violation_message(self, message: Any, 
                                      context: CallbackContext,
                                      warning_msg: Any) -> None:
        """Удаляет сообщение с нарушением"""
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
        """Блокирует пользователя"""
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
        """Обработчик ошибок бота"""
        logger.error(f"Ошибка: {context.error}", exc_info=True)
        if update and update.message:
            await update.message.reply_text("❌ Произошла ошибка при обработке команды")