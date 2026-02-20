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

USERS = {
    "admin": hash_password("admin123"),
    "scout": hash_password("scout123"),
    "manager": hash_password("manager123")
}

def authenticate(username, password):
    return username in USERS and USERS[username] == hash_password(password)

def create_auth_token(username):
    timestamp = str(int(time.time()))
    raw_token = f"{username}:{timestamp}:{hash_password(username + timestamp)}"
    return base64.b64encode(raw_token.encode()).decode()

def validate_auth_token(token):
    try:
        decoded = base64.b64decode(token.encode()).decode()
        parts = decoded.split(':')
        if len(parts) != 3:
            return None
        username, timestamp, token_hash = parts
        if username not in USERS:
            return None
        current_time = int(time.time())
        token_time = int(timestamp)
        if current_time - token_time > 86400:
            return None
        expected_hash = hash_password(username + timestamp)
        if token_hash != expected_hash:
            return None
        return username
    except:
        return None

def set_auth_url(username):
    token = create_auth_token(username)
    st.query_params.update({"auth": token})

def clear_auth_url():
    if "auth" in st.query_params:
        del st.query_params["auth"]

def check_url_auth():
    if "auth" in st.query_params:
        token = st.query_params["auth"]
        username = validate_auth_token(token)
        if username:
            return username
    return None

def initialize_session_state():
    url_username = check_url_auth()
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = bool(url_username)
    if "username" not in st.session_state:
        st.session_state.username = url_username or ""
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

def keep_session_alive():
    current_time = time.time()
    st.session_state.last_activity = current_time
    if "authenticated" in st.session_state and st.session_state.authenticated:
        st.session_state.prevent_reset = True
        if st.session_state.username and "auth" not in st.query_params:
            set_auth_url(st.session_state.username)

@st.cache_resource
def init_gsheet():
    try:
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
                st.error("❌ Foglio Google Sheets non trovato.")
                return None
            except gspread.exceptions.APIError as api_error:
                st.error(f"❌ Errore API Google Sheets: {str(api_error)}")
                return None
        else:
            st.warning("⚠️ Credenziali Google Sheets non configurate. Modalità demo attiva.")
            return None
    except Exception as e:
        st.error(f"Errore connessione Google Sheets: {str(e)}")
        return None

@st.cache_data(ttl=60, show_spinner="Caricamento dati...")
def load_data(_session_id=None):
    sheet = init_gsheet()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)

            new_columns = {
                "Numero Visione Partite": 0,
                "Livello 1": "",
                "Livello 2": "",
                "Livello 1 Prospettiva": "",
                "Link Transfermarkt": "",
                "Data inserimento in piattaforma": "",
                "Data ultima visione": "",
                "Data presentazione a Miniero": "",
                # NUOVI CAMPI
                "Monitoraggio Miniero": "",
                "In Scadenza": "",
                "Nazionalità": "Comunitario"
            }

            if len(df) > 0:
                for col_name, default_value in new_columns.items():
                    if col_name not in df.columns:
                        df[col_name] = default_value

            if len(df) > 0:
                rows_info = f"Righe utilizzate: {len(df)+1}/10,000,000"
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
                    "Livello 1 Prospettiva", "Link Transfermarkt",
                    "Monitoraggio Miniero", "In Scadenza", "Nazionalità"
                ]
                sheet.insert_row(headers, 1)
                return pd.DataFrame(columns=headers)
            except Exception as header_error:
                st.error(f"Errore inizializzazione foglio: {str(header_error)}")
                return pd.DataFrame()
    else:
        sample_data = {
            "Nome Giocatore": ["Mario Rossi", "Luca Bianchi", "Ahmed Ben Ali", "Carlos Gomez"],
            "Squadra": ["Juventus", "Milan", "Napoli", "Roma"],
            "Età": [25, 28, 22, 30],
            "Ruolo": ["Centrocampista", "Attaccante", "Difensore Centrale", "Ala Destra"],
            "Valore di Mercato": ["15M€", "20M€", "8M€", "5M€"],
            "Procuratore": ["Raiola", "Mendes", "N/A", "N/A"],
            "Altezza": [180, 175, 185, 178],
            "Piede": ["Destro", "Sinistro", "Destro", "Destro"],
            "Convocazioni": [45, 52, 30, 20],
            "Partite Giocate": [38, 41, 25, 18],
            "Gol": [8, 15, 1, 3],
            "Assist": [12, 7, 3, 5],
            "Minuti Giocati": [3200, 3650, 2100, 1400],
            "Data Inizio Contratto": ["2022-07-01", "2021-08-15", "2023-01-01", "2020-06-01"],
            "Data Fine Contratto": ["2025-06-30", "2024-07-31", "2026-06-30", "2024-12-31"],
            "Numero Visione Partite": [5, 8, 2, 3],
            "Data inserimento in piattaforma": ["2024-01-15", "2024-02-20", "2024-03-01", "2024-03-10"],
            "Data ultima visione": ["2024-03-10", "2024-03-25", "2024-03-15", "2024-03-20"],
            "Data presentazione a Miniero": ["2024-02-01", "", "", ""],
            "Da Monitorare": ["X", "X", "", ""],
            "Note Danilo/Antonio": ["Buon potenziale", "Ottimo in zona gol", "Da seguire", ""],
            "Note Alessio/Fabrizio": ["Da seguire", "Pronto per il salto", "", ""],
            "Presentato a Miniero": ["X", "", "", ""],
            "Risposta Miniero": ["Interessante", "", "", ""],
            "Livello 1": ["X", "", "", ""],
            "Livello 2": ["", "X", "", ""],
            "Livello 1 Prospettiva": ["", "X", "", ""],
            "Link Transfermarkt": [
                "https://www.transfermarkt.it/mario-rossi/profil/spieler/123456",
                "https://www.transfermarkt.it/luca-bianchi/profil/spieler/789012",
                "", ""
            ],
            # NUOVI CAMPI
            "Monitoraggio Miniero": ["", "X", "", ""],
            "In Scadenza": ["X", "X", "", ""],
            "Nazionalità": ["Comunitario", "Comunitario", "Extracomunitario", "Extracomunitario"]
        }
        return pd.DataFrame(sample_data)

def save_data(df):
    sheet = init_gsheet()
    if sheet:
        try:
            sheet.clear()
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            st.success("✅ Dati salvati con successo!")
            load_data.clear()
            rows_info = f"Righe utilizzate: {len(df)+1}/10,000,000"
            st.session_state.rows_info = rows_info
        except Exception as e:
            st.error(f"❌ Errore nel salvataggio: {str(e)}")
    else:
        st.info("💾 Modalità demo - i dati non vengono salvati permanentemente")

def safe_date_convert(date_str):
    try:
        if isinstance(date_str, str) and date_str:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        return date.today()
    except:
        return date.today()

def safe_int_convert(value, default=0):
    try:
        if pd.isna(value) or value == '' or value is None:
            return default
        return int(float(str(value)))
    except (ValueError, TypeError):
        return default

def handle_logout():
    clear_auth_url()
    keys_to_keep = ["session_id"]
    keys_to_remove = [key for key in st.session_state.keys() if key not in keys_to_keep]
    for key in keys_to_remove:
        del st.session_state[key]
    initialize_session_state()
    st.rerun()

# ─────────────────────────────────────────────
# FUNZIONI PER LA COLORAZIONE DELLE TABELLE
# ─────────────────────────────────────────────

# Colori per le righe (priorità: Presentato > Monitoraggio Miniero > In corso monitoraggio)
ROW_COLOR_PRESENTATO     = "#c8f7c5"   # verde chiaro
ROW_COLOR_MON_MINIERO    = "#f7c5c5"   # rosso chiaro
ROW_COLOR_MONITORAGGIO   = "#fff9c4"   # giallo chiaro
ROW_COLOR_DEFAULT        = ""          # nessun colore

# Colori per le celle specifiche
CELL_COLOR_SCADENZA       = "#ffe0b2"  # arancione chiaro
CELL_COLOR_COMUNITARIO    = "#bbdefb"  # blu chiaro
CELL_COLOR_EXTRACOMUNIT   = "#e1bee7"  # viola chiaro


def get_row_color(row):
    """Restituisce il colore di sfondo per l'intera riga in base alla priorità."""
    if row.get("Presentato a Miniero", "") == "X":
        return ROW_COLOR_PRESENTATO
    if row.get("Monitoraggio Miniero", "") == "X":
        return ROW_COLOR_MON_MINIERO
    if row.get("Da Monitorare", "") == "X" and row.get("Presentato a Miniero", "") != "X":
        return ROW_COLOR_MONITORAGGIO
    return ROW_COLOR_DEFAULT


def style_table(df_display, df_source, cell_col_scadenza=None, cell_col_nazionalita=None):
    """
    Applica Pandas Styler al dataframe da visualizzare.
    - df_display: dataframe con le colonne da mostrare
    - df_source:  dataframe originale con tutti i flag (stesso indice)
    - cell_col_scadenza:   nome della colonna in df_display per "In Scadenza"
    - cell_col_nazionalita: nome della colonna in df_display per "Nazionalità"
    """

    # Costruiamo una matrice di stili (righe x colonne) inizializzata vuota
    n_rows = len(df_display)
    n_cols = len(df_display.columns)
    styles = pd.DataFrame("", index=df_display.index, columns=df_display.columns)

    for i in df_display.index:
        # Colore riga
        row_color = get_row_color(df_source.loc[i])
        if row_color:
            styles.loc[i, :] = f"background-color: {row_color}"

        # Colore cella "In Scadenza"
        if cell_col_scadenza and cell_col_scadenza in df_display.columns:
            if str(df_source.loc[i, "In Scadenza"]) == "X":
                styles.loc[i, cell_col_scadenza] = f"background-color: {CELL_COLOR_SCADENZA}; font-weight: bold"

        # Colore cella "Nazionalità"
        if cell_col_nazionalita and cell_col_nazionalita in df_display.columns:
            nazionalita = str(df_source.loc[i, "Nazionalità"])
            if nazionalita == "Comunitario":
                styles.loc[i, cell_col_nazionalita] = f"background-color: {CELL_COLOR_COMUNITARIO}"
            elif nazionalita == "Extracomunitario":
                styles.loc[i, cell_col_nazionalita] = f"background-color: {CELL_COLOR_EXTRACOMUNIT}"

    return df_display.style.apply(lambda _: styles, axis=None)


def show_legend():
    """Mostra una legenda compatta con i colori usati."""
    st.markdown("""
    <div style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:12px; font-size:13px;">
        <span style="background:{p}; padding:3px 10px; border-radius:4px;">🟢 Presentato a Miniero</span>
        <span style="background:{m}; padding:3px 10px; border-radius:4px;">🔴 Monitoraggio Miniero</span>
        <span style="background:{mo}; padding:3px 10px; border-radius:4px;">🟡 In corso monitoraggio</span>
        <span style="background:{s}; padding:3px 10px; border-radius:4px;">🟠 In scadenza (cella)</span>
        <span style="background:{c}; padding:3px 10px; border-radius:4px;">🔵 Comunitario (cella)</span>
        <span style="background:{e}; padding:3px 10px; border-radius:4px;">🟣 Extracomunitario (cella)</span>
    </div>
    """.format(
        p=ROW_COLOR_PRESENTATO,
        m=ROW_COLOR_MON_MINIERO,
        mo=ROW_COLOR_MONITORAGGIO,
        s=CELL_COLOR_SCADENZA,
        c=CELL_COLOR_COMUNITARIO,
        e=CELL_COLOR_EXTRACOMUNIT
    ), unsafe_allow_html=True)


# ─────────────────────────────────────────────
# APP PRINCIPALE
# ─────────────────────────────────────────────

def main():
    initialize_session_state()
    keep_session_alive()

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
                        set_auth_url(username)
                        keep_session_alive()
                        st.success("✅ Accesso effettuato!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Credenziali non valide")
        st.info("""
        **Credenziali demo:**
        - Username: admin, Password: admin123
        - Username: scout, Password: scout123
        - Username: manager, Password: manager123
        """)
        return

    keep_session_alive()

    st.title("⚽ Gestione Giocatori di Calcio")

    with st.sidebar:
        st.write(f"👤 Utente: {st.session_state.username}")
        st.write(f"🔗 Sessione: {st.session_state.session_id[:8]}...")
        if st.button("🚪 Logout", key="logout_btn"):
            handle_logout()
        if "rows_info" in st.session_state:
            st.info(st.session_state.rows_info)
        st.success("🟢 Sessione attiva")
        if st.button("🔄 Aggiorna Dati", key="refresh_data"):
            load_data.clear()
            st.rerun()

    df = load_data(_session_id=st.session_state.session_id)

    tab_names = ["📊 Dashboard", "➕ Aggiungi Giocatore", "✏️ Modifica Dati", "🔍 Ricerca"]
    selected_tab = st.tabs(tab_names)

    # ─── DASHBOARD ───────────────────────────────────────────────────────────
    with selected_tab[0]:
        st.header("Dashboard Giocatori")

        if not df.empty:
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

            # Filtri
            st.subheader("🔍 Filtri di Ricerca")
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                search_name_dash = st.text_input("🔍 Cerca per Nome", key="search_dash")
            with col_s2:
                filter_squad_dash = st.multiselect("Filtra per Squadra", options=df["Squadra"].unique(), key="squad_dash")
            with col_s3:
                filter_role_dash = st.multiselect("Filtra per Ruolo", options=df["Ruolo"].unique(), key="role_dash")

            filtered_df = df.copy()
            if search_name_dash:
                filtered_df = filtered_df[filtered_df["Nome Giocatore"].str.contains(search_name_dash, case=False, na=False)]
            if filter_squad_dash:
                filtered_df = filtered_df[filtered_df["Squadra"].isin(filter_squad_dash)]
            if filter_role_dash:
                filtered_df = filtered_df[filtered_df["Ruolo"].isin(filter_role_dash)]

            # Inverti ordine (ultimi inseriti prima)
            filtered_df = filtered_df.iloc[::-1].reset_index(drop=True)

            st.info(f"📊 Visualizzati **{len(filtered_df)}** giocatori su {len(df)} totali")

            # Legenda colori
            show_legend()

            st.divider()

            # ── ANAGRAFICA ──────────────────────────────────────────────────
            st.subheader("👤 Anagrafica Giocatore")

            df_anagrafica_src = filtered_df.copy()
            if "Da Monitorare" in df_anagrafica_src.columns:
                df_anagrafica_src["🔔 Monitor"] = df_anagrafica_src["Da Monitorare"].apply(
                    lambda x: "⭐ SI" if x == "X" else ""
                )

            anagrafica_cols = [
                "🔔 Monitor", "Nome Giocatore", "Livello 1", "Livello 2", "Livello 1 Prospettiva",
                "Squadra", "Età", "Ruolo", "Valore di Mercato", "Nazionalità",
                "Procuratore", "Altezza", "Piede", "Convocazioni", "Partite Giocate",
                "Gol", "Assist", "Minuti Giocati", "Data Inizio Contratto",
                "Data Fine Contratto", "In Scadenza", "Link Transfermarkt"
            ]
            df_ana_display = df_anagrafica_src[[c for c in anagrafica_cols if c in df_anagrafica_src.columns]].reset_index(drop=True)
            df_ana_source  = filtered_df.reset_index(drop=True)

            styled_ana = style_table(
                df_ana_display, df_ana_source,
                cell_col_scadenza="In Scadenza",
                cell_col_nazionalita="Nazionalità"
            )
            st.dataframe(styled_ana, use_container_width=True, hide_index=True, height=400)

            st.divider()

            # ── NOSTRA ANALISI ───────────────────────────────────────────────
            st.subheader("📊 Nostra Analisi")

            df_analisi_src = filtered_df.copy()
            if "Da Monitorare" in df_analisi_src.columns:
                df_analisi_src["Da Monitorare Display"] = df_analisi_src["Da Monitorare"].apply(
                    lambda x: "⭐ SI" if x == "X" else "No"
                )

            analisi_cols = [
                "Nome Giocatore", "Livello 1", "Livello 2", "Livello 1 Prospettiva",
                "Squadra", "Da Monitorare Display", "Monitoraggio Miniero",
                "Presentato a Miniero", "Risposta Miniero", "Numero Visione Partite",
                "Data inserimento in piattaforma", "Data ultima visione",
                "Data presentazione a Miniero"
            ]
            df_ana2_display = df_analisi_src[[c for c in analisi_cols if c in df_analisi_src.columns]].reset_index(drop=True)
            df_ana2_source  = filtered_df.reset_index(drop=True)

            styled_ana2 = style_table(
                df_ana2_display, df_ana2_source,
                cell_col_scadenza=None,
                cell_col_nazionalita=None
            )
            st.dataframe(styled_ana2, use_container_width=True, hide_index=True, height=400)

            st.divider()

            # ── NOSTRE NOTE ──────────────────────────────────────────────────
            st.subheader("📝 Nostre Note")

            df_note_src = filtered_df.copy()
            if "Da Monitorare" in df_note_src.columns:
                df_note_src["🔔 Monitor"] = df_note_src["Da Monitorare"].apply(
                    lambda x: "⭐ SI" if x == "X" else ""
                )

            note_cols = [
                "🔔 Monitor", "Nome Giocatore", "Livello 1", "Livello 2", "Livello 1 Prospettiva",
                "Squadra", "Note Danilo/Antonio", "Note Alessio/Fabrizio"
            ]
            df_note_display = df_note_src[[c for c in note_cols if c in df_note_src.columns]].reset_index(drop=True)
            df_note_source  = filtered_df.reset_index(drop=True)

            styled_note = style_table(
                df_note_display, df_note_source,
                cell_col_scadenza=None,
                cell_col_nazionalita=None
            )
            st.dataframe(styled_note, use_container_width=True, hide_index=True, height=400)

        else:
            st.info("Nessun giocatore nel database. Inizia aggiungendo un nuovo giocatore!")

    # ─── AGGIUNGI GIOCATORE ──────────────────────────────────────────────────
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

                st.write("")
                col_liv1, col_liv2, col_liv3 = st.columns(3)
                with col_liv1:
                    livello_1 = st.checkbox("Livello 1")
                with col_liv2:
                    livello_2 = st.checkbox("Livello 2")
                with col_liv3:
                    livello_1_prospettiva = st.checkbox("Livello 1 Prospettiva")

                st.write("")
                st.markdown("**Classificazione**")
                nazionalita = st.selectbox("Nazionalità", ["Comunitario", "Extracomunitario"])

            with col2:
                convocazioni = st.number_input("Convocazioni", min_value=0, value=0)
                partite = st.number_input("Partite Giocate", min_value=0, value=0)
                gol = st.number_input("Gol", min_value=0, value=0)
                assist = st.number_input("Assist", min_value=0, value=0)
                minuti = st.number_input("Minuti Giocati", min_value=0, value=0)

                inizio_contratto = st.date_input("Data Inizio Contratto")
                fine_contratto = st.date_input("Data Fine Contratto")

                numero_visione = st.number_input("Numero Visione Partite", min_value=0, value=0)

                data_inserimento = st.date_input("📅 Data inserimento in piattaforma", value=date.today())
                data_ultima_visione = st.date_input("👁️ Data ultima visione")
                data_presentazione_miniero = st.date_input("🎯 Data presentazione a Miniero")

                da_monitorare = st.checkbox("Da Monitorare")
                monitoraggio_miniero = st.checkbox("🔴 Monitoraggio richiesto da Miniero")
                in_scadenza = st.checkbox("🟠 In Scadenza")
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
                        "Monitoraggio Miniero": "X" if monitoraggio_miniero else "",
                        "In Scadenza": "X" if in_scadenza else "",
                        "Nazionalità": nazionalita,
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
                    st.info(f"✅ Giocatore aggiunto! Totale: {len(df_new)}")
                else:
                    st.error("❌ Nome e Squadra sono campi obbligatori!")

    # ─── MODIFICA DATI ───────────────────────────────────────────────────────
    with selected_tab[2]:
        st.header("Modifica Dati Esistenti")

        if not df.empty:
            if st.session_state.selected_player_index >= len(df):
                st.session_state.selected_player_index = 0

            def on_player_change():
                if "player_selector" in st.session_state:
                    st.session_state.selected_player_index = st.session_state.player_selector
                keep_session_alive()

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

                        st.write("")
                        col_liv1, col_liv2, col_liv3 = st.columns(3)
                        with col_liv1:
                            livello_1 = st.checkbox("Livello 1", value=player_data.get("Livello 1") == "X")
                        with col_liv2:
                            livello_2 = st.checkbox("Livello 2", value=player_data.get("Livello 2") == "X")
                        with col_liv3:
                            livello_1_prospettiva = st.checkbox("Livello 1 Prospettiva",
                                                                value=player_data.get("Livello 1 Prospettiva") == "X")

                        st.write("")
                        st.markdown("**Classificazione**")
                        naz_options = ["Comunitario", "Extracomunitario"]
                        current_naz = str(player_data.get("Nazionalità", "Comunitario"))
                        naz_index = naz_options.index(current_naz) if current_naz in naz_options else 0
                        nazionalita = st.selectbox("Nazionalità", naz_options, index=naz_index)

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

                        data_inserimento = st.date_input("📅 Data inserimento in piattaforma",
                                                         value=safe_date_convert(player_data.get("Data inserimento in piattaforma")))
                        data_ultima_visione = st.date_input("👁️ Data ultima visione",
                                                            value=safe_date_convert(player_data.get("Data ultima visione")))
                        data_presentazione_miniero = st.date_input("🎯 Data presentazione a Miniero",
                                                                   value=safe_date_convert(player_data.get("Data presentazione a Miniero")))

                        da_monitorare = st.checkbox("Da Monitorare", value=player_data.get("Da Monitorare") == "X")
                        monitoraggio_miniero = st.checkbox("🔴 Monitoraggio richiesto da Miniero",
                                                           value=player_data.get("Monitoraggio Miniero") == "X")
                        in_scadenza = st.checkbox("🟠 In Scadenza",
                                                  value=player_data.get("In Scadenza") == "X")
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
                                df.loc[selected_player, "Monitoraggio Miniero"] = "X" if monitoraggio_miniero else ""
                                df.loc[selected_player, "In Scadenza"] = "X" if in_scadenza else ""
                                df.loc[selected_player, "Nazionalità"] = nazionalita
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

    # ─── RICERCA ─────────────────────────────────────────────────────────────
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

            filtered_df_r = df.copy()
            if search_name:
                filtered_df_r = filtered_df_r[filtered_df_r["Nome Giocatore"].str.contains(search_name, case=False, na=False)]
            if filter_squad:
                filtered_df_r = filtered_df_r[filtered_df_r["Squadra"].isin(filter_squad)]
            if filter_role:
                filtered_df_r = filtered_df_r[filtered_df_r["Ruolo"].isin(filter_role)]

            st.subheader(f"Risultati ({len(filtered_df_r)} giocatori)")

            df_search = filtered_df_r.copy()
            if "Da Monitorare" in df_search.columns:
                df_search["Da Monitorare"] = df_search["Da Monitorare"].apply(
                    lambda x: "⭐ SI" if x == "X" else "No"
                )

            st.dataframe(df_search, use_container_width=True)
        else:
            st.info("Nessun dato disponibile per la ricerca.")


if __name__ == "__main__":
    main()
