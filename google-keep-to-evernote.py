"""
Google Keep to Evernote Converter
----------------------------------

Converts notes from a Google Takeout Keep export into Evernote-compatible .enex files.

Features:
- Converts note content, labels, timestamps, and pinned status
- Converts checklists to Evernote <en-todo> format
- Embeds images inline
- Handles Unicode and emoji properly
- Splits output into multiple .enex files (100 notes each)
- Logs skipped or problematic items to a migration log

Tested with over 5,000 notes and 500MB of export data.

Author: Tal Tabakman (https://github.com/tabakman)
Project: https://github.com/tabakman/google-keep-to-evernote
License: MIT
"""

import os
import sys
import json
import base64
import hashlib
import mimetypes
import html
import shutil
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from math import ceil

# Configuration
SOURCE_DIR = 'keep_source'
OUTPUT_DIR = 'evernote_output'
CHUNK_SIZE = 100
LOG_FILE = os.path.join(OUTPUT_DIR, 'migration_log.txt')

def escape_xml(text):
    return html.escape(text, quote=False)

def format_keep_time(usec):
    try:
        dt = datetime.utcfromtimestamp(int(usec) / 1_000_000)
        return dt.strftime('%Y%m%dT%H%M%SZ')
    except:
        return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

def log_warning(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as log:
        log.write(msg + '\n')

def create_enex_chunks(source_dir, output_dir, chunk_size=100):
    html_files = [f for f in os.listdir(source_dir) if f.endswith('.html')]
    html_files.sort()
    enex_notes = []
    media_count = 0
    pinned_count = 0
    checklist_count = 0

    for filename in html_files:
        base_name = os.path.splitext(filename)[0]
        html_path = os.path.join(source_dir, filename)
        json_path = os.path.join(source_dir, f"{base_name}.json")

        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
        except Exception as e:
            log_warning(f"[ERROR] Failed to parse HTML: {filename} — {e}")
            continue

        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else 'Untitled'

        content_div = soup.find('div', {'class': 'content'})
        if content_div:
            content = content_div
        elif soup.body:
            content = soup.body
        else:
            log_warning(f"[SKIP] No usable content found in {filename}")
            continue

        # Convert Google Keep checklist HTML to Evernote-compatible todos
        for checklist in content.find_all('ul', class_='list'):
            for li in checklist.find_all('li', class_='listitem'):
                bullet = li.find('span', class_='bullet')
                text = li.find('span', class_='text')
                if bullet and text:
                    char = bullet.get_text(strip=True)
                    is_checked = char in ['☑', '✓', '✔']
                    todo = soup.new_tag('en-todo', checked='true' if is_checked else 'false')
                    li.clear()
                    li.append(todo)
                    li.append(' ' + text.get_text(strip=True))
                    checklist_count += 1

        content_html = content.decode_contents()
        media_tags = ''
        resources = ''

        # Process embedded images
        for img in soup.find_all('img'):
            src = img.get('src', '')
            image_data = None
            mime_type = None

            if src.startswith('data:image/'):
                try:
                    header, encoded = src.split(',', 1)
                    mime_type = header.split(';')[0].split(':')[1]
                    image_data = base64.b64decode(encoded)
                except Exception as e:
                    log_warning(f"[WARN] Failed to decode base64 image in {filename}: {e}")
                    continue

            elif os.path.isfile(os.path.join(source_dir, src)):
                try:
                    full_path = os.path.join(source_dir, src)
                    with open(full_path, 'rb') as img_file:
                        image_data = img_file.read()
                    mime_type, _ = mimetypes.guess_type(full_path)
                except Exception as e:
                    log_warning(f"[WARN] Failed to load local image '{src}' in {filename}: {e}")
                    continue

            if image_data and mime_type:
                encoded = base64.b64encode(image_data).decode('utf-8')
                file_ext = mimetypes.guess_extension(mime_type)
                md5_hash = hashlib.md5(image_data).hexdigest()

                original_filename = os.path.basename(src)
                if not original_filename:
                    original_filename = f'image{file_ext or ".bin"}'

                resources += f'''
<resource>
    <data encoding="base64">
    {encoded}
    </data>
    <mime>{mime_type}</mime>
    <resource-attributes>
        <file-name>{escape_xml(original_filename)}</file-name>
    </resource-attributes>
</resource>'''

                media_tags += f'<en-media type="{mime_type}" hash="{md5_hash}"/>\n'
                media_count += 1
                print(f"[IMG] Embedded image '{original_filename}' as {mime_type}")

        # Extract metadata from JSON (tags, timestamps, pinned)
        tags = []
        created_time = updated_time = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as jf:
                    json_data = json.load(jf)
                    if 'labels' in json_data:
                        tags = [label.get('name') for label in json_data['labels'] if 'name' in label]
                    if json_data.get('isPinned'):
                        tags.append('pinned')
                        pinned_count += 1
                    created_time = format_keep_time(json_data.get('createdTimestampUsec', 0))
                    updated_time = format_keep_time(json_data.get('userEditedTimestampUsec', 0))
            except Exception as e:
                log_warning(f"[WARN] Failed to parse JSON for {filename}: {e}")

        tag_elements = ''.join(f'<tag>{escape_xml(tag)}</tag>' for tag in tags)
        full_en_note = f"{content_html}\n{media_tags}"

        note = f'''
<note>
    <title>{escape_xml(title)}</title>
    {tag_elements}
    <content><![CDATA[<en-note>{full_en_note}</en-note>]]></content>
    <created>{created_time}</created>
    <updated>{updated_time}</updated>
    {resources}
</note>'''

        enex_notes.append(note)
        print(f"[INFO] Parsed note: {title.encode('utf-8', errors='replace').decode('utf-8')}")

    # Split into .enex chunks
    total_chunks = ceil(len(enex_notes) / chunk_size)
    for i in range(total_chunks):
        chunk_notes = enex_notes[i * chunk_size:(i + 1) * chunk_size]
        chunk_filename = f'output_{i+1:03}.enex'
        chunk_path = os.path.join(output_dir, chunk_filename)

        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export2.dtd">\n')
            f.write(f'<en-export export-date="{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}" application="KeepToEvernoteScript" version="1.0">\n')
            for note in chunk_notes:
                f.write(note.encode('utf-8', errors='replace').decode('utf-8'))
            f.write('\n</en-export>')

        print(f"[OK] Wrote {chunk_filename} with {len(chunk_notes)} notes")

    # Final summary
    print("\n=== EXPORT SUMMARY ===")
    print(f"📝 Notes exported     : {len(enex_notes)}")
    print(f"📦 ENEX files created : {total_chunks}")
    print(f"🖼️  Images embedded    : {media_count}")
    print(f"☑️  Checkboxes converted: {checklist_count}")
    print(f"📌 Pinned notes        : {pinned_count}")
    print(f"📄 Migration log       : {LOG_FILE if os.path.exists(LOG_FILE) else 'No issues logged.'}")
    print("✅ Done! Your Evernote files are in:", output_dir)

# --- Initial folder checks ---
if not os.path.exists(SOURCE_DIR):
    print(f"[ERROR] Source folder '{SOURCE_DIR}' not found.")
    sys.exit(1)

files = os.listdir(SOURCE_DIR)
if not any(f.endswith(('.html', '.json', '.png', '.jpg', '.jpeg', '.gif')) for f in files):
    print(f"[ERROR] Folder '{SOURCE_DIR}' appears empty or missing Keep data.")
    print("Please place your Google Takeout Keep HTML, JSON, and image files into it (flat structure).")
    sys.exit(1)

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
elif os.listdir(OUTPUT_DIR):
    choice = input(f"[WARN] Output folder '{OUTPUT_DIR}' is not empty. Clear it? [Y/n]: ").strip().lower()
    if choice in ("y", "yes", ""):
        shutil.rmtree(OUTPUT_DIR)
        os.makedirs(OUTPUT_DIR)
        print(f"[OK] Output folder '{OUTPUT_DIR}' cleared.")
    else:
        print(f"[EXIT] Aborted by user.")
        sys.exit(0)

# --- Go ---
create_enex_chunks(SOURCE_DIR, OUTPUT_DIR, CHUNK_SIZE)
