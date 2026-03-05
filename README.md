# 📅 SPBSTU A.2.17 Schedule Monitor

Сервис мониторинга изменений в расписании аудитории А.2.17 СПбПУ. Автоматически отслеживает изменения и отправляет уведомления в Telegram.

## 🔧 Как это работает

Сервис запускается как Windows-служба и каждые 5 минут:
1. Запрашивает актуальное расписание через API СПбПУ
2. Сравнивает с ранее сохранённым
3. Если есть изменения — отправляет уведомление в Telegram

## 📁 Структура проекта

```
├── main.py                 # Логика проверки расписания
├── schedule_service.py     # Windows-сервис
├── telegram_notifier.py    # Отправка уведомлений в Telegram
├── tg_credentials.py       # Токен и chat_id (не в репо)
└── logs/                   # Логи работы сервиса (не в репо)
```

## ⚙️ Установка

### 1. Клонировать репозиторий
```bash
git clone https://github.com/Kent-PR/SPBSTU-a217-schedule-monitor.git
cd SPBSTU-a217-schedule-monitor
```

### 2. Установить зависимости
```bash
pip install requests pywin32
python Scripts/pywin32_postinstall.py -install
```

### 3. Создать файл с кредами
Создай файл `tg_credentials.py` в корне проекта:
```python
TG_TOKEN = "твой_токен" бота
TG_CHAT_ID = "твой_chat_id" можно узнать через бота
```

### 4. Установить и запустить сервис
```bash
python schedule_service.py install
sc start ScheduleMonitorService
```

## 🛠️ Управление сервисом

```bash
sc start ScheduleMonitorService    # запустить
sc stop ScheduleMonitorService     # остановить
sc query ScheduleMonitorService    # статус
python schedule_service.py remove  # удалить сервис
```

## 📦 Зависимости

- `requests` — HTTP-запросы к API
- `pywin32` — Windows-сервис

## 🔔 Пример уведомления в Telegram

```
⚠ Изменения в Room A.2.17(Stationary)

➕ Добавлено:
  2026-03-10 09:00 Математический анализ

➖ Удалено:
  2026-03-10 10:40 Физика
```
