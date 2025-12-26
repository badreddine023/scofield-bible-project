"""
SCOFIELD BIBLE PARSER & WEB APPLICATION
A complete implementation for parsing, structuring, and presenting the 1917 Scofield Reference Bible
"""

import json
import re
import sqlite3
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import zipfile
import io

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class BibleVerse:
    """Represents a single Bible verse with KJV text"""
    book: str
    chapter: int
    verse: int
    text: str
    note_ids: List[str] = None
    
    def __post_init__(self):
        if self.note_ids is None:
            self.note_ids = []
    
    @property
    def verse_id(self) -> str:
        return f"{self.book}.{self.chapter}.{self.verse}"
    
    @property
    def reference(self) -> str:
        return f"{self.book} {self.chapter}:{self.verse}"

@dataclass
class ScofieldNote:
    """Represents a Scofield study note"""
    note_id: str
    text: str
    linked_verses: List[str]  # List of verse_ids
    category: str = ""
    subcategory: str = ""
    
    @property
    def first_verse(self) -> str:
        return self.linked_verses[0] if self.linked_verses else ""

@dataclass
class CrossReference:
    """Represents a cross-reference relationship"""
    source_id: str  # verse_id or note_id
    target_id: str  # verse_id or note_id
    ref_type: str   # "parallel", "fulfillment", "explanation", "thematic"
    description: str = ""

@dataclass
class ThematicIndex:
    """Index of theological themes and doctrines"""
    theme: str
    description: str
    note_ids: List[str]
    verse_ids: List[str]
    related_themes: List[str]

# ============================================================================
# PARSER ENGINE
# ============================================================================

class ScofieldParser:
    """Parses raw KJV and Scofield notes into structured data"""
    
    # Bible book abbreviations mapping
    BOOK_ABBREV = {
        'GEN': 'Genesis', 'EXO': 'Exodus', 'LEV': 'Leviticus', 'NUM': 'Numbers',
        'DEU': 'Deuteronomy', 'JOS': 'Joshua', 'JDG': 'Judges', 'RUT': 'Ruth',
        '1SA': '1 Samuel', '2SA': '2 Samuel', '1KI': '1 Kings', '2KI': '2 Kings',
        '1CH': '1 Chronicles', '2CH': '2 Chronicles', 'EZR': 'Ezra', 'NEH': 'Nehemiah',
        'EST': 'Esther', 'JOB': 'Job', 'PSA': 'Psalms', 'PRO': 'Proverbs',
        'ECC': 'Ecclesiastes', 'SON': 'Song of Solomon', 'ISA': 'Isaiah', 'JER': 'Jeremiah',
        'LAM': 'Lamentations', 'EZE': 'Ezekiel', 'DAN': 'Daniel', 'HOS': 'Hosea',
        'JOE': 'Joel', 'AMO': 'Amos', 'OBA': 'Obadiah', 'JON': 'Jonah',
        'MIC': 'Micah', 'NAH': 'Nahum', 'HAB': 'Habakkuk', 'ZEP': 'Zephaniah',
        'HAG': 'Haggai', 'ZEC': 'Zechariah', 'MAL': 'Malachi', 'MAT': 'Matthew',
        'MAR': 'Mark', 'LUK': 'Luke', 'JOH': 'John', 'ACT': 'Acts',
        'ROM': 'Romans', '1CO': '1 Corinthians', '2CO': '2 Corinthians', 'GAL': 'Galatians',
        'EPH': 'Ephesians', 'PHI': 'Philippians', 'COL': 'Colossians', '1TH': '1 Thessalonians',
        '2TH': '2 Thessalonians', '1TI': '1 Timothy', '2TI': '2 Timothy', 'TIT': 'Titus',
        'PHM': 'Philemon', 'HEB': 'Hebrews', 'JAM': 'James', '1PE': '1 Peter',
        '2PE': '2 Peter', '1JO': '1 John', '2JO': '2 John', '3JO': '3 John',
        'JUD': 'Jude', 'REV': 'Revelation'
    }
    
    # Common theological themes in Scofield
    THEMES = [
        "Dispensation", "Covenant", "Grace", "Law", "Prophecy",
        "Kingdom", "Church", "Israel", "Gentiles", "Salvation",
        "Atonement", "Justification", "Sanctification", "Eschatology",
        "Second Coming", "Millennium", "Judgment", "Heaven", "Hell"
    ]
    
    def __init__(self):
        self.verses: Dict[str, BibleVerse] = {}
        self.notes: Dict[str, ScofieldNote] = {}
        self.cross_refs: List[CrossReference] = []
        self.thematic_index: Dict[str, ThematicIndex] = {}
        self.current_note_id = 1
        
    def parse_kjv_text(self, kjv_file_path: str) -> None:
        """Parse KJV Bible text from a structured file"""
        print(f"Parsing KJV text from {kjv_file_path}...")
        
        # Sample parser - adapt to your actual file format
        with open(kjv_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                # Example format: GEN\t1\t1\tIn the beginning...
                parts = line.split('\t')
                if len(parts) >= 4:
                    book_abbrev = parts[0].upper()
                    if book_abbrev not in self.BOOK_ABBREV:
                        continue
                        
                    try:
                        chapter = int(parts[1])
                        verse = int(parts[2])
                        text = '\t'.join(parts[3:])
                        
                        verse_obj = BibleVerse(
                            book=book_abbrev,
                            chapter=chapter,
                            verse=verse,
                            text=text
                        )
                        self.verses[verse_obj.verse_id] = verse_obj
                    except ValueError:
                        continue
        
        print(f"Loaded {len(self.verses)} verses")
    
    def parse_scofield_notes(self, notes_file_path: str) -> None:
        """Parse Scofield notes from a structured file"""
        print(f"Parsing Scofield notes from {notes_file_path}...")
        
        # This is a simplified parser - you'll need to adapt to your actual notes format
        with open(notes_file_path, 'r', encoding='utf-8') as f:
            current_note_text = []
            current_linked_verses = []
            
            for line in f:
                line = line.strip()
                
                # Look for note markers (adapt based on your format)
                if line.startswith('NOTE:'):
                    # Save previous note if exists
                    if current_note_text and current_linked_verses:
                        self._create_note(current_note_text, current_linked_verses)
                    
                    # Start new note
                    current_note_text = [line[5:].strip()]  # Remove 'NOTE:'
                    current_linked_verses = self._extract_verse_refs(line)
                
                elif line.startswith('REF:'):
                    # Extract cross-references
                    refs = self._extract_cross_refs(line)
                    for ref in refs:
                        self.cross_refs.append(ref)
                
                elif current_note_text:
                    # Continue accumulating note text
                    current_note_text.append(line)
        
        # Save the last note
        if current_note_text and current_linked_verses:
            self._create_note(current_note_text, current_linked_verses)
        
        print(f"Loaded {len(self.notes)} Scofield notes")
        print(f"Loaded {len(self.cross_refs)} cross-references")
    
    def _create_note(self, note_lines: List[str], linked_verses: List[str]) -> None:
        """Create a ScofieldNote object"""
        note_id = f"N{self.current_note_id:04d}"
        note_text = ' '.join(note_lines)
        
        # Extract category from first few words (simplified)
        category = ""
        first_words = note_text[:50].lower()
        for theme in self.THEMES:
            if theme.lower() in first_words:
                category = theme
                break
        
        note = ScofieldNote(
            note_id=note_id,
            text=note_text,
            linked_verses=linked_verses,
            category=category
        )
        
        self.notes[note_id] = note
        
        # Link note to verses
        for verse_id in linked_verses:
            if verse_id in self.verses:
                self.verses[verse_id].note_ids.append(note_id)
        
        self.current_note_id += 1
    
    def _extract_verse_refs(self, text: str) -> List[str]:
        """Extract verse references from text (e.g., 'Gen 1:1')"""
        # Simplified pattern - enhance as needed
        pattern = r'([1-3]?\s?[A-Z][a-z]+)\s+(\d+):(\d+)'
        matches = re.findall(pattern, text)
        
        verse_ids = []
        for book_name, chapter, verse in matches:
            # Convert full name to abbreviation
            book_abbrev = self._book_name_to_abbrev(book_name)
            if book_abbrev:
                verse_ids.append(f"{book_abbrev}.{chapter}.{verse}")
        
        return verse_ids
    
    def _extract_cross_refs(self, text: str) -> List[CrossReference]:
        """Extract cross-references from text"""
        refs = []
        # Example: "See John 1:1" or "cf. Genesis 3:15"
        pattern = r'(See|cf\.|compare)\s+([1-3]?\s?[A-Z][a-z]+)\s+(\d+):(\d+)'
        matches = re.findall(pattern, text)
        
        for _, book_name, chapter, verse in matches:
            book_abbrev = self._book_name_to_abbrev(book_name)
            if book_abbrev:
                target_id = f"{book_abbrev}.{chapter}.{verse}"
                # Simplified: assume cross-ref from current note to target verse
                refs.append(CrossReference(
                    source_id=f"N{self.current_note_id:04d}",
                    target_id=target_id,
                    ref_type="reference",
                    description="Cross-reference"
                ))
        
        return refs
    
    def _book_name_to_abbrev(self, book_name: str) -> Optional[str]:
        """Convert full book name to abbreviation"""
        book_name = book_name.strip().title()
        for abbrev, full_name in self.BOOK_ABBREV.items():
            if full_name.lower() == book_name.lower():
                return abbrev
        return None
    
    def build_thematic_index(self) -> None:
        """Build index of theological themes"""
        print("Building thematic index...")
        
        for theme in self.THEMES:
            note_ids = []
            verse_ids = []
            
            # Find notes containing theme
            for note_id, note in self.notes.items():
                if theme.lower() in note.text.lower():
                    note_ids.append(note_id)
                    verse_ids.extend(note.linked_verses)
            
            # Find verses containing theme
            for verse_id, verse in self.verses.items():
                if theme.lower() in verse.text.lower():
                    verse_ids.append(verse_id)
            
            # Remove duplicates
            verse_ids = list(set(verse_ids))
            
            if note_ids or verse_ids:
                self.thematic_index[theme] = ThematicIndex(
                    theme=theme,
                    description=f"References to {theme}",
                    note_ids=note_ids,
                    verse_ids=verse_ids,
                    related_themes=[]
                )
        
        print(f"Indexed {len(self.thematic_index)} themes")
    
    def export_to_json(self, output_dir: str) -> Dict[str, str]:
        """Export all data to JSON files"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        files_created = {}
        
        # Export verses
        verses_data = {v.verse_id: asdict(v) for v in self.verses.values()}
        verses_file = output_path / "verses.json"
        with open(verses_file, 'w', encoding='utf-8') as f:
            json.dump(verses_data, f, indent=2)
        files_created['verses'] = str(verses_file)
        
        # Export notes
        notes_data = {n.note_id: asdict(n) for n in self.notes.values()}
        notes_file = output_path / "notes.json"
        with open(notes_file, 'w', encoding='utf-8') as f:
            json.dump(notes_data, f, indent=2)
        files_created['notes'] = str(notes_file)
        
        # Export cross-references
        cross_refs_data = [asdict(cr) for cr in self.cross_refs]
        cross_refs_file = output_path / "cross_references.json"
        with open(cross_refs_file, 'w', encoding='utf-8') as f:
            json.dump(cross_refs_data, f, indent=2)
        files_created['cross_references'] = str(cross_refs_file)
        
        # Export thematic index
        thematic_data = {t: asdict(ti) for t, ti in self.thematic_index.items()}
        thematic_file = output_path / "thematic_index.json"
        with open(thematic_file, 'w', encoding='utf-8') as f:
            json.dump(thematic_data, f, indent=2)
        files_created['thematic_index'] = str(thematic_file)
        
        # Export metadata
        metadata = {
            "generated": datetime.now().isoformat(),
            "version": "1917 Scofield Reference Bible",
            "kjv_edition": "1769 Blayney",
            "statistics": {
                "verses": len(self.verses),
                "notes": len(self.notes),
                "cross_references": len(self.cross_refs),
                "themes": len(self.thematic_index)
            }
        }
        metadata_file = output_path / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        files_created['metadata'] = str(metadata_file)
        
        print(f"Exported data to {output_dir}")
        return files_created
    
    def create_sqlite_db(self, db_path: str) -> None:
        """Create SQLite database with all data"""
        print(f"Creating SQLite database at {db_path}...")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS verses (
            verse_id TEXT PRIMARY KEY,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text TEXT NOT NULL,
            note_ids TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            linked_verses TEXT NOT NULL,
            category TEXT,
            subcategory TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS cross_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            ref_type TEXT NOT NULL,
            description TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS themes (
            theme TEXT PRIMARY KEY,
            description TEXT,
            note_ids TEXT,
            verse_ids TEXT,
            related_themes TEXT
        )
        ''')
        
        # Insert verses
        for verse in self.verses.values():
            cursor.execute('''
            INSERT OR REPLACE INTO verses VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                verse.verse_id,
                verse.book,
                verse.chapter,
                verse.verse,
                verse.text,
                ','.join(verse.note_ids)
            ))
        
        # Insert notes
        for note in self.notes.values():
            cursor.execute('''
            INSERT OR REPLACE INTO notes VALUES (?, ?, ?, ?, ?)
            ''', (
                note.note_id,
                note.text,
                ','.join(note.linked_verses),
                note.category,
                note.subcategory
            ))
        
        # Insert cross-references
        for cr in self.cross_refs:
            cursor.execute('''
            INSERT INTO cross_references (source_id, target_id, ref_type, description)
            VALUES (?, ?, ?, ?)
            ''', (cr.source_id, cr.target_id, cr.ref_type, cr.description))
        
        # Insert themes
        for theme, theme_data in self.thematic_index.items():
            cursor.execute('''
            INSERT OR REPLACE INTO themes VALUES (?, ?, ?, ?, ?)
            ''', (
                theme,
                theme_data.description,
                ','.join(theme_data.note_ids),
                ','.join(theme_data.verse_ids),
                ','.join(theme_data.related_themes)
            ))
        
        # Create indexes for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_verses_book ON verses(book)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses(book, chapter, verse)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cross_refs_source ON cross_references(source_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cross_refs_target ON cross_references(target_id)')
        
        conn.commit()
        conn.close()
        print(f"Database created with {len(self.verses)} verses and {len(self.notes)} notes")

# ============================================================================
# WEB APPLICATION
# ============================================================================

from flask import Flask, render_template, request, jsonify, send_from_directory
import os

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

class BibleWebApp:
    """Flask web application for the Scofield Bible"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.parser = ScofieldParser()
        self.load_data()
        
        # Create static and template directories
        Path("static").mkdir(exist_ok=True)
        Path("templates").mkdir(exist_ok=True)
        
        # Create static files
        self._create_static_files()
        # Create HTML templates
        self._create_templates()
    
    def load_data(self):
        """Load data from JSON files or parse if needed"""
        if not self.data_dir.exists():
            print("Data directory not found. Please run parser first.")
            return
        
        # Try to load from JSON
        try:
            with open(self.data_dir / "verses.json", 'r', encoding='utf-8') as f:
                verses_data = json.load(f)
                self.verses = {vid: BibleVerse(**v) for vid, v in verses_data.items()}
            
            with open(self.data_dir / "notes.json", 'r', encoding='utf-8') as f:
                notes_data = json.load(f)
                self.notes = {nid: ScofieldNote(**n) for nid, n in notes_data.items()}
            
            print(f"Loaded {len(self.verses)} verses and {len(self.notes)} notes from JSON")
        except FileNotFoundError:
            print("JSON files not found. Please run the parser first.")
            self.verses = {}
            self.notes = {}
    
    def _create_static_files(self):
        """Create static CSS and JavaScript files"""
        
        # CSS file
        css_content = '''
        /* Connected Scofield Bible Styles */
        :root {
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --accent-color: #e74c3c;
            --light-bg: #f8f9fa;
            --dark-bg: #2c3e50;
            --text-color: #333;
            --border-color: #dee2e6;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background: var(--light-bg);
        }
        
        .app-container {
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        
        /* Sidebar */
        .sidebar {
            width: 300px;
            background: var(--dark-bg);
            color: white;
            padding: 20px;
            overflow-y: auto;
            border-right: 2px solid var(--secondary-color);
        }
        
        .book-list {
            margin-top: 20px;
        }
        
        .book-item {
            padding: 8px 12px;
            margin: 4px 0;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .book-item:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        .chapter-list {
            margin-left: 15px;
            margin-top: 5px;
            display: none;
        }
        
        .chapter-item {
            padding: 6px 10px;
            margin: 2px 0;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
            cursor: pointer;
        }
        
        .chapter-item:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        
        /* Main Content */
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .header {
            padding: 15px 20px;
            background: white;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .reference {
            font-size: 1.2em;
            font-weight: bold;
            color: var(--primary-color);
        }
        
        .view-toggle {
            display: flex;
            gap: 10px;
        }
        
        .toggle-btn {
            padding: 8px 16px;
            border: 2px solid var(--secondary-color);
            background: white;
            color: var(--secondary-color);
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .toggle-btn.active {
            background: var(--secondary-color);
            color: white;
        }
        
        .toggle-btn:hover:not(.active) {
            background: #f0f8ff;
        }
        
        /* Reader Area */
        .reader-area {
            flex: 1;
            display: flex;
            overflow: hidden;
            padding: 20px;
            gap: 20px;
        }
        
        .text-panel, .notes-panel {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .verse {
            margin-bottom: 15px;
            line-height: 1.8;
        }
        
        .verse-number {
            font-weight: bold;
            color: var(--secondary-color);
            margin-right: 8px;
            font-size: 0.9em;
            vertical-align: super;
        }
        
        .note-indicator {
            color: var(--accent-color);
            font-weight: bold;
            cursor: pointer;
            margin-left: 4px;
            font-size: 0.9em;
        }
        
        .note-content {
            background: #f8f9fa;
            border-left: 3px solid var(--accent-color);
            padding: 15px;
            margin: 10px 0;
            border-radius: 0 4px 4px 0;
        }
        
        /* Cross References */
        .cross-refs-panel {
            width: 300px;
            background: white;
            padding: 20px;
            border-left: 1px solid var(--border-color);
            overflow-y: auto;
            box-shadow: -2px 0 8px rgba(0,0,0,0.1);
        }
        
        .cross-ref-item {
            padding: 10px;
            margin: 8px 0;
            background: #f8f9fa;
            border-radius: 4px;
            border-left: 3px solid var(--secondary-color);
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .cross-ref-item:hover {
            background: #e9ecef;
        }
        
        .cross-ref-ref {
            font-weight: bold;
            color: var(--primary-color);
        }
        
        .cross-ref-text {
            font-size: 0.9em;
            color: #666;
            margin-top: 4px;
        }
        
        /* Search */
        .search-container {
            margin-bottom: 20px;
        }
        
        .search-input {
            width: 100%;
            padding: 10px;
            border: 2px solid var(--border-color);
            border-radius: 4px;
            font-size: 16px;
        }
        
        .search-input:focus {
            outline: none;
            border-color: var(--secondary-color);
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .app-container {
                flex-direction: column;
            }
            
            .sidebar {
                width: 100%;
                height: 200px;
            }
            
            .reader-area {
                flex-direction: column;
            }
            
            .cross-refs-panel {
                width: 100%;
                height: 200px;
            }
        }
        
        .hidden {
            display: none !important;
        }
        '''
        
        with open("static/style.css", "w", encoding="utf-8") as f:
            f.write(css_content)
        
        # JavaScript file
        js_content = '''
        // Connected Scofield Bible JavaScript
        
        class ScofieldReader {
            constructor() {
                this.currentBook = 'GEN';
                this.currentChapter = 1;
                this.currentVerse = null;
                this.viewMode = 'text'; // 'text' or 'notes'
                this.init();
            }
            
            init() {
                this.loadBookList();
                this.setupEventListeners();
                this.loadChapter(this.currentBook, this.currentChapter);
            }
            
            async loadBookList() {
                try {
                    const response = await fetch('/api/books');
                    const books = await response.json();
                    this.renderBookList(books);
                } catch (error) {
                    console.error('Error loading books:', error);
                }
            }
            
            renderBookList(books) {
                const container = document.getElementById('bookList');
                container.innerHTML = '';
                
                books.forEach(book => {
                    const bookDiv = document.createElement('div');
                    bookDiv.className = 'book-item';
                    bookDiv.textContent = book.name;
                    bookDiv.dataset.book = book.abbrev;
                    
                    const chapterDiv = document.createElement('div');
                    chapterDiv.className = 'chapter-list';
                    chapterDiv.id = `chapters-${book.abbrev}`;
                    
                    // Create chapter buttons
                    for (let i = 1; i <= book.chapters; i++) {
                        const chapterBtn = document.createElement('div');
                        chapterBtn.className = 'chapter-item';
                        chapterBtn.textContent = `Chapter ${i}`;
                        chapterBtn.dataset.chapter = i;
                        chapterBtn.onclick = () => this.loadChapter(book.abbrev, i);
                        chapterDiv.appendChild(chapterBtn);
                    }
                    
                    bookDiv.onclick = () => {
                        // Toggle chapter list
                        const chapters = document.getElementById(`chapters-${book.abbrev}`);
                        chapters.style.display = chapters.style.display === 'block' ? 'none' : 'block';
                    };
                    
                    container.appendChild(bookDiv);
                    container.appendChild(chapterDiv);
                });
            }
            
            async loadChapter(book, chapter) {
                this.currentBook = book;
                this.currentChapter = chapter;
                this.currentVerse = null;
                
                try {
                    // Update reference display
                    document.querySelector('.reference').textContent = 
                        `${this.getBookName(book)} ${chapter}`;
                    
                    // Load verses
                    const response = await fetch(`/api/verses/${book}/${chapter}`);
                    const verses = await response.json();
                    this.renderVerses(verses);
                    
                    // Update URL
                    history.pushState({}, '', `/${book}/${chapter}`);
                } catch (error) {
                    console.error('Error loading chapter:', error);
                }
            }
            
            renderVerses(verses) {
                const textPanel = document.getElementById('textPanel');
                const notesPanel = document.getElementById('notesPanel');
                
                textPanel.innerHTML = '';
                notesPanel.innerHTML = '';
                
                verses.forEach(verse => {
                    // Render in text panel
                    const verseDiv = document.createElement('div');
                    verseDiv.className = 'verse';
                    verseDiv.id = `verse-${verse.verse_id}`;
                    
                    const verseNum = document.createElement('span');
                    verseNum.className = 'verse-number';
                    verseNum.textContent = verse.verse;
                    verseNum.onclick = () => this.highlightVerse(verse.verse_id);
                    
                    const verseText = document.createElement('span');
                    verseText.innerHTML = this.formatVerseText(verse.text, verse.note_ids);
                    
                    verseDiv.appendChild(verseNum);
                    verseDiv.appendChild(verseText);
                    textPanel.appendChild(verseDiv);
                    
                    // Render notes if any
                    if (verse.notes && verse.notes.length > 0) {
                        verse.notes.forEach(note => {
                            const noteDiv = document.createElement('div');
                            noteDiv.className = 'note-content';
                            noteDiv.innerHTML = `
                                <strong>Note on verse ${verse.verse}:</strong>
                                <p>${note.text}</p>
                            `;
                            notesPanel.appendChild(noteDiv);
                        });
                    }
                });
                
                // Load cross-references for first verse
                if (verses.length > 0) {
                    this.loadCrossReferences(verses[0].verse_id);
                }
            }
            
            formatVerseText(text, noteIds) {
                // Add note indicators
                let formatted = text;
                noteIds?.forEach((noteId, index) => {
                    const indicator = `<sup class="note-indicator" onclick="reader.showNote('${noteId}')">${index + 1}</sup>`;
                    formatted += indicator;
                });
                return formatted;
            }
            
            highlightVerse(verseId) {
                // Remove previous highlights
                document.querySelectorAll('.verse').forEach(v => {
                    v.style.backgroundColor = '';
                });
                
                // Highlight selected verse
                const verseDiv = document.getElementById(`verse-${verseId}`);
                if (verseDiv) {
                    verseDiv.style.backgroundColor = '#f0f8ff';
                    this.loadCrossReferences(verseId);
                    
                    // Update current verse
                    const parts = verseId.split('.');
                    this.currentVerse = parseInt(parts[2]);
                }
            }
            
            async loadCrossReferences(verseId) {
                try {
                    const response = await fetch(`/api/cross-references/${verseId}`);
                    const refs = await response.json();
                    this.renderCrossReferences(refs);
                } catch (error) {
                    console.error('Error loading cross-references:', error);
                }
            }
            
            renderCrossReferences(refs) {
                const container = document.getElementById('crossRefs');
                container.innerHTML = '<h3>Cross References</h3>';
                
                if (refs.length === 0) {
                    container.innerHTML += '<p>No cross-references found.</p>';
                    return;
                }
                
                refs.forEach(ref => {
                    const refDiv = document.createElement('div');
                    refDiv.className = 'cross-ref-item';
                    refDiv.onclick = () => this.navigateToReference(ref.target_id);
                    
                    refDiv.innerHTML = `
                        <div class="cross-ref-ref">${ref.target_reference}</div>
                        <div class="cross-ref-text">${ref.target_text?.substring(0, 100)}...</div>
                        <small>${ref.ref_type}</small>
                    `;
                    
                    container.appendChild(refDiv);
                });
            }
            
            async showNote(noteId) {
                try {
                    const response = await fetch(`/api/note/${noteId}`);
                    const note = await response.json();
                    
                    // Switch to notes view
                    this.setViewMode('notes');
                    
                    // Scroll to and highlight note
                    const notesPanel = document.getElementById('notesPanel');
                    const noteElement = document.querySelector(`[data-note-id="${noteId}"]`);
                    if (noteElement) {
                        noteElement.scrollIntoView({ behavior: 'smooth' });
                        noteElement.style.backgroundColor = '#fff3cd';
                    }
                } catch (error) {
                    console.error('Error loading note:', error);
                }
            }
            
            setViewMode(mode) {
                this.viewMode = mode;
                
                const textPanel = document.getElementById('textPanel');
                const notesPanel = document.getElementById('notesPanel');
                const textBtn = document.querySelector('.toggle-btn:nth-child(1)');
                const notesBtn = document.querySelector('.toggle-btn:nth-child(2)');
                
                if (mode === 'text') {
                    textPanel.classList.remove('hidden');
                    notesPanel.classList.add('hidden');
                    textBtn.classList.add('active');
                    notesBtn.classList.remove('active');
                } else {
                    textPanel.classList.add('hidden');
                    notesPanel.classList.remove('hidden');
                    textBtn.classList.remove('active');
                    notesBtn.classList.add('active');
                }
            }
            
            navigateToReference(verseId) {
                const parts = verseId.split('.');
                const [book, chapter, verse] = parts;
                
                this.loadChapter(book, parseInt(chapter)).then(() => {
                    // Highlight the specific verse
                    setTimeout(() => {
                        this.highlightVerse(verseId);
                        const verseElement = document.getElementById(`verse-${verseId}`);
                        if (verseElement) {
                            verseElement.scrollIntoView({ behavior: 'smooth' });
                        }
                    }, 100);
                });
            }
            
            getBookName(abbrev) {
                const bookNames = {
                    'GEN': 'Genesis', 'EXO': 'Exodus', 'LEV': 'Leviticus', 'NUM': 'Numbers',
                    'DEU': 'Deuteronomy', 'JOS': 'Joshua', 'JDG': 'Judges', 'RUT': 'Ruth',
                    '1SA': '1 Samuel', '2SA': '2 Samuel', '1KI': '1 Kings', '2KI': '2 Kings',
                    '1CH': '1 Chronicles', '2CH': '2 Chronicles', 'EZR': 'Ezra', 'NEH': 'Nehemiah',
                    'EST': 'Esther', 'JOB': 'Job', 'PSA': 'Psalms', 'PRO': 'Proverbs',
                    'ECC': 'Ecclesiastes', 'SON': 'Song of Solomon', 'ISA': 'Isaiah', 'JER': 'Jeremiah',
                    'LAM': 'Lamentations', 'EZE': 'Ezekiel', 'DAN': 'Daniel', 'HOS': 'Hosea',
                    'JOE': 'Joel', 'AMO': 'Amos', 'OBA': 'Obadiah', 'JON': 'Jonah',
                    'MIC': 'Micah', 'NAH': 'Nahum', 'HAB': 'Habakkuk', 'ZEP': 'Zephaniah',
                    'HAG': 'Haggai', 'ZEC': 'Zechariah', 'MAL': 'Malachi', 'MAT': 'Matthew',
                    'MAR': 'Mark', 'LUK': 'Luke', 'JOH': 'John', 'ACT': 'Acts',
                    'ROM': 'Romans', '1CO': '1 Corinthians', '2CO': '2 Corinthians', 'GAL': 'Galatians',
                    'EPH': 'Ephesians', 'PHI': 'Philippians', 'COL': 'Colossians', '1TH': '1 Thessalonians',
                    '2TH': '2 Thessalonians', '1TI': '1 Timothy', '2TI': '2 Timothy', 'TIT': 'Titus',
                    'PHM': 'Philemon', 'HEB': 'Hebrews', 'JAM': 'James', '1PE': '1 Peter',
                    '2PE': '2 Peter', '1JO': '1 John', '2JO': '2 John', '3JO': '3 John',
                    'JUD': 'Jude', 'REV': 'Revelation'
                };
                return bookNames[abbrev] || abbrev;
            }
            
            async search(query) {
                try {
                    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                    const results = await response.json();
                    this.displaySearchResults(results);
                } catch (error) {
                    console.error('Error searching:', error);
                }
            }
            
            displaySearchResults(results) {
                // Create search results modal or panel
                console.log('Search results:', results);
                // Implement search results display
            }
        }
        
        // Initialize reader when page loads
        let reader;
        document.addEventListener('DOMContentLoaded', () => {
            reader = new ScofieldReader();
            window.reader = reader; // Make available globally
            
            // Setup search
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' && searchInput.value.trim()) {
                        reader.search(searchInput.value.trim());
                    }
                });
            }
            
            // Setup view toggle buttons
            document.querySelectorAll('.toggle-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const mode = this.textContent.toLowerCase().includes('text') ? 'text' : 'notes';
                    reader.setViewMode(mode);
                });
            });
        });
        
        // Handle browser back/forward
        window.addEventListener('popstate', () => {
            const path = window.location.pathname.split('/').filter(p => p);
            if (path.length >= 2) {
                reader.loadChapter(path[0], parseInt(path[1]));
            }
        });
        '''
        
        with open("static/script.js", "w", encoding="utf-8") as f:
            f.write(js_content)
    
    def _create_templates(self):
        """Create HTML templates"""
        
        # Main template
        html_content = '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Connected Scofield Bible</title>
            <link rel="stylesheet" href="/static/style.css">
            <link rel="manifest" href="/static/manifest.json">
            <meta name="theme-color" content="#2c3e50">
            <meta name="description" content="Interactive 1917 Scofield Reference Bible">
        </head>
        <body>
            <div class="app-container">
                <!-- Sidebar with books and chapters -->
                <div class="sidebar">
                    <h2>Scofield Bible</h2>
                    <div class="search-container">
                        <input type="text" id="searchInput" class="search-input" 
                               placeholder="Search verses or notes...">
                    </div>
                    <div class="book-list" id="bookList">
                        <!-- Books will be loaded here -->
                    </div>
                </div>
                
                <!-- Main content area -->
                <div class="main-content">
                    <!-- Header with reference and controls -->
                    <div class="header">
                        <div class="reference">Genesis 1</div>
                        <div class="view-toggle">
                            <button class="toggle-btn active">KJV Text</button>
                            <button class="toggle-btn">Scofield Notes</button>
                        </div>
                    </div>
                    
                    <!-- Reader area -->
                    <div class="reader-area">
                        <!-- Bible text panel -->
                        <div class="text-panel" id="textPanel">
                            <!-- Verses will be loaded here -->
                        </div>
                        
                        <!-- Notes panel (hidden by default) -->
                        <div class="notes-panel hidden" id="notesPanel">
                            <!-- Notes will be loaded here -->
                        </div>
                        
                        <!-- Cross-references panel -->
                        <div class="cross-refs-panel" id="crossRefs">
                            <h3>Cross References</h3>
                            <p>Select a verse to see cross-references.</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="/static/script.js"></script>
        </body>
        </html>
        '''
        
        with open("templates/index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Create manifest for PWA
        manifest = {
            "name": "Connected Scofield Bible",
            "short_name": "Scofield",
            "description": "Interactive 1917 Scofield Reference Bible",
            "start_url": "/",
            "display": "standalone",
            "theme_color": "#2c3e50",
            "background_color": "#ffffff",
            "icons": [
                {
                    "src": "/static/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                },
                {
                    "src": "/static/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png"
                }
            ]
        }
        
        with open("static/manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

# ============================================================================
# FLASK ROUTES
# ============================================================================

# Global app instance
web_app = None

def create_app():
    """Create and configure Flask application"""
    global web_app
    web_app = BibleWebApp()
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/static/<path:filename>')
    def static_files(filename):
        return send_from_directory('static', filename)
    
    @app.route('/api/books')
    def get_books():
        """Get list of all Bible books with chapter counts"""
        books = []
        # Count chapters per book
        chapter_counts = {}
        
        for verse_id, verse in web_app.verses.items():
            if verse.book not in chapter_counts:
                chapter_counts[verse.book] = set()
            chapter_counts[verse.book].add(verse.chapter)
        
        for abbrev, name in ScofieldParser.BOOK_ABBREV.items():
            if abbrev in chapter_counts:
                books.append({
                    'abbrev': abbrev,
                    'name': name,
                    'chapters': len(chapter_counts[abbrev])
                })
        
        return jsonify(books)
    
    @app.route('/api/verses/<book>/<int:chapter>')
    def get_chapter_verses(book, chapter):
        """Get all verses for a specific chapter"""
        verses = []
        
        for verse_id, verse in web_app.verses.items():
            if verse.book == book.upper() and verse.chapter == chapter:
                verse_data = asdict(verse)
                
                # Get notes for this verse
                notes = []
                for note_id in verse.note_ids:
                    if note_id in web_app.notes:
                        notes.append(asdict(web_app.notes[note_id]))
                
                verse_data['notes'] = notes
                verses.append(verse_data)
        
        # Sort by verse number
        verses.sort(key=lambda x: x['verse'])
        return jsonify(verses)
    
    @app.route('/api/cross-references/<verse_id>')
    def get_cross_references(verse_id):
        """Get cross-references for a specific verse"""
        # In a real implementation, you would query your cross-reference data
        # For now, return sample data
        refs = []
        
        # Example: Find verses that mention similar words
        if verse_id in web_app.verses:
            verse = web_app.verses[verse_id]
            words = set(verse.text.lower().split()[:5])  # First 5 words
            
            for other_id, other_verse in web_app.verses.items():
                if other_id != verse_id:
                    other_words = set(other_verse.text.lower().split())
                    common = words.intersection(other_words)
                    if len(common) >= 2:  # At least 2 common words
                        refs.append({
                            'source_id': verse_id,
                            'target_id': other_id,
                            'target_reference': other_verse.reference,
                            'target_text': other_verse.text[:100] + '...',
                            'ref_type': 'parallel',
                            'description': f'Shared words: {", ".join(common)}'
                        })
                        if len(refs) >= 10:  # Limit results
                            break
        
        return jsonify(refs)
    
    @app.route('/api/note/<note_id>')
    def get_note(note_id):
        """Get a specific note by ID"""
        if note_id in web_app.notes:
            return jsonify(asdict(web_app.notes[note_id]))
        return jsonify({'error': 'Note not found'}), 404
    
    @app.route('/api/search')
    def search():
        """Search verses and notes"""
        query = request.args.get('q', '').lower()
        results = []
        
        if not query:
            return jsonify([])
        
        # Search verses
        for verse_id, verse in web_app.verses.items():
            if query in verse.text.lower():
                results.append({
                    'type': 'verse',
                    'id': verse_id,
                    'reference': verse.reference,
                    'text': verse.text[:150] + '...' if len(verse.text) > 150 else verse.text,
                    'score': verse.text.lower().count(query)
                })
        
        # Search notes
        for note_id, note in web_app.notes.items():
            if query in note.text.lower():
                results.append({
                    'type': 'note',
                    'id': note_id,
                    'reference': note.linked_verses[0] if note.linked_verses else '',
                    'text': note.text[:150] + '...' if len(note.text) > 150 else note.text,
                    'score': note.text.lower().count(query)
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x['score'], reverse=True)
        return jsonify(results[:50])  # Limit to 50 results
    
    @app.route('/api/themes')
    def get_themes():
        """Get list of theological themes"""
        themes = list(ScofieldParser.THEMES)
        return jsonify(themes)
    
    @app.route('/api/theme/<theme_name>')
    def get_theme(theme_name):
        """Get all references to a specific theme"""
        # In a real implementation, query your thematic index
        results = []
        
        # Search for theme in notes
        for note_id, note in web_app.notes.items():
            if theme_name.lower() in note.text.lower():
                results.append({
                    'type': 'note',
                    'id': note_id,
                    'text': note.text[:200] + '...',
                    'linked_verses': note.linked_verses
                })
        
        return jsonify(results)
    
    return app

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main command-line interface"""
    parser = argparse.ArgumentParser(description="Scofield Bible Parser and Web Application")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Parse command
    parse_parser = subparsers.add_parser('parse', help='Parse KJV and Scofield files')
    parse_parser.add_argument('--kjv', type=str, required=True, help='Path to KJV text file')
    parse_parser.add_argument('--notes', type=str, required=True, help='Path to Scofield notes file')
    parse_parser.add_argument('--output', type=str, default='data', help='Output directory')
    parse_parser.add_argument('--db', type=str, help='Create SQLite database at this path')
    
    # Web server command
    web_parser = subparsers.add_parser('serve', help='Start web server')
    web_parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to')
    web_parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    web_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export to various formats')
    export_parser.add_argument('--format', choices=['json', 'sqlite', 'all'], default='all',
                              help='Export format')
    export_parser.add_argument('--input', type=str, default='data', help='Input data directory')
    export_parser.add_argument('--output', type=str, default='exports', help='Output directory')
    
    args = parser.parse_args()
    
    if args.command == 'parse':
        # Parse the data
        print("=" * 60)
        print("SCOFIELD BIBLE PARSER")
        print("=" * 60)
        
        parser = ScofieldParser()
        
        # Parse KJV text
        if Path(args.kjv).exists():
            parser.parse_kjv_text(args.kjv)
        else:
            print(f"Warning: KJV file not found at {args.kjv}")
            print("Creating sample data...")
            # Create sample data for demonstration
            parser.verses = {
                "GEN.1.1": BibleVerse("GEN", 1, 1, "In the beginning God created the heaven and the earth."),
                "GEN.1.2": BibleVerse("GEN", 1, 2, "And the earth was without form, and void; and darkness was upon the face of the deep."),
                "JOH.1.1": BibleVerse("JOH", 1, 1, "In the beginning was the Word, and the Word was with God, and the Word was God."),
                "ROM.3.23": BibleVerse("ROM", 3, 23, "For all have sinned, and come short of the glory of God;"),
            }
        
        # Parse Scofield notes
        if Path(args.notes).exists():
            parser.parse_scofield_notes(args.notes)
        else:
            print(f"Warning: Notes file not found at {args.notes}")
            print("Creating sample notes...")
            # Create sample notes
            parser.notes = {
                "N0001": ScofieldNote(
                    note_id="N0001",
                    text="The first creative act refers to the dateless past, and gives scope for all the geologic ages. (See Scofield 'Genesis 1:1')",
                    linked_verses=["GEN.1.1"],
                    category="Creation"
                ),
                "N0002": ScofieldNote(
                    note_id="N0002",
                    text="Sin originated with Satan (Isaiah 14:12-14), entered the world through Adam (Romans 5:12), and was judged at the cross.",
                    linked_verses=["ROM.3.23"],
                    category="Sin"
                )
            }
            
            # Add note IDs to verses
            parser.verses["GEN.1.1"].note_ids.append("N0001")
            parser.verses["ROM.3.23"].note_ids.append("N0002")
            
            # Add sample cross-reference
            parser.cross_refs.append(CrossReference(
                source_id="N0001",
                target_id="JOH.1.1",
                ref_type="parallel",
                description="Parallel beginnings"
            ))
        
        # Build thematic index
        parser.build_thematic_index()
        
        # Export to JSON
        files = parser.export_to_json(args.output)
        
        # Create SQLite database if requested
        if args.db:
            parser.create_sqlite_db(args.db)
        
        print("\nParsing complete!")
        print(f"Data exported to: {args.output}")
        for file_type, path in files.items():
            print(f"  {file_type}: {path}")
        
        if args.db:
            print(f"Database created: {args.db}")
    
    elif args.command == 'serve':
        # Start web server
        print("=" * 60)
        print("SCOFIELD BIBLE WEB APPLICATION")
        print("=" * 60)
        print(f"Starting server at http://{args.host}:{args.port}")
        print("Press Ctrl+C to stop")
        
        app = create_app()
        app.run(host=args.host, port=args.port, debug=args.debug)
    
    elif args.command == 'export':
        # Export data
        print("Export functionality to be implemented")
        # You would load data and export in various formats
    
    else:
        # Show help if no command provided
        parser.print_help()
        
        # Create a sample project structure
        print("\n" + "=" * 60)
        print("QUICK START")
        print("=" * 60)
        print("1. Create sample data:")
        print("   python scofield.py parse --kjv sample_kjv.txt --notes sample_notes.txt")
        print("\n2. Start the web application:")
        print("   python scofield.py serve")
        print("\n3. Open your browser to: http://127.0.0.1:5000")
        print("\nNote: You'll need to provide actual KJV and Scofield note files.")
        print("For testing, the parser will create sample data if files are not found.")

# ============================================================================
# SAMPLE DATA GENERATOR (for testing)
# ============================================================================

def create_sample_data():
    """Create sample data files for testing"""
    print("Creating sample data files...")
    
    # Create sample KJV file
    kjv_sample = """GEN	1	1	In the beginning God created the heaven and the earth.
GEN	1	2	And the earth was without form, and void; and darkness was upon the face of the deep. And the Spirit of God moved upon the face of the waters.
GEN	1	3	And God said, Let there be light: and there was light.
JOH	1	1	In the beginning was the Word, and the Word was with God, and the Word was God.
JOH	1	2	The same was in the beginning with God.
ROM	3	23	For all have sinned, and come short of the glory of God;
ROM	6	23	For the wages of sin is death; but the gift of God is eternal life through Jesus Christ our Lord."""
    
    with open("sample_kjv.txt", "w", encoding="utf-8") as f:
        f.write(kjv_sample)
    
    # Create sample notes file
    notes_sample = """NOTE: GENESIS 1:1
The first creative act refers to the dateless past, and gives scope for all the geologic ages.
REF: See John 1:1-3; Hebrews 11:3

NOTE: ROMANS 3:23
Sin originated with Satan (Isaiah 14:12-14), entered the world through Adam (Romans 5:12), and was judged at the cross.
REF: See Genesis 3:1-6; 1 John 3:8"""
    
    with open("sample_notes.txt", "w", encoding="utf-8") as f:
        f.write(notes_sample)
    
    print("Sample files created:")
    print("  - sample_kjv.txt")
    print("  - sample_notes.txt")
    print("\nRun: python scofield.py parse --kjv sample_kjv.txt --notes sample_notes.txt")

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Check if we should create sample data
    import sys
    if len(sys.argv) == 2 and sys.argv[1] == "create-sample":
        create_sample_data()
    else:
        main()
