import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Configuración de la página
st.set_page_config(page_title="Visor NSE Chihuahua", layout="wide")

st.title("🗺️ Mapa de Nivel Socioeconómico - Chihuahua")
st.markdown("Herramienta para identificar el NSE predominante por AGEB.")

# 1. Cargar datos
@st.cache_data
def cargar_datos():
    gdf = gpd.read_file("08a.shp")
    gdf = gdf.to_crs(epsg=4326)
    df = pd.read_csv("NSE_AGEB_Chihuahua_Ready.csv", dtype={'CVEGEO': str})
    df['VIVIENDAS'] = pd.to_numeric(df['VIVIENDAS'], errors='coerce').fillna(0)
    mapa_final = gdf.merge(df, on="CVEGEO", how="inner")
    return mapa_final

try:
    data = cargar_datos()
    
    # 2. Filtros
    st.sidebar.header("Filtros")
    lista_nombres = sorted(data['NOMBRE MUNICIPIO'].unique())
    seleccion_nombre = st.sidebar.selectbox("Selecciona un Municipio:", lista_nombres)
    
    # Filtrar datos
    data_filtrada = data[data['NOMBRE MUNICIPIO'] == seleccion_nombre]
    
    # Métricas
    st.sidebar.metric("Total AGEBs en zona", len(data_filtrada))
    total_viviendas = int(data_filtrada['VIVIENDAS'].sum())
    st.sidebar.write(f"🏠 **Viviendas analizadas:** {total_viviendas:,}")
    st.sidebar.markdown("---")

    # ==========================================
    # 🧠 EL CEREBRO (SESSION STATE)
    # ==========================================
    # Inicializamos la memoria si está vacía
    if 'lat_vista' not in st.session_state:
        st.session_state['lat_vista'] = 28.6353 
    if 'lon_vista' not in st.session_state:
        st.session_state['lon_vista'] = -106.0889
    if 'zoom_vista' not in st.session_state:
        st.session_state['zoom_vista'] = 13
    if 'marcador_memoria' not in st.session_state:
        st.session_state['marcador_memoria'] = None # Aquí guardaremos el pin rojo
    if 'ultimo_municipio' not in st.session_state:
        st.session_state['ultimo_municipio'] = None

    # Lógica 1: Si CAMBIA el municipio, reseteamos la vista al centro del municipio
    if seleccion_nombre != st.session_state['ultimo_municipio']:
        if not data_filtrada.empty:
            st.session_state['lat_vista'] = data_filtrada.geometry.centroid.y.mean()
            st.session_state['lon_vista'] = data_filtrada.geometry.centroid.x.mean()
            st.session_state['zoom_vista'] = 13
        st.session_state['marcador_memoria'] = None # Borramos búsquedas anteriores
        st.session_state['ultimo_municipio'] = seleccion_nombre # Actualizamos la memoria

    # ==========================================
    # 🔍 BUSCADOR
    # ==========================================
    st.sidebar.header("🔍 Buscador de Direcciones")
    # Usamos un formulario para que la página no recargue con cada letra que escribes
    with st.sidebar.form(key='form_busqueda'):
        direccion_input = st.text_input("Calle y número:", placeholder="Ej: Av. Universidad 123")
        boton_buscar = st.form_submit_button("Buscar 📍")

    # Lógica 2: Si presiona BUSCAR, actualizamos la memoria con la nueva dirección
    if boton_buscar and direccion_input:
        geolocator = Nominatim(user_agent="app_nse_chihuahua_fix")
        direccion_completa = f"{direccion_input}, {seleccion_nombre}, Chihuahua, México"
        
        with st.spinner(f"Buscando '{direccion_input}'..."):
            try:
                location = geolocator.geocode(direccion_completa, timeout=10)
                if location:
                    # ¡ÉXITO! Guardamos las nuevas coordenadas en la memoria
                    st.session_state['lat_vista'] = location.latitude
                    st.session_state['lon_vista'] = location.longitude
                    st.session_state['zoom_vista'] = 17
                    st.session_state['marcador_memoria'] = {
                        'lat': location.latitude, 
                        'lon': location.longitude, 
                        'texto': direccion_input
                    }
                    st.success("Dirección encontrada.")
                else:
                    st.warning("No se encontró la dirección. Intenta agregar la Colonia.")
            except Exception as e:
                st.error(f"Error de conexión: {e}")

    # ==========================================
    # 3. MAPA (Usando la Memoria)
    # ==========================================
    if not data_filtrada.empty:
        # Creamos el mapa usando las coordenadas guardadas en SESSION_STATE
        m = folium.Map(
            location=[st.session_state['lat_vista'], st.session_state['lon_vista']], 
            zoom_start=st.session_state['zoom_vista']
        )

        colores_nse = {
            'AB': '#006400', 'C+': '#32CD32', 'C': '#ADFF2F',
            'C-': '#FFFF00', 'D+': '#FFA500', 'D': '#FF4500', 'E': '#FF0000'
        }
        
        def style_function(feature):
            nse = feature['properties']['NIVEL PREDOMINANTE']
            return {'fillColor': colores_nse.get(nse, 'gray'), 'color': 'black', 'weight': 0.5, 'fillOpacity': 0.7}

        folium.GeoJson(
            data_filtrada,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['CVEGEO', 'NOMBRE MUNICIPIO', 'NIVEL PREDOMINANTE', 'VIVIENDAS'],
                aliases=['Clave AGEB:', 'Municipio:', 'NSE Predominante:', 'Viviendas:']
            )
        ).add_to(m)

        # Si hay un marcador en memoria, lo dibujamos
        if st.session_state['marcador_memoria']:
            datos_pin = st.session_state['marcador_memoria']
            folium.Marker(
                [datos_pin['lat'], datos_pin['lon']],
                popup=f"Búsqueda: {datos_pin['texto']}",
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)

        st_folium(m, width="100%", height=600)
    else:
        st.warning("No hay datos para mostrar.")

except Exception as e:
    st.error(f"Error al cargar: {e}")
