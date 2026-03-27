import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from fpdf import FPDF
import base64
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Aero Analyzer Pro", layout="wide")

if 'setups' not in st.session_state:
    st.session_state.setups = []

st.sidebar.title("🚀 Parâmetros Aero")
uploaded_file = st.sidebar.file_uploader("1. Foto Frontal", type=["jpg", "jpeg", "png"])
real_tire_width_mm = st.sidebar.number_input("2. Largura do Pneu (mm)", value=25.0, step=0.5)
speed_kmh = st.sidebar.slider("3. Velocidade Alvo (km/h)", 20, 60, 40)
drag_coeff = st.sidebar.slider("4. Coeficiente Cd", 0.50, 0.90, 0.63)

# --- APP ---
st.title("🚴 Calculadora de Área Frontal & CdA")

if uploaded_file:
    # Processamento da Imagem
    raw_img = Image.open(uploaded_file)
    w, h = raw_img.size
    canvas_w = 800
    canvas_h = int(h * (canvas_w / w))
    img_resized = raw_img.resize((canvas_w, canvas_h))

    tab1, tab2 = st.tabs(["📏 1. Calibração (Pneu)", "👤 2. Silhueta (Corpo)"])

    with tab1:
        st.write("Desenhe uma linha sobre a largura do pneu.")
        canvas_calib = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_image=img_resized,
            drawing_mode="line",
            key="canvas_calib",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
        )

    with tab2:
        st.write("Contorne a silhueta do ciclista.")
        canvas_silh = st_canvas(
            fill_color="rgba(0, 255, 0, 0.3)",
            stroke_width=2,
            stroke_color="#00FF00",
            background_image=img_resized,
            drawing_mode="polygon",
            key="canvas_silh",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
        )

    if st.button("📊 ANALISAR E SALVAR"):
        # Verifica Calibração
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            obj = canvas_calib.json_data["objects"][-1]
            px_width = np.sqrt(obj["width"]**2 + obj["height"]**2)
            
            if px_width > 0:
                mm_per_px = real_tire_width_mm / px_width
                
                # Verifica Silhueta
                if canvas_silh.image_data is not None:
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
                    st.balloons()
        else:
            st.error("Por favor, desenhe a linha de calibração no pneu!")

    # Exibição de Resultados
    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.table(df.style.format({'Area (m2)': '{:.4f}', 'CdA': '{:.4f}', 'Watts': '{:.1f}'}))
else:
    st.info("Aguardando foto...")
