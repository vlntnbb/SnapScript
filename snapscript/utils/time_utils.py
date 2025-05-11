#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime

def format_srt_time(time_sec: float) -> str:
    """Форматирует время в секундах в формат SRT (ЧЧ:ММ:СС,ммм)."""
    # Используем datetime для корректной обработки
    delta = datetime.timedelta(seconds=time_sec)
    hours, remainder = divmod(delta.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int(delta.microseconds / 1000)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},{milliseconds:03}"

def format_timecode(time_sec: float) -> str:
    """Форматирует время в секундах в читаемый таймкод (ЧЧ:ММ:СС)."""
    hours, remainder = divmod(time_sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

def seconds_to_timedelta(time_sec: float) -> datetime.timedelta:
    """Конвертирует секунды в объект timedelta."""
    return datetime.timedelta(seconds=time_sec) 