#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Keep to Evernote Converter
----------------------------------

Converts notes from a Google Takeout Keep export into Evernote-compatible .enex files.

Features:
- JSON-first timestamp extraction (accurate created/updated dates)
- Chronological sorting (oldest notes first in part01)
- Converts note content, labels, timestamps, and pinned/archived status
- Converts checklists to Evernote <en-todo> format
- Embeds images inline (base64 and file references)
- Handles Unicode and emoji properly
- Splits output into multiple .enex files (configurable notes per file)
- Comprehensive logging and error handling
- Command-line interface with sensible defaults

Author: Tal Tabakman (https://github.com/tabakman)
Contributors: StrayGuru (https://github.com/StrayGuru) - chronological sorting & JSON-first dates
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
import argparse
import unicodedata
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from math import ceil

# Default Configuration
DEFAULT_SOURCE_DIR = 'keep_source'
DEFAULT_OUTPUT_DIR = 'evernote_output'
DEFAULT_CHUNK_SIZE = 100

def escape_xml(text):
    """XML-escape text with proper Unicode normalization."""
    if text is None:
        return ""
    # Decode HTML entities and normalize Unicode to NFC
    text = html.unescape(str(text))
    text = unicodedata.normalize("NFC", text)
    return html.escape(text, quote=False)

def format_timestamp(epoch_seconds):
    """Convert epoch seconds to Evernote timestamp format."""
    try:
        dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
        return dt.strftime('%Y%m%dT%H%M%SZ')
    except:
        return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

def get_timestamps_from_json(json_path):
    """
    Extract timestamps and metadata from JSON file.
    Returns (created_epoch, updated_epoch, is_pinned, is_archived, labels)
    """
    created = updated = None
    is_pinned = False
    is_archived = False
    labels = []
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                
            # Extract created timestamp
            usec_c = data.get("createdTimestampUsec")
            if isinstance(usec_c, str) and usec_c.isdigit():
                usec_c = int(usec_c)
            if isinstance(usec_c, (int, float)):
                created = int(usec_c // 1_000_000)
            
            # Extract updated timestamp
            usec_u = data.get("userEditedTimestampUsec")
            if isinstance(usec_u, str) and usec_u.isdigit():
                usec_u = int(usec_u)
            if isinstance(usec_u, (int, float)):
                updated = int(usec_u // 1_000_000)
            
            # Extract metadata
            is_pinned = bool(data.get("isPinned", False))
            is_archived = bool(data.get("isArchived", False))
            
            # Extract labels
            if 'labels' in data:
                labels = [label.get('name') for label in data['labels'] if 'name' in label]
                
        except Exception as e:
            print(f"[WARN] Failed to parse JSON {json_path}: {e}")
    
    # Fallback to file modification time
    if created is None:
        try:
            created = int(os.path.getmtime(json_path.replace('.json', '.html')))
        except:
            created = int(datetime.now(timezone.utc).timestamp())
    
    if updated is None:
        updated = created
    
    return created, updated, is_pinned, is_archived, labels

def log_warning(log_file, msg):
    """Write warning message to log file."""
    with open(log_file, 'a', encoding='utf-8') as log:
        log.write(msg + '\n')

def process_note(html_path, source_dir, log_file):
    """
    Process a single note and return (note_xml, created_epoch, stats_dict).
    Returns None if the note cannot be processed.
    """
    base_name = os.path.splitext(os.path.basename(html_path))[0]
    json_path = os.path.join(source_dir, f"{base_name}.json")
    
    # Get metadata from JSON
    created_epoch, updated_epoch, is_pinned, is_archived, json_labels = get_timestamps_from_json(json_path)
    
    # Parse HTML
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
    except Exception as e:
        log_warning(log_file, f"[ERROR] Failed to parse HTML: {html_path} — {e}")
        return None
    
    # Extract title
    title_tag = soup.find('title')
    title = title_tag.text.strip() if title_tag else 'Untitled'
    title = escape_xml(title)
    
    # Extract content
    content_div = soup.find('div', {'class': 'content'})
    if content_div:
        content = content_div
    elif soup.body:
        content = soup.body
    else:
        log_warning(log_file, f"[SKIP] No usable content found in {html_path}")
        return None
    
    # Statistics
    stats = {
        'media_count': 0,
        'checklist_count': 0
    }
    
    # Convert checklists to Evernote format
    for checklist in content.find_all('ul', class_='list'):
        for li in checklist.find_all('li', class_='listitem'):
            bullet = li.find('span', class_='bullet')
            text = li.find('span', class_='text')
            if bullet and text:
                char = bullet.get_text(strip=True)
                # Check for various checkbox characters
                is_checked = char in ['☑', '✓', '✔', '&#9745;']
                todo = soup.new_tag('en-todo', checked='true' if is_checked else 'false')
                li.clear()
                li.append(todo)
                li.append(' ' + text.get_text(strip=True))
                stats['checklist_count'] += 1
    
    content_html = content.decode_contents()
    
    # Process images
    media_tags = ''
    resources = ''
    
    for img in soup.find_all('img'):
        src = img.get('src', '')
        image_data = None
        mime_type = None
        
        # Handle base64 embedded images
        if src.startswith('data:image/'):
            try:
                header, encoded = src.split(',', 1)
                mime_type = header.split(';')[0].split(':')[1]
                image_data = base64.b64decode(encoded)
            except Exception as e:
                log_warning(log_file, f"[WARN] Failed to decode base64 image in {html_path}: {e}")
                continue
        
        # Handle file reference images
        elif os.path.isfile(os.path.join(source_dir, src)):
            try:
                full_path = os.path.join(source_dir, src)
                with open(full_path, 'rb') as img_file:
                    image_data = img_file.read()
                mime_type, _ = mimetypes.guess_type(full_path)
            except Exception as e:
                log_warning(log_file, f"[WARN] Failed to load local image '{src}' in {html_path}: {e}")
                continue
        
        if image_data and mime_type:
            encoded = base64.b64encode(image_data).decode('utf-8')
            file_ext = mimetypes.guess_extension(mime_type)
            md5_hash = hashlib.md5(image_data).hexdigest()
            
            original_filename = os.path.basename(src)
            if not original_filename or original_filename.startswith('data:'):
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
            stats['media_count'] += 1
    
    # Normalize content
    content_html = html.unescape(content_html)
    content_html = unicodedata.normalize("NFC", content_html)
    
    # Build tags
    tags = json_labels.copy()
    if is_pinned:
        tags.append('pinned')
    if is_archived:
        tags.append('archived')
    
    tag_elements = ''.join(f'<tag>{escape_xml(tag)}</tag>' for tag in tags)
    
    # Format timestamps
    created_time = format_timestamp(created_epoch)
    updated_time = format_timestamp(updated_epoch)
    
    # Build complete note XML
    full_en_note = f"{content_html}\n{media_tags}"
    
    note_xml = f'''
<note>
    <title>{title}</title>
    {tag_elements}
    <content><![CDATA[<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd"><en-note>{full_en_note}</en-note>]]></content>
    <created>{created_time}</created>
    <updated>{updated_time}</updated>
    <note-attributes>
        <source>google-keep</source>
    </note-attributes>
    {resources}
</note>'''
    
    return note_xml, created_epoch, stats

def create_enex_chunks(source_dir, output_dir, chunk_size=100, sort_chronological=True):
    """
    Main processing function: converts Keep notes to ENEX format.
    """
    log_file = os.path.join(output_dir, 'migration_log.txt')
    
    # Find all HTML files
    html_files = [f for f in os.listdir(source_dir) if f.endswith('.html')]
    
    if not html_files:
        print(f"[ERROR] No HTML files found in {source_dir}")
        return
    
    print(f"[INFO] Found {len(html_files)} HTML files to process")
    
    # Process all notes
    notes_data = []  # (note_xml, created_epoch, stats)
    total_stats = {
        'media_count': 0,
        'checklist_count': 0,
        'pinned_count': 0,
        'archived_count': 0
    }
    
    for filename in html_files:
        html_path = os.path.join(source_dir, filename)
        result = process_note(html_path, source_dir, log_file)
        
        if result:
            note_xml, created_epoch, stats = result
            notes_data.append((note_xml, created_epoch))
            
            total_stats['media_count'] += stats['media_count']
            total_stats['checklist_count'] += stats['checklist_count']
            
            # Count pinned/archived from tags
            if 'pinned' in note_xml:
                total_stats['pinned_count'] += 1
            if 'archived' in note_xml:
                total_stats['archived_count'] += 1
            
            print(f"[INFO] Processed: {filename}")
    
    if not notes_data:
        print("[ERROR] No notes were successfully processed")
        return
    
    # Sort by creation date (oldest first) if requested
    if sort_chronological:
        notes_data.sort(key=lambda x: x[1])
        print(f"[INFO] Sorted {len(notes_data)} notes chronologically (oldest first)")
    
    # Extract just the XML (no longer need timestamps)
    enex_notes = [note_xml for note_xml, _ in notes_data]
    
    # Split into chunks
    total_chunks = ceil(len(enex_notes) / chunk_size)
    export_date = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    
    for i in range(total_chunks):
        chunk_notes = enex_notes[i * chunk_size:(i + 1) * chunk_size]
        chunk_filename = f'output_{i+1:03}.enex'
        chunk_path = os.path.join(output_dir, chunk_filename)
        
        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export2.dtd">\n')
            f.write(f'<en-export export-date="{export_date}" application="KeepToEvernoteScript" version="2.0">\n')
            for note in chunk_notes:
                f.write(note)
            f.write('\n</en-export>')
        
        print(f"[OK] Wrote {chunk_filename} with {len(chunk_notes)} notes")
    
    # Print summary
    print("\n=== EXPORT SUMMARY ===")
    print(f"📝 Notes exported     : {len(enex_notes)}")
    print(f"📦 ENEX files created : {total_chunks}")
    print(f"🖼️  Images embedded    : {total_stats['media_count']}")
    print(f"☑️  Checkboxes converted: {total_stats['checklist_count']}")
    print(f"📌 Pinned notes       : {total_stats['pinned_count']}")
    print(f"📁 Archived notes     : {total_stats['archived_count']}")
    if sort_chronological:
        print(f"📅 Sorting            : Chronological (oldest→newest)")
    if os.path.exists(log_file):
        print(f"📄 Migration log      : {log_file}")
    print(f"✅ Done! Your Evernote files are in: {output_dir}")

def main():
    parser = argparse.ArgumentParser(
        description="Convert Google Keep notes to Evernote .enex format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Use default directories
  %(prog)s -s my_keep_export        # Custom source directory
  %(prog)s -o my_output --size 200  # Custom output and chunk size
  %(prog)s --no-sort                # Don't sort chronologically
        """
    )
    
    parser.add_argument('-s', '--source',
                        default=DEFAULT_SOURCE_DIR,
                        help=f'Source directory with Keep HTML/JSON files (default: {DEFAULT_SOURCE_DIR})')
    
    parser.add_argument('-o', '--output',
                        default=DEFAULT_OUTPUT_DIR,
                        help=f'Output directory for ENEX files (default: {DEFAULT_OUTPUT_DIR})')
    
    parser.add_argument('--size', '--chunk-size',
                        type=int,
                        default=DEFAULT_CHUNK_SIZE,
                        dest='chunk_size',
                        help=f'Number of notes per ENEX file (default: {DEFAULT_CHUNK_SIZE})')
    
    parser.add_argument('--no-sort',
                        action='store_false',
                        dest='sort_chronological',
                        help='Do not sort notes chronologically (keep original order)')
    
    parser.add_argument('--clear-output',
                        action='store_true',
                        help='Clear output directory without prompting')
    
    args = parser.parse_args()
    
    source_dir = args.source
    output_dir = args.output
    chunk_size = args.chunk_size
    
    # Validate source directory
    if not os.path.exists(source_dir):
        print(f"[ERROR] Source folder '{source_dir}' not found.")
        print(f"Please create it and place your Google Takeout Keep files inside.")
        sys.exit(1)
    
    files = os.listdir(source_dir)
    if not any(f.endswith(('.html', '.json', '.png', '.jpg', '.jpeg', '.gif')) for f in files):
        print(f"[ERROR] Folder '{source_dir}' appears empty or missing Keep data.")
        print("Please place your Google Takeout Keep HTML, JSON, and image files into it.")
        sys.exit(1)
    
    # Handle output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"[OK] Created output folder: {output_dir}")
    elif os.listdir(output_dir):
        if args.clear_output:
            shutil.rmtree(output_dir)
            os.makedirs(output_dir)
            print(f"[OK] Cleared output folder: {output_dir}")
        else:
            choice = input(f"[WARN] Output folder '{output_dir}' is not empty. Clear it? [Y/n]: ").strip().lower()
            if choice in ("y", "yes", ""):
                shutil.rmtree(output_dir)
                os.makedirs(output_dir)
                print(f"[OK] Output folder '{output_dir}' cleared.")
            else:
                print(f"[EXIT] Aborted by user.")
                sys.exit(0)
    
    # Process notes
    create_enex_chunks(source_dir, output_dir, chunk_size, args.sort_chronological)

if __name__ == '__main__':
    main()
