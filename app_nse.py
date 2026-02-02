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
    # Cargar mapa (Shapefile)
    gdf = gpd.read_file("08a.shp")
    gdf = gdf.to_crs(epsg=4326) # Convertir a GPS
    
    # Cargar datos AMAI (CSV)
    df = pd.read_csv("NSE_AGEB_Chihuahua_Ready.csv", dtype={'CVEGEO': str})
    
    # Unir ambos
    mapa_final = gdf.merge(df, on="CVEGEO", how="inner")
    return mapa_final

try:
    data = cargar_datos()
    
    # 2. Filtros en la barra lateral
    st.sidebar.header("Filtros")
    
    # --- CAMBIO AQUÍ: Usamos 'NOMBRE MUNICIPIO' en lugar de la clave ---
    lista_nombres = sorted(data['NOMBRE MUNICIPIO'].unique())
    seleccion_nombre = st.sidebar.selectbox("Selecciona un Municipio:", lista_nombres)
    
    # Filtramos los datos usando el nombre seleccionado
    data_filtrada = data[data['NOMBRE MUNICIPIO'] == seleccion_nombre]
    
    # Métricas rápidas
    st.sidebar.metric("Total AGEBs en zona", len(data_filtrada))
    st.sidebar.write(f"Viviendas analizadas: {data_filtrada['VIVIENDAS'].sum():,}")

    # 3. Mapa Interactivo
    if not data_filtrada.empty:
        # Centrar mapa
        lat_centro = data_filtrada.geometry.centroid.y.mean()
        lon_centro = data_filtrada.geometry.centroid.x.mean()
        
        m = folium.Map(location=[lat_centro, lon_centro], zoom_start=13)

        # Paleta de colores
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

        # --- MEJORA: Tooltip con Nombre del Municipio ---
        folium.GeoJson(
            data_filtrada,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['CVEGEO', 'NOMBRE MUNICIPIO', 'NIVEL PREDOMINANTE'],
                aliases=['Clave AGEB:', 'Municipio:', 'NSE Predominante:']
            )
        ).add_to(m)

        st_folium(m, width="100%", height=600)
    else:
        st.warning("No hay datos para mostrar.")

except Exception as e:
    st.error(f"Error al cargar: {e}")
