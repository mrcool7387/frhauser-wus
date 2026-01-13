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
import pyperclip

rtb_install()
#endregion IMPORTS

#region LOGGING
# Erhöhtes Level auf DEBUG und detailliertes Format
file_handler = logging.FileHandler(f"logs/werwolf_app--{datetime.now().strftime("%d.%m.%YT%H-%M-%S")}.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d - %(message)s")
file_handler.setFormatter(file_formatter)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, tracebacks_show_locals=True), file_handler]
)
logger: logging.Logger = logging.getLogger("WERWOLF_APP")
#endregion LOGGING

#region GLOBALS
APP_NAME: str = "Werwolf User Selector"
APP_VERSION: str = "1.7.1" # Version Bump für Logging-Update

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
class BulkImportWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        logger.debug("Initialisiere BulkImportWindow")
        self.parent = parent
        self.title("Bulk Import")
        self.geometry("400x500")
        self.attributes("-topmost", True)

        ctk.CTkLabel(self, text="Namen zeilenweise einfügen:", font=("Arial", 16, "bold")).pack(pady=10)
        self.txt_input = ctk.CTkTextbox(self, width=350, height=300)
        self.txt_input.pack(padx=20, pady=10)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)

        ctk.CTkButton(btn_frame, text="Importieren", fg_color="#2ecc71", command=self.do_import).pack(side="right", padx=20)
        ctk.CTkButton(btn_frame, text="Abbrechen", fg_color="#e74c3c", command=self.destroy).pack(side="right", padx=5)

    def do_import(self):
        raw_text = self.txt_input.get("1.0", "end-1c")
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        logger.info(f"Bulk Import gestartet. {len(lines)} Zeilen erkannt.")
        
        added_count = 0
        for line in lines:
            parts = line.split(maxsplit=1)
            f_name = parts[0]
            l_name = parts[1] if len(parts) > 1 else ""
            
            if not any(u.first_name == f_name and u.last_name == l_name for u in NAMESLIST):
                new_user = User(id=uuid4(), first_name=f_name, last_name=l_name, last_played=None)
                NAMESLIST.append(new_user)
                logger.debug(f"User hinzugefügt: {f_name} {l_name} (ID: {new_user.id})")
                added_count += 1
            else:
                logger.warning(f"Überspringe Duplikat: {f_name} {l_name}")
        
        logger.info(f"Bulk Import abgeschlossen. {added_count} User hinzugefügt.")
        self.parent.refresh_lists()
        messagebox.showinfo("Erfolg", f"{added_count} neue Spieler hinzugefügt.")
        self.destroy()

class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        logger.debug("Öffne HistoryWindow")
        self.title("Vergangene Runden")
        self.geometry("500x600")
        self.attributes("-topmost", True)

        ctk.CTkLabel(self, text="Historie der Ziehungen", font=("Arial", 20, "bold")).pack(pady=15)
        
        container = ctk.CTkScrollableFrame(self)
        container.pack(expand=True, fill="both", padx=20, pady=10)

        if not HISTORY:
            logger.info("Historie ist leer.")
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
        logger.info(f"ResultWindow erstellt für {len(winners)} Gewinner.")
        self.title("Die Auserwählten")
        self.geometry("400x600")
        self.attributes("-topmost", True)
        
        ctk.CTkLabel(self, text="Auslosung abgeschlossen", font=("Arial", 20, "bold"), text_color="#2ecc71").pack(pady=15)
        
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(expand=True, fill="both", padx=20, pady=10)

        for i, user in enumerate(winners, 1):
            logger.debug(f"Gewinner-Display: #{i} - {user.first_name} {user.last_name}")
            f = ctk.CTkFrame(scroll)
            f.pack(fill="x", pady=3)
            ctk.CTkLabel(f, text=f"{i}. {user.first_name} {user.last_name}", font=("Arial", 14)).pack(side="left", padx=10, pady=5)
#endregion WINDOWS

#region MAIN_APP
class MainApp(ctk.CTk):
    def __init__(self) -> None:
        logger.info(f"Starte {APP_NAME} v{APP_VERSION}...")
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1200x850")

        self.present_user_ids: set[UUID] = set()
        self.paused_user_ids: set[UUID] = set()
        self.session_games: dict[UUID, int] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # UI Komponenten
        self._setup_ui()
        
        # Daten laden
        self.load_data()
        self.refresh_lists()

    def _setup_ui(self):
        logger.debug("Baue Haupt-UI auf...")
        # Header
        self.lbl_title = ctk.CTkLabel(self, text="Werwolf Spielermanagement Deluxe", font=("Arial", 28, "bold"))
        self.lbl_title.grid(row=0, column=0, columnspan=2, pady=20)

        # Linke Spalte
        self.frame_left = ctk.CTkFrame(self)
        self.frame_left.grid(row=1, column=0, padx=15, pady=10, sticky="nsew")
        
        header_left = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        header_left.pack(fill="x", pady=5)
        
        self.lbl_present_count = ctk.CTkLabel(header_left, text="Anwesend (0)", font=("Arial", 18, "bold"), text_color="#e67e22")
        self.lbl_present_count.pack(side="left", padx=10)
        
        ctk.CTkButton(header_left, text="Alle Leeren", fg_color="#c0392b", 
                     command=self.clear_presence).pack(side="right", padx=10)

        self.listbox_present = ctk.CTkScrollableFrame(self.frame_left, fg_color="#2c3e50")
        self.listbox_present.pack(expand=True, fill="both", padx=10, pady=5)

        # Rechte Spalte
        self.frame_right = ctk.CTkFrame(self)
        self.frame_right.grid(row=1, column=1, padx=15, pady=10, sticky="nsew")
        
        search_frame = ctk.CTkFrame(self.frame_right, fg_color="transparent")
        search_frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(search_frame, text="Suche:").pack(side="left", padx=5)
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Name tippen...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh_lists())

        self.listbox_all = ctk.CTkScrollableFrame(self.frame_right)
        self.listbox_all.pack(expand=True, fill="both", padx=10, pady=5)

        # Bottom Bar
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=15)

        self.btn_addUser = ctk.CTkButton(self.control_frame, text="+ Neuer Spieler", command=self.add_user_popup, fg_color="#2ecc71")
        self.btn_addUser.pack(side="left", padx=5)
        
        self.btn_bulkAdd = ctk.CTkButton(self.control_frame, text="Bulk Import", command=lambda: BulkImportWindow(self), fg_color="#27ae60")
        self.btn_bulkAdd.pack(side="left", padx=5)

        self.btn_history = ctk.CTkButton(self.control_frame, text="Historie", command=lambda: HistoryWindow(self), fg_color="#34495e")
        self.btn_history.pack(side="left", padx=5)

        self.btn_draw = ctk.CTkButton(self.control_frame, text="JETZT LOSEN", command=self.draw_from_present, fg_color="#e67e22", height=45, font=("Arial", 16, "bold"))
        self.btn_draw.pack(side="right", padx=10)

        self.draw_count_entry = ctk.CTkEntry(self.control_frame, width=60, font=("Arial", 14, "bold"))
        self.draw_count_entry.insert(0, "12")
        self.draw_count_entry.pack(side="right", padx=5)

    def clear_presence(self):
        logger.warning("Benutzer versucht Anwesenheitsliste zu leeren.")
        if messagebox.askyesno("Leeren", "Alle Spieler aus der Anwesenheitsliste entfernen?"):
            old_count = len(self.present_user_ids)
            self.present_user_ids.clear()
            self.paused_user_ids.clear()
            logger.info(f"Anwesenheitsliste geleert ({old_count} Spieler entfernt).")
            self.refresh_lists()

    def load_data(self):
        logger.info("Lade Daten aus data.json...")
        try:
            with open("data.json", "r") as f:
                content = json.load(f)
                if isinstance(content, list):
                    users_data = content
                    global HISTORY
                    HISTORY = []
                    logger.debug("Altes Datenformat (Liste) erkannt.")
                else:
                    users_data = content.get("users", [])
                    HISTORY = content.get("history", [])
                    logger.debug(f"Neues Datenformat erkannt. {len(HISTORY)} Historien-Einträge.")
                
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
                logger.info(f"{len(NAMESLIST)} Spieler erfolgreich geladen.")
        except FileNotFoundError:
            logger.error("data.json nicht gefunden. Starte mit leerer Datenbank.")
        except Exception as e:
            logger.critical(f"Fehler beim Laden der Daten: {e}", exc_info=True)

    def refresh_lists(self) -> None:
        logger.debug("Refresh der Listen-UI wird ausgeführt.")
        for widget in self.listbox_all.winfo_children(): widget.destroy()
        for widget in self.listbox_present.winfo_children(): widget.destroy()

        search_term = self.search_entry.get().lower()
        NAMESLIST.sort(key=lambda u: (u.first_name.lower(), u.last_name.lower()))
        
        active_candidates = [u for u in NAMESLIST if u.id in self.present_user_ids and u.id not in self.paused_user_ids]
        pechvoegel = sorted(active_candidates, key=lambda u: u.days_since_last_play(), reverse=True)[:3]
        logger.debug(f"Pechvögel des Tages: {[f'{u.first_name} ({u.days_since_last_play()} Tage)' for u in pechvoegel]}")

        self.lbl_present_count.configure(text=f"Anwesend ({len(self.present_user_ids)})")

        for user in NAMESLIST:
            is_present = user.id in self.present_user_ids
            is_paused = user.id in self.paused_user_ids
            
            if search_term and search_term not in f"{user.first_name} {user.last_name}".lower():
                if not is_present: continue

            target = self.listbox_present if is_present else self.listbox_all
            
            btn_color = "transparent"
            text_color = None
            
            if user.is_blacklisted:
                btn_color = "#c0392b"
                text_color = "white"
            elif is_paused:
                btn_color = "#7f8c8d"
                text_color = "#bdc3c7"
            elif is_present:
                btn_color = "#d35400"
                text_color = "white"

            pech_icon = "⭐ " if user in pechvoegel and not is_paused else ""
            session_count = self.session_games.get(user.id, 0)
            stats = f" [Sitzung: {session_count} | Total: {user.total_games}]"
            
            btn = ctk.CTkButton(target, text=f"{pech_icon}{user.get_display_text()}{stats}", 
                                 fg_color=btn_color, text_color=text_color, anchor="w",
                                 command=lambda u=user: self.toggle_presence(u))
            btn.pack(fill="x", pady=2, padx=5)
            btn.bind("<Button-3>", lambda event, u=user: self.show_context_menu(u))

    def show_context_menu(self, user: User):
        logger.debug(f"Kontextmenü für {user.first_name} {user.last_name} aufgerufen.")
        menu = ctk.CTkToplevel(self)
        menu.title("Optionen")
        menu.geometry("250x200")
        menu.attributes("-topmost", True)
        
        ctk.CTkLabel(menu, text=f"{user.first_name} verwalten", font=("Arial", 12, "bold")).pack(pady=10)
        
        if user.id in self.present_user_ids:
            p_text = "Aktivieren" if user.id in self.paused_user_ids else "Pausieren"
            ctk.CTkButton(menu, text=p_text, fg_color="#3498db", 
                         command=lambda: [self.toggle_pause(user), menu.destroy()]).pack(pady=5, padx=10, fill="x")

        status_txt = "Entsperren" if user.is_blacklisted else "Blacklisten"
        ctk.CTkButton(menu, text=status_txt, fg_color="#f39c12", 
                     command=lambda: [self.toggle_blacklist(user), menu.destroy()]).pack(pady=5, padx=10, fill="x")
        
        ctk.CTkButton(menu, text="Löschen", fg_color="#e74c3c", 
                     command=lambda: [self.delete_user(user), menu.destroy()]).pack(pady=5, padx=10, fill="x")

    def toggle_pause(self, user: User):
        if user.id in self.paused_user_ids:
            self.paused_user_ids.remove(user.id)
            logger.info(f"User {user.first_name} wurde REAKTIVIERT.")
        else:
            self.paused_user_ids.add(user.id)
            logger.info(f"User {user.first_name} wurde PAUSIERT.")
        self.refresh_lists()

    def toggle_blacklist(self, user: User):
        idx = next(i for i, u in enumerate(NAMESLIST) if u.id == user.id)
        new_status = not user.is_blacklisted
        NAMESLIST[idx] = replace(user, is_blacklisted=new_status)
        logger.warning(f"BLACKLIST STATUS GEÄNDERT: {user.first_name} -> {new_status}")
        
        if NAMESLIST[idx].is_blacklisted:
            self.present_user_ids.discard(user.id)
            logger.debug(f"{user.first_name} aus Anwesenheitsliste entfernt wegen Blacklist.")
        self.refresh_lists()

    def delete_user(self, user: User):
        logger.warning(f"Versuch User zu löschen: {user.first_name}")
        if messagebox.askyesno("Löschen", f"{user.first_name} wirklich löschen?"):
            global NAMESLIST
            NAMESLIST = [u for u in NAMESLIST if u.id != user.id]
            self.present_user_ids.discard(user.id)
            self.paused_user_ids.discard(user.id)
            logger.info(f"User {user.first_name} (ID: {user.id}) endgültig gelöscht.")
            self.refresh_lists()

    def toggle_presence(self, user: User) -> None:
        if user.is_blacklisted:
            logger.error(f"Klick auf geblockten User verhindert: {user.first_name}")
            messagebox.showwarning("Gesperrt", "Dieser Spieler steht auf der Blacklist!")
            return
        
        if user.id in self.present_user_ids: 
            self.present_user_ids.remove(user.id)
            if user.id in self.paused_user_ids: self.paused_user_ids.remove(user.id)
            logger.debug(f"{user.first_name} ist nun ABWESEND.")
        else: 
            self.present_user_ids.add(user.id)
            logger.debug(f"{user.first_name} ist nun ANWESEND.")
        self.refresh_lists()

    def add_user_popup(self) -> None:
        logger.debug("Öffne Popup für neuen Spieler.")
        popup = ctk.CTkToplevel(self)
        popup.geometry("300x200")
        v = ctk.CTkEntry(popup, placeholder_text="Vorname"); v.pack(pady=10)
        n = ctk.CTkEntry(popup, placeholder_text="Nachname"); n.pack(pady=10)
        def save():
            if v.get():
                new_user = User(id=uuid4(), first_name=v.get(), last_name=n.get(), last_played=None)
                NAMESLIST.append(new_user)
                logger.info(f"Neuer Spieler manuell erstellt: {new_user.first_name} (ID: {new_user.id})")
                self.refresh_lists()
                popup.destroy()
            else:
                logger.error("Speichern fehlgeschlagen: Vorname fehlt.")
        ctk.CTkButton(popup, text="Speichern", command=save).pack()

    def draw_from_present(self) -> None:
        raw_val = self.draw_count_entry.get()
        logger.info(f"Auslosung gestartet. Zielanzahl: {raw_val}")
        try: target = int(raw_val)
        except Exception as e:
            logger.error(f"Ungültige Anzahl im Entry: {raw_val} ({e})")
            return

        candidates = [u for u in NAMESLIST if u.id in self.present_user_ids 
                     and not u.is_blacklisted and u.id not in self.paused_user_ids]
        
        logger.info(f"Pool-Größe für Auslosung: {len(candidates)}")
        
        if not candidates:
            logger.warning("Auslosung abgebrochen: Keine aktiven Kandidaten.")
            messagebox.showinfo("Info", "Keine aktiven Spieler anwesend.")
            return

        count = min(target, len(candidates))
        winners = []
        pool = list(candidates)

        # Logging der Gewichtung
        logger.debug("--- Gewichtungs-Berechnung ---")
        for p in pool:
            w = pow(p.days_since_last_play() + 1, 2)
            logger.debug(f"Candidate: {p.first_name:10} | Last: {p.get_time_diff_str():15} | Weight: {w}")

        for i in range(count):
            weights = [pow(u.days_since_last_play() + 1, 2) for u in pool]
            pick = random.choices(pool, weights=weights, k=1)[0]
            winners.append(pick)
            pool.remove(pick)
            logger.debug(f"Zug {i+1}: Gewählt wurde {pick.first_name}")

        now = datetime.now()
        winner_names = []
        for i, user in enumerate(NAMESLIST):
            if any(w.id == user.id for w in winners):
                NAMESLIST[i] = replace(user, last_played=now, total_games=user.total_games + 1)
                winner_names.append(f"{user.first_name} {user.last_name}")
                self.session_games[user.id] = self.session_games.get(user.id, 0) + 1
        
        logger.info(f"Auslosung beendet. Gewinner: {winner_names}")
        
        HISTORY.append({"timestamp": now.isoformat(), "players": winner_names})
        if len(HISTORY) > 30: 
            HISTORY.pop(0)
            logger.debug("Historie gekürzt (Limit 30 erreicht).")

        self.refresh_lists()
        ResultWindow(self, [u for u in NAMESLIST if any(w.id == u.id for w in winners)])

    def run(self) -> None: 
        logger.info("Mainloop wird gestartet.")
        self.mainloop()
#endregion MAIN_APP

@atexit.register
def on_exit() -> None:
    logger.info("Programm wird beendet. Starte Datenspeicherung...")
    try:
        data = {
            "users": [{
                "id": str(u.id), "first_name": u.first_name, "last_name": u.last_name,
                "last_played": u.last_played.isoformat() if u.last_played else None,
                "total_games": u.total_games, "is_blacklisted": u.is_blacklisted
            } for u in NAMESLIST],
            "history": HISTORY
        }
        with open("data.json", "w") as f:
            json.dump(data, f, indent=4)
        logger.info(f"Daten erfolgreich in data.json gespeichert. {len(NAMESLIST)} User gesichert.")
    except Exception as e:
        logger.critical(f"FEHLER BEIM SPEICHERN: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        app = MainApp()
        app.run()
    except Exception as e:
        logger.critical(f"FATALER FEHLER beim Programmstart: {e}", exc_info=True)