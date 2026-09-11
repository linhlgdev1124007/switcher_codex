import re

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add "nexus" to nav_items
nav_items_target = r'''        nav_items = \[
            \("accounts", "Profiles", "⊞"\),
            \("activity", "Activity Log", "⌁"\),
            \("settings", "Preferences", "⚙"\),
            \("about", "About", "ⓘ"\),
        \]'''
nav_items_replacement = '''        nav_items = [
            ("accounts", "Profiles", "⊞"),
            ("nexus", "Nexus Link", "🔗"),
            ("activity", "Activity Log", "⌁"),
            ("settings", "Preferences", "⚙"),
            ("about", "About", "ⓘ"),
        ]'''
content = re.sub(nav_items_target, nav_items_replacement, content)

# 2. Add "nexus" to titles
titles_target = r'''        titles = \{
            "accounts": \("Codex Profiles", "Manage isolated CODEX_HOME environments and monitor rate limits in real-time."\),
            "activity": \("Activity Log", "Recent CLI execution and login session history."\),
            "settings": \("Preferences", "Application configuration and terminal emulator bindings."\),
            "about": \("About Codex Switcher", f"Version \{APP_VERSION\} • Modern Developer Luxury Edition"\),
        \}'''
titles_replacement = '''        titles = {
            "accounts": ("Codex Profiles", "Manage isolated CODEX_HOME environments and monitor rate limits in real-time."),
            "nexus": ("Nexus Link", "Drag and drop the energy wire to link the Main profile with another."),
            "activity": ("Activity Log", "Recent CLI execution and login session history."),
            "settings": ("Preferences", "Application configuration and terminal emulator bindings."),
            "about": ("About Codex Switcher", f"Version {APP_VERSION} • Modern Developer Luxury Edition"),
        }'''
content = re.sub(titles_target, titles_replacement, content)

# 3. Add "nexus" routing in switch_page
switch_target = r'''        if page == "accounts":
            self.filter_bar.grid\(\)
            self.discover_and_render\(\)
            return

        self.filter_bar.grid_remove\(\)
        self._render_placeholder_page\(page\)'''

switch_replacement = '''        if page == "accounts":
            self.filter_bar.grid()
            self.discover_and_render()
            return
            
        if page == "nexus":
            self.filter_bar.grid_remove()
            self._render_nexus_page()
            return

        self.filter_bar.grid_remove()
        self._render_placeholder_page(page)'''
content = re.sub(switch_target, switch_replacement, content)

# 4. Add the _render_nexus_page method before _render_placeholder_page
nexus_method = '''
    def _render_nexus_page(self):
        self._clear_scroll()
        import tkinter as tk
        
        card = ctk.CTkFrame(
            self.scroll,
            fg_color=C["surface"],
            border_width=1,
            border_color=C["border"],
            corner_radius=14,
        )
        card.grid(row=0, column=0, sticky="ew", pady=(8, 0))
        
        cv = tk.Canvas(card, bg=C["surface"], height=460, highlightthickness=0)
        cv.pack(fill="x", padx=10, pady=10)
        
        accounts = self.discover_accounts()
        accounts.sort(key=lambda x: (0 if x[1].lower() == "tuan03" or x[0].name == ".codex-tuan03" else 1, x[1].lower()))
        
        if not accounts:
            return
            
        main_acc = accounts[0]
        others = accounts[1:]
        
        self.nexus_nodes = []
        self.nexus_active_target = others[0][0] if others else None
            
        main_x, main_y = 120, 230
        
        # Draw Main Node
        cv.create_oval(main_x-40, main_y-40, main_x+40, main_y+40, fill=C["surface_2"], outline=C["indigo"], width=3)
        cv.create_text(main_x, main_y, text="★", fill=C["indigo_glow"], font=(FONT_FAMILY, 24, "bold"))
        cv.create_text(main_x, main_y+60, text=main_acc[1], fill=C["text"], font=(FONT_FAMILY, 12, "bold"))
        
        # Calculate positions for others
        spacing = 460 / (len(others) + 1) if others else 0
        
        for i, (path, label) in enumerate(others):
            ox = 550
            oy = spacing * (i + 1)
            
            tag = f"node_{i}"
            cv.create_oval(ox-25, oy-25, ox+25, oy+25, fill=C["surface_2"], outline=C["border_strong"], width=2, tags=("target_node", tag))
            cv.create_text(ox, oy, text=(label[:1] or "C").upper(), fill=C["text_2"], font=(FONT_FAMILY, 14, "bold"))
            cv.create_text(ox, oy+45, text=label, fill=C["text_2"], font=(FONT_FAMILY, 10))
            self.nexus_nodes.append({"path": path, "x": ox, "y": oy, "tag": tag})
            
        # Draw Wire & Glow
        wire_glow = cv.create_line(0, 0, 0, 0, fill=C["indigo_soft"], width=8, smooth=True)
        wire_id = cv.create_line(0, 0, 0, 0, fill=C["indigo_glow"], width=3, smooth=True)
        head_id = cv.create_oval(0, 0, 0, 0, fill=C["emerald"], outline=C["window"], width=2)
        
        def update_wire(end_x, end_y):
            mid_x = (main_x + end_x) / 2
            cv.coords(wire_glow, main_x+40, main_y, mid_x, main_y, mid_x, end_y, end_x-25, end_y)
            cv.coords(wire_id, main_x+40, main_y, mid_x, main_y, mid_x, end_y, end_x-25, end_y)
            cv.coords(head_id, end_x-32, end_y-7, end_x-18, end_y+7)
            
        def snap_to_target():
            if not self.nexus_active_target:
                update_wire(main_x+40, main_y)
                return
            for n in self.nexus_nodes:
                if n["path"] == self.nexus_active_target:
                    update_wire(n["x"], n["y"])
                    cv.itemconfig(n["tag"], outline=C["emerald"], width=3)
                else:
                    cv.itemconfig(n["tag"], outline=C["border_strong"], width=2)
                    
        snap_to_target()
        
        self.dragging = False
        
        def on_press(event):
            hx, hy, hx2, hy2 = cv.coords(head_id)
            if hx - 15 <= event.x <= hx2 + 15 and hy - 15 <= event.y <= hy2 + 15:
                self.dragging = True
                cv.itemconfig(head_id, fill=C["indigo_glow"])
                
        def on_drag(event):
            if self.dragging:
                update_wire(event.x, event.y)
                # Hover effect
                for n in self.nexus_nodes:
                    d = (n["x"] - event.x)**2 + (n["y"] - event.y)**2
                    if d < 1500:
                        cv.itemconfig(n["tag"], outline=C["indigo_glow"])
                    else:
                        cv.itemconfig(n["tag"], outline=C["border_strong"])
                        
        def on_release(event):
            if not self.dragging:
                return
            self.dragging = False
            closest = None
            min_d = 9999
            for n in self.nexus_nodes:
                d = (n["x"] - event.x)**2 + (n["y"] - event.y)**2
                if d < 2500:
                    if d < min_d:
                        min_d = d
                        closest = n
            
            if closest:
                self.nexus_active_target = closest["path"]
            snap_to_target()
            cv.itemconfig(head_id, fill=C["emerald"])
            
        cv.bind("<ButtonPress-1>", on_press)
        cv.bind("<B1-Motion>", on_drag)
        cv.bind("<ButtonRelease-1>", on_release)

    def _render_placeholder_page'''

content = content.replace("    def _render_placeholder_page", nexus_method)

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch successful!")
