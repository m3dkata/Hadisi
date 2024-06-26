import streamlit as st
import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from googletrans import Translator
from streamlit_tree_select import tree_select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(layout="wide", page_title="ХАДИСИ")

st.markdown("""
<style>
    .sidebar-divider {
        margin-top: 5px;
        margin-bottom: 5px;
        border-top: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize the translator
translator = Translator()

def create_database():
    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS books
                 (id INTEGER PRIMARY KEY, book_name TEXT, english TEXT, arabic TEXT, colindextitle TEXT, bulgarian_colindextitle TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS pages
                 (id INTEGER PRIMARY KEY, book_id INTEGER, 
                  book_page_number TEXT, book_page_english_name TEXT, book_page_arabic_name TEXT,
                  book_page_bulgarian_name TEXT,
                  FOREIGN KEY (book_id) REFERENCES books(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chapters
                 (id INTEGER PRIMARY KEY, page_id INTEGER, 
                  echapno TEXT, englishchapter TEXT, arabicchapter TEXT, bulgarianchapter TEXT,
                  arabic_achapintro TEXT, hadith_narrated TEXT, 
                  english_hadith_full TEXT, arabic_hadith_full TEXT, bulgarian_hadith_full TEXT,
                  FOREIGN KEY (page_id) REFERENCES pages(id))''')
    
    conn.commit()
    conn.close()

def scrape_main_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    collection_info = soup.find('div', class_='collection_info')
    colindextitle = collection_info.find('div', class_='colindextitle incomplete')
    
    arabic = colindextitle.find('div', class_='arabic').text.strip()
    english = colindextitle.find('div', class_='english').text.strip()
    colindextitle_text = collection_info.find('div', class_='colindextitle', recursive=False).text.strip()
    
    # Translate colindextitle to Bulgarian
    bulgarian_colindextitle = translator.translate(colindextitle_text, src='en', dest='bg').text
    
    return {
        'english': english,
        'arabic': arabic,
        'colindextitle': colindextitle_text,
        'bulgarian_colindextitle': bulgarian_colindextitle
    }

def scrape_book_page(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')
        
        book_info = soup.find('div', class_='book_info')
        if not book_info:
            logger.error(f"Book info not found on page: {url}")
            return None

        book_page_arabic_name = book_info.find('div', class_='book_page_arabic_name')
        book_page_number = book_info.find('div', class_='book_page_number')
        book_page_english_name = book_info.find('div', class_='book_page_english_name')

        if not all([book_page_arabic_name, book_page_number, book_page_english_name]):
            logger.error(f"Missing required book info elements on page: {url}")
            return None

        book_page_bulgarian_name = translator.translate(book_page_english_name.text.strip(), src='en', dest='bg').text
        
        chapters = []
        for chapter in soup.find_all('div', class_='chapter'):
            try:
                echapno = chapter.find('div', class_='echapno').text.strip('()')
                englishchapter = chapter.find('div', class_='englishchapter').text.strip()
                arabicchapter = chapter.find('div', class_='arabicchapter').text.strip()
                
                bulgarianchapter = translator.translate(englishchapter, src='en', dest='bg').text
                
                arabic_achapintro = chapter.find_next_sibling('div', class_='arabic achapintro aconly')
                arabic_achapintro = arabic_achapintro.text.strip() if arabic_achapintro else ""
                
                hadith = chapter.find_next_sibling('div', class_='actualHadithContainer')
                if not hadith:
                    logger.warning(f"Hadith container not found for chapter on page: {url}")
                    continue

                hadith_narrated = hadith.find('div', class_='hadith_narrated')
                english_hadith_full = hadith.find('div', class_='text_details')
                arabic_hadith_full = hadith.find('div', class_='arabic_hadith_full')

                if not all([hadith_narrated, english_hadith_full, arabic_hadith_full]):
                    logger.warning(f"Missing hadith elements for chapter on page: {url}")
                    continue

                bulgarian_hadith_full = translator.translate(english_hadith_full.text.strip(), src='en', dest='bg').text
                
                chapters.append({
                    'echapno': echapno,
                    'englishchapter': englishchapter,
                    'arabicchapter': arabicchapter,
                    'bulgarianchapter': bulgarianchapter,
                    'arabic_achapintro': arabic_achapintro,
                    'hadith_narrated': hadith_narrated.text.strip(),
                    'english_hadith_full': english_hadith_full.text.strip(),
                    'arabic_hadith_full': arabic_hadith_full.text.strip(),
                    'bulgarian_hadith_full': bulgarian_hadith_full
                })
            except AttributeError as e:
                logger.error(f"Error processing chapter on page {url}: {str(e)}")
                continue

        return {
            'book_page_number': book_page_number.text.strip(),
            'book_page_english_name': book_page_english_name.text.strip(),
            'book_page_arabic_name': book_page_arabic_name.text.strip(),
            'book_page_bulgarian_name': book_page_bulgarian_name,
            'chapters': chapters
        }
    except requests.RequestException as e:
        logger.error(f"Error fetching page {url}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error processing page {url}: {str(e)}")
        return None

def populate_database(book_name, start_page, end_page):
    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()
    
    # Check if the book already exists
    c.execute("SELECT id FROM books WHERE book_name = ?", (book_name,))
    existing_book = c.fetchone()
    
    if existing_book:
        book_id = existing_book[0]
        st.info(f"Книга '{book_name}' вече съществува в базата данни. Използване на съществуващ идентификатор на книга: {book_id}")
    else:
        # Scrape main page
        main_url = f"https://sunnah.com/{book_name}"
        main_data = scrape_main_page(main_url)
        
        if not main_data:
            st.error(f"Failed to scrape main page for book {book_name}")
            conn.close()
            return

        c.execute("INSERT INTO books (book_name, english, arabic, colindextitle, bulgarian_colindextitle) VALUES (?, ?, ?, ?, ?)",
                  (book_name, main_data['english'], main_data['arabic'], main_data['colindextitle'], main_data['bulgarian_colindextitle']))
        book_id = c.lastrowid
        st.success(f"Added new book '{book_name}' to the database with ID: {book_id}")
    
    # Scrape book pages
    for page_number in range(start_page, end_page + 1):
        # Check if the page already exists
        c.execute("SELECT id FROM pages WHERE book_id = ? AND book_page_number = ?", (book_id, str(page_number)))
        existing_page = c.fetchone()
        
        if existing_page:
            st.info(f"Page {page_number} for book '{book_name}' already exists in the database. Skipping.")
            continue
        
        url = f"https://sunnah.com/{book_name}/{page_number}"
        page_data = scrape_book_page(url)
        
        if page_data:
            c.execute("INSERT INTO pages (book_id, book_page_number, book_page_english_name, book_page_arabic_name, book_page_bulgarian_name) VALUES (?, ?, ?, ?, ?)",
                      (book_id, page_data['book_page_number'], page_data['book_page_english_name'], page_data['book_page_arabic_name'], page_data['book_page_bulgarian_name']))
            page_id = c.lastrowid
            
            for chapter in page_data['chapters']:
                c.execute("""INSERT INTO chapters 
                             (page_id, echapno, englishchapter, arabicchapter, bulgarianchapter, arabic_achapintro, 
                              hadith_narrated, english_hadith_full, arabic_hadith_full, bulgarian_hadith_full) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (page_id, chapter['echapno'], chapter['englishchapter'], chapter['arabicchapter'],
                           chapter['bulgarianchapter'], chapter['arabic_achapintro'], chapter['hadith_narrated'], 
                           chapter['english_hadith_full'], chapter['arabic_hadith_full'], chapter['bulgarian_hadith_full']))
            
            conn.commit()
            st.success(f"Scraped and translated Book {book_name}, Page {page_number}")
        else:
            st.warning(f"Failed to scrape Book {book_name}, Page {page_number}")
        
        time.sleep(1)  # To avoid overwhelming the server
    
    conn.close()

def main():
    # st.title("Hadith Scraper and Translator")

    # book_name = st.text_input("Enter the book name (e.g., 'muslim', 'bukhari'):", key="book_name_input")
    # start_page = st.number_input("Enter the starting page number:", min_value=1, value=1, key="start_page_input")
    # end_page = st.number_input("Enter the ending page number:", min_value=1, value=10, key="end_page_input")

    # if st.button("Scrape, Translate, and Update Database", key="scrape_button"):
    #     with st.spinner("Creating database schema..."):
    #         create_database()
    #     with st.spinner(f"Scraping, translating, and updating database for {book_name} (pages {start_page} to {end_page})... This may take a while."):
    #         populate_database(book_name, start_page, end_page)
    #     st.success("Database updated successfully with translations!")

    conn = sqlite3.connect('hadiths.db')
    c = conn.cursor()

    # Sidebar with tree-like structure
    HORIZONTAL_RED = "main_logo.png"
    ICON_RED = "logo.png"
    st.logo(HORIZONTAL_RED, icon_image=ICON_RED)
    st.sidebar.header(f":red[Хадисите на пророка Мохаммед(С.А.С)]")
    st.sidebar.header(f":red[(صلى الله عليه و سلم)]")
    c.execute("SELECT id, book_name, english, arabic FROM books")
    books = c.fetchall()

    if books:
        for i, book in enumerate(books):
            if st.sidebar.checkbox(f":red[{book[2].upper()} ({book[3]})]", key=f"book_{book[0]}"):
                c.execute("SELECT id, book_page_number, book_page_bulgarian_name FROM pages WHERE book_id = ? ORDER BY id", (book[0],))
                pages = c.fetchall()
                for page in pages:
                    if st.sidebar.checkbox(f":red-background[*{page[1]}: {page[2].upper()}*]", key=f"page_{page[0]}"):
                        c.execute("SELECT id, echapno, bulgarianchapter FROM chapters WHERE page_id = ? ORDER BY echapno", (page[0],))
                        chapters = c.fetchall()
                        for chapter in chapters:
                            if st.sidebar.button(f"{chapter[1]}: {chapter[2].strip('Глава:')}...", key=f"chapter_{chapter[0]}", help="Натиснете за преглед"):
                                display_chapter(c, chapter[0])
            
            # Add a divider after each book, except for the last one
            if i < len(books) - 1:
                st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)     

    else:
        st.sidebar.write("No books found in the database. Please scrape some data first.")

    conn.close()

def display_chapter(cursor, chapter_id):
    cursor.execute("""
        SELECT c.echapno, c.englishchapter, c.arabicchapter, c.bulgarianchapter,
               c.arabic_achapintro, c.hadith_narrated, c.english_hadith_full, c.arabic_hadith_full, c.bulgarian_hadith_full,
               p.book_page_number, p.book_page_english_name, p.book_page_arabic_name, p.book_page_bulgarian_name
        FROM chapters c
        JOIN pages p ON c.page_id = p.id
        WHERE c.id = ?
    """, (chapter_id,))
    chapter_data = cursor.fetchone()

    if chapter_data:
        # st.header("Book Information")
        col1, col2 = st.columns(2)
        with col1:
            # st.subheader("Arabic")
            st.subheader(f"{chapter_data[9]}. {chapter_data[12].upper()}")  # book_page_arabic_name
        with col2:
            # st.subheader("English")
            st.subheader(f"{chapter_data[9]}. {chapter_data[11]}")  # book_page_number and book_page_english_name
        # with col3:
        #     st.subheader("Bulgarian")
        #     st.write(chapter_data[13])
        st.divider()
        # st.subheader(f"Част: {chapter_data[0]}")
        col1, col2, col3 = st.columns(3)
        with col1:
            # st.subheader("English")
            st.subheader(chapter_data[3].strip("Глава:"))
        with col2:
            # st.subheader("Arabic")
            st.subheader(chapter_data[2])
        with col3:
            # st.subheader("Bulgarian")
            st.subheader(chapter_data[1].strip("Chapter:"))
    
        # col1, col2 = st.columns(2)
        # with col1:
        #     # st.subheader("Arabic Introduction")
        #     st.subheader(chapter_data[5])
        # with col2:
        #     # st.subheader("Hadith Narrated")
        #     st.subheader(chapter_data[4])

        # st.header("Hadith Full Text")
        col1, col2, col3 = st.columns(3)
        with col1:
            # st.subheader("English")
            bulgarian_text = chapter_data[8]
            bulgarian_text = bulgarian_text.replace("(ﷺ)", "(С.А.С)")
            bulgarian_text = bulgarian_text.replace("`", "")
            st.write(bulgarian_text)
        with col2:
            # st.subheader("Arabic")
            st.write(chapter_data[7])
        with col3:
            # st.subheader("Bulgarian")
            english_text = chapter_data[6]
            english_text = english_text.replace("(ﷺ)", "(S.A.W)")
            english_text = english_text.replace("`", "")
            st.write(english_text)

if __name__ == "__main__":
    main()