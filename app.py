"""
DocIntel Lab - Streamlit Application.
Integriert: Analyse (mit Native/Scanned), Ground Truth Editor, Benchmark.
"""

import streamlit as st
import pandas as pd
import json

from core import DocumentOrchestrator, get_available_extractors
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
</style>
""", unsafe_allow_html=True)

# === Session State ===
if "manifest" not in st.session_state:
    st.session_state.manifest = GroundTruthManifest()
if "benchmark_result" not in st.session_state:
    st.session_state.benchmark_result = None


# === Cached Resources ===
@st.cache_resource
def get_orchestrator():
    return DocumentOrchestrator()


# === Sidebar Navigation ===
st.sidebar.title("🔬 DocIntel Lab")

page = st.sidebar.radio(
    "Navigation",
    ["📄 Analyse", "🎯 Ground Truth", "📊 Benchmark"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.caption(f"**Ground Truth:** {len(st.session_state.manifest.documents)} Einträge")


# ============================================================
# SEITE 1: ANALYSE (Original-Funktionalität erhalten)
# ============================================================
if page == "📄 Analyse":
    st.title("🔬 Scientific Document Intelligence")
    st.markdown("""
    **Pipeline:** `Identifier` (Magika) → `Inspector` (Native/Scanned) → `Extractor` (Tabellen/Bilder)
    """)
    
    orch = get_orchestrator()
    
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
                    
                    # Tabellen mit GT-Vergleich
                    gt = st.session_state.manifest.get(uploaded_file.name)
                    tables = layout_stats.get("tables", 0)
                    if gt:
                        diff = tables - gt.table_count
                        if diff == 0:
                            m2.metric("Tabellen", tables, delta="✓ GT", delta_color="off")
                        else:
                            m2.metric("Tabellen", tables, delta=f"{diff:+d} vs GT", 
                                     delta_color="inverse" if diff > 0 else "normal")
                    else:
                        m2.metric("Tabellen", tables)
                    
                    # Bilder
                    u_imgs = layout_stats.get("images", 0)
                    t_imgs = layout_stats.get("images_total", 0)
                    m3.metric("Bilder (Unique)", u_imgs, delta=f"Total: {t_imgs}", delta_color="off")
                    
                    # Paragraphen & Mathe
                    paras = layout_stats.get("paragraphs", 0)
                    math = layout_stats.get("math_formulas", 0)
                    m4.metric("Text-Blöcke", paras)
                    m4.caption(f"🧮 Mathe: {'Hoch' if math > 0 else 'Niedrig'}")
                    
                    # OCR Hinweis
                    if layout_stats.get("requires_ocr"):
                        st.warning("⚠️ Gescanntes PDF - für Tabellen-/Texterkennung ist OCR erforderlich.")
                
                # Quick-Add zu Ground Truth
                col1, col2 = st.columns([3, 1])
                with col2:
                    if not gt:
                        if st.button("➕ Zu GT hinzufügen", key=f"add_{uploaded_file.name}"):
                            st.session_state.manifest.add(DocumentGroundTruth(
                                file_name=uploaded_file.name,
                                table_count=layout_stats.get("tables", 0),
                                image_count=layout_stats.get("images", 0),
                                pages=layout_stats.get("pages", 0)
                            ))
                            st.rerun()
                    else:
                        st.caption(f"✓ In GT (T={gt.table_count}, I={gt.image_count})")
                
                # Raw JSON
                with st.expander("🛠️ Rohe JSON-Daten"):
                    st.json(result)
        
        # Export
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
            
            st.download_button(
                "📥 Als CSV",
                df.to_csv(index=False).encode('utf-8'),
                "analyse_export.csv",
                "text/csv"
            )


# ============================================================
# SEITE 2: GROUND TRUTH EDITOR
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
# SEITE 3: BENCHMARK
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
