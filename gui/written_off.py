import logging
import customtkinter as ctk

class WrittenOffPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        logging.debug("Initializing WrittenOffPage")

        nav_frame = ctk.CTkFrame(self)
        nav_frame.pack(fill="x", pady=10)

        btn_back = ctk.CTkButton(nav_frame, text="← Назад", command=lambda: controller.switch_page("MainMenu"))
        btn_back.pack(side="left", padx=20)

        btn_home = ctk.CTkButton(nav_frame, text="Головна", command=lambda: controller.switch_page("MainMenu"))
        btn_home.pack(side="left", padx=20)

        lbl = ctk.CTkLabel(self, text="Списане обладнання", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)

        self.results_frame = ctk.CTkFrame(self)
        self.results_frame.pack(pady=10, fill="both", expand=True)

        self.results_list = ctk.CTkScrollableFrame(self.results_frame)
        self.results_list.pack(fill="both", expand=True)

    def refresh(self):
        for widget in self.results_list.winfo_children():
            widget.destroy()
        rows = self.db.get_all_equipment(show_written_off=True)
        for r in rows:
            btn = ctk.CTkButton(self.results_list,
                                text=f"{r['inventory_number']} — {r['name']} ({r['type']})\n{r['room']} | {r['owner']}",
                                anchor="w",
                                height=60,
                                command=lambda rid=r['id']: self.open_equipment_card(rid))
            btn.pack(pady=5, padx=10, fill="x")
        logging.debug("WrittenOffPage refreshed")

    def open_equipment_card(self, equip_id):
        eq_page = self.controller.frames["EquipmentCardPage"]
        eq_page.load_equipment(equip_id)
        self.controller.switch_page("EquipmentCardPage")
        logging.debug(f"Opening EquipmentCardPage for equipment ID: {equip_id}")
