import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Aero Performance Lab Pro v2", layout="wide")

# --- TRATAMENTO DE IMAGEM: SOLUÇÃO PARA TELA PRETA E CANAL ALPHA ---
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
        pdf.cell(35, 10, str(row["Setup"]), 1, 0, "C")
        pdf.cell(35, 10, f"{row['CdA']:.4f}", 1, 0, "C")
        pdf.cell(40, 10, f"{row['Vel. Est.']:.1f}", 1, 0, "C")
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
obs_tecnica = st.sidebar.text_area("Observacoes para este Setup", placeholder="Ex: Capacete Aero Giro, Maos juntas...")

st.title("🚴 Aero Analyzer Pro v2")

if uploaded_file:
    # Processar imagem base
    img_pil, c_w, c_h = get_clean_image(uploaded_file)
    
    t1, t2 = st.tabs(["📏 1. Calibrar (Zoom)", "👤 2. Silhueta (Pontos)"])

    with t1:
        st.info("Abaixo você vê um zoom da parte inferior da imagem para facilitar a calibração no pneu.")
        # Criar zoom automático (focando nos 30% inferiores da imagem onde o pneu costuma estar)
        zoom_factor = 2.0
        crop_h = int(c_h / zoom_factor)
        # Cortar a parte inferior da imagem
        img_zoom = img_pil.crop((0, c_h - crop_h, c_w, c_h))
        img_zoom = img_zoom.resize((c_w, c_h), Image.Resampling.LANCZOS)
        
        canvas_calib = st_canvas(
            fill_color="rgba(255,0,0,0.3)", stroke_width=3, stroke_color="#FF0000",
            background_image=img_zoom, drawing_mode="line", key="c_calib",
            height=c_h, width=c_w, update_streamlit=True
        )

    with t2:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.info("Clique nos pontos da silhueta. O app fechará o polígono automaticamente.")
            canvas_silh = st_canvas(
                fill_color="rgba(0,255,0,0.4)", stroke_width=2, stroke_color="#00FF00",
                background_image=img_pil, drawing_mode="polygon", key="c_silh",
                height=c_h, width=c_w, update_streamlit=True
            )
        
        with col2:
            st.write("### Edição")
            # O canvas do Streamlit não permite apagar o último nó programaticamente de forma fácil sem resetar
            # mas podemos oferecer o botão de limpar para recomeçar.
            if st.button("🗑️ Limpar Silhueta", use_container_width=True):
                st.rerun()
            st.caption("Dica: Clique duas vezes para fechar o polígono se necessário.")

    if st.button("🚀 CALCULAR E SALVAR SETUP", use_container_width=True):
        has_calib = canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0
        has_silh = canvas_silh.image_data is not None
        
        if has_calib and has_silh:
            # Pegar a linha de calibração do zoom
            line = canvas_calib.json_data["objects"][-1]
            dx = line["width"] * line["scaleX"]
            dy = line["height"] * line["scaleY"]
            px_len_zoom = np.sqrt(dx**2 + dy**2)
            
            # Ajustar px_len do zoom para a escala real (zoom_factor foi usado no crop/resize)
            # Como redimensionamos o crop de volta para c_w/c_h, a escala é proporcional ao zoom_factor
            px_len_real = px_len_zoom / zoom_factor
            
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
                st.success(f"Analise salva! CdA estimado: {cda:.4f}")
            else:
                st.error("Linha de calibração inválida.")
        else:
            st.warning("Certifique-se de calibrar no zoom (aba 1) e desenhar a silhueta (aba 2).")

    if st.session_state.setups:
        df = pd.DataFrame(st.session_state.setups)
        st.subheader("📊 Comparativo de Eficiencia")
        st.dataframe(df[["Setup", "CdA", "Vel. Est.", "Obs"]], hide_index=True)
        
        pdf_bytes = generate_pdf(df, tire_mm, ftp_watts, athlete_name)
        st.download_button("📥 Gerar Laudo PDF", data=pdf_bytes, file_name=f"Laudo_{athlete_name}.pdf", mime="application/pdf")
        
        if st.button("🗑️ Reiniciar Tudo"):
            st.session_state.setups = []
            st.rerun()
