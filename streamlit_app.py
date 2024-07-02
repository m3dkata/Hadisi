import hashlib
import json
import os
import re
import secrets
from networkx import center
import streamlit as st
import aiohttp
from bs4 import BeautifulSoup
import sqlite3
import asyncio
from googletrans import Translator
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial
import aiohttp
from streamlit.runtime.scriptrunner import RerunException
from streamlit_extras.stoggle import stoggle
from streamlit_extras.card import card
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt
from st_keyup import st_keyup
import streamlit.components.v1 as components
import re

if 'sidebar_state' not in st.session_state:
    st.session_state.sidebar_state = 'expanded'

if 'content_visible' not in st.session_state:
    st.session_state.content_visible = True  # Content is visible on initial load    


st.set_page_config(
    layout="wide",
    page_title="Хадисите на Мухаммед(С.А.С)",
    page_icon='logo.png',
    initial_sidebar_state=st.session_state.sidebar_state,
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

def custom_html(html_string, width=None, height=None, scrolling=False):
    # Remove the allow-downloads attribute
    html_string = re.sub(r'sandbox="([^"]*)\s*allow-downloads\s*([^"]*)"', r'sandbox="\1 \2"', html_string)
    return components.html(html_string, width, height, scrolling)

# Override Streamlit's html component
components.html = custom_html

st.markdown("""
<script>
// Polyfill for RegExp lookbehind
if (!RegExp.prototype.lookbehind) {
    RegExp.prototype.lookbehind = function(str) {
        return str.match(this);
    };
}

// Override problematic RegExp methods
var originalExec = RegExp.prototype.exec;
RegExp.prototype.exec = function(str) {
    try {
        return originalExec.call(this, str);
    } catch (e) {
        console.warn('RegExp compatibility issue:', e.message);
        return null;
    }
};

var originalTest = RegExp.prototype.test;
RegExp.prototype.test = function(str) {
    try {
        return originalTest.call(this, str);
    } catch (e) {
        console.warn('RegExp compatibility issue:', e.message);
        return false;
    }
};
</script>
""", unsafe_allow_html=True)


with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Generate hashed password
# password = "Breznitsa7229"
# hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
# print(hashed_password)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hide Streamlit's default footer
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
.stActionButton {visibility: hidden;}
.block-container {
    padding-top: 0;
    padding-left: 2rem;
    padding-right: 2rem;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stSidebarUserContent"] {
    margin-top: 10px;
    padding-top: 0rem;
}
@media (max-width: 640px) {
    .block-container {
    padding-top: 1px;
    padding-left: 1rem;
    padding-right: 1rem;
    }
}
}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.markdown("""
<style>
    .sidebar-divider {
        margin-top: 1px;
        margin-bottom: 1px;
        border-top: 1px solid;
        color: {theme.textColor} inherit;
    }
    #github{
        background-image: url("data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0iY3VycmVudENvbG9yIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGNvbG9yPSIjMzEzMzNGIj48cGF0aCBmaWxsLXJ1bGU9ImV2ZW5vZGQiIGNsaXAtcnVsZT0iZXZlbm9kZCIgZD0iTTguMDA2NjIgMC4zNTAwMDZDMy41NzkxNyAwLjM1MDAwNiAwIDMuODU1NCAwIDguMTkyMDZDMCAxMS42NTg2IDIuMjkzMjkgMTQuNTkyOSA1LjQ3NDcgMTUuNjMxNUM1Ljg3MjQ2IDE1LjcwOTUgNi4wMTgxNiAxNS40NjI3IDYuMDE4MTYgMTUuMjU1MUM2LjAxODE2IDE1LjA3MzMgNi4wMDUwNSAxNC40NTAxIDYuMDA1MDUgMTMuODAwOUMzLjc3NzggMTQuMjY4MyAzLjMxMzk5IDEyLjg2NiAzLjMxMzk5IDEyLjg2NkMyLjk1NjA2IDExLjk1NzIgMi40MjU3MiAxMS43MjM2IDIuNDI1NzIgMTEuNzIzNkMxLjY5Njc0IDExLjI0MzIgMi40Nzg4MiAxMS4yNDMyIDIuNDc4ODIgMTEuMjQzMkMzLjI4NzQ0IDExLjI5NTEgMy43MTE3NSAxMi4wNDgyIDMuNzExNzUgMTIuMDQ4MkM0LjQyNzQ1IDEzLjI0MjUgNS41ODA3NCAxMi45MDUxIDYuMDQ0NzEgMTIuNjk3M0M2LjExMDkyIDEyLjE5MDkgNi4zMjMxNSAxMS44NDA0IDYuNTQ4NSAxMS42NDU3QzQuNzcyMTEgMTEuNDYzOSAyLjkwMzEyIDEwLjc4ODggMi45MDMxMiA3Ljc3NjUxQzIuOTAzMTIgNi45MTk2IDMuMjIxMDcgNi4yMTg1MiAzLjcyNDg2IDUuNjczMjdDMy42NDUzOCA1LjQ3ODU2IDMuMzY2OTMgNC42NzM0NCAzLjgwNDUxIDMuNTk1ODRDMy44MDQ1MSAzLjU5NTg0IDQuNDgwNTUgMy4zODgwNyA2LjAwNDg4IDQuNDAwODFDNi42NTc1IDQuMjI5MTUgNy4zMzA1NCA0LjE0MTgzIDguMDA2NjIgNC4xNDEwOUM4LjY4MjY2IDQuMTQxMDkgOS4zNzE4MSA0LjIzMjA3IDEwLjAwODIgNC40MDA4MUMxMS41MzI3IDMuMzg4MDcgMTIuMjA4NyAzLjU5NTg0IDEyLjIwODcgMy41OTU4NEMxMi42NDYzIDQuNjczNDQgMTIuMzY3NyA1LjQ3ODU2IDEyLjI4ODIgNS42NzMyN0MxMi44MDUzIDYuMjE4NTIgMTMuMTEwMSA2LjkxOTYgMTMuMTEwMSA3Ljc3NjUxQzEzLjExMDEgMTAuNzg4OCAxMS4yNDExIDExLjQ1MDggOS40NTE0NiAxMS42NDU3QzkuNzQzMTggMTEuODkyMyA5Ljk5NDkyIDEyLjM1OTcgOS45OTQ5MiAxMy4wOTk4QzkuOTk0OTIgMTQuMTUxNCA5Ljk4MTgxIDE0Ljk5NTQgOS45ODE4MSAxNS4yNTVDOS45ODE4MSAxNS40NjI3IDEwLjEyNzcgMTUuNzA5NSAxMC41MjUzIDE1LjYzMTZDMTMuNzA2NyAxNC41OTI4IDE2IDExLjY1ODYgMTYgOC4xOTIwNkMxNi4wMTMxIDMuODU1NCAxMi40MjA4IDAuMzUwMDA2IDguMDA2NjIgMC4zNTAwMDZaIj48L3BhdGg+PC9zdmc+");
background-position-x: center;
background-position-y: center;
background-size: contain;
background-repeat: no-repeat;
width: 1.5rem;
height: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Define the HTML for the header
header_html = """
<style>
header-mine {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 65px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px;
    background-color: {blur}; /* Semi-transparent background */
    backdrop-filter: blur(10px); /* This creates the blur effect */
    -webkit-backdrop-filter: blur(10px); /* For Safari support */
    z-index: 1000;
    
}
.header-left {
    display: flex;
    align-items: center;
}
.header-right {
    display: flex;
    align-items: center;
}
.header-logo {
    height: 40px;
    margin-right: 10px;
}
.header-title {
    font-size: 1.2rem;
    font-weight: bold;
}
.header-links a {
    margin-left: 15px;
    text-decoration: none;
    color: #007bff;
}
.header-links a:hover {
    text-decoration: underline;
}
</style>
<header-mine>
    <div class="header-left">
    </div>
    <div class="header-right header-links">
        <a id="github" href="https://github.com/m3dkata"></a>
    </div>
</header-mine>
"""

# Inject the HTML into the Streamlit app
st.markdown(header_html, unsafe_allow_html=True)

ms = st.session_state
if "themes" not in ms: 
  ms.themes = {"current_theme": "light",
                    "refreshed": True,
                    
                    "light": {"theme.base": "dark",
                              "theme.backgroundColor": "#0E1117",
                              "theme.primaryColor": "#FF4B4B",
                              "theme.secondaryBackgroundColor": "#262730",
                              "theme.textColor": "#FAFAFA",
                              "button_face": "Тъмна тема 🌓",
                              "blur": "rgba(0, 0, 0, 0.5)"},

                    "dark":  {"theme.base": "light",
                              "theme.backgroundColor": "#FFFFFF",
                              "theme.primaryColor": "#FF4B4B",
                              "theme.secondaryBackgroundColor": "#F0F2F6",
                              "theme.textColor": "#31333F",
                              "button_face": "Светла тема 🌞",
                              "blur":"rgba(255, 255, 255, 0.5)"},
                    }
  

def ChangeTheme():
  previous_theme = ms.themes["current_theme"]
  tdict = ms.themes["light"] if ms.themes["current_theme"] == "light" else ms.themes["dark"]
  for vkey, vval in tdict.items(): 
    if vkey.startswith("theme"): st._config.set_option(vkey, vval)

  ms.themes["refreshed"] = False
  if previous_theme == "dark": ms.themes["current_theme"] = "light"
  elif previous_theme == "light": ms.themes["current_theme"] = "dark"


btn_face = ms.themes["light"]["button_face"] if ms.themes["current_theme"] == "light" else ms.themes["dark"]["button_face"]
st.sidebar.button(btn_face, on_click=ChangeTheme)

if ms.themes["refreshed"] == False:
  ms.themes["refreshed"] = True
  st.experimental_rerun()

# Database setup
DATABASE_URL = "sqlite:///hadiths.db"
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Caching
# Caching database queries
@st.cache_data
def get_books():
    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()
    c.execute("SELECT id, book_name, english, arabic FROM books")
    books = c.fetchall()
    conn.close()
    return books

@st.cache_data
def get_matching_pages(book_id, search_term):
    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT p.id, p.book_page_number, p.book_page_bulgarian_name
        FROM pages p
        JOIN chapters c ON p.id = c.page_id
        WHERE p.book_id = ? AND (
            LOWER(c.bulgarianchapter) LIKE ? OR
            LOWER(c.english_hadith_full) LIKE ? OR
            LOWER(c.bulgarian_hadith_full) LIKE ?
        )
        ORDER BY CAST(p.book_page_number AS INTEGER)
    """, (book_id, f"%{search_term.lower()}%", f"%{search_term.lower()}%", f"%{search_term.lower()}%"))
    pages = c.fetchall()
    conn.close()
    return pages

@st.cache_data
def get_matching_chapters(page_id, search_term):
    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()
    c.execute("""
        SELECT id, echapno, bulgarianchapter
        FROM chapters
        WHERE page_id = ? AND (
            LOWER(bulgarianchapter) LIKE ? OR
            LOWER(english_hadith_full) LIKE ? OR
            LOWER(bulgarian_hadith_full) LIKE ?
        )
        ORDER BY echapno
    """, (page_id, f"%{search_term.lower()}%", f"%{search_term.lower()}%", f"%{search_term.lower()}%"))
    chapters = c.fetchall()
    conn.close()
    return chapters

@st.cache_data
def get_pages(book_id):
    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()
    c.execute("SELECT id, book_page_number, book_page_bulgarian_name FROM pages WHERE book_id = ? ORDER BY CAST(book_page_number AS INTEGER)", (book_id,))
    pages = c.fetchall()
    conn.close()
    return pages

@st.cache_data
def get_chapters(page_id):
    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()
    c.execute("SELECT id, echapno, bulgarianchapter FROM chapters WHERE page_id = ? ORDER BY echapno", (page_id,))
    chapters = c.fetchall()
    conn.close()
    return chapters


# Initialize the translator
translator = Translator()

async def fetch_page(session, url):
    async with session.get(url) as response:
        return await response.text()

async def scrape_main_page(url):
    async with aiohttp.ClientSession() as session:
        try:
            html = await fetch_page(session, url)
            soup = BeautifulSoup(html, 'html.parser')
            
            collection_info = soup.find('div', class_='collection_info')
            if not collection_info:
                logger.error(f"Collection info not found on page: {url}")
                return None

            colindextitle = collection_info.find('div', class_='colindextitle incomplete')
            if not colindextitle:
                logger.error(f"Colindextitle not found on page: {url}")
                return None

            arabic = colindextitle.find('div', class_='arabic')
            english = colindextitle.find('div', class_='english')
            colindextitle_text = collection_info.find('div', class_='colindextitle', recursive=False)

            if not all([arabic, english, colindextitle_text]):
                logger.error(f"Missing required elements on page: {url}")
                return None

            arabic_text = arabic.text.strip()
            english_text = english.text.strip()
            colindextitle_text = colindextitle_text.text.strip()

            # Translate colindextitle to Bulgarian
            try:
                bulgarian_colindextitle = await translate_text(colindextitle_text, 'en', 'bg')
            except Exception as e:
                logger.error(f"Error translating colindextitle: {str(e)}")
                bulgarian_colindextitle = colindextitle_text  # Fallback to English

            return {
                'english': english_text,
                'arabic': arabic_text,
                'colindextitle': colindextitle_text,
                'bulgarian_colindextitle': bulgarian_colindextitle
            }
        except Exception as e:
            logger.error(f"Unexpected error processing main page {url}: {str(e)}")
            return None

async def scrape_book_page(html):
    try:
        soup = BeautifulSoup(html, 'html.parser')
        logger.debug("BeautifulSoup object created")

        # Check if the page contains any content
        main_content = soup.find('div', id='main')
        if not main_content:
            logger.warning("Main content div not found on page")
            return None

        book_info = soup.find('div', class_='book_info')
        logger.debug(f"Book info found: {book_info is not None}")

        if not book_info:
            logger.warning("Book info not found on page")
            return None

        book_page_arabic_name = book_info.find('div', class_='book_page_arabic_name')
        book_page_number = book_info.find('div', class_='book_page_number')
        book_page_english_name = book_info.find('div', class_='book_page_english_name')

        logger.debug(f"Book page elements found: Arabic={book_page_arabic_name is not None}, Number={book_page_number is not None}, English={book_page_english_name is not None}")

        if not all([book_page_arabic_name, book_page_number, book_page_english_name]):
            logger.warning("Missing required book info elements on page")
            return None

        book_page_bulgarian_name = await translate_text(book_page_english_name.text.strip(), 'en', 'bg')

        chapters = []
        all_elements = soup.find_all(['div', 'actualHadithContainer'])

        if not all_elements:
            logger.warning("No chapters or hadiths found on page")
            return None

        current_echapno = None
        sub_chapter_counter = 0
        previous_content = None

        for element in all_elements:
            try:
                if 'chapter' in element.get('class', []):
                    echapno_elem = element.find('div', class_='echapno')
                    if echapno_elem:
                        current_echapno = echapno_elem.text.strip('()')
                        sub_chapter_counter = 0
                    englishchapter = element.find('div', class_='englishchapter')
                    englishchapter = englishchapter.text.strip() if englishchapter else f"Chapter: {current_echapno}"
                    arabicchapter = element.find('div', class_='arabicchapter')
                    arabicchapter = arabicchapter.text.strip() if arabicchapter else ""
                    bulgarianchapter = await translate_text(englishchapter, 'en', 'bg')
                    arabic_achapintro = element.find_next_sibling('div', class_='arabic achapintro aconly')
                    arabic_achapintro = arabic_achapintro.text.strip() if arabic_achapintro else ""
                    hadith = element.find_next_sibling('div', class_='actualHadithContainer')
                elif 'actualHadithContainer' in element.get('class', []):
                    hadith = element
                    sub_chapter_counter += 1
                    englishchapter = f"{sub_chapter_counter}"
                    arabicchapter = ""
                    bulgarianchapter = f"{sub_chapter_counter}"
                    arabic_achapintro = ""
                else:
                    continue

                if not hadith:
                    logger.warning("Hadith container not found for chapter on page")
                    continue

                hadith_narrated = hadith.find('div', class_='hadith_narrated')
                english_hadith_full = hadith.find('div', class_='text_details')
                arabic_hadith_full = hadith.find('div', class_='arabic_hadith_full')

                if not all([english_hadith_full, arabic_hadith_full]):
                    logger.warning("Missing hadith elements for chapter on page")
                    continue

                bulgarian_hadith_full = await translate_text(english_hadith_full.text.strip(), 'en', 'bg')

                hadith_reference = hadith.find('table', class_='hadith_reference')
                hadith_reference_html = str(hadith_reference) if hadith_reference else ""

                echapno = f"{current_echapno}.{sub_chapter_counter}" if current_echapno else str(sub_chapter_counter)

                # Create a content string to compare
                content = f"{englishchapter}{arabicchapter}{bulgarianchapter}{arabic_achapintro}{hadith_narrated.text.strip() if hadith_narrated else ''}{english_hadith_full.text.strip() if english_hadith_full else ''}{arabic_hadith_full.text.strip() if arabic_hadith_full else ''}"

                # Only add the chapter if the content is different from the previous one
                if content != previous_content:
                    chapters.append({
                        'echapno': echapno,
                        'englishchapter': englishchapter,
                        'arabicchapter': arabicchapter,
                        'bulgarianchapter': bulgarianchapter,
                        'arabic_achapintro': arabic_achapintro,
                        'hadith_narrated': hadith_narrated.text.strip() if hadith_narrated else "",
                        'english_hadith_full': english_hadith_full.text.strip() if english_hadith_full else "",
                        'arabic_hadith_full': arabic_hadith_full.text.strip() if arabic_hadith_full else "",
                        'bulgarian_hadith_full': bulgarian_hadith_full,
                        'hadith_reference': hadith_reference_html
                    })
                    previous_content = content
                else:
                    logger.info(f"Skipping duplicate content for echapno {echapno}")

            except AttributeError as e:
                logger.error(f"Error processing chapter on page: {str(e)}")
                continue

        return {
            'book_page_number': book_page_number.text.strip() if book_page_number else "",
            'book_page_english_name': book_page_english_name.text.strip() if book_page_english_name else "",
            'book_page_arabic_name': book_page_arabic_name.text.strip() if book_page_arabic_name else "",
            'book_page_bulgarian_name': book_page_bulgarian_name,
            'chapters': chapters
        }

    except Exception as e:
        logger.error(f"Unexpected error in scrape_book_page: {str(e)}")
        logger.error(f"HTML content: {html[:500]}...")  # Log the first 500 characters of HTML
        return None

def is_valid_content_page(soup):
    # Check for elements that should be present on a valid content page
    if soup.find('div', id='main') and soup.find('div', class_='book_info'):
        return True
    return False

async def translate_text(text, src, dest):
    return translator.translate(text, src=src, dest=dest).text

def insert_into_database(conn, data):
    if data is None:
        return
    
    book_id, page_number, page_data = data
    with conn:
        c = conn.cursor()
        c.execute("INSERT INTO pages (book_id, book_page_number, book_page_english_name, book_page_arabic_name, book_page_bulgarian_name) VALUES (?, ?, ?, ?, ?)",
                  (book_id, page_data['book_page_number'], page_data['book_page_english_name'], page_data['book_page_arabic_name'], page_data['book_page_bulgarian_name']))
        page_id = c.lastrowid
        
        for chapter in page_data['chapters']:
            c.execute("""INSERT INTO chapters
                         (page_id, echapno, englishchapter, arabicchapter, bulgarianchapter, arabic_achapintro,
                          hadith_narrated, english_hadith_full, arabic_hadith_full, bulgarian_hadith_full, hadith_reference)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (page_id, chapter['echapno'], chapter['englishchapter'], chapter['arabicchapter'],
                       chapter['bulgarianchapter'], chapter['arabic_achapintro'], chapter['hadith_narrated'],
                       chapter['english_hadith_full'], chapter['arabic_hadith_full'], chapter['bulgarian_hadith_full'],
                       chapter['hadith_reference']))

async def scrape_and_translate_page(session, book_id, page_number, book_name):
    url = f"https://sunnah.com/{book_name}/{page_number}"
    try:
        html = await fetch_page(session, url)
        if not html:
            logger.warning(f"No HTML content fetched for page {page_number}")
            return None
        
        page_data = await scrape_book_page(html)
        
        if page_data:
            return book_id, page_number, page_data
        else:
            logger.warning(f"No data found for page {page_number}")
            return None
    except Exception as e:
        logger.error(f"Error scraping page {page_number}: {str(e)}")
        return None

async def populate_database(book_name, start_page, end_page):
    conn = sqlite3.connect('hadiths.db', check_same_thread=False)
    c = conn.cursor()
   
    # Check if the book already exists
    c.execute("SELECT id FROM books WHERE book_name = ?", (book_name,))
    existing_book = c.fetchone()
   
    if existing_book:
        book_id = existing_book[0]
        st.info(f"Книга '{book_name}' вече съществува в базата данни. Използване на съществуващ идентификатор на книга: {book_id}")
    else:
        # Scrape main page only if the book doesn't exist
        main_url = f"https://sunnah.com/{book_name}"
        main_data = await scrape_main_page(main_url)
       
        if not main_data:
            st.error(f"Failed to scrape main page for book {book_name}")
            conn.close()
            return

        c.execute("INSERT INTO books (book_name, english, arabic, colindextitle, bulgarian_colindextitle) VALUES (?, ?, ?, ?, ?)",
                  (book_name, main_data['english'], main_data['arabic'], main_data['colindextitle'], main_data['bulgarian_colindextitle']))
        book_id = c.lastrowid
        conn.commit()
        st.success(f"Добавена нова книга '{book_name}' към базата данни с ID: {book_id}")

    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()

    async with aiohttp.ClientSession() as session:
        total_pages = end_page - start_page + 1
        for i, page_number in enumerate(range(start_page, end_page + 1), 1):
            status_text.caption(f":green[Обработване на Глава {page_number} от {end_page}]")
           
            # Check if the page already exists
            c.execute("SELECT id FROM pages WHERE book_id = ? AND book_page_number = ?", (book_id, str(page_number)))
            existing_page = c.fetchone()
           
            if existing_page:
                page_id = existing_page[0]
                st.caption(f":blue[Страница {page_number} вече съществува. Пропускане на скрейпването.]")
            else:
                # Scrape the page only if it doesn't exist
                result = await scrape_and_translate_page(session, book_id, page_number, book_name)
               
                if result:
                    _, _, page_data = result
                   
                    c.execute("INSERT INTO pages (book_id, book_page_number, book_page_english_name, book_page_arabic_name, book_page_bulgarian_name) VALUES (?, ?, ?, ?, ?)",
                              (book_id, page_data['book_page_number'], page_data['book_page_english_name'], page_data['book_page_arabic_name'], page_data['book_page_bulgarian_name']))
                    page_id = c.lastrowid
                   
                    for chapter in page_data['chapters']:
                        # Check if the chapter already exists
                        c.execute("""SELECT id FROM chapters
                                     WHERE page_id = ? AND
                                           (english_hadith_full = ? OR
                                            arabic_hadith_full = ? OR
                                            bulgarian_hadith_full = ?)""",
                                  (page_id, chapter['english_hadith_full'], chapter['arabic_hadith_full'], chapter['bulgarian_hadith_full']))
                        existing_chapter = c.fetchone()
                       
                        if not existing_chapter:
                            c.execute("""INSERT INTO chapters
                                         (page_id, echapno, englishchapter, arabicchapter, bulgarianchapter, arabic_achapintro,
                                          hadith_narrated, english_hadith_full, arabic_hadith_full, bulgarian_hadith_full, hadith_reference)
                                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                      (page_id, chapter['echapno'], chapter['englishchapter'], chapter['arabicchapter'],
                                       chapter['bulgarianchapter'], chapter['arabic_achapintro'], chapter['hadith_narrated'],
                                       chapter['english_hadith_full'], chapter['arabic_hadith_full'], chapter['bulgarian_hadith_full'],
                                       chapter['hadith_reference']))
                        else:
                            pass
                            # st.caption(f":blue[Глава {chapter['echapno']} вече съществува. Пропускане.]")
                   
                    conn.commit()
                    st.caption(f"Обработена: Глава {page_number} - {page_data['book_page_english_name']} ({len(page_data['chapters'])} хадиса)")
                else:
                    st.caption(f":red[Неуспешно скрейпване на страница {page_number}]")
           
            # Update progress
            progress = i / total_pages
            progress_bar.progress(progress)

    conn.close()
    status_text.text("Всички страници са обработени.")
    progress_bar.progress(1.0)
    st.success("Базата данни е актуализирана успешно с преводите!")
    st.cache_data.clear()
    st.experimental_rerun()


def create_database():
    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()
    
    # Create books table
    c.execute('''CREATE TABLE IF NOT EXISTS books
                 (id INTEGER PRIMARY KEY, 
                  book_name TEXT, 
                  english TEXT, 
                  arabic TEXT, 
                  colindextitle TEXT, 
                  bulgarian_colindextitle TEXT)''')
    
    # Create pages table with ON DELETE CASCADE and ON UPDATE CASCADE
    c.execute('''CREATE TABLE IF NOT EXISTS pages
                 (id INTEGER PRIMARY KEY, 
                  book_id INTEGER, 
                  book_page_number TEXT, 
                  book_page_english_name TEXT, 
                  book_page_arabic_name TEXT, 
                  book_page_bulgarian_name TEXT,
                  FOREIGN KEY (book_id) REFERENCES books(id)
                  ON DELETE CASCADE ON UPDATE CASCADE)''')
    
    # Create chapters table with ON DELETE CASCADE and ON UPDATE CASCADE
    c.execute('''CREATE TABLE IF NOT EXISTS chapters
                 (id INTEGER PRIMARY KEY, 
                  page_id INTEGER, 
                  echapno TEXT, 
                  englishchapter TEXT, 
                  arabicchapter TEXT, 
                  bulgarianchapter TEXT,
                  arabic_achapintro TEXT, 
                  hadith_narrated TEXT, 
                  english_hadith_full TEXT, 
                  arabic_hadith_full TEXT, 
                  bulgarian_hadith_full TEXT,
                  hadith_reference TEXT,
                  FOREIGN KEY (page_id) REFERENCES pages(id)
                  ON DELETE CASCADE ON UPDATE CASCADE)''')
    # Add indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_books_book_name ON books(book_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_pages_book_id ON pages(book_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_chapters_page_id ON chapters(page_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_chapters_echapno ON chapters(echapno)')
    
    conn.commit()
    conn.close()

def update_chapter_text(cursor, chapter_id, new_text):
    try:
        cursor.execute("""
            UPDATE chapters
            SET bulgarian_hadith_full = ?
            WHERE id = ?
        """, (new_text, chapter_id))
        cursor.connection.commit()
        return True
    except Exception as e:
        print(f"Error updating chapter text: {e}")
        return False


def display_chapter(cursor, chapter_id):
    cursor.execute("""
        SELECT c.echapno, c.englishchapter, c.arabicchapter, c.bulgarianchapter,
               c.arabic_achapintro, c.hadith_narrated, c.english_hadith_full, c.arabic_hadith_full, c.bulgarian_hadith_full,
               p.book_page_number, p.book_page_english_name, p.book_page_arabic_name, p.book_page_bulgarian_name,
               c.hadith_reference
        FROM chapters c
        JOIN pages p ON c.page_id = p.id
        WHERE c.id = ?
    """, (chapter_id,))
    chapter_data = cursor.fetchone()

    if chapter_data:
        # Custom CSS for consistent two-column layout
        st.markdown("""
        <style>
        .custom-container {
            display: flex;
            flex-wrap: nowrap;
            width: 100%;
        }
        .custom-column {
            width: 50%;
            margin: 2px;
            padding: 2px;
            border: 1px solid;
            border-color: inherit;
            border-radius: 10px;
        }
        .custom-text {
            word-wrap: break-word;
            overflow-wrap: break-word;
            font-size: 1.0em;
            margin: 1px;
            padding: 1px;
        }
        @media (max-width: 640px) {
            .custom-text {
                font-size: 0.9em;
            }
        }
        </style>
        """, unsafe_allow_html=True)
        # Book and chapter information
        st.markdown(f"""
        <div class="custom-container">
            <div class="custom-column">
                <h3 class="custom-text">{chapter_data[9].replace("'", "")}. {chapter_data[12].upper()}</h3>
            </div>
            <div class="custom-column">
                <h3 class="custom-text">{chapter_data[9]}. {chapter_data[11]}</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)
        # st.markdown("<hr>", unsafe_allow_html=True)

        # col1, col2, col3 = st.columns(3)
        # Chapter titles
        st.markdown(f"""
        <div class="custom-container">
            <div class="custom-column">
                <h3 class="custom-text">{chapter_data[0]}. {chapter_data[3].strip('Глава:')}</h3>
            </div>
            <div class="custom-column">
                <h3 class="custom-text">{chapter_data[0]}. {chapter_data[2]}</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)        
        # with col3:
        #     st.subheader(f"{chapter_data[0]}. {chapter_data[1].strip('Chapter:')}")
        # st.divider()
        # col1, col2, col3 = st.columns(3)
        # Hadith text
        bulgarian_text = chapter_data[8]
        bulgarian_text = bulgarian_text.replace("(ﷺ)", "(С.А.С)")
        bulgarian_text = bulgarian_text.replace("`", "")
        arabic_text = chapter_data[7]
        # Add edit button and editing functionality
        if st.session_state["authentication_status"] and st.session_state["username"] == "moderator":
            edit_button = st.button(":lower_left_ballpoint_pen: РЕДАКТИРАНЕ", key=f"edit_button_{chapter_id}")
            if edit_button:
                st.session_state[f"editing_{chapter_id}"] = True

            if st.session_state.get(f"editing_{chapter_id}", False):
                edited_text = st.text_area("Редактирай българския текст", value=bulgarian_text, key=f"edit_area_{chapter_id}")
                save_button = st.button("Запази", key=f"save_button_{chapter_id}")
                if save_button:
                    success = update_chapter_text(cursor, chapter_id, edited_text)
                    if success:
                        st.session_state[f"message_{chapter_id}"] = "Текстът е успешно актуализиран!"
                    else:
                        st.session_state[f"message_{chapter_id}"] = "Грешка при актуализиране на текста."
                    st.session_state[f"editing_{chapter_id}"] = False
                    st.experimental_rerun()

            # Display any pending messages
            if f"message_{chapter_id}" in st.session_state:
                if "успешно" in st.session_state[f"message_{chapter_id}"]:
                    st.success(st.session_state[f"message_{chapter_id}"])
                else:
                    st.error(st.session_state[f"message_{chapter_id}"])
                del st.session_state[f"message_{chapter_id}"]  # Clear the message after displaying

            if not st.session_state.get(f"editing_{chapter_id}", False):
                st.markdown(f"""
                <div class="custom-container">
                    <div class="custom-column">
                        <p class="custom-text">{bulgarian_text}</p>
                    </div>
                    <div class="custom-column">
                        <p class="custom-text">{arabic_text}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="custom-container">
                <div class="custom-column">
                    <p class="custom-text">{bulgarian_text}</p>
                </div>
                <div class="custom-column">
                    <p class="custom-text">{arabic_text}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # with col3:
        #     english_text = chapter_data[6]
        #     english_text = english_text.replace("(ﷺ)", "(p.b.u.h)")
        #     english_text = english_text.replace("`", "")
        #     st.write(english_text)
        
        # Display the reference table
        st.caption("Референции в https://sunnah.com")
        references = chapter_data[13]
        references = references.replace("Reference", "Референция")
        references = references.replace("Book", "Книга")
        references = references.replace("Hadith", "Хадис")
        references = references.replace(":", "")
        references = re.sub(r'<a[^>]*>(.*?)</a>', r'\1', references)
        references = references.replace("In-book reference", "референция в книгата")
        references = references.replace("(deprecated numbering scheme)", "(отхвърлена схема за номериране)")
        st.caption(references, unsafe_allow_html=True)

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def scrape_books():
    json_file = 'books_data.json'
    books_data = load_json(json_file)
    
    if books_data is None or any('start_page' not in book for book in books_data):
        if books_data is None:
            books_data = []
            url = "https://sunnah.com/"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    content = await response.text()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            for title in soup.find_all('div', class_='collection_title'):
                link = title.find('a')
                if link:
                    book_name = link['href'].split('/')[-1]
                    english_name = title.find('div', class_='english_collection_title').text.strip()
                    arabic_name = title.find('div', class_='arabic_collection_title').text.strip()
                    books_data.append({
                        "book_name": book_name,
                        "english_name": english_name,
                        "arabic_name": arabic_name
                    })
        
        # Update or add page range for each book
        for book in books_data:
            if 'start_page' not in book or 'end_page' not in book:
                start, end = await get_book_range(book['book_name'])
                book['start_page'] = start
                book['end_page'] = end
        
        save_json(books_data, json_file)
    
    return books_data

async def get_book_range(book_name):
    url = f"https://sunnah.com/{book_name}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            content = await response.text()
    
    soup = BeautifulSoup(content, 'html.parser')
    
    book_titles = soup.find_all('div', class_='book_title')
    
    logger.info(f"Found {len(book_titles)} book titles for {book_name}")
    
    if book_titles:
        first_book = book_titles[0]
        last_book = book_titles[-1]
        
        start_number = first_book.find('div', class_='book_number title_number')
        end_number = last_book.find('div', class_='book_number title_number')
        
        logger.info(f"Start number element: {start_number}")
        logger.info(f"End number element: {end_number}")
        
        start = int(start_number.text) if start_number and start_number.text.strip() else 1
        end = int(end_number.text) if end_number and end_number.text.strip() else 10
        
        logger.info(f"Determined range for {book_name}: {start} to {end}")
        
        return start, end
    
    logger.warning(f"No book titles found for {book_name}, using default range")
    return 1, 10
    
def change():
    st.session_state.sidebar_state = (
        "expanded" if st.session_state.sidebar_state == "collapsed" else "collapsed"
    )

async def main_async():

    create_database()
    

    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()
    
    # Sidebar with tree-like structure
    HORIZONTAL_RED = "main_logo.png"
    ICON_RED = "logo.png"
    # st.logo(ICON_RED)
    
    if st.session_state.content_visible:
        col1, col2, col3 = st.columns([2,1,2])
        # Get total chapter count
        # c.execute("SELECT COUNT(*) FROM chapters")
        # total_chapters = c.fetchone()[0]

        with col1:
            pass
        with col2:
            st.image("logo.png", width=200, use_column_width="always")
        with col3:
            pass
        empty1, col3_text, empty2 = st.columns([1,2,1])
        with empty1:
            st.empty()
        with col3_text:
            st.subheader(f":rainbow[Хадиси с български и арабски текст от] :red[https://sunnah.com] ")
            # st.subheader(f":red[{total_chapters}] :rainbow[Хадиси с български и арабски текст]")
        with empty2:
            st.empty()    
    
        # Render login widget
        authenticator.login(fields={'Form name':'ВЛЕЗ', 'Username':'Потр. име', 'Password':'Парола', 'Login':'ВХОД'})
        
        if st.session_state["authentication_status"] and st.session_state["username"] == "moderator":
            ime, izhod = st.columns(2)
            with izhod:
                authenticator.logout('ИЗХОД', 'main')
            with ime:
                st.write(f'Здравейте *{st.session_state["name"]}*')
            
        if st.session_state["authentication_status"] and st.session_state["username"] == "m3dkata":
            authenticator.logout('ИЗХОД', 'main')
            st.write(f'Здравейте *{st.session_state["name"]}*')
            # Load books from JSON
            books = await scrape_books()
            book_options = [f"{book['english_name']} ({book['arabic_name']}) - {book['book_name']}" for book in books]
            
            selected_book = st.selectbox("Избери Книга:", book_options)
            
            if selected_book:
                book_name = selected_book.split(' - ')[-1]
                selected_book_data = next(book for book in books if book['book_name'] == book_name)
                
                # Use get() method with default values to avoid KeyError
                default_start = selected_book_data.get('start_page', 1)
                default_end = selected_book_data.get('end_page', 10)
                
                st.write(f"Книга: {selected_book}")
                
                col1, col2 = st.columns(2)
                with col1:
                    start_page = st.number_input("Начална Глава:", min_value=1, value=default_start)
                with col2:
                    end_page = st.number_input("Крайна Глава:", min_value=start_page, value=default_end)
                
            col1, col2 = st.columns(2)  
            with col1:
                if st.button("ДОБАВЯНЕ КЪМ БАЗАТА", key="scrape_button"):
                    if start_page > end_page:
                        st.error("Началната страница не може да бъде по-голяма от крайната страница.")
                    else:
                        with st.spinner(f"Скрейпване, превод и актуализиране на база данни за {book_name} (глави {start_page} до {end_page})... Това може да отнеме известно време."):
                            await populate_database(book_name, start_page, end_page)
                        st.success("Базата данни е актуализирана успешно с преводи!")
                        # Refresh the books data
                        books = get_books()
            with col2:  
                if st.button("Обновяване на данните за книгите"):
                    if os.path.exists('books_data.json'):
                        os.remove('books_data.json')
                    for file in os.listdir():
                        if file.startswith('book_range_') and file.endswith('.json'):
                            os.remove(file)
                    st.success("Данните за книгата са изчистени. Моля, опреснете страницата, за да направите повторно изчерпване.")

            # Add reset password widget
            if st.button('Нулиране на парола'):
                try:
                    if authenticator.reset_password(st.session_state["username"]):
                        st.success('Паролата е променена успешно')
                        # Update configuration file
                        with open('config.yaml', 'w') as file:
                            yaml.dump(config, file, default_flow_style=False)
                except Exception as e:
                    st.error(e)

            # Add update user details widget
            if st.button('Актуализиране на потребителски данни'):
                try:
                    if authenticator.update_user_details(st.session_state["username"]):
                        st.success('Записите са актуализирани успешно')
                        # Update configuration file
                        with open('config.yaml', 'w') as file:
                            yaml.dump(config, file, default_flow_style=False)
                except Exception as e:
                    st.error(e)

        elif st.session_state["authentication_status"] is False:
            st.error('Потребителското име/паролата е неправилно')
        elif st.session_state["authentication_status"] is None:
            st.warning('Моля, въведете вашето потребителско име и парола, за да влезете')

        # Add register new user widget (only if not logged in)
        # if st.session_state["authentication_status"] is None:
        #     if st.button('Register New User'):
        #         try:
        #             email, username, name = authenticator.register_user(pre_authorization=False)
        #             if email:
        #                 st.success('User registered successfully')
        #                 # Update configuration file
        #                 with open('config.yaml', 'w') as file:
        #                     yaml.dump(config, file, default_flow_style=False)
        #         except Exception as e:
        #             st.error(e)

        # Add forgot password widget (only if not logged in)
        if st.session_state["authentication_status"] is None:
            if st.button('ЗАБРАВЕНА ПАРОЛА'):
                try:
                    username, email, new_password = authenticator.forgot_password(fields={'Form name':'ЗАБРАВЕНА ПАРОЛА', 'Username':'Потр. име', 'Submit':'НАПРЕД'})
                    if username:
                        st.success('Новата парола ще бъде изпратена сигурно')
                        # Here you should implement a secure way to send the new password to the user
                        st.write(f"Новата парола за {username}: {new_password}")
                        # Update configuration file
                        with open('config.yaml', 'w') as file:
                            yaml.dump(config, file, default_flow_style=False)
                    elif username == False:
                        st.error('Потребителското име не е намерено')
                except Exception as e:
                    st.error(e)
    audio_files = {
        "1. АЛ-ФАТИХА": ("audio/bg/1. СУРА АЛ-ФАТИХА.mp3", "audio/ar/1. СУРА АЛ-ФАТИХА.mp3"),
        "2. АЛ-БАКАРА": ("audio/bg/2. СУРА АЛ-БАКАРА.mp3", "audio/ar/2. СУРА АЛ-БАКАРА.mp3"),
        "3. АЛ-ИМРАН": ("audio/bg/3. СУРА АЛ-ИМРАН.mp3", "audio/ar/3. СУРА АЛ-ИМРАН.mp3"),
        "4. АН-НИСА": ("audio/bg/4. СУРА АН-НИСА.mp3", "audio/ar/4. СУРА АН-НИСА.mp3"),
        "5. АЛ-МАИДА": ("audio/bg/5. СУРА АЛ-МАИДА.mp3", "audio/ar/5. СУРА АЛ-МАИДА.mp3"),
        "6. АЛ-АНАМ": ("audio/bg/6. СУРА АЛ-АНАМ.mp3", "audio/ar/6. СУРА АЛ-АНАМ.mp3"),
        "7. АЛ-ААРАФ": ("audio/bg/7. СУРА АЛ-ААРАФ.mp3", "audio/ar/7. СУРА АЛ-ААРАФ.mp3"),
        "8. АЛ-АНФАЛ": ("audio/bg/8. СУРА АЛ-АНФАЛ.mp3", "audio/ar/8. СУРА АЛ-АНФАЛ.mp3"),
        "9. АТ-ТАУБА": ("audio/bg/9. СУРА АТ-ТАУБА.mp3", "audio/ar/9. СУРА АТ-ТАУБА.mp3"),
        "10. ЮНУС": ("audio/bg/10. СУРА ЮНУС.mp3", "audio/ar/10. СУРА ЮНУС.mp3"),
        "11. ХУД": ("audio/bg/11. СУРА ХУД.mp3", "audio/ar/11. СУРА ХУД.mp3"),
        "12. ЮСУФ": ("audio/bg/12. СУРА ЮСУФ.mp3", "audio/ar/12. СУРА ЮСУФ.mp3"),
        "13. АР-РААД": ("audio/bg/13. СУРА АР-РААД.mp3", "audio/ar/13. СУРА АР-РААД.mp3"),
        "14. ИБРАХИМ": ("audio/bg/14. СУРА ИБРАХИМ.mp3", "audio/ar/14. СУРА ИБРАХИМ.mp3"),
        "15. АЛ-ХИДЖР": ("audio/bg/15. СУРА АЛ-ХИДЖР.mp3", "audio/ar/15. СУРА АЛ-ХИДЖР.mp3"),
        "16. АН-НАХЛ": ("audio/bg/16. СУРА АН-НАХЛ.mp3", "audio/ar/16. СУРА АН-НАХЛ.mp3"),
        "17. АЛ-ИСРА": ("audio/bg/17. СУРА АЛ-ИСРА.mp3", "audio/ar/17. СУРА АЛ-ИСРА.mp3"),
        "18. АЛ-КАХФ": ("audio/bg/18. СУРА АЛ-КАХФ.mp3", "audio/ar/18. СУРА АЛ-КАХФ.mp3"),
        "19. МАРИАМ": ("audio/bg/19. СУРА МАРИАМ.mp3", "audio/ar/19. СУРА МАРИАМ.mp3"),
        "20. ТА ХА": ("audio/bg/20. CYPA TA XA.mp3", "audio/ar/20. CYPA TA XA.mp3"),
        "21. АЛ-АНБИЯ": ("audio/bg/21. СУРА АЛ-АНБИЯ.mp3", "audio/ar/21. СУРА АЛ-АНБИЯ.mp3"),
        "22. АЛ-ХАДЖ": ("audio/bg/22. СУРА АЛ-ХАДЖ.mp3", "audio/ar/22. СУРА АЛ-ХАДЖ.mp3"),
        "23. АЛ-МУАМИНУН": ("audio/bg/23. СУРА АЛ-МУАМИНУН.mp3", "audio/ar/23. СУРА АЛ-МУАМИНУН.mp3"),
        "24. АН-НУР": ("audio/bg/24. СУРА АН-НУР.mp3", "audio/ar/24. СУРА АН-НУР.mp3"),
        "25. АЛ-ФУРКАН": ("audio/bg/25. СУРА АЛ-ФУРКАН.mp3", "audio/ar/25. СУРА АЛ-ФУРКАН.mp3"),
        "26. АШ-ШУАРА": ("audio/bg/26. СУРА АШ-ШУАРА.mp3", "audio/ar/26. СУРА АШ-ШУАРА.mp3"),
        "27. АН-НАМЛ": ("audio/bg/27. СУРА АН-НАМЛ.mp3", "audio/ar/27. СУРА АН-НАМЛ.mp3"),
        "28. АЛ-КАСАС": ("audio/bg/28. СУРА АЛ-КАCAC.mp3", "audio/ar/28. СУРА АЛ-КАCAC.mp3"),
        "29. АЛ-АНКАБУТ": ("audio/bg/29. СУРА АЛ-АНКАБУТ.mp3", "audio/ar/29. СУРА АЛ-АНКАБУТ.mp3"),
        "30. АР-РУМ": ("audio/bg/30. СУРА АР-РУМ.mp3", "audio/ar/30. СУРА АР-РУМ.mp3"),
        "31. ЛУКМАН": ("audio/bg/31. СУРА ЛУКМАН.mp3", "audio/ar/31. СУРА ЛУКМАН.mp3"),
        "32. АС-САДЖДА": ("audio/bg/32. СУРА АС-САДЖДА.mp3", "audio/ar/32. СУРА АС-САДЖДА.mp3"),
        "33. АЛ-АХЗАБ": ("audio/bg/33.СУРА АЛ-АХЗАБ.mp3", "audio/ar/33.СУРА АЛ-АХЗАБ.mp3"),
        "34. САБА": ("audio/bg/34. СУРА САБА.mp3", "audio/ar/34. СУРА САБА.mp3"),
        "35. ФАТИР": ("audio/bg/35. СУРА ФАТИР.mp3", "audio/ar/35. СУРА ФАТИР.mp3"),
        "36. ЙА СИН": ("audio/bg/36. СУРА ЙА СИН.mp3", "audio/ar/36. СУРА ЙА СИН.mp3"),
        "37. АС-САФФАТ": ("audio/bg/37. СУРА АС-САФФАТ.mp3", "audio/ar/37. СУРА АС-САФФАТ.mp3"),
        "38. САД": ("audio/bg/38. СУРА САД.mp3", "audio/ar/38. СУРА САД.mp3"),
        "39. АЗ-ЗУМАР": ("audio/bg/39. СУРА АЗ-ЗУМАР.mp3", "audio/ar/39. СУРА АЗ-ЗУМАР.mp3"),
        "40. ГАФИР": ("audio/bg/40. СУРА ГАФИР.mp3", "audio/ar/40. СУРА ГАФИР.mp3"),
        "41. ФУССИЛАТ": ("audio/bg/41. СУРА ФУССИЛАТ.mp3", "audio/ar/41. СУРА ФУССИЛАТ.mp3"),
        "42. АШ-ШУРА": ("audio/bg/42. СУРА АШ-ШУРА.mp3", "audio/ar/42. СУРА АШ-ШУРА.mp3"),
        "43. АЗ-ЗУХРУФ": ("audio/bg/43. СУРА АЗ-ЗУХРУФ.mp3", "audio/ar/43. СУРА АЗ-ЗУХРУФ.mp3"),
        "44. АД-ДУХАН": ("audio/bg/44. СУРА АД-ДУХАН.mp3", "audio/ar/44. СУРА АД-ДУХАН.mp3"),
        "45. АЛ-ДЖАСИЯ": ("audio/bg/45. СУРА АЛ-ДЖАСИЯ.mp3", "audio/ar/45. СУРА АЛ-ДЖАСИЯ.mp3"),
        "46. АЛ-АХКАФ": ("audio/bg/46. СУРА АЛ-АХКАФ.mp3", "audio/ar/46. СУРА АЛ-АХКАФ.mp3"),
        "47. МУХАММЕД": ("audio/bg/47. СУРА МУХАММЕД.mp3", "audio/ar/47. СУРА МУХАММЕД.mp3"),
        "48. АЛ-ФАТХ": ("audio/bg/48. СУРА АЛ-ФАТХ.mp3", "audio/ar/48. СУРА АЛ-ФАТХ.mp3"),
        "49. АЛ-ХУДЖУРАТ": ("audio/bg/49. СУРА АЛ-ХУДЖУРАТ.mp3", "audio/ar/49. СУРА АЛ-ХУДЖУРАТ.mp3"),
        "50. КАФ": ("audio/bg/50. СУРА КАФ.mp3", "audio/ar/50. СУРА КАФ.mp3"),
        "51. АЗ-ЗАРИЙАТ": ("audio/bg/51. СУРА АЗ-ЗАРИЙАТ.mp3", "audio/ar/51. СУРА АЗ-ЗАРИЙАТ.mp3"),
        "52. АТ-ТУР": ("audio/bg/52. СУРА АТ-ТУР.mp3", "audio/ar/52. СУРА АТ-ТУР.mp3"),
        "53. АН-НАДЖМ": ("audio/bg/53. СУРА АН-НАДЖМ.mp3", "audio/ar/53. СУРА АН-НАДЖМ.mp3"),
        "54. АЛ-КАМАР": ("audio/bg/54. СУРА АЛ-КАМАР.mp3", "audio/ar/54. СУРА АЛ-КАМАР.mp3"),
        "55. АР-РАХМАН": ("audio/bg/55. СУРА АР-РАХМАН.mp3", "audio/ar/55. СУРА АР-РАХМАН.mp3"),
        "56. АЛ-УАКИА": ("audio/bg/56. СУРА АЛ-УАКИА.mp3", "audio/ar/56. СУРА АЛ-УАКИА.mp3"),
        "57. АЛ-ХАДИД": ("audio/bg/57. СУРА АЛ-ХАДИД.mp3", "audio/ar/57. СУРА АЛ-ХАДИД.mp3"),
        "58. АЛ-МУДЖАДАЛА": ("audio/bg/58. СУРА АЛ-МУДЖАДАЛА.mp3", "audio/ar/58. СУРА АЛ-МУДЖАДАЛА.mp3"),
        "59. АЛ-ХАШР": ("audio/bg/59. СУРА АЛ-ХАШР.mp3", "audio/ar/59. СУРА АЛ-ХАШР.mp3"),
        "60. АЛ-МУМТАХАНА": ("audio/bg/60. СУРА АЛ-МУМТАХАНА.mp3", "audio/ar/60. СУРА АЛ-МУМТАХАНА.mp3"),
        "61. АС-САФФ": ("audio/bg/61. СУРА АС-САФФ.mp3", "audio/ar/61. СУРА АС-САФФ.mp3"),
        "62. АЛ-ДЖУМУА": ("audio/bg/62. СУРА АЛ-ДЖУМУA.mp3", "audio/ar/62. СУРА АЛ-ДЖУМУA.mp3"),
        "63. АЛ-МУНАФИКУН": ("audio/bg/63. СУРА АЛ-МУНАФИКУН.mp3", "audio/ar/63. СУРА АЛ-МУНАФИКУН.mp3"),
        "64. АТ-ТАГАБУН": ("audio/bg/64. СУРА АТ-ТАГАБУН.mp3", "audio/ar/64. СУРА АТ-ТАГАБУН.mp3"),
        "65. АТ-ТАЛАК": ("audio/bg/65. СУРА АТ-ТАЛАК.mp3", "audio/ar/65. СУРА АТ-ТАЛАК.mp3"),
        "66. АТ-ТАХРИМ": ("audio/bg/66. СУРА АТ-ТАХРИМ.mp3", "audio/ar/66. СУРА АТ-ТАХРИМ.mp3"),
        "67. АЛ-МУЛК": ("audio/bg/67. СУРА АЛ-МУЛК.mp3", "audio/ar/67. СУРА АЛ-МУЛК.mp3"),
        "68. АЛ-КАЛАМ": ("audio/bg/68. СУРА АЛ-КАЛАМ.mp3", "audio/ar/68. СУРА АЛ-КАЛАМ.mp3"),
        "69. АЛ-ХАККА": ("audio/bg/69. СУРА АЛ-ХАККА.mp3", "audio/ar/69. СУРА АЛ-ХАККА.mp3"),
        "70. АЛ-МААРИДЖ": ("audio/bg/70. СУРА АЛ-МААРИДЖ.mp3", "audio/ar/70. СУРА АЛ-МААРИДЖ.mp3"),
        "71. НУХ": ("audio/bg/71. СУРА НУХ.mp3", "audio/ar/71. СУРА НУХ.mp3"),
        "72. АЛ-ДЖИНН": ("audio/bg/72. СУРА АЛ-ДЖИНН.mp3", "audio/ar/72. СУРА АЛ-ДЖИНН.mp3"),
        "73. АЛ-МУЗЗАММИЛ": ("audio/bg/73. СУРА АЛ-МУЗЗАММИЛ.mp3", "audio/ar/73. СУРА АЛ-МУЗЗАММИЛ.mp3"),
        "74. АЛ-МУДДАССИР": ("audio/bg/74. АЛ-МУДДАССИР.mp3", "audio/ar/74. АЛ-МУДДАССИР.mp3"),
        "75. АЛ-КИЙАМА": ("audio/bg/75. СУРА АЛ-КИЙАМА.mp3", "audio/ar/75. СУРА АЛ-КИЙАМА.mp3"),
        "76. АЛ-ИНСАН": ("audio/bg/76. СУРА АЛ-ИНСАН.mp3", "audio/ar/76. СУРА АЛ-ИНСАН.mp3"),
        "77. АЛ-МУРСАЛАТ": ("audio/bg/77. СУРА АЛ-МУРСАЛАТ.mp3", "audio/ar/77. СУРА АЛ-МУРСАЛАТ.mp3"),
        "78. АН-НАБА": ("audio/bg/78. СУРА АН-НАБА.mp3", "audio/ar/78. СУРА АН-НАБА.mp3"),
        "79. АН-НАЗИАТ": ("audio/bg/79. СУРА АН-НАЗИАТ.mp3", "audio/ar/79. СУРА АН-НАЗИАТ.mp3"),
        "80. АБАСА": ("audio/bg/80. СУРА АБАСА.mp3", "audio/ar/80. СУРА АБАСА.mp3"),
        "81. АТ-ТАКУИР": ("audio/bg/81. СУРА АТ-ТАКУИР.mp3", "audio/ar/81. СУРА АТ-ТАКУИР.mp3"),
        "82. АЛ-ИНФИТАР": ("audio/bg/82. СУРА АЛ-ИНФИТАР.mp3", "audio/ar/82. СУРА АЛ-ИНФИТАР.mp3"),
        "83. АЛ-МУТАФФИФИН": ("audio/bg/83. СУРА АЛ-МУТАФФИФИН.mp3", "audio/ar/83. СУРА АЛ-МУТАФФИФИН.mp3"),
        "84. АЛ-ИНШИКАК": ("audio/bg/84. СУРА АЛ-ИНШИКАК.mp3", "audio/ar/84. СУРА АЛ-ИНШИКАК.mp3"),
        "85. АЛ-БУРУДЖ": ("audio/bg/85. СУРА АЛ-БУРУДЖ.mp3", "audio/ar/85. СУРА АЛ-БУРУДЖ.mp3"),
        "86. АТ-ТАРИК": ("audio/bg/86. СУРА АТ-ТАРИК.mp3", "audio/ar/86. СУРА АТ-ТАРИК.mp3"),
        "87. АЛ-АЛЯ": ("audio/bg/87. СУРА АЛ-АЛЯ.mp3", "audio/ar/87. СУРА АЛ-АЛЯ.mp3"),
        "88. АЛ-ГАШИЯ": ("audio/bg/88. СУРА АЛ-ГАШИЯ.mp3", "audio/ar/88. СУРА АЛ-ГАШИЯ.mp3"),
        "89. АЛ-ФАДЖР": ("audio/bg/89. СУРА АЛ-ФАДЖР.mp3", "audio/ar/89. СУРА АЛ-ФАДЖР.mp3"),
        "90. АЛ-БАЛАД": ("audio/bg/90. СУРА АЛ-БАЛАД.mp3", "audio/ar/90. СУРА АЛ-БАЛАД.mp3"),
        "91. АШ-ШАМС": ("audio/bg/91. СУРА АШ-ШАМС.mp3", "audio/ar/91. СУРА АШ-ШАМС.mp3"),
        "92. АЛ-ЛАЙЛ": ("audio/bg/92. СУРА АЛ-ЛАЙЛ.mp3", "audio/ar/92. СУРА АЛ-ЛАЙЛ.mp3"),
        "93. АД-ДУХА": ("audio/bg/93. СУРА АД-ДУХА.mp3", "audio/ar/93. СУРА АД-ДУХА.mp3"),
        "94. АЛ-ИНШИРАХ": ("audio/bg/94. СУРА АЛ-ИНШИРАХ.mp3", "audio/ar/94. СУРА АЛ-ИНШИРАХ.mp3"),
        "95. АТ-ТИН": ("audio/bg/95. СУРА АТ-ТИН.mp3", "audio/ar/95. СУРА АТ-ТИН.mp3"),
        "96. АЛ-АЛАК": ("audio/bg/96. СУРА АЛ-АЛАК.mp3", "audio/ar/96. СУРА АЛ-АЛАК.mp3"),
        "97. АЛ-КАДР": ("audio/bg/97. СУРА АЛ-КАДР.mp3", "audio/ar/97. СУРА АЛ-КАДР.mp3"),
        "98. АЛ-БАЙИНА": ("audio/bg/98. СУРА АЛ-БАЙИНА.mp3", "audio/ar/98. СУРА АЛ-БАЙИНА.mp3"),
        "99. АЗ-ЗАЛЗАЛА": ("audio/bg/99. СУРА АЗ-ЗАЛЗАЛА.mp3", "audio/ar/99. СУРА АЗ-ЗАЛЗАЛА.mp3"),
        "100. АЛ-АДИАТ": ("audio/bg/100. СУРА АЛ-АДИАТ.mp3", "audio/ar/100. СУРА АЛ-АДИАТ.mp3"),
        "101. АЛ-КАРИА": ("audio/bg/101. СУРА АЛ-КАРИА.mp3", "audio/ar/101. СУРА АЛ-КАРИА.mp3"),
        "102. АТ-ТАКАСУР": ("audio/bg/102. СУРА АТ-ТАКАСУР.mp3", "audio/ar/102. СУРА АТ-ТАКАСУР.mp3"),
        "103. АЛ-АСР": ("audio/bg/103. СУРА АЛ-АСP.mp3", "audio/ar/103. СУРА АЛ-АСP.mp3"),
        "104. АЛ-ХУМАЗА": ("audio/bg/104. СУРА АЛ-ХУМАЗА.mp3", "audio/ar/104. СУРА АЛ-ХУМАЗА.mp3"),
        "105. АЛ-ФИЛ": ("audio/bg/105. СУРА АЛ-ФИЛ.mp3", "audio/ar/105. СУРА АЛ-ФИЛ.mp3"),
        "106. КУРАЙШ": ("audio/bg/106. СУРА КУРАЙШ.mp3", "audio/ar/106. СУРА КУРАЙШ.mp3"),
        "107. АЛ-МАУН": ("audio/bg/107. СУРА АЛ-МАУН.mp3", "audio/ar/107. СУРА АЛ-МАУН.mp3"),
        "108. АЛ-КАУСАР": ("audio/bg/108. СУРА АЛ-КАУСАР.mp3", "audio/ar/108. СУРА АЛ-КАУСАР.mp3"),
        "109. АЛ-КАФИРУН": ("audio/bg/109. СУРА АЛ-КАФИРУН.mp3", "audio/ar/109. СУРА АЛ-КАФИРУН.mp3"),
        "110. АН-НАСР": ("audio/bg/110. CYPA AH-HACP.mp3", "audio/ar/110. CYPA AH-HACP.mp3"),
        "111. АЛ-МАСАД": ("audio/bg/111. СУРА АЛ-МАСАД.mp3", "audio/ar/111. СУРА АЛ-МАСАД.mp3"),
        "112. АЛ-ИХЛАС": ("audio/bg/112. СУРА АЛ-ИХЛАС.mp3", "audio/ar/112. СУРА АЛ-ИХЛАС.mp3"),
        "113. АЛ-ФАЛАК": ("audio/bg/113. СУРА АЛ-ФАЛАК.mp3", "audio/ar/113. СУРА АЛ-ФАЛАК.mp3"),
        "114. АН-НАС": ("audio/bg/114. CYPA AH-HAC.mp3", "audio/ar/114. CYPA AH-HAC.mp3")
    }
    with st.sidebar.expander("Слушай Коран-и керим"):
        selected_sura = st.selectbox(
            "Изберете сура",
            ["Избери Сура"] + list(audio_files.keys()),
            index=0
        )

        if selected_sura != "Избери Сура":
            audio_file_bg, audio_file_ar = audio_files[selected_sura]
            st.subheader(selected_sura)

            # Function to check if file exists and play audio
            def play_audio(file_path, language):
                if os.path.exists(file_path):
                    st.caption(language)
                    st.audio(file_path, format="audio/mpeg")
                else:
                    st.warning(f"{language} аудио файл не е намерен.")

            # Play Bulgarian audio
            play_audio(audio_file_bg, "Български")

            # Play Arabic audio
            play_audio(audio_file_ar, "Арабски")

            # Display a message if both files are missing
            if not os.path.exists(audio_file_bg) and not os.path.exists(audio_file_ar):
                st.error("Аудио файловете за тази сура не са налични. Моля, проверете директорията с аудио файлове.")
        
    # Search functionality
    search_term = st.sidebar.text_input(
        "Търсене", 
        help="Въведете текст на кирилица за търсене",
        key="search_term"
    )

    # Use a context manager for the database connection
    with sqlite3.connect('hadiths.db') as conn:
        c = conn.cursor()
    
        books = get_books()
        
        if books:
            for i, book in enumerate(books):
                if search_term:
                    matching_pages = get_matching_pages(book[0], search_term)
                    
                    if matching_pages:
                        st.sidebar.checkbox(f":{book[2].upper()} ({book[3]})", key=f"book_{book[0]}", value=True)
                        for page in matching_pages:
                            st.sidebar.checkbox(f":blue[*{page[1]}: {page[2].upper()}*]", key=f"page_{page[0]}", value=True)
                            chapters = get_matching_chapters(page[0], search_term)
                            for chapter in chapters:
                                chapter_text = f"{chapter[1]}: {chapter[2].strip('Глава:')}"
                                if st.sidebar.button(chapter_text, key=f"chapter_{chapter[0]}", help="Натиснете за преглед", on_click=change):
                                    st.session_state.chapter_index = chapters.index(chapter)
                                    st.session_state.chapters = chapters
                                    st.session_state.chapter_selected = True
                                    st.session_state.content_visible = False
                                    st.experimental_rerun()
                    
                    if matching_pages and i < len(books) - 1:
                        st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
                else:
                    if st.sidebar.checkbox(f"{book[2].upper()} ({book[3]})", key=f"book_{book[0]}"):
                        pages = get_pages(book[0])
                        for page in pages:
                            if st.sidebar.checkbox(f":blue[*{page[1]}: {page[2].upper()}*]", key=f"page_{page[0]}"):
                                chapters = get_chapters(page[0])
                                for chapter in chapters:
                                    if st.sidebar.button(f"{chapter[1]}: {chapter[2][:30].strip('Глава:')}...", key=f"chapter_{chapter[0]}", help="Натиснете за преглед", on_click=change):
                                        st.session_state.chapter_index = chapters.index(chapter)
                                        st.session_state.chapters = chapters
                                        st.session_state.chapter_selected = True
                                        st.session_state.content_visible = False
                                        st.experimental_rerun()
                    
                    if i < len(books) - 1:
                        st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        else:
            st.sidebar.write("Няма данни в базата.")

        # Initialize session state for chapters if not already initialized
        if "chapters" not in st.session_state:
            st.session_state.chapters = []

        # Initialize session state for chapter_selected if not already initialized
        if "chapter_selected" not in st.session_state:
            st.session_state.chapter_selected = False

        # Add custom CSS to position buttons fixed at bottom left and bottom right
        # prev, next = st.columns([1, 1], gap="small")
        

        # Add "PREV" and "NEXT" buttons only if a chapter has been selected
        if st.session_state.chapter_selected:
            # st.markdown('<div class="fixed-buttons">', unsafe_allow_html=True)
            # with bottom():
                # col1, col2 = st.columns([1, 1])
                # st.markdown("""
                # <style>
                #     div[data-testid="stHorizontalBlock"] {
                #         width: fit-content !important;
                #         flex: unset;
                #     }
                #     div[data-testid="stHorizontalBlock"] * {
                #         width: fit-content !important;
                #     }
                # </style>
                # """, unsafe_allow_html=True)
                # with prev:
                #     if st.button("< ПРЕДИШЕН", key="prev_btn"):
                #         if st.session_state.chapter_index > 0:
                #             st.session_state.chapter_index -= 1
                # with next:
                #     if st.button("СЛЕДВАЩ >", key="next_btn"):
                #         if st.session_state.chapter_index < len(st.session_state.chapters) - 1:
                #             st.session_state.chapter_index += 1
                # st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("""
                <style>
                    div[data-testid="column"] {
                        width: fit-content !important;
                        flex: unset;
                    }
                    div[data-testid="column"] * {
                        width: fit-content !important;
                    }
                    /* Styles for mobile devices */
                    @media (max-width: 640px) {
                        div[data-testid="column"] {
                            width: 100% !important;
                        }
                        div[data-testid="column"] * {
                            width: 100% !important;
                        .stButton > button {
                            width: 100%;
                            padding: 0px 0;
                            margin: 0px 0;
                        }
                    }
                </style>
                """, unsafe_allow_html=True)

                col = st.columns([2, 2],gap="small") # , vertical_alignment="bottom"

                with col[0]:
                    if st.button("&lt; ПРЕДИШЕН", key="prev_btn"):
                        if st.session_state.chapter_index > 0:
                            st.session_state.chapter_index -= 1
                with col[1]:
                    if st.button("СЛЕДВАЩ &gt;", key="next_btn"):
                        if st.session_state.chapter_index < len(st.session_state.chapters) - 1:
                            st.session_state.chapter_index += 1        



        # Display the current chapter based on the chapter index
        if "chapter_index" in st.session_state and "chapters" in st.session_state:
            current_chapter_index = st.session_state.chapter_index
            chapters = st.session_state.chapters
            if 0 <= current_chapter_index < len(chapters):
                display_chapter(c, chapters[current_chapter_index][0]) # Access the chapter ID correctly

        # conn.close()

if __name__ == "__main__":
    asyncio.run(main_async())