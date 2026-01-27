"""
DocIntel Lab - Streamlit Application.
Integriert: Analyse (mit Native/Scanned), Ground Truth Editor, Benchmark, Tabellen-Export.
"""

import streamlit as st
import pandas as pd
import json
import io
import zipfile
from typing import List

from core import DocumentOrchestrator, get_available_extractors, TableExporter, create_table_export_summary
from core.extractors import ExtractedTable, get_default_extractor
from benchmark import GroundTruthManifest, DocumentGroundTruth, BenchmarkRunner

# === Konfiguration ===
st.set_page_config(
    page_title="DocIntel Lab",
    layout="wide",
    page_icon="🔬",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.1rem; }
    .table-export-btn { margin: 2px; }
</style>
""", unsafe_allow_html=True)

# === Session State ===
if "manifest" not in st.session_state:
    st.session_state.manifest = GroundTruthManifest()
if "benchmark_result" not in st.session_state:
    st.session_state.benchmark_result = None
if "current_extraction" not in st.session_state:
    st.session_state.current_extraction = None
if "current_pdf_bytes" not in st.session_state:
    st.session_state.current_pdf_bytes = None


# === Cached Resources ===
@st.cache_resource
def get_orchestrator():
    return DocumentOrchestrator()

@st.cache_resource
def get_table_exporter():
    return TableExporter(crop_to_table=False)


# === Helper Functions ===
def create_table_download_buttons(
    tables: List[ExtractedTable],
    pdf_bytes: bytes,
    filename: str,
    container
):
    """Erstellt Download-Buttons für jede Tabelle."""
    exporter = get_table_exporter()
    
    # Filtere nur Haupt-Tabellen (keine Continuations)
    main_tables = [t for t in tables if not t.is_continuation]
    
    if not main_tables:
        container.info("Keine Tabellen zum Exportieren gefunden.")
        return
    
    container.markdown("### 📥 Tabellen exportieren")
    
    # Einzelne Tabellen
    cols = container.columns(min(len(main_tables), 4))
    
    for idx, table in enumerate(main_tables):
        col = cols[idx % len(cols)]
        
        # Button Label
        if table.is_spanning:
            label = f"T{table.table_id} (S.{table.page_range[0]}-{table.page_range[1]})"
        else:
            label = f"T{table.table_id} (S.{table.page_range[0]})"
        
        # Export durchführen
        try:
            exported = exporter.export_table(pdf_bytes, table)
            
            col.download_button(
                label=f"📄 {label}",
                data=exported.pdf_bytes,
                file_name=exported.filename,
                mime="application/pdf",
                key=f"dl_table_{filename}_{table.table_id}",
                use_container_width=True
            )
            col.caption(f"{exported.size_kb:.1f} KB")
        except Exception as e:
            col.error(f"Fehler: {e}")
    
    # Alle als ZIP
    if len(main_tables) > 1:
        container.markdown("---")
        
        try:
            zip_bytes = exporter.export_tables_as_zip(
                pdf_bytes, 
                tables,
                base_filename=filename.replace(".pdf", "")
            )
            
            container.download_button(
                label=f"📦 Alle {len(main_tables)} Tabellen als ZIP",
                data=zip_bytes,
                file_name=f"{filename.replace('.pdf', '')}_tables.zip",
                mime="application/zip",
                key=f"dl_all_tables_{filename}",
                type="primary"
            )
        except Exception as e:
            container.error(f"ZIP-Export fehlgeschlagen: {e}")


def create_selective_table_export(
    tables: List[ExtractedTable],
    pdf_bytes: bytes,
    filename: str,
    container
):
    """Erstellt einen selektiven Export mit Checkboxen."""
    exporter = get_table_exporter()
    main_tables = [t for t in tables if not t.is_continuation]
    
    if not main_tables:
        return
    
    container.markdown("### 🎯 Selektiver Export")
    
    # Checkboxen für Auswahl
    selected_tables = []
    
    cols = container.columns(min(len(main_tables), 4))
    for idx, table in enumerate(main_tables):
        col = cols[idx % len(cols)]
        
        label = f"T{table.table_id}: {table.page_range_str}"
        if col.checkbox(label, key=f"sel_{filename}_{table.table_id}"):
            selected_tables.append(table)
    
    if selected_tables:
        container.markdown(f"**{len(selected_tables)} Tabellen ausgewählt**")
        
        if len(selected_tables) == 1:
            # Einzelner Download
            table = selected_tables[0]
            exported = exporter.export_table(pdf_bytes, table)
            
            container.download_button(
                label=f"📄 Download: {exported.filename}",
                data=exported.pdf_bytes,
                file_name=exported.filename,
                mime="application/pdf",
                key=f"dl_selected_single_{filename}",
                type="primary"
            )
        else:
            # ZIP Download
            zip_bytes = exporter.export_tables_as_zip(
                pdf_bytes,
                selected_tables,
                base_filename=filename.replace(".pdf", "")
            )
            
            container.download_button(
                label=f"📦 Download: {len(selected_tables)} Tabellen als ZIP",
                data=zip_bytes,
                file_name=f"{filename.replace('.pdf', '')}_selected_tables.zip",
                mime="application/zip",
                key=f"dl_selected_zip_{filename}",
                type="primary"
            )


# === Sidebar Navigation ===
st.sidebar.title("🔬 DocIntel Lab")

page = st.sidebar.radio(
    "Navigation",
    ["📄 Analyse", "📥 Tabellen-Export", "🎯 Ground Truth", "📊 Benchmark"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.caption(f"**Ground Truth:** {len(st.session_state.manifest.documents)} Einträge")


# ============================================================
# SEITE 1: ANALYSE
# ============================================================
if page == "📄 Analyse":
    st.title("🔬 Scientific Document Intelligence")
    st.markdown("""
    **Pipeline:** `Identifier` (Magika) → `Inspector` (Native/Scanned) → `Extractor` (Tabellen/Bilder)
    """)
    
    orch = get_orchestrator()
    extractor = get_default_extractor()
    
    uploaded_files = st.file_uploader(
        "PDF Dateien hochladen",
        type=["pdf"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        all_results = []
        
        st.divider()
        st.subheader(f"📑 Analyse-Ergebnisse ({len(uploaded_files)} Dateien)")
        
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.getvalue()
            result = orch.run_pipeline(file_bytes, uploaded_file.name)
            all_results.append(result)
            
            # Speichere für Export-Seite
            extraction_result = extractor.extract(file_bytes, uploaded_file.name)
            
            pdf_details = result.get("pdf_details") or {}
            layout_stats = result.get("layout_stats") or {}
            
            # UI pro Datei
            with st.expander(f"📄 **{result['filename']}** ({result['format'].upper()})", expanded=True):
                
                # Header: Typ & Reasoning
                c1, c2 = st.columns([3, 1])
                with c1:
                    sub_type = pdf_details.get("sub_type", "N/A")
                    colors = {"NATIVE": "green", "SCANNED": "orange", "VECTOR_GRAPHIC": "blue"}
                    badge_color = colors.get(sub_type, "gray")
                    
                    st.markdown(f"**Typ:** :{badge_color}[{sub_type}] | **MIME:** `{result['mime']}`")
                    st.info(f"💡 **Reasoning:** {result['reasoning']}")
                
                with c2:
                    st.metric("Konfidenz", f"{result['confidence']:.1%}")
                
                # Detail-Metriken
                if layout_stats:
                    st.markdown("---")
                    m1, m2, m3, m4 = st.columns(4)
                    
                    m1.metric("Seiten", pdf_details.get("pages", 0))
                    text_cov = pdf_details.get("text_coverage_pct", 0)
                    m1.caption(f"📝 {text_cov:.0f} chars/page")
                    
                    # Tabellen mit Details
                    tables = layout_stats.get("tables", 0)
                    m2.metric("Tabellen", tables)
                    if extraction_result.tables:
                        spanning = extraction_result.spanning_table_count
                        if spanning > 0:
                            m2.caption(f"🔗 {spanning} spanning")
                    
                    # Bilder
                    u_imgs = layout_stats.get("images", 0)
                    t_imgs = layout_stats.get("images_total", 0)
                    m3.metric("Bilder (Unique)", u_imgs, delta=f"Total: {t_imgs}", delta_color="off")
                    
                    # Paragraphen & Mathe
                    paras = layout_stats.get("paragraphs", 0)
                    math = layout_stats.get("math_formulas", 0)
                    m4.metric("Text-Blöcke", paras)
                    m4.caption(f"🧮 Mathe: {'Hoch' if math > 0 else 'Niedrig'}")
                    
                    # Tabellen-Details
                    if extraction_result.tables:
                        st.markdown("---")
                        st.markdown("**📋 Tabellen-Details:**")
                        st.code(extraction_result.get_table_summary())
                        
                        # Schnell-Export Buttons
                        create_table_download_buttons(
                            extraction_result.tables,
                            file_bytes,
                            uploaded_file.name,
                            st
                        )
                    
                    # OCR Hinweis
                    if layout_stats.get("requires_ocr"):
                        st.warning("⚠️ Gescanntes PDF - für Tabellen-/Texterkennung ist OCR erforderlich.")
                
                # ### HIER EINGEFÜGT: Quick-Add Logic ###
                # Check ob bereits in GT vorhanden
                gt = st.session_state.manifest.get(uploaded_file.name)
                
                # Layout für den Button ganz rechts
                col_qa1, col_qa2 = st.columns([3, 1])
                with col_qa2:
                    if not gt:
                        if st.button("➕ Zu GT hinzufügen", key=f"add_{uploaded_file.name}"):
                            st.session_state.manifest.add(DocumentGroundTruth(
                                file_name=uploaded_file.name,
                                table_count=layout_stats.get("tables", 0),
                                image_count=layout_stats.get("images", 0),
                                pages=pdf_details.get("pages", 0) # Korrigiert auf pdf_details
                            ))
                            st.rerun()
                    else:
                        st.caption(f"✓ In GT (T={gt.table_count}, I={gt.image_count})")
                
                # Raw JSON
                with st.expander("🛠️ Rohe JSON-Daten"):
                    st.json(result)

        # ### HIER EINGEFÜGT: Gesamt-Export Tabelle (außerhalb der Schleife) ###
        if all_results:
            st.divider()
            st.subheader("📊 Export")
            
            flat_data = []
            for r in all_results:
                pdf = r.get("pdf_details") or {}
                lay = r.get("layout_stats") or {}
                flat_data.append({
                    "Filename": r["filename"],
                    "Format": r["format"],
                    "Sub-Type": pdf.get("sub_type", "N/A"),
                    "Confidence": r["confidence"],
                    "Pages": pdf.get("pages", 0),
                    "Tables": lay.get("tables", 0),
                    "Images_Unique": lay.get("images", 0),
                    "Images_Total": lay.get("images_total", 0),
                    "Paragraphs": lay.get("paragraphs", 0),
                    "Math": lay.get("math_formulas", 0),
                })
            
            df = pd.DataFrame(flat_data)
            st.dataframe(df, use_container_width=True)


# ============================================================
# SEITE 2: TABELLEN-EXPORT (NEU)
# ============================================================
elif page == "📥 Tabellen-Export":
    st.title("📥 Tabellen-Export")
    st.markdown("""
    Extrahiere einzelne Tabellen oder Seiten-Bereiche als separate PDF-Dateien.
    
    **Features:**
    - 📄 Einzelne Tabelle als PDF
    - 📦 Mehrere Tabellen als ZIP
    - 🎯 Selektiver Export mit Checkboxen
    - ✂️ Seiten-Range Export
    """)
    
    uploaded_file = st.file_uploader(
        "PDF hochladen",
        type=["pdf"],
        key="export_upload"
    )
    
    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name
        
        # Extraktion durchführen
        extractor = get_default_extractor()
        
        with st.spinner("Analysiere PDF..."):
            extraction = extractor.extract(file_bytes, filename)
        
        if extraction.error:
            st.error(f"Fehler bei Extraktion: {extraction.error}")
        else:
            st.success(f"✓ {extraction.pages} Seiten, {extraction.table_count} Tabellen gefunden")
            
            # Tabs für verschiedene Export-Modi
            tab1, tab2, tab3 = st.tabs(["📄 Einzelne Tabellen", "🎯 Selektiver Export", "✂️ Seiten-Range"])
            
            with tab1:
                if extraction.tables:
                    create_table_download_buttons(
                        extraction.tables,
                        file_bytes,
                        filename,
                        st
                    )
                else:
                    st.info("Keine Tabellen im Dokument gefunden.")
            
            with tab2:
                if extraction.tables:
                    create_selective_table_export(
                        extraction.tables,
                        file_bytes,
                        filename,
                        st
                    )
                else:
                    st.info("Keine Tabellen zum Auswählen.")
            
            with tab3:
                st.markdown("### ✂️ Seiten-Range exportieren")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    start_page = st.number_input(
                        "Von Seite",
                        min_value=1,
                        max_value=extraction.pages,
                        value=1,
                        key="range_start"
                    )
                
                with col2:
                    end_page = st.number_input(
                        "Bis Seite",
                        min_value=1,
                        max_value=extraction.pages,
                        value=min(extraction.pages, start_page),
                        key="range_end"
                    )
                
                if start_page > end_page:
                    st.error("Start-Seite muss kleiner/gleich End-Seite sein")
                else:
                    exporter = get_table_exporter()
                    
                    try:
                        range_bytes = exporter.export_page_range(
                            file_bytes,
                            start_page,
                            end_page
                        )
                        
                        if start_page == end_page:
                            range_filename = f"{filename.replace('.pdf', '')}_page_{start_page}.pdf"
                        else:
                            range_filename = f"{filename.replace('.pdf', '')}_pages_{start_page}-{end_page}.pdf"
                        
                        st.download_button(
                            label=f"📄 Download: Seiten {start_page}-{end_page}",
                            data=range_bytes,
                            file_name=range_filename,
                            mime="application/pdf",
                            type="primary"
                        )
                        
                        st.caption(f"Größe: {len(range_bytes)/1024:.1f} KB")
                        
                    except Exception as e:
                        st.error(f"Export fehlgeschlagen: {e}")
            
            # Tabellen-Übersicht
            st.markdown("---")
            st.markdown("### 📋 Tabellen-Übersicht")
            
            if extraction.tables:
                main_tables = [t for t in extraction.tables if not t.is_continuation]
                
                df_tables = pd.DataFrame([
                    {
                        "ID": f"T{t.table_id}",
                        "Seiten": t.page_range_str,
                        "Zeilen": t.rows,
                        "Spalten": t.cols,
                        "Spanning": "✓" if t.is_spanning else "",
                    }
                    for t in main_tables
                ])
                
                st.dataframe(df_tables, use_container_width=True, hide_index=True)
            else:
                st.info("Keine Tabellen gefunden.")


# ============================================================
# SEITE 3: GROUND TRUTH EDITOR
# ============================================================
elif page == "🎯 Ground Truth":
    st.title("🎯 Ground Truth Editor")
    st.markdown("""
    Definiere die **korrekten** Werte für deine Test-PDFs.
    
    **So geht's:**
    1. Lade PDFs in der Analyse-Seite hoch
    2. Öffne jedes PDF manuell und zähle die echten Tabellen/Bilder
    3. Trage hier die korrekten Werte ein
    4. Speichere das Manifest (JSON) für spätere Nutzung
    """)
    
    # Import/Export
    col1, col2, col3 = st.columns(3)
    
    with col1:
        uploaded_manifest = st.file_uploader("📂 Manifest laden", type=["json"], key="load_manifest")
        if uploaded_manifest:
            try:
                data = json.loads(uploaded_manifest.getvalue().decode('utf-8'))
                st.session_state.manifest = GroundTruthManifest(
                    documents=[DocumentGroundTruth.from_dict(d) for d in data.get("documents", [])]
                )
                st.success(f"✓ {len(st.session_state.manifest.documents)} Einträge geladen")
                st.rerun()
            except Exception as e:
                st.error(f"Fehler: {e}")
    
    with col2:
        if st.session_state.manifest.documents:
            manifest_json = json.dumps(
                {"documents": [d.to_dict() for d in st.session_state.manifest.documents]},
                indent=2, ensure_ascii=False
            )
            st.download_button(
                "💾 Manifest speichern",
                manifest_json.encode('utf-8'),
                "ground_truth.json",
                "application/json"
            )
    
    with col3:
        if st.button("🗑️ Alle löschen"):
            st.session_state.manifest = GroundTruthManifest()
            st.rerun()
    
    st.markdown("---")
    
    # Neuer Eintrag
    st.subheader("➕ Neuen Eintrag hinzufügen")
    
    with st.form("add_gt"):
        c1, c2 = st.columns(2)
        
        with c1:
            new_file = st.text_input("PDF Dateiname", placeholder="dokument.pdf")
            new_tables = st.number_input("Korrekte Tabellen-Anzahl", min_value=0, value=0)
            new_images = st.number_input("Korrekte Bilder-Anzahl (Unique)", min_value=0, value=0)
        
        with c2:
            new_pages = st.number_input("Seiten", min_value=0, value=0)
            new_category = st.selectbox(
                "Kategorie",
                ["general", "simple_table", "multi_table", "spanning_table", "borderless", "scanned"]
            )
            new_difficulty = st.slider("Schwierigkeit", 1, 5, 1)
        
        new_notes = st.text_input("Notizen")
        
        if st.form_submit_button("Hinzufügen", type="primary"):
            if new_file:
                if not new_file.endswith('.pdf'):
                    new_file += '.pdf'
                st.session_state.manifest.add(DocumentGroundTruth(
                    file_name=new_file,
                    table_count=new_tables,
                    image_count=new_images,
                    pages=new_pages,
                    category=new_category,
                    difficulty=new_difficulty,
                    notes=new_notes
                ))
                st.success(f"✓ '{new_file}' hinzugefügt")
                st.rerun()
            else:
                st.error("Dateiname erforderlich")
    
    # Bestehende Einträge
    if st.session_state.manifest.documents:
        st.markdown("---")
        st.subheader(f"📋 Einträge ({len(st.session_state.manifest.documents)})")
        
        for i, doc in enumerate(st.session_state.manifest.documents):
            with st.expander(f"📄 {doc.file_name} | T={doc.table_count}, I={doc.image_count}"):
                c1, c2, c3 = st.columns([2, 2, 1])
                
                with c1:
                    new_t = st.number_input("Tabellen", value=doc.table_count, key=f"t_{i}")
                    new_i = st.number_input("Bilder", value=doc.image_count, key=f"i_{i}")
                
                with c2:
                    st.text(f"Kategorie: {doc.category}")
                    st.text(f"Schwierigkeit: {'⭐' * doc.difficulty}")
                    if doc.notes:
                        st.caption(f"📝 {doc.notes}")
                
                with c3:
                    if st.button("💾", key=f"save_{i}", help="Speichern"):
                        doc.table_count = new_t
                        doc.image_count = new_i
                        st.rerun()
                    if st.button("🗑️", key=f"del_{i}", help="Löschen"):
                        st.session_state.manifest.remove(doc.file_name)
                        st.rerun()


# ============================================================
# SEITE 4: BENCHMARK
# ============================================================
elif page == "📊 Benchmark":
    st.title("📊 Benchmark")
    st.markdown("Vergleiche verschiedene Extraktions-Tools gegen deine Ground Truth.")
    
    # Status Check
    if not st.session_state.manifest.documents:
        st.warning("⚠️ Keine Ground Truth definiert. Gehe zum Ground Truth Editor.")
        st.stop()
    
    # Verfügbare Tools
    extractors = get_available_extractors()
    st.info(f"**Verfügbare Tools:** {', '.join(e.name for e in extractors)}")
    
    st.markdown("---")
    
    # File Upload
    st.subheader("📁 PDFs für Benchmark hochladen")
    st.caption("Dateinamen müssen mit Ground Truth Einträgen übereinstimmen")
    
    benchmark_files = st.file_uploader(
        "PDFs auswählen",
        type=["pdf"],
        accept_multiple_files=True,
        key="benchmark_files"
    )
    
    if benchmark_files:
        # Matching anzeigen
        matched = []
        unmatched = []
        
        for f in benchmark_files:
            gt = st.session_state.manifest.get(f.name)
            if gt:
                matched.append((f.name, gt))
            else:
                unmatched.append(f.name)
        
        c1, c2 = st.columns(2)
        with c1:
            if matched:
                st.success(f"✓ {len(matched)} mit Ground Truth")
                for name, gt in matched:
                    st.caption(f"  • {name} (T={gt.table_count}, I={gt.image_count})")
        with c2:
            if unmatched:
                st.warning(f"⚠️ {len(unmatched)} ohne Ground Truth")
                for name in unmatched:
                    st.caption(f"  • {name}")
        
        # Start Benchmark
        if matched and st.button("🚀 Benchmark starten", type="primary"):
            runner = BenchmarkRunner(
                manifest=st.session_state.manifest,
                extractors=extractors
            )
            
            files_data = [(f.name, f.getvalue()) for f in benchmark_files]
            
            with st.spinner("Benchmark läuft..."):
                result = runner.run(files_data)
            
            st.session_state.benchmark_result = result
            st.success("✓ Fertig!")
    
    # Ergebnisse
    if st.session_state.benchmark_result:
        result = st.session_state.benchmark_result
        
        st.markdown("---")
        st.subheader("📈 Ergebnisse")
        
        # Summary
        df_summary = pd.DataFrame(result.to_summary_list())
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        # Rankings
        st.subheader("🏆 Rankings")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("**Tabellen-Genauigkeit:**")
            for i, (name, acc) in enumerate(result.get_ranking("table_accuracy")[:3], 1):
                medal = ["🥇", "🥈", "🥉"][i-1]
                st.write(f"{medal} {name}: {acc:.0%}")
        
        with c2:
            st.markdown("**Bild-Genauigkeit:**")
            for i, (name, acc) in enumerate(result.get_ranking("image_accuracy")[:3], 1):
                medal = ["🥇", "🥈", "🥉"][i-1]
                st.write(f"{medal} {name}: {acc:.0%}")
        
        with c3:
            st.markdown("**Geschwindigkeit:**")
            for i, (name, ms) in enumerate(result.get_ranking("avg_time_ms")[:3], 1):
                medal = ["🥇", "🥈", "🥉"][i-1]
                st.write(f"{medal} {name}: {ms:.0f}ms")
        
        # Details
        if result.detailed_results:
            st.markdown("---")
            st.subheader("📋 Details")
            
            df_details = pd.DataFrame(result.detailed_results)
            
            # Färbung für Diff-Spalten
            def highlight_diff(val):
                if val is None:
                    return ""
                if val == 0:
                    return "background-color: #d4edda"
                elif val > 0:
                    return "background-color: #fff3cd"
                else:
                    return "background-color: #f8d7da"
            
            styled = df_details.style.applymap(highlight_diff, subset=["table_diff", "image_diff"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
            
            st.download_button(
                "📥 Details als CSV",
                df_details.to_csv(index=False).encode('utf-8'),
                "benchmark_details.csv",
                "text/csv"
            )
        
        # Tabellen-Details Report
        if result.table_reports:
            st.markdown("---")
            st.subheader("📋 Tabellen-Details")
            
            df_table_details = pd.DataFrame(result.to_detailed_table_list())
            st.dataframe(df_table_details, use_container_width=True, hide_index=True)
