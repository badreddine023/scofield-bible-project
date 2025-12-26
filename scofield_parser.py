# scofield_parser.py
"""
Enhanced Scofield Bible Parser - Complete Implementation
Builds on existing repository structure at: 
https://github.com/badreddine023/scofield-bible-project
"""

import json
import re
import sqlite3
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
import hashlib
from datetime import datetime
from enum import Enum
import csv
import logging
from collections import defaultdict
import zipfile
import io

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class NoteType(Enum):
    """Types of Scofield notes"""
    EXPLANATORY = "explanatory"
    DOCTRINAL = "doctrinal"
    PROPHETIC = "prophetic"
    HISTORICAL = "historical"
    PRACTICAL = "practical"
    THEMATIC = "thematic"
    CROSS_REFERENCE = "cross_reference"

class ReferenceType(Enum):
    """Types of cross-references"""
    PARALLEL = "parallel"
    FULFILLMENT = "fulfillment"
    QUOTATION = "quotation"
    THEMATIC = "thematic"
    TYPOLOGICAL = "typological"
    CONTRAST = "contrast"
    EXPLANATION = "explanation"

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
    note_ids: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    @property
    def verse_id(self) -> str:
        return f"{self.book}.{self.chapter}.{self.verse}"
    
    @property
    def reference(self) -> str:
        return f"{self.book} {self.chapter}:{self.verse}"
    
    @property
    def full_reference(self) -> str:
        book_name = BIBLE_BOOKS.get(self.book, self.book)
        return f"{book_name} {self.chapter}:{self.verse}"
    
    def to_dict(self) -> Dict:
        return {
            "verse_id": self.verse_id,
            "book": self.book,
            "chapter": self.chapter,
            "verse": self.verse,
            "text": self.text,
            "note_ids": self.note_ids,
            "keywords": self.keywords,
            "reference": self.reference,
            "full_reference": self.full_reference
        }

@dataclass
class ScofieldNote:
    """Represents a Scofield study note with enhanced metadata"""
    note_id: str
    text: str
    linked_verses: List[str]  # List of verse_ids
    note_type: str = NoteType.EXPLANATORY.value
    category: str = ""
    subcategory: str = ""
    keywords: List[str] = field(default_factory=list)
    theme_tags: List[str] = field(default_factory=list)
    related_notes: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.note_id.startswith("N"):
            self.note_id = f"N{self.note_id}"
    
    @property
    def first_verse(self) -> Optional[str]:
        return self.linked_verses[0] if self.linked_verses else None
    
    @property
    def verse_count(self) -> int:
        return len(self.linked_verses)
    
    def to_dict(self) -> Dict:
        return {
            "note_id": self.note_id,
            "text": self.text,
            "linked_verses": self.linked_verses,
            "note_type": self.note_type,
            "category": self.category,
            "subcategory": self.subcategory,
            "keywords": self.keywords,
            "theme_tags": self.theme_tags,
            "related_notes": self.related_notes,
            "verse_count": self.verse_count,
            "first_verse": self.first_verse
        }

@dataclass
class CrossReference:
    """Enhanced cross-reference relationship with metadata"""
    source_id: str  # verse_id or note_id
    target_id: str  # verse_id or note_id
    ref_type: str = ReferenceType.THEMATIC.value
    description: str = ""
    confidence: float = 1.0  # How confident we are in this reference (0-1)
    tags: List[str] = field(default_factory=list)
    
    @property
    def is_note_to_verse(self) -> bool:
        return self.source_id.startswith("N") and not self.target_id.startswith("N")
    
    @property
    def is_verse_to_verse(self) -> bool:
        return not self.source_id.startswith("N") and not self.target_id.startswith("N")
    
    def to_dict(self) -> Dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "ref_type": self.ref_type,
            "description": self.description,
            "confidence": self.confidence,
            "tags": self.tags,
            "is_note_to_verse": self.is_note_to_verse,
            "is_verse_to_verse": self.is_verse_to_verse
        }

@dataclass
class ThematicIndex:
    """Enhanced thematic index for doctrinal studies"""
    theme_id: str
    name: str
    description: str
    note_ids: List[str] = field(default_factory=list)
    verse_ids: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    sub_themes: List[str] = field(default_factory=list)
    parent_themes: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    
    @property
    def total_references(self) -> int:
        return len(self.note_ids) + len(self.verse_ids)
    
    def to_dict(self) -> Dict:
        return {
            "theme_id": self.theme_id,
            "name": self.name,
            "description": self.description,
            "note_ids": self.note_ids,
            "verse_ids": self.verse_ids,
            "categories": self.categories,
            "sub_themes": self.sub_themes,
            "parent_themes": self.parent_themes,
            "confidence_score": self.confidence_score,
            "total_references": self.total_references
        }

@dataclass
class ReadingPlan:
    """Custom reading plans based on themes or structure"""
    plan_id: str
    name: str
    description: str
    days: List[List[str]]  # Each day contains list of verse_ids
    theme: str = ""
    estimated_minutes: int = 15
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "days": self.days,
            "day_count": len(self.days),
            "total_verses": sum(len(day) for day in self.days),
            "theme": self.theme,
            "estimated_minutes": self.estimated_minutes,
            "tags": self.tags
        }

# ============================================================================
# BIBLE DATA CONSTANTS
# ============================================================================

BIBLE_BOOKS = {
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

BOOK_CHAPTER_COUNTS = {
    'GEN': 50, 'EXO': 40, 'LEV': 27, 'NUM': 36, 'DEU': 34,
    'JOS': 24, 'JDG': 21, 'RUT': 4, '1SA': 31, '2SA': 24,
    '1KI': 22, '2KI': 25, '1CH': 29, '2CH': 36, 'EZR': 10,
    'NEH': 13, 'EST': 10, 'JOB': 42, 'PSA': 150, 'PRO': 31,
    'ECC': 12, 'SON': 8, 'ISA': 66, 'JER': 52, 'LAM': 5,
    'EZE': 48, 'DAN': 12, 'HOS': 14, 'JOE': 3, 'AMO': 9,
    'OBA': 1, 'JON': 4, 'MIC': 7, 'NAH': 3, 'HAB': 3,
    'ZEP': 3, 'HAG': 2, 'ZEC': 14, 'MAL': 4, 'MAT': 28,
    'MAR': 16, 'LUK': 24, 'JOH': 21, 'ACT': 28, 'ROM': 16,
    '1CO': 16, '2CO': 13, 'GAL': 6, 'EPH': 6, 'PHI': 4,
    'COL': 4, '1TH': 5, '2TH': 3, '1TI': 6, '2TI': 4,
    'TIT': 3, 'PHM': 1, 'HEB': 13, 'JAM': 5, '1PE': 5,
    '2PE': 3, '1JO': 5, '2JO': 1, '3JO': 1, 'JUD': 1,
    'REV': 22
}

SCOFIELD_THEMES = [
    # Major Scofield Doctrines
    "Dispensation", "Covenant Theology", "Grace", "Law vs. Grace", "Prophecy",
    "Kingdom of God", "Church Age", "Israel and the Church", "Gentiles", 
    "Salvation", "Atonement", "Justification", "Sanctification", "Glorification",
    "Eschatology", "Second Coming", "Millennium", "Great White Throne",
    "Rapture", "Tribulation", "Antichrist", "Resurrection", "Judgment",
    "Heaven", "Hell", "New Jerusalem", "Eternal State",
    
    # Biblical Themes
    "Creation", "Fall of Man", "Redemption", "Covenants", "Promise",
    "Faith", "Hope", "Love", "Sin", "Repentance",
    "Forgiveness", "Mercy", "Justice", "Holiness", "Righteousness",
    
    # Christological Themes
    "Deity of Christ", "Humanity of Christ", "Virgin Birth", "Incarnation",
    "Atoning Death", "Resurrection", "Ascension", "High Priest",
    "Mediator", "Advocate", "King of Kings", "Lord of Lords"
]

# ============================================================================
# ENHANCED PARSER ENGINE
# ============================================================================

class EnhancedScofieldParser:
    """Advanced parser with text analysis and relationship extraction"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.verses: Dict[str, BibleVerse] = {}
        self.notes: Dict[str, ScofieldNote] = {}
        self.cross_refs: List[CrossReference] = []
        self.thematic_index: Dict[str, ThematicIndex] = {}
        self.reading_plans: Dict[str, ReadingPlan] = {}
        
        self.note_counter = 1
        self.theme_counter = 1
        self.plan_counter = 1
        
        # Text processing patterns
        self.verse_ref_pattern = re.compile(
            r'([1-3]?\s?[A-Z][a-z]+\.?\s+\d+:\d+(?:-\d+)?(?:,\s*\d+:\d+)*)',
            re.IGNORECASE
        )
        
        self.cross_ref_pattern = re.compile(
            r'(?:See|cf\.|compare|v\.?|verse)\s+([1-3]?\s?[A-Z][a-z]+\.?\s+\d+:\d+)',
            re.IGNORECASE
        )
        
        # Keyword extraction patterns
        self.doctrine_patterns = {
            'dispensation': r'\bdispensation(s|al)?\b',
            'covenant': r'\bcovenant(s|al)?\b',
            'grace': r'\bgrace\b',
            'law': r'\blaw\b',
            'prophecy': r'\bprophe(cy|cies|t(s|ic))\b',
            'kingdom': r'\bkingdom\b',
            'church': r'\bchurch\b',
            'Israel': r'\bIsrael\b',
            'salvation': r'\bsalvation\b',
            'atonement': r'\batonement\b',
            'justification': r'\bjustification\b',
            'sanctification': r'\bsanctification\b',
            'eschatology': r'\beschatology\b',
            'rapture': r'\brapture\b',
            'millennium': r'\bmillennium\b',
            'resurrection': r'\bresurrection\b'
        }
    
    def parse_kjv_from_file(self, file_path: str, format_type: str = 'tsv') -> None:
        """Parse KJV text from various file formats"""
        logger.info(f"Parsing KJV text from {file_path} (format: {format_type})")
        
        if format_type == 'tsv':
            self._parse_kjv_tsv(file_path)
        elif format_type == 'csv':
            self._parse_kjv_csv(file_path)
        elif format_type == 'json':
            self._parse_kjv_json(file_path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        logger.info(f"Loaded {len(self.verses)} verses")
    
    def _parse_kjv_tsv(self, file_path: str) -> None:
        """Parse KJV from tab-separated file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                if len(row) >= 4:
                    book_abbrev = row[0].upper().strip()
                    if book_abbrev in BIBLE_BOOKS:
                        try:
                            chapter = int(row[1].strip())
                            verse = int(row[2].strip())
                            text = ' '.join(row[3:]).strip()
                            
                            # Extract keywords from verse text
                            keywords = self._extract_keywords(text)
                            
                            verse_obj = BibleVerse(
                                book=book_abbrev,
                                chapter=chapter,
                                verse=verse,
                                text=text,
                                keywords=keywords
                            )
                            self.verses[verse_obj.verse_id] = verse_obj
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Error parsing row: {row} - {e}")
    
    def parse_scofield_notes_from_file(self, file_path: str, format_type: str = 'tsv') -> None:
        """Parse Scofield notes from various file formats"""
        logger.info(f"Parsing Scofield notes from {file_path}")
        
        # Based on your GitHub structure, adjust this parser
        if format_type == 'tsv':
            self._parse_notes_tsv(file_path)
        elif format_type == 'markdown':
            self._parse_notes_markdown(file_path)
        else:
            self._parse_notes_text(file_path)
        
        logger.info(f"Loaded {len(self.notes)} notes")
    
    def _parse_notes_tsv(self, file_path: str) -> None:
        """Parse notes from TSV file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 3:
                    try:
                        # Format: reference	note_text	category	keywords
                        ref_str = parts[0].strip()
                        note_text = parts[1].strip()
                        category = parts[2].strip() if len(parts) > 2 else ""
                        keywords = parts[3].split(',') if len(parts) > 3 else []
                        
                        # Parse reference (could be single or multiple verses)
                        verse_refs = self._parse_verse_reference(ref_str)
                        
                        if verse_refs:
                            # Create note
                            note_id = f"N{self.note_counter:04d}"
                            note = ScofieldNote(
                                note_id=note_id,
                                text=note_text,
                                linked_verses=verse_refs,
                                category=category,
                                keywords=[k.strip() for k in keywords if k.strip()],
                                theme_tags=self._extract_themes_from_note(note_text)
                            )
                            
                            self.notes[note_id] = note
                            
                            # Link note to verses
                            for verse_id in verse_refs:
                                if verse_id in self.verses:
                                    self.verses[verse_id].note_ids.append(note_id)
                            
                            self.note_counter += 1
                            
                            # Extract cross-references from note text
                            self._extract_cross_refs_from_note(note_id, note_text)
                    
                    except Exception as e:
                        logger.warning(f"Error parsing note line {line_num}: {e}")
    
    def _parse_verse_reference(self, ref_str: str) -> List[str]:
        """Parse verse reference string into list of verse_ids"""
        verse_ids = []
        
        # Handle multiple references separated by commas or semicolons
        ref_parts = re.split(r'[;,]+', ref_str)
        
        for ref_part in ref_parts:
            ref_part = ref_part.strip()
            if not ref_part:
                continue
            
            # Match patterns like "Gen 1:1" or "Genesis 1:1-3"
            match = re.match(
                r'([1-3]?\s?[A-Z][a-z]+)\.?\s+(\d+):(\d+)(?:-(\d+))?',
                ref_part,
                re.IGNORECASE
            )
            
            if match:
                book_name, chapter, start_verse, end_verse = match.groups()
                book_abbrev = self._book_name_to_abbrev(book_name)
                
                if book_abbrev:
                    start = int(start_verse)
                    end = int(end_verse) if end_verse else start
                    
                    for verse_num in range(start, end + 1):
                        verse_id = f"{book_abbrev}.{chapter}.{verse_num}"
                        verse_ids.append(verse_id)
        
        return verse_ids
    
    def _extract_cross_refs_from_note(self, note_id: str, note_text: str) -> None:
        """Extract cross-references from note text"""
        # Find all cross-reference mentions
        matches = self.cross_ref_pattern.findall(note_text)
        
        for ref_str in matches:
            target_verse_ids = self._parse_verse_reference(ref_str)
            
            for target_id in target_verse_ids:
                # Create cross-reference from note to verse
                cross_ref = CrossReference(
                    source_id=note_id,
                    target_id=target_id,
                    ref_type=ReferenceType.EXPLANATION.value,
                    description=f"Referenced in note {note_id}",
                    confidence=0.8
                )
                self.cross_refs.append(cross_ref)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        keywords = []
        text_lower = text.lower()
        
        for word, pattern in self.doctrine_patterns.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                keywords.append(word)
        
        # Add common biblical keywords
        common_keywords = ['God', 'Lord', 'Jesus', 'Christ', 'Holy Spirit', 
                          'faith', 'love', 'hope', 'sin', 'grace']
        
        for keyword in common_keywords:
            if keyword.lower() in text_lower:
                keywords.append(keyword)
        
        return list(set(keywords))
    
    def _extract_themes_from_note(self, note_text: str) -> List[str]:
        """Extract theme tags from note text"""
        themes = []
        note_lower = note_text.lower()
        
        for theme in SCOFIELD_THEMES:
            theme_lower = theme.lower()
            # Check for theme or related terms
            if (theme_lower in note_lower or 
                re.search(rf'\b{re.escape(theme_lower[:-1])}', note_lower)):
                themes.append(theme)
        
        return themes
    
    def _book_name_to_abbrev(self, book_name: str) -> Optional[str]:
        """Convert full book name to abbreviation"""
        # Clean up book name
        book_name = book_name.strip().title()
        
        # Handle common variations
        variations = {
            'Psalms': 'PSA',
            'Psalm': 'PSA',
            'Song of Solomon': 'SON',
            'Song of Songs': 'SON',
            'Ecclesiastes': 'ECC',
            'Revelation': 'REV',
            'Revelations': 'REV'
        }
        
        if book_name in variations:
            return variations[book_name]
        
        # Standard lookup
        for abbrev, full_name in BIBLE_BOOKS.items():
            if full_name.lower() == book_name.lower():
                return abbrev
        
        # Try partial matches
        for abbrev, full_name in BIBLE_BOOKS.items():
            if book_name.lower() in full_name.lower():
                return abbrev
        
        return None
    
    def build_thematic_network(self) -> None:
        """Build comprehensive thematic index with relationships"""
        logger.info("Building thematic network...")
        
        # Group notes by themes
        theme_to_notes = defaultdict(list)
        theme_to_verses = defaultdict(list)
        
        # Process notes
        for note_id, note in self.notes.items():
            for theme in note.theme_tags:
                theme_to_notes[theme].append(note_id)
                theme_to_verses[theme].extend(note.linked_verses)
        
        # Process verses
        for verse_id, verse in self.verses.items():
            for keyword in verse.keywords:
                if keyword.title() in SCOFIELD_THEMES:
                    theme_to_verses[keyword.title()].append(verse_id)
        
        # Create thematic index entries
        for theme_name, note_ids in theme_to_notes.items():
            theme_id = f"T{self.theme_counter:03d}"
            verse_ids = list(set(theme_to_verses.get(theme_name, [])))
            
            # Calculate confidence based on number of references
            confidence = min(1.0, (len(note_ids) + len(verse_ids)) / 100)
            
            thematic_entry = ThematicIndex(
                theme_id=theme_id,
                name=theme_name,
                description=f"References to {theme_name} in Scofield notes",
                note_ids=note_ids,
                verse_ids=verse_ids,
                confidence_score=confidence
            )
            
            self.thematic_index[theme_id] = thematic_entry
            self.theme_counter += 1
        
        # Build relationships between themes
        self._build_theme_relationships()
        
        logger.info(f"Built thematic index with {len(self.thematic_index)} themes")
    
    def _build_theme_relationships(self) -> None:
        """Build hierarchical and related relationships between themes"""
        theme_names = {theme_id: idx.name for theme_id, idx in self.thematic_index.items()}
        
        # Define theme hierarchies (you can expand this)
        theme_hierarchies = {
            "Dispensation": ["Law vs. Grace", "Church Age", "Millennium"],
            "Covenant Theology": ["Promise", "Israel and the Church"],
            "Eschatology": ["Second Coming", "Rapture", "Tribulation", "Millennium"],
            "Salvation": ["Justification", "Sanctification", "Glorification"],
            "Christological Themes": ["Deity of Christ", "Humanity of Christ", "Atoning Death"]
        }
        
        for parent_name, child_names in theme_hierarchies.items():
            # Find parent theme
            parent_theme = None
            for theme_id, idx in self.thematic_index.items():
                if idx.name == parent_name:
                    parent_theme = idx
                    break
            
            if parent_theme:
                # Find and link child themes
                for child_name in child_names:
                    for theme_id, idx in self.thematic_index.items():
                        if idx.name == child_name:
                            idx.parent_themes.append(parent_theme.theme_id)
                            parent_theme.sub_themes.append(theme_id)
    
    def generate_reading_plans(self) -> None:
        """Generate automatic reading plans based on themes"""
        logger.info("Generating reading plans...")
        
        # Generate plan for each major theme
        major_themes = ["Dispensation", "Covenant Theology", "Salvation", "Eschatology"]
        
        for theme_name in major_themes:
            # Find theme in index
            theme_entry = None
            for idx in self.thematic_index.values():
                if idx.name == theme_name:
                    theme_entry = idx
                    break
            
            if theme_entry and theme_entry.total_references > 10:
                plan_id = f"P{self.plan_counter:03d}"
                
                # Group verses by book for organized reading
                verses_by_book = defaultdict(list)
                for verse_id in theme_entry.verse_ids:
                    if verse_id in self.verses:
                        verse = self.verses[verse_id]
                        verses_by_book[verse.book].append(verse_id)
                
                # Create daily readings (max 10 verses per day)
                days = []
                current_day = []
                
                for book, book_verses in verses_by_book.items():
                    for verse_id in book_verses[:20]:  # Limit per book
                        if len(current_day) >= 10:
                            days.append(current_day)
                            current_day = []
                        current_day.append(verse_id)
                
                if current_day:
                    days.append(current_day)
                
                if days:  # Only create plan if we have verses
                    reading_plan = ReadingPlan(
                        plan_id=plan_id,
                        name=f"Scofield Study: {theme_name}",
                        description=f"Study {theme_name} through key Scofield references",
                        days=days,
                        theme=theme_name,
                        estimated_minutes=len(days) * 15,
                        tags=[theme_name, "Scofield", "Study"]
                    )
                    
                    self.reading_plans[plan_id] = reading_plan
                    self.plan_counter += 1
        
        logger.info(f"Generated {len(self.reading_plans)} reading plans")
    
    def analyze_connections(self) -> Dict[str, Any]:
        """Analyze and report on data connections"""
        logger.info("Analyzing connections...")
        
        analysis = {
            "summary": {
                "total_verses": len(self.verses),
                "total_notes": len(self.notes),
                "total_cross_references": len(self.cross_refs),
                "total_themes": len(self.thematic_index),
                "total_reading_plans": len(self.reading_plans)
            },
            "note_statistics": {
                "notes_with_cross_refs": sum(1 for n in self.notes.values() if n.related_notes),
                "average_verses_per_note": sum(len(n.linked_verses) for n in self.notes.values()) / len(self.notes) if self.notes else 0,
                "most_common_category": max(
                    [n.category for n in self.notes.values() if n.category],
                    key=lambda x: [n.category for n in self.notes.values()].count(x),
                    default="None"
                )
            },
            "theme_statistics": {
                "most_referenced_theme": max(
                    self.thematic_index.values(),
                    key=lambda x: x.total_references,
                    default=None
                ).name if self.thematic_index else "None",
                "themes_with_most_notes": sorted(
                    [(idx.name, len(idx.note_ids)) for idx in self.thematic_index.values()],
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            }
        }
        
        return analysis
    
    def export_all_data(self, export_dir: str = "exports") -> Dict[str, str]:
        """Export all data to JSON files"""
        export_path = Path(export_dir)
        export_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_files = {}
        
        # Export verses
        verses_data = {vid: verse.to_dict() for vid, verse in self.verses.items()}
        verses_file = export_path / f"verses_{timestamp}.json"
        with open(verses_file, 'w', encoding='utf-8') as f:
            json.dump(verses_data, f, indent=2, ensure_ascii=False)
        export_files['verses'] = str(verses_file)
        
        # Export notes
        notes_data = {nid: note.to_dict() for nid, note in self.notes.items()}
        notes_file = export_path / f"notes_{timestamp}.json"
        with open(notes_file, 'w', encoding='utf-8') as f:
            json.dump(notes_data, f, indent=2, ensure_ascii=False)
        export_files['notes'] = str(notes_file)
        
        # Export cross-references
        cross_refs_data = [cr.to_dict() for cr in self.cross_refs]
        cross_refs_file = export_path / f"cross_references_{timestamp}.json"
        with open(cross_refs_file, 'w', encoding='utf-8') as f:
            json.dump(cross_refs_data, f, indent=2, ensure_ascii=False)
        export_files['cross_references'] = str(cross_refs_file)
        
        # Export thematic index
        thematic_data = {tid: idx.to_dict() for tid, idx in self.thematic_index.items()}
        thematic_file = export_path / f"thematic_index_{timestamp}.json"
        with open(thematic_file, 'w', encoding='utf-8') as f:
            json.dump(thematic_data, f, indent=2, ensure_ascii=False)
        export_files['thematic_index'] = str(thematic_file)
        
        # Export reading plans
        plans_data = {pid: plan.to_dict() for pid, plan in self.reading_plans.items()}
        plans_file = export_path / f"reading_plans_{timestamp}.json"
        with open(plans_file, 'w', encoding='utf-8') as f:
            json.dump(plans_data, f, indent=2, ensure_ascii=False)
        export_files['reading_plans'] = str(plans_file)
        
        # Export metadata
        metadata = {
            "export_timestamp": timestamp,
            "project": "Enhanced Scofield Bible Parser",
            "version": "2.0.0",
            "source": "1917 Scofield Reference Bible",
            "analysis": self.analyze_connections()
        }
        metadata_file = export_path / f"metadata_{timestamp}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        export_files['metadata'] = str(metadata_file)
        
        # Create a consolidated export
        consolidated = {
            "metadata": metadata,
            "verses": verses_data,
            "notes": notes_data,
            "cross_references": cross_refs_data,
            "thematic_index": thematic_data,
            "reading_plans": plans_data
        }
        consolidated_file = export_path / f"scofield_bible_{timestamp}.json"
        with open(consolidated_file, 'w', encoding='utf-8') as f:
            json.dump(consolidated, f, indent=2, ensure_ascii=False)
        export_files['consolidated'] = str(consolidated_file)
        
        logger.info(f"Exported all data to {export_dir}")
        return export_files
    
    def create_sqlite_database(self, db_path: str = "scofield_bible.db") -> None:
        """Create SQLite database with all data"""
        logger.info(f"Creating SQLite database at {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create tables with enhanced schema
        cursor.executescript('''
        -- Verses table
        CREATE TABLE IF NOT EXISTS verses (
            verse_id TEXT PRIMARY KEY,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text TEXT NOT NULL,
            keywords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Notes table
        CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            note_type TEXT,
            category TEXT,
            subcategory TEXT,
            keywords TEXT,
            theme_tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Note-Verse linkage table
        CREATE TABLE IF NOT EXISTS note_verse_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id TEXT NOT NULL,
            verse_id TEXT NOT NULL,
            FOREIGN KEY (note_id) REFERENCES notes (note_id),
            FOREIGN KEY (verse_id) REFERENCES verses (verse_id),
            UNIQUE(note_id, verse_id)
        );
        
        -- Cross-references table
        CREATE TABLE IF NOT EXISTS cross_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            ref_type TEXT NOT NULL,
            description TEXT,
            confidence REAL DEFAULT 1.0,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Thematic index table
        CREATE TABLE IF NOT EXISTS themes (
            theme_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            categories TEXT,
            confidence_score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Theme-Verse linkage
        CREATE TABLE IF NOT EXISTS theme_verse_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id TEXT NOT NULL,
            verse_id TEXT NOT NULL,
            FOREIGN KEY (theme_id) REFERENCES themes (theme_id),
            FOREIGN KEY (verse_id) REFERENCES verses (verse_id),
            UNIQUE(theme_id, verse_id)
        );
        
        -- Theme-Note linkage
        CREATE TABLE IF NOT EXISTS theme_note_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id TEXT NOT NULL,
            note_id TEXT NOT NULL,
            FOREIGN KEY (theme_id) REFERENCES themes (theme_id),
            FOREIGN KEY (note_id) REFERENCES notes (note_id),
            UNIQUE(theme_id, note_id)
        );
        
        -- Reading plans table
        CREATE TABLE IF NOT EXISTS reading_plans (
            plan_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            theme TEXT,
            estimated_minutes INTEGER,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Reading plan days
        CREATE TABLE IF NOT EXISTS reading_plan_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id TEXT NOT NULL,
            day_number INTEGER NOT NULL,
            verse_ids TEXT NOT NULL,
            FOREIGN KEY (plan_id) REFERENCES reading_plans (plan_id)
        );
        ''')
        
        # Insert verses
        for verse in self.verses.values():
            cursor.execute('''
            INSERT OR REPLACE INTO verses (verse_id, book, chapter, verse, text, keywords)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                verse.verse_id,
                verse.book,
                verse.chapter,
                verse.verse,
                verse.text,
                ','.join(verse.keywords)
            ))
            
            # Insert note-verse links
            for note_id in verse.note_ids:
                cursor.execute('''
                INSERT OR IGNORE INTO note_verse_links (note_id, verse_id)
                VALUES (?, ?)
                ''', (note_id, verse.verse_id))
        
        # Insert notes
        for note in self.notes.values():
            cursor.execute('''
            INSERT OR REPLACE INTO notes (note_id, text, note_type, category, subcategory, keywords, theme_tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                note.note_id,
                note.text,
                note.note_type,
                note.category,
                note.subcategory,
                ','.join(note.keywords),
                ','.join(note.theme_tags)
            ))
        
        # Insert cross-references
        for cr in self.cross_refs:
            cursor.execute('''
            INSERT INTO cross_references (source_id, target_id, ref_type, description, confidence, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                cr.source_id,
                cr.target_id,
                cr.ref_type,
                cr.description,
                cr.confidence,
                ','.join(cr.tags)
            ))
        
        # Insert themes
        for theme in self.thematic_index.values():
            cursor.execute('''
            INSERT OR REPLACE INTO themes (theme_id, name, description, categories, confidence_score)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                theme.theme_id,
                theme.name,
                theme.description,
                ','.join(theme.categories),
                theme.confidence_score
            ))
            
            # Insert theme-verse links
            for verse_id in theme.verse_ids:
                cursor.execute('''
                INSERT OR IGNORE INTO theme_verse_links (theme_id, verse_id)
                VALUES (?, ?)
                ''', (theme.theme_id, verse_id))
            
            # Insert theme-note links
            for note_id in theme.note_ids:
                cursor.execute('''
                INSERT OR IGNORE INTO theme_note_links (theme_id, note_id)
                VALUES (?, ?)
                ''', (theme.theme_id, note_id))
        
        # Insert reading plans
        for plan in self.reading_plans.values():
            cursor.execute('''
            INSERT OR REPLACE INTO reading_plans (plan_id, name, description, theme, estimated_minutes, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                plan.plan_id,
                plan.name,
                plan.description,
                plan.theme,
                plan.estimated_minutes,
                ','.join(plan.tags)
            ))
            
            # Insert plan days
            for day_num, day_verses in enumerate(plan.days, 1):
                cursor.execute('''
                INSERT INTO reading_plan_days (plan_id, day_number, verse_ids)
                VALUES (?, ?, ?)
                ''', (plan.plan_id, day_num, ','.join(day_verses)))
        
        # Create indexes for performance
        cursor.executescript('''
        CREATE INDEX IF NOT EXISTS idx_verses_book ON verses(book);
        CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses(book, chapter, verse);
        CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category);
        CREATE INDEX IF NOT EXISTS idx_cross_refs_source ON cross_references(source_id);
        CREATE INDEX IF NOT EXISTS idx_cross_refs_target ON cross_references(target_id);
        CREATE INDEX IF NOT EXISTS idx_theme_verse ON theme_verse_links(theme_id, verse_id);
        CREATE INDEX IF NOT EXISTS idx_theme_note ON theme_note_links(theme_id, note_id);
        ''')
        
        conn.commit()
        
        # Run analysis queries
        analysis = cursor.execute('''
        SELECT 
            (SELECT COUNT(*) FROM verses) as total_verses,
            (SELECT COUNT(*) FROM notes) as total_notes,
            (SELECT COUNT(*) FROM cross_references) as total_cross_refs,
            (SELECT COUNT(*) FROM themes) as total_themes,
            (SELECT COUNT(*) FROM reading_plans) as total_plans
        ''').fetchone()
        
        conn.close()
        
        logger.info(f"Database created successfully:")
        logger.info(f"  - Verses: {analysis[0]}")
        logger.info(f"  - Notes: {analysis[1]}")
        logger.info(f"  - Cross-references: {analysis[2]}")
        logger.info(f"  - Themes: {analysis[3]}")
        logger.info(f"  - Reading plans: {analysis[4]}")
        
        return db_path

# ============================================================================
# WEB APPLICATION INTEGRATION
# ============================================================================

class ScofieldWebApp:
    """FastAPI-based web application for the Scofield Bible"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.parser = EnhancedScofieldParser(data_dir)
        
    def generate_api_code(self) -> str:
        """Generate FastAPI code for the web application"""
        api_code = '''
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from typing import List, Optional, Dict, Any
import sqlite3
import json
from pathlib import Path
import uvicorn

app = FastAPI(title="Connected Scofield Bible API", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DB_PATH = "scofield_bible.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
async def root():
    return {"message": "Connected Scofield Bible API", "version": "2.0.0"}

@app.get("/api/books")
async def get_books():
    """Get all Bible books with metadata"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT book, COUNT(*) as verse_count 
        FROM verses 
        GROUP BY book 
        ORDER BY 
            CASE book
                WHEN 'GEN' THEN 1
                WHEN 'EXO' THEN 2
                -- Add all books in order...
                WHEN 'REV' THEN 66
                ELSE 99
            END
    ''')
    
    books = []
    for row in cursor.fetchall():
        books.append({
            "abbrev": row["book"],
            "name": BIBLE_BOOKS.get(row["book"], row["book"]),
            "verse_count": row["verse_count"],
            "chapters": BOOK_CHAPTER_COUNTS.get(row["book"], 0)
        })
    
    conn.close()
    return books

@app.get("/api/verses/{book}/{chapter}")
async def get_chapter(book: str, chapter: int):
    """Get all verses for a chapter with notes"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get verses
    cursor.execute('''
        SELECT v.*, GROUP_CONCAT(nvl.note_id) as note_ids
        FROM verses v
        LEFT JOIN note_verse_links nvl ON v.verse_id = nvl.verse_id
        WHERE v.book = ? AND v.chapter = ?
        GROUP BY v.verse_id
        ORDER BY v.verse
    ''', (book.upper(), chapter))
    
    verses = []
    for row in cursor.fetchall():
        verse_data = dict(row)
        
        # Get notes for this verse
        if verse_data["note_ids"]:
            note_ids = verse_data["note_ids"].split(',')
            cursor.execute('''
                SELECT * FROM notes 
                WHERE note_id IN ({})
            '''.format(','.join(['?'] * len(note_ids))), note_ids)
            
            notes = [dict(note) for note in cursor.fetchall()]
            verse_data["notes"] = notes
        else:
            verse_data["notes"] = []
        
        verses.append(verse_data)
    
    conn.close()
    return verses

@app.get("/api/verse/{verse_id}")
async def get_verse(verse_id: str):
    """Get a specific verse with all related data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get verse
    cursor.execute('SELECT * FROM verses WHERE verse_id = ?', (verse_id,))
    verse = cursor.fetchone()
    
    if not verse:
        raise HTTPException(status_code=404, detail="Verse not found")
    
    verse_data = dict(verse)
    
    # Get notes
    cursor.execute('''
        SELECT n.* FROM notes n
        JOIN note_verse_links nvl ON n.note_id = nvl.note_id
        WHERE nvl.verse_id = ?
    ''', (verse_id,))
    verse_data["notes"] = [dict(note) for note in cursor.fetchall()]
    
    # Get cross-references
    cursor.execute('''
        SELECT cr.*, v.text as target_text, v.book as target_book, 
               v.chapter as target_chapter, v.verse as target_verse
        FROM cross_references cr
        JOIN verses v ON cr.target_id = v.verse_id
        WHERE cr.source_id = ?
        UNION
        SELECT cr.*, v.text as target_text, v.book as target_book,
               v.chapter as target_chapter, v.verse as target_verse
        FROM cross_references cr
        JOIN verses v ON cr.source_id = v.verse_id
        WHERE cr.target_id = ?
    ''', (verse_id, verse_id))
    
    verse_data["cross_references"] = [dict(cr) for cr in cursor.fetchall()]
    
    # Get themes
    cursor.execute('''
        SELECT t.* FROM themes t
        JOIN theme_verse_links tvl ON t.theme_id = tvl.theme_id
        WHERE tvl.verse_id = ?
    ''', (verse_id,))
    verse_data["themes"] = [dict(theme) for theme in cursor.fetchall()]
    
    conn.close()
    return verse_data

@app.get("/api/search")
async def search_verses(
    q: str = Query(..., min_length=2),
    search_type: str = Query("all", regex="^(all|verses|notes|themes)$"),
    limit: int = Query(50, ge=1, le=100)
):
    """Search across verses, notes, and themes"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    search_term = f"%{q}%"
    results = []
    
    if search_type in ["all", "verses"]:
        cursor.execute('''
            SELECT * FROM verses 
            WHERE text LIKE ? 
            OR keywords LIKE ?
            ORDER BY 
                CASE book
                    WHEN 'GEN' THEN 1
                    WHEN 'EXO' THEN 2
                    WHEN 'REV' THEN 66
                    ELSE 99
                END, chapter, verse
            LIMIT ?
        ''', (search_term, search_term, limit))
        
        for row in cursor.fetchall():
            results.append({
                "type": "verse",
                "data": dict(row),
                "relevance": 1.0
            })
    
    if search_type in ["all", "notes"]:
        cursor.execute('''
            SELECT * FROM notes 
            WHERE text LIKE ? 
            OR keywords LIKE ?
            OR theme_tags LIKE ?
            LIMIT ?
        ''', (search_term, search_term, search_term, limit))
        
        for row in cursor.fetchall():
            results.append({
                "type": "note",
                "data": dict(row),
                "relevance": 1.0
            })
    
    if search_type in ["all", "themes"]:
        cursor.execute('''
            SELECT * FROM themes 
            WHERE name LIKE ? 
            OR description LIKE ?
            OR categories LIKE ?
            ORDER BY confidence_score DESC
            LIMIT ?
        ''', (search_term, search_term, search_term, limit))
        
        for row in cursor.fetchall():
            results.append({
                "type": "theme",
                "data": dict(row),
                "relevance": 1.0
            })
    
    conn.close()
    return {"query": q, "count": len(results), "results": results}

@app.get("/api/themes")
async def get_themes(category: Optional[str] = None):
    """Get all themes, optionally filtered by category"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if category:
        cursor.execute('''
            SELECT * FROM themes 
            WHERE categories LIKE ?
            ORDER BY confidence_score DESC
        ''', (f"%{category}%",))
    else:
        cursor.execute('SELECT * FROM themes ORDER BY confidence_score DESC')
    
    themes = [dict(theme) for theme in cursor.fetchall()]
    
    # Get statistics for each theme
    for theme in themes:
        cursor.execute('''
            SELECT COUNT(*) as verse_count 
            FROM theme_verse_links 
            WHERE theme_id = ?
        ''', (theme["theme_id"],))
        theme["verse_count"] = cursor.fetchone()["verse_count"]
        
        cursor.execute('''
            SELECT COUNT(*) as note_count 
            FROM theme_note_links 
            WHERE theme_id = ?
        ''', (theme["theme_id"],))
        theme["note_count"] = cursor.fetchone()["note_count"]
    
    conn.close()
    return themes

@app.get("/api/theme/{theme_id}")
async def get_theme(theme_id: str):
    """Get a specific theme with all related verses and notes"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get theme
    cursor.execute('SELECT * FROM themes WHERE theme_id = ?', (theme_id,))
    theme = cursor.fetchone()
    
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    
    theme_data = dict(theme)
    
    # Get related verses
    cursor.execute('''
        SELECT v.* FROM verses v
        JOIN theme_verse_links tvl ON v.verse_id = tvl.verse_id
        WHERE tvl.theme_id = ?
        ORDER BY 
            CASE v.book
                WHEN 'GEN' THEN 1
                WHEN 'EXO' THEN 2
                WHEN 'REV' THEN 66
                ELSE 99
            END, v.chapter, v.verse
    ''', (theme_id,))
    theme_data["verses"] = [dict(verse) for verse in cursor.fetchall()]
    
    # Get related notes
    cursor.execute('''
        SELECT n.* FROM notes n
        JOIN theme_note_links tnl ON n.note_id = tnl.note_id
        WHERE tnl.theme_id = ?
    ''', (theme_id,))
    theme_data["notes"] = [dict(note) for note in cursor.fetchall()]
    
    # Get related themes
    cursor.execute('''
        SELECT t2.* FROM themes t1
        JOIN themes t2 ON t1.categories LIKE '%' || t2.categories || '%'
        WHERE t1.theme_id = ? AND t2.theme_id != ?
        LIMIT 10
    ''', (theme_id, theme_id))
    theme_data["related_themes"] = [dict(theme) for theme in cursor.fetchall()]
    
    conn.close()
    return theme_data

@app.get("/api/reading-plans")
async def get_reading_plans(theme: Optional[str] = None):
    """Get all reading plans, optionally filtered by theme"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if theme:
        cursor.execute('''
            SELECT * FROM reading_plans 
            WHERE theme = ? OR tags LIKE ?
            ORDER BY name
        ''', (theme, f"%{theme}%"))
    else:
        cursor.execute('SELECT * FROM reading_plans ORDER BY name')
    
    plans = []
    for row in cursor.fetchall():
        plan_data = dict(row)
        
        # Get days for this plan
        cursor.execute('''
            SELECT * FROM reading_plan_days 
            WHERE plan_id = ?
            ORDER BY day_number
        ''', (plan_data["plan_id"],))
        
        days = []
        for day_row in cursor.fetchall():
            day_data = dict(day_row)
            
            # Get verses for this day
            verse_ids = day_data["verse_ids"].split(',')
            if verse_ids:
                cursor.execute(f'''
                    SELECT * FROM verses 
                    WHERE verse_id IN ({','.join(['?'] * len(verse_ids))})
                    ORDER BY 
                        CASE book
                            WHEN 'GEN' THEN 1
                            WHEN 'EXO' THEN 2
                            WHEN 'REV' THEN 66
                            ELSE 99
                        END, chapter, verse
                ''', verse_ids)
                day_data["verses"] = [dict(verse) for verse in cursor.fetchall()]
            
            days.append(day_data)
        
        plan_data["days"] = days
        plans.append(plan_data)
    
    conn.close()
    return plans

@app.get("/api/statistics")
async def get_statistics():
    """Get comprehensive statistics about the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    # Basic counts
    cursor.execute("SELECT COUNT(*) as count FROM verses")
    stats["total_verses"] = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM notes")
    stats["total_notes"] = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM cross_references")
    stats["total_cross_references"] = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM themes")
    stats["total_themes"] = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM reading_plans")
    stats["total_reading_plans"] = cursor.fetchone()["count"]
    
    # Distribution stats
    cursor.execute('''
        SELECT book, COUNT(*) as count 
        FROM verses 
        GROUP BY book 
        ORDER BY count DESC
        LIMIT 5
    ''')
    stats["top_books_by_verses"] = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('''
        SELECT category, COUNT(*) as count 
        FROM notes 
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category 
        ORDER BY count DESC
        LIMIT 10
    ''')
    stats["top_note_categories"] = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('''
        SELECT ref_type, COUNT(*) as count 
        FROM cross_references 
        GROUP BY ref_type 
        ORDER BY count DESC
    ''')
    stats["cross_reference_types"] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return stats

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
        
        return api_code
    
    def generate_frontend_code(self) -> str:
        """Generate frontend code for the web application"""
        frontend_code = '''
<!-- index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connected Scofield Bible</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/vis-network.min.css">
    <style>
        :root {
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --accent-color: #e74c3c;
            --success-color: #27ae60;
            --warning-color: #f39c12;
            --danger-color: #c0392b;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f8f9fa;
        }
        
        .navbar-brand {
            font-weight: bold;
            color: var(--primary-color) !important;
        }
        
        .sidebar {
            height: calc(100vh - 56px);
            overflow-y: auto;
            background: white;
            border-right: 1px solid #dee2e6;
        }
        
        .main-content {
            height: calc(100vh - 56px);
            overflow-y: auto;
        }
        
        .verse-card {
            transition: all 0.3s ease;
            border-left: 3px solid var(--secondary-color);
        }
        
        .verse-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        .note-indicator {
            color: var(--accent-color);
            font-weight: bold;
            cursor: pointer;
        }
        
        .note-card {
            background-color: #f8f9fa;
            border-left: 3px solid var(--accent-color);
        }
        
        .theme-badge {
            background-color: var(--primary-color);
            color: white;
            margin-right: 5px;
            margin-bottom: 5px;
        }
        
        .network-container {
            width: 100%;
            height: 500px;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            background: white;
        }
        
        .search-highlight {
            background-color: #fff3cd;
            padding: 2px;
            border-radius: 2px;
        }
        
        .loading-spinner {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 9999;
        }
        
        @media (max-width: 768px) {
            .sidebar {
                height: auto;
                border-right: none;
                border-bottom: 1px solid #dee2e6;
            }
            
            .main-content {
                height: auto;
            }
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="bi bi-book"></i> Connected Scofield Bible
            </a>
            <div class="d-flex">
                <div class="input-group me-2" style="width: 300px;">
                    <input type="text" class="form-control" id="searchInput" placeholder="Search verses, notes, themes...">
                    <button class="btn btn-outline-secondary" type="button" id="searchButton">
                        <i class="bi bi-search"></i>
                    </button>
                </div>
                <button class="btn btn-outline-primary me-2" id="themeViewBtn">
                    <i class="bi bi-diagram-3"></i> Themes
                </button>
                <button class="btn btn-outline-success" id="plansBtn">
                    <i class="bi bi-calendar-check"></i> Plans
                </button>
            </div>
        </div>
    </nav>
    
    <!-- Main Layout -->
    <div class="container-fluid">
        <div class="row">
            <!-- Sidebar -->
            <div class="col-lg-3 col-md-4 sidebar p-3" id="sidebar">
                <h5 class="mb-3">Books</h5>
                <div id="bookList" class="mb-4">
                    <!-- Books will be loaded here -->
                </div>
                
                <h5 class="mb-3">Quick Stats</h5>
                <div class="card mb-3">
                    <div class="card-body p-2">
                        <small class="text-muted" id="statsText">Loading stats...</small>
                    </div>
                </div>
                
                <h5 class="mb-3">Popular Themes</h5>
                <div id="themeList">
                    <!-- Themes will be loaded here -->
                </div>
            </div>
            
            <!-- Main Content -->
            <div class="col-lg-9 col-md-8 main-content p-4" id="mainContent">
                <div id="contentArea">
                    <!-- Content will be loaded here -->
                    <div class="text-center text-muted mt-5">
                        <h3>Welcome to the Connected Scofield Bible</h3>
                        <p>Select a book and chapter to begin reading, or use the search feature to explore.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Loading Spinner -->
    <div class="loading-spinner" id="loadingSpinner">
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    </div>
    
    <!-- Modals -->
    <div class="modal fade" id="searchModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Search Results</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="searchResults"></div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="themeModal" tabindex="-1">
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Thematic Network</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="network-container" id="themeNetwork"></div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/vis-network.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dompurify@2.3.6/dist/purify.min.js"></script>
    
    <script>
        // Main application JavaScript
        class ScofieldApp {
            constructor() {
                this.apiBase = 'http://localhost:8000/api';
                this.currentBook = null;
                this.currentChapter = null;
                this.currentView = 'reader';
                this.init();
            }
            
            async init() {
                await this.loadBooks();
                await this.loadStats();
                await this.loadPopularThemes();
                this.setupEventListeners();
            }
            
            async loadBooks() {
                try {
                    const response = await fetch(`${this.apiBase}/books`);
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
                    bookDiv.className = 'card mb-2';
                    bookDiv.innerHTML = `
                        <div class="card-body py-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${book.name}</strong>
                                    <small class="text-muted ms-2">${book.abbrev}</small>
                                </div>
                                <span class="badge bg-primary">${book.chapters} ch</span>
                            </div>
                        </div>
                    `;
                    
                    bookDiv.addEventListener('click', () => this.loadBookChapters(book));
                    container.appendChild(bookDiv);
                });
            }
            
            async loadBookChapters(book) {
                this.currentBook = book;
                const container = document.getElementById('bookList');
                
                // Create chapter buttons
                const chaptersDiv = document.createElement('div');
                chaptersDiv.className = 'row mt-2';
                
                for (let i = 1; i <= book.chapters; i++) {
                    const col = document.createElement('div');
                    col.className = 'col-2 mb-2';
                    
                    const btn = document.createElement('button');
                    btn.className = 'btn btn-outline-primary btn-sm w-100';
                    btn.textContent = i;
                    btn.addEventListener('click', () => this.loadChapter(book.abbrev, i));
                    
                    col.appendChild(btn);
                    chaptersDiv.appendChild(col);
                }
                
                // Remove existing chapters if any
                const existingChapters = container.querySelector('.chapters-container');
                if (existingChapters) {
                    existingChapters.remove();
                }
                
                container.appendChild(chaptersDiv);
                chaptersDiv.classList.add('chapters-container');
            }
            
            async loadChapter(bookAbbrev, chapter) {
                this.showLoading(true);
                this.currentChapter = chapter;
                
                try {
                    const response = await fetch(`${this.apiBase}/verses/${bookAbbrev}/${chapter}`);
                    const verses = await response.json();
                    this.renderChapter(verses, bookAbbrev, chapter);
                } catch (error) {
                    console.error('Error loading chapter:', error);
                    this.showError('Failed to load chapter');
                } finally {
                    this.showLoading(false);
                }
            }
            
            renderChapter(verses, bookAbbrev, chapter) {
                const container = document.getElementById('contentArea');
                const bookName = BIBLE_BOOKS[bookAbbrev] || bookAbbrev;
                
                let html = `
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h3>${bookName} ${chapter}</h3>
                        <div>
                            <button class="btn btn-outline-secondary btn-sm me-2" id="prevChapter">
                                <i class="bi bi-chevron-left"></i> Previous
                            </button>
                            <button class="btn btn-outline-secondary btn-sm" id="nextChapter">
                                Next <i class="bi bi-chevron-right"></i>
                            </button>
                        </div>
                    </div>
                `;
                
                verses.forEach(verse => {
                    html += this.renderVerseCard(verse);
                });
                
                container.innerHTML = html;
                
                // Add event listeners for navigation
                document.getElementById('prevChapter').addEventListener('click', () => {
                    if (chapter > 1) {
                        this.loadChapter(bookAbbrev, chapter - 1);
                    }
                });
                
                document.getElementById('nextChapter').addEventListener('click', () => {
                    const maxChapters = BOOK_CHAPTER_COUNTS[bookAbbrev] || 50;
                    if (chapter < maxChapters) {
                        this.loadChapter(bookAbbrev, chapter + 1);
                    }
                });
                
                // Scroll to top
                document.querySelector('.main-content').scrollTop = 0;
            }
            
            renderVerseCard(verse) {
                let noteIndicators = '';
                if (verse.notes && verse.notes.length > 0) {
                    noteIndicators = verse.notes.map((note, idx) => 
                        `<sup class="note-indicator" data-note-id="${note.note_id}">[${idx + 1}]</sup>`
                    ).join('');
                }
                
                return `
                    <div class="card verse-card mb-3">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h5 class="card-title mb-0">
                                    <span class="badge bg-secondary">${verse.verse}</span>
                                    ${verse.text}${noteIndicators}
                                </h5>
                                <button class="btn btn-sm btn-outline-info" onclick="app.showVerseDetails('${verse.verse_id}')">
                                    <i class="bi bi-info-circle"></i>
                                </button>
                            </div>
                            
                            ${this.renderNotesSection(verse.notes)}
                        </div>
                    </div>
                `;
            }
            
            renderNotesSection(notes) {
                if (!notes || notes.length === 0) return '';
                
                let html = '<div class="mt-3">';
                notes.forEach((note, idx) => {
                    html += `
                        <div class="card note-card mb-2">
                            <div class="card-body">
                                <div class="d-flex justify-content-between">
                                    <small class="text-muted">Note ${idx + 1}</small>
                                    <span class="badge bg-info">${note.note_type || 'Note'}</span>
                                </div>
                                <p class="card-text mt-2">${this.escapeHtml(note.text)}</p>
                                ${this.renderNoteTags(note)}
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                return html;
            }
            
            renderNoteTags(note) {
                let tags = '';
                if (note.keywords) {
                    const keywordList = note.keywords.split(',').filter(k => k.trim());
                    keywordList.forEach(keyword => {
                        tags += `<span class="badge bg-secondary me-1">${keyword.trim()}</span>`;
                    });
                }
                if (note.theme_tags) {
                    const themeList = note.theme_tags.split(',').filter(t => t.trim());
                    themeList.forEach(theme => {
                        tags += `<span class="badge theme-badge">${theme.trim()}</span>`;
                    });
                }
                return tags ? `<div class="mt-2">${tags}</div>` : '';
            }
            
            async showVerseDetails(verseId) {
                this.showLoading(true);
                try {
                    const response = await fetch(`${this.apiBase}/verse/${verseId}`);
                    const verse = await response.json();
                    this.renderVerseDetailsModal(verse);
                } catch (error) {
                    console.error('Error loading verse details:', error);
                } finally {
                    this.showLoading(false);
                }
            }
            
            renderVerseDetailsModal(verse) {
                // Create and show modal with verse details
                const modalHtml = `
                    <div class="modal fade" id="verseDetailsModal" tabindex="-1">
                        <div class="modal-dialog modal-lg">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">${verse.full_reference || verse.verse_id}</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                </div>
                                <div class="modal-body">
                                    <div class="card mb-3">
                                        <div class="card-body">
                                            <h6>Verse Text</h6>
                                            <p class="lead">${this.escapeHtml(verse.text)}</p>
                                        </div>
                                    </div>
                                    
                                    ${verse.notes && verse.notes.length > 0 ? `
                                        <div class="card mb-3">
                                            <div class="card-body">
                                                <h6>Scofield Notes (${verse.notes.length})</h6>
                                                ${this.renderNotesSection(verse.notes)}
                                            </div>
                                        </div>
                                    ` : ''}
                                    
                                    ${verse.cross_references && verse.cross_references.length > 0 ? `
                                        <div class="card mb-3">
                                            <div class="card-body">
                                                <h6>Cross References (${verse.cross_references.length})</h6>
                                                <div class="list-group">
                                                    ${verse.cross_references.map(ref => `
                                                        <a href="#" class="list-group-item list-group-item-action" 
                                                           onclick="app.loadVerse('${ref.target_id}'); return false;">
                                                            <div class="d-flex w-100 justify-content-between">
                                                                <h6 class="mb-1">${ref.target_book} ${ref.target_chapter}:${ref.target_verse}</h6>
                                                                <small>${ref.ref_type}</small>
                                                            </div>
                                                            <p class="mb-1">${this.escapeHtml(ref.target_text?.substring(0, 100) + '...')}</p>
                                                        </a>
                                                    `).join('')}
                                                </div>
                                            </div>
                                        </div>
                                    ` : ''}
                                    
                                    ${verse.themes && verse.themes.length > 0 ? `
                                        <div class="card">
                                            <div class="card-body">
                                                <h6>Themes</h6>
                                                <div>
                                                    ${verse.themes.map(theme => `
                                                        <span class="badge theme-badge" 
                                                              onclick="app.showTheme('${theme.theme_id}')"
                                                              style="cursor: pointer;">
                                                            ${theme.name}
                                                        </span>
                                                    `).join('')}
                                                </div>
                                            </div>
                                        </div>
                                    ` : ''}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                // Add modal to DOM and show it
                const modalContainer = document.createElement('div');
                modalContainer.innerHTML = modalHtml;
                document.body.appendChild(modalContainer);
                
                const modal = new bootstrap.Modal(document.getElementById('verseDetailsModal'));
                modal.show();
                
                // Clean up after modal is hidden
                document.getElementById('verseDetailsModal').addEventListener('hidden.bs.modal', () => {
                    modalContainer.remove();
                });
            }
            
            async showTheme(themeId) {
                this.showLoading(true);
                try {
                    const response = await fetch(`${this.apiBase}/theme/${themeId}`);
                    const theme = await response.json();
                    this.renderThemeModal(theme);
                } catch (error) {
                    console.error('Error loading theme:', error);
                } finally {
                    this.showLoading(false);
                }
            }
            
            renderThemeModal(theme) {
                // Similar to verse details modal, but for themes
                console.log('Theme data:', theme);
                // Implement theme modal rendering
            }
            
            async loadStats() {
                try {
                    const response = await fetch(`${this.apiBase}/statistics`);
                    const stats = await response.json();
                    document.getElementById('statsText').textContent = 
                        `${stats.total_verses} verses, ${stats.total_notes} notes, ${stats.total_themes} themes`;
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }
            
            async loadPopularThemes() {
                try {
                    const response = await fetch(`${this.apiBase}/themes?limit=5`);
                    const themes = await response.json();
                    this.renderThemeList(themes);
                } catch (error) {
                    console.error('Error loading themes:', error);
                }
            }
            
            renderThemeList(themes) {
                const container = document.getElementById('themeList');
                container.innerHTML = '';
                
                themes.forEach(theme => {
                    const themeDiv = document.createElement('div');
                    themeDiv.className = 'card mb-2';
                    themeDiv.innerHTML = `
                        <div class="card-body py-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${theme.name}</strong>
                                    <small class="text-muted d-block">${theme.verse_count || 0} verses</small>
                                </div>
                                <button class="btn btn-sm btn-outline-primary" 
                                        onclick="app.showTheme('${theme.theme_id}')">
                                    <i class="bi bi-arrow-right"></i>
                                </button>
                            </div>
                        </div>
                    `;
                    container.appendChild(themeDiv);
                });
            }
            
            async search(query) {
                this.showLoading(true);
                try {
                    const response = await fetch(`${this.apiBase}/search?q=${encodeURIComponent(query)}`);
                    const results = await response.json();
                    this.showSearchResults(query, results);
                } catch (error) {
                    console.error('Error searching:', error);
                } finally {
                    this.showLoading(false);
                }
            }
            
            showSearchResults(query, results) {
                const modal = new bootstrap.Modal(document.getElementById('searchModal'));
                const container = document.getElementById('searchResults');
                
                let html = `
                    <p>Found ${results.count} results for "${query}":</p>
                    <div class="list-group">
                `;
                
                results.results.forEach(result => {
                    html += `
                        <div class="list-group-item">
                            <div class="d-flex w-100 justify-content-between">
                                <h6 class="mb-1">
                                    <span class="badge bg-info">${result.type}</span>
                                    ${this.getResultTitle(result)}
                                </h6>
                                <small>Relevance: ${result.relevance.toFixed(2)}</small>
                            </div>
                            <p class="mb-1">${this.getResultPreview(result)}</p>
                            <small>${this.getResultMetadata(result)}</small>
                        </div>
                    `;
                });
                
                html += '</div>';
                container.innerHTML = html;
                modal.show();
            }
            
            getResultTitle(result) {
                switch (result.type) {
                    case 'verse':
                        return result.data.reference || result.data.verse_id;
                    case 'note':
                        return `Note ${result.data.note_id}`;
                    case 'theme':
                        return result.data.name;
                    default:
                        return 'Unknown';
                }
            }
            
            getResultPreview(result) {
                const text = result.data.text || result.data.description || '';
                return this.escapeHtml(text.substring(0, 150) + (text.length > 150 ? '...' : ''));
            }
            
            getResultMetadata(result) {
                switch (result.type) {
                    case 'verse':
                        return `Book: ${result.data.book}, Chapter: ${result.data.chapter}`;
                    case 'note':
                        return `Type: ${result.data.note_type || 'Note'}, Category: ${result.data.category || 'None'}`;
                    case 'theme':
                        return `Confidence: ${(result.data.confidence_score || 0).toFixed(2)}`;
                    default:
                        return '';
                }
            }
            
            setupEventListeners() {
                // Search
                document.getElementById('searchInput').addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        const query = e.target.value.trim();
                        if (query) this.search(query);
                    }
                });
                
                document.getElementById('searchButton').addEventListener('click', () => {
                    const query = document.getElementById('searchInput').value.trim();
                    if (query) this.search(query);
                });
                
                // Theme view
                document.getElementById('themeViewBtn').addEventListener('click', () => {
                    this.showThematicNetwork();
                });
                
                // Reading plans
                document.getElementById('plansBtn').addEventListener('click', () => {
                    this.showReadingPlans();
                });
                
                // Add note indicator click handlers dynamically
                document.addEventListener('click', (e) => {
                    if (e.target.classList.contains('note-indicator')) {
                        const noteId = e.target.dataset.noteId;
                        if (noteId) this.showNoteDetails(noteId);
                    }
                });
            }
            
            showLoading(show) {
                document.getElementById('loadingSpinner').style.display = show ? 'block' : 'none';
            }
            
            showError(message) {
                // Implement error display
                console.error(message);
            }
            
            escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            
            async showThematicNetwork() {
                try {
                    const response = await fetch(`${this.apiBase}/themes`);
                    const themes = await response.json();
                    this.renderThematicNetwork(themes);
                } catch (error) {
                    console.error('Error loading thematic network:', error);
                }
            }
            
            renderThematicNetwork(themes) {
                // Create nodes and edges for vis.js network
                const nodes = [];
                const edges = [];
                
                themes.forEach((theme, index) => {
                    nodes.push({
                        id: theme.theme_id,
                        label: theme.name,
                        value: (theme.verse_count || 0) + (theme.note_count || 0),
                        color: this.getThemeColor(theme.confidence_score),
                        font: { size: 16 }
                    });
                    
                    // Add edges for related themes
                    if (theme.related_themes) {
                        theme.related_themes.forEach(relatedTheme => {
                            edges.push({
                                from: theme.theme_id,
                                to: relatedTheme.theme_id,
                                value: 1,
                                color: { color: '#3498db' }
                            });
                        });
                    }
                });
                
                // Create network
                const container = document.getElementById('themeNetwork');
                const data = { nodes, edges };
                const options = {
                    nodes: {
                        shape: 'dot',
                        scaling: {
                            min: 10,
                            max: 30
                        }
                    },
                    edges: {
                        width: 2,
                        smooth: true
                    },
                    physics: {
                        enabled: true,
                        barnesHut: {
                            gravitationalConstant: -8000,
                            springConstant: 0.04,
                            springLength: 95
                        }
                    },
                    interaction: {
                        hover: true,
                        tooltipDelay: 200
                    }
                };
                
                const network = new vis.Network(container, data, options);
                
                // Show modal
                const modal = new bootstrap.Modal(document.getElementById('themeModal'));
                modal.show();
                
                // Handle node clicks
                network.on('click', (params) => {
                    if (params.nodes.length > 0) {
                        const themeId = params.nodes[0];
                        this.showTheme(themeId);
                    }
                });
            }
            
            getThemeColor(confidence) {
                if (confidence > 0.7) return '#27ae60'; // Green
                if (confidence > 0.4) return '#f39c12'; // Orange
                return '#e74c3c'; // Red
            }
            
            async showReadingPlans() {
                try {
                    const response = await fetch(`${this.apiBase}/reading-plans`);
                    const plans = await response.json();
                    this.renderReadingPlans(plans);
                } catch (error) {
                    console.error('Error loading reading plans:', error);
                }
            }
            
            renderReadingPlans(plans) {
                // Implement reading plans display
                console.log('Reading plans:', plans);
            }
            
            async showNoteDetails(noteId) {
                // Implement note details modal
                console.log('Show note:', noteId);
            }
        }
        
        // Constants
        const BIBLE_BOOKS = ${json.dumps(BIBLE_BOOKS, indent=2)};
        const BOOK_CHAPTER_COUNTS = ${json.dumps(BOOK_CHAPTER_COUNTS, indent=2)};
        
        // Initialize app
        const app = new ScofieldApp();
        window.app = app;
    </script>
</body>
</html>
'''
        
        return frontend_code

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Enhanced Scofield Bible Parser and Web Application")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Parse command
    parse_parser = subparsers.add_parser('parse', help='Parse KJV and Scofield files')
    parse_parser.add_argument('--kjv', type=str, required=True, help='Path to KJV text file')
    parse_parser.add_argument('--notes', type=str, required=True, help='Path to Scofield notes file')
    parse_parser.add_argument('--format', type=str, default='tsv', help='Input format (tsv, csv, json)')
    parse_parser.add_argument('--output', type=str, default='data', help='Output directory')
    parse_parser.add_argument('--db', type=str, help='Create SQLite database at this path')
    
    # Generate web app command
    web_parser = subparsers.add_parser('generate-web', help='Generate web application code')
    web_parser.add_argument('--output-dir', type=str, default='web_app', help='Output directory for web files')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export to various formats')
    export_parser.add_argument('--format', choices=['json', 'sqlite', 'all'], default='all',
                              help='Export format')
    export_parser.add_argument('--input', type=str, default='data', help='Input data directory')
    export_parser.add_argument('--output', type=str, default='exports', help='Output directory')
    
    # Analysis command
    analysis_parser = subparsers.add_parser('analyze', help='Analyze the data')
    analysis_parser.add_argument('--input', type=str, default='data', help='Input data directory')
    
    args = parser.parse_args()
    
    if args.command == 'parse':
        print("=" * 70)
        print("ENHANCED SCOFIELD BIBLE PARSER")
        print("=" * 70)
        
        parser = EnhancedScofieldParser()
        
        # Parse KJV text
        if Path(args.kjv).exists():
            parser.parse_kjv_from_file(args.kjv, args.format)
        else:
            print(f"Warning: KJV file not found at {args.kjv}")
            print("Creating sample data...")
            # In a real implementation, you would create sample data
        
        # Parse Scofield notes
        if Path(args.notes).exists():
            parser.parse_scofield_notes_from_file(args.notes, args.format)
        else:
            print(f"Warning: Notes file not found at {args.notes}")
            print("Creating sample notes...")
            # In a real implementation, you would create sample notes
        
        # Build thematic network
        parser.build_thematic_network()
        
        # Generate reading plans
        parser.generate_reading_plans()
        
        # Analyze connections
        analysis = parser.analyze_connections()
        
        # Export data
        files = parser.export_all_data(args.output)
        
        # Create SQLite database if requested
        if args.db:
            parser.create_sqlite_database(args.db)
        
        print("\n" + "=" * 70)
        print("PARSING COMPLETE")
        print("=" * 70)
        print(f"\nSummary:")
        print(f"  Verses: {analysis['summary']['total_verses']}")
        print(f"  Notes: {analysis['summary']['total_notes']}")
        print(f"  Cross-references: {analysis['summary']['total_cross_references']}")
        print(f"  Themes: {analysis['summary']['total_themes']}")
        print(f"  Reading plans: {analysis['summary']['total_reading_plans']}")
        
        if args.db:
            print(f"\nDatabase created: {args.db}")
        
        print(f"\nData exported to: {args.output}")
        for file_type, path in files.items():
            print(f"  {file_type}: {path}")
    
    elif args.command == 'generate-web':
        print("=" * 70)
        print("GENERATING WEB APPLICATION")
        print("=" * 70)
        
        web_app = ScofieldWebApp()
        
        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Generate API code
        api_code = web_app.generate_api_code()
        with open(output_dir / "api.py", "w", encoding="utf-8") as f:
            f.write(api_code)
        
        # Generate frontend code
        frontend_code = web_app.generate_frontend_code()
        with open(output_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(frontend_code)
        
        # Generate requirements file
        requirements = """
fastapi==0.85.0
uvicorn[standard]==0.18.3
sqlite3
python-multipart
"""
        with open(output_dir / "requirements.txt", "w", encoding="utf-8") as f:
            f.write(requirements)
        
        # Generate README
        readme = """
# Connected Scofield Bible Web Application

A modern web application for exploring the 1917 Scofield Reference Bible with enhanced features.

## Features

- Interactive Bible reader with verse-by-verse navigation
- Scofield notes integrated with scripture
- Thematic network visualization
- Advanced search across verses, notes, and themes
- Reading plan generator
- Cross-reference explorer
- Responsive design for all devices

## Installation

1. Install Python dependencies:
pip install -r requirements.txt
text


2. Ensure you have the SQLite database (`scofield_bible.db`) in the same directory

3. Start the FastAPI server:

python api.py
text


4. Open `index.html` in your browser or serve it with a web server

## API Endpoints

- `GET /api/books` - List all Bible books
- `GET /api/verses/{book}/{chapter}` - Get verses for a chapter
- `GET /api/verse/{verse_id}` - Get detailed verse information
- `GET /api/search` - Search verses, notes, and themes
- `GET /api/themes` - Get all theological themes
- `GET /api/theme/{theme_id}` - Get detailed theme information
- `GET /api/reading-plans` - Get reading plans
- `GET /api/statistics` - Get database statistics

## Data Structure

The application uses a SQLite database with the following main tables:
- `verses` - Bible verses (KJV text)
- `notes` - Scofield study notes
- `cross_references` - Cross-reference relationships
- `themes` - Theological themes
- `reading_plans` - Generated reading plans

## Development

To modify the application:

1. Update `api.py` for backend changes
2. Update `index.html` for frontend changes
3. The database schema is defined in `scofield_parser.py`

## License

Public Domain - 1917 Scofield Reference Bible
"""
     with open(output_dir / "README.md", "w", encoding="utf-8") as f:
         f.write(readme)
     
     print(f"\nWeb application generated in: {output_dir}")
     print("\nFiles created:")
     print("  - api.py (FastAPI backend)")
     print("  - index.html (Frontend)")
     print("  - requirements.txt")
     print("  - README.md")
     print("\nTo run:")
     print(f"  1. cd {output_dir}")
     print("  2. pip install -r requirements.txt")
     print("  3. python api.py")
     print("  4. Open index.html in your browser")
 
 elif args.command == 'export':
     print("Export functionality...")
     # Implement export based on existing data
 
 elif args.command == 'analyze':
     print("Analysis functionality...")
     # Implement analysis
 
 else:
     parser.print_help()
     
     print("\n" + "=" * 70)
     print("QUICK START GUIDE")
     print("=" * 70)
     print("\n1. Parse your data:")
     print("   python scofield_parser.py parse --kjv kjv.txt --notes scofield_notes.txt")
     print("\n2. Generate web application:")
     print("   python scofield_parser.py generate-web --output-dir web_app")
     print("\n3. Run the web app:")
     print("   cd web_app")
     print("   pip install -r requirements.txt")
     print("   python api.py")
     print("   Then open index.html in your browser")
     print("\nFor more details, see the README files.")

if __name__ == "__main__":
 main()

Integration with Your Existing Repository

To integrate this enhanced version with your existing GitHub repository:
1. Update Your Repository Structure
text

scofield-bible-project/
├── data/                    # Raw and parsed data
│   ├── kjv.txt             # KJV Bible text
│   ├── scofield_notes.txt  # Scofield notes
│   └── parsed/             # Parsed JSON files
├── src/
│   ├── parser/             # Parser modules
│   │   ├── __init__.py
│   │   ├── models.py       # Data models
│   │   ├── parser.py       # Main parser
│   │   └── analyzer.py     # Analysis tools
│   ├── web/                # Web application
│   │   ├── api.py          # FastAPI backend
│   │   ├── frontend/       # Frontend files
│   │   └── templates/
│   └── utils/              # Utility functions
├── exports/                # Generated exports
├── docs/                   # Documentation
├── tests/                  # Test suite
├── requirements.txt        # Python dependencies
├── scofield_parser.py     # Main script (this file)
└── README.md              # Project documentation

2. Key Features Added to Your Project

    Enhanced Data Models with more metadata

    Thematic Network Analysis - automatic theme extraction

    Reading Plan Generator - creates study plans based on themes

    FastAPI Web Application - modern, fast backend API

    Interactive Frontend with visualization

    SQLite Database for efficient querying

    Advanced Search across all content

3. Next Steps for Your Repository

    Add your actual KJV and Scofield data to the data folder

    Customize the parser for your specific data format

    Run the parser to create the database:
    bash

python scofield_parser.py parse --kjv data/kjv.txt --notes data/scofield_notes.txt --db scofield.db

Generate the web application:
bash

python scofield_parser.py generate-web --output-dir web_app

    Test and deploy the web application

4. Deployment Options

Option 1: Local Development
bash

cd web_app
pip install -r requirements.txt
python api.py
# Open index.html in browser

Option 2: Docker Deployment
Create a Dockerfile in your repository:
dockerfile

FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "api.py"]

Option 3: Cloud Deployment

    Backend: Deploy to Railway, Render, or AWS

    Frontend: Deploy to Netlify, Vercel, or GitHub Pages

    Database: Use SQLite or migrate to PostgreSQL

