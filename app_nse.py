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
    
    # Limpieza de columna viviendas (quitar comas y convertir a números)
    df['VIVIENDAS'] = df['VIVIENDAS'].astype(str).str.replace(',', '')
    df['VIVIENDAS'] = pd.to_numeric(df['VIVIENDAS'], errors='coerce').fillna(0)
    
    mapa_final = gdf.merge(df, on="CVEGEO", how="inner")
    return mapa_final

try:
    data = cargar_datos()
    
    # ==========================================
    # BARRA LATERAL (FILTROS Y MENÚ)
    # ==========================================
    st.sidebar.title("Navegación")
    
    # --- PASO 1: SELECTOR DE MUNICIPIO ---
    st.sidebar.markdown("### 👇 Paso 1: Elige tu zona")
    lista_nombres = sorted(data['NOMBRE MUNICIPIO'].unique())
    # Intentamos seleccionar 'Chihuahua' por defecto
    index_def = lista_nombres.index('Chihuahua') if 'Chihuahua' in lista_nombres else 0
    seleccion_nombre = st.sidebar.selectbox("Municipio:", lista_nombres, index=index_def)
    
    # Filtrar datos por municipio
    data_filtrada = data[data['NOMBRE MUNICIPIO'] == seleccion_nombre]
    
    # Métricas del municipio seleccionado
    total_viviendas = int(data_filtrada['VIVIENDAS'].sum())
    col1, col2 = st.sidebar.columns(2)
    col1.metric("AGEBs", len(data_filtrada))
    col2.metric("Viviendas", f"{total_viviendas:,}")
    
    st.sidebar.markdown("---")

    # --- CEREBRO (SESSION STATE) ---
    # Inicializamos variables de memoria para el mapa
    if 'lat_vista' not in st.session_state: st.session_state['lat_vista'] = 28.6353 
    if 'lon_vista' not in st.session_state: st.session_state['lon_vista'] = -106.0889
    if 'zoom_vista' not in st.session_state: st.session_state['zoom_vista'] = 13
    if 'marcador_memoria' not in st.session_state: st.session_state['marcador_memoria'] = None
    if 'ultimo_municipio' not in st.session_state: st.session_state['ultimo_municipio'] = None

    # Si el usuario cambia de municipio, reseteamos la vista
    if seleccion_nombre != st.session_state['ultimo_municipio']:
        if not data_filtrada.empty:
            st.session_state['lat_vista'] = data_filtrada.geometry.centroid.y.mean()
            st.session_state['lon_vista'] = data_filtrada.geometry.centroid.x.mean()
            st.session_state['zoom_vista'] = 13
        st.session_state['marcador_memoria'] = None
        st.session_state['ultimo_municipio'] = seleccion_nombre

    # --- PASO 2: BUSCADOR DE DIRECCIONES ---
    st.sidebar.markdown("### 🔎 Paso 2: Ubica una dirección")
    with st.sidebar.form(key='form_busqueda'):
        direccion_input = st.text_input("Calle y número:", placeholder="Ej: Av. Universidad 123")
        boton_buscar = st.form_submit_button("Ir al punto 📍")

    if boton_buscar and direccion_input:
        geolocator = Nominatim(user_agent="app_nse_chihuahua_fix_final")
        direccion_completa = f"{direccion_input}, {seleccion_nombre}, Chihuahua, México"
        try:
            location = geolocator.geocode(direccion_completa, timeout=10)
            if location:
                st.session_state['lat_vista'] = location.latitude
                st.session_state['lon_vista'] = location.longitude
                st.session_state['zoom_vista'] = 16
                st.session_state['marcador_memoria'] = {
                    'lat': location.latitude, 
                    'lon': location.longitude, 
                    'texto': direccion_input
                }
                st.success(f"📍 ¡Encontrado!")
            else:
                st.warning("No se encontró. Intenta añadir la Colonia.")
        except Exception:
            st.error("Error de conexión.")
    
    st.sidebar.markdown("---")
    
    # --- GUÍA DE NIVELES (AMAI) ---
    st.sidebar.markdown("### 📖 Guía de Niveles Socioeconómicos (AMAI)")
    # Aquí estaba el posible error, asegúrate de copiar toda esta línea:
    with st.sidebar.expander("¿Qué significan los colores?"):
        st.markdown("""
        <div style='background-color: #B3B3B3; color: white; padding: 5px; border-radius: 5px; margin-bottom: 5px;'>
        <b>A/B (Alto):</b> Ingresos altos. Total conectividad y servicios.
        </div>
        <div style='background-color: #72CF72; color: black; padding: 5px; border-radius: 5px; margin-bottom: 5px;'>
        <b>C+ (Medio Alto):</b> Ingresos superiores al promedio.
        </div>
        <div style='background-color: #BCEB6D; color: black; padding: 5px; border-radius: 5px; margin-bottom: 5px;'>
        <b>C (Medio):</b> Ingresos promedio. Necesidades cubiertas.
        </div>
        <div style='background-color: #FAF95D; color: black; padding: 5px; border-radius: 5px; margin-bottom: 5px;'>
        <b>C- (Medio Emergente):</b> Vulnerables a crisis leves.
        </div>
        <div style='background-color: #EDB552; color: black; padding: 5px; border-radius: 5px; margin-bottom: 5px;'>
        <b>D+ (Bajo Típico):</b> Problemas de infraestructura básica.
        </div>
        <div style='background-color: #FC8B63; color: white; padding: 5px; border-radius: 5px; margin-bottom: 5px;'>
        <b>D (Bajo Extremo):</b> Carencia de servicios.
        </div>
        <div style='background-color: #ED5454; color: white; padding: 5px; border-radius: 5px; margin-bottom: 5px;'>
        <b>E (Muy Bajo):</b> Escasez grave.
        </div>
        """, unsafe_allow_html=True)
        st.caption("Clasificación basada en Regla AMAI 2022-2024.")

    # --- FUENTES Y CRÉDITOS ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📂 Fuentes de Datos")
    st.sidebar.info("""
    **NSE (Socioeconómico):** Asociación Mexicana de Agencias de Inteligencia de Mercado y Opinión (AMAI).  
    *Estimación por AGEB basada en Censo 2020.*
    
    **Cartografía (Mapas):** Instituto Nacional de Estadística y Geografía (INEGI).  
    *Marco Geoestadístico (Edición 2023).*
    """)
    st.sidebar.caption("Aplicación desarrollada con fines de visualización estadística.")

    # ==========================================
    # TÍTULO Y MAPA PRINCIPAL
    # ==========================================
    st.title(f"🗺️ Nivel Socioeconómico: {seleccion_nombre}")
    st.markdown(f"Visualizando distribución de NSE en **{seleccion_nombre}**, Chihuahua.")

    if not data_filtrada.empty:
        # Crear el mapa base con la vista guardada en memoria
        m = folium.Map(
            location=[st.session_state['lat_vista'], st.session_state['lon_vista']], 
            zoom_start=st.session_state['zoom_vista']
        )

        # Definir colores
        colores_nse = {
            'AB': '#006400', 'C+': '#32CD32', 'C': '#ADFF2F',
            'C-': '#FFFF00', 'D+': '#FFA500', 'D': '#FF4500', 'E': '#FF0000'
        }
        
        def style_function(feature):
            nse = feature['properties']['NIVEL PREDOMINANTE']
            return {'fillColor': colores_nse.get(nse, 'gray'), 'color': 'black', 'weight': 0.5, 'fillOpacity': 0.6}

        # Agregar capa de AGEBs
        folium.GeoJson(
            data_filtrada,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['NOMBRE MUNICIPIO', 'NIVEL PREDOMINANTE', 'VIVIENDAS'],
                aliases=['Municipio:', 'NSE:', 'Viviendas:']
            )
        ).add_to(m)

        # Agregar pin de búsqueda si existe
        if st.session_state['marcador_memoria']:
            p = st.session_state['marcador_memoria']
            folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color="red"), popup=p['texto']).add_to(m)

        # Herramientas de dibujo
        draw = Draw(
            export=False,
            position='topleft',
            draw_options={'polyline': False, 'circlemarker': False, 'marker': False},
            edit_options={'edit': False}
        )
        draw.add_to(m)

        # Mostrar mapa
        output_mapa = st_folium(m, width="100%", height=600)

        # --- LÓGICA DE DESCARGA POR SELECCIÓN ---
        if output_mapa and 'last_active_drawing' in output_mapa and output_mapa['last_active_drawing'] is not None:
            geometry_data = output_mapa['last_active_drawing']['geometry']
            poligono_usuario = shape(geometry_data)
            
            # Buscar AGEBs dentro del dibujo (usando centroide)
            agebs_seleccionados = data_filtrada[data_filtrada.geometry.centroid.within(poligono_usuario)]
            
            cantidad_sel = len(agebs_seleccionados)
            viviendas_sel = int(agebs_seleccionados['VIVIENDAS'].sum())
            
            if cantidad_sel > 0:
                st.markdown("### 📊 Resultados de tu selección")
                c1, c2 = st.columns(2)
                c1.metric("AGEBs Capturados", cantidad_sel)
                c2.metric("Viviendas Totales", f"{viviendas_sel:,}")
                
                with st.expander("🔎 Ver detalles de la zona"):
                    cols_mostrar = ['CVEGEO', 'NIVEL PREDOMINANTE', 'VIVIENDAS', 'AB', 'C+', 'C', 'D+', 'D', 'E']
                    cols_finales = [c for c in cols_mostrar if c in agebs_seleccionados.columns]
                    st.dataframe(agebs_seleccionados[cols_finales])
                
                # Botón de descarga
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






