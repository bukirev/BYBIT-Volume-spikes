import sys
import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QPushButton, QHBoxLayout, QAbstractItemView, QDialog, QFormLayout, QDialogButtonBox,
    QDoubleSpinBox, QGroupBox, QCheckBox, QLineEdit, QSystemTrayIcon, QMessageBox, QMenu, QAction, QSpinBox, QRadioButton, QButtonGroup, QTextEdit
)
from PyQt5.QtCore import QTimer, Qt, QSettings
from PyQt5.QtGui import QColor, QBrush, QFont
from PyQt5.QtMultimedia import QSound
import qasync
import webbrowser
import os
import requests

BYBIT_SYMBOLS_URL = "https://api.bybit.com/v5/market/instruments-info?category={category}"
BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline?category={category}&symbol={symbol}&interval=15&from={from_ts}&limit=200"
CATEGORIES = ["spot", "linear"]

NOTIFICATION_LOG_FILE = "notification_log.txt"

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
        
        # Количество свечей для среднего
        self.candles_spin = QSpinBox()
        self.candles_spin.setRange(4, 999)
        self.candles_spin.setValue(parent.settings.get("mean_candles", 20))
        update_layout.addRow("Кол-во свечей для среднего:", self.candles_spin)
        
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
        
        # Telegram
        telegram_group = QGroupBox("Telegram уведомления")
        telegram_layout = QFormLayout()
        self.telegram_token_edit = QLineEdit()
        self.telegram_token_edit.setText(parent.settings.get("telegram_token", ""))
        telegram_layout.addRow("Токен бота:", self.telegram_token_edit)
        self.telegram_chat_id_edit = QLineEdit()
        self.telegram_chat_id_edit.setText(parent.settings.get("telegram_chat_id", ""))
        telegram_layout.addRow("Chat ID:", self.telegram_chat_id_edit)
        self.telegram_thread_id_edit = QLineEdit()
        self.telegram_thread_id_edit.setText(parent.settings.get("telegram_thread_id", ""))
        telegram_layout.addRow("Message Thread ID (опц.):", self.telegram_thread_id_edit)
        self.enable_telegram_cb = QCheckBox("Отправлять уведомления в Telegram")
        self.enable_telegram_cb.setChecked(parent.settings.get("enable_telegram", False))
        telegram_layout.addRow(self.enable_telegram_cb)
        # Кнопка теста Telegram
        self.test_telegram_btn = QPushButton("Отправить тестовое сообщение")
        self.test_telegram_btn.clicked.connect(self.send_test_telegram)
        telegram_layout.addRow(self.test_telegram_btn)
        # Лимит журнала уведомлений
        self.log_limit_spin = QSpinBox()
        self.log_limit_spin.setRange(10, 500)
        self.log_limit_spin.setValue(parent.settings.get("log_limit", 50))
        telegram_layout.addRow("Лимит журнала:", self.log_limit_spin)
        telegram_group.setLayout(telegram_layout)
        layout.addWidget(telegram_group)
        
        # Размер шрифта интерфейса
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(parent.settings.get("font_size", 12))
        layout.addWidget(QLabel("Размер шрифта интерфейса:"))
        layout.addWidget(self.font_size_spin)
        
        # Размеры шрифта по частям интерфейса
        self.font_size_table_spin = QSpinBox()
        self.font_size_table_spin.setRange(8, 24)
        self.font_size_table_spin.setValue(parent.settings.get("font_size_table", 12))
        layout.addWidget(QLabel("Размер шрифта таблицы:"))
        layout.addWidget(self.font_size_table_spin)
        self.font_size_panel_spin = QSpinBox()
        self.font_size_panel_spin.setRange(8, 24)
        self.font_size_panel_spin.setValue(parent.settings.get("font_size_panel", 12))
        layout.addWidget(QLabel("Размер шрифта панели и кнопок:"))
        layout.addWidget(self.font_size_panel_spin)
        self.font_size_log_spin = QSpinBox()
        self.font_size_log_spin.setRange(8, 24)
        self.font_size_log_spin.setValue(parent.settings.get("font_size_log", 12))
        layout.addWidget(QLabel("Размер шрифта журнала уведомлений:"))
        layout.addWidget(self.font_size_log_spin)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        s = {
            "min_ratio": self.min_ratio_spin.value(),
            "min_volume": self.min_volume_spin.value(),
            "update_interval": self.update_interval_spin.value(),
            "mean_candles": self.candles_spin.value(),
            "enable_sound": self.enable_sound_cb.isChecked(),
            "enable_popup": self.enable_popup_cb.isChecked(),
            "telegram_token": self.telegram_token_edit.text().strip(),
            "telegram_chat_id": self.telegram_chat_id_edit.text().strip(),
            "telegram_thread_id": self.telegram_thread_id_edit.text().strip(),
            "enable_telegram": self.enable_telegram_cb.isChecked(),
            "log_limit": self.log_limit_spin.value(),
            "font_size": self.font_size_spin.value(),
            "font_size_table": self.font_size_table_spin.value(),
            "font_size_panel": self.font_size_panel_spin.value(),
            "font_size_log": self.font_size_log_spin.value(),
        }
        return s

    def send_test_telegram(self):
        token = self.telegram_token_edit.text().strip()
        chat_id = self.telegram_chat_id_edit.text().strip()
        thread_id = self.telegram_thread_id_edit.text().strip()
        if not token or not chat_id:
            QMessageBox.warning(self, "Ошибка", "Укажите токен и chat_id!")
            return
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": "Тестовое сообщение от Bybit Volume Spikes!",
            "parse_mode": "HTML"
        }
        if thread_id:
            if thread_id.isdigit():
                data["message_thread_id"] = int(thread_id)
        try:
            resp = requests.post(url, data=data, timeout=10)
            if resp.ok:
                QMessageBox.information(self, "Успех", "Тестовое сообщение отправлено!")
            else:
                QMessageBox.warning(self, "Ошибка", f"Ошибка Telegram: {resp.status_code} {resp.text}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка Telegram: {e}")

class NotificationLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Журнал уведомлений")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        self.load_log()
        log_font = self.text_edit.font()
        log_font.setPointSize(parent.settings.get("font_size_log", 12))
        self.text_edit.setFont(log_font)
        self.restore_log_window_geometry()
    def load_log(self):
        limit = getattr(self.parent(), 'settings', {}).get('log_limit', 50) if self.parent() else 50
        if os.path.exists(NOTIFICATION_LOG_FILE):
            with open(NOTIFICATION_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                self.text_edit.setPlainText(''.join(lines[:limit]))
        else:
            self.text_edit.setPlainText("Журнал пуст.")

    def restore_log_window_geometry(self):
        settings = QSettings("VolumeSpikes", "BybitMonitor")
        geometry = settings.value("log_window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        pos = settings.value("log_window_pos")
        if pos:
            self.move(pos)

    def closeEvent(self, event):
        settings = QSettings("VolumeSpikes", "BybitMonitor")
        settings.setValue("log_window_geometry", self.saveGeometry())
        settings.setValue("log_window_pos", self.pos())
        super().closeEvent(event)

class NotificationSystem:
    def __init__(self, parent):
        self.parent = parent
        self.notified_pairs = set()
        self.log = []
        self.load_log()
    def load_log(self):
        if os.path.exists(NOTIFICATION_LOG_FILE):
            with open(NOTIFICATION_LOG_FILE, "r", encoding="utf-8") as f:
                self.log = [line.strip() for line in f if line.strip()]
        else:
            self.log = []
    def save_log(self):
        with open(NOTIFICATION_LOG_FILE, "w", encoding="utf-8") as f:
            for entry in self.log:
                f.write(entry + "\n")
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
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tv_symbol = f"BYBIT:{data['symbol']}"
        if data['category'] == 'linear':
            tv_symbol += '.P'
        tv_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"
        hashtag_symbol = f"#{data['symbol']}"
        price = data.get('price', None)
        price_str = f"цена: {price:.3f}" if price is not None else ""
        # Ссылка в формате Markdown
        link_md = f"[ссылка на график]({tv_url})"
        message = (f"{hashtag_symbol} ({data['category']}) - {data['ratio']:.1f}x - {link_md}\n"
                   f"{price_str}\n"
                   f"Объем: {data['volume']:,.0f} USD\nВремя: {now}")
        log_entry = f"[{now}] {data['symbol']} ({data['category']}) - {data['ratio']:.1f}x, {price_str}, Объем: {data['volume']:,.0f} USD"
        self.log.insert(0, log_entry)
        self.log = self.log[:500]  # ограничим журнал 500 последних событий
        self.save_log()
        # Telegram и звук
        s = self.parent.settings
        if s.get("enable_telegram") and s.get("telegram_token") and s.get("telegram_chat_id"):
            self.send_telegram_message(
                s["telegram_token"],
                s["telegram_chat_id"],
                message,
                s.get("telegram_thread_id"),
                parse_mode="Markdown"
            )
        if self.parent.settings["enable_sound"]:
            try:
                QSound.play("alert.wav")
            except:
                print("Не удалось воспроизвести звук alert.wav")
        print(f"[ALERT] {now} - {message}")
        self.parent.show_notification_log(message)

    def send_telegram_message(self, token, chat_id, text, thread_id=None, parse_mode="HTML"):
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        if thread_id:
            if thread_id.isdigit():
                data["message_thread_id"] = int(thread_id)
            else:
                print(f"[Telegram] Некорректный message_thread_id: {thread_id}")
        try:
            resp = requests.post(url, data=data, timeout=10)
            if not resp.ok:
                print(f"[Telegram] Ошибка отправки: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[Telegram] Ошибка отправки: {e}")
    def show_notification_log(self, current_message):
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("Уведомление и журнал")
        dlg.setMinimumWidth(600)
        dlg.setMinimumHeight(400)
        layout = QVBoxLayout(dlg)
        label = QLabel(f"<b>Новое уведомление:</b><br>{current_message.replace(chr(10), '<br>')}")
        layout.addWidget(label)
        text_edit = QTextEdit(dlg)
        text_edit.setReadOnly(True)
        text_edit.setPlainText("\n".join(self.log))
        layout.addWidget(text_edit)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)
        # Авто-закрытие через 5 секунд
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(5000, dlg.accept)
        dlg.show()

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
        self.spot_radio = QRadioButton("spot")
        self.linear_radio = QRadioButton("фьючерсы")
        self.type_group = QButtonGroup(self)
        self.type_group.addButton(self.spot_radio)
        self.type_group.addButton(self.linear_radio)
        filter_layout.addWidget(self.spot_radio)
        filter_layout.addWidget(self.linear_radio)
        self.spot_radio.toggled.connect(self.on_type_changed)
        self.linear_radio.toggled.connect(self.on_type_changed)
        
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
        
        # Показывать все тикеры
        self.show_all_cb = QCheckBox("Показывать все тикеры")
        self.show_all_cb.stateChanged.connect(self.update_table)
        filter_layout.addWidget(self.show_all_cb)
        
        # Кнопки
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.manual_refresh)
        filter_layout.addWidget(self.refresh_btn)
        
        self.settings_btn = QPushButton("Настройки")
        self.settings_btn.clicked.connect(self.open_settings)
        filter_layout.addWidget(self.settings_btn)
        
        self.log_btn = QPushButton("Журнал уведомлений")
        self.log_btn.clicked.connect(self.show_notification_log)
        filter_layout.addWidget(self.log_btn)

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
        self.update_task = None
        self.timer.timeout.connect(lambda: qasync.asyncio.ensure_future(self.safe_update_online()))
        
        # Загрузка настроек
        self.load_settings()
        self.apply_font_size()
        # Восстановить выбор типа
        if self.settings.get("selected_type", "spot") == "spot":
            self.spot_radio.setChecked(True)
        else:
            self.linear_radio.setChecked(True)
        self.timer.start(self.settings["update_interval"] * 1000)
        
        # Система уведомлений
        self.notifier = NotificationSystem(self)
        
        # Запуск инициализации
        self.init_task = None
        self.load_stats()
        self.notification_log_dialog = None
        self.apply_font_sizes()
        self.restore_main_window_geometry()

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
        type_filter = self.settings.get("selected_type", "spot")
        name_filter = self.name_filter_edit.text().strip().upper()
        min_ratio = self.settings["min_ratio"]
        min_volume = self.settings["min_volume"]
        show_all = self.show_all_cb.isChecked()
        table_font = self.table.font()
        table_font.setPointSize(self.settings.get("font_size_table", 12))
        print(f"[DEBUG] update_table: type_filter={type_filter}, show_all={show_all}, min_ratio={min_ratio}, min_volume={min_volume}")
        print(f"[DEBUG] Всего тикеров в ticker_data: {len(self.ticker_data)}")
        for k, v in self.ticker_data.items():
            print(f"[DEBUG] {v['symbol']} category: {v['category']}, volume: {v['volume']}, ratio: {v['ratio']}")
        rows = []
        for key, v in self.ticker_data.items():
            if key in self.ignored_tickers:
                continue
            if v['category'] != type_filter:
                continue
            if name_filter and name_filter not in v['symbol'].upper():
                continue
            if not show_all:
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
            # Применяем шрифт к каждому элементу
            for item in items:
                item.setFont(table_font)
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
        import qasync
        qasync.asyncio.ensure_future(self.safe_update_online(async_manual=True))

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            
            # Обновляем интервал таймера при изменении
            if new_settings["update_interval"] != self.settings["update_interval"]:
                self.timer.stop()
                self.timer.start(new_settings["update_interval"] * 1000)
            
            # Пересчитываем средние значения при изменении периода
            if new_settings["mean_candles"] != self.settings["mean_candles"]:
                self.set_status("Пересчёт средних значений...")
                import qasync
                qasync.asyncio.ensure_future(self.safe_update_online())
            
            self.settings = new_settings
            self.save_settings()
            self.apply_font_size()
            self.apply_font_sizes()
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

    def on_type_changed(self):
        selected = "spot" if self.spot_radio.isChecked() else "linear"
        self.settings["selected_type"] = selected
        self.save_settings()
        self.set_status("Загрузка истории и расчёт средних...")
        import qasync
        qasync.asyncio.ensure_future(self.async_load_stats())

    def load_settings(self):
        settings = QSettings("VolumeSpikes", "BybitMonitor")
        self.settings = {
            "min_ratio": settings.value("min_ratio", 2.0, float),
            "min_volume": settings.value("min_volume", 10000, float),
            "update_interval": settings.value("update_interval", 90, int),
            "mean_candles": settings.value("mean_candles", 20, int),
            "enable_sound": settings.value("enable_sound", True, bool),
            "enable_popup": settings.value("enable_popup", True, bool),
            "selected_type": settings.value("selected_type", "spot", str),
            "telegram_token": settings.value("telegram_token", "", str),
            "telegram_chat_id": settings.value("telegram_chat_id", "", str),
            "telegram_thread_id": settings.value("telegram_thread_id", "", str),
            "enable_telegram": settings.value("enable_telegram", False, bool),
            "log_limit": settings.value("log_limit", 50, int),
            "font_size": settings.value("font_size", 12, int),
            "font_size_table": settings.value("font_size_table", 12, int),
            "font_size_panel": settings.value("font_size_panel", 12, int),
            "font_size_log": settings.value("font_size_log", 12, int),
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
        selected_type = self.settings.get("selected_type", "spot")
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
        now = datetime.now(timezone.utc)
        n_candles = self.settings.get("mean_candles", 20)
        return int((now - timedelta(minutes=15 * n_candles)).timestamp())

    async def async_load_stats(self):
        from_ts = self.get_window_timestamp()
        selected_type = self.settings.get("selected_type", "spot")
        self.tickers = await self.get_all_tickers(selected_type)
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

    async def safe_update_online(self, async_manual=False):
        import logging
        if self.update_task and not self.update_task.done():
            print("[DEBUG] Обновление уже выполняется, новый запуск отменён.")
            return  # Уже идёт обновление
        print(f"[DEBUG] Старт обновления (async_manual={async_manual})")
        import qasync
        self.update_task = qasync.asyncio.ensure_future(self.update_online(async_manual))
        def on_done(fut):
            print(f"[DEBUG] Обновление завершено (async_manual={async_manual})")
        self.update_task.add_done_callback(on_done)

    async def get_all_tickers(self, selected_type):
        tickers = []
        async with aiohttp.ClientSession() as session:
            try:
                url = BYBIT_SYMBOLS_URL.format(category=selected_type)
                async with session.get(url, timeout=10) as resp:
                    data = await resp.json()
                    for x in data['result']['list']:
                        tickers.append((x['symbol'], selected_type))
            except Exception as e:
                print(f"Ошибка получения тикеров {selected_type}: {e}")
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
        import asyncio
        try:
            if not self.ticker_data:
                return
            now = datetime.now(timezone.utc)
            from_ts = int((now - timedelta(minutes=30)).timestamp())
            count = 0
            selected_type = self.settings.get("selected_type", "spot")
            for idx, (symbol, category) in enumerate(list(self.ticker_data.keys())):
                if (symbol, category) in self.ignored_tickers:
                    continue
                if category != selected_type:
                    continue
                mean = self.ticker_data[(symbol, category)]['mean']
                klines = await self.get_klines(symbol, category, from_ts)
                if not klines:
                    continue
                last = klines[0]
                vol = float(last[5])
                ts = int(last[0]) // 1000
                dt = datetime.fromtimestamp(ts, timezone.utc).strftime('%H:%M')
                ratio = vol / (mean + 1e-9)
                price = float(last[4])
                self.ticker_data[(symbol, category)].update({
                    'volume': vol,
                    'ratio': ratio,
                    'datetime': dt,
                    'price': price
                })
                count += 1
                if async_manual and (idx+1) % 20 == 0:
                    self.set_status(f"Обновление: {idx+1}/{len(self.ticker_data)}")
            self.notifier.check_and_notify(self.ticker_data)
            self.update_table()
            self.set_status(f"Обновлено: {count} тикеров, {datetime.now().strftime('%H:%M:%S')}")
        except asyncio.CancelledError:
            return

    def show_notification_log(self, current_message=None):
        if self.notification_log_dialog is None or not self.notification_log_dialog.isVisible():
            self.notification_log_dialog = NotificationLogDialog(self)
            self.notification_log_dialog.show()
        if current_message is not None:
            # Обновить содержимое
            self.notification_log_dialog.load_log()
            self.notification_log_dialog.raise_()
            self.notification_log_dialog.activateWindow()

    def apply_font_size(self):
        font_size = self.settings.get("font_size", 12)
        font = self.font()
        font.setPointSize(font_size)
        self.setFont(font)
        # Применить к дочерним виджетам
        for child in self.findChildren(QWidget):
            child.setFont(font)

    def apply_font_sizes(self):
        # Таблица
        table_font = self.table.font()
        table_font.setPointSize(self.settings.get("font_size_table", 12))
        self.table.setFont(table_font)
        self.table.horizontalHeader().setFont(table_font)
        self.table.verticalHeader().setFont(table_font)
        # Панель и кнопки
        panel_font = self.font()
        panel_font.setPointSize(self.settings.get("font_size_panel", 12))
        for widget in [self.status_label, self.spot_radio, self.linear_radio, self.name_filter_edit, self.volume_sort_cb, self.refresh_btn, self.settings_btn, self.log_btn, self.show_all_cb]:
            if widget:
                widget.setFont(panel_font)
        # Журнал уведомлений (если открыт)
        if self.notification_log_dialog is not None:
            log_font = self.notification_log_dialog.text_edit.font()
            log_font.setPointSize(self.settings.get("font_size_log", 12))
            self.notification_log_dialog.text_edit.setFont(log_font)

    def restore_main_window_geometry(self):
        settings = QSettings("VolumeSpikes", "BybitMonitor")
        geometry = settings.value("main_window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        pos = settings.value("main_window_pos")
        if pos:
            self.move(pos)

    def closeEvent(self, event):
        settings = QSettings("VolumeSpikes", "BybitMonitor")
        settings.setValue("main_window_geometry", self.saveGeometry())
        settings.setValue("main_window_pos", self.pos())
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    widget = BybitVolumeSpikesWidget()
    widget.show()
    loop.call_soon_threadsafe(widget.load_stats)
    with loop:
        loop.run_forever()