import logging
import customtkinter as ctk

class SearchPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing SearchPage")

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Пошук обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Введіть інвентарний номер або назву")
        self.search_entry.pack(pady=5, padx=20, fill="x")
        self.search_var.trace_add("write", self.on_text_change)

        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.pack(pady=10, fill="both", expand=True)

        self.results_list = ctk.CTkScrollableFrame(self.results_frame)
        self.results_list.pack(fill="both", expand=True)

        self.current_results = []

    def on_text_change(self, *args):
        text = self.search_var.get().strip()
        self.update_results(text)

    def update_results(self, text):
        for widget in self.results_list.winfo_children():
            widget.destroy()
        if text == "":
            return
        rows = self.db.search_equipment(text)
        self.current_results = rows
        for r in rows:
            btn = ctk.CTkButton(self.results_list,
                                text=f"{r['inventory_number']} — {r['name']} ({r['type']})\n{r['room']} | {r['owner']}",
                                anchor="w",
                                height=60,
                                command=lambda rid=r['id']: self.open_equipment_card(rid))
            btn.pack(pady=5, padx=10, fill="x")

    def open_equipment_card(self, equip_id):
        eq_page = self.controller.frames["EquipmentCardPage"]
        eq_page.load_equipment(equip_id)
        self.controller.switch_page("EquipmentCardPage")
        logging.debug(f"Opening EquipmentCardPage for equipment ID: {equip_id}")

    def refresh(self):
        self.on_text_change()
        logging.debug("SearchPage refreshed")