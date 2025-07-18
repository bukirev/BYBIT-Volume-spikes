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
        self.setStyleSheet(parent.styleSheet() if parent is not None else "")
        layout = QVBoxLayout(self)
        # ... existing code ...
