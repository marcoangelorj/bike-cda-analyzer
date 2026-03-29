import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro", layout="wide")

# --- TRATAMENTO DE IMAGEM: SOLUÇÃO ANTI-TELA PRETA ---
def get_clean_base64(uploaded_file):
    img = Image.open(uploaded_file).convert("RGBA")
    white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    combined = Image.alpha_composite(white_bg, img).convert("RGB")
    
    canvas_w = 750
    w, h = combined.size
    canvas_h = int(h * (canvas_w / w))
    img_resized = combined.resize((canvas_w, canvas_h))
    
    buffered = io.BytesIO()
    img_resized.save(buffered, format="JPEG", quality=90)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}", canvas_w, canvas_h

# --- FUNÇÃO GERADORA DE PDF COM OBSERVAÇÕES ---
def generate_pdf(df, tire_mm, ftp, athlete):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Laudo de Analise Aerodinamica Frontal", ln=True, align="C")
    pdf.ln(5)
    
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 10, f"Atleta: {athlete}", ln=True)
    pdf.cell(0, 10, f"Setup: Pneu {tire_mm}mm | Potencia: {ftp}W", ln=True)
    pdf.ln(5)
    
    # Tabela
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(35, 10, "ID Setup", 1, 0, "C", True)
    pdf.cell(35, 10, "CdA", 1, 0, "C", True)
    pdf.cell(40, 10, "Vel. (km/h)", 1, 0, "C", True)
    pdf.cell(80, 10, "Observacoes Tecnicas", 1, 1, "C", True)
    
    pdf.set_font("helvetica", "", 9)
    for _, row in df.iterrows():
        pdf.cell(35, 10, str(row["Setup"]), 1, 0, "C")
        pdf.cell(35, 10, f"{row['CdA']:.4f}", 1, 0, "C")
        pdf.cell(40, 10, f"{row['Vel. Est.']:.1f}", 1, 0, "C")
        # Garante que o texto não saia da célula
        obs_texto = str(row["Obs"])[:50] 
        pdf.cell(80, 10, obs_texto, 1, 1, "L")
    
    pdf.ln(10)
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(0, 10, "Analise baseada em simulacao matematica (rho=1.225). Resultados podem variar na estrada.", align="C")
    
    return pdf.output()

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuracoes")
athlete_name = st.sidebar.text_input("Nome do Atleta", "Ciclista")
uploaded_file = st.sidebar.file_uploader("Foto Frontal", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Pneu (mm)", value=25.0)
ftp_watts = st.sidebar.number_input("Potencia (W)", value=250)
cd_val = st.sidebar.select_slider("Estimativa Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

# CAMPO DE OBSERVAÇÃO TÉCNICA
obs_tecnica = st.sidebar.text_area("Observacoes para este Setup", placeholder="Ex: Capacete Aero Giro, Maos juntas...")

st.title("🚴 Aero Analyzer Pro + PDF Report")

if uploaded_file:
    img_b64, c_w, c_h = get_clean_base64(uploaded_file)
    t1, t2 = st.tabs(["📏 1. Calibrar", "👤 2. Silhueta"])

    with t1:
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_color=img_b64, drawing_mode="line", key="c_calib",
            height=c_h, width=c_w, update_streamlit=True
        )

    with t2:
        if st.button("🗑️ Limpar Silhueta"): st.rerun()
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.4)", stroke_width=2, stroke_color="#00FF00",
            background_color=img_b64, drawing_mode="polygon", key="c_silh",
            height=c_h, width=c_w, update_streamlit=True
        )

    if st.button("🚀 CALCULAR E SALVAR SETUP", use_container_width=True):
        if canvas_calib.json_data and canvas_silh.image_data is not None:
            line = canvas_calib.json_data["objects"][-1]
            px_len = np.sqrt(line["width"]**2 + line["height"]**2)
            mm_px = tire_mm / px_len
            mask = canvas_silh.image_data[:, :, 3]
            area_m2 = (np.sum(mask > 0) * (mm_px**2)) / 1_000_000
            cda = area_m2 * cd_val
            kmh = ((ftp_watts / (0.5 * 1.225 * cda))**(1/3)) * 3.6

            st.session_state.setups.append({
                "Setup": f"Posicao {len(st.session_state.setups)+1}",
                "Area (m2)": area_m2,
                "CdA": cda,
                "Vel. Est.": kmh,
                "Obs": obs_tecnica
            })
            st.success("Analise salva!")

    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.subheader("📊 Comparativo de Eficiencia")
        st.dataframe(df[["Setup", "CdA", "Vel. Est.", "Obs"]], hide_index=True)
        
        pdf_bytes = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
        st.download_button("📥 Gerar Laudo PDF", data=pdf_bytes, file_name=f"Laudo_{athlete_name}.pdf", mime="application/pdf")
        
        if st.button("🗑️ Reiniciar Tudo"):
            st.session_state.setups = []
            st.rerun()
