import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro v6", layout="wide")

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
    # Correção: Use aspas simples dentro da f-string que usa aspas duplas
    pdf.cell(40, 10, "Vel. (km/h)", 1, 0, "C", True)
    pdf.cell(80, 10, "Observacoes Tecnicas", 1, 1, "C", True)
    
    pdf.set_font("helvetica", "", 9)
    for _, row in df.iterrows():
        pdf.cell(35, 10, str(row["Setup"]), 1, 0, "C")
        # CORREÇÃO DE SINTAXE AQUI: Usando aspas simples para chaves do dicionário
        pdf.cell(35, 10, f"{row['CdA']:.4f}", 1, 0, "C")
        pdf.cell(40, 10, f"{row['Vel. Est.']:.1f}", 1, 0, "C")
        obs_texto = str(row["Obs"])[:50] 
        pdf.cell(80, 10, obs_texto, 1, 1, "L")
    
    pdf.ln(10)
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(0, 10, "Analise baseada em simulacao matematica (rho=1.225). Resultados podem variar na estrada.", align="C")
    return pdf.output()

# Inicializar estado da sessão
if 'setups' not in st.session_state:
    st.session_state.setups = []
if 'calib_data' not in st.session_state:
    st.session_state.calib_data = None

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuracoes")
athlete_name = st.sidebar.text_input("Nome do Atleta", "Ciclista")
uploaded_file = st.sidebar.file_uploader("Foto Frontal", type=["png", "jpg", "jpeg"])
tire_mm = st.sidebar.number_input("Pneu (mm)", value=25.0)
ftp_watts = st.sidebar.number_input("Potencia (W)", value=250)
cd_val = st.sidebar.select_slider("Estimativa Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)
obs_tecnica = st.sidebar.text_area("Observacoes para este Setup", placeholder="Ex: Capacete Aero Giro, Maos juntas...")

st.title("🚴 Aero Analyzer Pro v6")

if uploaded_file:
    # Processar imagem base
    img_pil, c_w, c_h = get_clean_image(uploaded_file)
    
    # Criar abas
    t1, t2 = st.tabs(["📏 1. Calibrar", "👤 2. Silhueta"])

    with t1:
        st.info("Clique no botão para ativar o zoom horizontal e marcar o pneu com precisão. O zoom desativa automaticamente após a marcação.")
        
        if 'zoom_active_calib' not in st.session_state:
            st.session_state.zoom_active_calib = False

        col_zoom_btn, _ = st.columns([1, 3])
        with col_zoom_btn:
            if st.button("Ativar/Desativar Zoom Horizontal"):
                st.session_state.zoom_active_calib = not st.session_state.zoom_active_calib
                st.rerun()
        
        zoom_factor_h = 2.5
        if st.session_state.zoom_active_calib:
            # Zoom horizontal focado na parte inferior central
            crop_w = int(c_w / zoom_factor_h)
            left = (c_w - crop_w) // 2
            right = left + crop_w
            top = int(c_h * 0.75)
            bottom = c_h
            
            img_display = img_pil.crop((left, top, right, bottom))
            img_display = img_display.resize((c_w, c_h), Image.Resampling.LANCZOS)
        else:
            img_display = img_pil
            
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_image=img_display, drawing_mode="line", key="c_calib",
            height=c_h, width=c_w, update_streamlit=True
        )
        
        # Salvar calibração no estado da sessão
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            st.session_state.calib_data = {
                "line": canvas_calib.json_data["objects"][-1],
                "zoom_h_active": st.session_state.zoom_active_calib,
                "zoom_factor_h": zoom_factor_h
            }
            # Desativar o zoom automaticamente após a marcação
            if st.session_state.zoom_active_calib:
                st.session_state.zoom_active_calib = False
                st.rerun()

    with t2:
        col_main, col_ctrl = st.columns([4, 1])
        with col_main:
            st.info("Marque a silhueta clicando nos pontos. A imagem aparece instantaneamente abaixo.")
            canvas_silh = st_canvas(
                fill_color="rgba(0,255,0,0.4)", stroke_width=2, stroke_color="#00FF00",
                background_image=img_pil, drawing_mode="polygon", key="c_silh",
                height=c_h, width=c_w, update_streamlit=True
            )
        
        with col_ctrl:
            st.write("### Ações")
            if st.button("🚀 CALCULAR E SALVAR", use_container_width=True):
                has_calib = st.session_state.calib_data is not None
                has_silh = canvas_silh.image_data is not None
                
                if has_calib and has_silh:
                    calib = st.session_state.calib_data
                    line = calib["line"]
                    zoom_h_active = calib["zoom_h_active"]
                    z_factor = calib["zoom_factor_h"]
                    
                    dx = line["width"] * line["scaleX"]
                    dy = line["height"] * line["scaleY"]
                    px_len_canvas = np.sqrt(dx**2 + dy**2)
                    
                    # Ajustar px_len se o zoom horizontal estava ativo
                    px_len_real = px_len_canvas / z_factor if zoom_h_active else px_len_canvas
                    
                    if px_len_real > 0:
                        mm_px = tire_mm / px_len_real
                        mask = canvas_silh.image_data[:, :, 3]
                        pixel_count = np.sum(mask > 0)
                        
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
                        st.success(f"Salvo! CdA: {cda:.4f}")
                    else:
                        st.error("Calibração inválida.")
                else:
                    if not has_calib: st.warning("⚠️ Faça a calibração na Aba 1.")
                    if not has_silh: st.warning("⚠️ Marque a silhueta na Aba 2.")

            if st.button("🗑️ Limpar Silhueta", use_container_width=True):
                st.rerun()
            
            st.caption("Dica: Clique duplo para fechar o polígono.")

    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.subheader("📊 Comparativo de Eficiencia")
        st.dataframe(df[["Setup", "CdA", "Vel. Est.", "Obs"]], hide_index=True)
        
        pdf_bytes = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
        st.download_button("📥 Gerar Laudo PDF", data=pdf_bytes, file_name=f"Laudo_{athlete_name}.pdf", mime="application/pdf")
        
        if st.button("🗑️ Reiniciar Tudo"):
            st.session_state.setups = []
            st.session_state.calib_data = None
            st.rerun()
