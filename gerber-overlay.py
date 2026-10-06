import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def parse_and_blend_gerber(file1_path, file2_path, output_path):
    with open(file1_path, "r", encoding="utf-8", errors="ignore") as f1:
        content1 = f1.read()

    with open(file2_path, "r", encoding="utf-8", errors="ignore") as f2:
        content2 = f2.read()

    # 1. Clean File 1's trailing EOF markers (M02 / M00)
    content1_clean = re.sub(r"M0[02]\*?\s*", "", content1)

    # Ensure Layer 1 explicitly starts with standard Dark Polarity
    if "%LPD*%" not in content1_clean:
        content1_clean = "%LPD*%\n" + content1_clean

    # 2. Extract highest aperture (D-code) from File 1
    d_indices = [int(m) for m in re.findall(r"%ADD(\d+)", content1_clean)]
    offset = max(d_indices) + 1000 if d_indices else 1000

    # 3. Remap ALL D-codes in File 2 (%ADD definitions and D-code calls)
    def remap_add(match):
        return f"%ADD{int(match.group(1)) + offset}"

    def remap_dcode(match):
        return f"D{int(match.group(1)) + offset}*"

    content2_remapped = re.sub(r"%ADD(\d+)", remap_add, content2)
    content2_remapped = re.sub(r"(?<!%AD)D([1-9]\d+)\*", remap_dcode, content2_remapped)

    # 4. Remove commands in File 2 that erase or hide underlying geometry:
    # - %LPC*% (Level Polarity Clear - erases previous layers)
    # - %IP...% (Image Polarity)
    # - %MO...% & %FS...% (Units and format redefinitions)
    content2_remapped = re.sub(r"%LPC\*%?", "", content2_remapped)
    content2_remapped = re.sub(r"%MO[A-Z]+\*%", "", content2_remapped)
    content2_remapped = re.sub(r"%FS[A-Z0-9]+\*%", "", content2_remapped)
    content2_remapped = re.sub(r"%IP[A-Z]+\*%", "", content2_remapped)
    content2_remapped = re.sub(r"M0[02]\*?\s*", "", content2_remapped)

    # 5. Inject an explicit Level Dark directive for Layer 2 without wiping Layer 1
    overlay_header = (
        "\nG04 --- START TRANSPARENT OVERLAY LAYER ---*\n"
        "%LPD*%\n"  # Sets Layer 2 polarity to Dark so features add to Layer 1 rather than mask it
    )

    merged_content = (
        content1_clean.strip()
        + "\n"
        + overlay_header
        + content2_remapped.strip()
        + "\nM02*\n"
    )

    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.write(merged_content)


class GerberMergerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gerber Multi-Layer Overlay Merger")
        self.geometry("600x360")
        self.resizable(False, False)

        style = ttk.Style()
        style.theme_use("clam")

        self.file1_var = tk.StringVar()
        self.file2_var = tk.StringVar()
        self.output_var = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_lbl = ttk.Label(
            main_frame,
            text="Gerber File Overlay & Merger Tool",
            font=("Arial", 14, "bold"),
        )
        title_lbl.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # File 1 Row
        ttk.Label(main_frame, text="Base Gerber (File 1):", font=("Arial", 9, "bold")).grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(main_frame, textvariable=self.file1_var, width=42).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(main_frame, text="Browse...", command=lambda: self.browse_file(self.file1_var)).grid(row=1, column=2, pady=5)

        # File 2 Row
        ttk.Label(main_frame, text="Overlay Gerber (File 2):", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(main_frame, textvariable=self.file2_var, width=42).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(main_frame, text="Browse...", command=lambda: self.browse_file(self.file2_var)).grid(row=2, column=2, pady=5)

        # Output Row
        ttk.Label(main_frame, text="Save Merged As:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(main_frame, textvariable=self.output_var, width=42).grid(row=3, column=1, padx=5, pady=5)
        ttk.Button(main_frame, text="Save To...", command=self.browse_save_file).grid(row=3, column=2, pady=5)

        # Merge Button
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=20)

        merge_btn = ttk.Button(btn_frame, text="Merge Gerber Files", command=self.on_merge)
        merge_btn.pack(side=tk.LEFT, padx=10)

        # Status Bar
        self.status_label = ttk.Label(
            main_frame, text="Select Gerber files to begin.", font=("Arial", 9, "italic"), foreground="gray"
        )
        self.status_label.grid(row=5, column=0, columnspan=3)

    def browse_file(self, target_var):
        filename = filedialog.askopenfilename(
            title="Select Gerber File",
            filetypes=[("Gerber Files", "*.gbr *.pho *.art *.ger *.gtl *.gbl *.gts *.gbs"), ("All Files", "*.*")],
        )
        if filename:
            target_var.set(filename)
            if not self.output_var.get() and self.file1_var.get():
                base_dir = os.path.dirname(self.file1_var.get())
                self.output_var.set(os.path.join(base_dir, "merged_output.gbr"))

    def browse_save_file(self):
        filename = filedialog.asksaveasfilename(
            title="Save Merged Gerber File As",
            defaultextension=".gbr",
            filetypes=[("Gerber File", "*.gbr"), ("All Files", "*.*")],
        )
        if filename:
            self.output_var.set(filename)

    def on_merge(self):
        f1 = self.file1_var.get().strip()
        f2 = self.file2_var.get().strip()
        out = self.output_var.get().strip()

        if not f1 or not os.path.exists(f1) or not f2 or not os.path.exists(f2) or not out:
            messagebox.showerror("Error", "Please provide valid input and output file paths.")
            return

        try:
            parse_and_blend_gerber(f1, f2, out)
            self.status_label.config(
                text=f"Success! Merged file saved to {os.path.basename(out)}", foreground="green"
            )
            messagebox.showinfo(
                "Success", f"Merged file saved to:\n{out}\n\nBoth layers will now be visible together!"
            )
        except Exception as e:
            self.status_label.config(text="Merge failed.", foreground="red")
            messagebox.showerror("Merge Error", f"An error occurred while merging:\n{e}")


if __name__ == "__main__":
    app = GerberMergerApp()
    app.mainloop()
