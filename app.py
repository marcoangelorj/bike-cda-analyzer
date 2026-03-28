import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Aero Analyzer Pro", layout="wide")

# FUNÇÃO PARA CONVERTER IMAGEM (Remove transparência para evitar tela preta)
def prepare_image(img):
    # Se a imagem tiver transparência (como o seu modelo), criamos um fundo branco
    if img.mode in ("RGBA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
        return background
    return img.convert("RGB")

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.title("🏁 Parâmetros de Prova")
uploaded_file = st.sidebar.file_uploader("Subir Foto (como a do exemplo)", type=["jpg", "jpeg", "png"])
real_tire_width_mm = st.sidebar.number_input("Largura do Pneu (mm)", value=25.0)
dist_km = st.sidebar.selectbox("Distância (km)", [10, 20, 40, 90, 180], index=2)
user_ftp = st.sidebar.number_input("Sua Potência (Watts)", value=250)
drag_coeff = st.sidebar.select_slider("Coeficiente Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

st.title("🚴 Aero Analyzer & TT Predictor")

if uploaded_file:
    # 1. Processamento Robusto da Imagem
    raw_img = Image.open(uploaded_file)
    clean_img = prepare_image(raw_img) # AQUI resolvemos o problema da tela preta
    
    w, h = clean_img.size
    canvas_w = 700 
    canvas_h = int(h * (canvas_w / w))
    img_resized = clean_img.resize((canvas_w, canvas_h))

    tab1, tab2 = st.tabs(["📏 1. Calibração (Pneu)", "👤 2. Silhueta (Corpo)"])

    with tab1:
        st.write("Dê um zoom e desenhe uma linha na largura do pneu dianteiro.")
        canvas_calib = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_image=img_resized,
            drawing_mode="line",
            key="calib_v11",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
        )

    with tab2:
        st.write("Contorne toda a silhueta do ciclista + bike.")
        canvas_silh = st_canvas(
            fill_color="rgba(0, 255, 0, 0.4)",
            stroke_width=2,
            stroke_color="#00FF00",
            background_image=img_resized,
            drawing_mode="polygon",
            key="silh_v11",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
        )

    if st.button("🚀 ANALISAR SETUP"):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            obj = canvas_calib.json_data["objects"][-1]
            px_width = np.sqrt(obj["width"]**2 + obj["height"]**2)
            
            if px_width > 0 and canvas_silh.image_data is not None:
                mm_per_px = real_tire_width_mm / px_width
                
                # Área frontal (pixels verdes)
                mask = canvas_silh.image_data[:, :, 3]
                total_px = np.sum(mask > 0)
                
                area_m2 = (total_px * (mm_per_px**2)) / 1_000_000
                cda_calc = area_m2 * drag_coeff
                
                # Cálculo de Tempo
                v_ms = (user_ftp / (0.5 * 1.225 * cda_calc))**(1/3)
                tempo_seg = (dist_km * 1000) / v_ms
                
                mins, segs = divmod(int(tempo_seg), 60)
                horas, mins = divmod(mins, 60)
                tempo_fmt = f"{horas}h {mins}m {segs}s" if horas > 0 else f"{mins}m {segs}s"

                st.session_state.setups.append({
                    "Setup": f"Análise {len(st.session_state.setups)+1}",
                    "CdA": round(cda_calc, 4),
                    "Tempo": tempo_fmt,
                    "Vel. Estimada": f"{v_ms*3.6:.1f} km/h"
                })

    if st.session_state.setups:
        st.divider()
        st.subheader("📋 Resultados Comparativos")
        st.table(pd.DataFrame(st.session_state.setups))
        
        if st.button("🗑️ Limpar Histórico"):
            st.session_state.setups = []
            st.rerun()
else:
    st.info("Suba a imagem do ciclista para começar.")
