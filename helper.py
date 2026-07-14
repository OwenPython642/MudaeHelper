import sys
import os
import sqlite3
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
    QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

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
    },
    "light": {
        "bg_main": "#FFF0F5",
        "bg_container": "#FFFFFF",
        "fg_text": "#5C4044",
        "fg_title": "#D2143A",
        "color_primary": "#FFB6C1",
        "color_hover": "#FF69B4",
        "color_header": "#FFE4E1",
        "select_bg": "#FFE4E1",
        "select_fg": "#D2143A",
    },
}


class MudaeHelperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.current_theme = "dark"
        self.dernier_contenu = ""
        self.personnages_affiches = set()

        self.init_ui()
        
        # Timer pour surveiller le presse-papiers toutes les 300 ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.verifier_presse_papiers)
        self.timer.start(300)

    def init_ui(self):
        self.setWindowTitle("🌸 Mudae Rolls Helper 🌸")
        self.resize(620, 540)
        self.setMinimumSize(580, 450)
        
        # Rendre la fenêtre toujours au-dessus
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        # Widget central et Layout Principal
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
        self.title_label.setFont(QFont("Malgun Gothic", 14, QFont.Bold))
        
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setFixedSize(40, 32)
        self.btn_theme.clicked.connect(self.toggle_theme)

        top_layout.addWidget(self.title_label)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_theme)
        main_layout.addLayout(top_layout)

        # ---- TableWidget (Equivalent Treeview) ----
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "♡", 
            "Waifu / Husband  🎀", 
            "Rang  ⭐", 
            "Kakera  🌸"
        ])
        
        # Configuration des colonnes
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setFont(QFont("Segoe UI", 10))
        self.table.horizontalHeader().setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        # Comportement des colonnes et tailles
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 240)
        self.table.setColumnWidth(2, 110)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        
        main_layout.addWidget(self.table)

        # ---- Bouton Vider la liste ----
        btn_clear_layout = QHBoxLayout()
        self.btn_clear = QPushButton("💖  Vider la liste  💖")
        self.btn_clear.setObjectName("btn_clear")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setFixedHeight(45)
        self.btn_clear.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_clear.clicked.connect(self.vider_tableau)
        
        btn_clear_layout.addStretch()
        btn_clear_layout.addWidget(self.btn_clear, stretch=2)
        btn_clear_layout.addStretch()
        
        main_layout.addLayout(btn_clear_layout)

        # Application du thème par défaut
        self.appliquer_theme(self.current_theme)

    def appliquer_theme(self, theme_name):
        self.current_theme = theme_name
        t = THEMES[theme_name]

        self.btn_theme.setText("☀️" if theme_name == "dark" else "🌙")

        # Application du style global via QSS (Qt Style Sheets)
        qss = f"""
        QWidget#main_container {{
            background-color: {t['bg_main']};
        }}
        QLabel#title_label {{
            color: {t['fg_title']};
        }}
        QPushButton#btn_theme {{
            background-color: {t['bg_container']};
            color: {t['fg_text']};
            border: none;
            border-radius: 6px;
        }}
        QPushButton#btn_theme:hover {{
            background-color: {t['color_header']};
        }}
        QTableWidget {{
            background-color: {t['bg_container']};
            color: {t['fg_text']};
            gridline-color: transparent;
            border: none;
            selection-background-color: {t['select_bg']};
            selection-color: {t['select_fg']};
        }}
        QHeaderView::section {{
            background-color: {t['color_header']};
            color: {t['fg_text']};
            padding: 5px;
            border: none;
            font-weight: bold;
        }}
        QPushButton#btn_clear {{
            background-color: {t['color_primary']};
            color: {"#1e1a24" if theme_name == "dark" else t['fg_text']};
            border: none;
            border-radius: 8px;
        }}
        QPushButton#btn_clear:hover {{
            background-color: {t['color_hover']};
            color: {"#ffffff" if theme_name == "dark" else t['fg_text']};
        }}
        """
        self.setStyleSheet(qss)

    def toggle_theme(self):
        if self.current_theme == "dark":
            self.appliquer_theme("light")
        else:
            self.appliquer_theme("dark")

    def rechercher_personnage(self, texte):
        texte_clean = texte.strip(" \t\n\r⚡✨⭐💎🔹🔸▶️👥💌💍❤️")
        if not texte_clean:
            return None

        conn = sqlite3.connect(DB_FILENAME)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT c.name, c.rank, c.kakera_value 
            FROM characters c 
            WHERE LOWER(c.name) = LOWER(?)
            """,
            (texte_clean,),
        )
        result = cursor.fetchone()

        if not result:
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
            result = cursor.fetchone()

        conn.close()

        if result:
            return {
                "original_name": result[0],
                "rank": str(result[1]) if result[1] is not None else "N/A",
                "kakera": result[2] if result[2] is not None else 0,
            }
        return None

    def vider_tableau(self):
        self.personnages_affiches.clear()
        self.table.setRowCount(0)

    def analyser_et_ajouter(self, texte):
        character = self.rechercher_personnage(texte)
        if not character:
            return

        if character["original_name"] in self.personnages_affiches:
            return

        self.personnages_affiches.add(character["original_name"])

        # Récupération des données déjà présentes pour le tri
        tous_les_persos = [character]
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 1).text()
            rank = self.table.item(row, 2).text()
            kakera_str = self.table.item(row, 3).text()
            kakera_val = int(kakera_str.replace(" 🌸", "").replace(" 💎", ""))
            
            tous_les_persos.append({
                "original_name": name,
                "rank": rank,
                "kakera": kakera_val
            })

        # Tri par Kakera décroissant
        tous_les_persos.sort(key=lambda x: x["kakera"], reverse=True)

        # Nettoyage et réinsertion
        self.table.setRowCount(0)
        for i, p in enumerate(tous_les_persos, start=1):
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            # Création et configuration des cellules de la ligne
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

    def verifier_presse_papiers(self):
        try:
            clipboard = QApplication.clipboard()
            contenu_actuel = clipboard.text()
            if contenu_actuel != self.dernier_contenu and contenu_actuel.strip():
                self.dernier_contenu = contenu_actuel
                self.analyser_et_ajouter(contenu_actuel)
        except Exception:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)

    if not os.path.exists(DB_FILENAME):
        QMessageBox.critical(
            None, 
            "Erreur", 
            f"Base de données '{DB_FILENAME}' introuvable."
        )
        sys.exit(1)
    else:
        window = MudaeHelperApp()
        window.show()
        sys.exit(app.exec())
