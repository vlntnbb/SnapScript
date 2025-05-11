# SnapScript

Утилита для извлечения снимков из видео в моменты смены сцен с использованием библиотеки PySceneDetect.

## Возможности

- Автоматическое обнаружение смены сцен в видео
- Сохранение снимков с настраиваемым смещением от момента смены сцены
- Создание SRT-файла с таймкодами снимков
- Опциональная транскрипция аудио с помощью Whisper (faster-whisper)
- Генерация HTML-отчета с таймкодами и снимками
- Опциональное извлечение и включение аудио-сегментов в HTML-отчет

## Установка

```bash
# Клонирование репозитория
git clone https://github.com/vlntnbb/SnapScript.git
cd SnapScript

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # В Windows: .venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt
```

## Использование

Базовое использование:

```bash
python snapshot_extractor.py путь/к/видео.mp4
```

С дополнительными опциями:

```bash
python snapshot_extractor.py путь/к/видео.mp4 --threshold 15 --stabilization-offset 0.7
```

Для включения транскрипции:

```bash
python snapshot_extractor.py путь/к/видео.mp4 --transcribe --whisper-model medium
```

С извлечением аудио-сегментов:

```bash
python snapshot_extractor.py путь/к/видео.mp4 --transcribe --extract-audio
```

## Зависимости

- Python 3.6+
- OpenCV
- PySceneDetect
- faster-whisper (опционально для транскрипции)
- ffmpeg (для работы с аудио) 