import streamlit as st
import pandas as pd
from orchestrator import DocumentOrchestrator

st.set_page_config(page_title="DocIntel Lab", layout="wide")

# Initialisiere den Orchestrator einmalig
@st.cache_resource
def get_orchestrator():
    return DocumentOrchestrator()

orch = get_orchestrator()

st.title("🔬 Scientific Document Intelligence")
st.caption("Modular Pipeline: Identification -> Deep Inspection")

uploaded_files = st.file_uploader("Upload Files", accept_multiple_files=True)

if uploaded_files:
    all_results = []

    for uploaded_file in uploaded_files:
        # Die gesamte Logik ist jetzt in einer einzigen Zeile gekapselt!
        result = orch.run_pipeline(uploaded_file.getvalue(), uploaded_file.name)
        all_results.append(result)

        # UI Rendering
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**{result['filename']}**")
                if result['pdf_details']:
                    st.success(f"PDF Sub-Typ: {result['pdf_details']['sub_type']}")
                else:
                    st.info(f"Format: {result['format']}")
            with c2:
                st.metric("Conf.", f"{result['confidence']:.1%}")

    # Benchmark Export
    if all_results:
        st.divider()
        st.subheader("📊 Pipeline Export")
        st.dataframe(pd.DataFrame(all_results))