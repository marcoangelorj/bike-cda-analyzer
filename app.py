import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro v8", layout="wide")

# --- TRATAMENTO DE IMAGEM ---
@st.cache_data
def get_clean_image(uploaded_file, canvas_w=750):
    img = Image.open(uploaded_file).convert("RGBA")
    white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    combined = Image.alpha_composite(white_bg, img).convert("RGB")
    
    w, h = combined.size
    canvas_h = int(h * (canvas_w / w))
    img_resized = combined.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
    return img_resized, canvas_w, canvas_h

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

# --- ESTADO DA SESSÃO ---
if 'setups' not in st.session_state:
    st.session_state.setups = []
if 'calib_data' not in st.session_state:
    st.session_state.calib_data = None
if 'mode' not in st.session_state:
    st.session_state.mode = "calib" # "calib" ou "silh"
if 'zoom_active' not in st.session_state:
    st.session_state.zoom_active = False

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuracoes")
athlete_name = st.sidebar.text_input("Nome do Atleta", "Ciclista")
uploaded_file = st.sidebar.file_uploader("Foto Frontal", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Pneu (mm)", value=25.0)
ftp_watts = st.sidebar.number_input("Potencia (W)", value=250)
cd_val = st.sidebar.select_slider("Estimativa Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)
obs_tecnica = st.sidebar.text_area("Observacoes para este Setup", placeholder="Ex: Capacete Aero Giro, Maos juntas...")

st.title("🚴 Aero Analyzer Pro v8 (Aba Única)")

if uploaded_file:
    img_pil, c_w, c_h = get_clean_image(uploaded_file)
    
    # Interface de controle na parte superior
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
            st.session_state.do_calc = True
            
    with col_btn4:
        if st.button("🗑️ Reiniciar Tudo", use_container_width=True):
            st.session_state.setups = []
            st.session_state.calib_data = None
            st.session_state.mode = "calib"
            st.rerun()

    # Área de Desenho
    col_canvas, col_tools = st.columns([4, 1])
    
    with col_tools:
        st.write(f"**Modo Atual:** {'Calibração' if st.session_state.mode == 'calib' else 'Silhueta'}")
        
        if st.session_state.mode == "calib":
            st.info("Desenhe uma linha vermelha sobre o pneu.")
            if st.button("🔍 Zoom Horizontal"):
                st.session_state.zoom_active = not st.session_state.zoom_active
                st.rerun()
        else:
            st.info("Clique nos pontos para marcar a silhueta em verde.")
            if st.button("↩️ Apagar Último Ponto"):
                # O drawable-canvas não expõe o histórico de pontos do polígono facilmente via Python para deleção unitária
                # Mas podemos sugerir o reset ou usar o modo 'transform' para mover pontos se necessário.
                st.warning("Use o botão de limpar abaixo para recomeçar a silhueta.")
            if st.button("🗑️ Limpar Silhueta"):
                st.rerun()

    with col_canvas:
        zoom_factor = 2.5
        if st.session_state.mode == "calib" and st.session_state.zoom_active:
            crop_w = int(c_w / zoom_factor)
            left = (c_w - crop_w) // 2
            right = left + crop_w
            top = int(c_h * 0.75)
            bottom = c_h
            img_display = img_pil.crop((left, top, right, bottom))
            img_display = img_display.resize((c_w, c_h), Image.Resampling.LANCZOS)
        else:
            img_display = img_pil

        # Canvas Único
        canvas_result = st_canvas(
            fill_color="rgba(0,255,0,0.3)" if st.session_state.mode == "silh" else "rgba(255,0,0,0.3)",
            stroke_width=3 if st.session_state.mode == "calib" else 2,
            stroke_color="#FF0000" if st.session_state.mode == "calib" else "#00FF00",
            background_image=img_display,
            drawing_mode="line" if st.session_state.mode == "calib" else "polygon",
            key=f"canvas_{st.session_state.mode}_{uploaded_file.name}",
            height=c_h, width=c_w, update_streamlit=True
        )

        # Processar Calibração
        if st.session_state.mode == "calib" and canvas_result.json_data:
            objs = canvas_result.json_data["objects"]
            if len(objs) > 0:
                line = objs[-1]
                dx = line["width"] * line["scaleX"]
                dy = line["height"] * line["scaleY"]
                px_len = np.sqrt(dx**2 + dy**2)
                
                # Ajustar pelo zoom se necessário
                px_len_real = px_len / zoom_factor if st.session_state.zoom_active else px_len
                
                if px_len_real > 0:
                    st.session_state.calib_data = tire_mm / px_len_real
                    # Desativa zoom após marcar
                    if st.session_state.zoom_active:
                        st.session_state.zoom_active = False
                        st.rerun()

    # Lógica de Cálculo
    if 'do_calc' in st.session_state and st.session_state.do_calc:
        del st.session_state.do_calc
        if st.session_state.calib_data and canvas_result.image_data is not None:
            mask = canvas_result.image_data[:, :, 3]
            pixel_count = np.sum(mask > 0)
            
            if pixel_count > 0:
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
                st.success(f"Análise salva! CdA: {cda:.4f}")
            else:
                st.warning("Marque a silhueta antes de calcular.")
        else:
            st.warning("Calibre o pneu e marque a silhueta primeiro.")

    # Tabela de Resultados
    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.subheader("📊 Comparativo de Eficiencia")
        st.dataframe(df[["Setup", "CdA", "Vel. Est.", "Obs"]], hide_index=True)
        
        pdf_bytes = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
        st.download_button("📥 Gerar Laudo PDF", data=pdf_bytes, file_name=f"Laudo_{athlete_name}.pdf", mime="application/pdf")
