import re

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where _render_nexus_page starts
start_idx = content.find('    def _render_nexus_page(self):')
# Find where _render_placeholder_page starts
end_idx = content.find('    def _render_placeholder_page(self, page: str):')

if start_idx == -1 or end_idx == -1:
    print("Could not find method boundaries!")
    exit(1)

new_method = '''    def _render_nexus_page(self):
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
        
        accounts = self.discover_accounts()
        accounts.sort(key=lambda x: (0 if x[1].lower() == "tuan03" or x[0].name == ".codex-tuan03" else 1, x[1].lower()))
        
        if not accounts:
            return
            
        main_acc = accounts[0]
        others = accounts[1:]
        
        # Grid Layout Calculation
        req_height = max(460, (((len(others) - 1) // 2) + 1) * 160 + 100) if others else 460
        cv = tk.Canvas(card, bg=C["surface"], height=req_height, highlightthickness=0)
        cv.pack(fill="x", padx=10, pady=10)
        
        self.nexus_nodes = []
        self.nexus_active_target = others[0][0] if others else None
            
        main_x, main_y = 120, req_height / 2
        
        def draw_node_limits(path, cx, cy, tag=None):
            snap = self.snapshots.get(path)
            tags = ("target_node", tag) if tag else ()
            if not snap or not snap.limits:
                cv.create_text(cx, cy, text="No limit data", fill=C["text_3"], font=(FONT_FAMILY, 9), tags=tags)
                return
            
            y_offset = cy
            for lim in snap.limits[:2]:
                name = str(lim.name).replace(" window", "")
                rem = lim.remaining if lim.remaining is not None else 0
                color = usage_color(rem)
                
                cv.create_text(cx, y_offset, text=f"{name} ({int(rem)}%)", fill=color, font=(FONT_FAMILY, 9, "bold"), tags=tags)
                
                # Draw Progress Bar
                w = 36
                y_bar = y_offset + 10
                cv.create_line(cx - w, y_bar, cx + w, y_bar, fill=C["border_strong"], width=4, capstyle="round", tags=tags)
                if rem > 0:
                    pct = max(0.02, min(1.0, rem / 100.0))
                    cv.create_line(cx - w, y_bar, cx - w + (2*w * pct), y_bar, fill=color, width=4, capstyle="round", tags=tags)
                
                y_offset += 26

        # Draw Main Node
        cv.create_oval(main_x-40, main_y-40, main_x+40, main_y+40, fill=C["surface_2"], outline=C["indigo"], width=3)
        cv.create_text(main_x, main_y, text="★", fill=C["indigo_glow"], font=(FONT_FAMILY, 24, "bold"))
        cv.create_text(main_x, main_y+60, text=main_acc[1], fill=C["text"], font=(FONT_FAMILY, 12, "bold"))
        draw_node_limits(main_acc[0], main_x, main_y+84)
        
        # Calculate positions for others in Grid
        for i, (path, label) in enumerate(others):
            col = i % 2
            row = i // 2
            ox = 380 + col * 200
            oy = 100 + row * 160
            
            tag = f"node_{i}"
            cv.create_oval(ox-25, oy-25, ox+25, oy+25, fill=C["surface_2"], outline=C["border_strong"], width=2, tags=("target_node", tag))
            cv.create_text(ox, oy, text=(label[:1] or "C").upper(), fill=C["text_2"], font=(FONT_FAMILY, 14, "bold"))
            cv.create_text(ox, oy+42, text=label, fill=C["text_2"], font=(FONT_FAMILY, 11, "bold"), tags=("target_node", tag))
            draw_node_limits(path, ox, oy+64, tag=tag)
            self.nexus_nodes.append({"path": path, "x": ox, "y": oy, "tag": tag})
            
        # Draw Wire & Glow
        wire_glow = cv.create_line(0, 0, 0, 0, fill=C["indigo_soft"], width=8, smooth=True)
        wire_id = cv.create_line(0, 0, 0, 0, fill=C["indigo_glow"], width=3, smooth=True)
        head_id = cv.create_oval(0, 0, 0, 0, fill=C["emerald"], outline=C["window"], width=2)
        
        # We also draw an invisible larger hit-box for the head for easier dragging
        head_hitbox = cv.create_oval(0, 0, 0, 0, fill="", outline="")
        
        def update_wire(end_x, end_y):
            mid_x = (main_x + end_x) / 2
            cv.coords(wire_glow, main_x+40, main_y, mid_x, main_y, mid_x, end_y, end_x-25, end_y)
            cv.coords(wire_id, main_x+40, main_y, mid_x, main_y, mid_x, end_y, end_x-25, end_y)
            cv.coords(head_id, end_x-32, end_y-7, end_x-18, end_y+7)
            cv.coords(head_hitbox, end_x-42, end_y-17, end_x-8, end_y+17)
            
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
            # Check hitbox instead of head_id to allow easier grabbing
            items = cv.find_withtag("current")
            # Or manually check coordinates
            hx, hy, hx2, hy2 = cv.coords(head_hitbox)
            if hx <= event.x <= hx2 and hy <= event.y <= hy2:
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
            
        # Using tag_bind makes it vastly more reliable to grab
        cv.tag_bind(head_id, "<ButtonPress-1>", on_press)
        cv.tag_bind(head_hitbox, "<ButtonPress-1>", on_press)
        cv.bind("<B1-Motion>", on_drag)
        cv.bind("<ButtonRelease-1>", on_release)

'''

content = content[:start_idx] + new_method + content[end_idx:]

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Complete Nexus Rewrite Successful!")
