#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import logging
from typing import List, Optional, Tuple, Dict, Any

from snapscript.utils.fs_utils import is_command_available

logger = logging.getLogger('SnapScript.FFmpegWrapper')

class FFmpegWrapper:
    """Класс-обертка для работы с FFmpeg."""
    
    def __init__(self):
        """Инициализация обертки FFmpeg."""
        self._available = is_command_available("ffmpeg")
        if not self._available:
            logger.error("Команда 'ffmpeg' не найдена. Некоторые функции будут недоступны.")
    
    @property
    def is_available(self) -> bool:
        """Проверяет доступность FFmpeg."""
        return self._available
    
    def extract_audio(self, video_path: str, output_audio_path: str, 
                     sample_rate: int = 16000, mono: bool = True) -> bool:
        """Извлекает аудио из видеофайла.
        
        Args:
            video_path: Путь к видеофайлу
            output_audio_path: Путь для сохранения аудио
            sample_rate: Частота дискретизации (по умолчанию 16000 Гц для Whisper)
            mono: Флаг для конвертации в моно
            
        Returns:
            True если успешно, иначе False
        """
        if not self._available:
            logger.error("FFmpeg недоступен. Невозможно извлечь аудио.")
            return False
            
        logger.info(f"Извлечение аудио из {video_path} в {output_audio_path}...")
        
        command = [
            "ffmpeg",
            "-i", video_path,
            "-vn",                             # Не обрабатывать видео
            "-acodec", "pcm_s16le",            # Аудио кодек WAV
            "-ar", str(sample_rate),           # Частота дискретизации
            "-ac", "1" if mono else "2",       # Моно или стерео
            "-y",                              # Перезаписывать без запроса
            output_audio_path
        ]
        
        return self._run_command(command)
    
    def extract_audio_segment(self, video_path: str, output_audio_path: str, 
                             start_time: float, end_time: float) -> bool:
        """Извлекает сегмент аудио из видеофайла.
        
        Args:
            video_path: Путь к видеофайлу
            output_audio_path: Путь для сохранения аудио
            start_time: Начальное время сегмента в секундах
            end_time: Конечное время сегмента в секундах
            
        Returns:
            True если успешно, иначе False
        """
        if not self._available:
            logger.error("FFmpeg недоступен. Невозможно извлечь аудио-сегмент.")
            return False
            
        duration = end_time - start_time
        
        command = [
            "ffmpeg",
            "-i", video_path,                  # Входной файл
            "-ss", f"{start_time:.3f}",        # Начальное время
            "-t", f"{duration:.3f}",           # Длительность
            "-vn",                             # Не обрабатывать видео
            "-acodec", "mp3",                  # Аудио кодек MP3 для веб
            "-ar", "44100",                    # Частота дискретизации
            "-ac", "2",                        # Стерео
            "-ab", "128k",                     # Битрейт
            "-y",                              # Перезаписывать без запроса
            output_audio_path
        ]
        
        return self._run_command(command)
    
    def _run_command(self, command: List[str]) -> bool:
        """Выполняет команду FFmpeg.
        
        Args:
            command: Список аргументов команды
            
        Returns:
            True если команда выполнена успешно, иначе False
        """
        try:
            process = subprocess.run(command, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при выполнении FFmpeg:")
            logger.error(f"Команда: {' '.join(command)}")
            logger.error(f"Код возврата: {e.returncode}")
            logger.error(f"stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("Команда 'ffmpeg' не найдена.")
            return False
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при вызове FFmpeg: {e}")
            return False 