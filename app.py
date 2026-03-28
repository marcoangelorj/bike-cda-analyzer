import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io

# --- PATCH DE COMPATIBILIDADE PARA STREAMLIT 1.41+ ---
# O componente streamlit-drawable-canvas tenta usar 'streamlit.elements.image.image_to_url'
# que foi removido nas versões recentes do Streamlit. Este patch restaura a função.
try:
    import streamlit.elements.image as st_image
    if not hasattr(st_image, "image_to_url"):
        from streamlit.runtime.memory_media_file_storage import get_memory_media_file_storage
        
        def image_to_url(image, width, clamp, channels, output_format, image_id):
            # Simula a função removida usando o novo sistema de armazenamento do Streamlit
            storage = get_memory_media_file_storage()
            # Converte a imagem PIL para bytes se necessário
            if isinstance(image, Image.Image):
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")
                content = buffered.getvalue()
            else:
                content = image
                
            file_url = storage.add(content, "image/png", image_id)
            return file_url
            
        st_image.image_to_url = image_to_url
except Exception as e:
    # Se o patch falhar, o erro original será exibido pelo Streamlit
    pass

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Aero Analyzer Pro", layout="wide")

# FUNÇÃO PARA CONVERTER IMAGEM PARA BASE64 (Corrige fundo preto)
def get_image_base64(img):
    # Converte para RGB para remover canal alpha (que pode causar o fundo preto)
    img = img.convert("RGB") 
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG") # JPEG é mais leve e compatível
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}"

# Inicializa st.session_state.setups se não existir
if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.title("🏁 Parâmetros")
uploaded_file = st.sidebar.file_uploader("1. Foto Frontal", type=["jpg", "jpeg", "png"])
real_tire_width_mm = st.sidebar.number_input("2. Largura Pneu (mm)", value=25.0, min_value=1.0)
dist_km = st.sidebar.selectbox("3. Distância (km)", [10, 20, 40, 90, 180], index=2)
user_ftp = st.sidebar.number_input("4. Watts (FTP)", value=250, min_value=1)
drag_coeff = st.sidebar.select_slider("5. Cd", options=np.around(np.arange(0.22, 0.41, 0.01), 2), value=0.30)

st.title("🚴 Aero Analyzer & TT Predictor")

if uploaded_file:
    # 1. Processamento da imagem
    img = Image.open(uploaded_file)
    w, h = img.size
    canvas_w = 700 
    canvas_h = int(h * (canvas_w / w))
    img_resized = img.resize((canvas_w, canvas_h))
    
    tab1, tab2 = st.tabs(["📏 1. Calibração", "👤 2. Silhueta"])

    with tab1:
        st.write("Desenhe uma linha sobre a largura do pneu na imagem para calibração.")
        canvas_calib = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_image=img_resized,
            drawing_mode="line",
            key="canvas_calib_v10",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
        )

    with tab2:
        st.write("Contorne o ciclista para definir a área frontal.")
        canvas_silh = st_canvas(
            fill_color="rgba(0, 255, 0, 0.3)",
            stroke_width=2,
            stroke_color="#00FF00",
            background_image=img_resized,
            drawing_mode="polygon",
            key="canvas_silh_v10",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
        )

    if st.button("🚀 ANALISAR SETUP"):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            obj = canvas_calib.json_data["objects"][-1]
            # Calcula o comprimento da linha desenhada para calibração
            px_width = np.sqrt(obj["width"]**2 + obj["height"]**2)
            
            if px_width > 0:
                if canvas_silh.image_data is not None:
                    mm_per_px = real_tire_width_mm / px_width
                    mask = canvas_silh.image_data[:, :, 3] # Pega o canal alpha
                    total_px = np.sum(mask > 0) # Conta pixels não transparentes
                    
                    if total_px > 0:
                        area_m2 = (total_px * (mm_per_px**2)) / 1_000_000 # Converte mm^2 para m^2
                        cda_calc = area_m2 * drag_coeff
                        
                        # Constante da densidade do ar (rho) em kg/m^3
                        rho = 1.225 
                        
                        # Cálculo da velocidade em m/s
                        try:
                            v_ms = (user_ftp / (0.5 * rho * cda_calc))**(1/3)
                            tempo_seg = (dist_km * 1000) / v_ms
                            
                            mins, segs = divmod(int(tempo_seg), 60)
                            horas, mins = divmod(mins, 60)
                            tempo_fmt = f"{horas}h {mins}m {segs}s" if horas > 0 else f"{mins}m {segs}s"

                            st.session_state.setups.append({
                                "Setup": f"Análise {len(st.session_state.setups)+1}",
                                "CdA": round(cda_calc, 4),
                                "Tempo": tempo_fmt
                            })
                            st.success("Análise concluída com sucesso!")
                        except ZeroDivisionError:
                            st.error("Erro: CdA calculado é zero. Verifique se a silhueta foi desenhada corretamente.")
                    else:
                        st.warning("Por favor, contorne o ciclista na aba 'Silhueta' para calcular a área frontal.")
                else:
                    st.warning("Dados da silhueta não encontrados. Por favor, contorne o ciclista na aba 'Silhueta'.")
            else:
                st.warning("Por favor, desenhe uma linha válida para calibração na aba 'Calibração'.")
        else:
            st.warning("Por favor, desenhe uma linha para calibração na aba 'Calibração'.")

    if st.session_state.setups:
        st.divider()
        st.subheader("Resultados das Análises")
        st.table(pd.DataFrame(st.session_state.setups))
else:
    st.info("Suba uma foto para começar a análise aerodinâmica.")
