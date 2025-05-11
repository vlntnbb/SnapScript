#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import shutil
from typing import List, Dict, Any, Optional
from scenedetect.frame_timecode import FrameTimecode
from jinja2 import Environment, FileSystemLoader, select_autoescape

from snapscript.utils.time_utils import format_srt_time, format_timecode
from snapscript.utils.logging_utils import get_logger
from snapscript.utils.fs_utils import ensure_directory_exists

class ReportGenerator:
    """Класс для генерации HTML-отчетов."""
    
    def __init__(self, template_path="templates"):
        """Инициализация генератора отчетов."""
        self.logger = get_logger(__name__)
        self.template_dir = os.path.join(os.path.dirname(__file__), template_path)

        self.use_jinja = False
        try:
            if not os.path.isdir(self.template_dir):
                self.logger.error(f"Директория шаблонов не найдена: {self.template_dir}")
                raise FileNotFoundError(f"Директория шаблонов не найдена: {self.template_dir}")
            
            self.env = Environment(
                loader=FileSystemLoader(self.template_dir),
                autoescape=select_autoescape(['html', 'xml'])
            )
            self.snapshot_template_name = "snapshot_report.html"
            self.combined_template_name = "report_template.html"

            if not os.path.exists(os.path.join(self.template_dir, self.snapshot_template_name)):
                self.logger.error(f"Файл шаблона не найден: {os.path.join(self.template_dir, self.snapshot_template_name)}")
                raise FileNotFoundError(f"Файл шаблона не найден: {os.path.join(self.template_dir, self.snapshot_template_name)}")
            self.env.get_template(self.snapshot_template_name)

            if not os.path.exists(os.path.join(self.template_dir, self.combined_template_name)):
                self.logger.error(f"Файл шаблона не найден: {os.path.join(self.template_dir, self.combined_template_name)}")
                raise FileNotFoundError(f"Файл шаблона не найден: {os.path.join(self.template_dir, self.combined_template_name)}")
            self.env.get_template(self.combined_template_name)
            
            self.use_jinja = True
            self.logger.info("Шаблонизатор Jinja2 успешно инициализирован.")
        except Exception as e:
            self.logger.warning(f"Не удалось инициализировать Jinja2. Будет использован базовый генератор HTML. Ошибка: {e}")
    
    def create_html_report(self, snapshot_details: List[tuple], html_path: str, video_base_name: str) -> bool:
        """Создает простой HTML-отчет со снимками.
        
        Args:
            snapshot_details: Список кортежей (время_снимка, имя_файла)
            html_path: Путь для сохранения HTML файла
            video_base_name: Базовое имя видеофайла
            
        Returns:
            True если отчет создан успешно, иначе False
        """
        self.logger.info(f"Генерация HTML отчета: {html_path}")
        
        title = f"Отчет по снимкам: {video_base_name}"
        
        # Используем шаблонизатор Jinja2, если доступен
        if self.use_jinja and self.env:
            try:
                # Копируем CSS в папку отчета
                css_path = os.path.join(os.path.dirname(html_path), 'styles.css')
                src_css_path = os.path.join(os.path.dirname(__file__), 'templates', 'styles.css')
                shutil.copy2(src_css_path, css_path)
                
                # Подготавливаем данные для шаблона
                rows = []
                for i, (snap_time, snap_filename) in enumerate(snapshot_details):
                    rows.append({
                        'num': i + 1,
                        'time': snap_time.get_timecode(),
                        'filename': snap_filename
                    })
                
                # Получаем шаблон и рендерим его
                template = self.env.get_template(self.snapshot_template_name)
                html_content = template.render(title=title, rows=rows)
                
                # Записываем результат
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                self.logger.info(f"HTML отчет успешно сохранен: {html_path}")
                return True
            except Exception as e:
                self.logger.error(f"Ошибка при создании HTML отчета с помощью Jinja2: {e}")
                # Если ошибка при использовании Jinja2, пробуем запасной вариант
        
        # Запасной вариант - создание HTML без шаблонизатора
        try:
            # Базовый CSS
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
    <title>{title}</title>
    {html_css}
</head>
<body>
    <h1>{title}</h1>
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

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"HTML отчет успешно сохранен: {html_path}")
            return True
        except IOError as e:
            self.logger.error(f"Ошибка записи HTML отчета {html_path}: {e}")
            return False
    
    def create_combined_html_report(self, combined_events: List[Dict], 
                                  html_path: str, 
                                  video_base_name: str,
                                  audio_segments_available: bool = False) -> bool:
        """Создает HTML файл с хронологическим списком снимков и текстом транскрипции.
        
        Args:
            combined_events: Список событий (снимки и транскрипция)
            html_path: Путь для сохранения HTML файла
            video_base_name: Базовое имя видеофайла
            audio_segments_available: Доступны ли аудио-сегменты
            
        Returns:
            True если отчет создан успешно, иначе False
        """
        self.logger.info(f"Генерация комбинированного HTML отчета: {html_path}")
        
        # Определяем директорию отчета и создаем необходимые структуры
        report_dir = os.path.dirname(html_path)
        if not ensure_directory_exists(report_dir):
            return False
        
        # Подготовка ресурсов (CSS и JS)
        css_path = os.path.join(report_dir, 'styles.css')
        src_css_path = os.path.join(os.path.dirname(__file__), 'templates', 'styles.css')
        
        try:
            shutil.copy2(src_css_path, css_path)
            
            # Если доступны аудио-сегменты, копируем JS
            if audio_segments_available:
                js_path = os.path.join(report_dir, 'audio_controls.js')
                src_js_path = os.path.join(os.path.dirname(__file__), 'templates', 'audio_controls.js')
                shutil.copy2(src_js_path, js_path)
        except Exception as e:
            self.logger.error(f"Ошибка при копировании ресурсов: {e}")
        
        # Используем шаблонизатор Jinja2, если доступен
        if self.use_jinja and self.env:
            try:
                # Подготавливаем данные для шаблона
                events = []
                for event in combined_events:
                    event_type = event['type']
                    timestamp = event['timestamp']
                    
                    if event_type == 'snapshot':
                        events.append({
                            'type': 'snapshot',
                            'time_str': format_timecode(timestamp),
                            'data': event['data']
                        })
                    elif event_type == 'transcript':
                        transcript_event = {
                            'type': 'transcript',
                            'id': int(timestamp * 1000),
                            'data': event['data'].replace('\n', ' ')
                        }
                        
                        # Добавляем информацию об аудио-файле, если есть
                        if audio_segments_available and 'audio_file' in event:
                            transcript_event['audio_file'] = event['audio_file']
                        
                        events.append(transcript_event)
                
                # Получаем шаблон и рендерим его
                template = self.env.get_template(self.combined_template_name)
                html_content = template.render(
                    title=f"Комбинированный отчет: {video_base_name}",
                    events=events,
                    audio_available=audio_segments_available
                )
                
                # Записываем результат
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                self.logger.info(f"Комбинированный HTML отчет успешно сохранен: {html_path}")
                return True
            except Exception as e:
                self.logger.error(f"Ошибка при создании комбинированного HTML отчета с помощью Jinja2: {e}")
                # Если ошибка при использовании Jinja2, пробуем запасной вариант
        
        # Запасной вариант - создание HTML без шаблонизатора
        try:
            # Базовый HTML и CSS встроены в функцию
            css = """
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
            </style>
            """
            
            # JavaScript для управления аудио
            audio_control_js = """
            <script>
                // Код для управления аудио-плеерами
                let currentlyPlaying = null;
                let currentButton = null;
                
                function playAudio(audioId, buttonElement) {
                    const audioElement = document.getElementById(audioId);
                    
                    if (currentButton) {
                        currentButton.classList.remove('playing');
                        currentButton.innerHTML = '▶';
                    }
                    
                    if (currentlyPlaying && currentlyPlaying !== audioElement) {
                        currentlyPlaying.pause();
                        currentlyPlaying.currentTime = 0;
                    }
                    
                    if (currentlyPlaying === audioElement && !audioElement.paused) {
                        audioElement.pause();
                        currentlyPlaying = null;
                        currentButton = null;
                        return;
                    }
                    
                    audioElement.play();
                    currentlyPlaying = audioElement;
                    currentButton = buttonElement;
                    currentButton.classList.add('playing');
                    currentButton.innerHTML = '⏸';
                    
                    audioElement.onended = function() {
                        if (currentButton) {
                            currentButton.classList.remove('playing');
                            currentButton.innerHTML = '▶';
                        }
                        currentlyPlaying = null;
                    };
                }
            </script>
            """ if audio_segments_available else ""
            
            # Формируем HTML-документ
            html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Комбинированный отчет: {video_base_name}</title>
    <link rel="stylesheet" href="styles.css">
    {audio_control_js if audio_segments_available else ''}
</head>
<body>
    <h1>Комбинированный отчет: {video_base_name}</h1>
    <div class="timeline">
"""

            # Обрабатываем каждое событие в хронологическом порядке
            for event in combined_events:
                event_type = event['type']
                timestamp = event['timestamp']
                data = event['data']
                
                if event_type == 'snapshot':
                    # Для снимков добавляем таймкод
                    time_str = format_timecode(timestamp)
                    html_content += f'<div class="event snapshot">\n'
                    html_content += f'<div class="event-time">Снимок: {time_str}</div>\n'
                    html_content += f'<div class="snapshot"><img src="{data}" alt="Снимок {time_str}"></div>\n'
                    html_content += '</div>\n'
                elif event_type == 'transcript':
                    # Для транскрипции добавляем текст
                    text_html = data.replace('\n', ' ')
                    
                    html_content += f'<div class="transcript">\n'
                    
                    # Если доступны аудио-сегменты, добавляем аудио-плеер
                    if audio_segments_available and 'audio_file' in event:
                        audio_file = event['audio_file']
                        segment_id = f"audio_{int(timestamp * 1000)}"
                        button_id = f"btn_{segment_id}"
                        html_content += f'''
                        <div class="audio-player">
                            <audio id="{segment_id}" src="{audio_file}"></audio>
                            <button id="{button_id}" class="play-button" onclick="playAudio('{segment_id}', this)">▶</button>
                        </div>
                        '''
                    
                    html_content += f'<p>{text_html}</p>\n'
                    html_content += '</div>\n'
            
            html_content += """    </div>
</body>
</html>"""

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"Комбинированный HTML отчет успешно сохранен: {html_path}")
            return True
        except IOError as e:
            self.logger.error(f"Ошибка записи комбинированного HTML отчета {html_path}: {e}")
            return False 