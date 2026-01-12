#region IMPORTS
import atexit
from dataclasses import dataclass, replace
import json
import customtkinter as ctk
from datetime import datetime
import logging
import random
from rich.logging import RichHandler
from rich.traceback import install as rtb_install
from uuid import UUID, uuid4
from tkinter import messagebox

rtb_install()
#endregion IMPORTS

#region LOGGING
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, tracebacks_show_locals=True)]
)
logger: logging.Logger = logging.getLogger("WERWOLF_APP")
#endregion LOGGING

#region GLOBALS
APP_NAME: str = "Werwolf User Selector"
APP_VERSION: str = "1.6.1"

NAMESLIST: list['User'] = []
HISTORY: list[dict] = []
#endregion GLOBALS

#region CLASSES
@dataclass(frozen=True)
class User:
    id: UUID
    first_name: str
    last_name: str
    last_played: datetime | None
    total_games: int = 0
    is_blacklisted: bool = False

    def get_time_diff_str(self) -> str:
        if not self.last_played: return "nie"
        delta = datetime.now() - self.last_played
        seconds = delta.total_seconds()
        if seconds < 60: return "gerade eben"
        minutes = int(seconds // 60)
        if minutes < 60: return f"vor {minutes} Min."
        hours = int(minutes // 60)
        if hours < 24: return f"vor {hours} Std."
        return f"vor {int(hours // 24)} Tagen"

    def days_since_last_play(self) -> int:
        if not self.last_played: return 999
        return (datetime.now() - self.last_played).days

    def get_display_text(self) -> str:
        status = " [!] GESPERRT" if self.is_blacklisted else f" ({self.get_time_diff_str()})"
        return f"{self.first_name} {self.last_name}{status}"
#endregion CLASSES

#region WINDOWS
class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Vergangene Runden")
        self.geometry("500x600")
        self.attributes("-topmost", True)

        ctk.CTkLabel(self, text="Historie der Ziehungen", font=("Arial", 20, "bold")).pack(pady=15)
        
        container = ctk.CTkScrollableFrame(self)
        container.pack(expand=True, fill="both", padx=20, pady=10)

        if not HISTORY:
            ctk.CTkLabel(container, text="Noch keine Spiele aufgezeichnet.").pack(pady=20)

        for entry in reversed(HISTORY):
            frame = ctk.CTkFrame(container)
            frame.pack(fill="x", pady=10, padx=5)
            
            time_str = datetime.fromisoformat(entry["timestamp"]).strftime("%d.%m.%Y %H:%M")
            ctk.CTkLabel(frame, text=f"Runde am {time_str}", font=("Arial", 12, "bold"), text_color="#3498db").pack(pady=2, padx=10, anchor="w")
            
            names = ", ".join(entry["players"])
            lbl_names = ctk.CTkLabel(frame, text=names, font=("Arial", 11), wraplength=400, justify="left")
            lbl_names.pack(pady=5, padx=10, anchor="w")

class ResultWindow(ctk.CTkToplevel):
    def __init__(self, parent, winners: list[User]):
        super().__init__(parent)
        self.title("Die Auserwählten")
        self.geometry("400x600")
        self.attributes("-topmost", True)
        
        ctk.CTkLabel(self, text="Auslosung abgeschlossen", font=("Arial", 20, "bold"), text_color="#2ecc71").pack(pady=15)
        
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(expand=True, fill="both", padx=20, pady=10)

        for i, user in enumerate(winners, 1):
            f = ctk.CTkFrame(scroll)
            f.pack(fill="x", pady=3)
            ctk.CTkLabel(f, text=f"{i}. {user.first_name} {user.last_name}", font=("Arial", 14)).pack(side="left", padx=10, pady=5)
#endregion WINDOWS

#region MAIN_APP
class MainApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1200x850")

        self.present_user_ids: set[UUID] = set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        self.lbl_title = ctk.CTkLabel(self, text="Werwolf Spielermanagement Deluxe", font=("Arial", 28, "bold"))
        self.lbl_title.grid(row=0, column=0, columnspan=2, pady=20)

        # Listen
        self.frame_left = ctk.CTkFrame(self)
        self.frame_left.grid(row=1, column=0, padx=15, pady=10, sticky="nsew")
        self.lbl_present_count = ctk.CTkLabel(self.frame_left, text="Anwesend (0)", font=("Arial", 18, "bold"), text_color="#e67e22")
        self.lbl_present_count.pack(pady=5)
        self.listbox_present = ctk.CTkScrollableFrame(self.frame_left, fg_color="#2c3e50")
        self.listbox_present.pack(expand=True, fill="both", padx=10, pady=5)

        self.frame_right = ctk.CTkFrame(self)
        self.frame_right.grid(row=1, column=1, padx=15, pady=10, sticky="nsew")
        ctk.CTkLabel(self.frame_right, text="Alle registrierten Spieler", font=("Arial", 18)).pack(pady=5)
        self.listbox_all = ctk.CTkScrollableFrame(self.frame_right)
        self.listbox_all.pack(expand=True, fill="both", padx=10, pady=5)

        # Bottom Bar
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=15)

        self.btn_addUser = ctk.CTkButton(self.control_frame, text="+ Neuer Spieler", command=self.add_user_popup, fg_color="#2ecc71")
        self.btn_addUser.pack(side="left", padx=5)
        
        self.btn_history = ctk.CTkButton(self.control_frame, text="Historie", command=lambda: HistoryWindow(self), fg_color="#34495e")
        self.btn_history.pack(side="left", padx=5)

        self.btn_draw = ctk.CTkButton(self.control_frame, text="JETZT LOSEN", command=self.draw_from_present, fg_color="#e67e22", height=45, font=("Arial", 16, "bold"))
        self.btn_draw.pack(side="right", padx=10)

        self.draw_count_entry = ctk.CTkEntry(self.control_frame, width=60, font=("Arial", 14, "bold"))
        self.draw_count_entry.insert(0, "12")
        self.draw_count_entry.pack(side="right", padx=5)

        self.load_data()
        self.refresh_lists()

    def load_data(self):
        try:
            with open("data.json", "r") as f:
                content = json.load(f)
                
                # Check ob altes Listenformat vorliegt
                if isinstance(content, list):
                    logger.info("Altes Datenformat erkannt. Konvertiere...")
                    users_data = content
                    global HISTORY
                    HISTORY = []
                else:
                    users_data = content.get("users", [])
                    HISTORY = content.get("history", [])
                
                for ud in users_data:
                    u = User(
                        id=UUID(ud["id"]),
                        first_name=ud["first_name"],
                        last_name=ud["last_name"],
                        last_played=datetime.fromisoformat(ud["last_played"]) if ud.get("last_played") else None,
                        total_games=ud.get("total_games", 0),
                        is_blacklisted=ud.get("is_blacklisted", False)
                    )
                    NAMESLIST.append(u)
            logger.info("Daten erfolgreich geladen.")
        except FileNotFoundError:
            logger.warning("Keine data.json gefunden, starte leer.")
        except Exception as e:
            logger.error(f"Kritischer Fehler beim Laden: {e}")

    def refresh_lists(self) -> None:
        for widget in self.listbox_all.winfo_children(): widget.destroy()
        for widget in self.listbox_present.winfo_children(): widget.destroy()

        NAMESLIST.sort(key=lambda u: (u.first_name.lower(), u.last_name.lower()))
        self.lbl_present_count.configure(text=f"Anwesend ({len(self.present_user_ids)})")

        for user in NAMESLIST:
            target = self.listbox_present if user.id in self.present_user_ids else self.listbox_all
            
            btn_color = "#c0392b" if user.is_blacklisted else ("#d35400" if user.id in self.present_user_ids else "transparent")
            text_color = "white" if (user.is_blacklisted or user.id in self.present_user_ids) else None
            
            stats_text = f" [Spiele: {user.total_games}]"
            btn = ctk.CTkButton(target, text=user.get_display_text() + stats_text, 
                                 fg_color=btn_color, text_color=text_color, anchor="w",
                                 command=lambda u=user: self.toggle_presence(u))
            btn.pack(fill="x", pady=2, padx=5)
            
            btn.bind("<Button-3>", lambda event, u=user: self.show_context_menu(u))

    def show_context_menu(self, user: User):
        menu = ctk.CTkToplevel(self)
        menu.title("Optionen")
        menu.geometry("200x180")
        menu.attributes("-topmost", True)
        
        ctk.CTkLabel(menu, text=f"{user.first_name} verwalten", font=("Arial", 12, "bold")).pack(pady=10)
        
        status_txt = "Entsperren" if user.is_blacklisted else "Blacklisten"
        ctk.CTkButton(menu, text=status_txt, fg_color="#f39c12", 
                     command=lambda: [self.toggle_blacklist(user), menu.destroy()]).pack(pady=5, padx=10, fill="x")
        
        ctk.CTkButton(menu, text="Spieler löschen", fg_color="#e74c3c", 
                     command=lambda: [self.delete_user(user), menu.destroy()]).pack(pady=5, padx=10, fill="x")

    def toggle_blacklist(self, user: User):
        idx = next(i for i, u in enumerate(NAMESLIST) if u.id == user.id)
        NAMESLIST[idx] = replace(user, is_blacklisted=not user.is_blacklisted)
        if NAMESLIST[idx].is_blacklisted:
            self.present_user_ids.discard(user.id)
        self.refresh_lists()

    def delete_user(self, user: User):
        if messagebox.askyesno("Löschen", f"{user.first_name} wirklich löschen?"):
            global NAMESLIST
            NAMESLIST = [u for u in NAMESLIST if u.id != user.id]
            self.present_user_ids.discard(user.id)
            self.refresh_lists()

    def toggle_presence(self, user: User) -> None:
        if user.is_blacklisted:
            messagebox.showwarning("Gesperrt", "Dieser Spieler steht auf der Blacklist!")
            return
        if user.id in self.present_user_ids: self.present_user_ids.remove(user.id)
        else: self.present_user_ids.add(user.id)
        self.refresh_lists()

    def add_user_popup(self) -> None:
        popup = ctk.CTkToplevel(self)
        popup.geometry("300x200")
        v = ctk.CTkEntry(popup, placeholder_text="Vorname"); v.pack(pady=10)
        n = ctk.CTkEntry(popup, placeholder_text="Nachname"); n.pack(pady=10)
        def save():
            if v.get():
                NAMESLIST.append(User(id=uuid4(), first_name=v.get(), last_name=n.get(), last_played=None))
                self.refresh_lists(); popup.destroy()
        ctk.CTkButton(popup, text="Speichern", command=save).pack()

    def draw_from_present(self) -> None:
        try: target = int(self.draw_count_entry.get())
        except: return

        candidates = [u for u in NAMESLIST if u.id in self.present_user_ids and not u.is_blacklisted]
        if not candidates:
            messagebox.showinfo("Info", "Bitte erst Spieler in die linke Liste ziehen.")
            return

        count = min(target, len(candidates))
        winners = []
        pool = list(candidates)

        for _ in range(count):
            w = [pow(u.days_since_last_play() + 1, 2) for u in pool]
            pick = random.choices(pool, weights=w, k=1)[0]
            winners.append(pick)
            pool.remove(pick)

        now = datetime.now()
        winner_names = []
        for i, user in enumerate(NAMESLIST):
            if any(w.id == user.id for w in winners):
                NAMESLIST[i] = replace(user, last_played=now, total_games=user.total_games + 1)
                winner_names.append(f"{user.first_name} {user.last_name}")
        
        HISTORY.append({
            "timestamp": now.isoformat(),
            "players": winner_names
        })
        if len(HISTORY) > 30: HISTORY.pop(0)

        self.refresh_lists()
        ResultWindow(self, [u for u in NAMESLIST if any(w.id == u.id for w in winners)])

    def run(self) -> None: self.mainloop()
#endregion MAIN_APP

@atexit.register
def on_exit() -> None:
    with open("data.json", "w") as f:
        json.dump({
            "users": [{
                "id": str(u.id), "first_name": u.first_name, "last_name": u.last_name,
                "last_played": u.last_played.isoformat() if u.last_played else None,
                "total_games": u.total_games, "is_blacklisted": u.is_blacklisted
            } for u in NAMESLIST],
            "history": HISTORY
        }, f, indent=4)

if __name__ == "__main__":
    app = MainApp()
    app.run()