import streamlit as st
import pymysql
import pandas as pd
import folium
import json
import plotly.express as px
from streamlit_folium import folium_static

# Conexión a la base de datos
def connect_db():
    return pymysql.connect(
        host='sql5.freesqldatabase.com',
        user='sql5790740',
        password='3wPGJAURgi',
        database='sql5790740',
        port=3306
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

st.set_page_config(page_title="Sistema de Ingeniería Electoral", page_icon="📊", layout="wide")


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
def create_map_with_layers(results, municipio):
    map_center = [23.6345, -102.5528]  
    zoom_start = 6  
    
    m = folium.Map(location=map_center, zoom_start=zoom_start)

    geojson_url = 'json/simplify.json'
    try:
        with open(geojson_url) as f:
            geojson_data = json.load(f)
    except Exception as e:
        st.error(f"Error al cargar el archivo GeoJSON: {e}")
        return None

    municipio_normalizado = normalize_name(municipio)
    filtered_data = [
        feature for feature in geojson_data['features'] 
        if normalize_name(feature['properties']['nom_mun_ine']) == municipio_normalizado
    ]
    
    if not filtered_data:
        st.warning(f"No se encontraron datos para el municipio {municipio}.")
        return m

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

    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    layers = {
        'Ayuntamiento 2016': folium.FeatureGroup(name='Ayuntamiento 2016'),
        'Ayuntamiento 2018': folium.FeatureGroup(name='Ayuntamiento 2018'),
        'Ayuntamiento 2021': folium.FeatureGroup(name='Ayuntamiento 2021')
    }
    
    colors = {
        '2016': 'blue',
        '2018': 'green',
        '2021': 'red'
    }

    for year in ['2016', '2018', '2021']:
        year_results = [result for result in results if year in result['tabla']]
        for feature in filtered_data:
            seccion = feature['properties']['cve_seccion'].zfill(4)
            match = next((result for result in year_results if str(result['seccion']).zfill(4) == seccion), None)
            votos = match['votos'] if match else "Sin datos"

            popup = folium.Popup(f"Sección: {seccion}<br>Votos: {votos}", max_width=200)
            folium.GeoJson(
                feature,
                popup=popup,
                style_function = lambda feature, year=year: {'color': colors[year], 'weight': 2}
            ).add_to(layers[f'Ayuntamiento {year}'])

    for layer in layers.values():
        layer.add_to(m)

    folium.LayerControl().add_to(m)

    return m

# Streamlit UI
st.title('Sistema de ingeniería electoral e inteligencia territorial')

# Sidebar
tipo = st.sidebar.selectbox("Tipo de análisis", ["", "Ayuntamiento", "Gobernatura", "Diputacion"])
partido = st.sidebar.selectbox("Partido Político", ["", "PAN", "PRI", "MORENA", "PRD", "PVEM", "PT", "MC", "PAN_PRD_MC","PAN_PRD"])
municipio = st.sidebar.selectbox("Municipio", get_municipios())
with st.spinner('Cargando resultados...'):
    
    if st.sidebar.button('Consultar', key='consultar_button'):
        if tipo and partido and municipio:
        # Obtener resultados
         results = get_results(tipo, partido, municipio)
        if results:
            # Crear mapa
            m = create_map_with_layers(results, municipio)
            st.write("Resultados por tabla:")

            # Crear DataFrame
            df = pd.DataFrame(results)
            if not df.empty:
                # Análisis comparativo compacto y visual
                df['year'] = df['tabla'].apply(lambda x: x[-4:])  
                df_comparativo = df.groupby(['seccion', 'year'])['votos'].sum().reset_index()

                # Pivotar para tener las secciones como filas y los años como columnas
                df_comparativo = df_comparativo.pivot(index='seccion', columns='year', values='votos')

                if not df_comparativo.empty:
                    st.write("**Análisis comparativo de votos por sección y año:**")
                    st.dataframe(df_comparativo)

                    # Crear gráfico interactivo con Plotly
                    fig = px.bar(df_comparativo, 
                                 x=df_comparativo.index, 
                                 y=['2016', '2018', '2021'],
                                 title=f"Votos por sección para {municipio}",
                                 labels={'value': 'Votos', 'seccion': 'Sección'},
                                 barmode='group')
                    fig.update_layout(xaxis_title='Sección', yaxis_title='Votos')
                    st.plotly_chart(fig)

            # Mostrar el mapa
            folium_static(m)
        else:
            st.write("No se encontraron resultados.")
    else:
        st.write("Por favor, complete todos los campos.")

# Función para obtener resultados de LISTA_NOMINAL
def get_lista_nominal(tipo, municipio):
    municipio_normalizado = normalize_name(municipio)
    connection = connect_db()
    cursor = connection.cursor()

    if tipo == "Ayuntamiento":
        tablas = ['ayuntamiento2016', 'ayuntamiento2018', 'ayuntamiento2021']
    else:
        tablas = []

    lista_nominal_results = []
    for tabla in tablas:
        query = f"SELECT Municipio, SECCION, `LISTA_NOMINAL` FROM {tabla} WHERE Municipio = %s"
        cursor.execute(query, (municipio_normalizado,))
        rows = cursor.fetchall()
        for row in rows:
            lista_nominal_results.append({
                'municipio': row[0],
                'seccion': row[1],
                'lista_nominal': row[2],
                'tabla': tabla
            })
    connection.close()
    return lista_nominal_results
with st.spinner('Cargando resultados...'):

    if st.sidebar.button('Análisis Lista Nominal'):
     if tipo and partido and municipio:
        # Obtener resultados
        results = get_results(tipo, partido, municipio)
        lista_nominal_results = get_lista_nominal(tipo, municipio)

        if results and lista_nominal_results:
            # Crear mapa
            m = create_map_with_layers(results, municipio)
            st.write("Resultados por tabla:")

            # Crear DataFrame de votos y lista nominal
            df_votos = pd.DataFrame(results)
            df_lista_nominal = pd.DataFrame(lista_nominal_results)

            if not df_votos.empty and not df_lista_nominal.empty:
                # Combinar ambos DataFrames por sección y tabla
                df_combined = pd.merge(
                    df_votos, df_lista_nominal, 
                    on=['seccion', 'tabla'], 
                    suffixes=('_votos', '_lista_nominal')
                )

                # Calcular la relación votos / lista nominal
                df_combined['relacion_votos_lista'] = (
                    df_combined['votos'] / df_combined['lista_nominal'] * 100
                ).round(2)

                st.write("**Análisis de LISTA_NOMINAL y relación votos / lista nominal:**")
                st.dataframe(df_combined)

                # Análisis comparativo de lista nominal por sección y año
                df_combined['year'] = df_combined['tabla'].apply(lambda x: x[-4:])
                df_lista_nominal_comparativo = df_combined.groupby(['seccion', 'year'])['lista_nominal'].sum().reset_index()

                if not df_lista_nominal_comparativo.empty:
                    st.write("**Análisis de lista nominal por sección y año:**")
                    st.dataframe(df_lista_nominal_comparativo)

                    # Crear gráfico de lista nominal con Plotly
                    fig_nominal = px.bar(df_lista_nominal_comparativo, 
                                         x=df_lista_nominal_comparativo['seccion'], 
                                         y='lista_nominal', 
                                         color='year', 
                                         title=f"Lista Nominal por Sección para {municipio}",
                                         labels={'seccion': 'Sección', 'lista_nominal': 'Lista Nominal'})
                    st.plotly_chart(fig_nominal)

            folium_static(m)
        else:
            st.write("No se encontraron resultados de listas nominales.")
    else:
        st.write(" ")
