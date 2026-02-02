import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# Configuración de la página
st.set_page_config(page_title="Visor NSE Chihuahua", layout="wide")

st.title("🗺️ Mapa de Nivel Socioeconómico - Chihuahua")
st.markdown("Herramienta para identificar el NSE predominante por AGEB.")

# 1. Cargar datos
@st.cache_data
def cargar_datos():
    # Cargar mapa
    gdf = gpd.read_file("08a.shp")
    # Convertir a coordenadas GPS (Lat/Lon)
    gdf = gdf.to_crs(epsg=4326) 
    
    # Cargar datos AMAI
    df = pd.read_csv("NSE_AGEB_Chihuahua_Ready.csv", dtype={'CVEGEO': str})
    
    # Unir
    mapa_final = gdf.merge(df, on="CVEGEO", how="inner")
    return mapa_final

try:
    data = cargar_datos()
    
    # 2. Filtros
    st.sidebar.header("Filtros")
    
    # Lista de municipios disponibles
    municipios = sorted(data['CVE_MUN'].unique())
    seleccion_mun = st.sidebar.selectbox("Selecciona un Municipio (Clave):", municipios)
    
    # Filtrar datos
    data_filtrada = data[data['CVE_MUN'] == seleccion_mun]
    
    # Métricas
    st.sidebar.metric("Total AGEBs en zona", len(data_filtrada))

    # 3. Mapa
    if not data_filtrada.empty:
        # Centrar mapa
        lat_centro = data_filtrada.geometry.centroid.y.mean()
        lon_centro = data_filtrada.geometry.centroid.x.mean()
        
        m = folium.Map(location=[lat_centro, lon_centro], zoom_start=12)

        # Colores
        colores_nse = {
            'AB': '#006400', 'C+': '#32CD32', 'C': '#ADFF2F',
            'C-': '#FFFF00', 'D+': '#FFA500', 'D': '#FF4500', 'E': '#FF0000'
        }

        def style_function(feature):
            nse = feature['properties']['NIVEL PREDOMINANTE']
            return {
                'fillColor': colores_nse.get(nse, 'gray'),
                'color': 'black',
                'weight': 0.5,
                'fillOpacity': 0.7
            }

        folium.GeoJson(
            data_filtrada,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(fields=['CVEGEO', 'NIVEL PREDOMINANTE'])
        ).add_to(m)

        st_folium(m, width="100%", height=600)
    else:
        st.warning("No hay datos para mostrar en este municipio.")

except Exception as e:
    st.error(f"Error: {e}")