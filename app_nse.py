import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
# 🍺 NUEVO: Importamos el geocodificador de OpenStreetMap
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Configuración de la página
st.set_page_config(page_title="Visor NSE Chihuahua", layout="wide")

st.title("🗺️ Mapa de Nivel Socioeconómico - Chihuahua")
st.markdown("Herramienta para identificar el NSE predominante por AGEB.")

# 1. Cargar datos (Sin cambios aquí)
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
    
    st.sidebar.header("Filtros")
    lista_nombres = sorted(data['NOMBRE MUNICIPIO'].unique())
    seleccion_nombre = st.sidebar.selectbox("Selecciona un Municipio:", lista_nombres)
    data_filtrada = data[data['NOMBRE MUNICIPIO'] == seleccion_nombre]
    
    st.sidebar.metric("Total AGEBs en zona", len(data_filtrada))
    total_viviendas = int(data_filtrada['VIVIENDAS'].sum())
    st.sidebar.write(f"🏠 **Viviendas analizadas:** {total_viviendas:,}")
    st.sidebar.markdown("---") # Separador visual

    # ==========================================
    # 🍺 NUEVO: SECCIÓN DEL BUSCADOR
    # ==========================================
    st.sidebar.header("🔍 Buscador de Direcciones")
    direccion_input = st.sidebar.text_input("Calle y número (Ej: Av. Universidad y División del Norte):", key="input_direccion")
    buscar_btn = st.sidebar.button("Buscar en el mapa")

    # Variables por defecto para el mapa (si no se busca nada)
    lat_centro = data_filtrada.geometry.centroid.y.mean()
    lon_centro = data_filtrada.geometry.centroid.x.mean()
    zoom_inicial = 13
    marcador_busqueda = None # Variable para guardar el pin rojo si encontramos la dirección

    # Lógica de búsqueda (Solo si aprieta el botón y hay texto)
    if buscar_btn and direccion_input:
        # Inicializar geocodificador (importante poner un user_agent único)
        geolocator = Nominatim(user_agent="app_nse_chihuahua_v1")
        
        # Le agregamos el municipio y estado para que no busque en otro país
        direccion_completa = f"{direccion_input}, {seleccion_nombre}, Chihuahua, México"
        
        with st.spinner(f"Buscando '{direccion_input}'..."):
            try:
                # Realizar la búsqueda
                location = geolocator.geocode(direccion_completa, timeout=10)
                
                if location:
                    # Si lo encuentra, actualizamos el centro y el zoom
                    lat_centro = location.latitude
                    lon_centro = location.longitude
                    zoom_inicial = 17 # Zoom muy cercano
                    st.sidebar.success("📍 Dirección encontrada. El mapa se ha centrado.")
                    
                    # Creamos un marcador rojo para el punto exacto
                    marcador_busqueda = folium.Marker(
                        [lat_centro, lon_centro],
                        popup=f"Búsqueda: {direccion_input}",
                        icon=folium.Icon(color="red", icon="info-sign")
                    )
                else:
                    st.sidebar.warning(f"No pudimos encontrar '{direccion_input}'. Intenta verificar el nombre de la calle o añadir una colonia.")
            except Exception as e:
                 st.sidebar.error(f"Error de conexión con el servicio de mapas: {e}")

    # ==========================================
    # 3. Mapa Interactivo (Modificado)
    # ==========================================
    if not data_filtrada.empty:
        # Usamos las variables lat_centro, lon_centro y zoom_inicial que definimos arriba
        m = folium.Map(location=[lat_centro, lon_centro], zoom_start=zoom_inicial)

        # Paleta y estilo (Sin cambios)
        colores_nse = {
            'AB': '#006400', 'C+': '#32CD32', 'C': '#ADFF2F',
            'C-': '#FFFF00', 'D+': '#FFA500', 'D': '#FF4500', 'E': '#FF0000'
        }
        def style_function(feature):
            nse = feature['properties']['NIVEL PREDOMINANTE']
            return {
                'fillColor': colores_nse.get(nse, 'gray'), 'color': 'black', 'weight': 0.5, 'fillOpacity': 0.7
            }

        # Capa de AGEBs
        folium.GeoJson(
            data_filtrada,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['CVEGEO', 'NOMBRE MUNICIPIO', 'NIVEL PREDOMINANTE', 'VIVIENDAS'],
                aliases=['Clave AGEB:', 'Municipio:', 'NSE Predominante:', 'Viviendas:']
            )
        ).add_to(m)

        # 🍺 NUEVO: Si hubo una búsqueda exitosa, añadimos el marcador rojo al mapa
        if marcador_busqueda:
            marcador_busqueda.add_to(m)

        st_folium(m, width="100%", height=600)
    else:
        st.warning("No hay datos para mostrar.")

except Exception as e:
    st.error(f"Error al cargar: {e}")
