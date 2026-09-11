import re

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = r'''        cv = tk\.Canvas\(card, bg=C\["surface"\], height=460, highlightthickness=0\)
        cv\.pack\(fill="x", padx=10, pady=10\)
        
        accounts = self\.discover_accounts\(\)
        accounts\.sort\(key=lambda x: \(0 if x\[1\]\.lower\(\) == "tuan03" or x\[0\]\.name == "\.codex-tuan03" else 1, x\[1\]\.lower\(\)\)\)
        
        if not accounts:
            return
            
        main_acc = accounts\[0\]
        others = accounts\[1:\]
        
        self\.nexus_nodes = \[\]
        self\.nexus_active_target = others\[0\]\[0\] if others else None
            
        main_x, main_y = 120, 230
        
        def draw_node_limits\(path, cx, cy, tag=None\):
            snap = self\.snapshots\.get\(path\)
            tags = \("target_node", tag\) if tag else \(\)
            if not snap or not snap\.limits:
                cv\.create_text\(cx, cy, text="No limit data", fill=C\["text_3"\], font=\(FONT_FAMILY, 9\), tags=tags\)
                return
            
            y_offset = cy
            for lim in snap\.limits\[:2\]:
                name = str\(lim\.name\)\.replace\(" window", ""\)
                rem = lim\.remaining if lim\.remaining is not None else 0
                color = usage_color\(rem\)
                
                cv\.create_text\(cx, y_offset, text=f"\{name\} \(\{int\(rem\)\}%\)", fill=color, font=\(FONT_FAMILY, 9, "bold"\), tags=tags\)
                
                # Draw Progress Bar
                w = 36
                y_bar = y_offset \+ 10
                cv\.create_line\(cx - w, y_bar, cx \+ w, y_bar, fill=C\["border_strong"\], width=4, capstyle="round", tags=tags\)
                if rem > 0:
                    pct = max\(0\.02, min\(1\.0, rem / 100\.0\)\)
                    cv\.create_line\(cx - w, y_bar, cx - w \+ \(2\*w \* pct\), y_bar, fill=color, width=4, capstyle="round", tags=tags\)
                
                y_offset \+ 26

        # Draw Main Node
        cv\.create_oval\(main_x-40, main_y-40, main_x\+40, main_y\+40, fill=C\["surface_2"\], outline=C\["indigo"\], width=3\)
        cv\.create_text\(main_x, main_y, text="★", fill=C\["indigo_glow"\], font=\(FONT_FAMILY, 24, "bold"\)\)
        cv\.create_text\(main_x, main_y\+60, text=main_acc\[1\], fill=C\["text"\], font=\(FONT_FAMILY, 12, "bold"\)\)
        draw_node_limits\(main_acc\[0\], main_x, main_y\+84\)
        
        # Calculate positions for others
        spacing = 460 / \(len\(others\) \+ 1\) if others else 0
        
        for i, \(path, label\) in enumerate\(others\):
            ox = 550
            oy = spacing \* \(i \+ 1\)
            
            tag = f"node_\{i\}"
            cv\.create_oval\(ox-25, oy-25, ox\+25, oy\+25, fill=C\["surface_2"\], outline=C\["border_strong"\], width=2, tags=\("target_node", tag\)\)
            cv\.create_text\(ox, oy, text=\(label\[:1\] or "C"\)\.upper\(\), fill=C\["text_2"\], font=\(FONT_FAMILY, 14, "bold"\)\)
            cv\.create_text\(ox, oy\+42, text=label, fill=C\["text_2"\], font=\(FONT_FAMILY, 11, "bold"\), tags=\("target_node", tag\)\)
            draw_node_limits\(path, ox, oy\+64, tag=tag\)
            self\.nexus_nodes\.append\(\{"path": path, "x": ox, "y": oy, "tag": tag\}\)'''

replacement = '''        accounts = self.discover_accounts()
        accounts.sort(key=lambda x: (0 if x[1].lower() == "tuan03" or x[0].name == ".codex-tuan03" else 1, x[1].lower()))
        
        if not accounts:
            return
            
        main_acc = accounts[0]
        others = accounts[1:]

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
        
        # Calculate positions for others in a dynamic grid
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
            self.nexus_nodes.append({"path": path, "x": ox, "y": oy, "tag": tag})'''

# Replace carefully
content = re.sub(target, replacement, content)

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch grid layout successful!")
