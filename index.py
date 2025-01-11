import streamlit as st
import pymysql
import pandas as pd
import folium
from folium import plugins
import geopandas as gpd
import json
from streamlit_folium import folium_static
# Conexión a la base de datos
def connect_db():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='ironman'
    )

# Obtener los municipios
def get_municipios():
    connection = connect_db()
    cursor = connection.cursor()
    query = "SELECT DISTINCT Municipio FROM ayuntamiento2016 WHERE Municipio NOT LIKE '%TOTAL%'"
    cursor.execute(query)
    municipios = [row[0] for row in cursor.fetchall()]
    connection.close()
    return municipios

# Normalizar nombres
def normalize_name(name):
    replacements = {
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'Ñ': 'N',
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name.upper().strip()

# Función para obtener los resultados de la base de datos
def get_results(tipo, partido, municipio):
    municipio_normalizado = normalize_name(municipio)
    connection = connect_db()
    cursor = connection.cursor()

    if tipo == "Ayuntamiento":
        tablas = ['ayuntamiento2016', 'ayuntamiento2018', 'ayuntamiento2021']
    elif tipo == "Gobernatura":
        tablas = ['gobernatura2016', 'gobernatura2018', 'gobernatura2021']
    elif tipo == "Diputacion":
        tablas = ['diputacion2016', 'diputacion2018', 'diputacion2021']
    else:
        tablas = []

    results = []
    for tabla in tablas:
        query = f"SELECT Municipio, SECCION, `{partido}` AS votos FROM {tabla} WHERE Municipio = %s"
        cursor.execute(query, (municipio_normalizado,))
        rows = cursor.fetchall()
        for row in rows:
            results.append({
                'municipio': row[0],
                'seccion': row[1],
                'votos': row[2],
                'tabla': tabla
            })
    connection.close()
    return results

# Crear el mapa con Folium
def normalize_name(name):
    # Convertir todo el nombre a minúsculas y eliminar espacios adicionales
    return name.strip().lower()

def create_map_with_layers(results, municipio):
    map_center = [23.6345, -102.5528]  # Coordenadas generales si no encontramos coordenadas específicas
    zoom_start = 6  # Nivel de zoom por defecto
    
    m = folium.Map(location=map_center, zoom_start=zoom_start)

    geojson_url = 'json/simplify.json'  # Ruta a tu archivo GeoJSON
    try:
        with open(geojson_url) as f:
            geojson_data = json.load(f)
    except Exception as e:
        st.error(f"Error al cargar el archivo GeoJSON: {e}")
        return None

    # Normalizar el nombre del municipio a minúsculas
    municipio_normalizado = normalize_name(municipio)
    
    # Filtrar el GeoJSON para el municipio específico
    filtered_data = [
        feature for feature in geojson_data['features'] 
        if normalize_name(feature['properties']['nom_mun_ine']) == municipio_normalizado
    ]
    
    if not filtered_data:
        st.warning(f"No se encontraron datos para el municipio {municipio}.")
        return m

    # Obtenemos las coordenadas del centro del municipio (si existen en el GeoJSON)
    latitudes = []
    longitudes = []

    for feature in filtered_data:
        coordinates = feature['geometry']['coordinates']
        if feature['geometry']['type'] == 'Polygon' or feature['geometry']['type'] == 'MultiPolygon':
            latitudes.append(coordinates[0][0][1])
            longitudes.append(coordinates[0][0][0])
        else:
            latitudes.append(coordinates[1])
            longitudes.append(coordinates[0])

    center_lat = sum(latitudes) / len(latitudes)
    center_lon = sum(longitudes) / len(longitudes)

    # Ajustamos el mapa al centro del municipio
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    # Crear diferentes capas para cada año
    layers = {
        'Ayuntamiento 2016': folium.FeatureGroup(name='Ayuntamiento 2016'),
        'Ayuntamiento 2018': folium.FeatureGroup(name='Ayuntamiento 2018'),
        'Ayuntamiento 2021': folium.FeatureGroup(name='Ayuntamiento 2021')
    }

    # Filtrar resultados por año y añadir las capas correspondientes
    for year in ['2016', '2018', '2021']:
        year_results = [result for result in results if year in result['tabla']]
        for feature in filtered_data:
            seccion = feature['properties']['cve_seccion'].zfill(4)
            match = next((result for result in year_results if str(result['seccion']).zfill(4) == seccion), None)
            votos = match['votos'] if match else "Sin datos"

            # Crear un popup para cada sección
            popup = folium.Popup(f"Sección: {seccion}<br>Votos: {votos}", max_width=200)
            folium.GeoJson(
                feature,
                popup=popup,
                style_function=lambda feature: {'color': 'blue', 'weight': 2}
            ).add_to(layers[f'Ayuntamiento {year}'])

    # Añadir las capas al mapa y agregar el control de capas
    for layer in layers.values():
        layer.add_to(m)

    folium.LayerControl().add_to(m)

    return m

    # Añadir capas de votos al mapa
    for feature in filtered_data:
        seccion = feature['properties']['cve_seccion'].zfill(4)
        match = next((result for result in results if str(result['seccion']).zfill(4) == seccion), None)
        votos = match['votos'] if match else "Sin datos"
        
        # Crear un popup para cada sección
        popup = folium.Popup(f"Sección: {seccion}<br>Votos: {votos}", max_width=200)
        folium.GeoJson(feature, popup=popup, style_function=lambda feature: {
            'color': 'blue', 'weight': 2
        }).add_to(m)
    
    return m



# Streamlit UI
st.title('Análisis Político con Mapas')

# Formulario
tipo = st.selectbox("Tipo de análisis", ["", "Ayuntamiento", "Gobernatura", "Diputacion"])
partido = st.selectbox("Partido Político", ["", "PAN", "PRI", "MORENA", "PRD", "PVEM", "PT", "MC"])
municipio = st.selectbox("Municipio", get_municipios())

if st.button('Consultar'):
    if tipo and partido and municipio:
        # Obtener resultados
        results = get_results(tipo, partido, municipio)
        if results:
            # Crear mapa
            m = create_map_with_layers(results, municipio)
            st.write("Resultados por tabla:")
            # Mostrar el mapa
            folium_static(m)
        else:
            st.write("No se encontraron resultados.")
    else:
        st.write("Por favor, complete todos los campos.")
