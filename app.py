   import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro", layout="wide")

# --- TRATAMENTO DE IMAGEM (ESTABILIDADE TOTAL) ---
def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background
    return img.convert("RGB")

# --- FUNÇÃO GERADORA DE PDF ---
def generate_pdf(df, tire_mm, ftp):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "Relatorio de Analise Aerodinamica", ln=True, align='C')
    
    pdf.set_font("Arial", '', 12)
    pdf.ln(10)
    pdf.cell(200, 10, f"Parametros: Pneu {tire_mm}mm | Potencia Base: {ftp}W", ln=True)
    pdf.ln(5)
    
    # Cabeçalho da Tabela
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(40, 10, "Setup", 1, 0, 'C', True)
    pdf.cell(50, 10, "Area (m2)", 1, 0, 'C', True)
    pdf.cell(50, 10, "CdA", 1, 0, 'C', True)
    pdf.cell(50, 10, "Velocidade", 1, 1, 'C', True)
    
    # Dados
    for index, row in df.iterrows():
        pdf.cell(40, 10, str(row['Setup']), 1)
        pdf.cell(50, 10, f"{row['Area (m2)']:.4f}", 1)
        pdf.cell(50, 10, f"{row['CdA']:.4f}", 1)
        pdf.cell(50, 10, f"{row['Velocidade']:.1f} km/h", 1, 1)
        
    return pdf.output(dest='S').encode('latin-1')

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configurações Técnicas")
uploaded_file = st.sidebar.file_uploader("Upload PNG (Fundo Branco)", type=["png", "jpg"])
tire_mm = st.sidebar.number_input("Largura do Pneu (mm)", value=25.0, step=0.1)
ftp_watts = st.sidebar.number_input("Sua Potência (Watts)", value=250)
cd_fixed = st.sidebar.select_slider("Coeficiente Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

# --- CORPO DO APP ---
st.title("🚴 Aero Performance Lab")
st.markdown("---")

if uploaded_file:
    img_clean = process_image(uploaded_file)
    canvas_w = 700
    w, h = img_clean.size
    canvas_h = int(h * (canvas_w / w))
    img_resized = img_clean.resize((canvas_w, canvas_h))

    t1, t2 = st.tabs(["📏 1. Calibrar Pneu", "👤 2. Contornar Silhueta"])

    with t1:
        st.info("Desenhe a linha sobre a largura do pneu (25mm padrão).")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_image=img_resized, drawing_mode="line", key="c_calib",
            height=canvas_h, width=canvas_w
        )

    with t2:
        st.info("Clique nos pontos para contornar o atleta. Feche o poligono clicando no ponto inicial.")
        if st.button("🗑️ Resetar Contorno"): st.rerun()
        
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.4)", stroke_width=2, stroke_color="#00FF00",
            background_image=img_resized, drawing_mode="polygon", key="c_silh",
            height=canvas_h, width=canvas_w
        )

    if st.button("🚀 ANALISAR AGORA", use_container_width=True):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            line = canvas_calib.json_data["objects"][-1]
            px_len = np.sqrt(line["width"]**2 + line["height"]**2)
            
            if px_len > 0 and canvas_silh.image_data is not None:
                mm_per_px = tire_mm / px_len
                mask = canvas_silh.image_data[:, :, 3]
                total_px = np.sum(mask > 0)
                
                area_m2 = (total_px * (mm_per_px**2)) / 1_000_000
                cda = area_m2 * cd_fixed
                
                # Física: v = (P / (0.5 * rho * CdA))^(1/3)
                v_ms = (ftp_watts / (0.5 * 1.225 * cda))**(1/3)
                kmh = v_ms * 3.6

                st.session_state.setups.append({
                    "Setup": f"Posicao {len(st.session_state.setups)+1}",
                    "Area (m2)": area_m2,
                    "CdA": cda,
                    "Velocidade": kmh
                })
                st.balloons()

    # --- DASHBOARD E EXPORTAÇÃO ---
    if st.session_state.setups:
        st.divider()
        df = pd.DataFrame(st.session_state.setups)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.subheader("📋 Resultados")
            st.dataframe(df[["Setup", "Area (m2)", "CdA", "Velocidade"]], hide_index=True)
            
            # Botão de Download PDF
            pdf_data = generate_pdf(df, tire_mm, ftp_watts)
            st.download_button("📥 Baixar Relatorio PDF", data=pdf_data, file_name="analise_aero.pdf", mime="application/pdf")
            
            if st.button("🗑️ Limpar Tudo"):
                st.session_state.setups = []
                st.rerun()
        
        with c2:
            st.subheader("📊 Comparativo CdA")
            st.bar_chart(df, x="Setup", y="CdA", color="#00FF00")

else:
    st.info("Aguardando imagem PNG com fundo branco para iniciar.")
