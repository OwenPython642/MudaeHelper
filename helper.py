import os
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
import pyperclip

DB_FILENAME = "mudae_characters.db"


def rechercher_personnage(texte):
    """Recherche un personnage par son nom principal ou ses alias dans la DB."""
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


def vider_tableau():
    global personnages_affiches
    personnages_affiches.clear()
    for item in tree.get_children():
        tree.delete(item)


def analyser_et_ajouter(texte):
    global personnages_affiches

    character = rechercher_personnage(texte)
    if not character:
        return

    if character["original_name"] in personnages_affiches:
        return

    personnages_affiches.add(character["original_name"])

    tous_les_persos = [character]
    for item in tree.get_children():
        valeurs = tree.item(item)["values"]
        tous_les_persos.append(
            {
                "original_name": valeurs[1],
                "rank": valeurs[2],
                "kakera": int(str(valeurs[3]).replace(" 🌸", "").replace(" 💎", "")),
            }
        )

    for item in tree.get_children():
        tree.delete(item)

    tous_les_persos.sort(key=lambda x: x["kakera"], reverse=True)

    for i, p in enumerate(tous_les_persos, start=1):
        tree.insert(
            "",
            tk.END,
            values=(i, p["original_name"], p["rank"], f"{p['kakera']} 🌸"),
        )


def verifier_presse_papiers():
    global dernier_contenu
    try:
        contenu_actuel = pyperclip.paste()
        if contenu_actuel != dernier_contenu and contenu_actuel.strip():
            dernier_contenu = contenu_actuel
            analyser_et_ajouter(contenu_actuel)
    except Exception:
        pass

    root.after(300, verifier_presse_papiers)


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

current_theme = "dark"


def appliquer_theme(theme_name):
    global current_theme
    current_theme = theme_name
    t = THEMES[theme_name]

    root.configure(bg=t["bg_main"])
    main_frame.configure(bg=t["bg_main"])
    top_frame.configure(bg=t["bg_main"])
    title_label.configure(bg=t["bg_main"], fg=t["fg_title"])

    style.configure(
        "Treeview",
        background=t["bg_container"],
        fieldbackground=t["bg_container"],
        foreground=t["fg_text"],
    )
    style.map(
        "Treeview",
        background=[("selected", t["select_bg"])],
        foreground=[("selected", t["select_fg"])],
    )
    style.configure(
        "Treeview.Heading", background=t["color_header"], foreground=t["fg_text"]
    )
    style.map("Treeview.Heading", background=[("active", t["color_primary"])])

    btn_clear.configure(
        bg=t["color_primary"], fg=t["fg_text"] if theme_name == "light" else "#1e1a24"
    )

    btn_theme.configure(
        bg=t["bg_container"],
        activebackground=t["color_header"],
        text="☀️" if theme_name == "dark" else "🌙",
    )


def toggle_theme():
    if current_theme == "dark":
        appliquer_theme("light")
    else:
        appliquer_theme("dark")


def on_enter_clear(e):
    t = THEMES[current_theme]
    btn_clear["bg"] = t["color_hover"]
    if current_theme == "dark":
        btn_clear["fg"] = "#ffffff"


def on_leave_clear(e):
    t = THEMES[current_theme]
    btn_clear["bg"] = t["color_primary"]
    btn_clear["fg"] = t["fg_text"] if current_theme == "light" else "#1e1a24"


dernier_contenu = ""
personnages_affiches = set()

if not os.path.exists(DB_FILENAME):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Erreur", f"Base de données '{DB_FILENAME}' introuvable.")
else:
    root = tk.Tk()
    root.title("🌸 Mudae Rolls Helper 🌸")
    root.geometry("620x540")
    root.minsize(580, 450)
    root.attributes("-topmost", True)

    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    style = ttk.Style()
    style.theme_use("clam")

    style.configure("Treeview", rowheight=32, font=("Segoe UI", 10), borderwidth=0)
    style.configure(
        "Treeview.Heading", font=("Segoe UI", 10, "bold"), rowheight=35, borderwidth=0
    )

    main_frame = tk.Frame(root)
    main_frame.grid(row=0, column=0, sticky="nsew", padx=25, pady=20)

    main_frame.grid_rowconfigure(1, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)

    top_frame = tk.Frame(main_frame)
    top_frame.grid(row=0, column=0, pady=(0, 10), sticky="ew")
    top_frame.grid_columnconfigure(
        0, weight=1
    )

    title_label = tk.Label(
        top_frame,
        text="✨ quoicoubibou des montagnes ✨",
        font=("Malgun Gothic", 14, "bold"),
        anchor="w",
    )
    title_label.grid(row=0, column=0, sticky="w")

    btn_theme = tk.Button(
        top_frame,
        command=toggle_theme,
        font=("Segoe UI", 12),
        bd=0,
        relief="flat",
        cursor="hand2",
        padx=8,
        pady=4,
    )
    btn_theme.grid(row=0, column=1, sticky="e")

    colonnes = ("#", "Nom", "Rang", "Valeur")
    tree = ttk.Treeview(main_frame, columns=colonnes, show="headings")

    tree.heading("#", text="♡")
    tree.heading("Nom", text="Waifu / Husband  🎀")
    tree.heading("Rang", text="Rang  ⭐")
    tree.heading("Valeur", text="Kakera  🌸")

    tree.column("#", width=50, minwidth=40, anchor="center")
    tree.column("Nom", width=240, minwidth=150, anchor="w")
    tree.column("Rang", width=110, minwidth=80, anchor="center")
    tree.column("Valeur", width=120, minwidth=90, anchor="center")

    tree.grid(row=1, column=0, sticky="nsew")

    btn_clear = tk.Button(
        main_frame,
        text="💖  Vider la liste  💖",
        command=vider_tableau,
        font=("Segoe UI", 10, "bold"),
        bd=0,
        relief="flat",
        cursor="hand2",
        activebackground="#ff69b4",
        activeforeground="white",
        pady=10,
    )
    btn_clear.grid(
        row=2, column=0, pady=(15, 0), ipadx=30
    )
    btn_clear.bind("<Enter>", on_enter_clear)
    btn_clear.bind("<Leave>", on_leave_clear)

    appliquer_theme(current_theme)

    root.after(300, verifier_presse_papiers)
    root.mainloop()