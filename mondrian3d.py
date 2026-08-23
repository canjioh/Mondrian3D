# -*- coding: utf-8 -*-
"""
================================================================================
 MONDRIAN 3D  -  Decostruzione di un quadro neoplastico in livelli di profondita'
================================================================================

Un quadro tipo Mondrian (rettangoli colorati + linee nere) viene trattato come
un insieme di "tessere", ciascuna estrusa in un PARALLELEPIPEDO 3D con spessore
e assegnata a un LIVELLO di profondita'.

 * Visto FRONTALMENTE (pulsante "Ricomponi") il tutto si ricompone e sembra il
   quadro originale.
 * RUOTANDO (trascina il mouse, oppure auto-rotazione attorno all'asse scelto X/
   Y/Z) i livelli si separano DAVVERO nello spazio lungo la profondita', e con
   la "spirale" ruotano attorno all'asse di profondita' allontanandosi.

 * Rendering di qualita': scatole 3D con illuminazione/ombreggiatura e
   antialiasing (supersampling). Esporta un VIDEO MP4 scaricabile.

 * EDITOR: costruisci TU il quadro, scegli colore e LIVELLO di profondita' di
   ogni pezzo, salva/carica in JSON.

Dipendenze: numpy, Pillow, imageio, imageio-ffmpeg  (gia' installate).
Avvio:      python mondrian3d.py
================================================================================
"""

import json
import math
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    raise SystemExit("Manca Pillow.  Installa con:  python -m pip install Pillow")

# --------------------------------------------------------------------------- #
#  PALETTE
# --------------------------------------------------------------------------- #
WHITE  = "#f4f3ee"
RED    = "#d1160b"
BLUE   = "#124a9c"
YELLOW = "#f6d000"
BLACK  = "#14110f"

PALETTE = [("Bianco", WHITE), ("Rosso", RED), ("Blu", BLUE),
           ("Giallo", YELLOW), ("Nero", BLACK)]

# ordine delle 6 facce del parallelepipedo (indici sui suoi 8 vertici)
FACES = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
         (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


# --------------------------------------------------------------------------- #
#  QUADRO DI ESEMPIO (ricostruzione del "Composition" allegato)
# --------------------------------------------------------------------------- #
def example_mondrian():
    lt = 0.024
    return {"name": "Composition (esempio)", "tiles": [
        {"x": 0.00, "y": 0.00, "w": 1.00, "h": 1.00, "color": WHITE, "layer": 0},
        {"x": 0.000, "y": 0.000, "w": 0.300, "h": 0.280, "color": BLUE,   "layer": 1},
        {"x": 0.300, "y": 0.320, "w": 0.700, "h": 0.680, "color": RED,    "layer": 2},
        {"x": 0.885, "y": 0.000, "w": 0.115, "h": 0.105, "color": YELLOW, "layer": 3},
        {"x": 0.300 - lt / 2, "y": 0.000,         "w": lt,    "h": 1.000, "color": BLACK, "layer": 4},
        {"x": 0.000,          "y": 0.620 - lt / 2, "w": 0.300, "h": lt,    "color": BLACK, "layer": 4},
        {"x": 0.000,          "y": 0.280 - lt / 2, "w": 0.300, "h": lt,    "color": BLACK, "layer": 4},
        {"x": 0.300,          "y": 0.320 - lt / 2, "w": 0.700, "h": lt,    "color": BLACK, "layer": 4},
        {"x": 0.885 - lt / 2, "y": 0.000,         "w": lt,    "h": 0.130, "color": BLACK, "layer": 4},
        {"x": 0.885,          "y": 0.115 - lt / 2, "w": 0.115, "h": lt,    "color": BLACK, "layer": 4},
    ]}


# --------------------------------------------------------------------------- #
#  MOTORE 3D  (rendering su immagine PIL, nessuna dipendenza da tkinter)
# --------------------------------------------------------------------------- #
def rot_matrix(axis, a):
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class Engine:
    """Rasterizzatore 3D minimale: estrude ogni tessera in un parallelepipedo,
    illumina le facce e proietta in prospettiva. Painter's algorithm."""

    def __init__(self):
        self.cam_dist = 4.2
        self.light = np.array([-0.35, 0.45, 0.82])
        self.light /= np.linalg.norm(self.light)
        self.ambient = 0.55
        self.diffuse = 0.6
        self._bg_cache = {}

    def _bg(self, W, H):
        key = (W, H)
        if key not in self._bg_cache:
            top = np.array([234, 233, 227]); bot = np.array([198, 198, 194])
            t = np.linspace(0, 1, H)[:, None, None]
            arr = (top * (1 - t) + bot * t).astype("uint8")
            arr = np.repeat(arr, W, axis=1)
            self._bg_cache[key] = Image.fromarray(arr, "RGB")
        return self._bg_cache[key].copy()

    def box_vertices(self, tile, prm):
        x, y, w, h = tile["x"], tile["y"], tile["w"], tile["h"]
        L = tile.get("layer", 0)
        e = prm["expl"]
        theta = e * L * prm["spin"]
        sc = 1.0 + e * L * prm["spread"]
        z0 = L * 0.004 + e * L * prm["gap"] - prm["zshift"]
        z1 = z0 + prm["slab"]
        ct, st = math.cos(theta), math.sin(theta)

        xs = (np.array([x, x + w, x + w, x]) - 0.5) * sc
        ys = (np.array([y, y, y + h, y + h]) - 0.5) * sc
        xr = xs * ct - ys * st
        yr = xs * st + ys * ct

        V = np.empty((8, 3))
        V[0:4, 0] = xr; V[0:4, 1] = yr; V[0:4, 2] = z0
        V[4:8, 0] = xr; V[4:8, 1] = yr; V[4:8, 2] = z1
        return V

    def render(self, tiles, prm, R, size, ss=2):
        W = H = int(size * ss)
        img = self._bg(W, H)
        draw = ImageDraw.Draw(img)
        cx = cy = W / 2.0
        scale = W * 0.52
        d = self.cam_dist
        lw = max(1, int(round(1.1 * ss)))

        faces = []
        for t in tiles:
            V = self.box_vertices(t, prm)
            cam = V @ R.T
            z = cam[:, 2]
            denom = np.clip(d - z, 0.25, None)
            f = d / denom
            sx = cx + scale * f * cam[:, 0]
            sy = cy - scale * f * cam[:, 1]
            base = hex_to_rgb(t["color"])
            for idx in FACES:
                p0, p1, p2 = cam[idx[0]], cam[idx[1]], cam[idx[2]]
                n = np.cross(p1 - p0, p2 - p0)
                nn = np.linalg.norm(n)
                if nn < 1e-9:
                    continue
                n = n / nn
                if n[2] < 0:
                    n = -n
                shade = self.ambient + self.diffuse * max(0.0, float(n @ self.light))
                col = np.clip(base * shade, 0, 255).astype(int)
                edge = np.clip(base * shade * 0.55, 0, 255).astype(int)
                pts = [(sx[k], sy[k]) for k in idx]
                zc = float(cam[idx, 2].mean())
                faces.append((zc, pts, tuple(col), tuple(edge)))

        faces.sort(key=lambda r: r[0])  # dai piu' lontani ai piu' vicini
        for _, pts, col, edge in faces:
            draw.polygon(pts, fill=col, outline=edge, width=lw)

        if ss != 1:
            img = img.resize((size, size), Image.LANCZOS)
        return img


# --------------------------------------------------------------------------- #
#  APP
# --------------------------------------------------------------------------- #
class MondrianApp:
    def __init__(self, root):
        self.root = root
        root.title("Mondrian 3D  -  decostruzione a livelli di profondita'")
        root.configure(bg="#2b2b2b")

        self.engine = Engine()
        self.tiles = example_mondrian()["tiles"]

        # vista
        self.yaw = 0.55
        self.pitch = 0.42
        self.axis = tk.StringVar(value="y")
        self.mode = tk.StringVar(value="view")
        self._auto = None
        self._auto_angle = 0.0
        self._dragging = False
        self.photo = None

        # editor
        self.cur_color = RED
        self.cur_layer = tk.IntVar(value=1)
        self.snap = tk.BooleanVar(value=True)
        self.grid_n = tk.IntVar(value=20)
        self.selected = None
        self._drag = None

        # canvas
        self.CW = self.CH = 720
        self.cx = self.CW / 2
        self.cy = self.CH / 2
        self.scale = self.CW * 0.62

        self._build_ui()
        self._set_mode()
        self.render()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        main = tk.Frame(self.root, bg="#2b2b2b")
        main.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(main, width=self.CW, height=self.CH,
                                bg="#dcdcd4", highlightthickness=0)
        self.canvas.grid(row=0, column=0, padx=8, pady=8)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        panel = tk.Frame(main, bg="#2b2b2b")
        panel.grid(row=0, column=1, sticky="n", padx=(0, 8), pady=8)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        mfr = ttk.LabelFrame(panel, text="Modalita'")
        mfr.pack(fill="x", pady=4)
        ttk.Radiobutton(mfr, text="Vista 3D", value="view",
                        variable=self.mode, command=self._set_mode).pack(anchor="w")
        ttk.Radiobutton(mfr, text="Editor (costruisci il quadro)", value="edit",
                        variable=self.mode, command=self._set_mode).pack(anchor="w")

        # ---- vista 3D -------------------------------------------------------
        self.view_fr = ttk.LabelFrame(panel, text="Vista 3D")
        self.view_fr.pack(fill="x", pady=4)

        self.expl = self._slider(self.view_fr, "Esplosione", 0, 100, 45)
        self.spin = self._slider(self.view_fr, "Spirale (gradi/livello)", 0, 120, 22)
        self.spread = self._slider(self.view_fr, "Allontanamento", 0, 100, 12)
        self.gap = self._slider(self.view_fr, "Passo profondita'", 2, 100, 45)
        self.slab = self._slider(self.view_fr, "Spessore tessere", 2, 100, 22)

        axr = ttk.Frame(self.view_fr)
        axr.pack(fill="x", pady=(6, 2))
        ttk.Label(axr, text="Asse di rotazione:").pack(side="left")
        for lab, val in (("X", "x"), ("Y", "y"), ("Z", "z")):
            ttk.Radiobutton(axr, text=lab, value=val, variable=self.axis).pack(side="left")

        brow = ttk.Frame(self.view_fr)
        brow.pack(fill="x", pady=(6, 2))
        self.auto_btn = ttk.Button(brow, text="Auto-rotazione", command=self.toggle_auto)
        self.auto_btn.pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(brow, text="Ricomponi (frontale)", command=self.recompose).pack(
            side="left", expand=True, fill="x", padx=2)

        brow2 = ttk.Frame(self.view_fr)
        brow2.pack(fill="x", pady=2)
        ttk.Button(brow2, text="Reset vista 3D", command=self.reset_view).pack(
            side="left", expand=True, fill="x", padx=2)
        ttk.Button(brow2, text="Esporta MP4...", command=self.export_dialog).pack(
            side="left", expand=True, fill="x", padx=2)

        ttk.Label(self.view_fr, wraplength=240, foreground="#555",
                  text="Trascina sul quadro per ruotare a mano.\n"
                       "L'asse X/Y/Z vale per l'auto-rotazione\n"
                       "e per il video MP4.").pack(anchor="w", pady=(4, 2))

        # ---- editor ---------------------------------------------------------
        self.edit_fr = ttk.LabelFrame(panel, text="Editor")
        self.edit_fr.pack(fill="x", pady=4)

        ttk.Label(self.edit_fr, text="Colore:").pack(anchor="w")
        pal = ttk.Frame(self.edit_fr)
        pal.pack(fill="x", pady=2)
        self.color_btns = {}
        for name, hexv in PALETTE:
            b = tk.Button(pal, width=3, bg=hexv, relief="raised",
                          command=lambda c=hexv: self.set_color(c))
            b.pack(side="left", padx=1)
            self.color_btns[hexv] = b
        tk.Button(pal, text="+", width=3, command=self.pick_color).pack(side="left", padx=1)

        lr = ttk.Frame(self.edit_fr)
        lr.pack(fill="x", pady=6)
        ttk.Label(lr, text="Livello di profondita':").pack(side="left")
        ttk.Spinbox(lr, from_=0, to=20, width=5, textvariable=self.cur_layer,
                    command=self.render).pack(side="left", padx=4)

        sr = ttk.Frame(self.edit_fr)
        sr.pack(fill="x")
        ttk.Checkbutton(sr, text="Griglia magnetica", variable=self.snap).pack(side="left")
        ttk.Spinbox(sr, from_=4, to=60, width=4, textvariable=self.grid_n,
                    command=self.render).pack(side="left", padx=4)

        er = ttk.Frame(self.edit_fr)
        er.pack(fill="x", pady=(6, 2))
        ttk.Button(er, text="Livello -> selez.", command=self.apply_layer_to_selected).pack(
            side="left", expand=True, fill="x", padx=2)
        ttk.Button(er, text="Elimina selez.", command=self.delete_selected).pack(
            side="left", expand=True, fill="x", padx=2)

        er2 = ttk.Frame(self.edit_fr)
        er2.pack(fill="x", pady=2)
        ttk.Button(er2, text="Annulla ultimo", command=self.undo).pack(
            side="left", expand=True, fill="x", padx=2)
        ttk.Button(er2, text="Pulisci tutto", command=self.clear_all).pack(
            side="left", expand=True, fill="x", padx=2)

        ttk.Label(self.edit_fr, wraplength=240, foreground="#555",
                  text="Trascina = crea rettangolo (colore/livello\n"
                       "correnti). Click = seleziona. Il numero al\n"
                       "centro e' il livello di profondita'.").pack(anchor="w", pady=(4, 2))

        # ---- file -----------------------------------------------------------
        ffr = ttk.LabelFrame(panel, text="File")
        ffr.pack(fill="x", pady=4)
        ttk.Button(ffr, text="Salva JSON...", command=self.save_json).pack(fill="x", pady=1)
        ttk.Button(ffr, text="Carica JSON...", command=self.load_json).pack(fill="x", pady=1)
        ttk.Button(ffr, text="Carica esempio Mondrian", command=self.load_example).pack(fill="x", pady=1)

        for s in (self.expl, self.spin, self.spread, self.gap, self.slab):
            s.configure(command=lambda _=None: self.render())

    def _slider(self, parent, label, lo, hi, init):
        ttk.Label(parent, text=label).pack(anchor="w")
        var = tk.DoubleVar(value=init)
        s = ttk.Scale(parent, from_=lo, to=hi, variable=var, orient="horizontal")
        s.pack(fill="x")
        s._var = var
        return s

    def _set_mode(self):
        after = self.view_fr.master.winfo_children()[0]
        if self.mode.get() == "view":
            self.edit_fr.pack_forget()
            self.view_fr.pack(fill="x", pady=4, after=after)
        else:
            self.stop_auto()
            self.view_fr.pack_forget()
            self.edit_fr.pack(fill="x", pady=4, after=after)
            self._update_color_btns()
        self.selected = None
        self.render()

    # -------------------------------------------------------------- params --
    def _params(self):
        maxL = max((t.get("layer", 0) for t in self.tiles), default=0)
        e = self.expl._var.get() / 100.0
        gap = self.gap._var.get() / 100.0 * 0.35
        return {
            "expl": e,
            "spin": math.radians(self.spin._var.get()),
            "spread": self.spread._var.get() / 100.0 * 0.5,
            "gap": gap,
            "slab": self.slab._var.get() / 100.0 * 0.14 + 0.006,
            "zshift": 0.5 * e * maxL * gap,
        }

    def _view_matrix(self):
        R = rot_matrix("x", self.pitch) @ rot_matrix("y", self.yaw)
        if self._auto is not None:
            R = R @ rot_matrix(self.axis.get(), self._auto_angle)
        return R

    # -------------------------------------------------------------- render --
    def render(self):
        if self.mode.get() == "edit":
            self._render_editor()
        else:
            self._render_view()

    def _render_view(self):
        ss = 1 if self._dragging else 2
        img = self.engine.render(self.tiles, self._params(),
                                 self._view_matrix(), self.CW, ss=ss)
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

    def _render_editor(self):
        c = self.canvas
        c.delete("all")
        if self.snap.get():
            n = max(2, self.grid_n.get())
            for k in range(n + 1):
                f = k / n
                sx = self.cx + self.scale * (f - 0.5)
                sy = self.cy - self.scale * (f - 0.5)
                c.create_line(self.cx - self.scale * 0.5, sy,
                              self.cx + self.scale * 0.5, sy, fill="#c9c9c1")
                c.create_line(sx, self.cy - self.scale * 0.5,
                              sx, self.cy + self.scale * 0.5, fill="#c9c9c1")

        order = sorted(range(len(self.tiles)),
                       key=lambda i: self.tiles[i].get("layer", 0))
        for i in order:
            t = self.tiles[i]
            x0 = self.cx + self.scale * (t["x"] - 0.5)
            x1 = self.cx + self.scale * (t["x"] + t["w"] - 0.5)
            y0 = self.cy - self.scale * (t["y"] - 0.5)
            y1 = self.cy - self.scale * (t["y"] + t["h"] - 0.5)
            c.create_rectangle(x0, y0, x1, y1, fill=t["color"], outline="#333")
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            tc = "#ffffff" if t["color"] in (BLACK, BLUE, RED) else "#222222"
            c.create_text(mx, my, text=str(t.get("layer", 0)),
                          fill=tc, font=("Consolas", 12, "bold"))
            if i == self.selected:
                c.create_rectangle(x0, y0, x1, y1, outline="#00e5ff", width=3)

    # --------------------------------------------------------------- mouse --
    def on_press(self, ev):
        if self.mode.get() == "view":
            self._dragging = True
            self._drag = ("rot", ev.x, ev.y, self.yaw, self.pitch)
        else:
            self._drag = ("draw", ev.x, ev.y, ev.x, ev.y)

    def on_motion(self, ev):
        if not self._drag:
            return
        if self._drag[0] == "rot":
            _, x0, y0, yaw0, pit0 = self._drag
            self.yaw = yaw0 + (ev.x - x0) * 0.01
            self.pitch = max(-1.55, min(1.55, pit0 + (ev.y - y0) * 0.01))
            self.render()
        else:
            self._drag = ("draw", self._drag[1], self._drag[2], ev.x, ev.y)
            self.render()
            x0, y0 = self._drag[1], self._drag[2]
            self.canvas.create_rectangle(x0, y0, ev.x, ev.y,
                                         outline="#00e5ff", width=2, dash=(4, 3))

    def on_release(self, ev):
        if self._drag and self._drag[0] == "draw":
            _, x0, y0, _, _ = self._drag
            if abs(ev.x - x0) < 5 and abs(ev.y - y0) < 5:
                self.select_at(ev.x, ev.y)
            else:
                self.create_tile(x0, y0, ev.x, ev.y)
        self._drag = None
        if self._dragging:
            self._dragging = False
            self.render()  # ridisegna in alta qualita' a fine trascinamento

    # ------------------------------------------------------------- editor ---
    def screen_to_norm(self, sx, sy):
        nx = (sx - self.cx) / self.scale + 0.5
        ny = 0.5 - (sy - self.cy) / self.scale
        if self.snap.get():
            n = max(2, self.grid_n.get())
            nx = round(nx * n) / n
            ny = round(ny * n) / n
        return nx, ny

    def create_tile(self, x0, y0, x1, y1):
        ax, ay = self.screen_to_norm(x0, y0)
        bx, by = self.screen_to_norm(x1, y1)
        x, w = min(ax, bx), abs(bx - ax)
        y, h = min(ay, by), abs(by - ay)
        x = max(0.0, min(1.0, x)); y = max(0.0, min(1.0, y))
        w = min(w, 1.0 - x); h = min(h, 1.0 - y)
        if w < 0.01 or h < 0.01:
            return
        self.tiles.append({"x": x, "y": y, "w": w, "h": h,
                           "color": self.cur_color, "layer": int(self.cur_layer.get())})
        self.selected = len(self.tiles) - 1
        self.render()

    def select_at(self, sx, sy):
        nx, ny = self.screen_to_norm(sx, sy)
        best = None
        for i, t in enumerate(self.tiles):
            if t["x"] <= nx <= t["x"] + t["w"] and t["y"] <= ny <= t["y"] + t["h"]:
                if best is None or t.get("layer", 0) >= self.tiles[best].get("layer", 0):
                    best = i
        self.selected = best
        if best is not None:
            self.cur_layer.set(int(self.tiles[best].get("layer", 0)))
            self.set_color(self.tiles[best]["color"])
        self.render()

    def set_color(self, hexv):
        self.cur_color = hexv
        self._update_color_btns()

    def _update_color_btns(self):
        for hexv, b in self.color_btns.items():
            sel = (hexv == self.cur_color)
            b.configure(relief="sunken" if sel else "raised", bd=3 if sel else 1)

    def pick_color(self):
        res = colorchooser.askcolor(color=self.cur_color, title="Scegli un colore")
        if res and res[1]:
            self.set_color(res[1])

    def apply_layer_to_selected(self):
        if self.selected is not None:
            self.tiles[self.selected]["layer"] = int(self.cur_layer.get())
            self.render()

    def delete_selected(self):
        if self.selected is not None:
            del self.tiles[self.selected]
            self.selected = None
            self.render()

    def undo(self):
        if self.tiles:
            self.tiles.pop()
            self.selected = None
            self.render()

    def clear_all(self):
        if messagebox.askyesno("Pulisci", "Eliminare tutte le tessere?"):
            self.tiles = []
            self.selected = None
            self.render()

    # --------------------------------------------------------------- vista --
    def recompose(self):
        self.stop_auto()
        self.yaw = 0.0
        self.pitch = 0.0
        self.expl._var.set(0)
        self.render()

    def reset_view(self):
        self.stop_auto()
        self.yaw = 0.55
        self.pitch = 0.42
        if self.expl._var.get() < 10:
            self.expl._var.set(45)
        self.render()

    def toggle_auto(self):
        if self._auto:
            self.stop_auto()
        else:
            self.auto_btn.configure(text="Ferma rotazione")
            self._auto = True
            self._tick()

    def stop_auto(self):
        if self._auto:
            self.root.after_cancel(self._auto) if isinstance(self._auto, str) else None
            self._auto = None
            self._auto_angle = 0.0
        self.auto_btn.configure(text="Auto-rotazione")

    def _tick(self):
        self._auto_angle += 0.025
        self.render()
        self._auto = self.root.after(30, self._tick)

    # ----------------------------------------------------------- export mp4 -
    def export_dialog(self):
        self.stop_auto()
        win = tk.Toplevel(self.root)
        win.title("Esporta video MP4")
        win.configure(bg="#2b2b2b")
        win.transient(self.root)

        rows = [("Durata (secondi)", "dur", 8.0),
                ("Fotogrammi al secondo", "fps", 30),
                ("Risoluzione (px)", "res", 1080),
                ("Giri completi", "turns", 1.0)]
        vars_ = {}
        for i, (lab, key, val) in enumerate(rows):
            ttk.Label(win, text=lab).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            v = tk.StringVar(value=str(val))
            ttk.Entry(win, textvariable=v, width=10).grid(row=i, column=1, padx=8, pady=4)
            vars_[key] = v

        open_expl = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text="Apri l'esplosione durante il video",
                        variable=open_expl).grid(row=len(rows), column=0, columnspan=2,
                                                 sticky="w", padx=8, pady=4)

        prog = ttk.Progressbar(win, length=260, mode="determinate")
        prog.grid(row=len(rows) + 1, column=0, columnspan=2, padx=8, pady=8)
        status = ttk.Label(win, text="Asse di rotazione: %s" % self.axis.get().upper())
        status.grid(row=len(rows) + 2, column=0, columnspan=2, padx=8)

        def go():
            try:
                dur = float(vars_["dur"].get())
                fps = int(float(vars_["fps"].get()))
                res = int(float(vars_["res"].get()))
                turns = float(vars_["turns"].get())
            except ValueError:
                messagebox.showerror("Errore", "Valori non validi.")
                return
            res -= res % 2  # dimensioni pari per l'encoder
            path = filedialog.asksaveasfilename(
                initialdir=self._default_dir(), defaultextension=".mp4",
                filetypes=[("MP4", "*.mp4")], initialfile="mondrian3d.mp4")
            if not path:
                return
            self._render_mp4(path, dur, fps, res, turns, open_expl.get(),
                             prog, status, win)

        ttk.Button(win, text="Esporta", command=go).grid(
            row=len(rows) + 3, column=0, columnspan=2, pady=8)

    def _render_mp4(self, path, dur, fps, res, turns, open_expl, prog, status, win):
        try:
            import imageio.v2 as imageio
        except ImportError:
            messagebox.showerror("Errore", "Manca imageio.\n"
                                 "python -m pip install imageio imageio-ffmpeg")
            return

        nframes = max(1, int(round(dur * fps)))
        prog["maximum"] = nframes
        axis = self.axis.get()
        base = self._params()
        maxL = max((t.get("layer", 0) for t in self.tiles), default=0)
        Vbase = rot_matrix("x", self.pitch) @ rot_matrix("y", self.yaw)

        def smoothstep(u):
            u = max(0.0, min(1.0, u))
            return u * u * (3 - 2 * u)

        writer = imageio.get_writer(path, fps=fps, quality=8,
                                    macro_block_size=None, codec="libx264")
        try:
            for i in range(nframes):
                t = i / max(1, nframes - 1)
                if open_expl:
                    e = smoothstep(min(1.0, t * 2.0)) * base["expl"]
                else:
                    e = base["expl"]
                prm = dict(base)
                prm["expl"] = e
                prm["zshift"] = 0.5 * e * maxL * base["gap"]
                angle = turns * 2 * math.pi * t
                R = Vbase @ rot_matrix(axis, angle)
                img = self.engine.render(self.tiles, prm, R, res, ss=2)
                writer.append_data(np.asarray(img))
                prog["value"] = i + 1
                status.configure(text="Fotogramma %d / %d" % (i + 1, nframes))
                win.update()
        finally:
            writer.close()
        status.configure(text="Fatto!")
        messagebox.showinfo("Esportato", "Video salvato in:\n%s" % path)

    # ---------------------------------------------------------------- file --
    def _default_dir(self):
        return os.path.dirname(os.path.abspath(__file__))

    def save_json(self):
        path = filedialog.asksaveasfilename(
            initialdir=self._default_dir(), defaultextension=".json",
            filetypes=[("JSON", "*.json")], initialfile="mio_quadro.json")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": os.path.basename(path), "tiles": self.tiles},
                      f, indent=2, ensure_ascii=False)
        messagebox.showinfo("Salvato", "Quadro salvato in:\n%s" % path)

    def load_json(self):
        path = filedialog.askopenfilename(
            initialdir=self._default_dir(), filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.tiles = json.load(f)["tiles"]
            self.selected = None
            self.render()
        except Exception as exc:
            messagebox.showerror("Errore", "Impossibile caricare:\n%s" % exc)

    def load_example(self):
        self.tiles = example_mondrian()["tiles"]
        self.selected = None
        self.render()


def main():
    root = tk.Tk()
    MondrianApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
