import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- 🛠️ CORREÇÃO DE COMPATIBILIDADE (MONKEY PATCH) ---
# Isso resolve o erro 'AttributeError: image_to_url' no Render/Python 3.14
import streamlit.runtime.media_file_manager as mfm
if not hasattr(st, "image_to_url"):
    from streamlit.elements import image as st_image
    # Tenta mapear a função para o novo local interno do Streamlit
    st_image.image_to_url = mfm.add_queued_str_file if hasattr(mfm, "add_queued_str_file") else lambda *args, **kwargs: None

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro", layout="wide")

# Função para remover transparência e evitar tela preta
def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background
    return img.convert("RGB")

# Função para converter imagem para Base64 (Solução secundária contra o erro)
def get_image_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.header("⚙️ Parâmetros")
uploaded_file = st.sidebar.file_uploader("Upload PNG (Fundo Branco)", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Largura do Pneu (mm)", value=25.0, step=0.1)
ftp_watts = st.sidebar.number_input("Sua Potência (Watts)", value=250)
cd_fixed = st.sidebar.select_slider("Coeficiente Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

st.title("🚴 Aero Performance Lab")

if uploaded_file:
    img_clean = process_image(uploaded_file)
    canvas_w = 700
    w, h = img_clean.size
    canvas_h = int(h * (canvas_w / w))
    img_resized = img_clean.resize((canvas_w, canvas_h))
    
    # Gerar Base64 para garantir que o componente não quebre
    img_b64 = get_image_base64(img_resized)

    t1, t2 = st.tabs(["📏 1. Calibrar Pneu", "👤 2. Contornar Silhueta"])

    with t1:
        st.info("Desenhe a linha sobre a largura do pneu.")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_image=img_resized, # O patch acima fará isso funcionar
            drawing_mode="line", key="c_calib",
            height=canvas_h, width=canvas_w,
            update_streamlit=True
        )

    with t2:
        st.info("Contorne o atleta.")
        if st.button("🗑️ Resetar Contorno"): st.rerun()
        
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.4)", stroke_width=2, stroke_color="#00FF00",
            background_image=img_resized,
            drawing_mode="polygon", key="c_silh",
            height=canvas_h, width=canvas_w,
            update_streamlit=True
        )

    if st.button("🚀 ANALISAR", use_container_width=True):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            line = canvas_calib.json_data["objects"][-1]
            px_len = np.sqrt(line["width"]**2 + line["height"]**2)
            
            if px_len > 0 and canvas_silh.image_data is not None:
                mm_per_px = tire_mm / px_len
                mask = canvas_silh.image_data[:, :, 3]
                total_px = np.sum(mask > 0)
                
                area_m2 = (total_px * (mm_per_px**2)) / 1_000_000
                cda = area_m2 * cd_fixed
                v_ms = (ftp_watts / (0.5 * 1.225 * cda))**(1/3)
                kmh = v_ms * 3.6

                st.session_state.setups.append({
                    "Setup": f"Posicao {len(st.session_state.setups)+1}",
                    "Area (m2)": area_m2,
                    "CdA": cda,
                    "Velocidade": kmh
                })
                st.balloons()

    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.dataframe(df[["Setup", "Area (m2)", "CdA", "Velocidade"]], hide_index=True)
        if st.button("🗑️ Limpar Tudo"):
            st.session_state.setups = []
            st.rerun()
else:
    st.info("Aguardando imagem...")
