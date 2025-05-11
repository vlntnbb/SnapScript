#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import datetime
from typing import List, Dict, Any, Optional, Tuple
from tqdm import tqdm

# Проверяем и импортируем WhisperModel
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

from snapscript.core.ffmpeg_wrapper import FFmpegWrapper
from snapscript.utils.fs_utils import create_temp_audio_file, safe_remove_file
from snapscript.utils.logging_utils import get_logger

class AudioProcessor:
    """Класс для обработки аудио."""
    
    def __init__(self):
        """Инициализация обработчика аудио."""
        self.logger = get_logger('AudioProcessor')
        self.ffmpeg = FFmpegWrapper()
        
    def extract_audio(self, video_path: str, output_path: str = None) -> Optional[str]:
        """Извлекает аудио из видеофайла.
        
        Args:
            video_path: Путь к видеофайлу
            output_path: Путь для сохранения аудио, если не указан создается временный файл
            
        Returns:
            Путь к аудиофайлу или None в случае ошибки
        """
        if not self.ffmpeg.is_available:
            self.logger.error("FFmpeg недоступен. Невозможно извлечь аудио.")
            return None
            
        # Если путь не указан, создаем временный файл
        if not output_path:
            output_path = create_temp_audio_file(suffix=".wav")
            self.logger.info(f"Создан временный аудиофайл: {output_path}")
        
        # Извлекаем аудио
        if self.ffmpeg.extract_audio(video_path, output_path):
            return output_path
        else:
            return None
            
    def extract_audio_segment(self, video_path: str, output_path: str, 
                            start_time: float, end_time: float) -> bool:
        """Извлекает сегмент аудио из видеофайла.
        
        Args:
            video_path: Путь к видеофайлу
            output_path: Путь для сохранения аудио
            start_time: Начальное время сегмента в секундах
            end_time: Конечное время сегмента в секундах
            
        Returns:
            True если успешно, иначе False
        """
        return self.ffmpeg.extract_audio_segment(video_path, output_path, start_time, end_time)


class TranscriptionService:
    """Класс для транскрипции аудио с помощью Whisper."""
    
    def __init__(self, model_size: str = "medium", device: str = "cpu", language: str = "ru"):
        """Инициализация сервиса транскрипции.
        
        Args:
            model_size: Размер модели Whisper
            device: Устройство для вычислений ('cpu' или 'cuda')
            language: Код языка
        """
        self.logger = get_logger('Transcription')
        self.model_size = model_size
        self.device = device
        self.language = language
        self.model = None
        self._available = FASTER_WHISPER_AVAILABLE
        
    @property
    def is_available(self) -> bool:
        """Проверяет доступность Whisper."""
        return self._available
        
    def load_model(self) -> bool:
        """Загружает модель Whisper.
        
        Returns:
            True если модель загружена успешно, иначе False
        """
        if not self._available:
            self.logger.error("Библиотека faster-whisper не установлена.")
            return False
            
        try:
            self.logger.info(f"Загрузка модели Whisper '{self.model_size}'...")
            self.model = WhisperModel(
                self.model_size, 
                device=self.device, 
                compute_type="int8"
            )
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке модели Whisper: {e}")
            return False
    
    def transcribe(self, audio_path: str) -> Tuple[List, Dict[str, Any]]:
        """Транскрибирует аудиофайл.
        
        Args:
            audio_path: Путь к аудиофайлу
            
        Returns:
            Кортеж (список сегментов, информация о транскрипции)
        """
        if not self._available:
            self.logger.error("Библиотека faster-whisper не установлена.")
            return [], {}
            
        if not self.model:
            if not self.load_model():
                return [], {}
        
        try:
            self.logger.info("Транскрипция аудио... (это может занять время)")
            
            segments, info = self.model.transcribe(
                audio_path,
                language=self.language,
                beam_size=5
            )
            
            self.logger.info(f"Обнаружен язык: {info.language} с вероятностью {info.language_probability:.2f}")
            self.logger.info(f"Длительность аудио: {datetime.timedelta(seconds=info.duration)}")
            
            # Собираем все сегменты из генератора в список
            segments_list = []
            total_duration = info.duration
            
            self.logger.info("Обработка сегментов транскрипции...")
            with tqdm(total=total_duration, unit='sec', unit_scale=True, desc="Транскрипция") as pbar:
                for segment in segments:
                    # Обновляем прогресс-бар
                    pbar.n = round(segment.end, 2)
                    pbar.refresh()
                    
                    # Сохраняем сегмент
                    segments_list.append(segment)
                
                # Убедимся, что прогресс-бар дошел до конца
                if total_duration > 0 and pbar.n < total_duration:
                    pbar.n = round(total_duration, 2)
                    pbar.refresh()
            
            return segments_list, info
            
        except Exception as e:
            self.logger.error(f"Ошибка при транскрипции: {e}")
            return [], {} 