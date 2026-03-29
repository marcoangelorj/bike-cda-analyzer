import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro v2.1", layout="wide")

# --- TRATAMENTO DE IMAGEM: SOLUÇÃO PARA TELA PRETA E CANAL ALPHA ---
def get_clean_image(uploaded_file, canvas_w=750):
    img = Image.open(uploaded_file).convert("RGBA")
    # Cria fundo branco sólido para evitar o erro de transparência do navegador
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
    pdf.cell(0, 10, f"Parametros: Pneu {tire_mm}mm | Potencia: {ftp}W", ln=True)
    pdf.ln(5)
    
    # Cabeçalho da Tabela
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(30, 10, "ID Setup", 1, 0, "C", True)
    pdf.cell(30, 10, "CdA", 1, 0, "C", True)
    pdf.cell(35, 10, "Vel. (km/h)", 1, 0, "C", True)
    pdf.cell(95, 10, "Observacoes Tecnicas", 1, 1, "C", True)
    
    pdf.set_font("helvetica", "", 9)
    for _, row in df.iterrows():
        pdf.cell(30, 10, str(row["Setup"]), 1, 0, "C")
        pdf.cell(30, 10, f"{row['CdA']:.4f}", 1, 0, "C")
        pdf.cell(35, 10, f"{row['Vel. Est.']:.1f}", 1, 0, "C")
        # Garante que as observações não quebrem a linha do PDF
        obs_texto = str(row["Obs"])[:60] if row["Obs"] else "-"
        pdf.cell(95, 10, obs_texto, 1, 1, "L")
    
    pdf.ln(10)
    pdf.set_font("helvetica", "I", 8)
    pdf.multi_cell(0, 5, "Analise baseada em simulacao matematica (rho=1.225). Resultados podem variar conforme condicoes ambientais e de asfalto.")
    
    return pdf.output()

if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuracoes")
athlete_name = st.sidebar.text_input("Nome do Atleta", "Ciclista")
uploaded_file = st.sidebar.file_uploader("Foto Frontal", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Largura Pneu (mm)", value=25.0)
ftp_watts = st.sidebar.number_input("Potencia Alvo (Watts)", value=250)
cd_val = st.sidebar.select_slider("Estimativa Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)
obs_tecnica = st.sidebar.text_area("Observacoes para este Setup", placeholder="Ex: Capacete Aero X, Clip inclinado 15 graus...")

st.title("🚴 Aero Analyzer Pro v2.1")
st.caption("Especializado em Consultoria e Treinamento Individualizado - Angelo, MSc.")

if uploaded_file:
    img_pil, c_w, c_h = get_clean_image(uploaded_file)
    
    t1, t2 = st.tabs(["📏 1. Calibrar (Zoom)", "👤 2. Silhueta (Área Frontal)"])
    
    with t1:
        st.info("Desenhe a linha vermelha na largura total do pneu dianteiro.")
        # ZOOM: Foca nos 30% inferiores para pegar o pneu com precisão
        zoom_factor = 2.0
        crop_h = int(c_h / zoom_factor)
        img_zoom = img_pil.crop((0, c_h - crop_h, c_w, c_h))
        img_zoom = img_zoom.resize((c_w, c_h), Image.Resampling.LANCZOS)
        
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_image=img_zoom, drawing_mode="line", key="c_calib",
            height=c_h, width=c_w, update_streamlit=True
        )

    with t2:
        st.info("Contorne o ciclista + bike. Clique duas vezes para fechar o polígono.")
        if st.button("🗑️ Resetar Contorno"): st.rerun()
        
        canvas_silh = st_canvas(
            fill_color="rgba(0, 255, 0, 0.4)", stroke_width=2, stroke_color="#00FF00",
            background_image=img_pil, drawing_mode="polygon", key="c_silh",
            height=c_h, width=c_w, update_streamlit=True
        )

    if st.button("🚀 CALCULAR E SALVAR SETUP", use_container_width=True):
        if canvas_calib.json_data and canvas_silh.image_data is not None:
            # Cálculo de escala considerando o zoom
            line = canvas_calib.json_data["objects"][-1]
            dx = line["width"] * line.get("scaleX", 1)
            dy = line["height"] * line.get("scaleY", 1)
            px_len_zoom = np.sqrt(dx**2 + dy**2)
            
            # Reverte o zoom para escala real da imagem original
            px_len_real = px_len_zoom / zoom_factor
            
            if px_len_real > 5: # Validação mínima
                mm_px = tire_mm / px_len_real
                mask = canvas_silh.image_data[:, :, 3]
                total_px = np.sum(mask > 0)
                
                area_m2 = (total_px * (mm_px**2)) / 1_000_000
                cda = area_m2 * cd_val
                
                # Fórmula Física de Ciclismo
                v_ms = (ftp_watts / (0.5 * 1.225 * cda))**(1/3)
                kmh = v_ms * 3.6

                st.session_state.setups.append({
                    "Setup": f"Setup {len(st.session_state.setups)+1}",
                    "CdA": cda,
                    "Vel. Est.": kmh,
                    "Area (m2)": area_m2,
                    "Obs": obs_tecnica
                })
                st.success(f"Análise concluída! CdA: {cda:.4f}")
            else:
                st.error("Linha de calibração muito curta ou inválida.")

    if st.session_state.setups:
        st.divider()
        df = pd.DataFrame(st.session_state.setups)
        
        col_res1, col_res2 = st.columns([1, 1])
        with col_res1:
            st.subheader("📋 Resultados")
            st.dataframe(df[["Setup", "CdA", "Vel. Est.", "Obs"]], hide_index=True)
            
            # Exportação PDF
            pdf_data = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
            st.download_button("📥 Baixar Laudo PDF", data=pdf_data, file_name=f"Laudo_Aero_{athlete_name}.pdf", mime="application/pdf")

        with col_res2:
            st.subheader("📊 Gráfico Comparativo CdA")
            st.bar_chart(df, x="Setup", y="CdA", color="#00FF00")
            
        if st.button("🗑️ Limpar Histórico"):
            st.session_state.setups = []
            st.rerun()
