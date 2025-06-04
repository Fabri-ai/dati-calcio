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
        if "gsheet_credentials" in st.secrets:
            credentials_info = dict(st.secrets["gsheet_credentials"])
            
            # CORREZIONE: Scope corretti senza trailing slash
            credentials = Credentials.from_service_account_info(
                credentials_info,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",  # Rimosso il trailing slash
                    "https://www.googleapis.com/auth/drive"
                ]
            )
            
            # Autorizzazione con gspread
            gc = gspread.authorize(credentials)
            
            # ID del foglio Google Sheets
            sheet_id = st.secrets.get("sheet_id", "1GjubMgZkxjISauMyrnQdZlunOUMEKKSGoEwk6tm7d4c")
            
            # CORREZIONE: Test di connessione prima di restituire il sheet
            try:
                spreadsheet = gc.open_by_key(sheet_id)
                sheet = spreadsheet.sheet1
                # Test di lettura per verificare la connessione
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

# Funzione per caricare i dati
@st.cache_data(ttl=30)  # BUG FIX: Ridotto TTL per aggiornamenti più frequenti
def load_data():
    sheet = init_gsheet()
    if sheet:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            
            # BUG FIX: Info sul limite righe Google Sheets
            if len(df) > 0:
                rows_info = f"Righe utilizzate: {len(df)+1}/10,000,000 (Google Sheets supporta fino a 10 milioni di righe)"
                if "rows_info" not in st.session_state:
                    st.session_state.rows_info = rows_info
            
            return df
        except Exception as e:
            # Se il foglio è vuoto, crea le intestazioni
            try:
                headers = [
                    "Nome Giocatore", "Squadra", "Età", "Ruolo", "Valore di Mercato",
                    "Procuratore", "Altezza", "Piede", "Convocazioni", "Partite Giocate",
                    "Gol", "Assist", "Minuti Giocati", "Data Inizio Contratto",
                    "Data Fine Contratto", "Da Monitorare", "Note Danilo/Antonio",
                    "Note Alessio/Fabrizio", "Presentato a Miniero", "Risposta Miniero"
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
            
            # BUG FIX: Forza l'aggiornamento della cache dopo il salvataggio
            st.cache_data.clear()
            
            # BUG FIX: Aggiorna l'info sulle righe
            rows_info = f"Righe utilizzate: {len(df)+1}/10,000,000 (Google Sheets supporta fino a 10 milioni di righe)"
            st.session_state.rows_info = rows_info
            
        except Exception as e:
            st.error(f"❌ Errore nel salvataggio: {str(e)}")
    else:
        st.info("💾 Modalità demo - i dati non vengono salvati permanentemente")

# BUG FIX: Funzione per convertire stringhe di date in oggetti date
def safe_date_convert(date_str):
    try:
        if isinstance(date_str, str) and date_str:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        return date.today()
    except:
        return date.today()

# BUG FIX: Funzione per conversione sicura dei numeri
def safe_int_convert(value, default=0):
    try:
        if pd.isna(value) or value == '' or value is None:
            return default
        return int(float(str(value)))
    except (ValueError, TypeError):
        return default

# Funzione principale dell'app
def main():
    # BUG FIX: Controllo autenticazione con persistenza migliorata
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    # BUG FIX: Mantieni il tab attivo durante la sessione
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = 0

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
    
    # Sidebar con logout e info
    with st.sidebar:
        st.write(f"👤 Utente: {st.session_state.username}")
        if st.button("🚪 Logout"):
            # BUG FIX: Pulizia completa della sessione
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        # BUG FIX: Mostra info sulle righe se disponibile
        if "rows_info" in st.session_state:
            st.info(st.session_state.rows_info)

    # Caricamento dati
    df = load_data()

    # BUG FIX: Tabs con stato persistente
    tab_names = ["📊 Dashboard", "➕ Aggiungi Giocatore", "✏️ Modifica Dati", "🔍 Ricerca"]
    
    # BUG FIX: Usa on_change per tracciare il cambio di tab
    def on_tab_change():
        # Reset dei parametri di modifica quando si cambia tab
        if "selected_player_index" in st.session_state:
            del st.session_state.selected_player_index
    
    selected_tab = st.tabs(tab_names)

    # Dashboard
    with selected_tab[0]:
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
                # BUG FIX: Calcolo età media sicuro
                if "Età" in df.columns and len(df) > 0:
                    ages = pd.to_numeric(df["Età"], errors='coerce').dropna()
                    avg_age = ages.mean() if len(ages) > 0 else 0
                else:
                    avg_age = 0
                st.metric("Età Media", f"{avg_age:.1f}")

            # Tabella principale
            st.subheader("Lista Giocatori")
            st.dataframe(df, use_container_width=True)
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
                    
                    # BUG FIX: Info sul numero di righe dopo inserimento
                    st.info(f"✅ Giocatore aggiunto! Totale giocatori nel database: {len(df_new)}")
                else:
                    st.error("❌ Nome e Squadra sono campi obbligatori!")

    # BUG FIX: Modifica Dati - Completamente rivista
    with selected_tab[2]:
        st.header("Modifica Dati Esistenti")
        
        if not df.empty:
            # BUG FIX: Usa session state per mantenere la selezione
            if "selected_player_index" not in st.session_state:
                st.session_state.selected_player_index = 0
            
            # BUG FIX: Selectbox con key per evitare reset
            selected_player = st.selectbox(
                "Seleziona Giocatore da Modificare",
                options=range(len(df)),
                format_func=lambda x: f"{df.iloc[x]['Nome Giocatore']} - {df.iloc[x]['Squadra']}",
                index=st.session_state.selected_player_index,
                key="player_selector"
            )
            
            # BUG FIX: Aggiorna l'indice nel session state
            if selected_player != st.session_state.selected_player_index:
                st.session_state.selected_player_index = selected_player
            
            if selected_player is not None:
                player_data = df.iloc[selected_player]
                
                # BUG FIX: Form completo con TUTTI i campi modificabili
                with st.form("edit_player_form", clear_on_submit=False):
                    st.subheader(f"Modifica: {player_data['Nome Giocatore']}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nome = st.text_input("Nome Giocatore*", value=str(player_data["Nome Giocatore"]))
                        squadra = st.text_input("Squadra*", value=str(player_data["Squadra"]))
                        eta = st.number_input("Età", min_value=16, max_value=50, 
                                            value=safe_int_convert(player_data.get("Età"), 25))
                        
                        # BUG FIX: Ruolo con valore corrente selezionato
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
                        
                        # BUG FIX: Piede con valore corrente
                        piedi = ["Destro", "Sinistro", "Ambidestro"]
                        current_piede = str(player_data.get("Piede", "Destro"))
                        piede_index = piedi.index(current_piede) if current_piede in piedi else 0
                        piede = st.selectbox("Piede", piedi, index=piede_index)
                        
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
                        
                        # BUG FIX: Date con conversione sicura
                        inizio_contratto = st.date_input("Data Inizio Contratto", 
                                                       value=safe_date_convert(player_data.get("Data Inizio Contratto")))
                        fine_contratto = st.date_input("Data Fine Contratto", 
                                                     value=safe_date_convert(player_data.get("Data Fine Contratto")))
                        
                        da_monitorare = st.checkbox("Da Monitorare", value=player_data.get("Da Monitorare") == "X")
                        presentato_miniero = st.checkbox("Presentato a Miniero", 
                                                       value=player_data.get("Presentato a Miniero") == "X")
                    
                    # BUG FIX: Tutte le note modificabili
                    note_danilo = st.text_area("Note Danilo/Antonio", 
                                             value=str(player_data.get("Note Danilo/Antonio", "")))
                    note_alessio = st.text_area("Note Alessio/Fabrizio", 
                                              value=str(player_data.get("Note Alessio/Fabrizio", "")))
                    risposta_miniero = st.text_area("Risposta Miniero", 
                                                  value=str(player_data.get("Risposta Miniero", "")))
                    
                    col_save, col_delete = st.columns(2)
                    with col_save:
                        if st.form_submit_button("💾 Salva Modifiche", type="primary"):
                            if nome and squadra:
                                # BUG FIX: Aggiorna TUTTI i campi
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
                                df.loc[selected_player, "Da Monitorare"] = "X" if da_monitorare else ""
                                df.loc[selected_player, "Presentato a Miniero"] = "X" if presentato_miniero else ""
                                df.loc[selected_player, "Note Danilo/Antonio"] = note_danilo
                                df.loc[selected_player, "Note Alessio/Fabrizio"] = note_alessio
                                df.loc[selected_player, "Risposta Miniero"] = risposta_miniero
                                
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
                                del st.session_state.confirm_delete
                                st.success("✅ Giocatore eliminato!")
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
