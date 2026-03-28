import streamlit as st
import numpy as np
import pandas as pd
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import base64
import io

# --- PATCH DE COMPATIBILIDADE PARA STREAMLIT 1.41+ ---
try:
    import streamlit.elements.image as st_image
    if not hasattr(st_image, "image_to_url"):
        from streamlit.runtime.memory_media_file_storage import get_memory_media_file_storage
        
        def image_to_url(image, width, clamp, channels, output_format, image_id):
            storage = get_memory_media_file_storage()
            if isinstance(image, Image.Image):
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")
                content = buffered.getvalue()
            else:
                content = image
            file_url = storage.add(content, "image/png", image_id)
            return file_url
        st_image.image_to_url = image_to_url
except Exception:
    pass

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Aero Analyzer Pro", layout="wide")

# FUNÇÃO PARA CONVERTER IMAGEM PARA DATA URI (BASE64)
def get_image_data_uri(img):
    img = img.convert("RGB") 
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}"

# Inicializa st.session_state.setups se não existir
if 'setups' not in st.session_state:
    st.session_state.setups = []

# --- SIDEBAR ---
st.sidebar.title("🏁 Parâmetros")
uploaded_file = st.sidebar.file_uploader("1. Foto Frontal", type=["jpg", "jpeg", "png"])
real_tire_width_mm = st.sidebar.number_input("2. Largura Pneu (mm)", value=25.0, min_value=1.0, help="Largura real do pneu frontal para calibração de escala.")
dist_km = st.sidebar.selectbox("3. Distância (km)", [10, 20, 40, 90, 180], index=2)
user_ftp = st.sidebar.number_input("4. Watts (FTP)", value=250, min_value=1, help="Potência média sustentada.")
drag_coeff = st.sidebar.select_slider("5. Coeficiente de Arrasto (Cd)", options=np.around(np.arange(0.20, 0.51, 0.01), 2), value=0.30, help="Estimativa do Cd baseado na posição (0.25-0.30 para TT agressivo).")

st.title("🚴 Aero Analyzer & TT Predictor")

if uploaded_file:
    # 1. Processamento da imagem
    img_raw = Image.open(uploaded_file).convert("RGB")
    w, h = img_raw.size
    canvas_w = 700 
    canvas_h = int(h * (canvas_w / w))
    img_resized = img_raw.resize((canvas_w, canvas_h))
    
    # CONVERSÃO PARA DATA URI
    img_data_uri = get_image_data_uri(img_resized)
    file_id = uploaded_file.name

    tab1, tab2 = st.tabs(["📏 1. Calibração", "👤 2. Silhueta"])

    with tab1:
        st.info("💡 DICA: Na imagem modelo, desenhe a linha horizontalmente sobre a parte mais larga do pneu frontal.")
        canvas_calib = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=3,
            stroke_color="#FF0000",
            background_image=img_data_uri,
            drawing_mode="line",
            key=f"canvas_calib_{file_id}",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
            background_color="#FFFFFF",
        )

    with tab2:
        st.info("💡 DICA: Contorne todo o conjunto (ciclista + bike). Como o fundo é verde sólido, tente ser o mais preciso possível nas bordas.")
        canvas_silh = st_canvas(
            fill_color="rgba(0, 255, 0, 0.3)",
            stroke_width=2,
            stroke_color="#00FF00",
            background_image=img_data_uri,
            drawing_mode="polygon",
            key=f"canvas_silh_{file_id}",
            height=canvas_h,
            width=canvas_w,
            update_streamlit=True,
            background_color="#FFFFFF",
        )

    if st.button("🚀 ANALISAR SETUP"):
        if canvas_calib.json_data and len(canvas_calib.json_data["objects"]) > 0:
            obj = canvas_calib.json_data["objects"][-1]
            # Cálculo da distância euclidiana para a linha de calibração
            # Em imagens frontais, a precisão aqui é vital para a escala mm/px
            px_width = np.sqrt(obj["width"]**2 + obj["height"]**2)
            
            if px_width > 5: # Evita linhas acidentais muito curtas
                if canvas_silh.image_data is not None:
                    mm_per_px = real_tire_width_mm / px_width
                    # O canal 3 (alpha) contém o desenho do polígono
                    mask = canvas_silh.image_data[:, :, 3]
                    total_px = np.sum(mask > 0)
                    
                    if total_px > 100: # Evita cliques acidentais
                        # Cálculo da Área Frontal (A) em m^2
                        # Área (m2) = (Pixels * (mm/px)^2) / 1.000.000
                        area_m2 = (total_px * (mm_per_px**2)) / 1_000_000
                        cda_calc = area_m2 * drag_coeff
                        
                        # Física: P = 0.5 * rho * CdA * v^3
                        rho = 1.225 # Densidade do ar padrão ao nível do mar
                        
                        try:
                            v_ms = (user_ftp / (0.5 * rho * cda_calc))**(1/3)
                            v_kmh = v_ms * 3.6
                            tempo_seg = (dist_km * 1000) / v_ms
                            
                            mins, segs = divmod(int(tempo_seg), 60)
                            horas, mins = divmod(mins, 60)
                            tempo_fmt = f"{horas}h {mins}m {segs}s" if horas > 0 else f"{mins}m {segs}s"

                            st.session_state.setups.append({
                                "Setup": f"Análise {len(st.session_state.setups)+1}",
                                "Área (m²)": round(area_m2, 4),
                                "CdA": round(cda_calc, 4),
                                "Vel. Est. (km/h)": round(v_kmh, 2),
                                "Tempo": tempo_fmt
                            })
                            st.success("Análise concluída com sucesso!")
                        except ZeroDivisionError:
                            st.error("Erro nos cálculos. Verifique as marcações.")
                    else:
                        st.warning("Por favor, contorne o ciclista na aba 'Silhueta'.")
                else:
                    st.warning("Dados da silhueta não encontrados.")
            else:
                st.warning("A linha de calibração está muito curta. Desenhe sobre a largura do pneu.")
        else:
            st.warning("Por favor, realize a calibração na aba 'Calibração'.")

    if st.session_state.setups:
        st.divider()
        st.subheader("📊 Resultados Comparativos")
        df_results = pd.DataFrame(st.session_state.setups)
        st.table(df_results)
        
        # Gráfico simples de comparação de CdA se houver mais de um setup
        if len(st.session_state.setups) > 1:
            st.bar_chart(df_results.set_index("Setup")["CdA"])
else:
    st.info("Suba uma foto frontal (como a imagem modelo) para começar.")
