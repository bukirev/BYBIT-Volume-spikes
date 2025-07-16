import sys
import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QPushButton, QHBoxLayout, QAbstractItemView, QDialog, QFormLayout, QDialogButtonBox,
    QDoubleSpinBox, QGroupBox, QCheckBox, QLineEdit, QSystemTrayIcon, QMessageBox, QMenu, QAction, QSpinBox
)
from PyQt5.QtCore import QTimer, Qt, QSettings
from PyQt5.QtGui import QColor, QBrush, QFont
from PyQt5.QtMultimedia import QSound
import qasync
import webbrowser

BYBIT_SYMBOLS_URL = "https://api.bybit.com/v5/market/instruments-info?category={category}"
BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline?category={category}&symbol={symbol}&interval=15&from={from_ts}&limit=200"
CATEGORIES = ["spot", "linear"]

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(450)
        self.setStyleSheet(parent.styleSheet())
        layout = QVBoxLayout(self)
        
        # Настройки порогов
        thresholds_group = QGroupBox("Пороги уведомлений")
        thresholds_layout = QFormLayout()
        self.min_ratio_spin = QDoubleSpinBox()
        self.min_ratio_spin.setRange(1.0, 20.0)
        self.min_ratio_spin.setSingleStep(0.5)
        self.min_ratio_spin.setValue(parent.settings["min_ratio"])
        thresholds_layout.addRow("Минимальная кратность:", self.min_ratio_spin)
        
        self.min_volume_spin = QDoubleSpinBox()
        self.min_volume_spin.setRange(0, 10000000)
        self.min_volume_spin.setValue(parent.settings["min_volume"])
        self.min_volume_spin.setSuffix(" USD")
        thresholds_layout.addRow("Минимальный объем:", self.min_volume_spin)
        thresholds_group.setLayout(thresholds_layout)
        layout.addWidget(thresholds_group)
        
        # Настройки обновления
        update_group = QGroupBox("Обновление данных")
        update_layout = QFormLayout()
        self.update_interval_spin = QSpinBox()
        self.update_interval_spin.setRange(30, 600)
        self.update_interval_spin.setValue(parent.settings["update_interval"])
        self.update_interval_spin.setSuffix(" сек")
        update_layout.addRow("Интервал обновления:", self.update_interval_spin)
        
        self.window_size_combo = QComboBox()
        self.window_size_combo.addItems(["Текущий день", "Последние 4 часа", "Последние 24 часа", "Последние 48 часов"])
        self.window_size_combo.setCurrentText(parent.settings["window_size"])
        update_layout.addRow("Период для среднего:", self.window_size_combo)
        update_group.setLayout(update_layout)
        layout.addWidget(update_group)
        
        # Уведомления
        notify_group = QGroupBox("Уведомления")
        notify_layout = QVBoxLayout()
        self.enable_sound_cb = QCheckBox("Звуковые уведомления")
        self.enable_sound_cb.setChecked(parent.settings["enable_sound"])
        notify_layout.addWidget(self.enable_sound_cb)
        
        self.enable_popup_cb = QCheckBox("Всплывающие уведомления")
        self.enable_popup_cb.setChecked(parent.settings["enable_popup"])
        notify_layout.addWidget(self.enable_popup_cb)
        notify_group.setLayout(notify_layout)
        layout.addWidget(notify_group)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        return {
            "min_ratio": self.min_ratio_spin.value(),
            "min_volume": self.min_volume_spin.value(),
            "update_interval": self.update_interval_spin.value(),
            "window_size": self.window_size_combo.currentText(),
            "enable_sound": self.enable_sound_cb.isChecked(),
            "enable_popup": self.enable_popup_cb.isChecked()
        }

class NotificationSystem:
    def __init__(self, parent):
        self.parent = parent
        self.notified_pairs = set()
        
    def check_and_notify(self, ticker_data):
        if not self.parent.isVisible():
            return
            
        for key, data in ticker_data.items():
            if not data or 'datetime' not in data:
                continue
                
            notification_id = f"{key}-{data['datetime']}"
            
            if notification_id in self.notified_pairs:
                continue
                
            if (data['ratio'] >= self.parent.settings["min_ratio"] and 
                data['volume'] >= self.parent.settings["min_volume"]):
                
                self.notified_pairs.add(notification_id)
                self.send_notification(data)
    
    def send_notification(self, data):
        message = (f"{data['symbol']} ({data['category']}) - {data['ratio']:.1f}x\n"
                   f"Объем: {data['volume']:,.0f} USD")
        
        # Всплывающее уведомление
        if self.parent.settings["enable_popup"]:
            try:
                if not QSystemTrayIcon.isSystemTrayAvailable():
                    return
                    
                if not hasattr(self.parent, 'tray_icon'):
                    self.parent.tray_icon = QSystemTrayIcon(self.parent)
                    self.parent.tray_icon.setIcon(self.parent.windowIcon())
                    
                self.parent.tray_icon.showMessage("Объемная вспышка!", message, QSystemTrayIcon.Information, 5000)
            except Exception as e:
                print(f"Ошибка уведомления: {e}")
        
        # Звуковое уведомление
        if self.parent.settings["enable_sound"]:
            try:
                QSound.play("alert.wav")
            except:
                print("Не удалось воспроизвести звук alert.wav")
        
        # Логирование в консоль
        print(f"[ALERT] {datetime.now().strftime('%H:%M:%S')} - {message}")

class BybitVolumeSpikesWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bybit Volume Spikes (15m)")
        self.setMinimumWidth(1200)
        self.setMinimumHeight(750)
        self.setStyleSheet(self.dark_stylesheet())
        self.setWindowIcon(self.style().standardIcon(getattr(self.style(), 'SP_ComputerIcon')))
        layout = QVBoxLayout(self)
        
        # Статусная строка
        self.status_label = QLabel("Загрузка...")
        self.status_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.status_label)
        
        # Панель фильтров
        filter_layout = QHBoxLayout()
        
        # Фильтр по типу
        filter_layout.addWidget(QLabel("Тип:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Все", "spot", "linear"])
        self.type_combo.currentIndexChanged.connect(self.update_table)
        filter_layout.addWidget(self.type_combo)
        
        # Фильтр по имени
        filter_layout.addWidget(QLabel("Фильтр:"))
        self.name_filter_edit = QLineEdit()
        self.name_filter_edit.setPlaceholderText("Фильтр по имени...")
        self.name_filter_edit.textChanged.connect(self.update_table)
        filter_layout.addWidget(self.name_filter_edit)
        
        # Сортировка
        self.volume_sort_cb = QCheckBox("Сортировать по объёму")
        self.volume_sort_cb.stateChanged.connect(self.update_table)
        filter_layout.addWidget(self.volume_sort_cb)
        
        # Кнопки
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.manual_refresh)
        filter_layout.addWidget(self.refresh_btn)
        
        self.settings_btn = QPushButton("Настройки")
        self.settings_btn.clicked.connect(self.open_settings)
        filter_layout.addWidget(self.settings_btn)
        
        filter_layout.addStretch(1)
        layout.addLayout(filter_layout)
        
        # Таблица
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Тикер", "Тип", "Средний объём", "Текущий объём", "Кратн.", "Время"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.doubleClicked.connect(self.on_double_click)
        layout.addWidget(self.table)
        
        # Инициализация данных
        self.ticker_data = {}
        self.tickers = []
        self.ignored_tickers = set()
        self.loop = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: asyncio.create_task(self.update_online()))
        
        # Загрузка настроек
        self.load_settings()
        self.timer.start(self.settings["update_interval"] * 1000)
        
        # Система уведомлений
        self.notifier = NotificationSystem(self)
        
        # Запуск инициализации
        self.init_task = None
        self.load_stats()

    def set_status(self, text):
        self.status_label.setText(text)

    def show_context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid() or idx.column() != 0:
            return
            
        row = idx.row()
        symbol = self.table.item(row, 0).text()
        category = self.table.item(row, 1).text()
        
        menu = QMenu(self)
        
        # Открыть в TradingView
        open_tv = QAction("Открыть в TradingView", self)
        open_tv.triggered.connect(lambda: self.open_tradingview(symbol, category))
        menu.addAction(open_tv)
        
        # Скопировать тикер
        copy_ticker = QAction("Скопировать тикер", self)
        copy_ticker.triggered.connect(lambda: self.copy_to_clipboard(symbol))
        menu.addAction(copy_ticker)
        
        # Игнорировать тикер
        ignore_ticker = QAction("Игнорировать тикер", self)
        ignore_ticker.triggered.connect(lambda: self.ignore_ticker(symbol, category))
        menu.addAction(ignore_ticker)
        
        # Показать все игнорируемые
        show_ignored = QAction("Показать игнорируемые", self)
        show_ignored.triggered.connect(self.show_ignored_tickers)
        menu.addAction(show_ignored)
        
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def ignore_ticker(self, symbol, category):
        self.ignored_tickers.add((symbol, category))
        self.update_table()
        QMessageBox.information(self, "Тикер игнорируется", 
                               f"{symbol} ({category}) добавлен в список игнорируемых")

    def show_ignored_tickers(self):
        if not self.ignored_tickers:
            QMessageBox.information(self, "Игнорируемые тикеры", "Список пуст")
            return
            
        ignored_list = "\n".join([f"{s} ({c})" for s, c in self.ignored_tickers])
        msg = QMessageBox(self)
        msg.setWindowTitle("Игнорируемые тикеры")
        msg.setText(f"Игнорируемые тикеры ({len(self.ignored_tickers)}):")
        msg.setDetailedText(ignored_list)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def copy_to_clipboard(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.status_label.setText(f"Скопировано: {text}")

    def update_table(self):
        type_filter = self.type_combo.currentText()
        name_filter = self.name_filter_edit.text().strip().upper()
        min_ratio = self.settings["min_ratio"]
        min_volume = self.settings["min_volume"]
        
        rows = []
        for key, v in self.ticker_data.items():
            # Пропускаем игнорируемые тикеры
            if key in self.ignored_tickers:
                continue
                
            # Применяем фильтры
            if type_filter != "Все" and v['category'] != type_filter:
                continue
                
            if name_filter and name_filter not in v['symbol'].upper():
                continue
                
            if v['volume'] < min_volume or v['ratio'] < min_ratio:
                continue
                
            rows.append(v)
        
        # Сортировка
        if self.volume_sort_cb.isChecked():
            rows.sort(key=lambda x: x['volume'], reverse=True)
        else:
            rows.sort(key=lambda x: x['ratio'], reverse=True)
            
        # Отображение
        max_ratio = max(r['ratio'] for r in rows) if rows else 0
        self.table.setRowCount(len(rows))
        
        for row_idx, r in enumerate(rows):
            items = [
                QTableWidgetItem(r['symbol']),
                QTableWidgetItem(r['category']),
                QTableWidgetItem(f"{r['mean']:,.0f}"),
                QTableWidgetItem(f"{r['volume']:,.0f}"),
                QTableWidgetItem(f"{r['ratio']:.2f}"),
                QTableWidgetItem(r['datetime']),
            ]
            
            # Цветовая индикация
            if r['ratio'] == max_ratio and max_ratio > 1:
                for item in items:
                    item.setBackground(QBrush(QColor(0, 60, 0)))  # Темно-зеленый
                items[4].setForeground(QBrush(QColor(0, 255, 0)))  # Зеленый текст для кратности
            elif r['ratio'] > 3:
                for item in items:
                    item.setBackground(QBrush(QColor(80, 50, 0)))  # Темно-оранжевый
                items[4].setForeground(QBrush(QColor(255, 165, 0)))  # Оранжевый текст
            elif r['ratio'] > 2:
                for item in items:
                    item.setBackground(QBrush(QColor(60, 60, 0)))  # Темно-желтый
                items[4].setForeground(QBrush(QColor(255, 215, 0)))  # Желтый текст
            
            # Установка элементов в таблицу
            for col_idx, item in enumerate(items):
                self.table.setItem(row_idx, col_idx, item)
        
        # Обновление статуса
        visible_count = len(rows)
        total_count = len(self.ticker_data)
        ignored_count = len(self.ignored_tickers)
        self.status_label.setText(
            f"Показано: {visible_count} | Всего: {total_count} | "
            f"Игнорируется: {ignored_count} | "
            f"Пороги: кратность ≥{min_ratio:.1f}x, объем ≥{min_volume:,.0f}"
        )
        
        self.table.resizeRowsToContents()

    def manual_refresh(self):
        self.set_status("Ручное обновление...")
        asyncio.create_task(self.update_online(async_manual=True))

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            
            # Обновляем интервал таймера при изменении
            if new_settings["update_interval"] != self.settings["update_interval"]:
                self.timer.stop()
                self.timer.start(new_settings["update_interval"] * 1000)
            
            # Пересчитываем средние значения при изменении периода
            if new_settings["window_size"] != self.settings["window_size"]:
                self.set_status("Пересчёт средних значений...")
                asyncio.create_task(self.recalculate_means())
            
            self.settings = new_settings
            self.save_settings()
            self.update_table()

    def dark_stylesheet(self):
        return """
        QWidget {
            background-color: #232629;
            color: #e0e0e0;
            font-family: Arial;
        }
        QHeaderView::section {
            background-color: #2c2f33;
            color: #e0e0e0;
            font-weight: bold;
            font-size: 12px;
            border: 1px solid #444;
            padding: 4px;
        }
        QTableWidget {
            background-color: #232629;
            gridline-color: #444;
            selection-background-color: #44475a;
            selection-color: #f8f8f2;
            font-size: 11px;
        }
        QTableWidget QTableCornerButton::section {
            background-color: #2c2f33;
            border: 1px solid #444;
        }
        QLabel {
            color: #f8f8f2;
            font-size: 11px;
            padding: 4px;
        }
        QComboBox, QPushButton, QLineEdit {
            background-color: #232629;
            color: #e0e0e0;
            border: 1px solid #444;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
            min-height: 24px;
        }
        QComboBox:focus, QPushButton:focus, QLineEdit:focus {
            border: 1.5px solid #8BC34A;
        }
        QPushButton:hover {
            background-color: #2c2f33;
        }
        QGroupBox {
            border: 1px solid #555;
            border-radius: 5px;
            margin-top: 1ex;
            font-size: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
            background-color: #232629;
        }
        QDoubleSpinBox, QSpinBox {
            background-color: #2a2a2a;
            color: #e0e0e0;
            border: 1px solid #444;
            border-radius: 3px;
            padding: 2px;
        }
        QCheckBox {
            font-size: 12px;
            padding: 4px;
        }
        QMenu {
            background-color: #2c2f33;
            color: #e0e0e0;
            border: 1px solid #555;
        }
        QMenu::item:selected {
            background-color: #44475a;
        }
        """

    def open_tradingview(self, symbol, category):
        tv_symbol = f"BYBIT:{symbol}"
        if category == 'linear':
            tv_symbol += '.P'
        url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"
        webbrowser.open(url)

    def on_double_click(self, index):
        if index.row() >= 0 and index.column() >= 0:
            symbol = self.table.item(index.row(), 0).text()
            category = self.table.item(index.row(), 1).text()
            self.open_tradingview(symbol, category)

    def load_settings(self):
        settings = QSettings("VolumeSpikes", "BybitMonitor")
        self.settings = {
            "min_ratio": settings.value("min_ratio", 2.0, float),
            "min_volume": settings.value("min_volume", 10000, float),
            "update_interval": settings.value("update_interval", 90, int),
            "window_size": settings.value("window_size", "Текущий день", str),
            "enable_sound": settings.value("enable_sound", True, bool),
            "enable_popup": settings.value("enable_popup", True, bool)
        }
        # Загрузка игнорируемых тикеров
        ignored = settings.value("ignored_tickers", "")
        if ignored:
            self.ignored_tickers = set(tuple(t.split(':')) for t in ignored.split(';') if t)

    def save_settings(self):
        settings = QSettings("VolumeSpikes", "BybitMonitor")
        for key, value in self.settings.items():
            settings.setValue(key, value)
        # Сохранение игнорируемых тикеров
        ignored_str = ";".join([f"{s}:{c}" for s, c in self.ignored_tickers])
        settings.setValue("ignored_tickers", ignored_str)

    def load_stats(self):
        self.set_status("Загрузка истории и расчёт средних...")
        asyncio.ensure_future(self.async_load_stats())

    async def recalculate_means(self):
        from_ts = self.get_window_timestamp()
        for idx, (symbol, category) in enumerate(self.tickers):
            if (symbol, category) in self.ignored_tickers:
                continue
                
            klines = await self.get_klines(symbol, category, from_ts)
            if not klines or len(klines) < 4:  # Минимум 1 час данных
                continue
                
            volumes = [float(k[5]) for k in klines]
            mean = float(np.mean(volumes))
            
            if (symbol, category) in self.ticker_data:
                self.ticker_data[(symbol, category)]['mean'] = mean
                # Пересчитываем соотношение
                volume = self.ticker_data[(symbol, category)].get('volume', 0)
                self.ticker_data[(symbol, category)]['ratio'] = volume / (mean + 1e-9)
            
            if (idx+1) % 20 == 0:
                self.set_status(f"Пересчёт: {idx+1}/{len(self.tickers)}")
                
        self.update_table()
        self.set_status("Средние значения пересчитаны")

    def get_window_timestamp(self):
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        
        if self.settings["window_size"] == "Текущий день":
            return int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        elif self.settings["window_size"] == "Последние 4 часа":
            return int((now - timedelta(hours=4)).timestamp())
        elif self.settings["window_size"] == "Последние 24 часа":
            return int((now - timedelta(hours=24)).timestamp())
        else:  # Последние 48 часов
            return int((now - timedelta(hours=48)).timestamp())

    async def async_load_stats(self):
        from_ts = self.get_window_timestamp()
        self.tickers = await self.get_all_tickers()
        self.ticker_data = {}
        
        for idx, (symbol, category) in enumerate(self.tickers):
            klines = await self.get_klines(symbol, category, from_ts)
            if not klines or len(klines) < 4:  # Минимум 1 час данных
                continue
                
            volumes = [float(k[5]) for k in klines]
            mean = float(np.mean(volumes))
            
            self.ticker_data[(symbol, category)] = {
                'symbol': symbol,
                'category': category,
                'mean': mean,
                'volume': 0.0,
                'ratio': 0.0,
                'datetime': ''
            }
            self.update_table()
            
            if (idx+1) % 20 == 0:
                self.set_status(f"Загрузка: {idx+1}/{len(self.tickers)}")
                
        self.set_status("Готово. Ожидание онлайн-обновлений...")
        await self.update_online()

    async def get_all_tickers(self):
        tickers = []
        async with aiohttp.ClientSession() as session:
            for category in CATEGORIES:
                try:
                    url = BYBIT_SYMBOLS_URL.format(category=category)
                    async with session.get(url, timeout=10) as resp:
                        data = await resp.json()
                        for x in data['result']['list']:
                            tickers.append((x['symbol'], category))
                except Exception as e:
                    print(f"Ошибка получения тикеров {category}: {e}")
        return tickers

    async def get_klines(self, symbol, category, from_ts):
        try:
            url = BYBIT_KLINE_URL.format(category=category, symbol=symbol, from_ts=from_ts)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    return data.get('result', {}).get('list', [])
        except Exception as e:
            print(f"Ошибка получения данных для {symbol}: {e}")
            return []

    async def update_online(self, async_manual=False):
        if not self.ticker_data:
            return
            
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        from_ts = int((now - timedelta(minutes=30)).timestamp())
        count = 0
        
        for idx, (symbol, category) in enumerate(list(self.ticker_data.keys())):
            # Пропускаем игнорируемые тикеры
            if (symbol, category) in self.ignored_tickers:
                continue
                
            mean = self.ticker_data[(symbol, category)]['mean']
            klines = await self.get_klines(symbol, category, from_ts)
            if not klines:
                continue
                
            last = klines[0]  # Последняя свеча
            vol = float(last[5])
            ts = int(last[0]) // 1000
            dt = datetime.utcfromtimestamp(ts).strftime('%H:%M')
            ratio = vol / (mean + 1e-9)
            
            self.ticker_data[(symbol, category)].update({
                'volume': vol,
                'ratio': ratio,
                'datetime': dt
            })
            
            count += 1
            if async_manual and (idx+1) % 20 == 0:
                self.set_status(f"Обновление: {idx+1}/{len(self.ticker_data)}")
        
        # Проверка уведомлений
        self.notifier.check_and_notify(self.ticker_data)
        
        # Обновление таблицы
        self.update_table()
        self.set_status(f"Обновлено: {count} тикеров, {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    widget = BybitVolumeSpikesWidget()
    widget.show()
    loop.call_soon_threadsafe(widget.load_stats)
    with loop:
        loop.run_forever()