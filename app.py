import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Aero Analyzer Pro", layout="wide")

# FUNÇÃO DE PROCESSAMENTO: Garante fundo branco e remove canal Alpha
def get_clean_base64(uploaded_file):
    img = Image.open(uploaded_file)
    
    # 1. Converte para RGBA para garantir que temos acesso ao canal de transparência
    img = img.convert("RGBA")
    
    # 2. Cria um fundo branco sólido do mesmo tamanho da imagem
    white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    
    # 3. Sobrepõe a imagem original no fundo branco (remove transparência)
    combined = Image.alpha_composite(white_bg, img).convert("RGB")
    
    # 4. Redimensiona para o Canvas para manter performance
    canvas_w = 700
    w, h = combined.size
    canvas_h = int(h * (canvas_w / w))
    img_resized = combined.resize((canvas_w, canvas_h))
    
    # 5. Converte para Base64 (JPEG é mais seguro para evitar erros de leitura)
    buffered = io.BytesIO()
    img_resized.save(buffered, format="JPEG", quality=90)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/jpeg;base64,{img_str}", canvas_w, canvas_h

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.header("⚙️ Parâmetros")
uploaded_file = st.sidebar.file_uploader("Upload PNG (Fundo Branco)", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Largura Pneu (mm)", value=25.0)

st.title("🚴 Aero Performance Lab")

if uploaded_file:
    # Obtém a imagem limpa e as dimensões calculadas
    img_b64, c_w, c_h = get_clean_base64(uploaded_file)

    t1, t2 = st.tabs(["📏 1. Calibrar", "👤 2. Silhueta"])

    with t1:
        st.write("Desenhe a linha no pneu.")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_color=img_b64, # Injeção direta via Base64
            drawing_mode="line",
            key="calib_final",
            height=c_h,
            width=c_w,
            update_streamlit=True
        )

    with t2:
        st.write("Contorne o atleta.")
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.4)",
            stroke_width=2,
            stroke_color="#00FF00",
            background_color=img_b64, # Injeção direta via Base64
            drawing_mode="polygon",
            key="silh_final",
            height=c_h,
            width=c_w,
            update_streamlit=True
        )

    # Processamento de dados (CdA)
    if st.button("🚀 ANALISAR"):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            line = canvas_calib.json_data["objects"][-1]
            px_len = np.sqrt(line["width"]**2 + line["height"]**2)
            if px_len > 0 and canvas_silh.image_data is not None:
                mm_px = tire_mm / px_len
                mask = canvas_silh.image_data[:, :, 3]
                total_px = np.sum(mask > 0)
                area = (total_px * (mm_px**2)) / 1_000_000
                st.metric("Área Frontal Calculada", f"{area:.4f} m²")
else:
    st.info("Aguardando upload da imagem...")
