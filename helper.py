import sys
import os
import sqlite3
import random
import time
import threading
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QDialog,
    QCompleter,
    QStackedWidget,  # <-- Ajouté pour la gestion des pages
    QFormLayout,  # <-- Ajouté pour le formulaire des paramètres
    QComboBox,  # <-- Ajouté pour les menus déroulants
    QSpinBox,  # <-- Ajouté pour le sélecteur de nombre de rolls
)
from PySide6.QtCore import (
    Qt,
    QTimer,
    QUrl,
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    QObject,
    Signal,
)
from PySide6.QtGui import (
    QFont,
    QShortcut,
    QKeySequence,
    QColor,
    QPixmap,
    QImage,
)
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkRequest,
    QNetworkReply,
)

from pynput import keyboard, mouse

DB_FILENAME = "mudae_characters.db"

THEMES = {
    "dark": {
        "bg_main": "#1e1a24",
        "bg_container": "#25202c",
        "fg_text": "#fbc5d8",
        "fg_title": "#ff79c6",
        "color_primary": "#ff79c6",
        "color_hover": "#ff92df",
        "color_header": "#2d2635",
        "select_bg": "#3d3248",
        "select_fg": "#ffffff",
    }
}


class MacroSignaler(QObject):
    trigger = Signal()


class GlobalHotkeyThread(threading.Thread):
    """Thread d'écoute global multiplateforme pour intercepter la touche '<'."""

    def __init__(self, trigger_signal):
        super().__init__(daemon=True)
        self.trigger_signal = trigger_signal
        self.listener = None

    def on_press(self, key):
        try:
            # Détection du caractère '<' peu importe la disposition (AZERTY, QWERTY...)
            if hasattr(key, "char") and key.char == "<":
                self.trigger_signal.emit()
        except Exception:
            pass

    def run(self):
        # Initialise l'écouteur global du clavier de pynput
        self.listener = keyboard.Listener(on_press=self.on_press)
        with self.listener:
            self.listener.join()


class GachaRollDialog(QDialog):
    """Pop-up animée simulant un roll de gacha premium, sans aucun son."""

    def __init__(self, parent, character, network_manager):
        super().__init__(parent)
        self.character = character
        self.network_manager = network_manager
        self.image_pixmap = None
        self.parent_app = parent

        # Fenêtre sans bordures avec fond transparent
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(380, 540)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)

        self.container = QWidget()
        self.container.setObjectName("container")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignCenter)
        self.container_layout.setSpacing(15)
        self.container_layout.setContentsMargins(20, 20, 20, 20)
        self.layout.addWidget(self.container)

        # Éléments du portail d'invocation (Le rideau fermé)
        self.status_label = QLabel("✨ CONVOCATION DES ESPRITS... ✨")
        self.status_label.setFont(QFont("Malgun Gothic", 14, QFont.Weight.Bold))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #ff79c6;")

        self.portal_symbol = QLabel("🌀")
        self.portal_symbol.setFont(QFont("Segoe UI", 64))
        self.portal_symbol.setAlignment(Qt.AlignCenter)

        # Éléments du personnage (cachés au départ)
        self.img_label = QLabel()
        self.img_label.setFixedSize(220, 260)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet(
            "background-color: rgba(0,0,0,0.3); border-radius: 16px;"
        )
        self.img_label.hide()

        # Panel de lisibilité assombri pour les informations
        self.info_panel = QWidget()
        self.info_panel.setObjectName("info_panel")
        self.info_panel.setStyleSheet(
            "background-color: rgba(30, 26, 36, 0.85); border-radius: 16px;"
        )
        self.info_panel_layout = QVBoxLayout(self.info_panel)
        self.info_panel_layout.setSpacing(6)
        self.info_panel_layout.setContentsMargins(15, 12, 15, 12)
        self.info_panel.hide()

        self.name_label = QLabel()
        self.name_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("color: white;")
        self.name_label.setWordWrap(True)

        self.series_label = QLabel()
        font_series = QFont("Segoe UI", 9)
        font_series.setItalic(True)
        self.series_label.setFont(font_series)
        self.series_label.setAlignment(Qt.AlignCenter)
        self.series_label.setStyleSheet("color: #b0b0b0;")
        self.series_label.setWordWrap(True)

        self.stats_label = QLabel()
        self.stats_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.stats_label.setAlignment(Qt.AlignCenter)
        self.stats_label.setStyleSheet("color: #ff79c6;")

        self.info_panel_layout.addWidget(self.name_label)
        self.info_panel_layout.addWidget(self.series_label)
        self.info_panel_layout.addWidget(self.stats_label)

        self.close_btn = QPushButton("RETOUR")
        self.close_btn.setFixedHeight(40)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.hide()

        self.container_layout.addWidget(self.status_label)
        self.container_layout.addWidget(self.portal_symbol)
        self.container_layout.addWidget(self.img_label)
        self.container_layout.addWidget(self.info_panel)
        self.container_layout.addWidget(self.close_btn)

        # Coins très arrondis (20px) sur le container
        self.container.setStyleSheet("""
            QWidget#container {
                background-color: #1e1a24;
                border: 3px solid #ff79c6;
                border-radius: 20px;
            }
            QPushButton {
                background-color: #ff79c6;
                color: #1e1a24;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff92df;
            }
        """)

        # Halo lumineux de base
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setOffset(0, 0)
        self.shadow.setColor(QColor(255, 121, 198))
        self.container.setGraphicsEffect(self.shadow)

        # Overlay Blanc pour l'effet de Flash
        self.flash_overlay = QWidget(self.container)
        self.flash_overlay.setStyleSheet(
            "background-color: white; border-radius: 20px;"
        )
        self.flash_overlay.hide()

        # Timer de la cinématique d'invocation
        self.portal_timer = QTimer(self)
        self.portal_timer.timeout.connect(self.animate_portal)
        self.portal_ticks = 0
        self.portal_timer.start(50)

        # Raccourci local pour enchaîner les rolls directement (Ctrl+Shift+R)
        self.shortcut_reroll = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
        self.shortcut_reroll.activated.connect(self.trigger_reroll)

        self.pre_download_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.flash_overlay.setGeometry(self.container.rect())

    def pre_download_image(self):
        url = self.character.get("image_url")
        if url:
            req = QNetworkRequest(QUrl(url))
            self.reply = self.network_manager.get(req)
            self.reply.finished.connect(self.on_image_loaded)

    def on_image_loaded(self):
        if self.reply.error() == QNetworkReply.NoError:
            data = self.reply.readAll()
            img = QImage()
            if img.loadFromData(data):
                self.image_pixmap = QPixmap.fromImage(img)
        self.reply.deleteLater()

    def animate_portal(self):
        self.portal_ticks += 1
        symbols = ["🌀", "🌌", "🔮", "⚡", "🌟"]
        self.portal_symbol.setText(symbols[self.portal_ticks % len(symbols)])

        scale = 1.0 + 0.15 * (self.portal_ticks % 10 - 5) / 5.0
        font_size = int(64 * scale)
        self.portal_symbol.setFont(QFont("Segoe UI", font_size))

        colors = ["#ff79c6", "#8a2be2", "#00bfff", "#ffd700", "#ff4500"]
        selected_color = QColor(colors[self.portal_ticks % len(colors)])
        self.shadow.setColor(selected_color)

        if self.portal_ticks >= 25:
            self.portal_timer.stop()
            self.trigger_flash_and_reveal()

    def trigger_flash_and_reveal(self):
        self.flash_overlay.setGeometry(self.container.rect())
        self.flash_overlay.show()

        self.flash_opacity = QGraphicsOpacityEffect(self.flash_overlay)
        self.flash_overlay.setGraphicsEffect(self.flash_opacity)

        self.flash_anim = QPropertyAnimation(self.flash_opacity, b"opacity")
        self.flash_anim.setDuration(400)
        self.flash_anim.setStartValue(1.0)
        self.flash_anim.setEndValue(0.0)
        self.flash_anim.setEasingCurve(QEasingCurve.OutQuad)
        self.flash_anim.finished.connect(self.flash_overlay.hide)
        self.flash_anim.start()

        self.portal_symbol.hide()
        self.status_label.setText("🎉 INVOCATION RÉUSSIE ! 🎉")
        self.status_label.setStyleSheet("color: #ffd700; font-weight: bold;")

        self.parent_app.appliquer_glow_engine(
            self.container, self.shadow, self.character["rank"]
        )

        self.name_label.setText(self.character["original_name"])
        self.series_label.setText(self.character.get("series_name", "Série Inconnue"))

        self.target_kakera = int(self.character.get("kakera", 0))
        self.current_kakera = 0
        self.stats_label.setText(f"⭐ {self.character['rank']}  |  🌸 0")

        self.kakera_timer = QTimer(self)
        self.kakera_timer.timeout.connect(self.increment_kakera_counter)
        self.kakera_timer.start(25)

        self.info_panel.show()
        self.close_btn.show()

        self.img_label.show()
        if self.image_pixmap:
            self.parent_app.afficher_image_avec_bounce(
                self.img_label, self.image_pixmap, 220, 260
            )
        else:
            self.img_label.setText("🌸 Pas d'image 🌸")
            self.parent_app.afficher_image_avec_bounce(
                self.img_label, QPixmap(), 220, 260
            )

    def increment_kakera_counter(self):
        if self.current_kakera < self.target_kakera:
            diff = self.target_kakera - self.current_kakera
            step = max(1, diff // 8)
            self.current_kakera += step
            self.stats_label.setText(
                f"⭐ {self.character['rank']}  |  🌸 {self.current_kakera}"
            )
        else:
            self.current_kakera = self.target_kakera
            self.stats_label.setText(
                f"⭐ {self.character['rank']}  |  🌸 {self.current_kakera}"
            )
            self.kakera_timer.stop()

    def trigger_reroll(self):
        """Ferme la fenêtre courante et lance un nouveau roll après un infime délai."""
        self.accept()
        QTimer.singleShot(50, self.parent_app.trigger_fake_roll)


class MudaeHelperApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.dernier_contenu = ""
        self.personnages_affiches = set()
        self.loaded_characters = {}
        self.image_cache = {}
        self.current_displayed_url = ""

        self.network_manager = QNetworkAccessManager(self)

        self.init_ui()

        # Timer du presse-papiers (300 ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.verifier_presse_papiers)
        self.timer.start(300)

        # Raccourci Gacha Simulator (Ctrl+Shift+R)
        self.shortcut_roll = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
        self.shortcut_roll.activated.connect(self.trigger_fake_roll)

        # Macro globale "<"
        self.macro_signaler = MacroSignaler()
        self.macro_signaler.trigger.connect(self.run_macro)
        self.hotkey_thread = GlobalHotkeyThread(self.macro_signaler.trigger)
        self.hotkey_thread.start()

    def init_ui(self):
        self.setWindowTitle("🌸 Mudae Rolls Helper 🌸")
        self.resize(880, 560)
        self.setMinimumSize(820, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.central_widget = QWidget()
        self.central_widget.setObjectName("main_container")
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(15)

        # ---- Top Frame Layout ----
        top_layout = QHBoxLayout()

        self.title_label = QLabel("✨ quoicoubibou des montagnes ✨")
        self.title_label.setObjectName("title_label")
        self.title_label.setFont(QFont("Malgun Gothic", 14, QFont.Weight.Bold))

        # Remplacement du bouton thème par le bouton Paramètres / Menu
        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setFixedSize(40, 32)
        self.btn_settings.clicked.connect(self.toggle_settings_view)

        top_layout.addWidget(self.title_label)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_settings)
        main_layout.addLayout(top_layout)

        # ---- Stacked Widget pour basculer de l'App aux Paramètres ----
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # ================= PAGE 0 : ÉCRAN PRINCIPAL =================
        self.main_page = QWidget()
        content_layout = QHBoxLayout(self.main_page)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        # Tableau (4 colonnes)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["♡", "Waifu / Husband  🎀", "Rang  ⭐", "Kakera  🌸"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setFont(QFont("Segoe UI", 10))
        self.table.horizontalHeader().setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 240)
        self.table.setColumnWidth(2, 110)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        # Clic sur le tableau redirige vers la mise à jour de la carte + COPIE DIRECTE
        self.table.itemClicked.connect(self.on_table_item_clicked)
        left_layout.addWidget(self.table)

        # Bouton Vider la liste
        btn_clear_layout = QHBoxLayout()
        self.btn_clear = QPushButton("💖  Vider la liste  💖")
        self.btn_clear.setObjectName("btn_clear")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setFixedHeight(45)
        self.btn_clear.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_clear.clicked.connect(self.vider_tableau)

        btn_clear_layout.addStretch()
        btn_clear_layout.addWidget(self.btn_clear, stretch=2)
        btn_clear_layout.addStretch()
        left_layout.addLayout(btn_clear_layout)

        content_layout.addLayout(left_layout, stretch=3)

        # Fiche Waifu Interactive
        self.card_widget = QWidget()
        self.card_widget.setObjectName("gacha_card")
        self.card_widget.setFixedWidth(270)

        card_inner_layout = QVBoxLayout(self.card_widget)
        card_inner_layout.setContentsMargins(15, 15, 15, 15)
        card_inner_layout.setSpacing(10)
        card_inner_layout.setAlignment(Qt.AlignTop)

        self.card_title = QLabel("FICHE PERSONNAGE")
        self.card_title.setObjectName("gacha_card_title")
        self.card_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.card_title.setAlignment(Qt.AlignCenter)

        self.card_img = QLabel()
        self.card_img.setFixedSize(240, 240)
        self.card_img.setAlignment(Qt.AlignCenter)
        self.card_img.setStyleSheet(
            "background-color: rgba(0,0,0,0.15); border-radius: 12px; color: grey;"
        )
        self.card_img.setText("Aucune sélection")

        self.card_name = QLabel("Copie un nom !")
        self.card_name.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.card_name.setWordWrap(True)
        self.card_name.setAlignment(Qt.AlignCenter)

        self.card_series = QLabel("Série / Origine")
        font_series = QFont("Segoe UI", 8)
        font_series.setItalic(True)
        self.card_series.setFont(font_series)
        self.card_series.setWordWrap(True)
        self.card_series.setAlignment(Qt.AlignCenter)
        self.card_series.setStyleSheet("color: gray;")

        stats_layout = QHBoxLayout()
        self.badge_rank = QLabel("⭐ N/A")
        self.badge_rank.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.badge_rank.setAlignment(Qt.AlignCenter)

        self.badge_kakera = QLabel("🌸 0")
        self.badge_kakera.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.badge_kakera.setAlignment(Qt.AlignCenter)

        stats_layout.addWidget(self.badge_rank)
        stats_layout.addWidget(self.badge_kakera)

        card_inner_layout.addWidget(self.card_title)
        card_inner_layout.addWidget(self.card_img)
        card_inner_layout.addWidget(self.card_name)
        card_inner_layout.addWidget(self.card_series)
        card_inner_layout.addLayout(stats_layout)

        self.card_shadow = QGraphicsDropShadowEffect(self)
        self.card_shadow.setBlurRadius(15)
        self.card_shadow.setOffset(0, 0)
        self.card_shadow.setColor(QColor(0, 0, 0, 100))
        self.card_widget.setGraphicsEffect(self.card_shadow)

        self.shadow_anim = QPropertyAnimation(self.card_shadow, b"blurRadius")
        self.shadow_anim.setDuration(1500)
        self.shadow_anim.setStartValue(10)
        self.shadow_anim.setEndValue(25)
        self.shadow_anim.setEasingCurve(QEasingCurve.InOutSine)
        self.shadow_anim.setLoopCount(-1)
        self.shadow_anim.start()

        content_layout.addWidget(self.card_widget, stretch=1)
        self.stacked_widget.addWidget(self.main_page)

        # ================= PAGE 1 : PARAMÈTRES & BATCH ROLLS =================
        self.settings_page = QWidget()
        self.settings_page.setObjectName("settings_page")

        settings_layout = QVBoxLayout(self.settings_page)
        settings_layout.setContentsMargins(40, 20, 40, 20)
        settings_layout.setSpacing(15)
        settings_layout.setAlignment(Qt.AlignTop)

        settings_title = QLabel("⚙️ PARAMÈTRES DU BATCH ROLL")
        settings_title.setFont(QFont("Malgun Gothic", 14, QFont.Weight.Bold))
        settings_title.setAlignment(Qt.AlignCenter)
        settings_title.setStyleSheet("color: #ff79c6; margin-bottom: 20px;")
        settings_layout.addWidget(settings_title)

        # Lecture de la structure DB pour peupler les formulaires
        self.load_filter_options()

        form_widget = QWidget()
        form_widget.setStyleSheet("""
            QWidget { 
                background-color: #25202c; 
                border-radius: 16px; 
                border: 2px solid #ff79c6; 
            } 
            QLabel { 
                color: #fbc5d8; 
                font-weight: bold; 
                border: none; 
            }
        """)
        form_layout = QFormLayout(form_widget)
        form_layout.setContentsMargins(25, 25, 25, 25)
        form_layout.setSpacing(15)

        self.combo_gender = QComboBox()
        self.combo_gender.addItems(self.genders)
        self.combo_gender.setStyleSheet(
            "background-color: #1e1a24; color: #ffffff; padding: 6px; border-radius: 8px;"
        )
        form_layout.addRow("Genre (Gender) :", self.combo_gender)

        self.combo_series = QComboBox()
        self.combo_series.addItems(self.series_list)
        self.combo_series.setEditable(True)
        self.combo_series.setInsertPolicy(QComboBox.NoInsert)
        self.combo_series.completer().setFilterMode(Qt.MatchContains)
        self.combo_series.setStyleSheet(
            "background-color: #1e1a24; color: #ffffff; padding: 6px; border-radius: 8px;"
        )
        form_layout.addRow("Série (Series) :", self.combo_series)

        self.combo_adult = QComboBox()
        self.combo_adult.addItems(
            ["Tous", "Adulte uniquement", "Non-adulte uniquement"]
        )
        self.combo_adult.setStyleSheet(
            "background-color: #1e1a24; color: #ffffff; padding: 6px; border-radius: 8px;"
        )
        form_layout.addRow("Filtre Adulte :", self.combo_adult)

        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 100)
        self.spin_count.setValue(10)
        self.spin_count.setStyleSheet(
            "background-color: #1e1a24; color: #ffffff; padding: 6px; border-radius: 8px;"
        )
        form_layout.addRow("Nombre de rolls (Max 100) :", self.spin_count)

        settings_layout.addWidget(form_widget)

        self.btn_run_batch = QPushButton("🎲   LANCER LE BATCH ROLL   🎲")
        self.btn_run_batch.setCursor(Qt.PointingHandCursor)
        self.btn_run_batch.setFixedHeight(50)
        self.btn_run_batch.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_run_batch.setStyleSheet("""
            QPushButton {
                background-color: #ff79c6;
                color: #1e1a24;
                border-radius: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff92df;
                color: #ffffff;
            }
        """)
        self.btn_run_batch.clicked.connect(self.executer_batch_rolls)
        settings_layout.addWidget(self.btn_run_batch)

        self.stacked_widget.addWidget(self.settings_page)

        # Application du thème sombre unique
        self.appliquer_theme()

    def get_db_schema(self):
        """Lit la structure de la table characters."""
        conn = sqlite3.connect(DB_FILENAME)
        cursor = conn.cursor()
        columns = []
        try:
            cursor.execute("PRAGMA table_info(characters)")
            columns = [row[1] for row in cursor.fetchall()]
        except Exception:
            pass
        finally:
            conn.close()
        return columns

    def load_filter_options(self):
        """Recherche dynamiquement les filtres valides présents dans la DB SQLite locale."""
        columns = self.get_db_schema()
        self.db_features = {
            "gender_col": (
                "gender"
                if "gender" in columns
                else ("sex" if "sex" in columns else None)
            ),
            "adult_col": (
                "is_adult"
                if "is_adult" in columns
                else (
                    "adult"
                    if "adult" in columns
                    else ("nsfw" if "nsfw" in columns else None)
                )
            ),
            "series_col": "id_series" if "id_series" in columns else None,
        }

        conn = sqlite3.connect(DB_FILENAME)
        cursor = conn.cursor()

        self.genders = ["Tous"]
        if self.db_features["gender_col"]:
            try:
                cursor.execute(
                    f"SELECT DISTINCT {self.db_features['gender_col']} FROM characters WHERE {self.db_features['gender_col']} IS NOT NULL"
                )
                self.genders.extend(
                    [str(r[0]).capitalize() for r in cursor.fetchall() if r[0]]
                )
            except Exception:
                pass

        self.series_list = ["Toutes"]
        try:
            cursor.execute("SELECT name FROM series ORDER BY name")
            self.series_list.extend([str(r[0]) for r in cursor.fetchall() if r[0]])
        except Exception:
            pass

        conn.close()

    def toggle_settings_view(self):
        """Bascule entre le menu d'accueil et le menu paramètres."""
        if self.stacked_widget.currentIndex() == 0:
            self.stacked_widget.setCurrentIndex(1)
            self.btn_settings.setText("🏠")
        else:
            self.stacked_widget.setCurrentIndex(0)
            self.btn_settings.setText("⚙️")

    def executer_batch_rolls(self):
        """Exécute un ensemble de tirages filtrés d'un seul coup."""
        gender_val = self.combo_gender.currentText()
        series_val = self.combo_series.currentText()
        adult_val = self.combo_adult.currentText()
        count_val = self.spin_count.value()

        query = """
            SELECT c.name, c.rank, c.kakera_value, c.image_url, s.name 
            FROM characters c 
            LEFT JOIN series s ON c.id_series = s.id_series
        """
        conditions = []
        params = []

        if gender_val != "Tous" and self.db_features["gender_col"]:
            conditions.append(f"LOWER(c.{self.db_features['gender_col']}) = LOWER(?)")
            params.append(gender_val)

        if series_val != "Toutes":
            conditions.append("LOWER(s.name) = LOWER(?)")
            params.append(series_val)

        if adult_val != "Tous" and self.db_features["adult_col"]:
            col = self.db_features["adult_col"]
            if adult_val == "Adulte uniquement":
                conditions.append(
                    f"(c.{col} = 1 OR c.{col} = '1' OR LOWER(c.{col}) = 'true' OR LOWER(c.{col}) = 'adult')"
                )
            else:
                conditions.append(
                    f"(c.{col} = 0 OR c.{col} = '0' OR LOWER(c.{col}) = 'false' OR c.{col} IS NULL)"
                )

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY RANDOM() LIMIT ?"
        params.append(count_val)

        conn = sqlite3.connect(DB_FILENAME)
        cursor = conn.cursor()
        rolled_characters = []
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            for r in rows:
                rolled_characters.append(
                    {
                        "original_name": r[0],
                        "rank": str(r[1]) if r[1] is not None else "N/A",
                        "kakera": r[2] if r[2] is not None else 0,
                        "image_url": r[3] if r[3] is not None else "",
                        "series_name": r[4] if r[4] is not None else "Série Inconnue",
                    }
                )
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du batch roll: {e}")
            return
        finally:
            conn.close()

        if not rolled_characters:
            QMessageBox.warning(
                self,
                "Aucun résultat",
                "Aucun personnage ne correspond à vos critères de recherche.",
            )
            return

        for p in rolled_characters:
            self.personnages_affiches.add(p["original_name"])
            self.loaded_characters[p["original_name"]] = p

        tous_les_persos = list(self.loaded_characters.values())
        tous_les_persos.sort(key=lambda x: x["kakera"], reverse=True)

        self.table.setRowCount(0)
        for i, p in enumerate(tous_les_persos, start=1):
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            item_idx = QTableWidgetItem(str(i))
            item_idx.setTextAlignment(Qt.AlignCenter)
            item_name = QTableWidgetItem(p["original_name"])
            item_rank = QTableWidgetItem(p["rank"])
            item_rank.setTextAlignment(Qt.AlignCenter)
            item_kakera = QTableWidgetItem(f"{p['kakera']} 🌸")
            item_kakera.setTextAlignment(Qt.AlignCenter)

            self.table.setItem(row_idx, 0, item_idx)
            self.table.setItem(row_idx, 1, item_name)
            self.table.setItem(row_idx, 2, item_rank)
            self.table.setItem(row_idx, 3, item_kakera)

        if rolled_characters:
            self.mettre_a_jour_carte(rolled_characters[0])

        self.stacked_widget.setCurrentIndex(0)
        self.btn_settings.setText("⚙️")

    def appliquer_theme(self):
        self.current_theme = "dark"
        t = THEMES["dark"]

        qss = f"""
        QWidget#main_container {{
            background-color: {t['bg_main']};
        }}
        QLabel#title_label {{
            color: {t['fg_title']};
        }}
        QPushButton#btn_settings {{
            background-color: {t['bg_container']};
            color: {t['fg_text']};
            border: none;
            border-radius: 10px;
            font-size: 14px;
        }}
        QPushButton#btn_settings:hover {{
            background-color: {t['color_header']};
        }}
        QTableWidget {{
            background-color: {t['bg_container']};
            color: {t['fg_text']};
            gridline-color: transparent;
            border: none;
            border-radius: 16px;
            selection-background-color: {t['select_bg']};
            selection-color: {t['select_fg']};
        }}
        QHeaderView::section {{
            background-color: {t['color_header']};
            color: {t['fg_text']};
            padding: 8px;
            border: none;
            font-weight: bold;
        }}
        QPushButton#btn_clear {{
            background-color: {t['color_primary']};
            color: "#1e1a24";
            border: none;
            border-radius: 16px;
        }}
        QPushButton#btn_clear:hover {{
            background-color: {t['color_hover']};
            color: "#ffffff";
        }}
        QWidget#gacha_card {{
            background-color: {t['bg_container']};
            border: 2px solid {t['color_primary']};
            border-radius: 20px;
        }}
        QLabel#gacha_card_title {{
            color: {t['fg_title']};
        }}
        """
        self.setStyleSheet(qss)
        self.appliquer_glow_engine(self.card_widget, self.card_shadow, "N/A")

    def appliquer_glow_engine(self, widget, shadow_effect, rank_str):
        rank_val = None
        try:
            rank_val = int(rank_str)
        except ValueError:
            pass

        if rank_val is not None:
            if rank_val <= 100:
                bg_style = "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFE000, stop:1 #799F0C);"
                border_color = "#FFD700"
                shadow_color = QColor("#FFD700")
                blur = 25
            elif rank_val <= 500:
                bg_style = "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8a2be2, stop:1 #ff007f);"
                border_color = "#ff007f"
                shadow_color = QColor("#ff007f")
                blur = 20
            elif rank_val <= 2000:
                bg_style = "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00c6ff, stop:1 #0072ff);"
                border_color = "#00c6ff"
                shadow_color = QColor("#00c6ff")
                blur = 15
            else:
                bg_color = THEMES["dark"]["bg_container"]
                bg_style = f"background-color: {bg_color};"
                border_color = THEMES["dark"]["color_primary"]
                shadow_color = QColor(border_color)
                blur = 8
        else:
            bg_color = THEMES["dark"]["bg_container"]
            bg_style = f"background-color: {bg_color};"
            border_color = THEMES["dark"]["color_primary"]
            shadow_color = QColor(border_color)
            blur = 8

        widget.setStyleSheet(f"""
            QWidget#{widget.objectName()} {{
                {bg_style}
                border: 2px solid {border_color};
                border-radius: 20px;
            }}
        """)
        shadow_effect.setColor(shadow_color)
        shadow_effect.setBlurRadius(blur)

    def rechercher_personnage(self, texte):
        texte_clean = texte.strip(" \t\n\r⚡✨⭐💎🔹🔸▶️👥💌💍❤️")
        if not texte_clean:
            return None

        conn = sqlite3.connect(DB_FILENAME)
        cursor = conn.cursor()
        result = None

        try:
            cursor.execute(
                """
                SELECT c.name, c.rank, c.kakera_value, c.image_url, s.name 
                FROM characters c 
                LEFT JOIN series s ON c.id_series = s.id_series
                WHERE LOWER(c.name) = LOWER(?)
                """,
                (texte_clean,),
            )
            result = cursor.fetchone()
        except sqlite3.OperationalError:
            try:
                cursor.execute(
                    """
                    SELECT c.name, c.rank, c.kakera_value 
                    FROM characters c 
                    WHERE LOWER(c.name) = LOWER(?)
                    """,
                    (texte_clean,),
                )
                res = cursor.fetchone()
                if res:
                    result = (res[0], res[1], res[2], "", "Série Inconnue")
            except Exception:
                result = None

        if not result:
            try:
                cursor.execute(
                    """
                    SELECT c.name, c.rank, c.kakera_value, c.image_url, s.name 
                    FROM aliases a
                    JOIN characters c ON a.id_character = c.id_character
                    LEFT JOIN series s ON c.id_series = s.id_series
                    WHERE LOWER(a.alias) = LOWER(?)
                    LIMIT 1
                    """,
                    (texte_clean,),
                )
                result = cursor.fetchone()
            except sqlite3.OperationalError:
                try:
                    cursor.execute(
                        """
                        SELECT c.name, c.rank, c.kakera_value 
                        FROM aliases a
                        JOIN characters c ON a.id_character = c.id_character
                        WHERE LOWER(a.alias) = LOWER(?)
                        LIMIT 1
                        """,
                        (texte_clean,),
                    )
                    res = cursor.fetchone()
                    if res:
                        result = (res[0], res[1], res[2], "", "Série Inconnue")
                except Exception:
                    result = None

        conn.close()

        if result:
            return {
                "original_name": result[0],
                "rank": str(result[1]) if result[1] is not None else "N/A",
                "kakera": result[2] if result[2] is not None else 0,
                "image_url": (
                    result[3] if len(result) > 3 and result[3] is not None else ""
                ),
                "series_name": (
                    result[4]
                    if len(result) > 4 and result[4] is not None
                    else "Série Inconnue"
                ),
            }
        return None

    def vider_tableau(self):
        self.personnages_affiches.clear()
        self.loaded_characters.clear()
        self.table.setRowCount(0)
        self.card_name.setText("Choisissez une waifu")
        self.card_series.setText("Série / Origine")
        self.badge_rank.setText("⭐ N/A")
        self.badge_kakera.setText("🌸 0")
        self.card_img.clear()
        self.card_img.setText("Aucune sélection")
        self.appliquer_glow_engine(self.card_widget, self.card_shadow, "N/A")

    def analyser_et_ajouter(self, texte):
        character = self.rechercher_personnage(texte)
        if not character:
            return

        if character["original_name"] in self.personnages_affiches:
            self.mettre_a_jour_carte(character)
            return

        self.personnages_affiches.add(character["original_name"])
        self.loaded_characters[character["original_name"]] = character

        tous_les_persos = list(self.loaded_characters.values())
        tous_les_persos.sort(key=lambda x: x["kakera"], reverse=True)

        self.table.setRowCount(0)
        for i, p in enumerate(tous_les_persos, start=1):
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            item_idx = QTableWidgetItem(str(i))
            item_idx.setTextAlignment(Qt.AlignCenter)
            item_name = QTableWidgetItem(p["original_name"])
            item_rank = QTableWidgetItem(p["rank"])
            item_rank.setTextAlignment(Qt.AlignCenter)
            item_kakera = QTableWidgetItem(f"{p['kakera']} 🌸")
            item_kakera.setTextAlignment(Qt.AlignCenter)

            self.table.setItem(row_idx, 0, item_idx)
            self.table.setItem(row_idx, 1, item_name)
            self.table.setItem(row_idx, 2, item_rank)
            self.table.setItem(row_idx, 3, item_kakera)

        self.mettre_a_jour_carte(character)

    def verifier_presse_papiers(self):
        try:
            clipboard = QApplication.clipboard()
            contenu_actuel = clipboard.text()
            if contenu_actuel != self.dernier_contenu and contenu_actuel.strip():
                self.dernier_contenu = contenu_actuel
                self.analyser_et_ajouter(contenu_actuel)
        except Exception:
            pass

    def afficher_carte_depuis_selection(self, item):
        row = item.row()
        name_item = self.table.item(row, 1)
        if name_item:
            name = name_item.text()
            if name in self.loaded_characters:
                self.mettre_a_jour_carte(self.loaded_characters[name])

    def on_table_item_clicked(self, item):
        """Met à jour l'affichage de la fiche ET copie la donnée correspondante."""
        self.afficher_carte_depuis_selection(item)

        col = item.column()
        raw_text = item.text()
        text_to_copy = ""

        if col == 1:  # Waifu Name
            text_to_copy = raw_text.strip()
        elif col == 2:  # Rank
            text_to_copy = raw_text.strip()
        elif col == 3:  # Kakera (enlever le 🌸 pour copier le chiffre brut)
            text_to_copy = raw_text.replace(" 🌸", "").strip()
        else:
            text_to_copy = raw_text.strip()

        if text_to_copy:
            QApplication.clipboard().setText(text_to_copy)

    def mettre_a_jour_carte(self, p):
        self.card_name.setText(p["original_name"])
        self.card_series.setText(p["series_name"])
        self.badge_rank.setText(f"⭐ {p['rank']}")
        self.badge_kakera.setText(f"🌸 {p['kakera']}")

        self.appliquer_glow_engine(self.card_widget, self.card_shadow, p["rank"])
        self.charger_image_async(p.get("image_url"))

    def charger_image_async(self, url):
        self.card_img.clear()
        if not url:
            self.card_img.setText("🌸 Pas d'image 🌸")
            return

        if url in self.image_cache:
            pix = self.image_cache[url]
            self.afficher_image_avec_bounce(self.card_img, pix, 240, 240)
            return

        self.current_displayed_url = url
        self.demarrer_shimmer(self.card_img)

        req = QNetworkRequest(QUrl(url))
        reply = self.network_manager.get(req)
        reply.setProperty("url", url)
        reply.finished.connect(self.on_image_downloaded)

    def on_image_downloaded(self):
        reply = self.sender()
        if not reply:
            return
        url = reply.property("url")
        self.arreter_shimmer(self.card_img)

        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            img = QImage()
            if img.loadFromData(data):
                pix = QPixmap.fromImage(img)
                self.image_cache[url] = pix
                if (
                    hasattr(self, "current_displayed_url")
                    and self.current_displayed_url == url
                ):
                    self.afficher_image_avec_bounce(self.card_img, pix, 240, 240)
            else:
                self.card_img.setText("🌸 Pas d'image 🌸")
        else:
            self.card_img.setText("🌸 Pas d'image 🌸")
        reply.deleteLater()

    def demarrer_shimmer(self, label):
        shimmer_effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(shimmer_effect)

        self.shimmer_anim = QPropertyAnimation(shimmer_effect, b"opacity", label)
        self.shimmer_anim.setDuration(1000)
        self.shimmer_anim.setStartValue(0.3)
        self.shimmer_anim.setEndValue(1.0)
        self.shimmer_anim.setLoopCount(-1)
        self.shimmer_anim.start()

    def arreter_shimmer(self, label):
        if hasattr(self, "shimmer_anim"):
            self.shimmer_anim.stop()
        label.setGraphicsEffect(None)

    def afficher_image_avec_bounce(self, label, pix, w, h):
        """Spring Animation sans fuite mémoire ni plantage de thread C++."""
        if not pix.isNull():
            label.setPixmap(
                pix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        label.setMinimumSize(0, 0)
        label.setMaximumSize(16777215, 16777215)

        anim_min = QPropertyAnimation(label, b"minimumSize", label)
        anim_min.setDuration(600)
        anim_min.setStartValue(QSize(0, 0))
        anim_min.setEndValue(QSize(w, h))
        anim_min.setEasingCurve(QEasingCurve.OutBack)

        anim_max = QPropertyAnimation(label, b"maximumSize", label)
        anim_max.setDuration(600)
        anim_max.setStartValue(QSize(0, 0))
        anim_max.setEndValue(QSize(w, h))
        anim_max.setEasingCurve(QEasingCurve.OutBack)

        from PySide6.QtCore import QParallelAnimationGroup

        anim_group = QParallelAnimationGroup(label)
        anim_group.addAnimation(anim_min)
        anim_group.addAnimation(anim_max)

        def set_final_size():
            try:
                label.setFixedSize(w, h)
            except RuntimeError:
                pass

        anim_group.finished.connect(set_final_size)
        anim_group.start()

    def trigger_fake_roll(self):
        """Sélectionne aléatoirement un personnage et l'invoque."""
        conn = sqlite3.connect(DB_FILENAME)
        cursor = conn.cursor()
        char_data = None

        try:
            cursor.execute("""
                SELECT c.name, c.rank, c.kakera_value, c.image_url, s.name 
                FROM characters c 
                LEFT JOIN series s ON c.id_series = s.id_series
                ORDER BY RANDOM() LIMIT 1
            """)
            res = cursor.fetchone()
            if res:
                char_data = {
                    "original_name": res[0],
                    "rank": str(res[1]) if res[1] is not None else "N/A",
                    "kakera": res[2] if res[2] is not None else 0,
                    "image_url": res[3] if res[3] is not None else "",
                    "series_name": res[4] if res[4] is not None else "Série Inconnue",
                }
        except sqlite3.OperationalError:
            try:
                cursor.execute(
                    "SELECT name, rank, kakera_value FROM characters ORDER BY RANDOM() LIMIT 1"
                )
                res = cursor.fetchone()
                if res:
                    char_data = {
                        "original_name": res[0],
                        "rank": str(res[1]) if res[1] is not None else "N/A",
                        "kakera": res[2] if res[2] is not None else 0,
                        "image_url": "",
                        "series_name": "Série Inconnue",
                    }
            except Exception:
                pass
        finally:
            conn.close()

        if char_data:
            dialog = GachaRollDialog(self, char_data, self.network_manager)
            dialog.exec()

    def run_macro(self):
        """Macro déclenchée par la touche '<' : Triple-clic + Copie (Multiplateforme)."""
        m_controller = mouse.Controller()
        k_controller = keyboard.Controller()

        # 1. Simulation du Triple Clic Gauche
        m_controller.click(mouse.Button.left, 3)
        time.sleep(
            0.15
        )  # Pause pour laisser le système appliquer la sélection de texte

        # 2. Simulation de la copie automatique selon l'OS (Cmd+C sur Mac, Ctrl+C ailleurs)
        modifier = keyboard.Key.cmd if sys.platform == "darwin" else keyboard.Key.ctrl

        with k_controller.pressed(modifier):
            k_controller.press("c")
            k_controller.release("c")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    if not os.path.exists(DB_FILENAME):
        QMessageBox.critical(
            None, "Erreur", f"Base de données '{DB_FILENAME}' introuvable."
        )
        sys.exit(1)
    else:
        window = MudaeHelperApp()
        window.show()
        sys.exit(app.exec())
