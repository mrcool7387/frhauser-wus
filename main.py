#region IMPORTS
import atexit
from dataclasses import dataclass
import json
import customtkinter as ctk
from datetime import datetime, timedelta
import logging
import random
from rich.logging import RichHandler
from rich.traceback import install as rtb_install
from uuid import UUID, uuid4

rtb_install()
#endregion IMPORTS

#region LOGGING
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[RichHandler(rich_tracebacks=True, tracebacks_show_locals=True)]
)
logger: logging.Logger = logging.getLogger("WERWOLF_APP")
#endregion LOGGING

#region GLOBALS
APP_NAME: str = "Werwolf User Selector"
APP_VERSION: str = "1.1.0"

NAMESLIST: list['User'] = []
#endregion GLOBALS

#region CLASSES
@dataclass
class User:
    id: UUID
    first_name: str
    last_name: str
    last_played: datetime | None

    def days_since_last_play(self) -> int:
        if not self.last_played or self.last_played.year == 1:
            return 999  # Sehr hoher Wert für "nie gespielt"
        delta = datetime.now() - self.last_played
        return delta.days

    def get_display_text(self) -> str:
        days = self.days_since_last_play()
        time_str = "nie" if days >= 999 else f"vor {days} Tagen"
        return f"{self.first_name} {self.last_name} ({time_str})"
#endregion CLASSES

#region SETUP
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

try:
    with open("data.json", "r") as f:
        data = json.load(f)
        for user_data in data:
            lp = user_data.get("last_played")
            try:
                user_uuid = UUID(user_data["id"])
            except ValueError:
                logger.error(f"Ungültige UUID für User: {user_data}")
                user_uuid = uuid4()
            user = User(
                id=user_uuid,
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                last_played=datetime.fromisoformat(lp) if lp and lp != "0001-01-01 00:00:00" else None
            )
            NAMESLIST.append(user)
    logger.info(f"{len(NAMESLIST)} User geladen.")
except FileNotFoundError:
    logger.warning("Keine data.json gefunden.")
#endregion SETUP

#region MAIN_APP
class MainApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1000x700")

        self.selected_users: list[User] = []

        # Grid Layout
        self.grid_columnconfigure(0, weight=1) # Links: Selektierte
        self.grid_columnconfigure(1, weight=1) # Rechts: Alle
        self.grid_rowconfigure(1, weight=1)

        # Header
        self.lbl_title = ctk.CTkLabel(self, text="Werwolf Spielerauswahl", font=("Arial", 24, "bold"))
        self.lbl_title.grid(row=0, column=0, columnspan=2, pady=20)

        # Linke Seite: Selektierte User
        self.frame_left = ctk.CTkFrame(self)
        self.frame_left.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.frame_left, text="Ausgewählte Spieler", font=("Arial", 16)).pack(pady=5)
        
        self.listbox_selected = ctk.CTkScrollableFrame(self.frame_left)
        self.listbox_selected.pack(expand=True, fill="both", padx=5, pady=5)

        # Rechte Seite: Alle User
        self.frame_right = ctk.CTkFrame(self)
        self.frame_right.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.frame_right, text="Alle verfügbaren User", font=("Arial", 16)).pack(pady=5)
        
        self.listbox_all = ctk.CTkScrollableFrame(self.frame_right)
        self.listbox_all.pack(expand=True, fill="both", padx=5, pady=5)

        # Bottom Controls
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        self.btn_addUser = ctk.CTkButton(self.control_frame, text="Neuer User", command=self.add_user_popup, fg_color="#2ecc71", hover_color="#27ae60")
        self.btn_addUser.pack(side="left", padx=10, pady=10)

        self.draw_count_entry = ctk.CTkEntry(self.control_frame, placeholder_text="Anzahl ziehen...", width=120)
        self.draw_count_entry.pack(side="right", padx=5)
        
        self.btn_draw = ctk.CTkButton(self.control_frame, text="Spieler auslosen", command=self.draw_players, fg_color="#3498db")
        self.btn_draw.pack(side="right", padx=10)

        self.refresh_lists()

    def refresh_lists(self) -> None:
        # Clear frames
        for widget in self.listbox_all.winfo_children():
            widget.destroy()
        for widget in self.listbox_selected.winfo_children():
            widget.destroy()

        # Alle User rechts anzeigen
        for user in NAMESLIST:
            btn = ctk.CTkButton(self.listbox_all, text=user.get_display_text(), 
                                 fg_color="transparent", border_width=1, anchor="w",
                                 command=lambda u=user: self.toggle_user(u))
            btn.pack(fill="x", pady=2, padx=2)

        # Selektierte User links
        for user in self.selected_users:
            btn = ctk.CTkButton(self.listbox_selected, text=user.get_display_text(), 
                                 fg_color="#e67e22", anchor="w",
                                 command=lambda u=user: self.toggle_user(u))
            btn.pack(fill="x", pady=2, padx=2)

    def toggle_user(self, user: User) -> None:
        if user in self.selected_users:
            self.selected_users.remove(user)
        else:
            self.selected_users.append(user)
        self.refresh_lists()

    def add_user_popup(self) -> None:
        popup = ctk.CTkToplevel(self)
        popup.title("User hinzufügen")
        popup.geometry("300x200")
        popup.after(10, popup.focus_force) # Bugfix für Fokus unter Windows

        v_name = ctk.CTkEntry(popup, placeholder_text="Vorname")
        v_name.pack(pady=10, padx=20)
        n_name = ctk.CTkEntry(popup, placeholder_text="Nachname")
        n_name.pack(pady=10, padx=20)

        def save():
            if v_name.get():
                new_u = User(id=uuid4(), first_name=v_name.get(), last_name=n_name.get(), last_played=None)
                NAMESLIST.append(new_u)
                self.refresh_lists()
                popup.destroy()

        ctk.CTkButton(popup, text="Speichern", command=save).pack(pady=10)

    def draw_players(self) -> None:
        try:
            count = int(self.draw_count_entry.get())
        except ValueError:
            logger.error("Ungültige Anzahl für die Auslosung.")
            return

        if len(NAMESLIST) < count:
            logger.warning("Nicht genug User vorhanden.")
            return

        # Gewichtete Auswahl: Höhere Wahrscheinlichkeit, wenn länger nicht gespielt
        # Gewicht = (Tage seit letztem Spiel + 1) ^ 2 (um Unterschiede zu verstärken)
        weights = [pow(u.days_since_last_play() + 1, 2) for u in NAMESLIST]
        
        drawn = random.choices(NAMESLIST, weights=weights, k=count)
        
        # Selektierte Liste für visuelles Feedback leeren und mit gezogenen füllen
        self.selected_users = list(set(drawn)) # Set um Duplikate bei kleinem Pool zu vermeiden
        
        # Last Played aktualisieren
        now = datetime.now()
        for u in self.selected_users:
            u.last_played = now
        
        self.refresh_lists()
        logger.info(f"{len(self.selected_users)} Spieler wurden ausgelost.")

    def run(self) -> None:
        self.mainloop()

#endregion MAIN_APP

@atexit.register
def on_exit() -> None:
    logger.info("Speichere Daten...")
    with open("data.json", "w") as f:
        data_to_save = []
        for u in NAMESLIST:
            d = u.__dict__.copy()
            d["id"] = str(d["id"])
            d["last_played"] = d["last_played"].isoformat() if d["last_played"] else None
            data_to_save.append(d)
        json.dump(data_to_save, f, indent=4)
    logger.info("Daten gespeichert. Bis bald!")

if __name__ == "__main__":
    app = MainApp()
    app.run()