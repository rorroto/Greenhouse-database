import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from datetime import datetime

# 1. Configuración de la página (Estética)
st.set_page_config(page_title="Monitor de Invernaderos", page_icon="🍄", layout="wide")

# Conexión a Base de Datos
conn = sqlite3.connect('invernaderos.db', check_same_thread=False)
c = conn.cursor()

# Crear tablas si no existen
c.execute('CREATE TABLE IF NOT EXISTS invernaderos (id INTEGER PRIMARY KEY, nombre TEXT)')
c.execute('''CREATE TABLE IF NOT EXISTS registros 
             (id INTEGER PRIMARY KEY, inv_id INTEGER, fecha TEXT, t_max REAL, t_min REAL, h_max REAL, h_min REAL, co2 REAL)''')
conn.commit()

# --- INTERFAZ ---
st.title("🍄 Panel de Monitoreo Ambiental")
st.divider()

# Sidebar: Gestión de Invernaderos y Filtros
with st.sidebar:
    st.header("Configuración")
    nuevo_inv = st.text_input("Nuevo Invernadero")
    if st.button("Añadir"):
        c.execute('INSERT INTO invernaderos (nombre) VALUES (?)', (nuevo_inv,))
        conn.commit()
        st.success("Añadido")

    inv_df = pd.read_sql('SELECT * FROM invernaderos', conn)
    if not inv_df.empty:
        inv_seleccionado = st.selectbox("Seleccionar Invernadero", inv_df['nombre'])
        inv_id = inv_df[inv_df['nombre'] == inv_seleccionado]['id'].values[0]
        
        # Filtros de tiempo
        st.subheader("Filtros de Gráfica")
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        filtro_mes = st.selectbox("Mes", ["Todos"] + meses)
        filtro_año = st.number_input("Año", value=datetime.now().year)
    else:
        st.warning("Crea un invernadero para empezar")
        st.stop()

# --- CUERPO PRINCIPAL ---
tab1, tab2, tab3 = st.tabs(["📝 Registro", "📊 Visualización", "📋 Historial"])

with tab1:
    with st.form("registro_datos"):
        col1, col2 = st.columns(2)
        with col1:
            t_max = st.number_input("Temp Máxima (°C)", step=0.1)
            t_min = st.number_input("Temp Mínima (°C)", step=0.1)
        with col2:
            h_max = st.number_input("Humedad Máx (%)", step=0.1)
            h_min = st.number_input("Humedad Mín (%)", step=0.1)
        co2 = st.number_input("CO2 (ppm)", step=1.0)
        fecha = st.date_input("Fecha del registro", datetime.now())
        if st.form_submit_button("Guardar Datos"):
            c.execute('INSERT INTO registros (inv_id, fecha, t_max, t_min, h_max, h_min, co2) VALUES (?,?,?,?,?,?,?)',
                      (int(inv_id), str(fecha), t_max, t_min, h_max, h_min, co2))
            conn.commit()
            st.balloons()

with tab2:
    # Cargar datos y procesar promedios
    query = f"SELECT * FROM registros WHERE inv_id = {inv_id}"
    df = pd.read_sql(query, conn)
    
    if not df.empty:
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['prom_temp'] = (df['t_max'] + df['t_min']) / 2
        df['prom_hum'] = (df['h_max'] + df['h_min']) / 2
        
        # Filtrar por mes/año
        if filtro_mes != "Todos":
            mes_num = meses.index(filtro_mes) + 1
            df = df[(df['fecha'].dt.month == mes_num) & (df['fecha'].dt.year == filtro_año)]
        
        df_diario = df.groupby(df['fecha'].dt.date).mean().reset_index()

        # Métricas rápidas
        c1, c2, c3 = st.columns(3)
        c1.metric("Temp Promedio", f"{df_diario['prom_temp'].mean():.1f} °C")
        c2.metric("Humedad Promedio", f"{df_diario['prom_hum'].mean():.1f} %")
        c3.metric("CO2 Promedio", f"{df_diario['co2'].mean():.0f} ppm")

        # Climograma
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_diario['fecha'], y=df_diario['prom_hum'], name="Humedad %", 
                             marker_color='rgba(0, 0, 255, 0.3)', yaxis='y2'))
        fig.add_trace(go.Scatter(x=df_diario['fecha'], y=df_diario['prom_temp'], name="Temp °C", 
                                 line=dict(color='red', width=3)))
        
        fig.update_layout(
            title="Climograma Diario",
            yaxis=dict(title="Temperatura (°C)", range=[0, 45]),
            yaxis2=dict(title="Humedad (%)", range=[0, 100], overlaying='y', side='right'),
            hovermode="x unified", dragmode=False
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Gráfica CO2
        st.bar_chart(df_diario.set_index('fecha')['co2'])
    else:
        st.info("Aún no hay datos para mostrar gráficas.")

with tab3:
    st.subheader("Registros almacenados")
    df_hist = pd.read_sql(f"SELECT id, fecha, t_max, t_min, h_max, h_min, co2 FROM registros WHERE inv_id = {inv_id}", conn)
    st.dataframe(df_hist, use_container_width=True)
    
    id_borrar = st.number_input("ID del registro a eliminar", step=1, min_value=0)
    if st.button("Eliminar Registro", type="primary"):
        c.execute(f"DELETE FROM registros WHERE id = {id_borrar}")
        conn.commit()
        st.experimental_rerun()
