#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import logging

logger = logging.getLogger('SnapScript.FSUtils')

def get_unique_output_dir(base_output_dir: str, base_name: str) -> str:
    """Генерирует уникальный путь к папке вывода.
    Если папка base_output_dir/base_name существует,
    добавляет суффикс (1), (2), ...
    
    Args:
        base_output_dir: Базовая директория
        base_name: Базовое имя папки
        
    Returns:
        Уникальный путь к папке
    """
    output_path = os.path.join(base_output_dir, base_name)
    counter = 1
    
    while os.path.isdir(output_path): 
        output_path = os.path.join(base_output_dir, f"{base_name} ({counter})")
        counter += 1
        
    return output_path

def ensure_directory_exists(path: str) -> bool:
    """Создает директорию, если она не существует.
    
    Args:
        path: Путь к директории
        
    Returns:
        True если создание успешно или директория уже существует,
        False в случае ошибки
    """
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        logger.error(f"Не удалось создать директорию {path}: {e}")
        return False

def is_command_available(command: str) -> bool:
    """Проверяет, доступна ли указанная команда в PATH.
    
    Args:
        command: Имя команды
        
    Returns:
        True если команда доступна, иначе False
    """
    return shutil.which(command) is not None

def create_temp_audio_file(suffix=".wav") -> str:
    """Создает временный аудиофайл.
    
    Args:
        suffix: Расширение файла
        
    Returns:
        Путь к временному файлу
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    temp_file_path = temp_file.name
    temp_file.close()
    return temp_file_path

def safe_remove_file(file_path: str) -> bool:
    """Безопасно удаляет файл, не вызывая исключения, если файл не существует.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        True если файл успешно удален или его не существует,
        False в случае ошибки
    """
    if not file_path or not os.path.exists(file_path):
        return True
        
    try:
        os.remove(file_path)
        return True
    except OSError as e:
        logger.error(f"Не удалось удалить файл {file_path}: {e}")
        return False 