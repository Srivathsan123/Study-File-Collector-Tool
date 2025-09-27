import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import shutil
import os

# -------- Matching helpers --------
def normalize_for_match(s):
    return "".join(ch for ch in s.upper() if ch.isalnum())

def name_matches_study(name, identifiers, strict=False):
    return any(
        sid.upper() in name.upper() if strict else normalize_for_match(sid) in normalize_for_match(name)
        for sid in identifiers
    )

# -------- File operations & filters --------
EXCLUDED_PREFIXES = ("~$",)
EXCLUDED_NAMES = {"desktop.ini", "thumbs.db"}
EXCLUDED_SUFFIXES = (".tmp", ".temp", ".bak")
DEFAULT_EXTS = {
    "doc", "docx", "dotx", "rtf", "pdf", "xls", "xlsx", "xlsm", "xlsb", "csv", "tsv",
    "ppt", "pptx", "potx", "ppsx", "txt", "json", "xml", "yml", "yaml",
    "sas", "sas7bdat", "xpt", "log", "lst", "png", "jpg", "jpeg", "tif", "tiff", "zip", "7z", "rar"
}

def is_excluded_file(filename):
    fname = filename.lower()
    return fname in EXCLUDED_NAMES or any(fname.startswith(pfx) for pfx in EXCLUDED_PREFIXES) or any(fname.endswith(sfx) for sfx in EXCLUDED_SUFFIXES)

def next_available_name(dest_dir, filename):
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem, suffix, i = candidate.stem, candidate.suffix, 1
    while True:
        new_name = f"{stem} ({i}){suffix}"
        candidate = dest_dir / new_name
        if not candidate.exists():
            return candidate
        i += 1

def gather_extensions(exts, allow_all):
    return set() if allow_all else set(e.lower().lstrip(".") for e in exts) or DEFAULT_EXTS

def should_take_file(path, allowed_exts):
    return not is_excluded_file(path.name) and (not allowed_exts or path.suffix.lower().lstrip(".") in allowed_exts)


def collect_files(identifiers, src, dest_root, move, strict, allowed_exts, exclude_dirs, dry_run):
    study_id = identifiers[0]  # Use first identifier (assumed to be Study ID) for folder name
    dest_dir = dest_root / study_id
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
    taken = scanned = skipped = errors = 0
    for root, dirs, files in os.walk(src, topdown=True):
        current = Path(root).resolve()
        dirs[:] = [d for d in dirs if d.lower() not in exclude_dirs]
        if dest_dir.resolve() in current.parents or current == dest_dir.resolve():
            dirs[:] = []
            continue
        for fname in files:
            scanned += 1
            fpath = current / fname
            if not should_take_file(fpath, allowed_exts):
                skipped += 1
                continue
            if not name_matches_study(fpath.stem, identifiers, strict):
                skipped += 1
                continue
            target_path = next_available_name(dest_dir, fpath.name)
            try:
                if not dry_run:
                    shutil.move(str(fpath), str(target_path)) if move else shutil.copy2(str(fpath), str(target_path))
                taken += 1
            except:
                errors += 1
    return scanned, taken, skipped, errors, str(dest_dir)


# -------- GUI --------
def run_scan():
    id_input = entries["Study/Project IDs"].get().strip()
    identifiers = [s.strip() for s in id_input.split(",") if s.strip()]
    source_dir = Path(entries["Source Directory"].get().strip()).resolve()
    dest_dir = Path(entries["Destination Directory"].get().strip()).resolve()
    move = options["Move files (instead of copy)"].get()
    strict = options["Strict matching"].get()
    dry_run = options["Dry run (preview only)"].get()
    allow_all_exts = options["Allow all file extensions"].get()
    exclude_dirs = set(folder.strip().lower() for folder in exclude_entry.get().split(",") if folder.strip())

    if not identifiers or not source_dir or not dest_dir:
        messagebox.showerror("Error", "Please fill in all required fields.")
        return

    allowed_exts = gather_extensions([], allow_all_exts)
    scanned, taken, skipped, errors, final_dest = collect_files(
        identifiers, source_dir, dest_dir, move, strict, allowed_exts, exclude_dirs, dry_run
    )

    messagebox.showinfo("Scan Complete", f"""🎉 Scan finished successfully!
Destination folder: {final_dest}
Scanned: {scanned}
Matched: {taken}
Skipped: {skipped}
Errors: {errors}""")

def browse_directory(entry):
    path = filedialog.askdirectory()
    if path:
        entry.delete(0, tk.END)
        entry.insert(0, path)

def reset_fields():
    for entry in entries.values():
        entry.delete(0, tk.END)
    for var in options.values():
        var.set(False)
    options["Dry run (preview only)"].set(True)
    exclude_entry.delete(0, tk.END)

# Create main window
root = tk.Tk()
root.title("📁 Study File Collector")
root.geometry("540x560")
root.configure(bg="#f0f8ff")

# Title label
title_label = tk.Label(root, text="Study File Collector", font=("Helvetica", 16, "bold"), bg="#f0f8ff", fg="#333")
title_label.pack(pady=(20, 10))

# Entry fields
entry_frame = tk.Frame(root, bg="#f0f8ff")
entry_frame.pack(pady=10, padx=20, fill="x")

fields = ["Study/Project IDs", "Source Directory", "Destination Directory"]
entries = {}

for i, field in enumerate(fields):
    label = tk.Label(entry_frame, text=field + ":", width=20, anchor="w", bg="#f0f8ff")
    label.grid(row=i, column=0, sticky="w", pady=5)

    entry = tk.Entry(entry_frame, width=35)
    entry.grid(row=i, column=1, padx=5, pady=5)

    if field != "Study/Project IDs":
        browse_btn = tk.Button(entry_frame, text="Browse", command=lambda e=entry: browse_directory(e))
        browse_btn.grid(row=i, column=2, padx=5, pady=5)

    entries[field] = entry

# Checkboxes
options_frame = tk.LabelFrame(root, text="Options", bg="#f0f8ff", padx=10, pady=10, font=("Helvetica", 10, "bold"))
options_frame.pack(pady=10, padx=20, fill="x")

options = {
    "Move files (instead of copy)": tk.BooleanVar(),
    "Strict matching": tk.BooleanVar(),
    "Dry run (preview only)": tk.BooleanVar(value=True),
    "Allow all file extensions": tk.BooleanVar()
}

for label, var in options.items():
    cb = tk.Checkbutton(options_frame, text=label, variable=var, bg="#f0f8ff", anchor="w")
    cb.pack(fill="x", padx=10, pady=2)

# Exclude folders entry
exclude_frame = tk.Frame(root, bg="#f0f8ff")
exclude_frame.pack(pady=10, padx=20, fill="x")

exclude_label = tk.Label(exclude_frame, text="Exclude folders (comma-separated):", bg="#f0f8ff", anchor="w")
exclude_label.pack(side="left")

exclude_entry = tk.Entry(exclude_frame, width=35)
exclude_entry.pack(side="left", padx=5)

# Run and Reset buttons
button_frame = tk.Frame(root, bg="#f0f8ff")
button_frame.pack(pady=20)

run_button = tk.Button(button_frame, text="🚀 Run", font=("Helvetica", 12, "bold"), bg="#4CAF50", fg="white", command=run_scan)
run_button.pack(side="left", padx=10)

reset_button = tk.Button(button_frame, text="🔄 Reset", font=("Helvetica", 12, "bold"), bg="#f44336", fg="white", command=reset_fields)
reset_button.pack(side="left", padx=10)

# Start GUI loop
root.mainloop()