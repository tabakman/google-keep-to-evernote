# Google Keep to Evernote Converter 📝➡️🐘

This script converts your **Google Keep archive** into Evernote-compatible `.enex` files — with support for:

- 📅 **Chronological sorting** (oldest notes first, based on JSON timestamps)
- 🖼 Embedded images (inline in note content)
- ☑️ Checklists (converted to Evernote-style todos)
- 📌 Pinned notes (tagged as `pinned`)
- 📁 Archived notes (tagged as `archived`)
- 🏷 Labels → Tags
- 📅 Created/modified timestamps
- 🧾 UTF-8/emoji compatibility
- 📂 Output split into multiple `.enex` files (configurable chunk size)
- 🎯 Command-line interface with flexible options

Tested with:
- 5,000+ notes
- >500MB of HTML, JSON, and images from Google Takeout

---

## 📤 How to Export Your Google Keep Data

1. Go to [Google Takeout](https://takeout.google.com/)
2. Deselect everything, then enable only **Keep**
3. Export and download the `.zip` file
4. Unzip it — inside `Takeout/Keep/` you’ll find:
   - `.html` files (one per note)
   - `.json` files (metadata)
   - any attached images (`.jpg`, `.png`, `.gif`, etc.)

👉 Copy **all of those files (flat)** into the `keep_source/` folder in this repo.

> Requires `beautifulsoup4`.  
> See [Troubleshooting](#%EF%B8%8F-troubleshooting) if you hit an import error.

---

## 🚀 Quick Start

1. **Put your extracted Keep files** (HTML, JSON, and images) into `keep_source/`

2. **Run the converter**:

```bash
# Basic usage (uses default directories)
python google-keep-to-evernote.py

# Or with custom options
python google-keep-to-evernote.py -s my_keep_export -o my_output --size 200
```

It will:

- Ask if you'd like to clear the output folder (or use `--clear-output` to skip the prompt)
- Convert your notes to Evernote `.enex` format
- **Sort notes chronologically** (oldest first in `output_001.enex`)
- Embed images and todos
- Split the result into multiple `output_###.enex` files in `evernote_output/`
- Log skipped notes or failed images to `migration_log.txt`

### Command-Line Options

```bash
python google-keep-to-evernote.py [OPTIONS]

Options:
  -s, --source DIR          Source directory (default: keep_source)
  -o, --output DIR          Output directory (default: evernote_output)
  --size N                  Notes per file (default: 100)
  --no-sort                 Don't sort chronologically
  --clear-output            Clear output folder without prompting
  -h, --help                Show help message
```

**Examples:**

```bash
# Use default settings
python google-keep-to-evernote.py

# Custom directories and 200 notes per file
python google-keep-to-evernote.py -s my_keep -o my_enex --size 200

# Keep original order (don't sort by date)
python google-keep-to-evernote.py --no-sort

# Auto-clear output folder
python google-keep-to-evernote.py --clear-output
```

---

## 📁 Folder Structure

```
.
├── google-keep-to-evernote.py         # ← the main script
├── keep_source/                       # ← your Keep HTML/JSON/image files go here
├── evernote_output/                   # ← final ENEX files + log
```

---

## ✅ Features

| Feature                 | Supported |
|------------------------|-----------|
| Note content           | ✅
| JSON-first timestamps  | ✅
| Chronological sorting  | ✅
| Tags / labels          | ✅
| Checklists             | ✅
| Embedded images        | ✅
| Pinned notes           | ✅ (tagged)
| Archived notes         | ✅ (tagged)
| Migration log          | ✅
| Evernote-ready `.enex` | ✅
| Configurable chunking  | ✅
| Command-line interface | ✅

---

## 🛠️ Troubleshooting

### `ModuleNotFoundError: No module named 'bs4'`

This means the script is missing the BeautifulSoup library.

Fix it by running:

```bash
pip install beautifulsoup4
```

Then run the script again:

```bash
python google-keep-to-evernote.py
```

If you're using a virtual environment, make sure it’s activated before installing.

---

## 👥 Credits

- **Tal Tabakman** ([@tabakman](https://github.com/tabakman)) - Original creator
- **StrayGuru** ([@StrayGuru](https://github.com/StrayGuru)) - Chronological sorting & JSON-first date extraction
- **John Peach** ([@johnpeach](https://github.com/johnpeach)) - Fixed UTF-8 conversion errors

---

## 📄 License

This project is licensed under the MIT License.

Contributions are welcome — feel free to fork, open issues, or submit pull requests to make this better for others migrating their notes.

