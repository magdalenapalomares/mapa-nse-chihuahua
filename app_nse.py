import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from shapely.geometry import shape
import json

# Configuración de la página
st.set_page_config(page_title="Visor NSE Chihuahua", layout="wide")

# 1. Cargar datos
@st.cache_data
def cargar_datos():
    # Cargar mapa (INEGI)
    gdf = gpd.read_file("08a.shp")
    gdf = gdf.to_crs(epsg=4326)
    
    # Cargar datos (AMAI)
    df = pd.read_csv("NSE_AGEB_Chihuahua_Ready.csv", dtype={'CVEGEO': str})
    
    # Limpieza de columna viviendas
    df['VIVIENDAS'] = df['VIVIENDAS'].astype(str).str.replace(',', '')
    df['VIVIENDAS'] = pd.to_numeric(df['VIVIENDAS'], errors='coerce').fillna(0)
    
    mapa_final = gdf.merge(df, on="CVEGEO", how="inner")
    return mapa_final

try:
    data = cargar_datos()
    
    # --- BARRA LATERAL ---
    st.sidebar.title("🎛️ Panel de Control")
    
    # PASO 1
    st.sidebar.markdown("### 👇 Paso 1: Elige tu zona")
    lista_nombres = sorted(data['NOMBRE MUNICIPIO'].unique())
    index_def = lista_nombres.index('Chihuahua') if 'Chihuahua' in lista_nombres else 0
    seleccion_nombre = st.sidebar.selectbox("Municipio:", lista_nombres, index=index_def)
    
    # Filtrar datos
    data_filtrada = data[data['NOMBRE MUNICIPIO'] == seleccion_nombre]
    
    # Métricas
    total_viviendas = int(data_filtrada['VIVIENDAS'].sum())
    col_metric1, col_metric2 = st.sidebar.columns(2)
    col_metric1.metric("AGEBs", len(data_filtrada))
    col_metric2.metric("Viviendas", f"{total_viviendas:,}")
    
    st.sidebar.markdown("---")

    # --- CEREBRO (SESSION STATE) ---
    if 'lat_vista' not in st.session_state: st.session_state['lat_vista'] = 28.6353 
    if 'lon_vista' not in st.session_state: st.session_state['lon_vista'] = -106.0889
    if 'zoom_vista' not in st.session_state: st.session_state['zoom_vista'] = 13
    if 'marcador_memoria' not in st.session_state: st.session_state['marcador_memoria'] = None
    if 'ultimo_municipio' not in st.session_state: st.session_state['ultimo_municipio'] = None

    if seleccion_nombre != st.session_state['ultimo_municipio']:
        if not data_filtrada.empty:
            st.session_state['lat_vista'] = data_filtrada.geometry.centroid.y.mean()
            st.session_state['lon_vista'] = data_filtrada.geometry.centroid.x.mean()
            st.session_state['zoom_vista'] = 13
        st.session_state['marcador_memoria'] = None
        st.session_state['ultimo_municipio'] = seleccion_nombre

    # PASO 2: BUSCADOR
    st.sidebar.markdown("### 🔎 Paso 2: Ubica una dirección")
    with st.sidebar.form(key='form_busqueda'):
        direccion_input = st.text_input("Calle y número:", placeholder="Ej: Av. Universidad 123")
        boton_buscar = st.form_submit_button("Ir al punto 📍")

    if boton_buscar and direccion_input:
        geolocator = Nominatim(user_agent="app_nse_chihuahua_fuentes")
        direccion_completa = f"{direccion_input}, {seleccion_nombre}, Chihuahua, México"
        try:
            location = geolocator.geocode(direccion_completa, timeout=10)
            if location:
                st.session_state['lat_vista'] = location.latitude
                st.session_state['lon_vista'] = location.longitude
                st.session_state['zoom_vista'] = 16
                st.session_state['marcador_memoria'] = {'lat': location.latitude, 'lon': location.longitude, 'texto': direccion_input}
                st.success(f"📍 ¡Encontrado!")
            else:
                st.warning("No se encontró. Intenta añadir la Colonia.")
        except Exception:
            st.error("Error de conexión.")
    
    st.sidebar.markdown("---")
    
    # GUÍA DE NIVELES (AMAI)
    st.sidebar.markdown("### 📖 Guía de Niveles (AMAI)")
    with st.sidebar
