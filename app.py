import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro", layout="wide")

# FUNÇÃO DE TRATAMENTO: Garante fundo branco e evita erro de URL no Render
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

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR: PARÂMETROS TÉCNICOS ---
st.sidebar.header("⚙️ Parâmetros de Performance")
athlete = st.sidebar.text_input("Atleta", "Triatleta Pro")
uploaded_file = st.sidebar.file_uploader("1. Foto Frontal (PNG/JPG)", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("2. Largura do Pneu (mm)", value=25.0, step=0.1)
ftp_watts = st.sidebar.number_input("3. Potência Alvo (Watts)", value=250)
dist_km = st.sidebar.selectbox("4. Distância da Prova (km)", [10, 20, 40, 90, 180], index=2)

cd_val = st.sidebar.select_slider(
    "5. Estimativa de Cd",
    options=np.around(np.arange(0.22, 0.41, 0.01), 2),
    value=0.30,
    help="0.22-0.28: Elite TT | 0.30: Amador TT | 0.40: Road Bike"
)

# --- CORPO DO APP ---
st.title("🚴 Aero Analyzer & TT Predictor")
st.markdown(f"**Atleta:** {athlete} | **Ambiente:** Nível do Mar (ρ = 1.225 kg/m³)")

if uploaded_file:
    img_b64, c_w, c_h = get_clean_base64(uploaded_file)

    tab1, tab2 = st.tabs(["📏 1. Calibração (Pneu)", "👤 2. Silhueta (Área Frontal)"])

    with tab1:
        st.info("Desenhe uma linha horizontal exatamente sobre a largura do pneu.")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_color=img_b64, drawing_mode="line", key="c_calib",
            height=c_h, width=c_w, update_streamlit=True
        )

    with tab2:
        st.info("Contorne a silhueta completa (Ciclista + Bike). Clique no primeiro ponto para fechar.")
        if st.button("🗑️ Resetar Contorno"): st.rerun()
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.4)", stroke_width=2, stroke_color="#00FF00",
            background_color=img_b64, drawing_mode="polygon", key="c_silh",
            height=c_h, width=c_w, update_streamlit=True
        )

    # --- BOTÃO DE ANÁLISE DE PERFORMANCE ---
    if st.button("🚀 ANALISAR CdA E PERFORMANCE", use_container_width=True):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            line = canvas_calib.json_data["objects"][-1]
            px_len = np.sqrt(line["width"]**2 + line["height"]**2)
            
            if px_len > 0 and canvas_silh.image_data is not None:
                # 1. Escala
                mm_px = tire_mm / px_len
                # 2. Área Frontal (A)
                mask = canvas_silh.image_data[:, :, 3]
                total_px = np.sum(mask > 0)
                area_m2 = (total_px * (mm_px**2)) / 1_000_000
                
                # 3. CdA
                cda = area_m2 * cd_val
                
                # 4. Física: v = (P / (0.5 * rho * CdA))^(1/3)
                v_ms = (ftp_watts / (0.5 * 1.225 * cda))**(1/3)
                kmh = v_ms * 3.6
                
                # 5. Tempo
                tempo_seg = (dist_km * 1000) / v_ms
                mins, segs = divmod(int(tempo_seg), 60)
                horas, mins = divmod(mins, 60)
                tempo_fmt = f"{horas}h {mins}m {segs}s" if horas > 0 else f"{mins}m {segs}s"

                st.session_state.setups.append({
                    "Setup": f"Análise {len(st.session_state.setups)+1}",
                    "Área (m²)": round(area_m2, 4),
                    "CdA": round(cda, 4),
                    "Vel. Est.": round(kmh, 1),
                    "Tempo": tempo_fmt,
                    "CdA_val": cda # Para o gráfico
                })
                st.success("Análise concluída e salva no histórico!")

    # --- DASHBOARD DE RESULTADOS ---
    if st.session_state.setups:
        st.divider()
        df = pd.DataFrame(st.session_state.setups)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("📋 Tabela Comparativa")
            st.dataframe(df[["Setup", "Área (m²)", "CdA", "Vel. Est.", "Tempo"]], hide_index=True)
            if st.button("🗑️ Limpar Histórico"):
                st.session_state.setups = []
                st.rerun()
        
        with col2:
            st.subheader("📊 Gráfico de Eficiência (CdA)")
            st.bar_chart(df, x="Setup", y="CdA_val", color="#00FF00")
            st.caption("Quanto menor o CdA, menor a resistência aerodinâmica.")

else:
    st.info("Aguardando upload da imagem frontal (PNG com fundo branco) para iniciar.")
