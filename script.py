import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px

# -------------------------------
# Inicjalizacja bazy danych
# -------------------------------
def init_db():
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS shared_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            shared_with_user_id INTEGER NOT NULL,
            FOREIGN KEY(note_id) REFERENCES notes(id),
            FOREIGN KEY(shared_with_user_id) REFERENCES users(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_data BLOB NOT NULL,
            upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS shared_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            shared_with_user_id INTEGER NOT NULL,
            share_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(file_id) REFERENCES files(id),
            FOREIGN KEY(shared_with_user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# -------------------------------
# Funkcje użytkownika
# -------------------------------
def register_user(username, password):
    try:
        conn = sqlite3.connect("notes.db")
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username, password):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    return user[0] if user else None

def delete_account(user_id):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    try:
        # Usuń wszystkie pliki użytkownika
        c.execute("DELETE FROM files WHERE user_id = ?", (user_id,))
        
        # Usuń wszystkie notatki użytkownika
        c.execute("DELETE FROM notes WHERE user_id = ?", (user_id,))
        
        # Usuń udostępnienia notatek dla tego użytkownika
        c.execute("DELETE FROM shared_notes WHERE shared_with_user_id = ?", (user_id,))
        
        # Usuń udostępnienia plików dla tego użytkownika
        c.execute("DELETE FROM shared_files WHERE shared_with_user_id = ?", (user_id,))
        
        # Na końcu usuń samo konto
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        return True, "Konto zostało usunięte"
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Błąd podczas usuwania konta: {str(e)}"

def get_all_users():
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("SELECT username FROM users ORDER BY username")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def check_user_exists(username):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return user is not None

# -------------------------------
# Notatki
# -------------------------------
def add_note(user_id, content):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("INSERT INTO notes (user_id, content) VALUES (?, ?)", (user_id, content))
    conn.commit()
    conn.close()

def edit_note(note_id, user_id, new_content):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("UPDATE notes SET content = ? WHERE id = ? AND user_id = ?", (new_content, note_id, user_id))
    success = c.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_notes(user_id):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("SELECT id, content, timestamp FROM notes WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    notes = c.fetchall()
    conn.close()
    return notes

def delete_note(note_id, user_id):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    # Usuń też udostępnienia tej notatki
    c.execute("DELETE FROM shared_notes WHERE note_id = ?", (note_id,))
    conn.commit()
    conn.close()

# -------------------------------
# Udostępnianie notatek
# -------------------------------
def share_note_with_user(note_id, target_username):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    # Pobierz id użytkownika docelowego
    c.execute("SELECT id FROM users WHERE username = ?", (target_username,))
    target_user = c.fetchone()
    if not target_user:
        conn.close()
        return False, "Nie znaleziono użytkownika"
    target_user_id = target_user[0]

    # Sprawdź czy notatka należy do aktualnego użytkownika
    c.execute("SELECT user_id FROM notes WHERE id = ?", (note_id,))
    owner = c.fetchone()
    if not owner or owner[0] != st.session_state.user_id:
        conn.close()
        return False, "Brak dostępu do notatki"

    # Sprawdź, czy już nie udostępniono
    c.execute("SELECT id FROM shared_notes WHERE note_id = ? AND shared_with_user_id = ?", (note_id, target_user_id))
    if c.fetchone():
        conn.close()
        return False, "Notatka jest już udostępniona temu użytkownikowi"

    c.execute("INSERT INTO shared_notes (note_id, shared_with_user_id) VALUES (?, ?)", (note_id, target_user_id))
    conn.commit()
    conn.close()
    return True, "Notatka udostępniona"

def get_shared_notes(user_id):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute('''
        SELECT n.id, n.content, n.timestamp, u.username
        FROM notes n
        JOIN shared_notes s ON n.id = s.note_id
        JOIN users u ON n.user_id = u.id
        WHERE s.shared_with_user_id = ?
        ORDER BY n.timestamp DESC
    ''', (user_id,))
    shared = c.fetchall()
    conn.close()
    return shared

# -------------------------------
# Zarządzanie plikami
# -------------------------------
def save_file(user_id, filename, file_data):
    try:
        # Sprawdź czy plik jest poprawnym CSV
        df = pd.read_csv(pd.io.common.BytesIO(file_data))
        # Konwertuj wszystkie kolumny na odpowiednie typy
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    df[col] = pd.to_numeric(df[col], errors='ignore')
                except:
                    pass
        
        # Sprawdź czy plik o takiej nazwie już istnieje
        conn = sqlite3.connect("notes.db")
        c = conn.cursor()
        c.execute("SELECT id FROM files WHERE user_id = ? AND filename = ?", (user_id, filename))
        if c.fetchone():
            conn.close()
            return False, "Plik o takiej nazwie już istnieje"
        
        # Zapisz plik
        c.execute("INSERT INTO files (user_id, filename, file_data) VALUES (?, ?, ?)",
                  (user_id, filename, file_data))
        conn.commit()
        conn.close()
        return True, "Plik został zapisany"
    except Exception as e:
        return False, f"Błąd podczas zapisywania pliku: {str(e)}"

def rename_file(file_id, user_id, new_filename):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    
    # Sprawdź czy użytkownik jest właścicielem pliku
    c.execute("SELECT user_id FROM files WHERE id = ?", (file_id,))
    result = c.fetchone()
    
    if not result or result[0] != user_id:
        conn.close()
        return False, "Tylko właściciel może zmienić nazwę pliku"
    
    # Sprawdź czy nazwa kończy się na .csv
    if not new_filename.lower().endswith('.csv'):
        conn.close()
        return False, "Nazwa pliku musi kończyć się na .csv"
    
    # Sprawdź czy nie ma innych rozszerzeń w nazwie
    if new_filename.count('.') > 1:
        conn.close()
        return False, "Nazwa pliku nie może zawierać innych kropek"
    
    # Sprawdź czy nowa nazwa nie jest już używana przez inny plik użytkownika
    c.execute("SELECT id FROM files WHERE user_id = ? AND filename = ? AND id != ?", 
              (user_id, new_filename, file_id))
    if c.fetchone():
        conn.close()
        return False, "Plik o takiej nazwie już istnieje"
    
    # Zmień nazwę pliku
    c.execute("UPDATE files SET filename = ? WHERE id = ?", (new_filename, file_id))
    conn.commit()
    conn.close()
    return True, "Nazwa pliku została zmieniona"

def get_user_files(user_id):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("SELECT id, filename, upload_date FROM files WHERE user_id = ? ORDER BY upload_date DESC",
              (user_id,))
    files = c.fetchall()
    conn.close()
    return files

def get_file_data(file_id, user_id):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("SELECT file_data FROM files WHERE id = ? AND user_id = ?",
              (file_id, user_id))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def delete_file(file_id, user_id):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute("DELETE FROM files WHERE id = ? AND user_id = ?",
              (file_id, user_id))
    success = c.rowcount > 0
    conn.commit()
    conn.close()
    return success

# -------------------------------
# Udostępnianie plików
# -------------------------------
def share_file_with_user(file_id, target_username):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    # Pobierz id użytkownika docelowego
    c.execute("SELECT id FROM users WHERE username = ?", (target_username,))
    target_user = c.fetchone()
    if not target_user:
        conn.close()
        return False, "Nie znaleziono użytkownika"
    target_user_id = target_user[0]

    # Sprawdź czy plik należy do aktualnego użytkownika
    c.execute("SELECT user_id FROM files WHERE id = ?", (file_id,))
    owner = c.fetchone()
    if not owner or owner[0] != st.session_state.user_id:
        conn.close()
        return False, "Brak dostępu do pliku"

    # Sprawdź, czy już nie udostępniono
    c.execute("SELECT id FROM shared_files WHERE file_id = ? AND shared_with_user_id = ?", (file_id, target_user_id))
    if c.fetchone():
        conn.close()
        return False, "Plik jest już udostępniony temu użytkownikowi"

    c.execute("INSERT INTO shared_files (file_id, shared_with_user_id) VALUES (?, ?)", (file_id, target_user_id))
    conn.commit()
    conn.close()
    return True, "Plik udostępniony"

def get_shared_files(user_id):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    c.execute('''
        SELECT f.id, f.filename, f.upload_date, u.username, sf.share_date
        FROM files f
        JOIN shared_files sf ON f.id = sf.file_id
        JOIN users u ON f.user_id = u.id
        WHERE sf.shared_with_user_id = ?
        ORDER BY sf.share_date DESC
    ''', (user_id,))
    shared = c.fetchall()
    conn.close()
    return shared

def get_file_data_shared(file_id, user_id):
    conn = sqlite3.connect("notes.db")
    c = conn.cursor()
    # Sprawdź czy użytkownik ma dostęp do pliku (jest właścicielem lub ma udostępniony)
    c.execute('''
        SELECT f.file_data 
        FROM files f
        LEFT JOIN shared_files sf ON f.id = sf.file_id
        WHERE f.id = ? AND (f.user_id = ? OR sf.shared_with_user_id = ?)
    ''', (file_id, user_id, user_id))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(page_title="Mini BI", layout="wide")

# Autoryzacja
if "user_id" not in st.session_state:
    st.session_state.user_id = None
    st.session_state.username = None

if st.session_state.user_id is None:
    st.title("🔐 Zaloguj się lub zarejestruj")

    tab1, tab2 = st.tabs(["🔑 Logowanie", "📝 Rejestracja"])

    with tab1:
        username = st.text_input("Login")
        password = st.text_input("Hasło", type="password")
        if st.button("Zaloguj"):
            user_id = login_user(username, password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.username = username
                st.success(f"✅ Zalogowano jako {username}")
                st.rerun()
            else:
                st.error("❌ Błędny login lub hasło")

    with tab2:
        new_user = st.text_input("Nowa nazwa użytkownika")
        new_pass = st.text_input("Nowe hasło", type="password")
        if st.button("Zarejestruj"):
            if register_user(new_user, new_pass):
                st.success("✅ Konto utworzone. Możesz się zalogować.")
            else:
                st.error("❌ Użytkownik już istnieje")

    st.stop()

# Główna aplikacja po zalogowaniu
st.title("📊 Mini BI – przeglądarka danych i notatki")
st.sidebar.markdown(f"👤 Zalogowany jako: `{st.session_state.username}`")
if st.sidebar.button("🚪 Wyloguj", use_container_width=True):
    st.session_state.user_id = None
    st.session_state.username = None
    st.rerun()

# Dodaj separator
st.sidebar.markdown("---")

# Notatki i udostępnianie w sidebar
with st.sidebar:
    st.header("📝 Notatki")
    
    # Dodaj notatkę
    with st.form("note_form"):
        note_text = st.text_area("Nowa notatka", height=100)
        submitted = st.form_submit_button("Dodaj notatkę")
        if submitted and note_text.strip():
            add_note(st.session_state.user_id, note_text.strip())
            st.success("Notatka dodana")
            st.rerun()
    
    # Wyszukiwanie notatek
    search_term = st.text_input("Szukaj w notatkach")
    
    # Opcje sortowania
    sort_option = st.selectbox(
        "Sortuj według",
        ["Najnowsze", "Najstarsze", "Alfabetycznie"],
        index=0
    )

    # Pobierz notatki użytkownika
    notes = get_notes(st.session_state.user_id)
    
    # Sortowanie notatek
    if sort_option == "Najnowsze":
        notes.sort(key=lambda x: x[2], reverse=True)
    elif sort_option == "Najstarsze":
        notes.sort(key=lambda x: x[2])
    else:  # Alfabetycznie
        notes.sort(key=lambda x: x[1].lower())
    
    if search_term:
        notes = [n for n in notes if search_term.lower() in n[1].lower()]
    
    if notes:
        st.subheader("Twoje notatki")
        for note_id, content, timestamp in notes:
            st.markdown(f"**{timestamp}**")
            
            # Edycja notatki
            if f"edit_{note_id}" not in st.session_state:
                st.session_state[f"edit_{note_id}"] = False
            
            if st.session_state[f"edit_{note_id}"]:
                edited_content = st.text_area("Edytuj notatkę", value=content, key=f"edit_area_{note_id}")
                col1, col2 = st.columns([1,1])
                with col1:
                    if st.button("Zapisz", key=f"save_{note_id}"):
                        if edit_note(note_id, st.session_state.user_id, edited_content):
                            st.success("Notatka zaktualizowana")
                            st.session_state[f"edit_{note_id}"] = False
                            st.rerun()
                with col2:
                    if st.button("Anuluj", key=f"cancel_{note_id}"):
                        st.session_state[f"edit_{note_id}"] = False
                        st.rerun()
            else:
                st.markdown(content)
                col1, col2 = st.columns([2,1])
                with col1:
                    if st.button("✏️ Edytuj", key=f"edit_btn_{note_id}"):
                        st.session_state[f"edit_{note_id}"] = True
                        st.rerun()
                with col2:
                    if st.button("🗑️ Usuń", key=f"del_{note_id}"):
                        delete_note(note_id, st.session_state.user_id)
                        st.rerun()
            st.markdown("---")

    else:
        st.info("Brak notatek")

    # Udostępnianie notatki
    st.subheader("📤 Udostępnij notatkę")

    if notes:
        note_ids = [note[0] for note in notes]
        note_texts = [note[1][:30] + ("..." if len(note[1]) > 30 else "") for note in notes]
        selected_note_idx = st.selectbox("Wybierz notatkę do udostępnienia", range(len(notes)), format_func=lambda i: note_texts[i])

        target_user = st.text_input("Udostępnij użytkownikowi (login)")

        if st.button("📤 Udostępnij"):
            success, msg = share_note_with_user(note_ids[selected_note_idx], target_user.strip())
            if success:
                st.success(msg)
            else:
                st.error(msg)

    # Notatki udostępnione dla użytkownika
    shared_notes = get_shared_notes(st.session_state.user_id)
    if shared_notes:
        st.subheader("📨 Notatki udostępnione dla Ciebie")
        for note_id, content, timestamp, owner_username in shared_notes:
            st.markdown(f"**{timestamp}** – od `{owner_username}`")
            st.markdown(content)
            st.markdown("---")

# Dodaj sekcję ustawień konta na samym dole sidebara
with st.sidebar.expander("⚙️ Ustawienia konta", expanded=False):
    st.markdown("### Usuń konto")
    st.warning("⚠️ Uwaga: Usunięcie konta jest nieodwracalne. Wszystkie Twoje pliki i notatki zostaną usunięte.")
    
    confirm_delete = st.checkbox("Potwierdzam, że chcę usunąć swoje konto")
    if st.button("🗑️ Usuń konto", type="primary", disabled=not confirm_delete):
        success, message = delete_account(st.session_state.user_id)
        if success:
            st.success(message)
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()
        else:
            st.error(message)

# Główne zakładki
tab1, tab2 = st.tabs(["📁 Pliki", "📊 Analiza danych"])

with tab1:
    st.header("Zarządzanie plikami")
    
    # Wczytywanie pliku
    uploaded_file = st.file_uploader("Wybierz plik CSV", type=["csv"])
    if uploaded_file is not None:
        file_data = uploaded_file.getvalue()
        success, message = save_file(st.session_state.user_id, uploaded_file.name, file_data)
        if success:
            st.success(f"✅ {message}")
        else:
            st.error(f"❌ {message}")
    
    # Lista plików
    st.subheader("Twoje pliki")
    files = get_user_files(st.session_state.user_id)
    if files:
        for file_id, filename, upload_date in files:
            col1, col2, col3, col4 = st.columns([3,1,1,1])
            with col1:
                st.markdown(f"**{filename}**")
                st.caption(f"Data dodania: {upload_date}")
            with col2:
                if st.button("✏️ Zmień nazwę", key=f"rename_file_{file_id}"):
                    st.session_state[f"renaming_file_{file_id}"] = True
            with col3:
                if st.button("🗑️ Usuń", key=f"del_file_{file_id}"):
                    if delete_file(file_id, st.session_state.user_id):
                        st.success("Plik usunięty")
                        st.rerun()
            with col4:
                if st.button("📤 Udostępnij", key=f"share_file_{file_id}"):
                    st.session_state[f"sharing_file_{file_id}"] = True
            
            if st.session_state.get(f"renaming_file_{file_id}", False):
                new_filename = st.text_input("Nowa nazwa pliku (musi kończyć się na .csv)", 
                                           value=filename, 
                                           key=f"new_filename_{file_id}")
                col1, col2 = st.columns([1,1])
                with col1:
                    if st.button("Zapisz", key=f"save_rename_{file_id}"):
                        if new_filename.strip():
                            if not new_filename.lower().endswith('.csv'):
                                st.error("Nazwa pliku musi kończyć się na .csv")
                            elif new_filename.count('.') > 1:
                                st.error("Nazwa pliku nie może zawierać innych kropek")
                            else:
                                success, msg = rename_file(file_id, st.session_state.user_id, new_filename.strip())
                                if success:
                                    st.success(msg)
                                else:
                                    st.error(msg)
                                st.session_state[f"renaming_file_{file_id}"] = False
                                st.rerun()
                        else:
                            st.error("Nazwa pliku nie może być pusta")
                with col2:
                    if st.button("Anuluj", key=f"cancel_rename_{file_id}"):
                        st.session_state[f"renaming_file_{file_id}"] = False
                        st.rerun()
            
            if st.session_state.get(f"sharing_file_{file_id}", False):
                target_user = st.text_input("Udostępnij użytkownikowi (login)", key=f"share_user_{file_id}")
                
                col1, col2 = st.columns([1,1])
                with col1:
                    if st.button("Potwierdź", key=f"confirm_share_{file_id}"):
                        if target_user.strip():
                            if target_user.strip() == st.session_state.username:
                                st.error("Nie możesz udostępnić pliku samemu sobie")
                            elif not check_user_exists(target_user.strip()):
                                st.error("Nie znaleziono takiego użytkownika")
                            else:
                                success, msg = share_file_with_user(file_id, target_user.strip())
                                if success:
                                    st.success(msg)
                                else:
                                    st.error(msg)
                                st.session_state[f"sharing_file_{file_id}"] = False
                                st.rerun()
                        else:
                            st.error("Wprowadź nazwę użytkownika")
                with col2:
                    if st.button("Anuluj", key=f"cancel_share_{file_id}"):
                        st.session_state[f"sharing_file_{file_id}"] = False
                        st.rerun()
            st.markdown("---")
    else:
        st.info("Brak zapisanych plików")

    # Udostępnione pliki
    st.subheader("📨 Pliki udostępnione dla Ciebie")
    shared_files = get_shared_files(st.session_state.user_id)
    if shared_files:
        for file_id, filename, upload_date, owner_username, share_date in shared_files:
            st.markdown(f"**{filename}**")
            st.caption(f"Udostępniony przez: {owner_username}")
            st.caption(f"Data udostępnienia: {share_date}")
            st.caption(f"Data dodania: {upload_date}")
            st.markdown("---")
    else:
        st.info("Nie masz żadnych udostępnionych plików")

with tab2:
    st.header("Analiza danych")
    
    # Wybór pliku do analizy
    files = get_user_files(st.session_state.user_id)
    shared_files = get_shared_files(st.session_state.user_id)
    
    # Przygotuj listę wszystkich dostępnych plików
    all_files = []
    for file_id, filename, upload_date in files:
        all_files.append((file_id, filename, upload_date, "Moje pliki"))
    for file_id, filename, upload_date, owner_username, share_date in shared_files:
        all_files.append((file_id, filename, upload_date, f"Udostępnione przez: {owner_username}"))
    
    if all_files:
        selected_file = st.selectbox(
            "Wybierz plik do analizy",
            options=all_files,
            format_func=lambda x: f"{x[1]} ({x[3]})"
        )
        
        if selected_file:
            file_data = get_file_data_shared(selected_file[0], st.session_state.user_id)
            if file_data:
                df = pd.read_csv(pd.io.common.BytesIO(file_data))
                st.session_state.current_df = df
                st.session_state.current_filename = selected_file[1]
                
                # Analiza wybranego pliku
                st.subheader(f"Analiza pliku: {st.session_state.current_filename}")
                
                st.subheader("🔍 Podgląd danych")
                st.dataframe(df)

                st.subheader("📊 Statystyki ogólne")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Liczba wierszy", len(df))
                with col2:
                    st.metric("Liczba kolumn", len(df.columns))

                st.write(df.describe())

                numeric_cols = df.select_dtypes(include='number').columns.tolist()
                categorical_cols = df.select_dtypes(include='object').columns.tolist()

                # Filtrowanie danych
                st.subheader("🔎 Filtrowanie danych")
                selected_col = st.selectbox("Wybierz kolumnę do filtrowania", df.columns)

                if df[selected_col].dtype == 'object':
                    selected_vals = st.multiselect("Wybierz wartości", df[selected_col].unique())
                    if selected_vals:
                        df = df[df[selected_col].isin(selected_vals)]
                else:
                    min_val, max_val = float(df[selected_col].min()), float(df[selected_col].max())
                    selected_range = st.slider("Zakres", min_val, max_val, (min_val, max_val))
                    df = df[(df[selected_col] >= selected_range[0]) & (df[selected_col] <= selected_range[1])]

                st.download_button("⬇️ Pobierz przefiltrowane dane CSV", df.to_csv(index=False), file_name="filtered_data.csv")

                # Wykresy
                st.subheader("📈 Wykresy")

                col1, col2 = st.columns(2)
                with col1:
                    col_to_plot = st.selectbox("Kolumna numeryczna", numeric_cols)
                    if col_to_plot:
                        fig = px.histogram(df, x=col_to_plot)
                        st.plotly_chart(fig, use_container_width=True)

                with col2:
                    col_cat = st.selectbox("Kolumna kategoryczna", categorical_cols)
                    if col_cat:
                        value_counts_df = df[col_cat].value_counts().reset_index()
                        value_counts_df.columns = [col_cat, "count"]
                        fig = px.bar(value_counts_df, x=col_cat, y="count")
                        st.plotly_chart(fig, use_container_width=True)

                st.subheader("📉 Scatterplot (2 kolumny)")
                cols_scatter = st.multiselect("Wybierz 2 kolumny", numeric_cols, max_selections=2)
                if len(cols_scatter) == 2:
                    fig = px.scatter(df, x=cols_scatter[0], y=cols_scatter[1])
                    st.plotly_chart(fig, use_container_width=True)

                st.subheader("📊 Grupowanie i agregacja")
                group_col = st.selectbox("Grupuj wg", categorical_cols)
                agg_col = st.selectbox("Agreguj kolumnę", numeric_cols)
                agg_func = st.selectbox("Funkcja agregująca", ["sum", "mean", "count"])

                if group_col and agg_col:
                    grouped_df = df.groupby(group_col)[agg_col].agg(agg_func).reset_index()
                    fig = px.bar(grouped_df, x=group_col, y=agg_col)
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Najpierw wgraj plik CSV w zakładce 'Pliki'")
