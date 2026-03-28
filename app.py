import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Aero TT Lab Pro", layout="wide")

# Função para converter imagem para Base64 (Evita o erro de URL)
def get_image_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.title("🏁 Configurações")
uploaded_file = st.sidebar.file_uploader("1. Foto Frontal", type=["jpg", "jpeg", "png"])
real_tire_width_mm = st.sidebar.number_input("2. Largura do Pneu (mm)", value=25.0, step=0.5)
dist_km = st.sidebar.selectbox("3. Distância (km)", [10, 20, 40, 90, 180], index=2)
user_ftp = st.sidebar.number_input("4. Watts", value=250, step=5)
drag_coeff = st.sidebar.select_slider("5. Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

st.title("🚴 Aero Analyzer & TT Predictor")

if uploaded_file:
    # 1. Processamento da imagem
    img = Image.open(uploaded_file)
    w, h = img.size
    canvas_w = 700 # Reduzi um pouco para garantir que caiba na tela
    canvas_h = int(h * (canvas_w / w))
    img_resized = img.resize((canvas_w, canvas_h))
    
    # 2. Converte para Base64
    img_b64 = get_image_base64(img_resized)

    tab1, tab2 = st.tabs(["📏 1. Calibração (Pneu)", "👤 2. Silhueta (Corpo)"])

    with tab1:
        st.write("Desenhe uma linha sobre o pneu (Vermelho).")
        canvas_calib = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_image=Image.open(io.BytesIO(base64.b64decode(img_b64.split(",")[1]))), # Re-abre como objeto PIL
            drawing_mode="line",
            key="canvas_calib_v4",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
        )

    with tab2:
        st.write("Contorne o ciclista (Verde).")
        canvas_silh = st_canvas(
            fill_color="rgba(0, 255, 0, 0.3)",
            stroke_width=2,
            stroke_color="#00FF00",
            background_image=Image.open(io.BytesIO(base64.b64decode(img_b64.split(",")[1]))), # Re-abre como objeto PIL
            drawing_mode="polygon",
            key="canvas_silh_v4",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
        )

    if st.button("🚀 ANALISAR SETUP"):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            # Pega o último objeto desenhado (a linha)
            obj = canvas_calib.json_data["objects"][-1]
            # Teorema de Pitágoras para o comprimento da linha
            px_width = np.sqrt(obj["width"]**2 + obj["height"]**2)
            
            if px_width > 0 and canvas_silh.image_data is not None:
                mm_per_px = real_tire_width_mm / px_width
                
                # Área frontal (pixels com cor verde)
                mask = canvas_silh.image_data[:, :, 3]
                total_px = np.sum(mask > 0)
                
                area_m2 = (total_px * (mm_per_px**2)) / 1_000_000
                cda_calc = area_m2 * drag_coeff
                
                # Estimativa de tempo (V = (P/(0.5*rho*CdA))^(1/3))
                v_ms = (user_ftp / (0.5 * 1.225 * cda_calc))**(1/3)
                tempo_seg = (dist_km * 1000) / v_ms
                
                mins, segs = divmod(int(tempo_seg), 60)
                horas, mins = divmod(mins, 60)
                tempo_formatado = f"{horas}h {mins}m {segs}s" if horas > 0 else f"{mins}m {segs}s"

                st.session_state.setups.append({
                    "Setup": f"Análise {len(st.session_state.setups)+1}",
                    "CdA": cda_calc,
                    "Tempo": tempo_formatado
                })
                st.success("Análise concluída!")

    if st.session_state.setups:
        st.divider()
        st.table(pd.DataFrame(st.session_state.setups))
else:
    st.info("Aguardando upload da imagem...")
