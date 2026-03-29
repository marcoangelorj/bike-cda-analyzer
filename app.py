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

# --- TRATAMENTO DE IMAGEM: SOLUÇÃO PARA TELA PRETA E CANAL ALPHA ---
def get_clean_base64(uploaded_file):
    # Abrir imagem e garantir modo RGBA para lidar com transparência
    img = Image.open(uploaded_file).convert("RGBA")
    
    # Criar um fundo branco sólido do mesmo tamanho
    white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    
    # Compor a imagem sobre o fundo branco (resolve problemas de transparência PNG)
    combined = Image.alpha_composite(white_bg, img).convert("RGB")
    
    # Redimensionamento proporcional para o canvas
    canvas_w = 750
    w, h = combined.size
    canvas_h = int(h * (canvas_w / w))
    img_resized = combined.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
    
    # Salvar como JPEG em memória para o Data URL (mais leve e compatível)
    buffered = io.BytesIO()
    img_resized.save(buffered, format="JPEG", quality=90)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/jpeg;base64,{img_str}", canvas_w, canvas_h

# --- FUNÇÃO GERADORA DE PDF COM OBSERVAÇÕES ---
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
    
    # Tabela
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(35, 10, "ID Setup", 1, 0, "C", True)
    pdf.cell(35, 10, "CdA", 1, 0, "C", True)
    pdf.cell(40, 10, "Vel. (km/h)", 1, 0, "C", True)
    pdf.cell(80, 10, "Observacoes Tecnicas", 1, 1, "C", True)
    
    pdf.set_font("helvetica", "", 9)
    for _, row in df.iterrows():
        pdf.cell(35, 10, str(row["Setup"]), 1, 0, "C")
        pdf.cell(35, 10, f"{row['CdA']:.4f}", 1, 0, "C")
        pdf.cell(40, 10, f"{row['Vel. Est.']:.1f}", 1, 0, "C")
        # Garante que o texto não saia da célula
        obs_texto = str(row["Obs"])[:50] 
        pdf.cell(80, 10, obs_texto, 1, 1, "L")
    
    pdf.ln(10)
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(0, 10, "Analise baseada em simulacao matematica (rho=1.225). Resultados podem variar na estrada.", align="C")
    
    return pdf.output()

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuracoes")
athlete_name = st.sidebar.text_input("Nome do Atleta", "Ciclista")
uploaded_file = st.sidebar.file_uploader("Foto Frontal", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Pneu (mm)", value=25.0)
ftp_watts = st.sidebar.number_input("Potencia (W)", value=250)
cd_val = st.sidebar.select_slider("Estimativa Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

# CAMPO DE OBSERVAÇÃO TÉCNICA
obs_tecnica = st.sidebar.text_area("Observacoes para este Setup", placeholder="Ex: Capacete Aero Giro, Maos juntas...")

st.title("🚴 Aero Analyzer Pro + PDF Report")

if uploaded_file:
    # Obtém a imagem processada para o fundo do canvas
    img_b64, c_w, c_h = get_clean_base64(uploaded_file)
    
    t1, t2 = st.tabs(["📏 1. Calibrar", "👤 2. Silhueta"])

    with t1:
        st.info("Desenhe uma linha sobre o pneu para calibrar a escala.")
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_image=Image.open(uploaded_file).convert("RGB").resize((c_w, c_h)), 
            drawing_mode="line", key="c_calib",
            height=c_h, width=c_w, update_streamlit=True
        )

    with t2:
        st.info("Desenhe um polígono ao redor da silhueta do ciclista.")
        if st.button("🗑️ Limpar Silhueta"): 
            st.rerun()
            
        # IMPORTANTE: Usamos background_image em vez de background_color para o canvas_drawable
        # No streamlit-drawable-canvas, background_color espera uma cor ou um Data URL, 
        # mas background_image é mais robusto para exibir fotos.
        canvas_silh = st_canvas(
            fill_color="rgba(0,255,0,0.4)", stroke_width=2, stroke_color="#00FF00",
            background_image=Image.open(uploaded_file).convert("RGB").resize((c_w, c_h)),
            drawing_mode="polygon", key="c_silh",
            height=c_h, width=c_w, update_streamlit=True
        )

    if st.button("🚀 CALCULAR E SALVAR SETUP", use_container_width=True):
        # Validação se os dados necessários existem
        has_calib = canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0
        has_silh = canvas_silh.image_data is not None
        
        if has_calib and has_silh:
            # Pegar a última linha desenhada para calibração
            line = canvas_calib.json_data["objects"][-1]
            # No fabric.js (usado pelo canvas), linhas têm x1, y1, x2, y2
            x1, y1 = line["left"], line["top"]
            # Para o modo 'line', o fabric armazena como um objeto com width e height relativos
            dx = line["width"] * line["scaleX"]
            dy = line["height"] * line["scaleY"]
            px_len = np.sqrt(dx**2 + dy**2)
            
            if px_len > 0:
                mm_px = tire_mm / px_len
                # O image_data contém o desenho do usuário (polígono)
                # A área é calculada baseada nos pixels onde o alpha > 0
                mask = canvas_silh.image_data[:, :, 3]
                pixel_count = np.sum(mask > 0)
                
                area_m2 = (pixel_count * (mm_px**2)) / 1_000_000
                cda = area_m2 * cd_val
                # Fórmula de potência aerodinâmica: P = 0.5 * rho * CdA * v^3
                # v = (P / (0.5 * rho * CdA))^(1/3)
                kmh = ((ftp_watts / (0.5 * 1.225 * cda))**(1/3)) * 3.6

                st.session_state.setups.append({
                    "Setup": f"Posicao {len(st.session_state.setups)+1}",
                    "Area (m2)": area_m2,
                    "CdA": cda,
                    "Vel. Est.": kmh,
                    "Obs": obs_tecnica
                })
                st.success(f"Analise salva! CdA estimado: {cda:.4f}")
            else:
                st.error("Linha de calibração inválida.")
        else:
            st.warning("Certifique-se de calibrar (aba 1) e desenhar a silhueta (aba 2) antes de calcular.")

    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.subheader("📊 Comparativo de Eficiencia")
        st.dataframe(df[["Setup", "CdA", "Vel. Est.", "Obs"]], hide_index=True)
        
        pdf_bytes = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
        st.download_button("📥 Gerar Laudo PDF", data=pdf_bytes, file_name=f"Laudo_{athlete_name}.pdf", mime="application/pdf")
        
        if st.button("🗑️ Reiniciar Tudo"):
            st.session_state.setups = []
            st.rerun()
