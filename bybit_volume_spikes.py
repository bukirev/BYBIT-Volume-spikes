import sys
import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QPushButton, QHBoxLayout, QAbstractItemView
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor, QBrush, QFont
import qasync

BYBIT_SYMBOLS_URL = "https://api.bybit.com/v5/market/instruments-info?category={category}"
BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline?category={category}&symbol={symbol}&interval=15&from={from_ts}&limit=1000"
CATEGORIES = ["spot", "linear"]

class BybitVolumeSpikesWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bybit Volume Spikes (15m)")
        self.setMinimumWidth(1200)
        self.setMinimumHeight(700)
        self.setStyleSheet(self.dark_stylesheet())
        layout = QVBoxLayout(self)
        self.status_label = QLabel("Загрузка...")
        self.status_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.status_label)
        # --- Фильтр по типу ---
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Тип:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Все", "spot", "linear"])
        self.type_combo.currentIndexChanged.connect(self.update_table)
        filter_layout.addWidget(self.type_combo)
        self.refresh_btn = QPushButton("Обновить вручную")
        self.refresh_btn.clicked.connect(self.manual_refresh)
        filter_layout.addWidget(self.refresh_btn)
        filter_layout.addStretch(1)
        layout.addLayout(filter_layout)
        # --- Таблица ---
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Тикер", "Тип", "Средний объём", "Текущий объём", "Кратн.", "Время"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)
        self.ticker_data = {}  # (symbol, category) -> dict с средним объёмом, текущим объёмом, временем, кратностью
        self.tickers = []
        self.loop = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: asyncio.create_task(self.update_online()))
        self.timer.start(90 * 1000)  # 1.5 минуты
        self.init_task = None

    def set_status(self, text):
        self.status_label.setText(text)

    def show_context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid() or idx.column() != 0:
            return
        row = idx.row()
        symbol = self.table.item(row, 0).text()
        category = self.table.item(row, 1).text()
        from PyQt5.QtWidgets import QMenu, QAction, QApplication
        menu = QMenu(self)
        open_tv = QAction("Открыть график в TradingView", self)
        copy_ticker = QAction("Скопировать тикер", self)
        menu.addAction(open_tv)
        menu.addAction(copy_ticker)
        def open_tv_func():
            self.open_tradingview(symbol, category)
        def copy_ticker_func():
            clipboard = QApplication.clipboard()
            clipboard.setText(symbol)
        open_tv.triggered.connect(open_tv_func)
        copy_ticker.triggered.connect(copy_ticker_func)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def update_table(self):
        type_filter = self.type_combo.currentText()
        rows = [v for v in self.ticker_data.values() if type_filter == "Все" or v['category'] == type_filter]
        if not rows:
            self.table.setRowCount(0)
            return
        rows.sort(key=lambda x: x['ratio'], reverse=True)
        max_ratio = rows[0]['ratio'] if rows else 0
        self.table.setRowCount(len(rows))
        for row, r in enumerate(rows):
            items = [
                QTableWidgetItem(r['symbol']),
                QTableWidgetItem(r['category']),
                QTableWidgetItem(f"{r['mean']:.2f}"),
                QTableWidgetItem(f"{r['volume']:.2f}"),
                QTableWidgetItem(f"{r['ratio']:.2f}"),
                QTableWidgetItem(r['datetime']),
            ]
            # Цветовая индикация строки
            if r['ratio'] == max_ratio and max_ratio > 1:
                for item in items:
                    item.setBackground(QBrush(QColor(0, 60, 0)))
                items[3].setForeground(QBrush(QColor(0, 255, 0)))
            elif r['ratio'] > 2:
                for item in items:
                    item.setBackground(QBrush(QColor(60, 60, 0)))
                items[3].setForeground(QBrush(QColor(255, 215, 0)))
            for col, item in enumerate(items):
                self.table.setItem(row, col, item)
        self.table.resizeRowsToContents()

    def manual_refresh(self):
        self.set_status("Ручное обновление...")
        asyncio.create_task(self.update_online(async_manual=True))

    def dark_stylesheet(self):
        return """
        QWidget {
            background-color: #232629;
            color: #e0e0e0;
        }
        QHeaderView::section {
            background-color: #2c2f33;
            color: #e0e0e0;
            font-weight: bold;
            border: 1px solid #444;
        }
        QTableWidget {
            background-color: #232629;
            gridline-color: #444;
            selection-background-color: #44475a;
            selection-color: #f8f8f2;
        }
        QTableWidget QTableCornerButton::section {
            background-color: #2c2f33;
            border: 1px solid #444;
        }
        QLabel {
            color: #f8f8f2;
        }
        QComboBox, QPushButton {
            background-color: #232629;
            color: #e0e0e0;
            border: 1px solid #444;
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 15px;
        }
        QComboBox:focus, QPushButton:focus {
            border: 1.5px solid #8BC34A;
        }
        """

    def open_tradingview(self, symbol, category):
        import webbrowser
        tv_symbol = f"BYBIT:{symbol}"
        if category == 'linear':
            tv_symbol += '.P'
        url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"
        webbrowser.open(url)

    def mouseDoubleClickEvent(self, event):
        idx = self.table.currentRow()
        if idx >= 0 and idx < self.table.rowCount():
            symbol = self.table.item(idx, 0).text()
            category = self.table.item(idx, 1).text()
            self.open_tradingview(symbol, category)
        super().mouseDoubleClickEvent(event)

    def load_stats(self):
        self.set_status("Загрузка истории и расчёт медианы/стд...")
        asyncio.create_task(self.async_load_stats())

    async def async_load_stats(self):
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        start_utc = now.replace(hour=0, minute=0, second=0, microsecond=0)
        from_ts = int(start_utc.timestamp())
        self.tickers = await self.get_all_tickers()
        self.ticker_data = {}
        for idx, (symbol, category) in enumerate(self.tickers):
            klines = await self.get_klines(symbol, category, from_ts)
            if not klines or len(klines) < 8:
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
            if (idx+1) % 20 == 0:
                self.set_status(f"Расчёт: {idx+1}/{len(self.tickers)}")
        self.set_status("Готово. Ожидание онлайн-обновлений...")
        asyncio.create_task(self.update_online())

    async def get_all_tickers(self):
        tickers = []
        async with aiohttp.ClientSession() as session:
            for category in CATEGORIES:
                url = BYBIT_SYMBOLS_URL.format(category=category)
                async with session.get(url) as resp:
                    data = await resp.json()
                    for x in data['result']['list']:
                        tickers.append((x['symbol'], category))
        return tickers

    async def get_klines(self, symbol, category, from_ts):
        url = BYBIT_KLINE_URL.format(category=category, symbol=symbol, from_ts=from_ts)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get('result', {}).get('list', [])

    async def update_online(self, async_manual=False):
        if not self.ticker_data:
            return
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        from_ts = int((now - timedelta(minutes=30)).timestamp())
        for idx, (symbol, category) in enumerate(list(self.ticker_data.keys())):
            mean = self.ticker_data[(symbol, category)]['mean']
            klines = await self.get_klines(symbol, category, from_ts)
            if not klines:
                continue
            last = klines[0]  # Последняя (самая свежая) свеча
            vol = float(last[5])
            ts = int(last[0]) // 1000
            dt = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            ratio = vol / (mean + 1e-9)
            self.ticker_data[(symbol, category)].update({
                'volume': vol,
                'ratio': ratio,
                'datetime': dt
            })
            if (idx+1) % 20 == 0 and async_manual:
                self.set_status(f"Онлайн-проверка: {idx+1}/{len(self.ticker_data)}")
        self.update_table()
        self.set_status("Таблица обновлена.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    widget = BybitVolumeSpikesWidget()
    widget.show()
    loop.call_soon_threadsafe(widget.load_stats)
    with loop:
        loop.run_forever() 