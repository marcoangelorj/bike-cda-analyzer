import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro v10", layout="wide")

# --- TRATAMENTO DE IMAGEM COM CACHE ---
@st.cache_data
def get_processed_images(uploaded_file, canvas_w=750):
    img = Image.open(uploaded_file).convert("RGBA")
    white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    combined = Image.alpha_composite(white_bg, img).convert("RGB")
    
    w, h = combined.size
    canvas_h = int(h * (canvas_w / w))
    img_main = combined.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
    
    # Configuração do Zoom (Foco no pneu)
    zoom_factor = 2.5
    img_zoom = combined.crop((0, int(h * 0.70), w, h)) # Foca nos 30% inferiores
    img_zoom = img_zoom.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
    
    return img_main, img_zoom, canvas_w, canvas_h, zoom_factor

# --- FUNÇÃO DO PDF ---
def generate_pdf(df, tire_mm, ftp, athlete):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Laudo de Analise Aerodinamica - Angelo, MSc.", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 10, f"Atleta: {athlete} | Pneu: {tire_mm}mm | FTP: {ftp}W", ln=True)
    pdf.ln(5)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(30, 10, "Setup", 1, 0, "C", True)
    pdf.cell(30, 10, "Area (m2)", 1, 0, "C", True)
    pdf.cell(30, 10, "CdA", 1, 0, "C", True)
    pdf.cell(35, 10, "Vel. (km/h)", 1, 0, "C", True)
    pdf.cell(65, 10, "Obs", 1, 1, "C", True)
    
    pdf.set_font("helvetica", "", 9)
    for _, row in df.iterrows():
        pdf.cell(30, 10, str(row["Setup"]), 1, 0, "C")
        pdf.cell(30, 10, f"{row['Area (m2)']:.4f}", 1, 0, "C")
        pdf.cell(30, 10, f"{row['CdA']:.4f}", 1, 0, "C")
        pdf.cell(35, 10, f"{row['Vel. Est.']:.1f}", 1, 0, "C")
        pdf.cell(65, 10, str(row["Obs"])[:40], 1, 1, "L")
    
    return pdf.output()

# Inicialização do Histórico
if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.header("⚙️ Parâmetros Técnicos")
athlete_name = st.sidebar.text_input("Nome do Atleta", "Atleta Exemplo")
uploaded_file = st.sidebar.file_uploader("Upload da Foto Frontal", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Largura Real do Pneu (mm)", value=25.0, step=0.1)
ftp_watts = st.sidebar.number_input("Potência Alvo (Watts)", value=250)

# NOVA BARRA DESLIZANTE DE DISTÂNCIA
dist_km = st.sidebar.slider("Distância do Pedal (km)", min_value=20, max_value=180, value=90, step=5)

cd_val = st.sidebar.select_slider("Coeficiente Cd Estimado", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)
obs_tecnica = st.sidebar.text_area("Notas do Setup (Ex: Capacete, Clip...)")

st.title("🚴 Aero Analyzer Pro v10")
st.caption("Consultoria e Treinamento Individualizado - Prof. Angelo, MSc.")

if uploaded_file:
    img_main, img_zoom, c_w, c_h, z_factor = get_processed_images(uploaded_file)
    
    tab1, tab2 = st.tabs(["📏 1. Calibração (Zoom Pneu)", "👤 2. Silhueta (Área Frontal)"])
    
    with tab1:
        st.info("Desenhe a linha vermelha sobre a largura total do pneu.")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_image=img_zoom, drawing_mode="line", key="c_calib",
            height=c_h, width=c_w, update_streamlit=True
        )

    with tab2:
        st.info("Contorne a silhueta. Clique no primeiro ponto para fechar o polígono.")
        if st.button("🗑️ Resetar Silhueta"): st.rerun()
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.4)", stroke_width=2, stroke_color="#00FF00",
            background_image=img_main, drawing_mode="polygon", key="c_silh",
            height=c_h, width=c_w, update_streamlit=True
        )

    if st.button("🚀 CALCULAR PERFORMANCE", use_container_width=True):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            # 1. Escala (considerando o zoom de 30% inferior)
            line = canvas_calib.json_data["objects"][-1]
            dx = line["width"] * line.get("scaleX", 1)
            dy = line["height"] * line.get("scaleY", 1)
            px_zoom = np.sqrt(dx**2 + dy**2)
            
            # Ajuste de escala: o zoom amplia a imagem original. 
            # Como o crop foi redimensionado para c_w, o fator é proporcional.
            mm_px = tire_mm / (px_zoom / z_factor)
            
            if canvas_silh.image_data is not None:
                mask = canvas_silh.image_data[:, :, 3]
                pixel_count = np.sum(mask > 0)
                
                # CÁLCULOS BIOMECÂNICOS
                area_m2 = (pixel_count * (mm_px**2)) / 1_000_000
                cda = area_m2 * cd_val
                v_ms = (ftp_watts / (0.5 * 1.225 * cda))**(1/3)
                kmh = v_ms * 3.6
                
                # Tempo estimado para a distância selecionada
                tempo_seg = (dist_km * 1000) / v_ms
                m, s = divmod(int(tempo_seg), 60)
                h, m = divmod(m, 60)
                tempo_fmt = f"{h}h {m}m {s}s"

                # EXIBIÇÃO IMEDIATA DOS RESULTADOS
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Área Frontal (A)", f"{area_m2:.4f} m²")
                col_b.metric("CdA Estimado", f"{cda:.4f}")
                col_c.metric("Velocidade Est.", f"{kmh:.1f} km/h")
                
                st.info(f"⏱️ Tempo estimado para {dist_km}km: **{tempo_fmt}**")

                st.session_state.setups.append({
                    "Setup": f"Análise {len(st.session_state.setups)+1}",
                    "Area (m2)": area_m2,
                    "CdA": cda,
                    "Vel. Est.": kmh,
                    "Tempo": tempo_fmt,
                    "Dist": dist_km,
                    "Obs": obs_tecnica
                })

    if st.session_state.setups:
        st.divider()
        df = pd.DataFrame(st.session_state.setups)
        
        st.subheader("📊 Histórico de Análises")
        st.dataframe(df[["Setup", "Area (m2)", "CdA", "Vel. Est.", "Tempo", "Obs"]], hide_index=True)
        
        # Download do PDF
        pdf_bytes = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
        st.download_button("📥 Baixar Laudo Profissional (PDF)", data=pdf_bytes, file_name=f"Laudo_Aero_{athlete_name}.pdf", mime="application/pdf")
        
        if st.button("🗑️ Limpar Tudo"):
            st.session_state.setups = []
            st.rerun()
else:
    st.info("Aguardando upload da imagem frontal para iniciar a consultoria.")
