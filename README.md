# 📅 SPBSTU A.2.17 Schedule Monitor

Сервис мониторинга изменений в расписании аудитории А.2.17 НИК(Технополис) СПбПУ. Автоматически отслеживает изменения и отправляет уведомления в Telegram.

## 🔧 Как это работает

Сервис запускается как Windows-служба и работает в двух режимах:

**Мгновенные проверки** (каждые 10 минут):
1. Запрашивает актуальное расписание через API СПбПУ
2. Сравнивает с расписанием на начало дня
3. Если есть изменения — сразу отправляет уведомление в Telegram и сохраняет изменения

**Сводные проверки** (в 10:00 и 17:00):
1. Запрашивает актуальное расписание
2. Сравнивает с эталоном предыдущей сводки
3. Отправляет сводку если есть изменения
4. Обновляет эталон и проверяет конфликты в расписании

## 📁 Структура проекта

```
├── main.py                 # Логика проверки расписания
├── scheduler.py            # Планировщик проверок
├── schedule_service.py     # Windows-сервис
├── storage.py              # Работа с файлами и папками
├── formatter.py            # Форматирование сообщений для Telegram
├── conflict_checker.py     # Поиск конфликтов в расписании
├── telegram_notifier.py    # Отправка уведомлений в Telegram
├── constants.py            # Константы
├── tg_credentials.py       # Токен и chat_id (не в репо)
├── data/                   # Расписания и изменения (не в репо)
│   └── 1948/
│       ├── 1948_current_schedule.json
│       └── 2026/03/07_(Сб)/
│           ├── 1948_schedule.json
│           └── changes/
│               └── 1948_10_00_00.json
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
TG_TOKEN = "твой_токен"
TG_CHAT_ID = "твой_chat_id"
```

### 4. Инициализировать расписание
```python
from main import run_check
run_check(is_summary=True)
```

### 5. Установить и запустить сервис
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

## 🔔 Примеры уведомлений в Telegram

**Изменение в расписании:**
```
⚠ Изменения в Room А.2.17(Mobile)

➕ Добавлено
📅 16.03.2026 (Пн)
🕐 14:00 – 15:40
📖 Педагогическая и методическая деятельнос...

➖ Удалено
📅 17.03.2026 (Вт)
🕐 10:00 – 11:40
📖 Высшая математика
```

**Конфликт в расписании:**
```
⚠️ Конфликты в Room A.2.17(Stationary)

📅 19.03.2026 (Чт)
🕐 18:00
```