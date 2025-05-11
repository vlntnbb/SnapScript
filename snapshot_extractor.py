#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import logging
import cv2
import subprocess # Для вызова ffmpeg
import tempfile   # Для временного аудиофайла
import shutil     # Для проверки наличия ffmpeg
import datetime   # Для форматирования времени в Whisper SRT
from tqdm import tqdm

# Проверяем и импортируем WhisperModel, обрабатываем возможный ImportError
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

from scenedetect import open_video, SceneManager, ContentDetector
from scenedetect.frame_timecode import FrameTimecode

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger('SnapshotExtractor')
# Логгер PySceneDetect тоже настроим
logging.getLogger('PySceneDetect').setLevel(logging.WARNING) # Уменьшим детальность логов PySceneDetect


def format_srt_time(time_sec: float) -> str:
    """Форматирует время в секундах в формат SRT (ЧЧ:ММ:СС,ммм)."""
    # Используем datetime для корректной обработки
    delta = datetime.timedelta(seconds=time_sec)
    hours, remainder = divmod(delta.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int(delta.microseconds / 1000)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{milliseconds:03}"

def create_srt(snapshot_details: list[tuple[FrameTimecode, str]], srt_path: str):
    """Создает SRT файл из списка деталей снимков (время, имя файла)."""
    srt_content = ""
    for i, (snap_time, snap_filename) in enumerate(snapshot_details):
        start_sec = snap_time.get_seconds()
        end_sec = start_sec + 0.5 # Короткая длительность для отображения имени файла
        srt_content += f"{i + 1}\n"
        srt_content += f"{format_srt_time(start_sec)} --> {format_srt_time(end_sec)}\n"
        srt_content += f"{snap_filename}\n\n"

    try:
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        logger.info(f"SRT файл снимков успешно сохранен: {srt_path}")
    except IOError as e:
        logger.error(f"Ошибка записи SRT файла снимков {srt_path}: {e}")

# Новая функция для создания SRT транскрипта
def create_transcript_srt(segments: list, srt_path: str):
    """Создает SRT файл из сегментов транскрипции Whisper."""
    srt_content = ""
    segment_num = 1
    for segment in segments:
        start_time = segment.start
        end_time = segment.end
        text = segment.text.strip()

        # Пропускаем пустые сегменты, если такие вдруг появятся
        if not text:
            continue

        srt_content += f"{segment_num}\n"
        srt_content += f"{format_srt_time(start_time)} --> {format_srt_time(end_time)}\n"
        # Добавляем текст, обрабатывая возможные переносы строк внутри него
        srt_content += f"{text.replace('\n', ' ')}\n\n"
        segment_num += 1

    try:
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        logger.info(f"SRT файл транскрипта успешно сохранен: {srt_path}")
    except IOError as e:
        logger.error(f"Ошибка записи SRT файла транскрипта {srt_path}: {e}")

# --- Новая функция для создания HTML отчета ---
def create_html_report(snapshot_details: list[tuple[FrameTimecode, str]], html_path: str, video_base_name: str):
    """Создает HTML файл с таблицей снимков (время, изображение)."""
    logger.info(f"Генерация HTML отчета: {html_path}")
    # Базовый CSS для таблицы
    html_css = """
    <style>
        body { font-family: sans-serif; }
        table { border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: middle; }
        th { background-color: #f2f2f2; }
        img { max-width: 320px; height: auto; display: block; }
    </style>
    """
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Отчет по снимкам: {video_base_name}</title>
    {html_css}
</head>
<body>
    <h1>Отчет по снимкам: {video_base_name}</h1>
    <table>
        <thead>
            <tr>
                <th>№</th>
                <th>Таймкод</th>
                <th>Снимок</th>
            </tr>
        </thead>
        <tbody>
"""

    for i, (snap_time, snap_filename) in enumerate(snapshot_details):
        time_str = snap_time.get_timecode()
        # Имя файла используется как ссылка для <img>
        html_content += f"""            <tr>
                <td>{i + 1}</td>
                <td>{time_str}</td>
                <td><img src="{snap_filename}" alt="Снимок {i + 1}"></td>
            </tr>
"""

    html_content += """        </tbody>
    </table>
</body>
</html>"""

    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"HTML отчет успешно сохранен: {html_path}")
    except IOError as e:
        logger.error(f"Ошибка записи HTML отчета {html_path}: {e}")

# --- Новая функция для извлечения аудио-фрагмента
def extract_audio_segment(video_path: str, output_audio_path: str, start_time: float, end_time: float) -> bool:
    """Извлекает фрагмент аудио из видеофайла с помощью ffmpeg."""
    duration = end_time - start_time
    command = [
        "ffmpeg",
        "-i", video_path,      # Входной файл
        "-ss", f"{start_time:.3f}",  # Начальное время
        "-t", f"{duration:.3f}",     # Длительность
        "-vn",                 # Не обрабатывать видео
        "-acodec", "mp3",      # Аудио кодек MP3 для лучшей поддержки в браузерах
        "-ar", "44100",        # Обычная частота дискретизации для веб
        "-ac", "2",            # Стерео
        "-ab", "128k",         # Битрейт
        "-y",                  # Перезаписывать выходной файл без запроса
        output_audio_path
    ]
    try:
        # Используем stderr=subprocess.PIPE и stdout=subprocess.PIPE, чтобы скрыть вывод ffmpeg
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при извлечении аудио-фрагмента с помощью ffmpeg:")
        logger.error(f"Команда: {' '.join(e.cmd)}")
        logger.error(f"Код возврата: {e.returncode}")
        logger.error(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при вызове ffmpeg для извлечения аудио-фрагмента: {e}")
        return False

# --- Обновленная функция для создания комбинированного HTML отчета ---
def create_combined_html_report(combined_events: list[dict], html_path: str, video_base_name: str, audio_segments_available: bool = False):
    """Создает HTML файл с хронологическим списком снимков и текстом транскрипции.
    Тайминги указываются только у скриншотов, а текст транскрипции располагается
    между скриншотами в хронологическом порядке.
    
    Если audio_segments_available=True, добавляются аудио-плееры к каждому сегменту транскрипции.
    """
    logger.info(f"Генерация комбинированного HTML отчета: {html_path}")
    html_css = """
    <style>
        body { font-family: sans-serif; line-height: 1.6; }
        .event { border: 1px solid #ddd; margin-bottom: 15px; padding: 10px; border-radius: 5px; }
        .event-time { font-weight: bold; color: #555; font-size: 0.9em; }
        .snapshot img { max-width: 480px; height: auto; display: block; margin-top: 5px; }
        .transcript { margin-top: 10px; margin-bottom: 10px; display: flex; align-items: center; }
        .transcript p { margin: 5px 0; flex-grow: 1; }
        .audio-player { margin-right: 10px; }
        .play-button {
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 5px 10px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 12px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        .playing {
            background-color: #FF5722; /* Оранжевый цвет для активного аудио */
        }
        .speed-controls {
            position: fixed;
            top: 10px;
            right: 10px;
            background-color: #f8f8f8;
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #ddd;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            z-index: 1000;
        }
        .speed-button {
            background-color: #e7e7e7;
            border: none;
            color: black;
            padding: 5px 8px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 12px;
            margin: 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        .speed-active {
            background-color: #2196F3;
            color: white;
        }
        .auto-scroll-option {
            margin-top: 10px;
            display: flex;
            align-items: center;
        }
        .auto-scroll-option input {
            margin-right: 5px;
        }
        .auto-scroll-option label {
            font-size: 14px;
            cursor: pointer;
        }
        .current-playing {
            border-left: 4px solid #FF5722;
            padding-left: 15px;
        }
    </style>
    """
    
    # JavaScript для управления аудио-плеерами (остановка предыдущего при запуске нового)
    audio_control_js = """
    <script>
        // Переменная для хранения текущего воспроизводимого аудио
        let currentlyPlaying = null;
        // Переменная для хранения текущей активной кнопки
        let currentButton = null;
        // Переменная для хранения текущего активного элемента (контейнер транскрипции)
        let currentElement = null;
        // Массив всех аудио-элементов
        let allAudioElements = [];
        // Текущая скорость воспроизведения
        let currentPlaybackRate = 1.0;
        // Следовать ли за аудио
        let autoScroll = true;
        
        // Функция инициализации - вызывается при загрузке страницы
        window.onload = function() {
            // Собираем все аудио-элементы в массив
            allAudioElements = Array.from(document.querySelectorAll('audio'));
            console.log(`Найдено ${allAudioElements.length} аудио-элементов`);
            
            // Выделяем кнопку скорости 1x как активную по умолчанию
            document.getElementById('speed-1').classList.add('speed-active');
            
            // Устанавливаем начальное значение чекбокса автопрокрутки
            document.getElementById('auto-scroll').checked = autoScroll;
        };
        
        // Функция переключения автопрокрутки
        function toggleAutoScroll() {
            autoScroll = document.getElementById('auto-scroll').checked;
        }
        
        // Функция для изменения скорости воспроизведения
        function changeSpeed(speed) {
            // Обновляем текущую скорость
            currentPlaybackRate = speed;
            
            // Применяем скорость к текущему воспроизводимому аудио, если оно есть
            if (currentlyPlaying) {
                currentlyPlaying.playbackRate = speed;
            }
            
            // Обновляем визуальное отображение активной кнопки скорости
            document.querySelectorAll('.speed-button').forEach(button => {
                button.classList.remove('speed-active');
            });
            document.getElementById('speed-' + speed.toString().replace('.', '_')).classList.add('speed-active');
        }
        
        // Функция для получения следующего аудио-элемента
        function getNextAudio(currentAudio) {
            // Находим индекс текущего аудио в массиве
            const currentIndex = allAudioElements.indexOf(currentAudio);
            // Если текущий элемент найден и это не последний элемент
            if (currentIndex !== -1 && currentIndex < allAudioElements.length - 1) {
                // Возвращаем следующий элемент
                return allAudioElements[currentIndex + 1];
            }
            // В противном случае возвращаем null
            return null;
        }
        
        // Функция для прокрутки к элементу
        function scrollToElement(element) {
            if (element) {
                // Находим ближайший скриншот до этого элемента
                let prevSnapshot = element.previousElementSibling;
                while (prevSnapshot && !prevSnapshot.classList.contains('snapshot')) {
                    prevSnapshot = prevSnapshot.previousElementSibling;
                }
                
                // Если есть скриншот перед текущим элементом и он находится не слишком далеко,
                // прокручиваем к этому скриншоту
                if (prevSnapshot && prevSnapshot.classList.contains('snapshot') && 
                    element.offsetTop - prevSnapshot.offsetTop < window.innerHeight) {
                    prevSnapshot.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
                // Иначе прокручиваем к текущему элементу
                else {
                    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        }
        
        // Функция для воспроизведения аудио и остановки предыдущего
        function playAudio(audioId, buttonElement) {
            // Получаем элемент аудио
            const audioElement = document.getElementById(audioId);
            // Находим контейнер transcript, который содержит этот аудио
            const transcriptElement = buttonElement.closest('.transcript');
            
            // Если есть текущая активная кнопка, убираем класс playing
            if (currentButton) {
                currentButton.classList.remove('playing');
                currentButton.innerHTML = '▶';
            }
            
            // Если есть текущий активный элемент, убираем класс current-playing
            if (currentElement) {
                currentElement.classList.remove('current-playing');
            }
            
            // Если есть текущее воспроизводимое аудио и это не то же самое, что мы пытаемся запустить
            if (currentlyPlaying && currentlyPlaying !== audioElement) {
                // Останавливаем предыдущее аудио
                currentlyPlaying.pause();
                currentlyPlaying.currentTime = 0;
            }
            
            // Если мы нажимаем на уже играющее аудио, останавливаем его
            if (currentlyPlaying === audioElement && !audioElement.paused) {
                audioElement.pause();
                currentlyPlaying = null;
                currentButton = null;
                currentElement = null;
                return;
            }
            
            // Воспроизводим новое аудио и сохраняем ссылку на него
            audioElement.playbackRate = currentPlaybackRate; // Устанавливаем выбранную скорость
            audioElement.play();
            currentlyPlaying = audioElement;
            
            // Сохраняем ссылку на кнопку и изменяем её внешний вид
            currentButton = buttonElement;
            currentButton.classList.add('playing');
            currentButton.innerHTML = '⏸'; // Меняем иконку на "пауза"
            
            // Сохраняем ссылку на элемент и добавляем класс current-playing
            currentElement = transcriptElement;
            currentElement.classList.add('current-playing');
            
            // Если включена опция автопрокрутки, прокручиваем к текущему элементу
            if (autoScroll) {
                scrollToElement(transcriptElement);
            }
            
            // Добавляем обработчик события окончания аудио
            audioElement.onended = function() {
                // Когда аудио закончилось, возвращаем исходный вид кнопке
                if (currentButton) {
                    currentButton.classList.remove('playing');
                    currentButton.innerHTML = '▶';
                }
                
                // Убираем выделение с текущего элемента
                if (currentElement) {
                    currentElement.classList.remove('current-playing');
                }
                
                // Очищаем ссылку на текущее аудио
                currentlyPlaying = null;
                
                // Находим следующий аудио-элемент
                const nextAudio = getNextAudio(audioElement);
                if (nextAudio) {
                    // Находим ID кнопки для следующего аудио
                    const nextAudioId = nextAudio.id;
                    const nextButtonId = 'btn_' + nextAudioId;
                    const nextButton = document.getElementById(nextButtonId);
                    
                    // Если нашли кнопку, запускаем следующее аудио
                    if (nextButton) {
                        playAudio(nextAudioId, nextButton);
                    }
                }
            };
        }
    </script>
    """
    
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Комбинированный отчет: {video_base_name}</title>
    {html_css}
    {audio_control_js if audio_segments_available else ''}
</head>
<body>
    <h1>Комбинированный отчет: {video_base_name}</h1>
"""

    # Добавляем элементы управления скоростью, если доступны аудио-сегменты
    if audio_segments_available:
        html_content += """
    <div class="speed-controls">
        <span>Скорость: </span>
        <button id="speed-1" class="speed-button" onclick="changeSpeed(1.0)">1x</button>
        <button id="speed-1_25" class="speed-button" onclick="changeSpeed(1.25)">1.25x</button>
        <button id="speed-1_5" class="speed-button" onclick="changeSpeed(1.5)">1.5x</button>
        <button id="speed-1_75" class="speed-button" onclick="changeSpeed(1.75)">1.75x</button>
        <button id="speed-2" class="speed-button" onclick="changeSpeed(2.0)">2x</button>
        <button id="speed-2_5" class="speed-button" onclick="changeSpeed(2.5)">2.5x</button>
        <div class="auto-scroll-option">
            <input type="checkbox" id="auto-scroll" checked onchange="toggleAutoScroll()">
            <label for="auto-scroll">Следовать за аудио</label>
        </div>
    </div>
    """

    html_content += """    <div class="timeline">
"""

    # Сортируем все события по времени
    combined_events.sort(key=lambda event: event['timestamp'])
    
    # Обрабатываем каждое событие в хронологическом порядке
    for event in combined_events:
        event_type = event['type']
        timestamp_sec = event['timestamp']
        data = event['data']
        
        if event_type == 'snapshot':
            # Для снимков добавляем таймкод
            time_str = format_srt_time(timestamp_sec)
            html_content += f'<div class="event snapshot">'
            html_content += f'<div class="event-time">Снимок: {time_str}</div>'
            html_content += f'<div class="snapshot"><img src="{data}" alt="Снимок {time_str}"></div>'
            html_content += '</div>\n'
        elif event_type == 'transcript':
            # Для транскрипции добавляем текст без таймкода
            text_html = data.replace('\n', ' ')
            
            html_content += f'<div class="transcript">'
            
            # Если доступны аудио-сегменты, добавляем аудио-плеер
            if audio_segments_available and 'audio_file' in event:
                audio_file = event['audio_file']
                segment_id = f"audio_{int(timestamp_sec * 1000)}"
                button_id = f"btn_{segment_id}"
                html_content += f'''
                <div class="audio-player">
                    <audio id="{segment_id}" src="{audio_file}"></audio>
                    <button id="{button_id}" class="play-button" onclick="playAudio('{segment_id}', this)">▶</button>
                </div>
                '''
            
            html_content += f'<p>{text_html}</p>'
            html_content += '</div>\n'
    
    html_content += """    </div>
</body>
</html>"""

    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Комбинированный HTML отчет успешно сохранен: {html_path}")
    except IOError as e:
        logger.error(f"Ошибка записи комбинированного HTML отчета {html_path}: {e}")

# --- Функция для вывода прогресса транскрипции ---
def print_transcription_progress(step: float, total: float):
    """Callback функция для вывода прогресса транскрипции.
    Выводит прогресс каждые ~10 секунд обработанного аудио.
    """
    # Используем nonlocal для изменения переменной из внешней области видимости
    # Объявим ее перед циклом транскрипции
    global last_progress_print_time
    progress_interval_sec = 10.0 # Как часто выводить прогресс (в секундах аудио)

    if total > 0 and step >= last_progress_print_time + progress_interval_sec:
        progress_percent = (step / total) * 100
        # Используем print вместо logger, чтобы вывод был более заметным и не смешивался с логами ошибок
        print(f"  Транскрипция: обработано {step:.1f} / {total:.1f} сек ({progress_percent:.1f}%)", flush=True)
        last_progress_print_time = step


# Новая функция для проверки ffmpeg
def is_ffmpeg_available():
    """Проверяет, доступна ли команда ffmpeg в PATH."""
    return shutil.which("ffmpeg") is not None

# Новая функция для извлечения аудио
def extract_audio(video_path: str, output_audio_path: str) -> bool:
    """Извлекает аудио из видеофайла с помощью ffmpeg."""
    logger.info(f"Извлечение аудио из {video_path} в {output_audio_path}...")
    command = [
        "ffmpeg",
        "-i", video_path,      # Входной файл
        "-vn",                 # Не обрабатывать видео
        "-acodec", "pcm_s16le", # Аудио кодек (WAV)
        "-ar", "16000",         # Частота дискретизации 16kHz (рекомендуется для Whisper)
        "-ac", "1",             # Моно
        "-y",                  # Перезаписывать выходной файл без запроса
        output_audio_path
    ]
    try:
        # Используем stderr=subprocess.PIPE и stdout=subprocess.PIPE, чтобы скрыть вывод ffmpeg
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info(f"Аудио успешно извлечено.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при извлечении аудио с помощью ffmpeg:")
        logger.error(f"Команда: {' '.join(e.cmd)}")
        logger.error(f"Код возврата: {e.returncode}")
        logger.error(f"stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("Ошибка: команда 'ffmpeg' не найдена. Убедитесь, что ffmpeg установлен и доступен в PATH.")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при вызове ffmpeg: {e}")
        return False

# --- Логика для создания уникальной папки вывода ---
def get_unique_output_dir(base_output_dir: str, video_base_name: str) -> str:
    """Генерирует уникальный путь к папке вывода.
    Если папка base_output_dir/video_base_name существует,
    добавляет суффикс (1), (2), ...
    """
    output_path = os.path.join(base_output_dir, video_base_name)
    counter = 1
    # Используем os.path.isdir() для более надежной проверки директории
    while os.path.isdir(output_path): 
        output_path = os.path.join(base_output_dir, f"{video_base_name} ({counter})")
        counter += 1
    return output_path

# Обновляем основную функцию
def extract_snapshots_and_transcript(
    video_path: str,
    output_dir: str = '.', # Это теперь базовая папка для результатов
    threshold: float = 27.0,
    stabilization_offset_sec: float = 0.5,
    transcribe: bool = False,
    whisper_model_size: str = "medium",
    extract_audio_segments: bool = False  # Новый параметр для извлечения аудио-сегментов
):
    """
    Извлекает снапшоты, создает SRT файл для них,
    опционально извлекает аудио, транскрибирует его и создает SRT транскрипта.
    Если extract_audio_segments=True, то для каждого сегмента транскрипции
    создается отдельный аудио-файл.
    Все результаты сохраняются в уникальную папку с именем видеофайла.
    """
    if not os.path.exists(video_path):
        logger.error(f"Видеофайл не найден: {video_path}")
        return

    # Проверка зависимостей для транскрипции
    if transcribe:
        if not FASTER_WHISPER_AVAILABLE:
            logger.error("Ошибка: библиотека faster-whisper не найдена. Установите ее: pip install faster-whisper")
            return
        if not is_ffmpeg_available():
            logger.error("Ошибка: команда 'ffmpeg' не найдена. Транскрипция невозможна без ffmpeg.")
            transcribe = False
    
    # Проверка зависимостей для извлечения аудио-сегментов
    if extract_audio_segments and not is_ffmpeg_available():
        logger.error("Ошибка: команда 'ffmpeg' не найдена. Извлечение аудио-сегментов невозможно без ffmpeg.")
        extract_audio_segments = False

    base_name = os.path.splitext(os.path.basename(video_path))[0]

    # --- Определяем и создаем уникальную папку для вывода --- 
    run_output_dir = get_unique_output_dir(output_dir, base_name)
    try:
        os.makedirs(run_output_dir, exist_ok=True)
        logger.info(f"Результаты будут сохранены в: {run_output_dir}")
    except OSError as e:
        logger.error(f"Не удалось создать папку вывода {run_output_dir}: {e}")
        return

    # --- Обновляем пути для сохранения файлов --- 
    # Все пути теперь внутри run_output_dir
    snapshot_dir = run_output_dir # Снимки прямо в папку запуска
    srt_transcript_path = os.path.join(run_output_dir, f"{base_name}_transcript.srt")
    html_report_path = os.path.join(run_output_dir, "report.html")
    
    # Создаем папку для аудио-сегментов, если нужно
    audio_segments_dir = None
    if extract_audio_segments:
        audio_segments_dir = os.path.join(run_output_dir, "audio_segments")
        try:
            os.makedirs(audio_segments_dir, exist_ok=True)
            logger.info(f"Аудио-сегменты будут сохранены в: {audio_segments_dir}")
        except OSError as e:
            logger.error(f"Не удалось создать папку для аудио-сегментов {audio_segments_dir}: {e}")
            extract_audio_segments = False

    video = None
    temp_audio_file = None
    try:
        # --- Обнаружение сцен и сохранение снапшотов ---
        logger.info("--- Начало обработки снапшотов ---")
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=threshold))
        logger.info(f"Обнаружение сцен с порогом {threshold}...")
        scene_manager.detect_scenes(video=video, show_progress=True)
        scene_list = scene_manager.get_scene_list()

        if not scene_list:
            logger.warning("Смены сцен не найдены. Снапшоты и SRT снимков не будут созданы.")
            snapshot_details = []
        else:
            logger.info(f"Найдено {len(scene_list)} сцен(ы).")
            logger.info(f"Сохранение стабильных кадров со смещением {stabilization_offset_sec} сек...")
            saved_count = 0
            snapshot_details = []
            for i, (start_time, end_time) in enumerate(scene_list):
                offset_timecode = FrameTimecode(stabilization_offset_sec, video.frame_rate)
                snapshot_time = start_time + offset_timecode

                if snapshot_time >= end_time:
                    if end_time.get_frames() > start_time.get_frames():
                        snapshot_time = end_time - 1
                    else:
                        snapshot_time = start_time
                    logger.warning(f"Сцена {i+1} слишком коротка для смещения {stabilization_offset_sec}s. Используется кадр {snapshot_time.get_timecode()}")

                try:
                    video.seek(target=snapshot_time)
                    frame_data = video.read()

                    if frame_data is not False:
                        snapshot_filename = f"{i + 1}.jpg"
                        # Используем обновленный snapshot_dir
                        snapshot_path = os.path.join(snapshot_dir, snapshot_filename)
                        if cv2.imwrite(snapshot_path, frame_data):
                            saved_count += 1
                            snapshot_details.append((snapshot_time, snapshot_filename))
                        else:
                            logger.error(f"Ошибка OpenCV при сохранении кадра: {snapshot_path}")

                    else:
                        logger.error(f"Не удалось прочитать кадр для сцены {i + 1} в позиции {snapshot_time.get_timecode()}.")
                        if snapshot_time.get_frames() > 0:
                            video.seek(target=snapshot_time - 1)
                            frame_data = video.read()
                            if frame_data is not False:
                                snapshot_filename = f"{i + 1}_fallback.jpg"
                                snapshot_path = os.path.join(snapshot_dir, snapshot_filename)
                                if cv2.imwrite(snapshot_path, frame_data):
                                    logger.warning(f"Сохранен предыдущий кадр как {snapshot_filename}")
                                else:
                                    logger.error(f"Ошибка OpenCV при сохранении fallback кадра: {snapshot_path}")

                except Exception as e:
                    logger.error(f"Ошибка при сохранении кадра для сцены {i + 1} ({snapshot_time.get_timecode()}): {e}")

            if saved_count > 0:
                 # Лог теперь использует run_output_dir
                 logger.info(f"Сохранено {saved_count} снапшотов в директорию: {run_output_dir}")
            else:
                 logger.warning(f"Не удалось сохранить ни одного снапшота.")

        # --- Данные для комбинированного отчета --- 
        combined_events = []
        # Добавляем события снимков
        for snap_time, snap_filename in snapshot_details:
            combined_events.append({
                'type': 'snapshot',
                'timestamp': snap_time.get_seconds(),
                'data': snap_filename
            })
        
        segments_list = [] # Инициализируем здесь на случай, если транскрипция не будет выполняться
        audio_segments_available = False  # Флаг для отслеживания, доступны ли аудио сегменты

        logger.info("--- Обработка снапшотов завершена ---")

        # --- Транскрипция (если включена) ---
        if transcribe:
            logger.info("--- Начало транскрипции --- ")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                temp_audio_file = temp_audio.name

            logger.info(f"Временный аудиофайл: {temp_audio_file}")
            if extract_audio(video_path, temp_audio_file):
                try:
                    logger.info(f"Загрузка модели Whisper '{whisper_model_size}'...")
                    model = WhisperModel(whisper_model_size, device="cpu", compute_type="int8")
                    logger.info("Транскрипция аудио... (это может занять время)")
                    
                    segments, info = model.transcribe(
                        temp_audio_file,
                        language="ru",
                        beam_size=5 
                    )

                    logger.info(f"Обнаружен язык: {info.language} с вероятностью {info.language_probability:.2f}")
                    logger.info(f"Длительность аудио: {datetime.timedelta(seconds=info.duration)}")

                    # --- Обработка сегментов с прогресс-баром tqdm ---
                    segments_list = [] 
                    total_duration = info.duration
                    logger.info("Обработка сегментов транскрипции...")
                    with tqdm(total=total_duration, unit='sec', unit_scale=True, desc="Транскрипция") as pbar:
                        last_update_time = 0
                        # Итерируем по генератору segments
                        for segment in segments: 
                            # Обновляем прогресс-бар по времени окончания сегмента
                            current_progress = segment.end
                            pbar.n = round(current_progress, 2)
                            pbar.refresh() # Принудительное обновление
                            last_update_time = current_progress
                            
                            # Сохраняем сегмент и добавляем в события
                            segments_list.append(segment)
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
                                if extract_audio_segments and audio_segments_dir:
                                    segment_id = f"segment_{int(segment.start * 1000)}-{int(segment.end * 1000)}"
                                    audio_file = os.path.join(audio_segments_dir, f"{segment_id}.mp3")
                                    # Относительный путь для HTML
                                    relative_audio_file = os.path.join("audio_segments", f"{segment_id}.mp3")
                                    
                                    if extract_audio_segment(video_path, audio_file, segment.start, segment.end):
                                        segment_event['audio_file'] = relative_audio_file
                                        audio_segments_available = True
                                    else:
                                        logger.warning(f"Не удалось извлечь аудио-сегмент для фрагмента {segment_id}")
                                
                                combined_events.append(segment_event)
                        
                        # Убедимся, что прогресс-бар дошел до конца
                        if total_duration > 0 and pbar.n < total_duration:
                             pbar.n = round(total_duration, 2)
                             pbar.refresh()

                    # Сохраняем SRT транскрипта
                    if segments_list:
                        create_transcript_srt(segments_list, srt_transcript_path)
                    else:
                        logger.warning("Транскрипция не дала результатов.")

                except Exception as e:
                    logger.error(f"Ошибка во время транскрипции: {e}")
            else:
                logger.error("Транскрипция не выполнена из-за ошибки извлечения аудио.")

            logger.info("--- Транскрипция завершена --- ")
        
        # --- Создание комбинированного HTML отчета --- 
        if combined_events: # Создаем отчет, если есть хоть какие-то события
             # Сортируем события по времени
             combined_events.sort(key=lambda item: item['timestamp'])
             # Вызываем функцию генерации HTML с флагом, показывающим, доступны ли аудио-сегменты
             create_combined_html_report(combined_events, html_report_path, base_name, audio_segments_available)
        else:
            logger.warning("Комбинированный HTML отчет не создан, так как нет ни снимков, ни данных транскрипции.")

    except Exception as e:
        logger.error(f"Произошла общая ошибка при обработке видео: {e}")
    finally:
        # Закрываем видеофайл (если он был открыт) - VideoStream делает это сам
        # if video:
        #     pass
        # Удаляем временный аудиофайл, если он был создан
        if temp_audio_file and os.path.exists(temp_audio_file):
            try:
                os.remove(temp_audio_file)
                logger.info(f"Временный аудиофайл удален: {temp_audio_file}")
            except OSError as e:
                logger.error(f"Не удалось удалить временный аудиофайл {temp_audio_file}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Извлечение снапшотов и транскрипция видео.")
    parser.add_argument("video_file", help="Путь к видеофайлу (MP4, MKV и т.д.).")
    parser.add_argument("-o", "--output", default=".", help="Базовая директория для сохранения папок с результатами.") # Обновил help

    # Аргументы для снапшотов
    parser.add_argument("-t", "--threshold", type=float, default=27.0,
                        help="Порог чувствительности ContentDetector для снапшотов (по умолчанию 27.0). Меньше = чувствительнее.")
    parser.add_argument("--stabilization-offset", type=float, default=0.5,
                        help="Смещение в секундах от начала сцены для 'стабилизированного' снимка (по умолчанию 0.5).")

    # Аргументы для транскрипции
    parser.add_argument("--transcribe", action="store_true",
                        help="Включить извлечение аудио и транскрипцию.")
    # Проверяем доступность faster_whisper перед добавлением аргумента
    if FASTER_WHISPER_AVAILABLE:
        parser.add_argument("--whisper-model", default="medium",
                            choices=["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"],
                            help="Размер модели Whisper для транскрипции (по умолчанию 'medium'). 'large-v3' самый точный, 'tiny' самый быстрый.")
    else:
        # Добавляем 'заглушку', если faster-whisper не импортирован
         parser.add_argument('--whisper-model', action='store_const', const='medium', help=argparse.SUPPRESS)

    # Новый аргумент для извлечения аудио-сегментов
    parser.add_argument("--extract-audio", action="store_true",
                        help="Извлекать аудио для каждого сегмента транскрипции и добавлять плееры в отчет.")

    args = parser.parse_args()

    # Вызываем обновленную основную функцию
    extract_snapshots_and_transcript(
        args.video_file,
        args.output,
        args.threshold,
        args.stabilization_offset,
        args.transcribe,
        args.whisper_model,
        args.extract_audio  # Передаем новый параметр
    ) 