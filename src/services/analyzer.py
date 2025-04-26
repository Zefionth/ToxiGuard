import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from src.data.manager import DataManager

logger = logging.getLogger(__name__)

class OpenAIAnalyzer:
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
    "violation_score": 0-100,
    "violation": bool,
    "reason": "конкретная причина"
    }

    Примеры:
    - "Иди нахуй": {"toxic":100,"spam":0,"danger":80,"violation_score":100,"violation":true,"reason":"явное оскорбление"}
    - "Ты глупый": {"toxic":70,"spam":0,"danger":30,"violation_score":70,"violation":true,"reason":"скрытое оскорбление"}
    - "У тебя задержка": {"toxic":60,"spam":0,"danger":40,"violation_score":60,"violation":false,"reason":"потенциально оскорбительное"}
- "Купите виагру": {"spam":95,"toxic":0,"danger":50,"violation_score":95,"violation":true,"reason":"коммерческий спам"}"""
    def __init__(self, api_key: str, base_url: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.data_manager: Optional[DataManager] = None

    def set_data_manager(self, data_manager: DataManager) -> None:
        self.data_manager = data_manager

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
            
        try:
            logger.info(f"Analyzing message with sensitivity {self.data_manager.settings['sensitivity']}%")
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
            
            sensitivity_threshold = (1.01 - self.data_manager.settings['sensitivity']/100) * 100
            result['violation'] = result['violation_score'] >= sensitivity_threshold
            
            return result
        
        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            return {
                "spam": 0, "toxic": 0, "danger": 0,
                "violation_score": 0, "violation": False,
                "reason": "Ошибка анализа"
            }