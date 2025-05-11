#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import cv2
from typing import List, Tuple, Optional

from scenedetect import open_video, SceneManager, ContentDetector
from scenedetect.scene_manager import SceneList
from scenedetect.frame_timecode import FrameTimecode

from snapscript.utils.logging_utils import get_logger

class VideoProcessor:
    """Класс для обработки видео и обнаружения сцен."""
    
    def __init__(self, video_path: str, threshold: float = 27.0, 
                stabilization_offset_sec: float = 0.5):
        """Инициализация обработчика видео.
        
        Args:
            video_path: Путь к видеофайлу
            threshold: Порог для обнаружения сцен (меньше = чувствительнее)
            stabilization_offset_sec: Смещение в секундах от начала сцены
        """
        self.video_path = video_path
        self.threshold = threshold
        self.stabilization_offset_sec = stabilization_offset_sec
        self.logger = get_logger('VideoProcessor')
        self.video = None
        self.scene_list = None
    
    def detect_scenes(self) -> SceneList:
        """Обнаружение сцен в видео.
        
        Returns:
            Список сцен
        """
        if not os.path.exists(self.video_path):
            self.logger.error(f"Видеофайл не найден: {self.video_path}")
            return []
            
        try:
            self.video = open_video(self.video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=self.threshold))
            
            self.logger.info(f"Обнаружение сцен с порогом {self.threshold}...")
            scene_manager.detect_scenes(video=self.video, show_progress=True)
            
            self.scene_list = scene_manager.get_scene_list()
            
            if not self.scene_list:
                self.logger.warning("Смены сцен не найдены.")
            else:
                self.logger.info(f"Найдено {len(self.scene_list)} сцен(ы).")
                
            return self.scene_list
            
        except Exception as e:
            self.logger.error(f"Ошибка при обнаружении сцен: {e}")
            return []
    
    def extract_snapshots(self, output_dir: str) -> List[Tuple[FrameTimecode, str]]:
        """Извлечение снимков для каждой сцены.
        
        Args:
            output_dir: Директория для сохранения снимков
            
        Returns:
            Список кортежей (время_снимка, имя_файла)
        """
        if not self.scene_list or not self.video:
            self.logger.error("Необходимо сначала вызвать detect_scenes()")
            return []
            
        self.logger.info(f"Сохранение стабильных кадров со смещением {self.stabilization_offset_sec} сек...")
        
        saved_count = 0
        snapshot_details = []
        
        for i, (start_time, end_time) in enumerate(self.scene_list):
            # Вычисляем время снимка с учетом смещения
            offset_timecode = FrameTimecode(self.stabilization_offset_sec, self.video.frame_rate)
            snapshot_time = start_time + offset_timecode
            
            # Если сцена слишком короткая для смещения
            if snapshot_time >= end_time:
                if end_time.get_frames() > start_time.get_frames():
                    snapshot_time = end_time - 1
                else:
                    snapshot_time = start_time
                self.logger.warning(
                    f"Сцена {i+1} слишком коротка для смещения {self.stabilization_offset_sec}s. "
                    f"Используется кадр {snapshot_time.get_timecode()}"
                )
            
            try:
                # Перемещаемся к нужному кадру и считываем его
                self.video.seek(target=snapshot_time)
                frame_data = self.video.read()
                
                if frame_data is not False:
                    # Сохраняем кадр
                    snapshot_filename = f"{i + 1}.jpg"
                    snapshot_path = os.path.join(output_dir, snapshot_filename)
                    
                    if cv2.imwrite(snapshot_path, frame_data):
                        saved_count += 1
                        snapshot_details.append((snapshot_time, snapshot_filename))
                    else:
                        self.logger.error(f"Ошибка OpenCV при сохранении кадра: {snapshot_path}")
                else:
                    # Не удалось прочитать кадр, пробуем предыдущий
                    self.logger.error(
                        f"Не удалось прочитать кадр для сцены {i + 1} "
                        f"в позиции {snapshot_time.get_timecode()}."
                    )
                    
                    if snapshot_time.get_frames() > 0:
                        self.video.seek(target=snapshot_time - 1)
                        frame_data = self.video.read()
                        
                        if frame_data is not False:
                            snapshot_filename = f"{i + 1}_fallback.jpg"
                            snapshot_path = os.path.join(output_dir, snapshot_filename)
                            
                            if cv2.imwrite(snapshot_path, frame_data):
                                saved_count += 1
                                snapshot_details.append((snapshot_time, snapshot_filename))
                                self.logger.warning(f"Сохранен предыдущий кадр как {snapshot_filename}")
                            else:
                                self.logger.error(f"Ошибка OpenCV при сохранении fallback кадра: {snapshot_path}")
            
            except Exception as e:
                self.logger.error(
                    f"Ошибка при сохранении кадра для сцены {i + 1} "
                    f"({snapshot_time.get_timecode()}): {e}"
                )
        
        if saved_count > 0:
            self.logger.info(f"Сохранено {saved_count} снапшотов в директорию: {output_dir}")
        else:
            self.logger.warning(f"Не удалось сохранить ни одного снапшота.")
        
        return snapshot_details
    
    def close(self):
        """Освобождает ресурсы."""
        # VideoStream делает это сам, но метод добавлен для совместимости
        self.video = None 