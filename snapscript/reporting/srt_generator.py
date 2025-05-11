#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from typing import List, Tuple, Any

from scenedetect.frame_timecode import FrameTimecode
from snapscript.utils.time_utils import format_srt_time
from snapscript.utils.logging_utils import get_logger

class SRTGenerator:
    """Класс для создания SRT файлов."""
    
    def __init__(self):
        """Инициализация генератора SRT."""
        self.logger = get_logger('SRTGenerator')
    
    def create_snapshot_srt(self, snapshot_details: List[Tuple[FrameTimecode, str]], srt_path: str) -> bool:
        """Создает SRT файл из списка деталей снимков.
        
        Args:
            snapshot_details: Список кортежей (время_снимка, имя_файла)
            srt_path: Путь для сохранения SRT файла
            
        Returns:
            True если файл создан успешно, иначе False
        """
        srt_content = ""
        
        for i, (snap_time, snap_filename) in enumerate(snapshot_details):
            start_sec = snap_time.get_seconds()
            end_sec = start_sec + 0.5  # Короткая длительность для отображения
            
            srt_content += f"{i + 1}\n"
            srt_content += f"{format_srt_time(start_sec)} --> {format_srt_time(end_sec)}\n"
            srt_content += f"{snap_filename}\n\n"
        
        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            self.logger.info(f"SRT файл снимков успешно сохранен: {srt_path}")
            return True
        except IOError as e:
            self.logger.error(f"Ошибка записи SRT файла снимков {srt_path}: {e}")
            return False
    
    def create_transcript_srt(self, segments: List[Any], srt_path: str) -> bool:
        """Создает SRT файл из сегментов транскрипции.
        
        Args:
            segments: Список сегментов транскрипции
            srt_path: Путь для сохранения SRT файла
            
        Returns:
            True если файл создан успешно, иначе False
        """
        srt_content = ""
        segment_num = 1
        
        for segment in segments:
            start_time = segment.start
            end_time = segment.end
            text = segment.text.strip()
            
            # Пропускаем пустые сегменты
            if not text:
                continue
            
            srt_content += f"{segment_num}\n"
            srt_content += f"{format_srt_time(start_time)} --> {format_srt_time(end_time)}\n"
            srt_content += f"{text.replace('\n', ' ')}\n\n"
            segment_num += 1
        
        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            self.logger.info(f"SRT файл транскрипта успешно сохранен: {srt_path}")
            return True
        except IOError as e:
            self.logger.error(f"Ошибка записи SRT файла транскрипта {srt_path}: {e}")
            return False 