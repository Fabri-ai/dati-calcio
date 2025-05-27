import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import date, datetime
import hashlib

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

# Funzione per inizializzare la connessione a Google Sheets
@st.cache_resource
def init_gsheet():
    try:
        # Configurazione delle credenziali Google Sheets
        # In produzione, carica le credenziali dal file secrets.toml di Streamlit
        if "gsheet_credentials" in st.secrets:
            credentials_info = st.secrets["gsheet_credentials"]
            credentials = Credentials.from_service_account_info(
                credentials_info,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets/",
                    "https://www.googleapis.com/auth/drive"
                ]
            )
            gc = gspread.authorize(credentials)
            
            # ID del foglio Google Sheets (da sostituire con il tuo)
            sheet_id = st.secrets.get("sheet_id", "YOUR_SHEET_ID")
            sheet = gc.open_by_key(sheet_id).sheet1
            return sheet
        else:
            st.warning("⚠️ Credenziali Google Sheets non configurate. Modalità demo attiva.")
            return None
    except Exception as e:
        st.error(f"Errore connessione Google Sheets: {str(e)}")
        return None

# Funzione per caricare i dati
@st.cache_data(ttl=60)
def load_data():
    sheet = init_gsheet()
    if sheet:
        try:
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        except:
            # Se il foglio è vuoto, crea le intestazioni
            headers = [
                "Nome Giocatore", "Squadra", "Età", "Ruolo", "Valore di Mercato",
                "Procuratore", "Altezza", "Piede", "Convocazioni", "Partite Giocate",
                "Gol", "Assist", "Minuti Giocati", "Data Inizio Contratto",
                "Data Fine Contratto", "Da Monitorare", "Note Danilo/Antonio",
                "Note Alessio/Fabrizio", "Presentato a Miniero", "Risposta Miniero"
            ]
            sheet.insert_row(headers, 1)
            return pd.DataFrame(columns=headers)
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
            "Da Monitorare": ["X", ""],
            "Note Danilo/Antonio": ["Buon potenziale", "Ottimo in zona gol"],
            "Note Alessio/Fabrizio": ["Da seguire", "Pronto per il salto"],
            "Presentato a Miniero": ["X", ""],
            "Risposta Miniero": ["Interessante", "Da valutare"]
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
            st.cache_data.clear()
        except Exception as e:
            st.error(f"❌ Errore nel salvataggio: {str(e)}")
    else:
        st.info("💾 Modalità demo - i dati non vengono salvati permanentemente")

# Funzione principale dell'app
def main():
    # Controllo autenticazione
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

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
                        st.success("✅ Accesso effettuato!")
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

    # Interfaccia principale
    st.title("⚽ Gestione Giocatori di Calcio")
    
    # Sidebar con logout
    with st.sidebar:
        st.write(f"👤 Utente: {st.session_state.username}")
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.rerun()

    # Caricamento dati
    df = load_data()

    # Tabs per diverse sezioni
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "➕ Aggiungi Giocatore", "✏️ Modifica Dati", "🔍 Ricerca"])

    with tab1:
        st.header("Dashboard Giocatori")
        
        if not df.empty:
            # Statistiche generali
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
                avg_age = df["Età"].mean() if "Età" in df.columns else 0
                st.metric("Età Media", f"{avg_age:.1f}")

            # Tabella principale
            st.subheader("Lista Giocatori")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Nessun giocatore nel database. Inizia aggiungendo un nuovo giocatore!")

    with tab2:
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
                
            with col2:
                convocazioni = st.number_input("Convocazioni", min_value=0, value=0)
                partite = st.number_input("Partite Giocate", min_value=0, value=0)
                gol = st.number_input("Gol", min_value=0, value=0)
                assist = st.number_input("Assist", min_value=0, value=0)
                minuti = st.number_input("Minuti Giocati", min_value=0, value=0)
                
                inizio_contratto = st.date_input("Data Inizio Contratto")
                fine_contratto = st.date_input("Data Fine Contratto")
                
                da_monitorare = st.checkbox("Da Monitorare")
                presentato_miniero = st.checkbox("Presentato a Miniero")
            
            note_danilo = st.text_area("Note Danilo/Antonio")
            note_alessio = st.text_area("Note Alessio/Fabrizio")
            risposta_miniero = st.text_area("Risposta Miniero")
            
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
                        "Da Monitorare": "X" if da_monitorare else "",
                        "Note Danilo/Antonio": note_danilo,
                        "Note Alessio/Fabrizio": note_alessio,
                        "Presentato a Miniero": "X" if presentato_miniero else "",
                        "Risposta Miniero": risposta_miniero
                    }
                    
                    df_new = pd.concat([df, pd.DataFrame([new_player])], ignore_index=True)
                    save_data(df_new)
                else:
                    st.error("❌ Nome e Squadra sono campi obbligatori!")

    with tab3:
        st.header("Modifica Dati Esistenti")
        
        if not df.empty:
            selected_player = st.selectbox(
                "Seleziona Giocatore da Modificare",
                options=df.index,
                format_func=lambda x: f"{df.iloc[x]['Nome Giocatore']} - {df.iloc[x]['Squadra']}"
            )
            
            if selected_player is not None:
                player_data = df.iloc[selected_player]
                
                with st.form("edit_player_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nome = st.text_input("Nome Giocatore", value=player_data["Nome Giocatore"])
                        squadra = st.text_input("Squadra", value=player_data["Squadra"])
                        eta = st.number_input("Età", min_value=16, max_value=50, value=int(player_data["Età"]))
                        
                    with col2:
                        da_monitorare = st.checkbox("Da Monitorare", value=player_data["Da Monitorare"] == "X")
                        presentato_miniero = st.checkbox("Presentato a Miniero", value=player_data["Presentato a Miniero"] == "X")
                    
                    note_danilo = st.text_area("Note Danilo/Antonio", value=player_data.get("Note Danilo/Antonio", ""))
                    note_alessio = st.text_area("Note Alessio/Fabrizio", value=player_data.get("Note Alessio/Fabrizio", ""))
                    risposta_miniero = st.text_area("Risposta Miniero", value=player_data.get("Risposta Miniero", ""))
                    
                    col_save, col_delete = st.columns(2)
                    with col_save:
                        if st.form_submit_button("💾 Salva Modifiche"):
                            df.loc[selected_player, "Nome Giocatore"] = nome
                            df.loc[selected_player, "Squadra"] = squadra
                            df.loc[selected_player, "Età"] = eta
                            df.loc[selected_player, "Da Monitorare"] = "X" if da_monitorare else ""
                            df.loc[selected_player, "Presentato a Miniero"] = "X" if presentato_miniero else ""
                            df.loc[selected_player, "Note Danilo/Antonio"] = note_danilo
                            df.loc[selected_player, "Note Alessio/Fabrizio"] = note_alessio
                            df.loc[selected_player, "Risposta Miniero"] = risposta_miniero
                            
                            save_data(df)
                    
                    with col_delete:
                        if st.form_submit_button("🗑️ Elimina Giocatore", type="secondary"):
                            df_updated = df.drop(selected_player).reset_index(drop=True)
                            save_data(df_updated)
        else:
            st.info("Nessun giocatore disponibile per la modifica.")

    with tab4:
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
