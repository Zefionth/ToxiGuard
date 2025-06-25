import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from src.data.manager import DataManager

logger = logging.getLogger(__name__)

class OpenAIAnalyzer:
    ANALYSIS_PROMPT = """Анализируй сообщения по критериям:

    Спам (0-100):
    - Реклама: 90-100
    - Предл. купить/продать: 70-90
    - Бренды: 30-70
    - Флуд: 50-80
    - Ссылки: 80-100
    - Мошеннич.: 100

    Токсичность (0-100):
    - Мат/оскорб.: 90-100
    - Скрыт. оскорб.: 60-80
    - Грубость: 40-60
    - Пасс.агрессия: 30-50
    - Нейтр.: 0-20

    Опасный (0-100):
    - Фишинг/мош.: 100
    - Насилие: 100
    - Угрозы: 90-100
    - Дискриминац.: 80-100

    Ответ ТОЛЬКО JSON: {"spam":%, "toxic":%, "danger":%, "reason":"конкрет.причина"}
    """
    def __init__(self, api_key: str, base_url: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.data_manager: Optional[DataManager] = None
        self.current_group_id: Optional[int] = None

    def set_data_manager(self, data_manager: DataManager) -> None:
        self.data_manager = data_manager

    def set_current_group(self, group_id: int) -> None:
        """Устанавливает текущую группу для анализа"""
        self.current_group_id = group_id

    def _calculate_violation_score(self, spam: float, toxic: float, danger: float) -> float:
        spam_norm = min(max(spam / 100, 0), 1)
        toxic_norm = min(max(toxic / 100, 0), 1)
        danger_norm = min(max(danger / 100, 0), 1)
        
        base_score = max(toxic_norm, danger_norm, spam_norm)
        additional_impact = 0.5 * (toxic_norm + danger_norm + spam_norm - base_score)
        return min(base_score + additional_impact, 1.0) * 100

    async def analyze_message(self, message_text: str) -> Dict[str, Any]:
        if not self.data_manager:
            raise ValueError("DataManager not set!")
            
        if not self.current_group_id:
            raise ValueError("Group ID not set! Call set_current_group() first.")
            
        try:
            group_settings = self.data_manager.get_group_settings(self.current_group_id)
            sensitivity = group_settings['sensitivity']
            
            logger.info(f"Analyzing message with sensitivity {sensitivity}%")
            chat_completion = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.ANALYSIS_PROMPT},
                    {"role": "user", "content": message_text}
                ],
                temperature=0.3
            )
            
            result = json.loads(chat_completion.choices[0].message.content)
            result['violation_score'] = self._calculate_violation_score(
                result['spam'],
                result['toxic'],
                result['danger']
            )
            
            sensitivity_threshold = (1.01 - sensitivity/100) * 100
            result['violation'] = result['violation_score'] >= sensitivity_threshold
            
            return result
        
        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            return {
                "spam": 0, "toxic": 0, "danger": 0,
                "violation_score": 0, "violation": False,
                "reason": "Ошибка анализа"
            }