import logging
import time
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes, CallbackContext
from typing import Any, Dict
from Levenshtein import distance as levenshtein_distance
from src.data.manager import DataManager
from src.services.analyzer import OpenAIAnalyzer

logger = logging.getLogger(__name__)

class Handlers:
    def __init__(self, data_manager: DataManager, analyzer: OpenAIAnalyzer):
        self.data_manager = data_manager
        self.analyzer = analyzer
        self.analyzer.set_data_manager(data_manager)

    async def is_admin(self, update: Update, context: CallbackContext) -> bool:
        """Проверяет, является ли пользователь администратором чата"""
        if update.effective_chat.type == "private":
            return False
            
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            return chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        except Exception as e:
            logger.error(f"Admin check error: {e}")
            return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        if update.effective_chat.type == "private":
            await self.handle_private_chat(update, context)
            return
            
        logger.info(f"Start command from user {update.effective_user.id} in chat {update.effective_chat.id}")
        await update.message.reply_text(
            "🛡️ Бот-модератор для Telegram\n\n"
            "Автоматически удаляет спам, оскорбления и нарушителей.\n"
            "Добавьте меня в группу с правами администратора!"
        )

    async def handle_private_chat(self, update: Update, context: CallbackContext) -> None:
        """Обработчик личных сообщений с ботом"""
        user = update.effective_user
        logger.info(f"Private message from {user.id}")
        
        text = (
            "👋 Привет! Я бот-модератор для групповых чатов.\n\n"
            "Чтобы начать работу:\n"
            "1. Добавьте меня в группу\n"
            "2. Выдайте права администратора\n"
            "3. Настройте чувствительность через /settings\n\n"
            "В личных сообщениях я могу только показать команды: /commands"
        )
        await update.message.reply_text(text)

    async def show_commands(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает список всех команд"""
        commands = [
            "/start - Информация о боте",
            "/commands - Список всех команд",
            "/settings - Текущие настройки (только в группах)",
            "/set_sensitivity <1-100> - Установить строгость (админы)",
            "/add_ban_word <слово> - Добавить запрещенное слово (админы)",
            "/remove_ban_word <слово> - Удалить слово из списка (админы)",
            "/ban_list - Показать запрещенные слова",
            "/stats - Статистика модерации",
            "/user_info <@username> - Информация о пользователе"
        ]
        await update.message.reply_text("📜 Доступные команды:\n\n" + "\n".join(commands))

    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает текущие настройки"""
        if update.effective_chat.type == "private":
            await update.message.reply_text("⚙️ Настройки доступны только в групповых чатах!")
            return
            
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Только администраторы могут просматривать настройки!")
            return
            
        settings = self.data_manager.get_group_settings(update.effective_chat.id)
        ban_words = self.data_manager.get_ban_words(update.effective_chat.id)
        
        response = (
            "⚙️ Текущие настройки:\n\n"
            f"• Чувствительность: {settings['sensitivity']}%\n"
            f"• Автоудаление: {'включено' if settings['auto_delete'] else 'выключено'}\n"
            f"• Предупреждений до бана: {settings['warn_before_ban']}\n"
            f"• Всего запрещенных слов: {len(ban_words)}"
        )
        await update.message.reply_text(response)

    async def set_sensitivity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Устанавливает уровень чувствительности"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Только администраторы могут изменять настройки!")
            return
            
        if not context.args:
            await update.message.reply_text("Укажите уровень от 1 до 100")
            return
        
        try:
            level = int(context.args[0])
            if 1 <= level <= 100:
                current_settings = self.data_manager.get_group_settings(update.effective_chat.id)
                current_settings['sensitivity'] = level
                self.data_manager.update_group_settings(update.effective_chat.id, current_settings)
                await update.message.reply_text(f"✅ Чувствительность установлена на {level}%")
            else:
                await update.message.reply_text("Уровень должен быть от 1 до 100")
        except ValueError:
            await update.message.reply_text("Пожалуйста, укажите число от 1 до 100")

    async def add_ban_word(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Добавляет слово в черный список"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Только администраторы могут изменять черный список!")
            return
            
        if not context.args:
            await update.message.reply_text("Укажите слово для добавления")
            return
        
        word = ' '.join(context.args).lower()
        ban_words = self.data_manager.get_ban_words(update.effective_chat.id)
        
        if word in ban_words:
            await update.message.reply_text(f"❌ Слово '{word}' уже в списке")
        else:
            self.data_manager.add_ban_word(update.effective_chat.id, word)
            await update.message.reply_text(f"✅ Слово '{word}' добавлено в черный список")

    async def remove_ban_word(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Удаляет слово из черного списка"""
        if not await self.is_admin(update, context):
            await update.message.reply_text("❌ Только администраторы могут изменять черный список!")
            return
            
        if not context.args:
            await update.message.reply_text("Укажите слово для удаления")
            return
        
        word = ' '.join(context.args).lower()
        ban_words = self.data_manager.get_ban_words(update.effective_chat.id)
        
        if word not in ban_words:
            await update.message.reply_text(f"❌ Слово '{word}' не найдено в списке")
        else:
            self.data_manager.remove_ban_word(update.effective_chat.id, word)
            await update.message.reply_text(f"✅ Слово '{word}' удалено из черного списка")

    async def show_ban_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает список запрещенных слов"""
        ban_words = self.data_manager.get_ban_words(update.effective_chat.id)
        if not ban_words:
            await update.message.reply_text("📭 Список запрещенных слов пуст")
        else:
            words_list = "\n".join(f"• {word}" for word in ban_words)
            await update.message.reply_text(f"📋 Запрещенные слова:\n\n{words_list}")

    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает статистику модерации"""
        stats = self.data_manager.get_stats(update.effective_chat.id)
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
        
        # Поиск пользователя в текущей группе
        user = self.data_manager.get_user(update.effective_chat.id, user_identifier)
        
        if user:
            response = (
                "👤 Информация о пользователе:\n\n"
                f"• Юзернейм: @{user.get('username', 'нет')}\n"
                f"• Имя: {user.get('first_name', '')} {user.get('last_name', '')}\n"
                f"• Сообщений: {user.get('messages', 0)}\n"
                f"• Нарушений: {user.get('warnings', 0)}\n"
            )
        else:
            response = "Пользователь не найден в этой группе"
        
        await update.message.reply_text(response)
    
    def _check_message_similarity(self, text1: str, text2: str) -> float:
        """Проверяет схожесть сообщений по расстоянию Левенштейна"""
        max_len = max(len(text1), len(text2))
        if max_len == 0:
            return 0.0
        distance = levenshtein_distance(text1.lower(), text2.lower())
        return 1.0 - (distance / max_len)
    
    async def _process_spam_attempt(self, update: Update, context: CallbackContext, user: Any) -> None:
        """Обрабатывает попытку спама повторяющимися сообщениями"""
        try:
            bot_member = await context.bot.get_chat_member(update.message.chat.id, context.bot.id)
            if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                logger.warning("Bot is not admin, can't delete messages")
                return
        except Exception as e:
            logger.error(f"Admin check failed: {e}")
            return

        group_id = update.effective_chat.id
        user_id = user.id
        user_data = self.data_manager.get_user(group_id, user_id)
        
        if not user_data:
            self.data_manager.init_user(group_id, {
                'id': user_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name
            })
            user_data = {'warnings': 0}

        warnings = user_data.get('warnings', 0) + 1
        self.data_manager.update_user_stats(group_id, user_id, {'warnings': warnings})
        self.data_manager.update_stats(group_id, {'violations_found': 1})
        
        settings = self.data_manager.get_group_settings(group_id)
        warning_text = (
            f"🚨 Нарушение правил!\n"
            f"▫️ Причина: флуд\n\n"
            f"Предупреждение {warnings}/{settings['warn_before_ban']}"
        )
        
        try:
            await context.bot.send_message(
                update.message.chat.id,
                warning_text,
                reply_to_message_id=update.message.message_id
            )   
            await update.message.delete()
            self.data_manager.update_stats(group_id, {'deleted_messages': 1})
        except Exception as e:
            logger.error(f"Failed to delete spam message: {str(e)}")
        
        if warnings >= settings['warn_before_ban']:
            await self._ban_user(update, context, user, {"reason": "Многократный флуд"})

    async def handle_message(self, update: Update, context: CallbackContext) -> None:
        """Обрабатывает все входящие сообщения"""
        try:
            if update.effective_chat.type == "private":
                await self.handle_private_chat(update, context)
                return

            if not update.message or not update.message.text:
                return

            message = update.message
            user = message.from_user
            chat = message.chat
            group_id = chat.id
            user_id = user.id

            logger.info(f"New message from {user_id} in chat {group_id}")

            if user.is_bot:
                logger.debug("Ignoring message from bot")
                return
            
            # Инициализация пользователя если нужно
            if not self.data_manager.get_user(group_id, user_id):
                self.data_manager.init_user(group_id, {
                    'id': user_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                })
                
            last_msg = self.data_manager.get_last_message(str(user_id))
            current_time = time.time()
            
            if last_msg:
                time_diff = current_time - last_msg["time"]
                text_similarity = self._check_message_similarity(message.text, last_msg["text"])
                
                if (time_diff < 5 and text_similarity > 0.8) or text_similarity > 0.9:
                    await self._process_spam_attempt(update, context, user)
                    return

            # Обновляем статистику
            self.data_manager.update_user_stats(group_id, user_id, {'messages': 1})
            self.data_manager.update_stats(group_id, {'messages_checked': 1})
            self.data_manager.add_last_message(str(user_id), message.text, current_time)

            # Проверка на запрещенные слова
            ban_words = self.data_manager.get_ban_words(group_id)
            ban_word_violation = any(word in message.text.lower() for word in ban_words)
            
            self.analyzer.set_current_group(update.effective_chat.id)
            violation = (self._create_ban_word_violation() if ban_word_violation 
                        else await self.analyzer.analyze_message(message.text))

            if violation['violation']:
                await self._process_violation(update, context, user, violation)

        except Exception as e:
            logger.error(f"Error in handle_message: {str(e)}", exc_info=True)
            if update.message:
                await update.message.reply_text("⚠️ Произошла ошибка при обработке сообщения")

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
        try:
            bot_member = await context.bot.get_chat_member(update.message.chat.id, context.bot.id)
            if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                logger.warning("Bot is not admin, can't moderate")
                return
        except Exception as e:
            logger.error(f"Admin check failed: {e}")
            return

        group_id = update.effective_chat.id
        user_id = user.id
        
        self.data_manager.update_stats(group_id, {'violations_found': 1})
        user_data = self.data_manager.get_user(group_id, user_id)
        warnings = user_data.get('warnings', 0) + 1
        self.data_manager.update_user_stats(group_id, user_id, {'warnings': warnings})

        warning_msg = await self._send_warning(update, context, user, violation, warnings)
        
        settings = self.data_manager.get_group_settings(group_id)
        if settings['auto_delete']:
            await self._delete_violation_message(update.message, context, warning_msg, group_id)

        if warnings >= settings['warn_before_ban']:
            await self._ban_user(update, context, user, violation)

    async def _send_warning(self, update: Update, context: CallbackContext,
                          user: Any, violation: Dict[str, Any], warnings: int) -> Any:
        """Отправляет предупреждение пользователю"""
        settings = self.data_manager.get_group_settings(update.effective_chat.id)
        
        warning_text = (
            f"🚨 Нарушение правил!\n"
            f"▫️ Причина: {violation['reason']}\n"
            f"▫️ Общий балл: {violation['violation_score']}%\n"
            f"▫️ Спам: {violation['spam']}%\n"
            f"▫️ Токсичность: {violation['toxic']}%\n"
            f"▫️ Опасность: {violation['danger']}%\n\n"
            f"Предупреждение {warnings}/{settings['warn_before_ban']}"
        )
        return await context.bot.send_message(
            update.message.chat.id,
            warning_text,
            reply_to_message_id=update.message.message_id
        )

    async def _delete_violation_message(self, message: Any, 
                                      context: CallbackContext,
                                      warning_msg: Any,
                                      group_id: int) -> None:
        """Удаляет сообщение с нарушением"""
        try:
            await message.delete()
            self.data_manager.update_stats(group_id, {'deleted_messages': 1})
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
            self.data_manager.update_stats(update.effective_chat.id, {'banned_users': 1})
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