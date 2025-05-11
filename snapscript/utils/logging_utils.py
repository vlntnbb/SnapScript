#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from typing import Optional

def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
    """Настраивает логирование для приложения.
    
    Args:
        verbose: Если True, устанавливает уровень логирования DEBUG
        log_file: Опциональный путь к файлу для записи логов
    """
    root_logger = logging.getLogger()
    
    # Очищаем уже существующие обработчики, если они есть
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Уровень логирования зависит от флага verbose
    log_level = logging.DEBUG if verbose else logging.INFO
    root_logger.setLevel(log_level)
    
    # Настраиваем форматирование
    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s', 
                                 datefmt='%Y-%m-%d %H:%M:%S')
    
    # Добавляем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Если указан файл лога, добавляем обработчик для записи в файл
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Уменьшаем уровень логов для некоторых библиотек
    logging.getLogger('PySceneDetect').setLevel(logging.WARNING)
    
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """Возвращает логгер с заданным именем.
    
    Args:
        name: Имя логгера
        
    Returns:
        Настроенный логгер
    """
    return logging.getLogger(f'SnapScript.{name}') 