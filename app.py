import streamlit as st
import json
import os
import hashlib
import datetime
import re
import shutil
import base64
from pathlib import Path
import difflib
from typing import Dict, List, Any, Optional, Tuple

# Configure page
st.set_page_config(
    page_title="SmartBuddy - Student Assistant",
    page_icon="🤖",
    layout="wide"
)

def apply_theme():
    """Apply dark theme"""
    st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    .stSidebar {
        background-color: #262730;
    }
    .stSelectbox > div > div {
        background-color: #262730;
        color: #fafafa;
    }
    .stTextInput > div > div > input {
        background-color: #262730;
        color: #fafafa;
    }
    .stTextArea > div > div > textarea {
        background-color: #262730;
        color: #fafafa;
    }
    .stButton > button {
        background-color: #ff4b4b;
        color: white;
    }
    .stMetric {
        background-color: #262730;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

# Constants
DATA_DIR = Path("data")
NOTES_DIR = Path("notes")
CHATS_DIR = Path("chats")
SALT = "smartbuddy_salt_2024"  # Static salt for password hashing

class DataManager:
    """Handles all data persistence operations"""
    
    def __init__(self):
        self.ensure_directories()
        self.ensure_files()
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        for directory in [DATA_DIR, NOTES_DIR, CHATS_DIR]:
            directory.mkdir(exist_ok=True)
    
    def ensure_files(self):
        """Create default data files if they don't exist"""
        default_data = {
            'auth.json': {
                'password_hash': self.hash_password('123'),
                'password_hint': 'Default password is 123'
            },
            'info.json': {
                'exam_dates': {},
                'faculty': {},
                'schedule': {},
                'events': {},
                'custom_categories': {}
            },
            'synonyms.json': {
                'dbms': ['database management system', 'database', 'db'],
                'cs': ['computer science', 'comp sci'],
                'java': ['programming', 'coding'],
                'notes': ['note', 'material', 'study material'],
                'exam': ['test', 'examination', 'quiz', 'exm', 'exams', 'tests'],
                'exm': ['exam', 'test', 'examination', 'quiz'],
                'faculty': ['teacher', 'professor', 'staff', 'instructor'],
                'schedule': ['timetable', 'time', 'timing', 'class']
            },
            'knowledge_base.json': [],
            'unanswered_queries.json': [],
            'notes_metadata.json': []
        }
        
        for filename, default_content in default_data.items():
            filepath = DATA_DIR / filename
            if not filepath.exists():
                self.save_json(filepath, default_content)
    
    def hash_password(self, password: str) -> str:
        """Hash password with salt"""
        return hashlib.sha256((password + SALT).encode()).hexdigest()
    
    def save_json(self, filepath: Path, data: Any):
        """Safely save JSON data with atomic write"""
        temp_path = filepath.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            temp_path.replace(filepath)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise e
    
    def load_json(self, filepath: Path) -> Any:
        """Load JSON data with error handling"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Return appropriate default based on filename
            if 'auth.json' in str(filepath):
                return {
                    'password_hash': self.hash_password('123'),
                    'password_hint': 'Default password is 123'
                }
            elif 'info.json' in str(filepath):
                return {
                    'exam_dates': {},
                    'faculty': {},
                    'schedule': {},
                    'events': {},
                    'custom_categories': {}
                }
            elif 'synonyms.json' in str(filepath):
                return {
                    'dbms': ['database management system', 'database', 'db'],
                    'cs': ['computer science', 'comp sci'],
                    'java': ['programming', 'coding'],
                    'notes': ['note', 'material', 'study material'],
                    'exam': ['test', 'examination', 'quiz', 'exm', 'exams', 'tests'],
                    'exm': ['exam', 'test', 'examination', 'quiz'],
                    'faculty': ['teacher', 'professor', 'staff', 'instructor'],
                    'schedule': ['timetable', 'time', 'timing', 'class']
                }
            else:
                return []

class NLPProcessor:
    """Handles natural language processing for the chatbot"""
    
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        self.synonyms = data_manager.load_json(DATA_DIR / 'synonyms.json')
    
    def preprocess_text(self, text: str) -> str:
        """Clean and normalize text"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def expand_synonyms(self, text: str) -> List[str]:
        """Expand text with synonyms"""
        words = text.split()
        expanded_terms = set(words)
        
        for word in words:
            for key, synonyms_list in self.synonyms.items():
                if word in synonyms_list or word == key:
                    expanded_terms.add(key)
                    expanded_terms.update(synonyms_list)
        
        return list(expanded_terms)
    
    def fuzzy_match(self, query: str, target: str, threshold: float = 0.6) -> float:
        """Calculate fuzzy match score using difflib"""
        query_clean = self.preprocess_text(query)
        target_clean = self.preprocess_text(target)
        
        ratio = difflib.SequenceMatcher(None, query_clean, target_clean).ratio()
        return ratio * 100
    
    def detect_intent(self, text: str) -> str:
        """Detect user intent from text with keyword expansion"""
        text_lower = text.lower()
        expanded_terms = self.expand_synonyms(text_lower)
        all_terms = set([text_lower] + expanded_terms)
        
        if any(word in term for term in all_terms for word in ['note', 'notes', 'material', 'pdf']):
            return 'notes_request'
        elif any(word in term for term in all_terms for word in ['exam', 'test', 'examination', 'exm', 'quiz']):
            return 'exam_info'
        elif any(word in term for term in all_terms for word in ['faculty', 'teacher', 'professor', 'staff']):
            return 'faculty_info'
        elif any(word in term for term in all_terms for word in ['schedule', 'timetable', 'class', 'time']):
            return 'schedule_info'
        elif any(word in term for term in all_terms for word in ['event', 'events', 'activity', 'activities']):
            return 'events_info'
        elif any(word in term for term in all_terms for word in ['mental', 'health', 'stress', 'anxiety']):
            return 'mental_health'
        elif any(word in term for term in all_terms for word in ['help', 'hi', 'hello', 'hey']):
            return 'help_greeting'
        else:
            # Check if this might match keywords in any info category
            info_data = self.data_manager.load_json(DATA_DIR / 'info.json')
            for category in ['exam_dates', 'faculty', 'schedule', 'events']:
                if self._check_category_keywords(text_lower, category, info_data):
                    return f"{category.split('_')[0]}_info"
            return 'unknown'
    
    def _check_category_keywords(self, query: str, category: str, info_data: dict) -> bool:
        """Check if query matches any keywords in a category"""
        if category not in info_data:
            return False
        
        content = info_data[category]
        if not isinstance(content, dict):
            return False
            
        for key, value in content.items():
            if isinstance(value, dict):
                keywords = value.get('keywords', [])
                for keyword in keywords:
                    if query in keyword or keyword in query:
                        return True
                    if self.fuzzy_match(query, keyword) > 80:
                        return True
        return False

class NotesManager:
    """Manages PDF notes with intelligent search and ranking"""
    
    def __init__(self, data_manager: DataManager, nlp_processor: NLPProcessor):
        self.data_manager = data_manager
        self.nlp_processor = nlp_processor
    
    def add_note(self, file, display_name: str, keywords: str) -> bool:
        """Add a new PDF note"""
        try:
            # Generate unique filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{file.name}"
            filepath = NOTES_DIR / filename
            
            # Save PDF file
            with open(filepath, 'wb') as f:
                f.write(file.read())
            
            # Update metadata
            metadata = self.data_manager.load_json(DATA_DIR / 'notes_metadata.json')
            note_id = len(metadata) + 1
            
            metadata.append({
                'id': note_id,
                'display_name': display_name,
                'filename': filename,
                'keywords': [k.strip().lower() for k in keywords.split(',')],
                'uploaded_at': datetime.datetime.now().isoformat()
            })
            
            self.data_manager.save_json(DATA_DIR / 'notes_metadata.json', metadata)
            return True
            
        except Exception as e:
            st.error(f"Error adding note: {str(e)}")
            return False
    
    def search_notes(self, query: str) -> List[Dict]:
        """Search notes with natural language understanding"""
        metadata = self.data_manager.load_json(DATA_DIR / 'notes_metadata.json')
        if not metadata:
            return []
        
        query_clean = self.nlp_processor.preprocess_text(query)
        query_words = query_clean.split()
        
        # Expand query with synonyms
        expanded_words = set(query_words)
        for word in query_words:
            expanded_words.update(self.nlp_processor.expand_synonyms(word))
        
        results = []
        
        for note in metadata:
            score = 0
            
            display_name_clean = self.nlp_processor.preprocess_text(note['display_name'])
            filename_stem = self.nlp_processor.preprocess_text(note['filename'].split('.')[0])
            keywords_clean = [self.nlp_processor.preprocess_text(k) for k in note.get('keywords', [])]
            
            # Check if any word in the sentence matches note name or keywords
            for word in expanded_words:
                # Display name matching
                if word in display_name_clean or display_name_clean in word:
                    score += 35
                elif self.nlp_processor.fuzzy_match(word, display_name_clean) > 70:
                    score += 20
                
                # Filename matching
                if word in filename_stem or filename_stem in word:
                    score += 30
                elif self.nlp_processor.fuzzy_match(word, filename_stem) > 70:
                    score += 15
                
                # Keywords matching
                for keyword in keywords_clean:
                    if word in keyword or keyword in word:
                        score += 25
                    elif self.nlp_processor.fuzzy_match(word, keyword) > 70:
                        score += 15
            
            # Boost for common note request patterns
            if any(pattern in query_clean for pattern in ['notes', 'material', 'study', 'pdf']):
                score += 5
            
            # Add to results if above threshold
            if score > 10:
                results.append({
                    'note': note,
                    'score': score
                })
        
        # Sort by score (highest first), then by upload date (newest first)
        results.sort(key=lambda x: (x['score'], x['note']['uploaded_at']), reverse=True)
        
        return [r['note'] for r in results]
    
    def get_all_notes(self) -> List[Dict]:
        """Get all notes metadata"""
        return self.data_manager.load_json(DATA_DIR / 'notes_metadata.json')
    
    def delete_note(self, note_id: int) -> bool:
        """Delete a note by ID"""
        try:
            metadata = self.data_manager.load_json(DATA_DIR / 'notes_metadata.json')
            note_to_delete = None
            
            for i, note in enumerate(metadata):
                if note['id'] == note_id:
                    note_to_delete = note
                    del metadata[i]
                    break
            
            if note_to_delete:
                # Delete file
                filepath = NOTES_DIR / note_to_delete['filename']
                if filepath.exists():
                    filepath.unlink()
                
                # Save updated metadata
                self.data_manager.save_json(DATA_DIR / 'notes_metadata.json', metadata)
                return True
            
            return False
            
        except Exception as e:
            st.error(f"Error deleting note: {str(e)}")
            return False
    
    def update_note(self, note_id: int, display_name: str, keywords: str) -> bool:
        """Update note metadata"""
        try:
            metadata = self.data_manager.load_json(DATA_DIR / 'notes_metadata.json')
            
            for note in metadata:
                if note['id'] == note_id:
                    note['display_name'] = display_name
                    note['keywords'] = [k.strip().lower() for k in keywords.split(',')]
                    break
            
            self.data_manager.save_json(DATA_DIR / 'notes_metadata.json', metadata)
            return True
            
        except Exception as e:
            st.error(f"Error updating note: {str(e)}")
            return False

class ChatBot:
    """Main chatbot logic"""
    
    def __init__(self, data_manager: DataManager, nlp_processor: NLPProcessor, notes_manager: NotesManager):
        self.data_manager = data_manager
        self.nlp_processor = nlp_processor
        self.notes_manager = notes_manager
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """Process user query and generate response"""
        # First try direct keyword matching across all categories
        direct_match = self._try_direct_keyword_match(query)
        if direct_match:
            return direct_match
        
        # Then try intent detection
        intent = self.nlp_processor.detect_intent(query)
        
        if intent == 'notes_request':
            return self._handle_notes_request(query)
        elif intent == 'exam_info':
            return self._handle_info_request(query, 'exam_dates')
        elif intent == 'faculty_info':
            return self._handle_info_request(query, 'faculty')
        elif intent == 'schedule_info':
            return self._handle_info_request(query, 'schedule')
        elif intent == 'events_info':
            return self._handle_info_request(query, 'events')
        elif intent == 'mental_health':
            return self._handle_mental_health()
        elif intent == 'help_greeting':
            return self._handle_greeting()
        else:
            return self._handle_unknown_query(query)
    
    def _try_direct_keyword_match(self, query: str) -> Optional[Dict[str, Any]]:
        """Try to find keyword matches in natural language sentences"""
        query_clean = self.nlp_processor.preprocess_text(query)
        query_words = query_clean.split()
        info_data = self.data_manager.load_json(DATA_DIR / 'info.json')
        
        # Expand query with synonyms
        expanded_words = set(query_words)
        for word in query_words:
            expanded_words.update(self.nlp_processor.expand_synonyms(word))
        
        categories = {
            'exam_dates': 'exam_info',
            'faculty': 'faculty_info',
            'schedule': 'schedule_info',
            'events': 'events_info',
            'custom_categories': 'custom_info'
        }
        
        best_match = None
        best_score = 0
        
        for category, intent_type in categories.items():
            if category not in info_data:
                continue
                
            content = info_data[category]
            if not isinstance(content, dict):
                continue
                
            for key, value in content.items():
                score = 0
                
                if isinstance(value, dict):
                    keywords = value.get('keywords', [])
                    display_value = value.get('value', '')
                    
                    # Check if any keyword or name appears in the sentence
                    for keyword in keywords:
                        for word in expanded_words:
                            if word in keyword or keyword in word:
                                score += 40
                            elif self.nlp_processor.fuzzy_match(word, keyword) > 70:
                                score += 25
                    
                    # Check key (name) matching
                    key_lower = key.lower()
                    for word in expanded_words:
                        if word in key_lower or key_lower in word:
                            score += 35
                        elif self.nlp_processor.fuzzy_match(word, key_lower) > 70:
                            score += 20
                    
                    # Boost score for common question patterns
                    if any(pattern in query_clean for pattern in ['when', 'what', 'where', 'how', 'start', 'begin']):
                        score += 5
                        
                    if score > best_score:
                        best_score = score
                        best_match = (category, key, display_value)
                
                # For custom categories, also check category name
                elif category == 'custom_categories':
                    key_lower = key.lower()
                    for word in expanded_words:
                        if word in key_lower or key_lower in word:
                            return {
                                'type': 'text',
                                'message': f"**{key}**: {value}"
                            }
        
        # Return specific match if found
        if best_match and best_score > 15:
            category, key, display_value = best_match
            return {
                'type': 'text',
                'message': f"**{key}**: {display_value}"
            }
        
        return None
    
    def _handle_notes_request(self, query: str) -> Dict[str, Any]:
        """Handle notes-related queries"""
        query_clean = self.nlp_processor.preprocess_text(query)
        
        # Check if user just wants to see all notes
        if query_clean in ['note', 'notes', 'show notes', 'list notes']:
            all_notes = self.notes_manager.get_all_notes()
            if all_notes:
                return {
                    'type': 'notes_list',
                    'message': "Here are all available notes:",
                    'notes': all_notes
                }
            else:
                return {
                    'type': 'text',
                    'message': "No notes are currently available. Please contact admin to add study materials."
                }
        
        # Search for specific notes
        matching_notes = self.notes_manager.search_notes(query)
        
        if matching_notes:
            best_match = matching_notes[0]
            return {
                'type': 'note_download',
                'message': f"{best_match['display_name']} notes:",
                'note': best_match
            }
        else:
            # No match found, show available notes
            all_notes = self.notes_manager.get_all_notes()
            if all_notes:
                return {
                    'type': 'notes_list',
                    'message': "Available notes:",
                    'notes': all_notes
                }
            else:
                return {
                    'type': 'text',
                    'message': "No notes found for that topic, and no other notes are available yet."
                }
    
    def _handle_info_request(self, query: str, category: str) -> Dict[str, Any]:
        """Handle information requests"""
        info_data = self.data_manager.load_json(DATA_DIR / 'info.json')
        
        if category in info_data and info_data[category]:
            content = info_data[category]
            query_clean = self.nlp_processor.preprocess_text(query)
            
            # Find the best matching item using keywords and fuzzy matching
            best_match = None
            best_score = 0
            
            if isinstance(content, dict):
                for key, value in content.items():
                    score = 0
                    
                    # Handle both old format (string) and new format (dict)
                    if isinstance(value, dict):
                        display_value = value.get('value', '')
                        keywords = value.get('keywords', [])
                        
                        # Check keywords first - more aggressive matching
                        for keyword in keywords:
                            # Exact match
                            if query_clean == keyword:
                                score += 50  # High score for exact keyword match
                            # Partial match - keyword contains query or vice versa
                            elif query_clean in keyword or keyword in query_clean:
                                score += 30
                            # Fuzzy match with lower threshold
                            elif self.nlp_processor.fuzzy_match(query_clean, keyword) > 60:
                                score += 20
                    else:
                        display_value = value
                        keywords = []
                    
                    # Check key and value for matches
                    if query_clean in key.lower():
                        score += 15
                    if query_clean in display_value.lower():
                        score += 10
                    
                    # Fuzzy match on key and value
                    score += self.nlp_processor.fuzzy_match(query_clean, key) * 0.1
                    score += self.nlp_processor.fuzzy_match(query_clean, display_value) * 0.1
                    
                    if score > best_score:
                        best_score = score
                        best_match = (key, display_value, keywords)
                
                # If we found a good match, return it specifically
                if best_match and best_score > 5:
                    key, display_value, keywords = best_match
                    # Return only the specific content
                    message = f"**{key}**: {display_value}"
                else:
                    # Return all information in the category
                    message = ""
                    for key, value in content.items():
                        if isinstance(value, dict):
                            display_value = value.get('value', '')
                        else:
                            display_value = value
                        message += f"**{key}**: {display_value}\n\n"
            else:
                message = f"{content}"
            
            return {
                'type': 'text',
                'message': message
            }
        else:
            return {
                'type': 'text',
                'message': f"No {category.replace('_', ' ')} information is available yet."
            }
    
    def _handle_mental_health(self) -> Dict[str, Any]:
        """Handle mental health queries"""
        tips = [
            "Take deep breaths and practice mindfulness",
            "Take regular breaks during study sessions",
            "Get enough sleep and maintain a healthy routine",
            "Talk to friends, family, or counselors when feeling stressed",
            "Exercise regularly to reduce stress and anxiety",
            "Break large tasks into smaller, manageable pieces"
        ]
        
        message = "Here are some mental health tips for students:\n\n"
        for tip in tips:
            message += f"• {tip}\n"
        
        message += "\n💡 Remember: It's okay to ask for help when you need it!"
        
        return {
            'type': 'text',
            'message': message
        }
    
    def _handle_greeting(self) -> Dict[str, Any]:
        """Handle greetings and help requests"""
        message = """👋 Hello! I'm SmartBuddy, your AI-powered college assistant with offline Natural Language Processing.


📚 **What I Can Help With:**

Just ask naturally"""
        return {
            'type': 'text',
            'message': message
        }
    
    def _handle_unknown_query(self, query: str) -> Dict[str, Any]:
        """Handle unknown queries and add to unanswered list"""
        # First check knowledge base
        knowledge_base = self.data_manager.load_json(DATA_DIR / 'knowledge_base.json')
        
        for qa in knowledge_base:
            if self.nlp_processor.fuzzy_match(query, qa['question']) > 75:
                return {
                    'type': 'text',
                    'message': qa['answer']
                }
        
        # Add to unanswered queries
        unanswered = self.data_manager.load_json(DATA_DIR / 'unanswered_queries.json')
        unanswered.append({
            'query': query,
            'asked_at': datetime.datetime.now().isoformat()
        })
        self.data_manager.save_json(DATA_DIR / 'unanswered_queries.json', unanswered)
        
        return {
            'type': 'text',
            'message': "I'm sorry, I don't have information about that yet. I've noted your question and admin can help provide an answer for future queries. Is there anything else I can help you with?"
        }

class ChatManager:
    """Manages chat sessions and history"""
    
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
    
    def create_new_chat(self) -> str:
        """Create a new chat session"""
        chat_id = f"chat_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        chat_data = {
            'id': chat_id,
            'name': 'New Chat',
            'created_at': datetime.datetime.now().isoformat(),
            'updated_at': datetime.datetime.now().isoformat(),
            'message_count': 0,
            'messages': []
        }
        
        chat_file = CHATS_DIR / f"{chat_id}.json"
        self.data_manager.save_json(chat_file, chat_data)
        
        return chat_id
    
    def save_chat_message(self, chat_id: str, role: str, message: str):
        """Save a message to chat history"""
        chat_file = CHATS_DIR / f"{chat_id}.json"
        
        if chat_file.exists():
            chat_data = self.data_manager.load_json(chat_file)
        else:
            chat_data = {
                'id': chat_id,
                'name': 'New Chat',
                'created_at': datetime.datetime.now().isoformat(),
                'updated_at': datetime.datetime.now().isoformat(),
                'message_count': 0,
                'messages': []
            }
        
        chat_data['messages'].append({
            'role': role,
            'text': message,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
        chat_data['message_count'] = len(chat_data['messages'])
        chat_data['updated_at'] = datetime.datetime.now().isoformat()
        
        # Auto-generate chat name from first user message
        if chat_data['name'] == 'New Chat' and role == 'user':
            chat_data['name'] = message[:30] + "..." if len(message) > 30 else message
        
        self.data_manager.save_json(chat_file, chat_data)
    
    def get_chat_history(self) -> List[Dict]:
        """Get all chat sessions"""
        chats = []
        
        for chat_file in CHATS_DIR.glob("chat_*.json"):
            try:
                chat_data = self.data_manager.load_json(chat_file)
                chats.append({
                    'id': chat_data['id'],
                    'name': chat_data['name'],
                    'message_count': chat_data['message_count'],
                    'updated_at': chat_data['updated_at']
                })
            except:
                continue
        
        # Sort by updated_at descending
        chats.sort(key=lambda x: x['updated_at'], reverse=True)
        return chats
    
    def load_chat(self, chat_id: str) -> Optional[Dict]:
        """Load a specific chat session"""
        chat_file = CHATS_DIR / f"{chat_id}.json"
        
        if chat_file.exists():
            return self.data_manager.load_json(chat_file)
        return None
    
    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat session"""
        chat_file = CHATS_DIR / f"{chat_id}.json"
        
        if chat_file.exists():
            chat_file.unlink()
            return True
        return False
    
    def rename_chat(self, chat_id: str, new_name: str) -> bool:
        """Rename a chat session"""
        chat_file = CHATS_DIR / f"{chat_id}.json"
        
        if chat_file.exists():
            chat_data = self.data_manager.load_json(chat_file)
            chat_data['name'] = new_name
            chat_data['updated_at'] = datetime.datetime.now().isoformat()
            self.data_manager.save_json(chat_file, chat_data)
            return True
        return False

# Initialize managers
@st.cache_resource
def get_managers():
    data_manager = DataManager()
    nlp_processor = NLPProcessor(data_manager)
    notes_manager = NotesManager(data_manager, nlp_processor)
    chatbot = ChatBot(data_manager, nlp_processor, notes_manager)
    chat_manager = ChatManager(data_manager)
    return data_manager, nlp_processor, notes_manager, chatbot, chat_manager

data_manager, nlp_processor, notes_manager, chatbot, chat_manager = get_managers()

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'chat'
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_chat_id' not in st.session_state:
    st.session_state.current_chat_id = chat_manager.create_new_chat()
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []

def render_sidebar():
    """Render the sidebar with navigation and chat history"""
    with st.sidebar:
        st.title("🤖 SmartBuddy")
        
        # New Chat button
        if st.button("➕ New Chat", use_container_width=True):
            # Save current chat if it has messages
            if st.session_state.chat_messages:
                for msg in st.session_state.chat_messages:
                    chat_manager.save_chat_message(
                        st.session_state.current_chat_id, 
                        msg['role'], 
                        msg['content']
                    )
            
            # Create new chat
            st.session_state.current_chat_id = chat_manager.create_new_chat()
            st.session_state.chat_messages = []
            st.rerun()
        
        st.divider()
        
        # Chat History
        st.subheader("💬 Chat History")
        chat_history = chat_manager.get_chat_history()
        
        for chat in chat_history[:10]:  # Show last 10 chats
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                if st.button(f"📄 {chat['name']}", key=f"load_{chat['id']}", use_container_width=True):
                    # Save current chat before loading
                    if st.session_state.chat_messages:
                        for msg in st.session_state.chat_messages:
                            chat_manager.save_chat_message(
                                st.session_state.current_chat_id, 
                                msg['role'], 
                                msg['content']
                            )
                    
                    # Load selected chat
                    loaded_chat = chat_manager.load_chat(chat['id'])
                    if loaded_chat:
                        st.session_state.current_chat_id = chat['id']
                        st.session_state.chat_messages = [
                            {'role': msg['role'], 'content': msg['text']}
                            for msg in loaded_chat['messages']
                        ]
                    st.rerun()
            
            with col2:
                if st.button("✏️", key=f"rename_{chat['id']}", help="Rename"):
                    st.session_state.rename_chat_id = chat['id']
                    st.session_state.rename_chat_name = chat['name']
            
            with col3:
                if st.button("🗑️", key=f"delete_{chat['id']}", help="Delete"):
                    chat_manager.delete_chat(chat['id'])
                    if st.session_state.current_chat_id == chat['id']:
                        st.session_state.current_chat_id = chat_manager.create_new_chat()
                        st.session_state.chat_messages = []
                    st.rerun()
        
        st.divider()
        
        # Admin Panel access
        if st.button("⚙️ Admin Panel", use_container_width=True):
            st.session_state.page = 'admin_login'
            st.rerun()
        
        # Instructions
        st.markdown("---")
        st.markdown("### 🚀 How to run")
        st.code("streamlit run app.py", language="bash")

def create_download_button(note: Dict) -> str:
    """Create a download button for a PDF note"""
    try:
        file_path = NOTES_DIR / note['filename']
        if file_path.exists():
            with open(file_path, 'rb') as f:
                pdf_data = f.read()
            
            b64_pdf = base64.b64encode(pdf_data).decode()
            download_link = f"""
                <a href="data:application/pdf;base64,{b64_pdf}" 
                   download="{note['display_name']}.pdf"
                   style="display: inline-block; padding: 0.5rem 1rem; background-color: #ff4b4b; 
                          color: white; text-decoration: none; border-radius: 0.5rem; margin: 0.5rem 0;">
                    📥 Download {note['display_name']}
                </a>
            """
            return download_link
    except Exception as e:
        st.error(f"Error creating download button: {str(e)}")
    
    return ""

def render_chat_interface():
    """Render the main chat interface"""
    st.title("💬 Chat with SmartBuddy")
    
    # Handle rename dialog
    if hasattr(st.session_state, 'rename_chat_id'):
        with st.form("rename_chat_form"):
            st.write("Rename Chat")
            new_name = st.text_input("New name:", value=st.session_state.rename_chat_name)
            col1, col2 = st.columns(2)
            
            with col1:
                if st.form_submit_button("Save"):
                    if new_name and new_name.strip():
                        chat_manager.rename_chat(st.session_state.rename_chat_id, new_name.strip())
                        del st.session_state.rename_chat_id
                        del st.session_state.rename_chat_name
                        st.rerun()
            
            with col2:
                if st.form_submit_button("Cancel"):
                    del st.session_state.rename_chat_id
                    del st.session_state.rename_chat_name
                    st.rerun()
        
        return
    
    # Display chat messages
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.chat_messages:
            if message['role'] == 'user':
                with st.chat_message("user"):
                    st.write(message['content'])
            else:
                with st.chat_message("assistant"):
                    st.write(message['content'])
                    
                    # Handle special response types
                    if 'note_download' in str(message):
                        # This is a hack to store note data in the message
                        # In a real app, you'd want a better way to handle this
                        pass
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about college..."):
        # Add user message
        st.session_state.chat_messages.append({'role': 'user', 'content': prompt})
        
        # Display user message immediately
        with st.chat_message("user"):
            st.write(prompt)
        
        # Generate bot response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = chatbot.process_query(prompt)
            
            if response['type'] == 'text':
                st.write(response['message'])
                st.session_state.chat_messages.append({'role': 'assistant', 'content': response['message']})
            
            elif response['type'] == 'note_download':
                st.write(response['message'])
                download_html = create_download_button(response['note'])
                if download_html:
                    st.markdown(download_html, unsafe_allow_html=True)
                
                st.session_state.chat_messages.append({'role': 'assistant', 'content': response['message']})
            
            elif response['type'] == 'notes_list':
                st.write(response['message'])
                
                # Create buttons for each note
                cols = st.columns(min(3, len(response['notes'])))
                for idx, note in enumerate(response['notes']):
                    with cols[idx % 3]:
                        if st.button(f"📚 {note['display_name']}", key=f"note_btn_{note['id']}"):
                            # Trigger download for selected note
                            download_html = create_download_button(note)
                            if download_html:
                                st.markdown(download_html, unsafe_allow_html=True)
                
                st.session_state.chat_messages.append({'role': 'assistant', 'content': response['message']})
        
        # Auto-save chat periodically
        if len(st.session_state.chat_messages) % 5 == 0:  # Save every 5 messages
            for msg in st.session_state.chat_messages:
                chat_manager.save_chat_message(
                    st.session_state.current_chat_id, 
                    msg['role'], 
                    msg['content']
                )

def render_admin_login():
    """Render admin login page"""
    st.title("🔒 Admin Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("admin_login"):
            st.write("Please enter the admin password:")
            password = st.text_input("Password", type="password")
            
            col_login, col_back = st.columns(2)
            
            with col_login:
                if st.form_submit_button("Login", use_container_width=True):
                    auth_data = data_manager.load_json(DATA_DIR / 'auth.json')
                    password_hash = data_manager.hash_password(password)
                    
                    if password_hash == auth_data['password_hash']:
                        st.session_state.authenticated = True
                        st.session_state.page = 'admin_panel'
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid password!")
            
            with col_back:
                if st.form_submit_button("Back to Chat", use_container_width=True):
                    st.session_state.page = 'chat'
                    st.rerun()
        
        # Forgot password option
        if st.button("Forgot Password?"):
            auth_data = data_manager.load_json(DATA_DIR / 'auth.json')
            st.info(f"Password Hint: {auth_data.get('password_hint', 'No hint available')}")

def render_admin_panel():
    """Render admin panel"""
    st.title("⚙️ Admin Panel")
    
    # Top navigation bar
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        st.write("### Welcome to Admin Panel")
    
    with col2:
        if st.button("🏠 Back to Chat", use_container_width=True):
            st.session_state.page = 'chat'
            st.rerun()
    
    with col3:
        if st.button("🔓 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.page = 'chat'
            st.rerun()
    
    with col4:
        st.write("")  # Empty column for layout
    
    st.divider()
    
    # Main navigation tabs
    admin_tab = st.selectbox("Select Section:", [
        "📊 Dashboard",
        "📚 Notes Management", 
        "📋 Information Management",
        "❓ Unanswered Queries",
        "🧠 Knowledge Base",
        "🔧 Settings"
    ])
    
    st.divider()
    
    # Apply theme
    apply_theme()
    
    if admin_tab == "📊 Dashboard":
        render_admin_dashboard()
    elif admin_tab == "📚 Notes Management":
        render_notes_management()
    elif admin_tab == "📋 Information Management":
        render_info_management()
    elif admin_tab == "❓ Unanswered Queries":
        render_unanswered_queries()
    elif admin_tab == "🧠 Knowledge Base":
        render_knowledge_base()
    elif admin_tab == "🔧 Settings":
        render_admin_settings()

def render_admin_dashboard():
    """Render admin dashboard"""
    st.subheader("📊 Dashboard")
    
    # Statistics
    notes_count = len(notes_manager.get_all_notes())
    unanswered_count = len(data_manager.load_json(DATA_DIR / 'unanswered_queries.json'))
    knowledge_count = len(data_manager.load_json(DATA_DIR / 'knowledge_base.json'))
    chats_count = len(list(CHATS_DIR.glob("chat_*.json")))
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📚 Total Notes", notes_count)
    
    with col2:
        st.metric("❓ Unanswered Queries", unanswered_count)
    
    with col3:
        st.metric("🧠 Knowledge Base", knowledge_count)
    
    with col4:
        st.metric("💬 Chat Sessions", chats_count)
    
    st.divider()
    
    # Recent activity with delete options
    col_header, col_delete = st.columns([3, 1])
    
    with col_header:
        st.subheader("Recent Activity")
    
    with col_delete:
        if st.button("🗑️ Clear All Activity", type="secondary"):
            # Clear old chat files (keep only 10 most recent)
            all_chats = list(CHATS_DIR.glob("chat_*.json"))
            if len(all_chats) > 10:
                old_chats = sorted(all_chats, key=lambda x: x.stat().st_mtime)[:-10]
                for chat_file in old_chats:
                    chat_file.unlink()
                st.success(f"Cleared {len(old_chats)} old chat sessions!")
                st.rerun()
    
    # Recent notes
    recent_notes = sorted(notes_manager.get_all_notes(), 
                         key=lambda x: x['uploaded_at'], reverse=True)[:5]
    
    if recent_notes:
        st.write("**Recent Notes:**")
        for note in recent_notes:
            col_note, col_del = st.columns([4, 1])
            with col_note:
                upload_date = datetime.datetime.fromisoformat(note['uploaded_at']).strftime("%Y-%m-%d %H:%M")
                st.write(f"• {note['display_name']} - {upload_date}")
            with col_del:
                if st.button("🗑️", key=f"del_note_{note['id']}", help="Delete this note"):
                    if notes_manager.delete_note(note['id']):
                        st.success("Note deleted!")
                        st.rerun()
    
    # Recent unanswered queries
    recent_queries = data_manager.load_json(DATA_DIR / 'unanswered_queries.json')[-5:]
    
    if recent_queries:
        st.write("**Recent Unanswered Queries:**")
        for idx, query in enumerate(recent_queries):
            col_query, col_del = st.columns([4, 1])
            with col_query:
                asked_date = datetime.datetime.fromisoformat(query['asked_at']).strftime("%Y-%m-%d %H:%M")
                st.write(f"• {query['query']} - {asked_date}")
            with col_del:
                if st.button("🗑️", key=f"del_query_{idx}", help="Delete this query"):
                    all_queries = data_manager.load_json(DATA_DIR / 'unanswered_queries.json')
                    if idx < len(all_queries):
                        del all_queries[-(len(recent_queries) - idx)]
                        data_manager.save_json(DATA_DIR / 'unanswered_queries.json', all_queries)
                        st.success("Query deleted!")
                        st.rerun()

def render_notes_management():
    """Render notes management interface"""
    st.subheader("📚 Notes Management")
    
    # Upload new note
    st.write("### Upload New Note")
    
    with st.form("upload_note"):
        uploaded_file = st.file_uploader("Choose PDF file", type=['pdf'])
        display_name = st.text_input("Display Name *", placeholder="e.g., Java Programming Notes")
        keywords = st.text_input("Keywords *", placeholder="e.g., java, programming, oop")
        
        if st.form_submit_button("Upload Note"):
            if uploaded_file and display_name and keywords:
                if notes_manager.add_note(uploaded_file, display_name, keywords):
                    st.success("Note uploaded successfully!")
                    st.rerun()
                else:
                    st.error("Failed to upload note!")
            else:
                st.error("All fields are required!")
    
    st.divider()
    
    # Manage existing notes
    st.write("### Manage Existing Notes")
    
    notes = notes_manager.get_all_notes()
    
    if not notes:
        st.info("No notes uploaded yet.")
        return
    
    for note in notes:
        with st.expander(f"📄 {note['display_name']}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Filename:** {note['filename']}")
                st.write(f"**Keywords:** {', '.join(note['keywords'])}")
                st.write(f"**Uploaded:** {datetime.datetime.fromisoformat(note['uploaded_at']).strftime('%Y-%m-%d %H:%M')}")
            
            with col2:
                # Edit form
                with st.form(f"edit_note_{note['id']}"):
                    new_display_name = st.text_input("Display Name", value=note['display_name'], key=f"edit_name_{note['id']}")
                    new_keywords = st.text_input("Keywords", value=', '.join(note['keywords']), key=f"edit_keywords_{note['id']}")
                    
                    col_save, col_delete = st.columns(2)
                    
                    with col_save:
                        if st.form_submit_button("Save", use_container_width=True):
                            if new_display_name and new_keywords:
                                if notes_manager.update_note(note['id'], new_display_name, new_keywords):
                                    st.success("Note updated!")
                                    st.rerun()
                                else:
                                    st.error("Update failed!")
                            else:
                                st.error("All fields required!")
                    
                    with col_delete:
                        if st.form_submit_button("Delete", use_container_width=True):
                            if notes_manager.delete_note(note['id']):
                                st.success("Note deleted!")
                                st.rerun()
                            else:
                                st.error("Delete failed!")

def render_info_management():
    """Render information management interface"""
    st.subheader("📋 Information Management")
    
    info_data = data_manager.load_json(DATA_DIR / 'info.json')
    
    # Tabs for different info categories
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Exam Dates", "👨‍🏫 Faculty", "🕐 Schedule", "🎉 Events", "➕ Custom"])
    
    with tab1:
        st.write("### Exam Dates")
        render_info_editor("exam_dates", info_data)
    
    with tab2:
        st.write("### Faculty Information")
        render_info_editor("faculty", info_data)
    
    with tab3:
        st.write("### Class Schedule")
        render_info_editor("schedule", info_data)
    
    with tab4:
        st.write("### Events")
        render_info_editor("events", info_data)
    
    with tab5:
        st.write("### Custom Categories")
        render_custom_categories(info_data)

def render_info_editor(category: str, info_data: Dict):
    """Render editor for a specific info category"""
    current_data = info_data.get(category, {})
    
    # Add new item
    with st.form(f"add_{category}"):
        st.write("Add New Item")
        col1, col2, col3 = st.columns([2, 2, 2])
        
        with col1:
            key = st.text_input("Key/Title")
        
        with col2:
            value = st.text_input("Value/Description")
            
        with col3:
            keywords = st.text_input("Keywords/Synonyms", placeholder="comma, separated, keywords")
        
        if st.form_submit_button("Add"):
            if key and value:
                # Store with keywords for better search
                item_data = {
                    'value': value,
                    'keywords': [k.strip().lower() for k in keywords.split(',') if k.strip()] if keywords else []
                }
                current_data[key] = item_data
                info_data[category] = current_data
                data_manager.save_json(DATA_DIR / 'info.json', info_data)
                st.success("Item added!")
                st.rerun()
            else:
                st.error("Key and Value are required!")
    
    st.divider()
    
    # Edit existing items
    if current_data:
        st.write("Edit Existing Items")
        
        for key, value in current_data.items():
            with st.form(f"edit_{category}_{key}"):
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                
                # Handle both old format (string) and new format (dict)
                if isinstance(value, dict):
                    display_value = value.get('value', '')
                    keywords_list = value.get('keywords', [])
                else:
                    display_value = value
                    keywords_list = []
                
                with col1:
                    new_key = st.text_input("Key", value=key, key=f"key_{category}_{key}")
                
                with col2:
                    new_value = st.text_input("Value", value=display_value, key=f"value_{category}_{key}")
                
                with col3:
                    keywords_str = ', '.join(keywords_list)
                    new_keywords = st.text_input("Keywords", value=keywords_str, key=f"keywords_{category}_{key}")
                
                with col4:
                    st.write("Actions")
                    if st.form_submit_button("Save"):
                        if new_key and new_value:
                            # Remove old key if changed
                            if key != new_key and key in current_data:
                                del current_data[key]
                            
                            # Store with keywords
                            item_data = {
                                'value': new_value,
                                'keywords': [k.strip().lower() for k in new_keywords.split(',') if k.strip()] if new_keywords else []
                            }
                            current_data[new_key] = item_data
                            info_data[category] = current_data
                            data_manager.save_json(DATA_DIR / 'info.json', info_data)
                            st.success("Updated!")
                            st.rerun()
                    
                    if st.form_submit_button("Delete"):
                        if key in current_data:
                            del current_data[key]
                            info_data[category] = current_data
                            data_manager.save_json(DATA_DIR / 'info.json', info_data)
                            st.success("Deleted!")
                            st.rerun()
    else:
        st.info(f"No {category} items yet.")

def render_custom_categories(info_data: Dict):
    """Render custom categories management"""
    custom_data = info_data.get('custom_categories', {})
    
    # Add new category
    with st.form("add_custom_category"):
        st.write("Add New Category")
        category_name = st.text_input("Category Name")
        category_content = st.text_area("Content")
        
        if st.form_submit_button("Add Category"):
            if category_name and category_content:
                custom_data[category_name] = category_content
                info_data['custom_categories'] = custom_data
                data_manager.save_json(DATA_DIR / 'info.json', info_data)
                st.success("Category added!")
                st.rerun()
            else:
                st.error("Both fields are required!")
    
    st.divider()
    
    # Edit existing categories
    if custom_data:
        st.write("Edit Custom Categories")
        
        for category, content in custom_data.items():
            with st.expander(f"📝 {category}"):
                with st.form(f"edit_custom_{category}"):
                    new_name = st.text_input("Category Name", value=category)
                    new_content = st.text_area("Content", value=content, height=100)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.form_submit_button("Save"):
                            if new_name and new_content:
                                # Remove old category if name changed
                                if category != new_name and category in custom_data:
                                    del custom_data[category]
                                custom_data[new_name] = new_content
                                info_data['custom_categories'] = custom_data
                                data_manager.save_json(DATA_DIR / 'info.json', info_data)
                                st.success("Updated!")
                                st.rerun()
                    
                    with col2:
                        if st.form_submit_button("Delete"):
                            if category in custom_data:
                                del custom_data[category]
                                info_data['custom_categories'] = custom_data
                                data_manager.save_json(DATA_DIR / 'info.json', info_data)
                                st.success("Deleted!")
                                st.rerun()
    else:
        st.info("No custom categories yet.")


def render_unanswered_queries():
    """Render unanswered queries management"""
    st.subheader("❓ Unanswered Queries")
    
    unanswered_data = data_manager.load_json(DATA_DIR / 'unanswered_queries.json')
    
    if not unanswered_data:
        st.info("No unanswered queries yet.")
        return
    
    for idx, query_data in enumerate(unanswered_data):
        with st.expander(f"❓ {query_data['query'][:50]}..."):
            st.write(f"**Query:** {query_data['query']}")
            st.write(f"**Asked:** {datetime.datetime.fromisoformat(query_data['asked_at']).strftime('%Y-%m-%d %H:%M')}")
            
            # Convert to Q&A or delete
            with st.form(f"handle_query_{idx}"):
                answer = st.text_area("Provide Answer (optional)")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.form_submit_button("Convert to Q&A"):
                        if answer:
                            # Add to knowledge base
                            knowledge_base = data_manager.load_json(DATA_DIR / 'knowledge_base.json')
                            knowledge_base.append({
                                'question': query_data['query'],
                                'answer': answer,
                                'created_at': datetime.datetime.now().isoformat(),
                                'updated_at': datetime.datetime.now().isoformat()
                            })
                            data_manager.save_json(DATA_DIR / 'knowledge_base.json', knowledge_base)
                            
                            # Remove from unanswered
                            unanswered_data.pop(idx)
                            data_manager.save_json(DATA_DIR / 'unanswered_queries.json', unanswered_data)
                            
                            st.success("Added to knowledge base!")
                            st.rerun()
                        else:
                            st.error("Answer is required!")
                
                with col2:
                    if st.form_submit_button("Delete Query"):
                        unanswered_data.pop(idx)
                        data_manager.save_json(DATA_DIR / 'unanswered_queries.json', unanswered_data)
                        st.success("Query deleted!")
                        st.rerun()

def render_knowledge_base():
    """Render knowledge base management"""
    st.subheader("🧠 Knowledge Base")
    
    knowledge_data = data_manager.load_json(DATA_DIR / 'knowledge_base.json')
    
    # Add new Q&A
    with st.form("add_qa"):
        st.write("Add New Q&A")
        question = st.text_input("Question")
        answer = st.text_area("Answer")
        
        if st.form_submit_button("Add Q&A"):
            if question and answer:
                knowledge_data.append({
                    'question': question,
                    'answer': answer,
                    'created_at': datetime.datetime.now().isoformat(),
                    'updated_at': datetime.datetime.now().isoformat()
                })
                data_manager.save_json(DATA_DIR / 'knowledge_base.json', knowledge_data)
                st.success("Q&A added!")
                st.rerun()
            else:
                st.error("Both fields are required!")
    
    st.divider()
    
    # Manage existing Q&A
    if knowledge_data:
        st.write("Manage Existing Q&A")
        
        for idx, qa in enumerate(knowledge_data):
            with st.expander(f"🧠 {qa['question'][:50]}..."):
                with st.form(f"edit_qa_{idx}"):
                    new_question = st.text_input("Question", value=qa['question'])
                    new_answer = st.text_area("Answer", value=qa['answer'], height=100)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.form_submit_button("Save"):
                            if new_question and new_answer:
                                knowledge_data[idx] = {
                                    'question': new_question,
                                    'answer': new_answer,
                                    'created_at': qa['created_at'],
                                    'updated_at': datetime.datetime.now().isoformat()
                                }
                                data_manager.save_json(DATA_DIR / 'knowledge_base.json', knowledge_data)
                                st.success("Updated!")
                                st.rerun()
                            else:
                                st.error("Both fields are required!")
                    
                    with col2:
                        if st.form_submit_button("Delete"):
                            knowledge_data.pop(idx)
                            data_manager.save_json(DATA_DIR / 'knowledge_base.json', knowledge_data)
                            st.success("Deleted!")
                            st.rerun()
    else:
        st.info("No Q&A pairs yet.")

def render_admin_settings():
    """Render admin settings"""
    st.subheader("🔧 Settings")
    
    # Change password
    with st.form("change_password"):
        st.write("Change Password")
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        password_hint = st.text_input("Password Hint")
        
        if st.form_submit_button("Change Password"):
            auth_data = data_manager.load_json(DATA_DIR / 'auth.json')
            current_hash = data_manager.hash_password(current_password)
            
            if current_hash != auth_data['password_hash']:
                st.error("Current password is incorrect!")
            elif new_password != confirm_password:
                st.error("New passwords don't match!")
            elif len(new_password) < 3:
                st.error("Password must be at least 3 characters!")
            else:
                auth_data['password_hash'] = data_manager.hash_password(new_password)
                auth_data['password_hint'] = password_hint if password_hint else "No hint provided"
                data_manager.save_json(DATA_DIR / 'auth.json', auth_data)
                st.success("Password changed successfully!")
    
    st.divider()
    
    # System information
    st.write("### System Information")
    st.info(f"**Data Directory:** {DATA_DIR.absolute()}")
    st.info(f"**Notes Directory:** {NOTES_DIR.absolute()}")
    st.info(f"**Chats Directory:** {CHATS_DIR.absolute()}")
    
    # Export data option
    if st.button("📤 Export All Data"):
        try:
            export_data = {
                'notes_metadata': data_manager.load_json(DATA_DIR / 'notes_metadata.json'),
                'info': data_manager.load_json(DATA_DIR / 'info.json'),
                'synonyms': data_manager.load_json(DATA_DIR / 'synonyms.json'),
                'knowledge_base': data_manager.load_json(DATA_DIR / 'knowledge_base.json'),
                'unanswered_queries': data_manager.load_json(DATA_DIR / 'unanswered_queries.json'),
                'export_date': datetime.datetime.now().isoformat()
            }
            
            export_json = json.dumps(export_data, indent=2, default=str)
            st.download_button(
                "📥 Download Export",
                export_json,
                f"smartbuddy_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "application/json"
            )
        except Exception as e:
            st.error(f"Export failed: {str(e)}")

# Main application logic
def main():
    # Apply theme first
    apply_theme()
    
    render_sidebar()
    
    if st.session_state.page == 'chat':
        render_chat_interface()
    elif st.session_state.page == 'admin_login':
        render_admin_login()
    elif st.session_state.page == 'admin_panel' and st.session_state.authenticated:
        render_admin_panel()
    else:
        # Fallback to chat
        st.session_state.page = 'chat'
        render_chat_interface()

if __name__ == "__main__":
    main()
