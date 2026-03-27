import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from fpdf import FPDF
import base64

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Aero Analyzer Pro", layout="wide")

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.title("🚀 Parâmetros Aero")
uploaded_file = st.sidebar.file_uploader("1. Foto Frontal", type=["jpg", "jpeg", "png"])
real_tire_width_mm = st.sidebar.number_input("2. Largura do Pneu (mm)", value=25.0, step=0.5)
speed_kmh = st.sidebar.slider("3. Velocidade Alvo (km/h)", 20, 60, 40)
drag_coeff = st.sidebar.slider("4. Coeficiente Cd (Estimado)", 0.50, 0.90, 0.63)

# --- FUNÇÃO RELATÓRIO PDF ---
def create_pdf(df, speed):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "Relatorio de Analise Aerodinamica", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, f"Velocidade de Analise: {speed} km/h", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 10, "Setup", 1)
    pdf.cell(40, 10, "Area (m2)", 1)
    pdf.cell(40, 10, "CdA", 1)
    pdf.cell(40, 10, "Watts (Aero)", 1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 10)
    for _, row in df.iterrows():
        pdf.cell(40, 10, str(row['Nome']), 1)
        pdf.cell(40, 10, f"{row['Area (m2)']:.4f}", 1)
        pdf.cell(40, 10, f"{row['CdA']:.4f}", 1)
        pdf.cell(40, 10, f"{row['Watts']:.1f}W", 1)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# --- CORPO DO APP ---
st.title("🚴 Calculadora de Área Frontal & CdA")

if uploaded_file:
    # --- PROCESSO DE IMAGEM (ORDEM CORRETA) ---
    img = Image.open(uploaded_file)
    w, h = img.size
    canvas_w = 800
    canvas_h = int(h * (canvas_w / w))
    
    # CRIANDO A VARIÁVEL img_resized ANTES DE TUDO
    img_resized = img.resize((canvas_w, canvas_h))
    
    tab1, tab2 = st.tabs(["📏 Calibração (Pneu)", "👤 Silhueta (Corpo)"])

    with tab1:
        st.write("Desenhe uma **LINHA** exatamente sobre a largura do pneu.")
        canvas_calib = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_image=img_resized,
            drawing_mode="line",
            key="calib",
            height=canvas_h,
            width=canvas_w,
        )

    with tab2:
        st.write("Use o **POLÍGONO** para contornar o ciclista e a bike.")
        canvas_silh = st_canvas(
            fill_color="rgba(0, 255, 0, 0.3)",
            stroke_width=1,
            stroke_color="#00FF00",
            background_image=img_resized,
            drawing_mode="polygon",
            key="silh",
            height=canvas_h,
            width=canvas_w,
        )

    # --- PROCESSAMENTO ---
    if st.button("📊 ANALISAR E SALVAR SETUP"):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            # Calibração
            obj = canvas_calib.json_data["objects"][-1]
            px_width = np.sqrt(obj["width"]**2 + obj["height"]**2)
            mm_per_px = real_tire_width_mm / px_width
            
            # Área (Alpha channel)
            mask = canvas_silh.image_data[:, :, 3]
            total_px = np.sum(mask > 0)
            
            area_m2 = (total_px * (mm_per_px**2)) / 1_000_000
            cda_calc = area_m2 * drag_coeff
            v_ms = speed_kmh / 3.6
            watts = 0.5 * 1.225 * (v_ms**3) * cda_calc
            
            st.session_state.setups.append({
                "Nome": f"Setup {len(st.session_state.setups)+1}",
                "Area (m2)": area_m2,
                "CdA": cda_calc,
                "Watts": watts
            })
            st.success("Análise concluída!")
        else:
            st.error("Erro: Desenhe a linha no pneu antes de clicar!")

    # --- RESULTADOS ---
    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.table(df.style.format({'Area (m2)': '{:.4f}', 'CdA': '{:.4f}', 'Watts': '{:.1f}'}))
        
        pdf_bytes = create_pdf(df, speed_kmh)
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="relatorio_aero.pdf">📥 Baixar PDF</a>'
        st.markdown(href, unsafe_allow_html=True)
else:
    st.warning("Carregue uma foto na barra lateral!")
