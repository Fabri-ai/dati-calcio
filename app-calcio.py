import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import date, datetime
import hashlib
import time
import base64

# Configurazione pagina
st.set_page_config(
    page_title="Gestione Giocatori",
    page_icon="⚽",
    layout="wide"
)

# Funzione per l'hash delle password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Utenti autorizzati (in un'app reale, questi dovrebbero essere in un database sicuro)
USERS = {
    "admin": hash_password("admin123"),
    "scout": hash_password("scout123"),
    "manager": hash_password("manager123")
}

# Funzione di autenticazione
def authenticate(username, password):
    return username in USERS and USERS[username] == hash_password(password)

# FIX: Funzioni per gestire l'autenticazione persistente tramite URL
def create_auth_token(username):
    """Crea un token di autenticazione sicuro"""
    timestamp = str(int(time.time()))
    raw_token = f"{username}:{timestamp}:{hash_password(username + timestamp)}"
    return base64.b64encode(raw_token.encode()).decode()

def validate_auth_token(token):
    """Valida il token di autenticazione"""
    try:
        decoded = base64.b64decode(token.encode()).decode()
        parts = decoded.split(':')
        if len(parts) != 3:
            return None
        
        username, timestamp, token_hash = parts
        
        # Verifica che l'utente esista
        if username not in USERS:
            return None
        
        # Verifica che il token non sia troppo vecchio (24 ore)
        current_time = int(time.time())
        token_time = int(timestamp)
        if current_time - token_time > 86400:  # 24 ore
            return None
        
        # Verifica l'hash del token
        expected_hash = hash_password(username + timestamp)
        if token_hash != expected_hash:
            return None
        
        return username
    except:
        return None

def set_auth_url(username):
    """Imposta l'URL con il token di autenticazione"""
    token = create_auth_token(username)
    st.query_params.update({"auth": token})

def clear_auth_url():
    """Rimuove il token dall'URL"""
    if "auth" in st.query_params:
        del st.query_params["auth"]

def check_url_auth():
    """Controlla se c'è un token valido nell'URL"""
    if "auth" in st.query_params:
        token = st.query_params["auth"]
        username = validate_auth_token(token)
        if username:
            return username
    return None

# FIX: Inizializzazione robusta dello stato di sessione con controllo URL
def initialize_session_state():
    """Inizializza tutti i parametri di sessione necessari"""
    
    # Prima controlla se c'è un'autenticazione valida nell'URL
    url_username = check_url_auth()
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = bool(url_username)
    
    if "username" not in st.session_state:
        st.session_state.username = url_username or ""
    
    # Se abbiamo un username dall'URL ma non siamo autenticati nel session state
    if url_username and not st.session_state.authenticated:
        st.session_state.authenticated = True
        st.session_state.username = url_username
    
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = 0
    if "selected_player_index" not in st.session_state:
        st.session_state.selected_player_index = 0
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = time.time()
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(int(time.time()))
    if "prevent_reset" not in st.session_state:
        st.session_state.prevent_reset = False

# FIX: Funzione per mantenere la sessione attiva
def keep_session_alive():
    """Mantiene la sessione attiva e previene reset inaspettati"""
    current_time = time.time()
    st.session_state.last_activity = current_time
    
    # Forza il mantenimento dell'autenticazione
    if "authenticated" in st.session_state and st.session_state.authenticated:
        st.session_state.prevent_reset = True
        
        # Assicura che l'URL abbia sempre il token aggiornato
        if st.session_state.username and "auth" not in st.query_params:
            set_auth_url(st.session_state.username)

# Funzione per inizializzare la connessione a Google Sheets
@st.cache_resource
def init_gsheet():
    try:
        # Configurazione delle credenziali Google Sheets
        if "gsheet_credentials" in st.secrets:
            credentials_info = dict(st.secrets["gsheet_credentials"])
            
            credentials = Credentials.from_service_account_info(
                credentials_info,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
            )
            
            gc = gspread.authorize(credentials)
            sheet_id = st.secrets.get("sheet_id", "1GjubMgZkxjISauMyrnQdZlunOUMEKKSGoEwk6tm7d4c")
            
            try:
                spreadsheet = gc.open_by_key(sheet_id)
                sheet = spreadsheet.sheet1
                sheet.get('A1:A1')
                return sheet
            except gspread.exceptions.SpreadsheetNotFound:
                st.error("❌ Foglio Google Sheets non trovato. Verifica l'ID del foglio.")
                st.error("💡 Assicurati che il service account abbia accesso al foglio.")
                return None
            except gspread.exceptions.APIError as api_error:
                st.error(f"❌ Errore API Google Sheets: {str(api_error)}")
                st.error("💡 Verifica che le API Google Sheets e Drive siano abilitate.")
                return None
                
        else:
            st.warning("⚠️ Credenziali Google Sheets non configurate. Modalità demo attiva.")
            return None
            
    except Exception as e:
        st.error(f"Errore connessione Google Sheets: {str(e)}")
        st.error("💡 Verifica che il service account abbia accesso al foglio e che le API siano abilitate.")
        return None

# FIX: Cache con gestione migliorata per evitare reset
@st.cache_data(ttl=60, show_spinner="Caricamento dati...")
def load_data(_session_id=None):
    """Carica i dati con cache persistente basata su session_id"""
    sheet = init_gsheet()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            # Aggiungi colonne se non esistono
            new_columns = {
                "Numero Visione Partite": 0,
                "Livello 1": "",
                "Livello 2": "",
                "Livello 1 Prospettiva": "",
                "Link Transfermarkt": "",
                "Data inserimento in piattaforma": "",
                "Data ultima visione": "",
                "Data presentazione a Miniero": ""
            }
            
            if len(df) > 0:
                for col_name, default_value in new_columns.items():
                    if col_name not in df.columns:
                        df[col_name] = default_value
            
            if len(df) > 0:
                rows_info = f"Righe utilizzate: {len(df)+1}/10,000,000 (Google Sheets supporta fino a 10 milioni di righe)"
                if "rows_info" not in st.session_state:
                    st.session_state.rows_info = rows_info
            
            return df
        except Exception as e:
            try:
                headers = [
                    "Nome Giocatore", "Squadra", "Età", "Ruolo", "Valore di Mercato",
                    "Procuratore", "Altezza", "Piede", "Convocazioni", "Partite Giocate",
                    "Gol", "Assist", "Minuti Giocati", "Data Inizio Contratto", 
                    "Data Fine Contratto", "Numero Visione Partite", 
                    "Data inserimento in piattaforma", "Data ultima visione", 
                    "Data presentazione a Miniero",
                    "Da Monitorare", "Note Danilo/Antonio", "Note Alessio/Fabrizio", 
                    "Presentato a Miniero", "Risposta Miniero", "Livello 1", "Livello 2", 
                    "Livello 1 Prospettiva", "Link Transfermarkt"
                ]
                sheet.insert_row(headers, 1)
                return pd.DataFrame(columns=headers)
            except Exception as header_error:
                st.error(f"Errore nell'inizializzazione del foglio: {str(header_error)}")
                return pd.DataFrame()
    else:
        # Modalità demo con dati di esempio
        sample_data = {
            "Nome Giocatore": ["Mario Rossi", "Luca Bianchi"],
            "Squadra": ["Juventus", "Milan"],
            "Età": [25, 28],
            "Ruolo": ["Centrocampista", "Attaccante"],
            "Valore di Mercato": ["15M€", "20M€"],
            "Procuratore": ["Raiola", "Mendes"],
            "Altezza": [180, 175],
            "Piede": ["Destro", "Sinistro"],
            "Convocazioni": [45, 52],
            "Partite Giocate": [38, 41],
            "Gol": [8, 15],
            "Assist": [12, 7],
            "Minuti Giocati": [3200, 3650],
            "Data Inizio Contratto": ["2022-07-01", "2021-08-15"],
            "Data Fine Contratto": ["2025-06-30", "2024-07-31"],
            "Numero Visione Partite": [5, 8],
            "Data inserimento in piattaforma": ["2024-01-15", "2024-02-20"],
            "Data ultima visione": ["2024-03-10", "2024-03-25"],
            "Data presentazione a Miniero": ["2024-02-01", ""],
            "Da Monitorare": ["X", ""],
            "Note Danilo/Antonio": ["Buon potenziale", "Ottimo in zona gol"],
            "Note Alessio/Fabrizio": ["Da seguire", "Pronto per il salto"],
            "Presentato a Miniero": ["X", ""],
            "Risposta Miniero": ["Interessante", "Da valutare"],
            "Livello 1": ["X", ""],
            "Livello 2": ["", "X"],
            "Livello 1 Prospettiva": ["", "X"],
            "Link Transfermarkt": ["https://www.transfermarkt.it/mario-rossi/profil/spieler/123456", 
                                   "https://www.transfermarkt.it/luca-bianchi/profil/spieler/789012"]
        }
        return pd.DataFrame(sample_data)

# Funzione per salvare i dati
def save_data(df):
    sheet = init_gsheet()
    if sheet:
        try:
            sheet.clear()
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            st.success("✅ Dati salvati con successo!")
            
            # FIX: Pulizia cache più selettiva
            load_data.clear()
            
            rows_info = f"Righe utilizzate: {len(df)+1}/10,000,000 (Google Sheets supporta fino a 10 milioni di righe)"
            st.session_state.rows_info = rows_info
            
        except Exception as e:
            st.error(f"❌ Errore nel salvataggio: {str(e)}")
    else:
        st.info("💾 Modalità demo - i dati non vengono salvati permanentemente")

# Funzione per convertire stringhe di date in oggetti date
def safe_date_convert(date_str):
    try:
        if isinstance(date_str, str) and date_str:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        return date.today()
    except:
        return date.today()

# Funzione per conversione sicura dei numeri
def safe_int_convert(value, default=0):
    try:
        if pd.isna(value) or value == '' or value is None:
            return default
        return int(float(str(value)))
    except (ValueError, TypeError):
        return default

# FIX: Gestione robusta del logout con pulizia URL
def handle_logout():
    """Gestisce il logout in modo pulito"""
    # Pulisce l'URL dal token
    clear_auth_url()
    
    # Mantieni alcune informazioni di sessione se necessario
    session_id = st.session_state.get("session_id")
    
    # Pulisci solo i dati di autenticazione, non tutto
    keys_to_keep = ["session_id"]
    keys_to_remove = [key for key in st.session_state.keys() if key not in keys_to_keep]
    
    for key in keys_to_remove:
        del st.session_state[key]
    
    # Inizializza di nuovo
    initialize_session_state()
    st.rerun()

# Funzione principale dell'app
def main():
    # FIX: Inizializzazione robusta all'avvio con controllo URL
    initialize_session_state()
    keep_session_alive()

    # FIX: Controllo autenticazione con persistenza migliorata tramite URL
    if not st.session_state.authenticated:
        st.title("🔐 Login - Gestione Giocatori")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                login_button = st.form_submit_button("Accedi")
                
                if login_button:
                    if authenticate(username, password):
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.prevent_reset = True
                        
                        # FIX: Imposta il token nell'URL per la persistenza
                        set_auth_url(username)
                        
                        keep_session_alive()
                        st.success("✅ Accesso effettuato!")
                        time.sleep(0.5)  # Piccola pausa per mostrare il messaggio
                        st.rerun()
                    else:
                        st.error("❌ Credenziali non valide")
        
        # Informazioni per demo
        st.info("""
        **Credenziali demo:**
        - Username: admin, Password: admin123
        - Username: scout, Password: scout123
        - Username: manager, Password: manager123
        """)
        return

    # FIX: Mantieni la sessione attiva durante l'uso
    keep_session_alive()

    # Interfaccia principale
    st.title("⚽ Gestione Giocatori di Calcio")
    
    # Sidebar con logout e info
    with st.sidebar:
        st.write(f"👤 Utente: {st.session_state.username}")
        st.write(f"🔗 Sessione: {st.session_state.session_id[:8]}...")
        
        if st.button("🚪 Logout", key="logout_btn"):
            handle_logout()
        
        if "rows_info" in st.session_state:
            st.info(st.session_state.rows_info)
        
        # FIX: Indicatore di sessione attiva
        st.success("🟢 Sessione attiva")
        
        # FIX: Pulsante per refresh dati
        if st.button("🔄 Aggiorna Dati", key="refresh_data"):
            load_data.clear()
            st.rerun()

    # FIX: Caricamento dati con session_id per stabilità
    df = load_data(_session_id=st.session_state.session_id)

    # Tabs con gestione migliorata
    tab_names = ["📊 Dashboard", "➕ Aggiungi Giocatore", "✏️ Modifica Dati", "🔍 Ricerca"]
    selected_tab = st.tabs(tab_names)

    # Dashboard
    with selected_tab[0]:
        st.header("Dashboard Giocatori")
        
        if not df.empty:
            # Metriche generali
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Totale Giocatori", len(df))
            with col2:
                monitored = len(df[df["Da Monitorare"] == "X"])
                st.metric("Da Monitorare", monitored)
            with col3:
                presented = len(df[df["Presentato a Miniero"] == "X"])
                st.metric("Presentati a Miniero", presented)
            with col4:
                if "Età" in df.columns and len(df) > 0:
                    ages = pd.to_numeric(df["Età"], errors='coerce').dropna()
                    avg_age = ages.mean() if len(ages) > 0 else 0
                else:
                    avg_age = 0
                st.metric("Età Media", f"{avg_age:.1f}")
            
            st.divider()
            
            # Filtri di ricerca
            st.subheader("🔍 Filtri di Ricerca")
            col_search1, col_search2, col_search3 = st.columns(3)
            
            with col_search1:
                search_name_dash = st.text_input("🔍 Cerca per Nome", key="search_dash")
                
            with col_search2:
                filter_squad_dash = st.multiselect("Filtra per Squadra", options=df["Squadra"].unique(), key="squad_dash")
                
            with col_search3:
                filter_role_dash = st.multiselect("Filtra per Ruolo", options=df["Ruolo"].unique(), key="role_dash")
            
            # Applica filtri
            filtered_df = df.copy()
            
            if search_name_dash:
                filtered_df = filtered_df[filtered_df["Nome Giocatore"].str.contains(search_name_dash, case=False, na=False)]
            
            if filter_squad_dash:
                filtered_df = filtered_df[filtered_df["Squadra"].isin(filter_squad_dash)]
                
            if filter_role_dash:
                filtered_df = filtered_df[filtered_df["Ruolo"].isin(filter_role_dash)]
            
            st.info(f"📊 Visualizzati **{len(filtered_df)}** giocatori su {len(df)} totali")
            
            st.divider()
            
            # Sezione Anagrafica Giocatore
            st.subheader("👤 Anagrafica Giocatore")
            anagrafica_cols = [
                "Nome Giocatore", "Squadra", "Età", "Ruolo", "Valore di Mercato",
                "Procuratore", "Altezza", "Piede", "Convocazioni", "Partite Giocate",
                "Gol", "Assist", "Minuti Giocati", "Data Inizio Contratto", 
                "Data Fine Contratto", "Link Transfermarkt"
            ]
            df_anagrafica = filtered_df[[col for col in anagrafica_cols if col in filtered_df.columns]]
            st.dataframe(df_anagrafica, use_container_width=True, hide_index=True)
            
            st.divider()
            
            # Sezione Nostra Analisi
            st.subheader("📊 Nostra Analisi")
            analisi_cols = [
                "Nome Giocatore", "Squadra", "Da Monitorare", "Presentato a Miniero", 
                "Risposta Miniero", "Numero Visione Partite", "Livello 1", "Livello 2", 
                "Livello 1 Prospettiva", "Data inserimento in piattaforma", 
                "Data ultima visione", "Data presentazione a Miniero"
            ]
            df_analisi = filtered_df[[col for col in analisi_cols if col in filtered_df.columns]]
            st.dataframe(df_analisi, use_container_width=True, hide_index=True)
            
            st.divider()
            
            # Sezione Nostre Note
            st.subheader("📝 Nostre Note")
            note_cols = [
                "Nome Giocatore", "Squadra", "Note Danilo/Antonio", "Note Alessio/Fabrizio"
            ]
            df_note = filtered_df[[col for col in note_cols if col in filtered_df.columns]]
            st.dataframe(df_note, use_container_width=True, hide_index=True)
            
        else:
            st.info("Nessun giocatore nel database. Inizia aggiungendo un nuovo giocatore!")

    # Aggiungi Giocatore
    with selected_tab[1]:
        st.header("Aggiungi Nuovo Giocatore")
        
        with st.form("add_player_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome Giocatore*")
                squadra = st.text_input("Squadra*")
                eta = st.number_input("Età", min_value=16, max_value=50, value=25)
                ruolo = st.selectbox("Ruolo", [
                    "Portiere", "Difensore Centrale", "Terzino Destro", 
                    "Terzino Sinistro", "Centrocampista Difensivo",
                    "Centrocampista", "Centrocampista Offensivo",
                    "Ala Destra", "Ala Sinistra", "Attaccante", "Seconda Punta"
                ])
                valore = st.text_input("Valore di Mercato (es. 15M€)")
                procuratore = st.text_input("Procuratore")
                altezza = st.number_input("Altezza (cm)", min_value=150, max_value=220, value=180)
                piede = st.selectbox("Piede", ["Destro", "Sinistro", "Ambidestro"])
                
                st.write("")  # Spaziatura
                col_liv1, col_liv2, col_liv3 = st.columns(3)
                with col_liv1:
                    livello_1 = st.checkbox("Livello 1")
                with col_liv2:
                    livello_2 = st.checkbox("Livello 2")
                with col_liv3:
                    livello_1_prospettiva = st.checkbox("Livello 1 Prospettiva")
                
            with col2:
                convocazioni = st.number_input("Convocazioni", min_value=0, value=0)
                partite = st.number_input("Partite Giocate", min_value=0, value=0)
                gol = st.number_input("Gol", min_value=0, value=0)
                assist = st.number_input("Assist", min_value=0, value=0)
                minuti = st.number_input("Minuti Giocati", min_value=0, value=0)
                
                inizio_contratto = st.date_input("Data Inizio Contratto")
                fine_contratto = st.date_input("Data Fine Contratto")
                
                numero_visione = st.number_input("Numero Visione Partite", min_value=0, value=0)
                
                # NUOVI CAMPI DATA
                data_inserimento = st.date_input("📅 Data inserimento in piattaforma", value=date.today())
                data_ultima_visione = st.date_input("👁️ Data ultima visione")
                data_presentazione_miniero = st.date_input("🎯 Data presentazione a Miniero")
                
                da_monitorare = st.checkbox("Da Monitorare")
                presentato_miniero = st.checkbox("Presentato a Miniero")
            
            note_danilo = st.text_area("Note Danilo/Antonio")
            note_alessio = st.text_area("Note Alessio/Fabrizio")
            risposta_miniero = st.text_area("Risposta Miniero")
            
            link_transfermarkt = st.text_input("Link Transfermarkt", placeholder="https://www.transfermarkt.it/...")
            
            if st.form_submit_button("➕ Aggiungi Giocatore"):
                if nome and squadra:
                    new_player = {
                        "Nome Giocatore": nome,
                        "Squadra": squadra,
                        "Età": eta,
                        "Ruolo": ruolo,
                        "Valore di Mercato": valore,
                        "Procuratore": procuratore,
                        "Altezza": altezza,
                        "Piede": piede,
                        "Convocazioni": convocazioni,
                        "Partite Giocate": partite,
                        "Gol": gol,
                        "Assist": assist,
                        "Minuti Giocati": minuti,
                        "Data Inizio Contratto": inizio_contratto.strftime("%Y-%m-%d"),
                        "Data Fine Contratto": fine_contratto.strftime("%Y-%m-%d"),
                        "Numero Visione Partite": numero_visione,
                        "Data inserimento in piattaforma": data_inserimento.strftime("%Y-%m-%d"),
                        "Data ultima visione": data_ultima_visione.strftime("%Y-%m-%d"),
                        "Data presentazione a Miniero": data_presentazione_miniero.strftime("%Y-%m-%d"),
                        "Da Monitorare": "X" if da_monitorare else "",
                        "Note Danilo/Antonio": note_danilo,
                        "Note Alessio/Fabrizio": note_alessio,
                        "Presentato a Miniero": "X" if presentato_miniero else "",
                        "Risposta Miniero": risposta_miniero,
                        "Livello 1": "X" if livello_1 else "",
                        "Livello 2": "X" if livello_2 else "",
                        "Livello 1 Prospettiva": "X" if livello_1_prospettiva else "",
                        "Link Transfermarkt": link_transfermarkt
                    }
                    
                    df_new = pd.concat([df, pd.DataFrame([new_player])], ignore_index=True)
                    save_data(df_new)
                    st.info(f"✅ Giocatore aggiunto! Totale giocatori nel database: {len(df_new)}")
                else:
                    st.error("❌ Nome e Squadra sono campi obbligatori!")

    # FIX: Modifica Dati con gestione robusta della selezione
    with selected_tab[2]:
        st.header("Modifica Dati Esistenti")
        
        if not df.empty:
            # FIX: Gestione migliorata della selezione giocatore
            if st.session_state.selected_player_index >= len(df):
                st.session_state.selected_player_index = 0
            
            # FIX: Callback per gestire il cambio di selezione
            def on_player_change():
                # Aggiorna l'indice nel session state
                if "player_selector" in st.session_state:
                    st.session_state.selected_player_index = st.session_state.player_selector
                # Mantieni la sessione attiva
                keep_session_alive()
            
            # Selectbox con gestione migliorata
            selected_player = st.selectbox(
                "Seleziona Giocatore da Modificare",
                options=range(len(df)),
                format_func=lambda x: f"{df.iloc[x]['Nome Giocatore']} - {df.iloc[x]['Squadra']}",
                index=st.session_state.selected_player_index,
                key="player_selector",
                on_change=on_player_change
            )
            
            if selected_player is not None:
                player_data = df.iloc[selected_player]
                
                with st.form("edit_player_form", clear_on_submit=False):
                    st.subheader(f"Modifica: {player_data['Nome Giocatore']}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nome = st.text_input("Nome Giocatore*", value=str(player_data["Nome Giocatore"]))
                        squadra = st.text_input("Squadra*", value=str(player_data["Squadra"]))
                        eta = st.number_input("Età", min_value=16, max_value=50, 
                                            value=safe_int_convert(player_data.get("Età"), 25))
                        
                        ruoli = ["Portiere", "Difensore Centrale", "Terzino Destro", 
                                "Terzino Sinistro", "Centrocampista Difensivo",
                                "Centrocampista", "Centrocampista Offensivo",
                                "Ala Destra", "Ala Sinistra", "Attaccante", "Seconda Punta"]
                        current_ruolo = str(player_data.get("Ruolo", "Centrocampista"))
                        ruolo_index = ruoli.index(current_ruolo) if current_ruolo in ruoli else 0
                        ruolo = st.selectbox("Ruolo", ruoli, index=ruolo_index)
                        
                        valore = st.text_input("Valore di Mercato", value=str(player_data.get("Valore di Mercato", "")))
                        procuratore = st.text_input("Procuratore", value=str(player_data.get("Procuratore", "")))
                        altezza = st.number_input("Altezza (cm)", min_value=150, max_value=220, 
                                                value=safe_int_convert(player_data.get("Altezza"), 180))
                        
                        piedi = ["Destro", "Sinistro", "Ambidestro"]
                        current_piede = str(player_data.get("Piede", "Destro"))
                        piede_index = piedi.index(current_piede) if current_piede in piedi else 0
                        piede = st.selectbox("Piede", piedi, index=piede_index)
                        
                        st.write("")  # Spaziatura
                        col_liv1, col_liv2, col_liv3 = st.columns(3)
                        with col_liv1:
                            livello_1 = st.checkbox("Livello 1", value=player_data.get("Livello 1") == "X")
                        with col_liv2:
                            livello_2 = st.checkbox("Livello 2", value=player_data.get("Livello 2") == "X")
                        with col_liv3:
                            livello_1_prospettiva = st.checkbox("Livello 1 Prospettiva", 
                                                               value=player_data.get("Livello 1 Prospettiva") == "X")
                        
                    with col2:
                        convocazioni = st.number_input("Convocazioni", min_value=0, 
                                                     value=safe_int_convert(player_data.get("Convocazioni"), 0))
                        partite = st.number_input("Partite Giocate", min_value=0, 
                                                value=safe_int_convert(player_data.get("Partite Giocate"), 0))
                        gol = st.number_input("Gol", min_value=0, 
                                            value=safe_int_convert(player_data.get("Gol"), 0))
                        assist = st.number_input("Assist", min_value=0, 
                                               value=safe_int_convert(player_data.get("Assist"), 0))
                        minuti = st.number_input("Minuti Giocati", min_value=0, 
                                               value=safe_int_convert(player_data.get("Minuti Giocati"), 0))
                        
                        inizio_contratto = st.date_input("Data Inizio Contratto", 
                                                       value=safe_date_convert(player_data.get("Data Inizio Contratto")))
                        fine_contratto = st.date_input("Data Fine Contratto", 
                                                     value=safe_date_convert(player_data.get("Data Fine Contratto")))
                        
                        numero_visione = st.number_input("Numero Visione Partite", min_value=0, 
                                                        value=safe_int_convert(player_data.get("Numero Visione Partite"), 0))
                        
                        # NUOVI CAMPI DATA
                        data_inserimento = st.date_input("📅 Data inserimento in piattaforma", 
                                                        value=safe_date_convert(player_data.get("Data inserimento in piattaforma")))
                        data_ultima_visione = st.date_input("👁️ Data ultima visione", 
                                                           value=safe_date_convert(player_data.get("Data ultima visione")))
                        data_presentazione_miniero = st.date_input("🎯 Data presentazione a Miniero", 
                                                                  value=safe_date_convert(player_data.get("Data presentazione a Miniero")))
                        
                        da_monitorare = st.checkbox("Da Monitorare", value=player_data.get("Da Monitorare") == "X")
                        presentato_miniero = st.checkbox("Presentato a Miniero", 
                                                       value=player_data.get("Presentato a Miniero") == "X")
                    
                    note_danilo = st.text_area("Note Danilo/Antonio", 
                                             value=str(player_data.get("Note Danilo/Antonio", "")))
                    note_alessio = st.text_area("Note Alessio/Fabrizio", 
                                              value=str(player_data.get("Note Alessio/Fabrizio", "")))
                    risposta_miniero = st.text_area("Risposta Miniero", 
                                                  value=str(player_data.get("Risposta Miniero", "")))
                    
                    link_transfermarkt = st.text_input("Link Transfermarkt", 
                                                      value=str(player_data.get("Link Transfermarkt", "")),
                                                      placeholder="https://www.transfermarkt.it/...")
                    
                    col_save, col_delete = st.columns(2)
                    with col_save:
                        if st.form_submit_button("💾 Salva Modifiche", type="primary"):
                            if nome and squadra:
                                # Mantieni la sessione attiva durante il salvataggio
                                keep_session_alive()
                                
                                df.loc[selected_player, "Nome Giocatore"] = nome
                                df.loc[selected_player, "Squadra"] = squadra
                                df.loc[selected_player, "Età"] = eta
                                df.loc[selected_player, "Ruolo"] = ruolo
                                df.loc[selected_player, "Valore di Mercato"] = valore
                                df.loc[selected_player, "Procuratore"] = procuratore
                                df.loc[selected_player, "Altezza"] = altezza
                                df.loc[selected_player, "Piede"] = piede
                                df.loc[selected_player, "Convocazioni"] = convocazioni
                                df.loc[selected_player, "Partite Giocate"] = partite
                                df.loc[selected_player, "Gol"] = gol
                                df.loc[selected_player, "Assist"] = assist
                                df.loc[selected_player, "Minuti Giocati"] = minuti
                                df.loc[selected_player, "Data Inizio Contratto"] = inizio_contratto.strftime("%Y-%m-%d")
                                df.loc[selected_player, "Data Fine Contratto"] = fine_contratto.strftime("%Y-%m-%d")
                                df.loc[selected_player, "Numero Visione Partite"] = numero_visione
                                df.loc[selected_player, "Data inserimento in piattaforma"] = data_inserimento.strftime("%Y-%m-%d")
                                df.loc[selected_player, "Data ultima visione"] = data_ultima_visione.strftime("%Y-%m-%d")
                                df.loc[selected_player, "Data presentazione a Miniero"] = data_presentazione_miniero.strftime("%Y-%m-%d")
                                df.loc[selected_player, "Da Monitorare"] = "X" if da_monitorare else ""
                                df.loc[selected_player, "Presentato a Miniero"] = "X" if presentato_miniero else ""
                                df.loc[selected_player, "Note Danilo/Antonio"] = note_danilo
                                df.loc[selected_player, "Note Alessio/Fabrizio"] = note_alessio
                                df.loc[selected_player, "Risposta Miniero"] = risposta_miniero
                                df.loc[selected_player, "Livello 1"] = "X" if livello_1 else ""
                                df.loc[selected_player, "Livello 2"] = "X" if livello_2 else ""
                                df.loc[selected_player, "Livello 1 Prospettiva"] = "X" if livello_1_prospettiva else ""
                                df.loc[selected_player, "Link Transfermarkt"] = link_transfermarkt
                                
                                save_data(df)
                                st.success("✅ Modifiche salvate con successo!")
                            else:
                                st.error("❌ Nome e Squadra sono campi obbligatori!")
                    
                    with col_delete:
                        if st.form_submit_button("🗑️ Elimina Giocatore", type="secondary"):
                            # FIX: Conferma eliminazione più robusta
                            if st.session_state.get("confirm_delete", False):
                                df_updated = df.drop(selected_player).reset_index(drop=True)
                                save_data(df_updated)
                                st.session_state.selected_player_index = 0
                                if "confirm_delete" in st.session_state:
                                    del st.session_state.confirm_delete
                                st.success("✅ Giocatore eliminato!")
                                keep_session_alive()
                                st.rerun()
                            else:
                                st.session_state.confirm_delete = True
                                st.warning("⚠️ Clicca di nuovo per confermare l'eliminazione!")
        else:
            st.info("Nessun giocatore disponibile per la modifica.")

    # Ricerca
    with selected_tab[3]:
        st.header("Ricerca e Filtri")
        
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                search_name = st.text_input("🔍 Cerca per Nome")
                
            with col2:
                filter_squad = st.multiselect("Filtra per Squadra", options=df["Squadra"].unique())
                
            with col3:
                filter_role = st.multiselect("Filtra per Ruolo", options=df["Ruolo"].unique())
            
            # Applica filtri
            filtered_df = df.copy()
            
            if search_name:
                filtered_df = filtered_df[filtered_df["Nome Giocatore"].str.contains(search_name, case=False, na=False)]
            
            if filter_squad:
                filtered_df = filtered_df[filtered_df["Squadra"].isin(filter_squad)]
                
            if filter_role:
                filtered_df = filtered_df[filtered_df["Ruolo"].isin(filter_role)]
            
            st.subheader(f"Risultati ({len(filtered_df)} giocatori)")
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.info("Nessun dato disponibile per la ricerca.")

if __name__ == "__main__":
    main()
