import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io

# --- 🛠️ CORREÇÃO DE COMPATIBILIDADE (MONKEY PATCH) ---
# Isso resolve o erro 'AttributeError: image_to_url' nas versões novas do Streamlit
import streamlit.runtime.media_file_manager as mfm
if not hasattr(st, "image_to_url"):
    from streamlit.elements import image as st_image
    st_image.image_to_url = mfm.add_queued_str_file if hasattr(mfm, "add_queued_str_file") else lambda *args, **kwargs: None

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero TT Lab Pro", layout="wide")

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.title("🏁 Configurações de Prova")
uploaded_file = st.sidebar.file_uploader("1. Foto Frontal (JPG/PNG)", type=["jpg", "jpeg", "png"])
real_tire_width_mm = st.sidebar.number_input("2. Largura do Pneu (mm)", value=25.0, step=0.5)
dist_km = st.sidebar.selectbox("3. Distância da Prova (km)", [10, 20, 40, 90, 180], index=2)
user_ftp = st.sidebar.number_input("4. Potência Sustentada (Watts)", value=250, step=5)

drag_coeff = st.sidebar.select_slider(
    "5. Coeficiente Cd (Elite)",
    options=np.around(np.arange(0.22, 0.41, 0.01), 2),
    value=0.30
)

# --- FUNÇÕES DE CÁLCULO ---
def estimar_tempo(cda, watts, dist_km):
    rho = 1.225
    v_ms = (watts / (0.5 * rho * cda))**(1/3)
    tempo_segundos = (dist_km * 1000) / v_ms
    return tempo_segundos

def formatar_tempo(segundos):
    mins, segs = divmod(int(segundos), 60)
    horas, mins = divmod(mins, 60)
    return f"{horas}h {mins}m {segs}s" if horas > 0 else f"{mins}m {segs}s"

# --- CORPO DO APP ---
st.title("🚴 Aero Analyzer & TT Predictor")

if uploaded_file:
    # Processamento de Imagem
    raw_img = Image.open(uploaded_file)
    w, h = raw_img.size
    canvas_w = 800
    canvas_h = int(h * (canvas_w / w))
    img_resized = raw_img.resize((canvas_w, canvas_h))
    
    tab1, tab2 = st.tabs(["📏 1. Calibração (Pneu)", "👤 2. Silhueta (Corpo)"])

    with tab1:
        st.write("Desenhe uma linha sobre a largura do pneu.")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_image=img_resized,
            drawing_mode="line",
            key="calib_v3",
            height=canvas_h,
            width=canvas_w
        )

    with tab2:
        st.write("Contorne a silhueta do ciclista.")
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.3)",
            stroke_width=1,
            stroke_color="#00FF00",
            background_image=img_resized,
            drawing_mode="polygon",
            key="silh_v3",
            height=canvas_h,
            width=canvas_w
        )

    if st.button("🚀 ANALISAR E COMPARAR"):
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
                st.success("Dados salvos na tabela abaixo!")

    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.subheader(f"📊 Projeção para {dist_km}km a {user_ftp}W")
        st.table(df[["Setup", "CdA", "Formatado"]])
        
        if len(df) >= 2:
            ganho = df['Tempo'].iloc[0] - df['Tempo'].iloc[-1]
            st.metric("Tempo Salvo (vs Setup 1)", f"{int(ganho)} seg", delta=f"{ganho/60:.1f} min")
else:
    st.info("Aguardando foto frontal para análise.")
