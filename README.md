# Google Keep to Evernote Converter 📝➡️🐘

This script converts your **Google Keep archive** into Evernote-compatible `.enex` files — with support for:

- 🖼 Embedded images (inline in note content)
- ☑️ Checklists (converted to Evernote-style todos)
- 📌 Pinned notes (tagged as `pinned`)
- 🏷 Labels → Tags
- 📅 Created/modified timestamps
- 🧾 UTF-8/emoji compatibility
- 📂 Output split into multiple `.enex` files (chunks of 100 notes)

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
> See [Troubleshooting](#troubleshooting) if you hit an import error.

---

## 🚀 Quick Start

1. **Put your extracted Keep files** (HTML, JSON, and images) into `keep_source/`

2. **Run the converter**:

```bash
python google-keep-to-evernote.py
```

It will:

- Ask if you'd like to clear the output folder
- Convert your notes to Evernote `.enex` format
- Embed images and todos
- Split the result into multiple `output_###.enex` files in `evernote_output/`
- Log skipped notes or failed images to `migration_log.txt`

---

## 📁 Folder Structure

```
.
├── google-keep-to-evernote.py         # ← the script
├── keep_source/            # ← your Keep HTML/JSON/image files go here
├── evernote_output/        # ← final ENEX files + log
```

---

## ✅ Features

| Feature                 | Supported |
|------------------------|-----------|
| Note content           | ✅
| Timestamps             | ✅
| Tags / labels          | ✅
| Checklists             | ✅
| Embedded images        | ✅
| Pinned notes           | ✅ (tagged)
| Migration log          | ✅
| Evernote-ready `.enex` | ✅
| Chunked output         | ✅ (100 notes per file)

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

## 📄 License

This project is licensed under the MIT License.

Contributions are welcome — feel free to fork, open issues, or submit pull requests to make this better for others migrating their notes.

