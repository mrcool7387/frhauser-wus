#region IMPORTS
import atexit
from dataclasses import dataclass
import json
import customtkinter as ctk
from datetime import date, datetime
import logging
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
logger: logging.Logger = logging.getLogger("MAINAPP")
#endregion LOGGING

#region GLOBALS
APP_NAME: str = "Werwolf User Selector App"
APP_VERSION: str = "1.0.0"

NAMESLIST: list[User] = []
SELECTED: list[User] =[]
#endregion GLOBALS

#region CLASSES
@dataclass
class User:
    id: UUID
    first_name: str
    last_name: str
    last_played: datetime | None
#endregion CLASSES

#region SETUP
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

try:
    with open("data.json", "r") as f:
        data = json.load(f)
        for user_data in data:
            user = User(
                id=UUID(user_data["id"]),
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                last_played=datetime.fromisoformat(user_data["last_played"]) if user_data["last_played"] else None
            )
            NAMESLIST.append(user)
    logger.info("Loaded existing users from data.json.")
    for i, u in enumerate(NAMESLIST):
        logger.debug(f"{i:03d}:{repr(u)}")
except FileNotFoundError:
    logger.warning("data.json not found. Starting with an empty user list.")

#endregion SETUP

#region MAIN_APP
class MainApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("800x600")
        logger.info("Application initialized.")#
        
        self.btn_addUser = ctk.CTkButton(master=self, text="Add User", command=self.add_user, fg_color="green")
        self.btn_addUser.pack(pady=20, side="top", padx=20, anchor="ne")
        
        logger.info("Main window set up.")
    
    def add_user(self) -> None:
        popup = ctk.CTkToplevel(self)
        popup.title("User hinzufügen")
        popup.geometry("400x100")

        frame = ctk.CTkFrame(master=popup)
        frame.pack(pady=20, padx=20, fill="both", expand=True)

        entry_frame = ctk.CTkFrame(master=frame)
        entry_frame.pack(pady=10)

        entry_vorname = ctk.CTkEntry(master=entry_frame, placeholder_text="Vorname")
        entry_vorname.pack(side="left", padx=5)
        entry_vorname.focus()

        def focus_vorname(event) -> None:
            logger.debug("Focusing Nachname entry.")
            entry_nachname.focus() 
        entry_vorname.bind("<Return>", focus_vorname)
        
        entry_nachname = ctk.CTkEntry(master=entry_frame, placeholder_text="Nachname")
        entry_nachname.pack(side="left", padx=5)
        
        def send_user(event) -> None:
            logger.debug(f"Creating new user. ({entry_vorname.get() = }; {entry_nachname.get() = })")
            self._create_user(entry_vorname.get(), entry_nachname.get())
            popup.destroy()
        entry_nachname.bind("<Return>", send_user)
        
    def _create_user(self, vorname: str, nachname: str) -> None:
        logger.info("Creating user instance.")
        new_user = User(id=uuid4(), first_name=vorname, last_name=nachname, last_played=datetime.fromordinal(1))
        logger.debug(f"User instance created: {repr(new_user)}")
        
        NAMESLIST.append(new_user)
        logger.info(f"User '{vorname} {nachname}' added.")

    def run(self) -> None:
        self.mainloop()
        

#endregion MAIN_APP

@atexit.register
def on_exit() -> None:
    logger.info("Application is exiting. Saving state...")
    with open("data.json", "w") as f:
        json.dump([user.__dict__ for user in NAMESLIST], f, default=str)
    logger.info("State saved successfully.")
    
    logger.critical("Goodbye!")
    

if __name__ == "__main__":
    app = MainApp()
    app.run()