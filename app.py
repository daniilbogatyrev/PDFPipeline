import streamlit as st
import pandas as pd
from core.identifier import FileIdentifier

st.set_page_config(page_title="Doc Intelligence Lab", layout="wide")

# Modell im Cache halten
@st.cache_resource
def get_identifier():
    return FileIdentifier()

identifier = get_identifier()

st.title("🔬 Phase 1: File Identification")
st.info("In diesem Schritt bestimmen wir rein über die Byte-Struktur den Dateityp.")

uploaded_files = st.file_uploader("Datei hochladen", accept_multiple_files=True)

if uploaded_files:
    results = []
    
    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        
        # NUR Modul 1 aufrufen
        id_data = identifier.identify(file_bytes)
        
        # Daten für die Tabelle sammeln
        results.append({
            "Filename": uploaded_file.name,
            "Detected Type": id_data["label"],
            "MIME Type": id_data["mime"],
            "Group": id_data["group"],
            "Confidence": f"{id_data['score']:.2%}"
        })

    # Ergebnis-Tabelle anzeigen
    st.subheader("Identification Results")
    st.table(pd.DataFrame(results))

    # Logik-Check für uns (unsichtbar für den User oder als Debug)
    for res in results:
        if res["Detected Type"] == "pdf":
            st.success(f"✅ {res['Filename']} ist eine PDF. Bereit für Phase 2 (Inspection).")
        else:
            st.info(f"ℹ️ {res['Filename']} ist kein PDF. Andere Pipeline erforderlich.")