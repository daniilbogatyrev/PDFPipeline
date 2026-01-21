import streamlit as st
import pandas as pd
import json
from core.orchestrator import DocumentOrchestrator

# Konfiguration
st.set_page_config(page_title="DocIntel Lab", layout="wide", page_icon="🔬")

# Custom CSS für Metriken (optional, macht es etwas kompakter)
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_orchestrator():
    return DocumentOrchestrator()

orch = get_orchestrator()

# --- Header ---
st.title("🔬 Scientific Document Intelligence")
st.markdown("""
**Pipeline-Status:** `Identifier` (Magika) → `Inspector` (PyMuPDF) → `Analyzer` (Heuristics)  
Lade Dokumente hoch, um eine vollständige strukturelle Analyse und Qualitätsprüfung durchzuführen.
""")

uploaded_files = st.file_uploader("Upload Files (PDF, Images, etc.)", accept_multiple_files=True)

if uploaded_files:
    all_results = []
    
    # Container für die Analyse-Ergebnisse
    st.divider()
    st.subheader(f"📑 Analyse-Ergebnisse ({len(uploaded_files)} Dateien)")

    for uploaded_file in uploaded_files:
        # 1. Pipeline ausführen
        file_bytes = uploaded_file.getvalue()
        result = orch.run_pipeline(file_bytes, uploaded_file.name)
        all_results.append(result)

        # Daten sicher extrahieren (mit Defaults)
        pdf_details = result.get("pdf_details") or {}
        layout_stats = result.get("layout_stats") or {}
        
        # 2. UI Rendering pro File
        with st.expander(f"📄 **{result['filename']}** ({result['format'].upper()})", expanded=True):
            
            # A. Top Level Info & Reasoning
            c1, c2 = st.columns([3, 1])
            with c1:
                # Dynamische Farbe für den Typ
                sub_type = pdf_details.get("sub_type", "N/A")
                if sub_type == "NATIVE":
                    badge_color = "green"
                elif sub_type == "SCANNED":
                    badge_color = "orange"
                elif "VECTOR" in sub_type:
                    badge_color = "blue"
                else:
                    badge_color = "gray"
                
                st.markdown(f"**Typ:** :{badge_color}[{sub_type}] | **MIME:** `{result['mime']}`")
                st.info(f"💡 **System-Reasoning:** {result['reasoning']}")
            
            with c2:
                conf = result['confidence']
                st.metric("Modell-Konfidenz", f"{conf:.1%}", help="Wie sicher ist Magika beim Dateityp?")

            # B. Detail-Metriken (Nur wenn Layout-Daten da sind)
            if layout_stats:
                st.markdown("---")
                m1, m2, m3, m4 = st.columns(4)
                
                # Spalte 1: Seiten & Text
                pages = pdf_details.get("pages", 0)
                text_cov = pdf_details.get("text_coverage_pct", 0)
                m1.metric("Seiten", pages)
                m1.caption(f"📝 Text-Dichte: **{text_cov:.0f} chars/page**")

                # Spalte 2: Struktur
                tables = layout_stats.get("tables", 0)
                m2.metric("Tabellen", tables, help="Erkannte Tabellenstrukturen")
                
                # Spalte 3: Bilder (Advanced View)
                u_imgs = layout_stats.get("images", 0)
                t_imgs = layout_stats.get("images_total", 0)
                # Nutzung von 'delta' für den Vergleich Unique vs Total
                m3.metric(
                    "Bilder (Unique)", 
                    u_imgs, 
                    delta=f"Total: {t_imgs} Objekte",
                    delta_color="off",
                    help="Unique = Dedupliziert (z.B. Logos entfernt). Total = Alle Bild-Referenzen."
                )

                # Spalte 4: Inhalt & Mathe
                paras = layout_stats.get("paragraphs", 0)
                math = layout_stats.get("math_formulas", 0)
                m4.metric("Text-Blöcke", paras)
                if math > 0:
                    m4.caption(f"🧮 Mathe-Inhalt: **Hoch** (~{math})")
                else:
                    m4.caption("🧮 Mathe-Inhalt: Niedrig")

            # C. Raw Data View (für Debugging)
            with st.expander("🛠️ Rohe JSON-Daten ansehen"):
                st.json(result)

    # --- Globaler Export Bereich ---
    if all_results:
        st.divider()
        st.subheader("📊 Dataset Export")
        
        # Flattening der Daten für sauberen CSV Export
        flat_data = []
        for r in all_results:
            # Safe Access Helpers
            pdf = r.get("pdf_details") or {}
            lay = r.get("layout_stats") or {}
            
            row = {
                "Filename": r["filename"],
                "Format": r["format"],
                "Sub-Type": pdf.get("sub_type", "N/A"),
                "Confidence": r["confidence"],
                "Pages": pdf.get("pages", 0),
                "Text_Coverage_Avg": pdf.get("text_coverage_pct", 0),
                "Total_Text": "",
                "Tables": lay.get("tables", 0),
                "Images_Unique": lay.get("images", 0),
                "Images_Total": lay.get("images_total", 0),
                "Paragraphs": lay.get("paragraphs", 0),
                "Math_Score": lay.get("math_formulas", 0),
                "Reasoning": r["reasoning"]
            }
            flat_data.append(row)
        
        df = pd.DataFrame(flat_data)
        
        # Vorschau
        st.dataframe(df, use_container_width=True)
        
        # Download Button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Als CSV herunterladen",
            data=csv,
            file_name="doc_intel_export.csv",
            mime="text/csv",
        )