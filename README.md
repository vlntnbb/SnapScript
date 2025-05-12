# SnapScript

Утилита для извлечения снимков из видео в моменты смены сцен с использованием библиотеки PySceneDetect.

## Возможности

- Автоматическое обнаружение смены сцен в видео
- Сохранение снимков с настраиваемым смещением от момента смены сцены
- Создание SRT-файла с таймкодами снимков
- Опциональная транскрипция аудио с помощью Whisper (faster-whisper)
- Генерация HTML-отчета с таймкодами и снимками
- Опциональное извлечение и включение аудио-сегментов в HTML-отчет
- Пакетная обработка всех видеофайлов в папке

## Установка

```bash
# Клонирование репозитория
git clone https://github.com/vlntnbb/SnapScript.git
cd SnapScript

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # В Windows: .venv\Scripts\activate

# Установка основных зависимостей
pip install -r requirements.txt

# Для работы с транскрипцией нужны дополнительные зависимости
pip install faster-whisper

# Для красивых HTML-отчетов (Jinja2)
pip install jinja2
```

## Использование

По умолчанию, папка с результатами будет создана внутри директории `userdata` (например, `userdata/имя_видео/`).

### Базовое использование:

```bash
python -m snapscript.main путь/к/видео.mp4
```

Указать другую папку для сохранения результатов:

```bash
python -m snapscript.main путь/к/видео.mp4 -o путь/к/другой_папке
```

С дополнительными опциями:

```bash
python -m snapscript.main путь/к/видео.mp4 --threshold 15 --stabilization-offset 0.7
```

Для включения транскрипции:

```bash
python -m snapscript.main путь/к/видео.mp4 --transcribe 
```

Для выбора точности/скорости транскрипции следует указать размер модели Whisper (tiny, base, small, medium, large-v1, large-v2, large-v3). По умолчанию: medium.

```bash
python -m snapscript.main путь/к/видео.mp4 --transcribe --whisper-model large-v1
```

С извлечением аудио-сегментов:

```bash
python -m snapscript.main путь/к/видео.mp4 --transcribe --extract-audio
```

### Пакетная обработка папки

Для обработки всех видеофайлов в папке используйте:

```bash
python -m snapscript.main --batch-folder "путь/к/папке" [опции]
```

Например:
```bash
python -m snapscript.main --batch-folder "userdata/platform anounces" --transcribe --extract-audio --whisper-model large-v2 --threshold 20 --stabilization-offset 0.7 --output userdata --verbose
```

### Примечания по запуску
- Если видите ошибку `ModuleNotFoundError: No module named 'snapscript'`, убедитесь, что запускаете из корня проекта через `python -m snapscript.main ...`.
- Для Windows используйте двойные обратные слэши в путях или обрамляйте путь в кавычки.

## Структура проекта

```
snapscript/
├── main.py                  - Точка входа для CLI (запуск через python -m snapscript.main)
├── core/                    - Основные компоненты
│   ├── video_processor.py   - Обработка видео и обнаружение сцен
│   ├── audio_processor.py   - Обработка аудио и транскрипция
│   └── ffmpeg_wrapper.py    - Обертка для ffmpeg
├── reporting/               - Компоненты отчетов
│   ├── report_generator.py  - Генератор HTML отчетов
│   ├── srt_generator.py     - Генератор SRT файлов
│   └── templates/           - HTML и CSS шаблоны
└── utils/                   - Вспомогательные компоненты
    ├── time_utils.py        - Утилиты для работы с временем
    ├── fs_utils.py          - Утилиты для файловой системы
    └── logging_utils.py     - Настройка логирования
```

## Зависимости

- Python 3.8–3.12 (PySceneDetect не поддерживает 3.13!)
- OpenCV
- PySceneDetect
- faster-whisper (опционально для транскрипции)
- ffmpeg (для работы с аудио)
- Jinja2 (для шаблонизации HTML)

## Лицензия

MIT 
