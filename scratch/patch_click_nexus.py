import re

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = r'''        self\.dragging = False
        
        def on_press\(event\):
            # Tính toán khoảng cách từ chuột đến tâm của head_id
            hx1, hy1, hx2, hy2 = cv\.coords\(head_id\)
            hcx = \(hx1 \+ hx2\) / 2
            hcy = \(hy1 \+ hy2\) / 2
            
            # Cho phép bán kính nắm dây lên tới 40 pixel \(rất dễ bấm\)
            if \(event\.x - hcx\)\*\*2 \+ \(event\.y - hcy\)\*\*2 < 1600:
                self\.dragging = True
                cv\.itemconfig\(head_id, fill=C\["indigo_glow"\]\)
                
        def on_drag\(event\):
            if self\.dragging:
                update_wire\(event\.x, event\.y\)
                # Hiệu ứng hover
                for n in self\.nexus_nodes:
                    d = \(n\["x"\] - event\.x\)\*\*2 \+ \(n\["y"\] - event\.y\)\*\*2
                    if d < 1500:
                        cv\.itemconfig\(n\["tag"\], outline=C\["indigo_glow"\]\)
                    else:
                        cv\.itemconfig\(n\["tag"\], outline=C\["border_strong"\]\)
                        
        def on_release\(event\):
            if not self\.dragging:
                return
            self\.dragging = False
            closest = None
            min_d = 9999
            for n in self\.nexus_nodes:
                d = \(n\["x"\] - event\.x\)\*\*2 \+ \(n\["y"\] - event\.y\)\*\*2
                if d < 2500:
                    if d < min_d:
                        min_d = d
                        closest = n
            
            if closest:
                self\.nexus_active_target = closest\["path"\]
            snap_to_target\(\)
            cv\.itemconfig\(head_id, fill=C\["emerald"\]\)
            
        cv\.bind\("<ButtonPress-1>", on_press\)
        cv\.bind\("<B1-Motion>", on_drag\)
        cv\.bind\("<ButtonRelease-1>", on_release\)'''

replacement = '''        def on_click(event):
            closest = None
            min_d = 9999
            for n in self.nexus_nodes:
                d = (n["x"] - event.x)**2 + (n["y"] - event.y)**2
                # Bán kính 65 pixel bao phủ hình tròn, chữ và thanh quota
                if d < 4225:
                    if d < min_d:
                        min_d = d
                        closest = n
            
            if closest:
                self.nexus_active_target = closest["path"]
                snap_to_target()
                
        cv.bind("<ButtonPress-1>", on_click)'''

content = re.sub(target, replacement, content)

with open(r'D:\SWITCH_CODEX\codex_switcher.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch click logic successful!")
