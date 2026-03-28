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
    # Remove transparência de PNGs e garante fundo branco
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background
    return img.convert("RGB")

# --- FUNÇÃO GERADORA DE PDF (Usando fpdf2) ---
def generate_pdf(df, tire_mm, ftp, athlete_name):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Relatorio de Analise Aerodinamica Frontal", ln=True, align="C")
    
    # Dados do Atleta
    pdf.set_font("helvetica", "", 12)
    pdf.ln(5)
    pdf.cell(0, 10, f"Atleta: {athlete_name}", ln=True)
    pdf.cell(0, 10, f"Parametros: Pneu {tire_mm}mm | Potencia Alvo: {ftp}W", ln=True)
    pdf.ln(10)
    
    # Tabela de Resultados
    pdf.set_font("helvetica", "B", 11)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(40, 10, "Setup", 1, 0, "C", True)
    pdf.cell(40, 10, "Area (m2)", 1, 0, "C", True)
    pdf.cell(40, 10, "CdA", 1, 0, "C", True)
    pdf.cell(40, 10, "Vel. Est. (km/h)", 1, 1, "C", True)
    
    pdf.set_font("helvetica", "", 11)
    for _, row in df.iterrows():
        pdf.cell(40, 10, str(row["Setup"]), 1, 0, "C")
        pdf.cell(40, 10, f"{row['Area (m2)']:.4f}", 1, 0, "C")
        pdf.cell(40, 10, f"{row['CdA']:.4f}", 1, 0, "C")
        pdf.cell(40, 10, f"{row['Velocidade']:.1f}", 1, 1, "C")
        
    pdf.ln(10)
    pdf.set_font("helvetica", "I", 9)
    pdf.multi_cell(0, 5, "Nota: Os calculos consideram densidade do ar de 1.225 kg/m3 (nivel do mar) e o coeficiente de arrasto (Cd) selecionado no momento da analise.")
    
    # Retorna o PDF como bytes
    return pdf.output()

if "setups" not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.header("👤 Perfil do Atleta")
athlete_name = st.sidebar.text_input("Nome do Atleta", value="Ciclista Pro")
st.sidebar.divider()
st.sidebar.header("⚙️ Parametros")
uploaded_file = st.sidebar.file_uploader("Upload PNG (Fundo Branco)", type=["png", "jpg"])
tire_mm = st.sidebar.number_input("Largura do Pneu (mm)", value=25.0, step=0.1)
ftp_watts = st.sidebar.number_input("Potencia de Referencia (Watts)", value=250)
cd_fixed = st.sidebar.select_slider("Coeficiente Cd (0.22 - 0.40)", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

# --- CORPO DO APP ---
st.title("🚴 Aero Performance Lab")
st.markdown("Analise de Area Frontal para Contra-Relogio e Triatlo")

if uploaded_file:
    img_clean = process_image(uploaded_file)
    canvas_w = 700
    w, h = img_clean.size
    canvas_h = int(h * (canvas_w / w))
    img_resized = img_clean.resize((canvas_w, canvas_h))

    t1, t2 = st.tabs(["📏 1. Calibrar Escala", "👤 2. Mapear Silhueta"])

    with t1:
        st.info("Desenhe a linha sobre a largura do pneu para calibrar a escala real.")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_image=img_resized, drawing_mode="line", key="c_calib",
            height=canvas_h, width=canvas_w
        )

    with t2:
        st.info("Contorne o atleta (Poligono). Clique no primeiro ponto para fechar.")
        if st.button("🗑️ Resetar Contorno"): st.rerun()
        
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.4)", stroke_width=2, stroke_color="#00FF00",
            background_image=img_resized, drawing_mode="polygon", key="c_silh",
            height=canvas_h, width=canvas_w
        )

    if st.button("🚀 ANALISAR POSICAO", use_container_width=True):
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
                    "Setup": f"Analise {len(st.session_state.setups)+1}",
                    "Area (m2)": area_m2,
                    "CdA": cda,
                    "Velocidade": kmh
                })
                st.balloons()

    if st.session_state.setups:
        st.divider()
        df = pd.DataFrame(st.session_state.setups)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.subheader("📋 Tabela Comparativa")
            st.dataframe(df[["Setup", "Area (m2)", "CdA", "Velocidade"]], hide_index=True)
            
            # Geração de PDF via botão
            try:
                pdf_bytes = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
                st.download_button(
                    label="📥 Baixar Relatorio PDF",
                    data=pdf_bytes,
                    file_name=f"Relatorio_Aero_{athlete_name.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
            
            if st.button("🗑️ Limpar Historico"):
                st.session_state.setups = []
                st.rerun()
        
        with c2:
            st.subheader("📊 Eficiencia Aerodinamica (CdA)")
            st.bar_chart(df, x="Setup", y="CdA", color="#00FF00")

else:
    st.info("👈 Faca o upload da imagem modelo PNG com fundo branco para iniciar.")
