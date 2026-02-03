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

st.title("🗺️ Mapa de Nivel Socioeconómico - Chihuahua")
st.markdown("Herramienta para identificar el NSE predominante, buscar direcciones y **descargar datos por zona**.")

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
    
    # --- BARRA LATERAL ---
    st.sidebar.header("Filtros")
    lista_nombres = sorted(data['NOMBRE MUNICIPIO'].unique())
    seleccion_nombre = st.sidebar.selectbox("Selecciona un Municipio:", lista_nombres)
    
    # Filtrar datos por municipio
    data_filtrada = data[data['NOMBRE MUNICIPIO'] == seleccion_nombre]
    
    # Métricas
    st.sidebar.metric("Total AGEBs en municipio", len(data_filtrada))
    total_viviendas = int(data_filtrada['VIVIENDAS'].sum())
    st.sidebar.write(f"🏠 **Viviendas totales:** {total_viviendas:,}")
    st.sidebar.markdown("---")

    # --- CEREBRO (SESSION STATE) ---
    if 'lat_vista' not in st.session_state: st.session_state['lat_vista'] = 28.6353 
    if 'lon_vista' not in st.session_state: st.session_state['lon_vista'] = -106.0889
    if 'zoom_vista' not in st.session_state: st.session_state['zoom_vista'] = 13
    if 'marcador_memoria' not in st.session_state: st.session_state['marcador_memoria'] = None
    if 'ultimo_municipio' not in st.session_state: st.session_state['ultimo_municipio'] = None

    # Resetear vista si cambia el municipio
    if seleccion_nombre != st.session_state['ultimo_municipio']:
        if not data_filtrada.empty:
            st.session_state['lat_vista'] = data_filtrada.geometry.centroid.y.mean()
            st.session_state['lon_vista'] = data_filtrada.geometry.centroid.x.mean()
            st.session_state['zoom_vista'] = 13
        st.session_state['marcador_memoria'] = None
        st.session_state['ultimo_municipio'] = seleccion_nombre

    # --- BUSCADOR ---
    st.sidebar.header("🔍 Buscador")
    with st.sidebar.form(key='form_busqueda'):
        direccion_input = st.text_input("Calle y número:", placeholder="Ej: Av. Universidad 123")
        boton_buscar = st.form_submit_button("Buscar 📍")

    if boton_buscar and direccion_input:
        geolocator = Nominatim(user_agent="app_nse_chihuahua_pro")
        direccion_completa = f"{direccion_input}, {seleccion_nombre}, Chihuahua, México"
        try:
            location = geolocator.geocode(direccion_completa, timeout=10)
            if location:
                st.session_state['lat_vista'] = location.latitude
                st.session_state['lon_vista'] = location.longitude
                st.session_state['zoom_vista'] = 16
                st.session_state['marcador_memoria'] = {'lat': location.latitude, 'lon': location.longitude, 'texto': direccion_input}
                st.success("Dirección encontrada.")
            else:
                st.warning("No se encontró la dirección.")
        except Exception:
            st.error("Error de conexión.")

    # ==========================================
    # 3. MAPA CON HERRAMIENTAS DE DIBUJO
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

        # Capa base de AGEBs
        folium.GeoJson(
            data_filtrada,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['CVEGEO', 'NOMBRE MUNICIPIO', 'NIVEL PREDOMINANTE', 'VIVIENDAS'],
                aliases=['Clave AGEB:', 'Municipio:', 'NSE Predominante:', 'Viviendas:']
            )
        ).add_to(m)

        # Pin de búsqueda
        if st.session_state['marcador_memoria']:
            p = st.session_state['marcador_memoria']
            folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color="red"), popup=p['texto']).add_to(m)

        # --- 🍺 HERRAMIENTA DE DIBUJO (DRAW) ---
        draw = Draw(
            export=False,
            position='topleft',
            draw_options={'polyline': False, 'circlemarker': False, 'marker': False},
            edit_options={'edit': False}
        )
        draw.add_to(m)

        # Renderizar mapa y capturar interacción
        output_mapa = st_folium(m, width="100%", height=600)

        # ==========================================
        # 4. LÓGICA DE DESCARGA POR SELECCIÓN
        # ==========================================
        st.markdown("### 📥 Descarga de Datos por Zona")
        st.info("Usa las herramientas de dibujo en la izquierda del mapa (Cuadrado, Polígono o Círculo) para seleccionar un área.")

        # Verificar si el usuario dibujó algo
        if output_mapa and 'last_active_drawing' in output_mapa and output_mapa['last_active_drawing'] is not None:
            geometry_data = output_mapa['last_active_drawing']['geometry']
            
            # Convertir el dibujo (GeoJSON) a una forma geométrica de Python (Shapely)
            poligono_usuario = shape(geometry_data)
            
            # --- FILTRO ESPACIAL ---
            # Buscamos qué AGEBs intersectan (tocan o están dentro) del dibujo
            # Usamos data_filtrada para solo buscar en el municipio actual (más rápido)
            agebs_seleccionados = data_filtrada[data_filtrada.geometry.intersects(poligono_usuario)]
            
            cantidad_sel = len(agebs_seleccionados)
            
            if cantidad_sel > 0:
                st.success(f"✅ ¡Selección exitosa! Has capturado **{cantidad_sel} AGEBs** dentro de tu zona.")
                
                # Mostrar vista previa
                with st.expander("Ver tabla de datos seleccionados"):
                    # Limpiamos columnas raras antes de mostrar
                    cols_mostrar = ['CVEGEO', 'NOMBRE MUNICIPIO', 'NIVEL PREDOMINANTE', 'VIVIENDAS', 'AB', 'C+', 'C', 'D+', 'D', 'E']
                    # Asegurar que existan las columnas (a veces el merge cambia nombres)
                    cols_finales = [c for c in cols_mostrar if c in agebs_seleccionados.columns]
                    st.dataframe(agebs_seleccionados[cols_finales])
                
                # Botón de Descarga
                csv = agebs_seleccionados.drop(columns='geometry').to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar esta selección (CSV)",
                    data=csv,
                    file_name="seleccion_nse_zona.csv",
                    mime="text/csv",
                )
            else:
                st.warning("⚠️ Tu dibujo no tocó ningún AGEB. Intenta dibujar sobre las zonas coloreadas.")

    else:
        st.warning("No hay datos para mostrar.")

except Exception as e:
    st.error(f"Error en la aplicación: {e}")
