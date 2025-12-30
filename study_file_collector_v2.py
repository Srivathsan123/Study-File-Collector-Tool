import tkinter as tk

from tkinter import filedialog, messagebox, ttk

from pathlib import Path

import shutil

import os

import json

 

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

    return (

        fname in EXCLUDED_NAMES

        or any(fname.startswith(pfx) for pfx in EXCLUDED_PREFIXES)

        or any(fname.endswith(sfx) for sfx in EXCLUDED_SUFFIXES)

    )

 

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

    # If allow_all is True -> empty set means "allow all" in should_take_file

    return set() if allow_all else set(e.lower().lstrip(".") for e in exts) or DEFAULT_EXTS

 

def should_take_file(path, allowed_exts):

    return not is_excluded_file(path.name) and (not allowed_exts or path.suffix.lower().lstrip(".") in allowed_exts)

 

def resolve_dest_dir(dest_root: Path, study_id: str) -> Path:

    """

    If dest_root already matches the study_id (e.g., user chose .../D9802C00001),

    reuse dest_root itself to avoid creating a nested D9802C00001/D9802C00001.

    If dest_root/study_id exists, reuse it; else create dest_root/study_id.

    """

    root_name = dest_root.name.strip().lower()

    id_name = study_id.strip().lower()

 

    # If the destination directory is already the study folder, reuse it

    if root_name == id_name:

        return dest_root

 

    # Prefer an existing child folder if present

    candidate = dest_root / study_id

    if candidate.exists():

        return candidate

 

    # Otherwise, use dest_root/study_id

    return candidate

 

def collect_files(identifiers, src, dest_root, move, strict, allowed_exts, exclude_dirs, dry_run):

    study_id = identifiers[0]  # Use first identifier (assumed to be Study ID) for folder name

    dest_dir = resolve_dest_dir(dest_root, study_id)

 

    if not dry_run:

        dest_dir.mkdir(parents=True, exist_ok=True)

 

    taken = scanned = skipped = errors = 0

 

    for root, dirs, files in os.walk(src, topdown=True):

        current = Path(root).resolve()

 

        # Respect excluded directories

        dirs[:] = [d for d in dirs if d.lower() not in exclude_dirs]

 

        # Prevent scanning inside destination (avoid self-copy/move)

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

                    if move:

                        shutil.move(str(fpath), str(target_path))

                    else:

                        shutil.copy2(str(fpath), str(target_path))

                taken += 1

            except Exception:

                errors += 1

 

    return scanned, taken, skipped, errors, str(dest_dir)

 

# -------- History (Recents) --------

APP_DIR = Path.home() / ".study_file_collector"

STUDY_HISTORY_PATH = APP_DIR / "study_ids_history.json"

SRC_HISTORY_PATH = APP_DIR / "source_dirs_history.json"

DEST_HISTORY_PATH = APP_DIR / "dest_dirs_history.json"

MAX_HISTORY = 50  # keep last 50 unique items (MRU)

 

def _ensure_app_dir():

    try:

        APP_DIR.mkdir(parents=True, exist_ok=True)

    except Exception:

        pass

 

def load_history_file(path: Path):

    try:

        if path.exists():

            with open(path, "r", encoding="utf-8") as f:

                data = json.load(f)

                if isinstance(data, list):

                    # Only keep strings

                    return [str(s) for s in data if isinstance(s, str)]

    except Exception:

        pass

    return []

 

def save_history_file(path: Path, history_list):

    try:

        _ensure_app_dir()

        with open(path, "w", encoding="utf-8") as f:

            json.dump(history_list[:MAX_HISTORY], f, ensure_ascii=False, indent=2)

    except Exception:

        # Non-fatal; ignore save errors

        pass

 

def update_history_list(path: Path, new_item: str, case_insensitive=True):

    """

    Put new_item at front (MRU), drop duplicates (optionally case-insensitive),

    return updated list.

    """

    item = (new_item or "").strip()

    if not item:

        return load_history_file(path)

    history = load_history_file(path)

    new_history = []

    seen = set()

    # Normalize comparison key

    def key(s): return s.lower() if case_insensitive else s

    for s in [item] + history:

        k = key(s)

        if k not in seen:

            new_history.append(s)

            seen.add(k)

    save_history_file(path, new_history)

    return new_history

 

def update_history_from_ids_input(input_text):

    """

    For Study IDs: split comma-separated text, MRU-order update.

    """

    entered_ids = [s.strip() for s in (input_text or "").split(",") if s.strip()]

    if not entered_ids:

        return load_history_file(STUDY_HISTORY_PATH)

    history = load_history_file(STUDY_HISTORY_PATH)

 

    new_history, seen = [], set()

    for sid in entered_ids + history:

        key = sid.lower()

        if key not in seen:

            new_history.append(sid)

            seen.add(key)

    save_history_file(STUDY_HISTORY_PATH, new_history)

    return new_history

 

def clear_history_file(path: Path):

    try:

        if path.exists():

            path.unlink()

    except Exception:

        pass

 

# -------- GUI --------

def run_scan():

    id_input = study_ids_var.get().strip()

    identifiers = [s.strip() for s in id_input.split(",") if s.strip()]

 

    source_dir_text = source_dir_var.get().strip()

    dest_dir_text = dest_dir_var.get().strip()

 

    if not identifiers or not source_dir_text or not dest_dir_text:

        messagebox.showerror("Error", "Please fill in all required fields.")

        return

 

    source_dir = Path(source_dir_text).resolve()

    dest_dir = Path(dest_dir_text).resolve()

 

    move = options["Move files (instead of copy)"].get()

    strict = options["Strict matching"].get()

    dry_run = options["Dry run (preview only)"].get()

    allow_all_exts = options["Allow all file extensions"].get()

    exclude_dirs = set(folder.strip().lower() for folder in exclude_entry.get().split(",") if folder.strip())

 

    # Update histories (IDs, Source, Destination)

    study_ids_combo["values"] = update_history_from_ids_input(id_input)

    source_dir_combo["values"] = update_history_list(SRC_HISTORY_PATH, source_dir_text)

    dest_dir_combo["values"] = update_history_list(DEST_HISTORY_PATH, dest_dir_text)

 

    allowed_exts = gather_extensions([], allow_all_exts)

    scanned, taken, skipped, errors, final_dest = collect_files(

        identifiers, source_dir, dest_dir, move, strict, allowed_exts, exclude_dirs, dry_run

    )

 

    messagebox.showinfo(

        "Scan Complete",

        f"""🎉 Scan finished successfully!

Destination folder: {final_dest}

Scanned: {scanned}

Matched: {taken}

Skipped: {skipped}

Errors: {errors}"""

    )

 

def browse_directory_for(var: tk.StringVar, combo: ttk.Combobox, history_path: Path):

    path = filedialog.askdirectory()

    if path:

        var.set(path)

        updated = update_history_list(history_path, path)

        combo["values"] = updated

 

def reset_fields():

    # Reset entry fields

    study_ids_var.set("")

    source_dir_var.set("")

    dest_dir_var.set("")

    # Reset options

    for var in options.values():

        var.set(False)

    options["Dry run (preview only)"].set(True)

    exclude_entry.delete(0, tk.END)

 

def clear_history_action_study():

    if messagebox.askyesno("Clear Study ID History", "Remove all saved Study/Project IDs from history?"):

        clear_history_file(STUDY_HISTORY_PATH)

        study_ids_combo["values"] = []

        messagebox.showinfo("History Cleared", "Study ID history has been cleared.")

 

def clear_history_action_src():

    if messagebox.askyesno("Clear Source History", "Remove all saved Source directories from history?"):

        clear_history_file(SRC_HISTORY_PATH)

        source_dir_combo["values"] = []

        messagebox.showinfo("History Cleared", "Source directory history has been cleared.")

 

def clear_history_action_dest():

    if messagebox.askyesno("Clear Destination History", "Remove all saved Destination directories from history?"):

        clear_history_file(DEST_HISTORY_PATH)

        dest_dir_combo["values"] = []

        messagebox.showinfo("History Cleared", "Destination directory history has been cleared.")

 

# Create main window

root = tk.Tk()

root.title("📁 Study File Collector")

# 🔧 Let Tk auto-size to content (removes excess bottom space)

# root.geometry("760x680")  # <-- removed fixed height

 

root.configure(bg="#f0f8ff")

 

# Title label

title_label = tk.Label(root, text="Study File Collector", font=("Helvetica", 16, "bold"), bg="#f0f8ff", fg="#333")

title_label.pack(pady=(16, 8))  # tightened padding

 

# Entry fields container

entry_frame = tk.Frame(root, bg="#f0f8ff")

entry_frame.pack(pady=8, padx=20, fill="x")  # tightened vertical padding

 

# --- Study/Project IDs row (Combobox + Clear History) ---

label_ids = tk.Label(entry_frame, text="Study/Project IDs:", width=22, anchor="w", bg="#f0f8ff")

label_ids.grid(row=0, column=0, sticky="w", pady=5)

 

study_ids_var = tk.StringVar()

study_ids_combo = ttk.Combobox(entry_frame, textvariable=study_ids_var, width=45)

study_ids_combo.grid(row=0, column=1, padx=5, pady=5, sticky="we")

study_ids_combo["values"] = load_history_file(STUDY_HISTORY_PATH)

study_ids_combo.configure(state="normal")  # allow typing

study_ids_combo.set("")

 

ids_btn_frame = tk.Frame(entry_frame, bg="#f0f8ff")

ids_btn_frame.grid(row=0, column=2, padx=5, pady=5, sticky="w")

 

clear_hist_btn = tk.Button(ids_btn_frame, text="Clear History", command=clear_history_action_study)

clear_hist_btn.pack(side="left")

 

# --- Source Directory row (Combobox + Browse + Clear) ---

label_src = tk.Label(entry_frame, text="Source Directory:", width=22, anchor="w", bg="#f0f8ff")

label_src.grid(row=1, column=0, sticky="w", pady=5)

 

source_dir_var = tk.StringVar()

source_dir_combo = ttk.Combobox(entry_frame, textvariable=source_dir_var, width=45)

source_dir_combo.grid(row=1, column=1, padx=5, pady=5, sticky="we")

source_dir_combo["values"] = load_history_file(SRC_HISTORY_PATH)

source_dir_combo.configure(state="normal")

source_dir_combo.set("")

 

src_btn_frame = tk.Frame(entry_frame, bg="#f0f8ff")

src_btn_frame.grid(row=1, column=2, padx=5, pady=5, sticky="w")

 

src_browse_btn = tk.Button(src_btn_frame, text="Browse", command=lambda: browse_directory_for(source_dir_var, source_dir_combo, SRC_HISTORY_PATH))

src_browse_btn.pack(side="left", padx=(0, 5))

 

src_clear_btn = tk.Button(src_btn_frame, text="Clear History", command=clear_history_action_src)

src_clear_btn.pack(side="left")

 

# --- Destination Directory row (Combobox + Browse + Clear) ---

label_dest = tk.Label(entry_frame, text="Destination Directory:", width=22, anchor="w", bg="#f0f8ff")

label_dest.grid(row=2, column=0, sticky="w", pady=5)

 

dest_dir_var = tk.StringVar()

dest_dir_combo = ttk.Combobox(entry_frame, textvariable=dest_dir_var, width=45)

dest_dir_combo.grid(row=2, column=1, padx=5, pady=5, sticky="we")

dest_dir_combo["values"] = load_history_file(DEST_HISTORY_PATH)

dest_dir_combo.configure(state="normal")

dest_dir_combo.set("")

 

dest_btn_frame = tk.Frame(entry_frame, bg="#f0f8ff")

dest_btn_frame.grid(row=2, column=2, padx=5, pady=5, sticky="w")

 

dest_browse_btn = tk.Button(dest_btn_frame, text="Browse", command=lambda: browse_directory_for(dest_dir_var, dest_dir_combo, DEST_HISTORY_PATH))

dest_browse_btn.pack(side="left", padx=(0, 5))

 

dest_clear_btn = tk.Button(dest_btn_frame, text="Clear History", command=clear_history_action_dest)

dest_clear_btn.pack(side="left")

 

# Checkboxes

options_frame = tk.LabelFrame(root, text="Options", bg="#f0f8ff", padx=10, pady=10, font=("Helvetica", 10, "bold"))

options_frame.pack(pady=8, padx=20, fill="x")  # tightened padding

 

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

exclude_frame.pack(pady=8, padx=20, fill="x")  # tightened padding

 

exclude_label = tk.Label(exclude_frame, text="Exclude folders (comma-separated):", bg="#f0f8ff", anchor="w")

exclude_label.pack(side="left")

 

exclude_entry = tk.Entry(exclude_frame, width=45)

exclude_entry.pack(side="left", padx=5)

 

# Run and Reset buttons

button_frame = tk.Frame(root, bg="#f0f8ff")

button_frame.pack(pady=8)  # tightened padding (was larger)

 

run_button = tk.Button(button_frame, text="🚀 Run", font=("Helvetica", 12, "bold"), bg="#4CAF50", fg="white", command=run_scan)

run_button.pack(side="left", padx=10)

 

reset_button = tk.Button(button_frame, text="🔄 Reset", font=("Helvetica", 12, "bold"), bg="#f44336", fg="white", command=reset_fields)

reset_button.pack(side="left", padx=10)

 

# 🔧 After building UI, set window size to the required content size

root.update_idletasks()

root.geometry(f"{root.winfo_reqwidth()}x{root.winfo_reqheight()}")

 

# Start GUI loop

root.mainloop()