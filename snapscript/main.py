#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
from typing import List, Dict, Any, Optional

from snapscript.core.video_processor import VideoProcessor
from snapscript.core.audio_processor import AudioProcessor, TranscriptionService, FASTER_WHISPER_AVAILABLE
from snapscript.core.ffmpeg_wrapper import FFmpegWrapper
from snapscript.reporting.srt_generator import SRTGenerator
from snapscript.reporting.report_generator import ReportGenerator
from snapscript.utils.fs_utils import get_unique_output_dir, ensure_directory_exists, safe_remove_file
from snapscript.utils.logging_utils import setup_logging

def parse_arguments():
    """Парсинг аргументов командной строки."""
    parser = argparse.ArgumentParser(description="Извлечение снапшотов и транскрипция видео.")
    parser.add_argument("video_file", help="Путь к видеофайлу (MP4, MKV и т.д.).")
    parser.add_argument("-o", "--output", default="userdata", 
                      help="Базовая директория для сохранения папок с результатами (по умолчанию: userdata).")
    parser.add_argument("-v", "--verbose", action="store_true", 
                      help="Включить подробный вывод для отладки.")

    # Аргументы для снапшотов
    parser.add_argument("-t", "--threshold", type=float, default=27.0,
                      help="Порог чувствительности ContentDetector для снапшотов (по умолчанию 27.0). "
                           "Меньше = чувствительнее.")
    parser.add_argument("--stabilization-offset", type=float, default=0.5,
                      help="Смещение в секундах от начала сцены для 'стабилизированного' снимка "
                           "(по умолчанию 0.5).")

    # Аргументы для транскрипции
    parser.add_argument("--transcribe", action="store_true",
                      help="Включить извлечение аудио и транскрипцию.")
    
    # Проверяем доступность faster_whisper перед добавлением аргумента
    if FASTER_WHISPER_AVAILABLE:
        parser.add_argument("--whisper-model", default="medium",
                          choices=["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"],
                          help="Размер модели Whisper для транскрипции (по умолчанию 'medium'). "
                               "'large-v3' самый точный, 'tiny' самый быстрый.")
    else:
        # Добавляем 'заглушку', если faster-whisper не импортирован
        parser.add_argument('--whisper-model', action='store_const', const='medium', 
                          help=argparse.SUPPRESS)

    # Аргумент для извлечения аудио-сегментов
    parser.add_argument("--extract-audio", action="store_true",
                      help="Извлекать аудио для каждого сегмента транскрипции и добавлять плееры в отчет.")
    
    # Аргумент для указания выходного лог-файла
    parser.add_argument("--log-file", 
                      help="Путь к файлу для записи логов. Если не указан, логи выводятся только в консоль.")

    return parser.parse_args()

def process_video(args):
    """Основная функция обработки видео."""
    logger = logging.getLogger('SnapScript')
    
    # Проверяем существование видеофайла
    if not os.path.exists(args.video_file):
        logger.error(f"Видеофайл не найден: {args.video_file}")
        return False
    
    # Проверяем зависимости для транскрипции
    if args.transcribe:
        if not FASTER_WHISPER_AVAILABLE:
            logger.error("Ошибка: библиотека faster-whisper не найдена. "
                        "Установите ее: pip install faster-whisper")
            return False
        
        ffmpeg = FFmpegWrapper()
        if not ffmpeg.is_available:
            logger.error("Ошибка: команда 'ffmpeg' не найдена. Транскрипция невозможна без ffmpeg.")
            return False
    
    # Проверяем зависимости для извлечения аудио-сегментов
    if args.extract_audio:
        ffmpeg = FFmpegWrapper()
        if not ffmpeg.is_available:
            logger.error("Ошибка: команда 'ffmpeg' не найдена. "
                        "Извлечение аудио-сегментов невозможно без ffmpeg.")
            args.extract_audio = False
    
    # Получаем базовое имя видеофайла
    base_name = os.path.splitext(os.path.basename(args.video_file))[0]
    
    # Создаем уникальную папку для вывода
    run_output_dir = get_unique_output_dir(args.output, base_name)
    if not ensure_directory_exists(run_output_dir):
        return False
    
    logger.info(f"Результаты будут сохранены в: {run_output_dir}")
    
    # Инициализируем компоненты
    video_processor = VideoProcessor(
        args.video_file, 
        args.threshold, 
        args.stabilization_offset
    )
    
    srt_generator = SRTGenerator()
    report_generator = ReportGenerator()
    
    # Этап 1: Обработка видео и извлечение снимков
    logger.info("--- Начало обработки снапшотов ---")
    
    # Обнаружение сцен
    scene_list = video_processor.detect_scenes()
    if not scene_list:
        logger.warning("Смены сцен не найдены. Снапшоты и SRT снимков не будут созданы.")
        snapshot_details = []
    else:
        # Извлечение снимков
        snapshot_details = video_processor.extract_snapshots(run_output_dir)
    
    # Этап 2: Создание SRT для снимков
    if snapshot_details:
        srt_snapshot_path = os.path.join(run_output_dir, f"{base_name}_snapshots.srt")
        srt_generator.create_snapshot_srt(snapshot_details, srt_snapshot_path)
    
    # Подготовка данных для комбинированного отчета
    combined_events = []
    
    # Добавляем события снимков
    for snap_time, snap_filename in snapshot_details:
        combined_events.append({
            'type': 'snapshot',
            'timestamp': snap_time.get_seconds(),
            'data': snap_filename
        })
    
    # Инициализируем переменные для транскрипции
    segments_list = []
    audio_segments_available = False
    temp_audio_file = None
    
    logger.info("--- Обработка снапшотов завершена ---")
    
    # Этап 3: Транскрипция (если включена)
    if args.transcribe:
        logger.info("--- Начало транскрипции ---")
        
        # Подготовка директории для аудио-сегментов
        audio_segments_dir = None
        if args.extract_audio:
            audio_segments_dir = os.path.join(run_output_dir, "audio_segments")
            if not ensure_directory_exists(audio_segments_dir):
                args.extract_audio = False
            else:
                logger.info(f"Аудио-сегменты будут сохранены в: {audio_segments_dir}")
        
        # Извлечение аудио
        audio_processor = AudioProcessor()
        temp_audio_file = audio_processor.extract_audio(args.video_file)
        
        if temp_audio_file:
            # Транскрипция аудио
            transcription = TranscriptionService(
                model_size=args.whisper_model,
                device="cpu",
                language="ru"
            )
            
            segments_list, info = transcription.transcribe(temp_audio_file)
            
            if segments_list:
                # Создание SRT с транскрипцией
                srt_transcript_path = os.path.join(run_output_dir, f"{base_name}_transcript.srt")
                srt_generator.create_transcript_srt(segments_list, srt_transcript_path)
                
                # Обработка сегментов для комбинированного отчета
                for segment in segments_list:
                    text = segment.text.strip()
                    if text:
                        # Создаем событие транскрипции
                        segment_event = {
                            'type': 'transcript',
                            'timestamp': segment.start,
                            'end_time': segment.end,
                            'data': text
                        }
                        
                        # Если нужно извлекать аудио-сегменты, делаем это
                        if args.extract_audio and audio_segments_dir:
                            segment_id = f"segment_{int(segment.start * 1000)}-{int(segment.end * 1000)}"
                            audio_file = os.path.join(audio_segments_dir, f"{segment_id}.mp3")
                            
                            # Относительный путь для HTML
                            relative_audio_file = os.path.join("audio_segments", f"{segment_id}.mp3")
                            
                            if audio_processor.extract_audio_segment(
                                args.video_file, audio_file, segment.start, segment.end
                            ):
                                segment_event['audio_file'] = relative_audio_file
                                audio_segments_available = True
                            else:
                                logger.warning(
                                    f"Не удалось извлечь аудио-сегмент для фрагмента {segment_id}"
                                )
                        
                        combined_events.append(segment_event)
            else:
                logger.warning("Транскрипция не дала результатов.")
        else:
            logger.error("Транскрипция не выполнена из-за ошибки извлечения аудио.")
        
        logger.info("--- Транскрипция завершена ---")
    
    # Этап 4: Создание комбинированного HTML отчета
    if combined_events:
        # Сортируем события по времени
        combined_events.sort(key=lambda item: item['timestamp'])
        
        # Создаем отчет
        html_report_path = os.path.join(run_output_dir, "report.html")
        report_generator.create_combined_html_report(
            combined_events, 
            html_report_path, 
            base_name, 
            audio_segments_available
        )
    else:
        logger.warning(
            "Комбинированный HTML отчет не создан, так как нет ни снимков, ни данных транскрипции."
        )
    
    # Очистка временных файлов
    if temp_audio_file:
        safe_remove_file(temp_audio_file)
    
    # Закрываем видеообработчик (освобождаем ресурсы)
    video_processor.close()
    
    return True

def main():
    """Точка входа в приложение."""
    # Парсинг аргументов
    args = parse_arguments()
    
    # Настройка логирования
    setup_logging(args.verbose, args.log_file)
    logger = logging.getLogger('SnapScript')
    
    try:
        # Приветствие
        logger.info("SnapScript - утилита для извлечения снимков из видео в моменты смены сцен")
        
        # Обработка видео
        success = process_video(args)
        
        # Завершение
        if success:
            logger.info("Обработка завершена успешно.")
            return 0
        else:
            logger.error("Обработка завершилась с ошибками.")
            return 1
    except KeyboardInterrupt:
        logger.info("Прервано пользователем.")
        return 130
    except Exception as e:
        logger.exception(f"Необработанная ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 