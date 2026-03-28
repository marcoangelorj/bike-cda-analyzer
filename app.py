import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Aero Performance Lab Pro", layout="wide")

# Função para converter imagem para Base64 (A solução definitiva)
def get_image_base64(img):
    img = img.convert("RGB")
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}"

# Função para o PDF
def generate_pdf(df, tire_mm, ftp, athlete_name):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Relatorio de Analise Aerodinamica", ln=True, align="C")
    pdf.set_font("helvetica", "", 12)
    pdf.ln(10)
    pdf.cell(0, 10, f"Atleta: {athlete_name} | Pneu: {tire_mm}mm | Potencia: {ftp}W", ln=True)
    pdf.ln(10)
    for _, row in df.iterrows():
        pdf.cell(0, 10, f"{row['Setup']}: CdA {row['CdA']:.4f} | Vel: {row['Velocidade']:.1f} km/h", ln=True)
    return pdf.output()

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.header("⚙️ Parametros")
athlete_name = st.sidebar.text_input("Nome do Atleta", "Ciclista Pro")
uploaded_file = st.sidebar.file_uploader("Upload PNG/JPG", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Largura Pneu (mm)", value=25.0)
ftp_watts = st.sidebar.number_input("Watts (FTP)", value=250)
cd_val = st.sidebar.select_slider("Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

st.title("🚴 Aero Analyzer Pro")

if uploaded_file:
    img = Image.open(uploaded_file)
    # Redimensionamento
    canvas_w = 700
    w, h = img.size
    canvas_h = int(h * (canvas_w / w))
    img_res = img.resize((canvas_w, canvas_h))
    
    # CONVERSÃO PARA BASE64
    img_b64 = get_image_base64(img_res)

    t1, t2 = st.tabs(["📏 1. Calibrar", "👤 2. Silhueta"])

    with t1:
        st.write("Desenhe a linha no pneu.")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_color=img_b64, # INJETANDO IMAGEM VIA BASE64
            drawing_mode="line",
            key="calib_render",
            height=canvas_h,
            width=canvas_w,
        )

    with t2:
        st.write("Contorne o atleta.")
        if st.button("🗑️ Resetar"): st.rerun()
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.4)",
            stroke_width=2,
            stroke_color="#00FF00",
            background_color=img_b64, # INJETANDO IMAGEM VIA BASE64
            drawing_mode="polygon",
            key="silh_render",
            height=canvas_h,
            width=canvas_w,
        )

    if st.button("🚀 ANALISAR", use_container_width=True):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            line = canvas_calib.json_data["objects"][-1]
            px_len = np.sqrt(line["width"]**2 + line["height"]**2)
            if px_len > 0 and canvas_silh.image_data is not None:
                mm_px = tire_mm / px_len
                mask = canvas_silh.image_data[:, :, 3]
                total_px = np.sum(mask > 0)
                area = (total_px * (mm_px**2)) / 1_000_000
                cda = area * cd_val
                v_ms = (ftp_watts / (0.5 * 1.225 * cda))**(1/3)
                
                st.session_state.setups.append({
                    "Setup": f"Posicao {len(st.session_state.setups)+1}",
                    "CdA": cda,
                    "Velocidade": v_ms * 3.6
                })

    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.table(df)
        pdf_out = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
        st.download_button("📥 Baixar PDF", pdf_out, "analise.pdf", "application/pdf")
