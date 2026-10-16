"""Magnetoti — תוכנה ליצירת דפי מגנטים להדפסה (Windows)."""
import os
import sys
import threading
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

import engine as E

APP_NAME = "Magnetoti"
VERSION = "v1.0"
BG = "#f8f9ff"
PRIMARY = "#2d4a73"
IMG_TYPES = [("תמונות", "*.jpg *.jpeg *.png *.bmp *.webp *.tif *.tiff"), ("כל הקבצים", "*.*")]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — מגנטים להדפסה")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        self.configure(bg=BG)
        try:
            self.state("zoomed")  # Windows: מסך מלא
        except tk.TclError:
            pass

        self.items: list[E.Item] = []
        self.page_idx = 0
        self._preview_job = None
        self._photo = None
        self._busy = False

        self._style()
        self._vars()
        self._build_toolbar()
        self._build_body()
        self._build_status()
        self.refresh()

    # ---------------------------------------------------------------- UI setup
    def _style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("vista")
        except tk.TclError:
            st.theme_use("clam")
        st.configure(".", font=("Segoe UI", 10), background=BG)
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG)
        st.configure("TCheckbutton", background=BG)
        st.configure("TLabelframe", background=BG)
        st.configure("TLabelframe.Label", background=BG, font=("Segoe UI", 10, "bold"), foreground=PRIMARY)
        st.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), foreground="white", background=PRIMARY)
        st.map("Primary.TButton", background=[("active", "#3b5f94")])

    def _vars(self):
        self.v_paper = tk.StringVar(value=list(E.PAPER_SIZES_MM)[0])
        self.v_land = tk.BooleanVar(value=False)
        self.v_preset = tk.StringVar(value="7.5×10")
        self.v_mw = tk.DoubleVar(value=7.5)
        self.v_mh = tk.DoubleVar(value=10.0)
        self.v_rot = tk.BooleanVar(value=False)
        self.v_gap = tk.DoubleVar(value=2.0)
        self.v_margin = tk.DoubleVar(value=5.0)
        self.v_frame = tk.StringVar(value=E.FRAMES[0])
        self.v_frame_mm = tk.DoubleVar(value=3.0)
        self.v_round = tk.BooleanVar(value=False)
        self.v_effect = tk.StringVar(value=E.EFFECTS[0])
        self.v_gamma = tk.DoubleVar(value=1.0)
        self.v_cut = tk.BooleanVar(value=True)
        self.v_fit = tk.StringVar(value="fill")
        self.v_quality = tk.StringVar(value="רגיל — 300 DPI")
        for v in (self.v_paper, self.v_land, self.v_mw, self.v_mh, self.v_rot, self.v_gap, self.v_margin,
                  self.v_frame, self.v_frame_mm, self.v_round, self.v_effect, self.v_gamma, self.v_cut, self.v_fit):
            v.trace_add("write", lambda *_: self.schedule_refresh())

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(fill="x")
        ttk.Label(bar, text="MAGNETOTI", font=("Segoe UI", 18, "bold"), foreground=PRIMARY).pack(side="left")
        ttk.Button(bar, text="העלאת תמונות", command=self.add_images).pack(side="right", padx=4)
        ttk.Button(bar, text="נקה הכל", command=self.clear_all).pack(side="right", padx=4)
        ttk.Separator(self, orient="horizontal").pack(fill="x")

    def _build_body(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        # --- פאנל הגדרות (ימין) ---
        right = ttk.Frame(body, padding=10, width=320)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self._build_settings(right)

        # --- רשימת תמונות (שמאל) ---
        left = ttk.Frame(body, padding=8, width=260)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        ttk.Label(left, text="התמונות שלי", font=("Segoe UI", 11, "bold"), foreground=PRIMARY).pack(anchor="e")
        self.lst = tk.Listbox(left, activestyle="none", font=("Segoe UI", 10), exportselection=False,
                              bd=1, relief="solid", highlightthickness=0)
        self.lst.pack(fill="both", expand=True, pady=6)
        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Button(row, text="＋", width=3, command=lambda: self.change_copies(1)).pack(side="left")
        ttk.Button(row, text="－", width=3, command=lambda: self.change_copies(-1)).pack(side="left", padx=2)
        ttk.Button(row, text="הסר", command=self.remove_selected).pack(side="right")
        ttk.Label(left, text="＋/－ משנים כמות עותקים לתמונה", foreground="#777").pack(anchor="e", pady=(4, 0))

        # --- תצוגה מקדימה (אמצע) ---
        mid = ttk.Frame(body, padding=6)
        mid.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(mid, bg="#e7e9f2", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.schedule_refresh())
        nav = ttk.Frame(mid)
        nav.pack(fill="x", pady=(6, 0))
        ttk.Button(nav, text="◀ הבא", command=lambda: self.goto(1)).pack(side="right")
        self.lbl_page = ttk.Label(nav, text="")
        self.lbl_page.pack(side="right", padx=10)
        ttk.Button(nav, text="הקודם ▶", command=lambda: self.goto(-1)).pack(side="right")
        self.lbl_info = ttk.Label(nav, text="", foreground="#555")
        self.lbl_info.pack(side="left")

    def _row(self, parent, label, widget_factory):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text=label).pack(side="right", padx=(6, 0))
        w = widget_factory(f)
        w.pack(side="left", fill="x", expand=True)
        return w

    def _build_settings(self, p):
        ttk.Label(p, text="הגדרות הדפסה", font=("Segoe UI", 13, "bold"), foreground=PRIMARY).pack(anchor="e", pady=(0, 6))

        # מגנט
        g = ttk.LabelFrame(p, text="גודל מגנט (ס״מ)", padding=6)
        g.pack(fill="x", pady=4)
        cb = self._row(g, "גודל", lambda f: ttk.Combobox(f, textvariable=self.v_preset, state="readonly",
                                                          values=list(E.MAGNET_PRESETS_CM), justify="right"))
        cb.bind("<<ComboboxSelected>>", self.on_preset)
        sz = ttk.Frame(g)
        sz.pack(fill="x", pady=2)
        ttk.Label(sz, text="רוחב").pack(side="right")
        ttk.Spinbox(sz, from_=1, to=40, increment=0.5, width=6, textvariable=self.v_mw,
                    command=self.on_custom).pack(side="right", padx=4)
        ttk.Label(sz, text="גובה").pack(side="right", padx=(8, 0))
        ttk.Spinbox(sz, from_=1, to=40, increment=0.5, width=6, textvariable=self.v_mh,
                    command=self.on_custom).pack(side="right", padx=4)
        ttk.Checkbutton(g, text="סיבוב אוטומטי לניצול מקסימלי של הדף", variable=self.v_rot).pack(anchor="e")

        # דף
        g = ttk.LabelFrame(p, text="דף", padding=6)
        g.pack(fill="x", pady=4)
        self._row(g, "גודל נייר", lambda f: ttk.Combobox(f, textvariable=self.v_paper, state="readonly",
                                                          values=list(E.PAPER_SIZES_MM), justify="right"))
        ttk.Checkbutton(g, text="הדפסה לרוחב", variable=self.v_land).pack(anchor="e")
        self._row(g, "שוליים (מ״מ)", lambda f: ttk.Spinbox(f, from_=0, to=30, increment=0.5, width=6, textvariable=self.v_margin))
        self._row(g, "רווח בין מגנטים (מ״מ)", lambda f: ttk.Spinbox(f, from_=0, to=20, increment=0.5, width=6, textvariable=self.v_gap))
        ttk.Checkbutton(g, text="קווי חיתוך", variable=self.v_cut).pack(anchor="e")

        # עיצוב
        g = ttk.LabelFrame(p, text="עיצוב", padding=6)
        g.pack(fill="x", pady=4)
        self._row(g, "מסגרת", lambda f: ttk.Combobox(f, textvariable=self.v_frame, state="readonly",
                                                      values=E.FRAMES, justify="right"))
        self._row(g, "עובי מסגרת (מ״מ)", lambda f: ttk.Spinbox(f, from_=0.5, to=15, increment=0.5, width=6, textvariable=self.v_frame_mm))
        self._row(g, "אפקט", lambda f: ttk.Combobox(f, textvariable=self.v_effect, state="readonly",
                                                     values=E.EFFECTS, justify="right"))
        ttk.Checkbutton(g, text="פינות מעוגלות", variable=self.v_round).pack(anchor="e")
        fit = ttk.Frame(g)
        fit.pack(fill="x")
        ttk.Radiobutton(fit, text="מילוי (חיתוך)", value="fill", variable=self.v_fit).pack(side="right", padx=6)
        ttk.Radiobutton(fit, text="התאמה מלאה", value="fit", variable=self.v_fit).pack(side="right")
        gm = ttk.Frame(g)
        gm.pack(fill="x", pady=(4, 0))
        self.lbl_gamma = ttk.Label(gm, text="1.00", width=5)
        self.lbl_gamma.pack(side="left")
        ttk.Label(gm, text="תיקון Gamma").pack(side="right")
        ttk.Scale(gm, from_=0.5, to=2.0, variable=self.v_gamma, command=self._gamma_changed).pack(side="right", fill="x", expand=True, padx=6)

        # איכות
        g = ttk.LabelFrame(p, text="איכות", padding=6)
        g.pack(fill="x", pady=4)
        self._row(g, "איכות הדפסה", lambda f: ttk.Combobox(f, textvariable=self.v_quality, state="readonly",
                                                            values=list(E.QUALITY_DPI), justify="right"))

        # פעולות
        ttk.Button(p, text="🖨  הדפסה", style="Primary.TButton", command=self.do_print).pack(fill="x", pady=(10, 4), ipady=4)
        ttk.Button(p, text="שמירה כ-PDF", command=self.do_pdf).pack(fill="x", pady=2)
        ttk.Button(p, text="הורדה (JPEG)", command=self.do_jpeg).pack(fill="x", pady=2)

    def _build_status(self):
        bar = ttk.Frame(self, padding=(10, 3))
        bar.pack(fill="x", side="bottom")
        self.status = ttk.Label(bar, text="מוכן", foreground=PRIMARY)
        self.status.pack(side="right")
        ttk.Label(bar, text=f"{APP_NAME} {VERSION}", foreground="#888").pack(side="left")
        self.progress = ttk.Progressbar(bar, length=180, mode="determinate")
        self.progress.pack(side="left", padx=12)

    # ----------------------------------------------------------------- events
    def _gamma_changed(self, _=None):
        self.lbl_gamma.config(text=f"{self.v_gamma.get():.2f}")

    def on_preset(self, _=None):
        val = E.MAGNET_PRESETS_CM.get(self.v_preset.get())
        if val:
            self.v_mw.set(val[0])
            self.v_mh.set(val[1])

    def on_custom(self):
        self.v_preset.set("מותאם אישית")

    def add_images(self):
        paths = filedialog.askopenfilenames(title="בחר תמונות", filetypes=IMG_TYPES)
        for p in paths:
            self.items.append(E.Item(p))
        self.refresh_list()
        self.schedule_refresh()

    def clear_all(self):
        self.items.clear()
        self.page_idx = 0
        self.refresh_list()
        self.schedule_refresh()

    def selected(self):
        sel = self.lst.curselection()
        return sel[0] if sel else None

    def change_copies(self, d):
        i = self.selected()
        if i is None:
            return
        self.items[i].copies = max(1, self.items[i].copies + d)
        self.refresh_list(select=i)
        self.schedule_refresh()

    def remove_selected(self):
        i = self.selected()
        if i is None:
            return
        del self.items[i]
        self.refresh_list()
        self.schedule_refresh()

    def refresh_list(self, select=None):
        self.lst.delete(0, "end")
        for it in self.items:
            self.lst.insert("end", f"{os.path.basename(it.path)}   ×{it.copies}")
        if select is not None and select < len(self.items):
            self.lst.selection_set(select)

    def goto(self, d):
        n = E.page_count(self.items, self.settings())
        if n:
            self.page_idx = max(0, min(n - 1, self.page_idx + d))
            self.schedule_refresh()

    # --------------------------------------------------------------- settings
    def _num(self, var, default):
        try:
            return float(var.get())
        except (tk.TclError, ValueError):
            return default

    def settings(self) -> E.Settings:
        m = max(0.0, self._num(self.v_margin, 5))
        return E.Settings(
            paper_mm=E.PAPER_SIZES_MM.get(self.v_paper.get(), (210, 297)),
            landscape=self.v_land.get(),
            magnet_mm=(max(5, self._num(self.v_mw, 7.5) * 10), max(5, self._num(self.v_mh, 10) * 10)),
            auto_rotate=self.v_rot.get(),
            margin_mm=(m, m, m, m),
            gap_mm=max(0.0, self._num(self.v_gap, 2)),
            frame=self.v_frame.get(),
            frame_mm=max(0.5, self._num(self.v_frame_mm, 3)),
            rounded=self.v_round.get(),
            effect=self.v_effect.get(),
            gamma=self._num(self.v_gamma, 1.0),
            cut_lines=self.v_cut.get(),
            fit_mode=self.v_fit.get(),
            dpi=E.QUALITY_DPI.get(self.v_quality.get(), 300),
        )

    # --------------------------------------------------------------- preview
    def schedule_refresh(self):
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(120, self.refresh)

    def refresh(self):
        self._preview_job = None
        s = self.settings()
        cols, rows, mw, mh, rot = E.grid_for(s)
        n = E.page_count(self.items, s)
        self.page_idx = min(self.page_idx, max(0, n - 1))
        total = sum(i.copies for i in self.items)
        self.lbl_page.config(text=f"דף {self.page_idx + 1} מתוך {max(n, 1)}")
        self.lbl_info.config(text=f"{cols}×{rows} מגנטים בדף  |  סה״כ {total} מגנטים  |  {n} דפים")

        self.canvas.delete("all")
        cw, ch = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        pw, ph = s.paper_mm[::-1] if s.landscape else s.paper_mm
        scale = min((cw - 30) / pw, (ch - 30) / ph)
        preview_dpi = max(40, min(150, int(scale * E.MM_PER_INCH)))
        try:
            if self.items and cols * rows > 0:
                page = E.render_page(self.items, s, self.page_idx, preview_dpi)
            else:
                page = Image.new("RGB", (E.mm_to_px(pw, preview_dpi), E.mm_to_px(ph, preview_dpi)), "white")
        except Exception as ex:  # קובץ פגום וכד'
            self.status.config(text=f"שגיאה בתצוגה: {ex}")
            return
        w, h = int(pw * scale), int(ph * scale)
        page = page.resize((w, h), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(page)
        x, y = (cw - w) // 2, (ch - h) // 2
        self.canvas.create_rectangle(x + 4, y + 4, x + w + 4, y + h + 4, fill="#c7cad8", outline="")
        self.canvas.create_image(x, y, anchor="nw", image=self._photo)
        if not self.items:
            self.canvas.create_text(cw // 2, ch // 2, text="לחצו על ״העלאת תמונות״ כדי להתחיל",
                                    font=("Segoe UI", 15), fill="#8890a8")
        if cols * rows <= 0:
            self.status.config(text="המגנט גדול מדי עבור הדף")
        else:
            self.status.config(text="מוכן")

    # ---------------------------------------------------------------- output
    def _need_items(self):
        s = self.settings()
        if not self.items:
            messagebox.showinfo(APP_NAME, "לא הועלו תמונות.")
            return None
        if E.page_count(self.items, s) == 0:
            messagebox.showwarning(APP_NAME, "המגנט גדול מדי עבור גודל הדף שנבחר.")
            return None
        return s

    def _run_bg(self, work, done):
        if self._busy:
            return
        self._busy = True
        self.progress["value"] = 0

        def prog(i, n):
            self.after(0, lambda: self.progress.configure(value=100 * i / n))

        def target():
            try:
                res = work(prog)
                self.after(0, lambda: self._finish(done, res, None))
            except Exception as ex:
                self.after(0, lambda: self._finish(done, None, ex))

        self.status.config(text="מעבד…")
        threading.Thread(target=target, daemon=True).start()

    def _finish(self, done, res, err):
        self._busy = False
        self.progress["value"] = 0
        self.status.config(text="מוכן")
        if err:
            messagebox.showerror(APP_NAME, f"אירעה שגיאה:\n{err}")
        else:
            done(res)

    def do_pdf(self):
        s = self._need_items()
        if not s:
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialfile="magnets.pdf")
        if not path:
            return
        self._run_bg(lambda prog: E.save_pdf(self.items, s, path, prog) or path,
                     lambda p: self._opened(p, "ה-PDF נשמר בהצלחה."))

    def do_jpeg(self):
        s = self._need_items()
        if not s:
            return
        path = filedialog.asksaveasfilename(defaultextension=".jpg", filetypes=[("JPEG", "*.jpg")], initialfile="magnets.jpg")
        if not path:
            return
        self._run_bg(lambda prog: E.save_jpegs(self.items, s, path, prog),
                     lambda ps: messagebox.showinfo(APP_NAME, f"נשמרו {len(ps)} קבצים."))

    def do_print(self):
        s = self._need_items()
        if not s:
            return
        tmp = os.path.join(tempfile.gettempdir(), "magnetoti_print.pdf")

        def done(p):
            try:
                if sys.platform == "win32":
                    os.startfile(p, "print")  # שולח להדפסה בעזרת הקורא הרשום ל-PDF
                else:
                    os.startfile(p) if hasattr(os, "startfile") else None
            except OSError:
                if sys.platform == "win32":
                    os.startfile(p)  # אם אין קורא עם פעולת הדפסה - פותח את הקובץ
        self._run_bg(lambda prog: E.save_pdf(self.items, s, tmp, prog) or tmp, done)

    def _opened(self, path, msg):
        if messagebox.askyesno(APP_NAME, msg + "\nלפתוח את הקובץ?"):
            try:
                os.startfile(path)
            except (AttributeError, OSError):
                pass


if __name__ == "__main__":
    try:  # חדות במסכים עם הגדלת DPI
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()
