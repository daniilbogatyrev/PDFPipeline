"""
DocIntel Lab - Streamlit Application.
Integriert: Analyse, Tabellen-Export, CSV-Export, Ground Truth Editor, Benchmarks.
"""

import streamlit as st
import pandas as pd
import json
import io
import zipfile
from typing import List

from core import DocumentOrchestrator, get_available_extractors, TableExporter, create_table_export_summary
from core.extractors import ExtractedTable, get_default_extractor, get_available_csv_extractors
from benchmark import (
    GroundTruthManifest, DocumentGroundTruth, BenchmarkRunner,
    CSVGroundTruthManifest, CSVGroundTruth, CSVBenchmarkRunner
)

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
    .csv-preview { font-family: monospace; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# === Session State ===
if "manifest" not in st.session_state:
    st.session_state.manifest = GroundTruthManifest()
if "csv_manifest" not in st.session_state:
    st.session_state.csv_manifest = CSVGroundTruthManifest()
if "benchmark_result" not in st.session_state:
    st.session_state.benchmark_result = None
if "csv_benchmark_result" not in st.session_state:
    st.session_state.csv_benchmark_result = None


# === Cached Resources ===
@st.cache_resource
def get_orchestrator():
    return DocumentOrchestrator()

@st.cache_resource
def get_table_exporter():
    return TableExporter(crop_to_table=False)


# === Helper Functions ===
def create_table_download_buttons(tables: List[ExtractedTable], pdf_bytes: bytes, filename: str, container):
    """Erstellt Download-Buttons für PDF-Export jeder Tabelle."""
    exporter = get_table_exporter()
    main_tables = [t for t in tables if not t.is_continuation]
    
    if not main_tables:
        container.info("Keine Tabellen zum Exportieren gefunden.")
        return
    
    container.markdown("#### 📥 Als PDF exportieren")
    cols = container.columns(min(len(main_tables), 4))
    
    for idx, table in enumerate(main_tables):
        col = cols[idx % len(cols)]
        label = f"T{table.table_id} ({table.page_range_str})"
        
        try:
            exported = exporter.export_table(pdf_bytes, table)
            col.download_button(
                label=f"📄 {label}",
                data=exported.pdf_bytes,
                file_name=exported.filename,
                mime="application/pdf",
                key=f"dl_pdf_{filename}_{table.table_id}",
                use_container_width=True
            )
            col.caption(f"{exported.size_kb:.1f} KB")
        except Exception as e:
            col.error(f"Fehler: {e}")


def create_csv_download_buttons(tables: List[ExtractedTable], filename: str, container):
    """Erstellt Download-Buttons für CSV-Export jeder Tabelle."""
    main_tables = [t for t in tables if not t.is_continuation and t.has_data]
    
    if not main_tables:
        container.info("Keine Tabellen mit Daten gefunden.")
        return
    
    container.markdown("#### 📊 Als CSV exportieren")
    cols = container.columns(min(len(main_tables), 4))
    
    for idx, table in enumerate(main_tables):
        col = cols[idx % len(cols)]
        label = f"T{table.table_id} ({table.rows}×{table.cols})"
        
        try:
            csv_data = table.to_csv()
            csv_filename = f"{filename.replace('.pdf', '')}_table_{table.table_id}.csv"
            
            col.download_button(
                label=f"📊 {label}",
                data=csv_data.encode('utf-8'),
                file_name=csv_filename,
                mime="text/csv",
                key=f"dl_csv_{filename}_{table.table_id}",
                use_container_width=True
            )
            col.caption(f"{len(csv_data)} Bytes")
        except Exception as e:
            col.error(f"Fehler: {e}")
    
    # Alle CSVs als ZIP
    if len(main_tables) > 1:
        container.markdown("---")
        try:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for table in main_tables:
                    csv_data = table.to_csv()
                    csv_filename = f"{filename.replace('.pdf', '')}_table_{table.table_id}.csv"
                    zf.writestr(csv_filename, csv_data)
            
            container.download_button(
                label=f"📦 Alle {len(main_tables)} CSVs als ZIP",
                data=zip_buffer.getvalue(),
                file_name=f"{filename.replace('.pdf', '')}_tables.zip",
                mime="application/zip",
                key=f"dl_all_csv_{filename}",
                type="primary"
            )
        except Exception as e:
            container.error(f"ZIP-Export fehlgeschlagen: {e}")


# === Sidebar Navigation ===
st.sidebar.title("🔬 DocIntel Lab")

page = st.sidebar.radio(
    "Navigation",
    [
        "📄 Analyse",
        "📊 CSV Export",
        "📥 PDF Export", 
        "🎯 Ground Truth",
        "📈 Tabellen-Benchmark",
        "📉 CSV-Benchmark"
    ],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.caption(f"**Ground Truth:** {len(st.session_state.manifest.documents)} Dokumente")
st.sidebar.caption(f"**CSV Ground Truth:** {len(st.session_state.csv_manifest.tables)} Tabellen")


# ============================================================
# SEITE 1: ANALYSE
# ============================================================
if page == "📄 Analyse":
    st.title("🔬 Document Intelligence")
    st.markdown("**Pipeline:** `Identifier` → `Inspector` → `Extractor` → `CSV`")
    
    orch = get_orchestrator()
    extractor = get_default_extractor()
    
    uploaded_files = st.file_uploader(
        "PDF Dateien hochladen",
        type=["pdf"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.divider()
        
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.getvalue()
            result = orch.run_pipeline(file_bytes, uploaded_file.name)
            extraction = extractor.extract(file_bytes, uploaded_file.name)
            
            pdf_details = result.get("pdf_details") or {}
            layout_stats = result.get("layout_stats") or {}
            
            with st.expander(f"📄 **{result['filename']}**", expanded=True):
                # Header
                col1, col2 = st.columns([3, 1])
                with col1:
                    sub_type = pdf_details.get("sub_type", "N/A")
                    colors = {"NATIVE": "green", "SCANNED": "orange", "VECTOR_GRAPHIC": "blue"}
                    st.markdown(f"**Typ:** :{colors.get(sub_type, 'gray')}[{sub_type}]")
                    st.info(f"💡 {result['reasoning']}")
                with col2:
                    st.metric("Konfidenz", f"{result['confidence']:.1%}")
                
                # Metriken
                if layout_stats:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Seiten", layout_stats.get("pages", 0))
                    m2.metric("Tabellen", layout_stats.get("tables", 0))
                    m3.metric("Bilder", layout_stats.get("images", 0))
                    m4.metric("Textblöcke", layout_stats.get("paragraphs", 0))
                    
                    # Tabellen-Details
                    if extraction.tables:
                        st.markdown("---")
                        st.markdown("**📋 Tabellen-Details:**")
                        st.code(extraction.get_table_summary())
                        
                        # Daten-Preview
                        tables_with_data = extraction.tables_with_data
                        if tables_with_data:
                            st.markdown("**📊 Daten-Vorschau:**")
                            
                            for table in tables_with_data[:3]:  # Max 3 Tabellen
                                with st.expander(f"Tabelle {table.table_id} ({table.page_range_str})"):
                                    try:
                                        df = table.to_dataframe()
                                        st.dataframe(df.head(10), use_container_width=True)
                                        if len(df) > 10:
                                            st.caption(f"... und {len(df) - 10} weitere Zeilen")
                                    except Exception as e:
                                        st.error(f"Vorschau nicht möglich: {e}")
                
                # Quick Export Buttons
                if extraction.tables_with_data:
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        create_csv_download_buttons(extraction.tables, uploaded_file.name, st)
                    with col2:
                        create_table_download_buttons(extraction.tables, file_bytes, uploaded_file.name, st)


# ============================================================
# SEITE 2: CSV EXPORT
# ============================================================
elif page == "📊 CSV Export":
    st.title("📊 CSV Export")
    st.markdown("Extrahiere Tabellen als CSV-Dateien. Vergleiche verschiedene Tools.")
    
    uploaded_file = st.file_uploader("PDF hochladen", type=["pdf"], key="csv_upload")
    
    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name
        
        # Tool-Auswahl
        available_extractors = get_available_csv_extractors()
        tool_names = [e.name for e in available_extractors]
        
        selected_tool = st.selectbox(
            "Extraktions-Tool",
            tool_names,
            index=0
        )
        
        extractor = next(e for e in available_extractors if e.name == selected_tool)
        
        with st.spinner(f"Extrahiere mit {selected_tool}..."):
            extraction = extractor.extract(file_bytes, filename)
        
        if extraction.error:
            st.error(f"Fehler: {extraction.error}")
        else:
            st.success(f"✓ {extraction.table_count} Tabellen gefunden, {len(extraction.tables_with_data)} mit Daten")
            
            # Tabellen-Übersicht
            if extraction.tables_with_data:
                st.markdown("### 📋 Extrahierte Tabellen")
                
                for table in extraction.tables_with_data:
                    with st.expander(f"Tabelle {table.table_id} - {table.page_range_str} ({table.rows}×{table.cols})", expanded=False):
                        try:
                            df = table.to_dataframe()
                            
                            # Tabs für Vorschau und Export
                            tab1, tab2, tab3 = st.tabs(["📊 Vorschau", "📝 CSV", "💾 Download"])
                            
                            with tab1:
                                st.dataframe(df, use_container_width=True)
                            
                            with tab2:
                                csv_data = table.to_csv()
                                st.code(csv_data[:2000] + ("..." if len(csv_data) > 2000 else ""), language="csv")
                            
                            with tab3:
                                csv_filename = f"{filename.replace('.pdf', '')}_table_{table.table_id}.csv"
                                st.download_button(
                                    label=f"📥 {csv_filename}",
                                    data=csv_data.encode('utf-8'),
                                    file_name=csv_filename,
                                    mime="text/csv",
                                    key=f"dl_csv_detail_{table.table_id}"
                                )
                                
                                # Zu Ground Truth hinzufügen
                                if st.button(f"➕ Zu CSV Ground Truth", key=f"add_gt_{table.table_id}"):
                                    gt = CSVGroundTruth.from_dataframe(df, table.table_id, filename)
                                    st.session_state.csv_manifest.add(gt)
                                    st.success(f"✓ Tabelle {table.table_id} zu Ground Truth hinzugefügt")
                                    st.rerun()
                        
                        except Exception as e:
                            st.error(f"Fehler: {e}")
                
                # Alle exportieren
                st.markdown("---")
                create_csv_download_buttons(extraction.tables, filename, st)
            else:
                st.warning("Keine Tabellen mit extrahierbaren Daten gefunden.")
        
        # Tool-Vergleich
        st.markdown("---")
        st.markdown("### 🔄 Tool-Vergleich")
        
        if st.button("Alle Tools vergleichen"):
            comparison_data = []
            
            for ext in available_extractors:
                with st.spinner(f"Teste {ext.name}..."):
                    result = ext.extract(file_bytes, filename)
                    
                    tables_with_data = len(result.tables_with_data) if result.success else 0
                    
                    comparison_data.append({
                        "Tool": ext.name,
                        "Status": "✓" if result.success else "✗",
                        "Tabellen": result.table_count,
                        "Mit Daten": tables_with_data,
                        "Zeit (ms)": round(result.execution_time_ms, 1)
                    })
            
            df_comparison = pd.DataFrame(comparison_data)
            st.dataframe(df_comparison, use_container_width=True, hide_index=True)


# ============================================================
# SEITE 3: PDF EXPORT
# ============================================================
elif page == "📥 PDF Export":
    st.title("📥 Tabellen als PDF exportieren")
    st.markdown("Exportiere einzelne Tabellen oder Seiten-Bereiche als separate PDFs.")
    
    uploaded_file = st.file_uploader("PDF hochladen", type=["pdf"], key="pdf_export_upload")
    
    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name
        
        extractor = get_default_extractor()
        extraction = extractor.extract(file_bytes, filename)
        
        if extraction.error:
            st.error(f"Fehler: {extraction.error}")
        else:
            st.success(f"✓ {extraction.pages} Seiten, {extraction.table_count} Tabellen")
            
            tab1, tab2 = st.tabs(["📄 Tabellen", "✂️ Seiten-Range"])
            
            with tab1:
                create_table_download_buttons(extraction.tables, file_bytes, filename, st)
            
            with tab2:
                col1, col2 = st.columns(2)
                with col1:
                    start_page = st.number_input("Von Seite", 1, extraction.pages, 1)
                with col2:
                    end_page = st.number_input("Bis Seite", 1, extraction.pages, min(extraction.pages, start_page))
                
                if start_page <= end_page:
                    exporter = get_table_exporter()
                    range_bytes = exporter.export_page_range(file_bytes, start_page, end_page)
                    range_filename = f"{filename.replace('.pdf', '')}_pages_{start_page}-{end_page}.pdf"
                    
                    st.download_button(
                        label=f"📄 Download: Seiten {start_page}-{end_page}",
                        data=range_bytes,
                        file_name=range_filename,
                        mime="application/pdf",
                        type="primary"
                    )


# ============================================================
# SEITE 4: GROUND TRUTH EDITOR
# ============================================================
elif page == "🎯 Ground Truth":
    st.title("🎯 Ground Truth Editor")
    
    tab1, tab2 = st.tabs(["📋 Tabellen-Zählung", "📊 CSV-Inhalte"])
    
    # Tab 1: Tabellen-Zählung Ground Truth
    with tab1:
        st.markdown("Definiere die korrekte **Anzahl** der Tabellen pro Dokument.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            uploaded_manifest = st.file_uploader("📂 Manifest laden", type=["json"], key="load_count_manifest")
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
                st.download_button("💾 Speichern", manifest_json.encode('utf-8'), "ground_truth.json", "application/json")
        
        with col3:
            if st.button("🗑️ Alle löschen", key="clear_count"):
                st.session_state.manifest = GroundTruthManifest()
                st.rerun()
        
        st.markdown("---")
        
        # Einträge anzeigen
        if st.session_state.manifest.documents:
            for i, doc in enumerate(st.session_state.manifest.documents):
                with st.expander(f"📄 {doc.file_name} | T={doc.table_count}"):
                    new_t = st.number_input("Tabellen", value=doc.table_count, key=f"count_t_{i}")
                    if st.button("💾 Speichern", key=f"save_count_{i}"):
                        doc.table_count = new_t
                        st.rerun()
                    if st.button("🗑️ Löschen", key=f"del_count_{i}"):
                        st.session_state.manifest.remove(doc.file_name)
                        st.rerun()
    
    # Tab 2: CSV Ground Truth
    with tab2:
        st.markdown("Definiere den erwarteten **Inhalt** der Tabellen als CSV.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            uploaded_csv_manifest = st.file_uploader("📂 CSV Manifest laden", type=["json"], key="load_csv_manifest")
            if uploaded_csv_manifest:
                try:
                    st.session_state.csv_manifest = CSVGroundTruthManifest.load(
                        io.BytesIO(uploaded_csv_manifest.getvalue())
                    )
                    st.success(f"✓ {len(st.session_state.csv_manifest.tables)} Tabellen geladen")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler: {e}")
        
        with col2:
            if st.session_state.csv_manifest.tables:
                # Speichern als JSON
                manifest_data = {
                    "version": "1.0",
                    "type": "csv_ground_truth",
                    "tables": [t.to_dict() for t in st.session_state.csv_manifest.tables]
                }
                st.download_button(
                    "💾 Speichern",
                    json.dumps(manifest_data, indent=2, ensure_ascii=False).encode('utf-8'),
                    "csv_ground_truth.json",
                    "application/json"
                )
        
        with col3:
            if st.button("🗑️ Alle löschen", key="clear_csv"):
                st.session_state.csv_manifest = CSVGroundTruthManifest()
                st.rerun()
        
        st.markdown("---")
        
        # CSV hochladen
        st.markdown("#### ➕ CSV Ground Truth hinzufügen")
        
        col1, col2 = st.columns(2)
        with col1:
            gt_filename = st.text_input("PDF Dateiname", placeholder="dokument.pdf")
            gt_table_id = st.number_input("Tabellen-ID", min_value=1, value=1)
        with col2:
            uploaded_csv = st.file_uploader("CSV-Datei", type=["csv"], key="upload_gt_csv")
        
        if uploaded_csv and gt_filename:
            try:
                csv_content = uploaded_csv.getvalue().decode('utf-8')
                df = pd.read_csv(io.StringIO(csv_content))
                
                st.markdown("**Vorschau:**")
                st.dataframe(df.head(), use_container_width=True)
                
                if st.button("➕ Hinzufügen"):
                    gt = CSVGroundTruth(
                        table_id=gt_table_id,
                        file_name=gt_filename if gt_filename.endswith('.pdf') else gt_filename + '.pdf',
                        csv_data=csv_content,
                        rows=len(df),
                        cols=len(df.columns),
                        has_header=True
                    )
                    st.session_state.csv_manifest.add(gt)
                    st.success(f"✓ Hinzugefügt: {gt_filename} Tabelle {gt_table_id}")
                    st.rerun()
            except Exception as e:
                st.error(f"Fehler beim Lesen: {e}")
        
        # Bestehende Einträge
        if st.session_state.csv_manifest.tables:
            st.markdown("---")
            st.markdown(f"#### 📋 {len(st.session_state.csv_manifest.tables)} CSV Ground Truth Einträge")
            
            for gt in st.session_state.csv_manifest.tables:
                with st.expander(f"📄 {gt.file_name} - Tabelle {gt.table_id} ({gt.rows}×{gt.cols})"):
                    try:
                        df = gt.dataframe
                        st.dataframe(df.head(), use_container_width=True)
                    except:
                        st.code(gt.csv_data[:500])
                    
                    if st.button("🗑️ Löschen", key=f"del_csv_{gt.file_name}_{gt.table_id}"):
                        st.session_state.csv_manifest.remove(gt.file_name, gt.table_id)
                        st.rerun()


# ============================================================
# SEITE 5: TABELLEN-BENCHMARK
# ============================================================
elif page == "📈 Tabellen-Benchmark":
    st.title("📈 Tabellen-Zählung Benchmark")
    st.markdown("Vergleiche wie gut verschiedene Tools Tabellen **zählen**.")
    
    if not st.session_state.manifest.documents:
        st.warning("⚠️ Keine Ground Truth definiert. Gehe zum Ground Truth Editor.")
        st.stop()
    
    extractors = get_available_extractors()
    st.info(f"**Verfügbare Tools:** {', '.join(e.name for e in extractors)}")
    
    benchmark_files = st.file_uploader("PDFs hochladen", type=["pdf"], accept_multiple_files=True, key="bench_files")
    
    if benchmark_files:
        matched = [(f.name, st.session_state.manifest.get(f.name)) for f in benchmark_files if st.session_state.manifest.get(f.name)]
        
        if matched:
            st.success(f"✓ {len(matched)} Dateien mit Ground Truth")
            
            if st.button("🚀 Benchmark starten", type="primary"):
                runner = BenchmarkRunner(manifest=st.session_state.manifest, extractors=extractors)
                files_data = [(f.name, f.getvalue()) for f in benchmark_files]
                
                with st.spinner("Benchmark läuft..."):
                    result = runner.run(files_data)
                
                st.session_state.benchmark_result = result
                st.success("✓ Fertig!")
    
    if st.session_state.benchmark_result:
        result = st.session_state.benchmark_result
        
        st.markdown("### 📊 Ergebnisse")
        df_summary = pd.DataFrame(result.to_summary_list())
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        # Rankings
        st.markdown("### 🏆 Rankings")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Tabellen-Genauigkeit:**")
            for i, (name, acc) in enumerate(result.get_ranking("table_accuracy")[:3], 1):
                st.write(f"{'🥇🥈🥉'[i-1]} {name}: {acc:.0%}")
        
        with col2:
            st.markdown("**Bild-Genauigkeit:**")
            for i, (name, acc) in enumerate(result.get_ranking("image_accuracy")[:3], 1):
                st.write(f"{'🥇🥈🥉'[i-1]} {name}: {acc:.0%}")
        
        with col3:
            st.markdown("**Geschwindigkeit:**")
            for i, (name, ms) in enumerate(result.get_ranking("avg_time_ms")[:3], 1):
                st.write(f"{'🥇🥈🥉'[i-1]} {name}: {ms:.0f}ms")


# ============================================================
# SEITE 6: CSV BENCHMARK
# ============================================================
elif page == "📉 CSV-Benchmark":
    st.title("📉 CSV-Qualität Benchmark")
    st.markdown("Vergleiche wie gut verschiedene Tools Tabellen-**Inhalte** extrahieren.")
    
    if not st.session_state.csv_manifest.tables:
        st.warning("⚠️ Keine CSV Ground Truth definiert. Gehe zum Ground Truth Editor.")
        st.stop()
    
    extractors = get_available_csv_extractors()
    st.info(f"**Verfügbare Tools:** {', '.join(e.name for e in extractors)}")
    st.caption(f"**Ground Truth:** {len(st.session_state.csv_manifest.tables)} Tabellen in {len(st.session_state.csv_manifest.files)} Dateien")
    
    benchmark_files = st.file_uploader("PDFs hochladen", type=["pdf"], accept_multiple_files=True, key="csv_bench_files")
    
    if benchmark_files:
        # Matching
        gt_files = set(st.session_state.csv_manifest.files)
        matched_files = [f for f in benchmark_files if f.name in gt_files]
        
        if matched_files:
            st.success(f"✓ {len(matched_files)} Dateien mit CSV Ground Truth")
            
            # Optionen
            col1, col2, col3 = st.columns(3)
            with col1:
                normalize_ws = st.checkbox("Whitespace normalisieren", value=True)
            with col2:
                case_insensitive = st.checkbox("Groß-/Kleinschreibung ignorieren", value=False)
            with col3:
                numeric_tol = st.number_input("Numerische Toleranz", value=0.001, format="%.4f")
            
            if st.button("🚀 CSV Benchmark starten", type="primary"):
                runner = CSVBenchmarkRunner(
                    manifest=st.session_state.csv_manifest,
                    extractors=extractors,
                    normalize_whitespace=normalize_ws,
                    case_insensitive=case_insensitive,
                    numeric_tolerance=numeric_tol
                )
                
                files_data = [(f.name, f.getvalue()) for f in matched_files]
                
                with st.spinner("CSV Benchmark läuft..."):
                    result = runner.run(files_data)
                
                st.session_state.csv_benchmark_result = result
                st.success("✓ Fertig!")
        else:
            st.warning("Keine der hochgeladenen Dateien hat CSV Ground Truth.")
    
    # Ergebnisse
    if st.session_state.csv_benchmark_result:
        result = st.session_state.csv_benchmark_result
        
        st.markdown("### 📊 Tool-Übersicht")
        df_summary = pd.DataFrame(result.to_summary_list())
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        # Rankings
        st.markdown("### 🏆 Rankings")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Zellen-Genauigkeit:**")
            for i, (name, acc) in enumerate(result.get_ranking("cell_accuracy")[:3], 1):
                st.write(f"{'🥇🥈🥉'[i-1]} {name}: {acc:.1%}")
        
        with col2:
            st.markdown("**Exakte Matches:**")
            for i, (name, acc) in enumerate(result.get_ranking("exact_accuracy")[:3], 1):
                st.write(f"{'🥇🥈🥉'[i-1]} {name}: {acc:.1%}")
        
        with col3:
            st.markdown("**Struktur-Genauigkeit:**")
            for i, (name, acc) in enumerate(result.get_ranking("structure_accuracy")[:3], 1):
                st.write(f"{'🥇🥈🥉'[i-1]} {name}: {acc:.0%}")
        
        # Detail-Tabelle
        st.markdown("### 📋 Details pro Tabelle")
        df_details = pd.DataFrame(result.to_detailed_list())
        
        # Färbung
        def color_accuracy(val):
            if isinstance(val, str) and '%' in val:
                num = float(val.replace('%', ''))
                if num >= 95:
                    return 'background-color: #d4edda'
                elif num >= 80:
                    return 'background-color: #fff3cd'
                else:
                    return 'background-color: #f8d7da'
            return ''
        
        if 'accuracy' in df_details.columns:
            styled = df_details.style.applymap(color_accuracy, subset=['accuracy'])
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.dataframe(df_details, use_container_width=True, hide_index=True)
        
        st.download_button(
            "📥 Details als CSV",
            df_details.to_csv(index=False).encode('utf-8'),
            "csv_benchmark_details.csv",
            "text/csv"
        )
