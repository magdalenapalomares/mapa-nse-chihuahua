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
    gdf = gpd.read_file("08a.shp")
    gdf = gdf.to_crs(epsg=4326)
    df = pd.read_csv("NSE_AGEB_Chihuahua_Ready.csv", dtype={'CVEGEO': str})
    df['VIVIENDAS'] = df['VIVIENDAS'].astype(str).str.replace(',', '')
    df['VIVIENDAS'] = pd.to_numeric(df['VIVIENDAS'], errors='coerce').fillna(0)
    mapa_final = gdf.merge(df, on="CVEGEO", how="inner")
    return mapa_final

try:
    data = cargar_datos()
    
    # --- BARRA LATERAL (MEJORADA VISUALMENTE) ---
    st.sidebar.title("🎛️ Panel de Control")
    
    # 🍺 MEJORA 1: Llamada a la acción clara
    st.sidebar.markdown("### 👇 Paso 1: Elige tu zona")
    st.sidebar.info("Selecciona el municipio que quieres analizar para actualizar el mapa.")
    
    lista_nombres = sorted(data['NOMBRE MUNICIPIO'].unique())
    # Índice por defecto: Chihuahua (si existe) o el primero
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

    # --- BUSCADOR ---
    st.sidebar.markdown("### 🔎 Paso 2: Ubica una dirección")
    with st.sidebar.form(key='form_busqueda'):
        direccion_input = st.text_input("Calle y número:", placeholder="Ej: Av. Universidad 123")
        boton_buscar = st.form_submit_button("Ir al punto 📍")

    if boton_buscar and direccion_input:
        geolocator = Nominatim(user_agent="app_nse_chihuahua_final")
        direccion_completa = f"{direccion_input}, {seleccion_nombre}, Chihuahua, México"
        try:
            location = geolocator.geocode(direccion_completa, timeout=10)
            if location:
                st.session_state['lat_vista'] = location.latitude
                st.session_state['lon_vista'] = location.longitude
                st.session_state['zoom_vista'] = 16
                st.session_state['marcador_memoria'] = {'lat': location.latitude, 'lon': location.longitude, 'texto': direccion_input}
                st.success(f"📍 ¡Encontrado! Mostrando: {direccion_input}")
            else:
                st.warning("No se encontró. Intenta añadir la Colonia.")
        except Exception:
            st.error("Error de conexión.")
    
    # 🍺 MEJORA 2: Sección de Ayuda
    with st.sidebar.expander("ℹ️ Ayuda y Tips"):
        st.markdown("""
        1. **Filtra:** Cambia de municipio arriba.
        2. **Busca:** Escribe una calle para hacer zoom.
        3. **Dibuja:** Usa las herramientas (⬛ ⬤ ⬠) en el mapa para seleccionar una zona y descargar los datos.
        """)

    # ==========================================
    # 3. TÍTULO PRINCIPAL DINÁMICO
    # ==========================================
    # 🍺 MEJORA 3: El título cambia según lo que seleccionas
    st.title(f"🗺️ Nivel Socioeconómico: {seleccion_nombre}")
    st.markdown(f"Visualizando distribución de riqueza en **{seleccion_nombre}**, Chihuahua.")

    # ==========================================
    # 4. MAPA
    # ==========================================
    if not data_filtrada.empty:
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
            return {'fillColor': colores_nse.get(nse, 'gray'), 'color': 'black', 'weight': 0.5, 'fillOpacity': 0.6}

        folium.GeoJson(
            data_filtrada,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['NOMBRE MUNICIPIO', 'NIVEL PREDOMINANTE', 'VIVIENDAS'],
                aliases=['Municipio:', 'NSE:', 'Viviendas:']
            )
        ).add_to(m)

        if st.session_state['marcador_memoria']:
            p = st.session_state['marcador_memoria']
            folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color="red"), popup=p['texto']).add_to(m)

        draw = Draw(
            export=False,
            position='topleft',
            draw_options={'polyline': False, 'circlemarker': False, 'marker': False},
            edit_options={'edit': False}
        )
        draw.add_to(m)

        output_mapa = st_folium(m, width="100%", height=600)

        # CÁLCULO DE SELECCIÓN
        if output_mapa and 'last_active_drawing' in output_mapa and output_mapa['last_active_drawing'] is not None:
            geometry_data = output_mapa['last_active_drawing']['geometry']
            poligono_usuario = shape(geometry_data)
            
            agebs_seleccionados = data_filtrada[data_filtrada.geometry.centroid.within(poligono_usuario)]
            
            cantidad_sel = len(agebs_seleccionados)
            viviendas_sel = int(agebs_seleccionados['VIVIENDAS'].sum())
            
            if cantidad_sel > 0:
                st.markdown("### 📊 Resultados de tu selección")
                col1, col2 = st.columns(2)
                col1.metric("AGEBs Capturados", cantidad_sel)
                col2.metric("Viviendas Totales", f"{viviendas_sel:,}")
                
                with st.expander("🔎 Ver detalles de la zona"):
                    cols_mostrar = ['CVEGEO', 'NIVEL PREDOMINANTE', 'VIVIENDAS', 'AB', 'C+', 'C', 'D+', 'D', 'E']
                    cols_finales = [c for c in cols_mostrar if c in agebs_seleccionados.columns]
                    st.dataframe(agebs_seleccionados[cols_finales])
                
                csv = agebs_seleccionados.drop(columns='geometry').to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar datos de esta zona (CSV)",
                    data=csv,
                    file_name=f"nse_{seleccion_nombre}_seleccion.csv",
                    mime="text/csv",
                )
            else:
                st.warning("⚠️ Tu selección no capturó el centro de ningún AGEB. Intenta cubrir más área.")

    else:
        st.warning("No hay datos para mostrar.")

except Exception as e:
    st.error(f"Error en la aplicación: {e}")
