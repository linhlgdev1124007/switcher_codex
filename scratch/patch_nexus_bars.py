import re

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = r'''        def format_limits\(path\):
            snap = self\.snapshots\.get\(path\)
            if not snap or not snap\.limits:
                return "No limit data"
            parts = \[\]
            for lim in snap\.limits:
                name = str\(lim\.name\)\.replace\(" window", ""\)
                if lim\.remaining is not None:
                    parts\.append\(f"\{name\}: \{int\(lim\.remaining\)\}"\)
            return " \| "\.join\(parts\[:2\]\) if parts else "No limit data"

        # Draw Main Node
        cv\.create_oval\(main_x-40, main_y-40, main_x\+40, main_y\+40, fill=C\["surface_2"\], outline=C\["indigo"\], width=3\)
        cv\.create_text\(main_x, main_y, text="★", fill=C\["indigo_glow"\], font=\(FONT_FAMILY, 24, "bold"\)\)
        cv\.create_text\(main_x, main_y\+60, text=main_acc\[1\], fill=C\["text"\], font=\(FONT_FAMILY, 12, "bold"\)\)
        cv\.create_text\(main_x, main_y\+78, text=format_limits\(main_acc\[0\]\), fill=C\["emerald"\], font=\(FONT_FAMILY, 9\)\)
        
        # Calculate positions for others
        spacing = 460 / \(len\(others\) \+ 1\) if others else 0
        
        for i, \(path, label\) in enumerate\(others\):
            ox = 550
            oy = spacing \* \(i \+ 1\)
            
            tag = f"node_\{i\}"
            cv\.create_oval\(ox-25, oy-25, ox\+25, oy\+25, fill=C\["surface_2"\], outline=C\["border_strong"\], width=2, tags=\("target_node", tag\)\)
            cv\.create_text\(ox, oy, text=\(label\[:1\] or "C"\)\.upper\(\), fill=C\["text_2"\], font=\(FONT_FAMILY, 14, "bold"\)\)
            cv\.create_text\(ox, oy\+45, text=label, fill=C\["text_2"\], font=\(FONT_FAMILY, 10\)\)
            cv\.create_text\(ox, oy\+60, text=format_limits\(path\), fill=C\["emerald"\], font=\(FONT_FAMILY, 8\)\)
            self\.nexus_nodes\.append\(\{"path": path, "x": ox, "y": oy, "tag": tag\}\)'''

replacement = '''        def draw_node_limits(path, cx, cy, tag=None):
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
        
        # Calculate positions for others
        spacing = 460 / (len(others) + 1) if others else 0
        
        for i, (path, label) in enumerate(others):
            ox = 550
            oy = spacing * (i + 1)
            
            tag = f"node_{i}"
            cv.create_oval(ox-25, oy-25, ox+25, oy+25, fill=C["surface_2"], outline=C["border_strong"], width=2, tags=("target_node", tag))
            cv.create_text(ox, oy, text=(label[:1] or "C").upper(), fill=C["text_2"], font=(FONT_FAMILY, 14, "bold"))
            cv.create_text(ox, oy+42, text=label, fill=C["text_2"], font=(FONT_FAMILY, 11, "bold"), tags=("target_node", tag))
            draw_node_limits(path, ox, oy+64, tag=tag)
            self.nexus_nodes.append({"path": path, "x": ox, "y": oy, "tag": tag})'''

content = re.sub(target, replacement, content)

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch progress bar successful!")
