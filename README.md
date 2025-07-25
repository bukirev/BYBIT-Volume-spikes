# Bybit Volume Spikes Monitor (v2)

Мониторинг аномальных всплесков объема на бирже Bybit с расширенными возможностями


## 🚀 Основные возможности

- **Анализ объемов в реальном времени**  
  Отслеживание 15-минутных свечей на спотовом и фьючерсном рынках Bybit
- **Умные уведомления**
  - Звуковые оповещения
  - Всплывающие уведомления
  - Фильтрация ложных срабатываний
- **Расширенные настройки**
  - Регулировка порогов срабатывания
  - Настройка периода для средних значений
  - Управление интервалом обновления
- **Контекстные действия**
  - Быстрый переход к графику TradingView
  - Игнорирование тикеров
  - Копирование символов

## 🛠 Установка

1. Установите зависимости:
```bash
pip install pyqt5 aiohttp numpy qasync
```

2. Склонируйте репозиторий:
```bash

git clone https://github.com/bukirev/BYBIT-Volume-spikes.git
cd bybit-volume-spikes
```

3. Запустите приложение:
```bash
python bybit_volume_spikes-v2.py
```

## ⚙ Настройки

Доступны через меню "Настройки":
- **Пороги уведомлений**
  - Минимальная кратность (отношение объема к среднему)
  - Минимальный объем (в USD)
  
- **Обновление данных**
  - Интервал обновления (30-600 секунд)
  - Период для расчета среднего:
    - Текущий день
    - Последние 4 часа
    - Последние 24 часа
    - Последние 48 часов

- **Уведомления**
  - Звуковые оповещения
  - Всплывающие окна

## 🖥 Использование интерфейса

- **Фильтрация данных**
  - Выбор типа рынка (спот, фьючерсы, все)
  - Фильтр по имени символа
  - Сортировка по объему или кратности

- **Цветовая индикация**
  - Зеленый: максимальная кратность в списке
  - Оранжевый: кратность > 3
  - Желтый: кратность > 2

- **Контекстное меню** (правый клик по символу)
  - Открыть в TradingView
  - Скопировать тикер
  - Игнорировать тикер
  - Просмотр игнорируемых тикеров

- **Двойной клик** по строке открывает график в TradingView

## 🔔 Система уведомлений

Приложение предупредит вас когда:
- Объем торгов превысит установленный порог
- Соотношение объема к среднему превысит заданное значение
- Уведомления срабатывают только 1 раз для каждой свечи

## 📊 Как это работает

1. **Инициализация данных**
   - Загрузка всех доступных пар с Bybit
   - Расчет средних объемов за выбранный период

2. **Онлайн-обновление**
   - Каждые N секунд проверяются последние свечи
   - Рассчитывается соотношение текущего объема к среднему
   - Обновляется таблица данных

3. **Фильтрация и сортировка**
   - Автоматическая фильтрация по порогам
   - Сортировка по значимости всплесков
   - Визуальное выделение аномалий

## 🤝 Поддержка и обратная связь

Сообщения об ошибках и запросы функций:  


---

**Важно:** Для работы приложения требуется стабильное интернет-соединение и доступ к API Bybit.


