import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro v9", layout="wide")

# --- TRATAMENTO DE IMAGEM COM CACHE ---
@st.cache_data
def get_processed_images(uploaded_file, canvas_w=750):
    # Imagem original limpa (sem fundo transparente)
    img = Image.open(uploaded_file).convert("RGBA")
    white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    combined = Image.alpha_composite(white_bg, img).convert("RGB")
    
    # Versão para o canvas principal
    w, h = combined.size
    canvas_h = int(h * (canvas_w / w))
    img_main = combined.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
    
    # Versão para o Zoom de Calibração (Alta Resolução)
    # Focamos nos 25% inferiores onde o pneu costuma estar
    zoom_factor = 2.5
    crop_w = int(w / zoom_factor)
    left = (w - crop_w) // 2
    right = left + crop_w
    top = int(h * 0.75)
    bottom = h
    
    # Fazemos o crop na imagem ORIGINAL (alta resolução) para não perder pixel
    img_zoom_raw = combined.crop((left, top, right, bottom))
    # Redimensionamos para o tamanho do canvas para facilitar a marcação
    img_zoom = img_zoom_raw.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
    
    return img_main, img_zoom, canvas_w, canvas_h, zoom_factor

# --- FUNÇÃO GERADORA DE PDF ---
def generate_pdf(df, tire_mm, ftp, athlete):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Laudo de Analise Aerodinamica Frontal", ln=True, align="C")
    pdf.ln(5)
    
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 10, f"Atleta: {athlete}", ln=True)
    pdf.cell(0, 10, f"Setup: Pneu {tire_mm}mm | Potencia: {ftp}W", ln=True)
    pdf.ln(5)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(35, 10, "ID Setup", 1, 0, "C", True)
    pdf.cell(35, 10, "CdA", 1, 0, "C", True)
    pdf.cell(40, 10, "Vel. (km/h)", 1, 0, "C", True)
    pdf.cell(80, 10, "Observacoes Tecnicas", 1, 1, "C", True)
    
    pdf.set_font("helvetica", "", 9)
    for _, row in df.iterrows():
        pdf.cell(35, 10, str(row['Setup']), 1, 0, "C")
        pdf.cell(35, 10, f"{row['CdA']:.4f}", 1, 0, "C")
        pdf.cell(40, 10, f"{row['Vel. Est.']:.1f}", 1, 0, "C")
        obs_texto = str(row['Obs'])[:50] 
        pdf.cell(80, 10, obs_texto, 1, 1, "L")
    
    pdf.ln(10)
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(0, 10, "Analise baseada em simulacao matematica (rho=1.225). Resultados podem variar na estrada.", align="C")
    return pdf.output()

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if 'setups' not in st.session_state:
    st.session_state.setups = []
if 'calib_data' not in st.session_state:
    st.session_state.calib_data = None
if 'mode' not in st.session_state:
    st.session_state.mode = "calib"
if 'zoom_active' not in st.session_state:
    st.session_state.zoom_active = False
if 'last_uploaded_file' not in st.session_state:
    st.session_state.last_uploaded_file = None

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuracoes")
athlete_name = st.sidebar.text_input("Nome do Atleta", "Ciclista")
uploaded_file = st.sidebar.file_uploader("Foto Frontal", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Pneu (mm)", value=25.0)
ftp_watts = st.sidebar.number_input("Potencia (W)", value=250)
cd_val = st.sidebar.select_slider("Estimativa Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)
obs_tecnica = st.sidebar.text_area("Observacoes para este Setup", placeholder="Ex: Capacete Aero Giro, Maos juntas...")

# Resetar se o arquivo mudar
if uploaded_file and uploaded_file.name != st.session_state.last_uploaded_file:
    st.session_state.last_uploaded_file = uploaded_file.name
    st.session_state.calib_data = None
    st.session_state.mode = "calib"
    st.session_state.zoom_active = False

st.title("🚴 Aero Analyzer Pro v9")

if uploaded_file:
    img_main, img_zoom, c_w, c_h, z_factor = get_processed_images(uploaded_file)
    
    # Layout de botões superior
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    
    with col_btn1:
        if st.button("📏 1. Calibrar Pneu", use_container_width=True):
            st.session_state.mode = "calib"
            st.rerun()
            
    with col_btn2:
        if st.button("👤 2. Marcar Silhueta", use_container_width=True):
            st.session_state.mode = "silh"
            st.rerun()
            
    with col_btn3:
        if st.button("🚀 CALCULAR E SALVAR", use_container_width=True):
            st.session_state.execute_calc = True
            
    with col_btn4:
        if st.button("🗑️ Reiniciar Tudo", use_container_width=True):
            st.session_state.setups = []
            st.session_state.calib_data = None
            st.session_state.mode = "calib"
            st.rerun()

    # Área de Trabalho
    col_canvas, col_tools = st.columns([4, 1])
    
    with col_tools:
        st.subheader("Ferramentas")
        st.write(f"Modo: **{st.session_state.mode.upper()}**")
        
        if st.session_state.mode == "calib":
            st.info("Trace uma linha vermelha no pneu.")
            if st.button("🔍 Alternar Zoom", use_container_width=True):
                st.session_state.zoom_active = not st.session_state.zoom_active
                st.rerun()
        else:
            st.info("Clique nos pontos para a silhueta verde.")
            if st.button("🗑️ Limpar Silhueta", use_container_width=True):
                # Usamos uma chave dinâmica para o canvas da silhueta para limpá-lo
                if 'silh_key_ver' not in st.session_state: st.session_state.silh_key_ver = 0
                st.session_state.silh_key_ver += 1
                st.rerun()

    with col_canvas:
        # Determinar imagem de fundo e configurações do canvas
        if st.session_state.mode == "calib" and st.session_state.zoom_active:
            bg_img = img_zoom
            d_mode = "line"
        elif st.session_state.mode == "calib":
            bg_img = img_main
            d_mode = "line"
        else:
            bg_img = img_main
            d_mode = "polygon"

        # Chave única para evitar conflitos de estado entre modos
        canvas_key = f"canvas_{st.session_state.mode}_{st.session_state.get('silh_key_ver', 0)}"
        
        canvas_result = st_canvas(
            fill_color="rgba(0,255,0,0.3)" if st.session_state.mode == "silh" else "rgba(255,0,0,0.3)",
            stroke_width=3 if st.session_state.mode == "calib" else 2,
            stroke_color="#FF0000" if st.session_state.mode == "calib" else "#00FF00",
            background_image=bg_img,
            drawing_mode=d_mode,
            key=canvas_key,
            height=c_h, width=c_w, update_streamlit=True
        )

        # Capturar calibração imediatamente após o desenho
        if st.session_state.mode == "calib" and canvas_result.json_data:
            objs = canvas_result.json_data.get("objects", [])
            if len(objs) > 0:
                line = objs[-1]
                dx = line["width"] * line["scaleX"]
                dy = line["height"] * line["scaleY"]
                px_len = np.sqrt(dx**2 + dy**2)
                
                # Ajustar pelo fator de zoom se ativo
                px_len_real = px_len / z_factor if st.session_state.zoom_active else px_len
                
                if px_len_real > 0:
                    st.session_state.calib_data = tire_mm / px_len_real

    # Processamento do Cálculo (fora do bloco do canvas para estabilidade)
    if st.session_state.get('execute_calc'):
        st.session_state.execute_calc = False # Resetar flag
        
        if st.session_state.calib_data and canvas_result.image_data is not None:
            # Pegar a máscara da silhueta (canal alpha)
            mask = canvas_result.image_data[:, :, 3]
            pixel_count = np.sum(mask > 0)
            
            if pixel_count > 10: # Evitar cliques acidentais
                mm_px = st.session_state.calib_data
                area_m2 = (pixel_count * (mm_px**2)) / 1_000_000
                cda = area_m2 * cd_val
                kmh = ((ftp_watts / (0.5 * 1.225 * cda))**(1/3)) * 3.6

                st.session_state.setups.append({
                    "Setup": f"Posicao {len(st.session_state.setups)+1}",
                    "Area (m2)": area_m2,
                    "CdA": cda,
                    "Vel. Est.": kmh,
                    "Obs": obs_tecnica
                })
                st.success(f"Análise salva com sucesso! CdA: {cda:.4f}")
            else:
                st.warning("⚠️ Desenhe a silhueta antes de calcular.")
        else:
            if not st.session_state.calib_data:
                st.error("❌ Erro: Calibre o pneu na aba 1 primeiro.")
            else:
                st.error("❌ Erro: Dados da silhueta não encontrados.")

    # Exibição dos Resultados
    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.subheader("📊 Resultados Comparativos")
        st.dataframe(df[["Setup", "CdA", "Vel. Est.", "Obs"]], hide_index=True)
        
        pdf_bytes = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
        st.download_button("📥 Baixar Laudo PDF", data=pdf_bytes, file_name=f"Laudo_{athlete_name}.pdf", mime="application/pdf")
