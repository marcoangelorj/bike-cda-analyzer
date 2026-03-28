import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Aero TT Lab Pro", layout="wide")

# FUNÇÃO PARA TRANSFORMAR IMAGEM EM TEXTO (BASE64)
# Isso impede o erro 'image_to_url' pois o Streamlit não precisa gerenciar o link da imagem
def get_image_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.title("🏁 Configurações de Prova")
uploaded_file = st.sidebar.file_uploader("1. Foto Frontal", type=["jpg", "jpeg", "png"])
real_tire_width_mm = st.sidebar.number_input("2. Largura do Pneu (mm)", value=25.0, step=0.5)
dist_km = st.sidebar.selectbox("3. Distância (km)", [10, 20, 40, 90, 180], index=2)
user_ftp = st.sidebar.number_input("4. Watts", value=250, step=5)
drag_coeff = st.sidebar.select_slider("5. Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

# --- FUNÇÕES DE CÁLCULO ---
def estimar_tempo(cda, watts, dist_km):
    rho = 1.225
    v_ms = (watts / (0.5 * rho * cda))**(1/3)
    return (dist_km * 1000) / v_ms

def formatar_tempo(segundos):
    mins, segs = divmod(int(segundos), 60)
    horas, mins = divmod(mins, 60)
    return f"{horas}h {mins}m {segs}s" if horas > 0 else f"{mins}m {segs}s"

# --- CORPO DO APP ---
st.title("🚴 Aero Analyzer & TT Predictor")

if uploaded_file:
    # 1. Processa a imagem original
    img = Image.open(uploaded_file)
    w, h = img.size
    canvas_w = 800
    canvas_h = int(h * (canvas_w / w))
    img_resized = img.resize((canvas_w, canvas_h))
    
    # 2. CONVERTE PARA BASE64 (A MÁGICA QUE RESOLVE O ERRO)
    img_b64 = get_image_base64(img_resized)

    tab1, tab2 = st.tabs(["📏 Calibração", "👤 Silhueta"])

    with tab1:
        st.write("Desenhe uma linha sobre o pneu.")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_image=None, # Deixe None aqui
            background_color=img_b64, # O truque: Passamos o Base64 como cor de fundo
            drawing_mode="line",
            key="c_calib",
            height=canvas_h,
            width=canvas_w,
        )

    with tab2:
        st.write("Contorne o ciclista.")
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.3)",
            stroke_width=1,
            stroke_color="#00FF00",
            background_image=None, # Deixe None aqui
            background_color=img_b64, # O truque: Passamos o Base64 como cor de fundo
            drawing_mode="polygon",
            key="c_silh",
            height=canvas_h,
            width=canvas_w,
        )

    if st.button("🚀 ANALISAR"):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            obj = canvas_calib.json_data["objects"][-1]
            px_width = np.sqrt(obj["width"]**2 + obj["height"]**2)
            
            if px_width > 0 and canvas_silh.image_data is not None:
                mm_per_px = real_tire_width_mm / px_width
                mask = canvas_silh.image_data[:, :, 3]
                total_px = np.sum(mask > 0)
                
                area_m2 = (total_px * (mm_per_px**2)) / 1_000_000
                cda_calc = area_m2 * drag_coeff
                tempo_seg = estimar_tempo(cda_calc, user_ftp, dist_km)
                
                st.session_state.setups.append({
                    "Setup": f"Análise {len(st.session_state.setups)+1}",
                    "CdA": cda_calc,
                    "Tempo": tempo_seg,
                    "Formatado": formatar_tempo(tempo_seg)
                })

    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.table(df[["Setup", "CdA", "Formatado"]])
else:
    st.info("Suba uma foto para começar.")
