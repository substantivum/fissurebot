# utils.py

import logging
from typing import Dict, Any

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FissureBot")

# Глобальные переменные
voice_clients: Dict[int, Any] = {}
queues: Dict[int, list] = {}
current_playing: Dict[int, str] = {}

# Константы
DAILY_COOLDOWN = 86400
LEVEL_UP_EXPERIENCE = 100