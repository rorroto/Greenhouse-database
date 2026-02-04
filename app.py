import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from datetime import datetime

# 1. Configuración de la página
st.set_page_config(page_title="Monitor de Invernaderos", page_icon="🍄", layout="wide")

# Conexión a Base de Datos
conn = sqlite3.connect('invernaderos.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS invernaderos (id INTEGER PRIMARY KEY, nombre TEXT)')
c.execute('''CREATE TABLE IF NOT EXISTS registros 
             (id INTEGER PRIMARY KEY, inv_id INTEGER, fecha TEXT, t_max REAL, t_min REAL, h_max REAL, h_min REAL, co2 REAL)''')
conn.commit()

st.title("🍄 Panel de Monitoreo Ambiental")
st.divider()

with st.sidebar:
    st.header("Configuración")
    nuevo_inv = st.text_input("Nuevo Invernadero")
    if st.button("Añadir"):
        c.execute('INSERT INTO invernaderos (nombre) VALUES (?)', (nuevo_inv,))
        conn.commit()
        st.success("Invernadero creado")
        st.rerun()

    inv_df = pd.read_sql('SELECT * FROM invernaderos', conn)
    if not inv_df.empty:
        inv_seleccionado = st.selectbox("Seleccionar Invernadero", inv_df['nombre'])
        inv_id = int(inv_df[inv_df['nombre'] == inv_seleccionado]['id'].values[0])
        
        st.subheader("Filtros de Tiempo")
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        filtro_mes = st.selectbox("Mes", ["Todos"] + meses)
        filtro_año = st.number_input("Año", value=datetime.now().year, step=1)
    else:
        st.warning("Crea un invernadero para empezar")
        st.stop()

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
        fecha_reg = st.date_input("Fecha del registro", datetime.now())
        if st.form_submit_button("Guardar Datos"):
            c.execute('INSERT INTO registros (inv_id, fecha, t_max, t_min, h_max, h_min, co2) VALUES (?,?,?,?,?,?,?)',
                      (inv_id, str(fecha_reg), t_max, t_min, h_max, h_min, co2))
            conn.commit()
            st.success("Datos guardados correctamente")
            st.balloons()

with tab2:
    df = pd.read_sql(f"SELECT * FROM registros WHERE inv_id = {inv_id}", conn)
    
    if not df.empty:
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['prom_temp'] = (df['t_max'] + df['t_min']) / 2
        df['prom_hum'] = (df['h_max'] + df['h_min']) / 2
        
        if filtro_mes != "Todos":
            mes_num = meses.index(filtro_mes) + 1
            df = df[(df['fecha'].dt.month == mes_num) & (df['fecha'].dt.year == filtro_año)]
        
        # CORRECCIÓN DEL ERROR: Agrupación segura
        df_diario = df.groupby(df['fecha'].dt.date).agg({
            'prom_temp': 'mean',
            'prom_hum': 'mean',
            'co2': 'mean'
        }).reset_index()
        df_diario.columns = ['fecha_dia', 'prom_temp', 'prom_hum', 'co2']

        if not df_diario.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Temp Promedio", f"{df_diario['prom_temp'].mean():.1f} °C")
            c2.metric("Humedad Promedio", f"{df_diario['prom_hum'].mean():.1f} %")
            c3.metric("CO2 Promedio", f"{df_diario['co2'].mean():.0f} ppm")

            # Climograma mejorado
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_diario['fecha_dia'], y=df_diario['prom_hum'], name="Humedad %", 
                                 marker_color='rgba(0, 150, 255, 0.3)', yaxis='y2'))
            fig.add_trace(go.Scatter(x=df_diario['fecha_dia'], y=df_diario['prom_temp'], name="Temp °C", 
                                     line=dict(color='red', width=3), mode='lines+markers'))
            
            fig.update_layout(
                title=f"Climograma: {inv_seleccionado}",
                yaxis=dict(title="Temperatura (°C)", range=[0, 50]),
                yaxis2=dict(title="Humedad (%)", range=[0, 100], overlaying='y', side='right'),
                hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Concentración de CO2")
            st.bar_chart(df_diario.set_index('fecha_dia')['co2'])
        else:
            st.warning("No hay datos para el mes/año seleccionado.")
    else:
        st.info("Registra tu primer dato en la pestaña 'Registro' para ver gráficas.")

with tab3:
    st.subheader("Historial de Datos")
    df_hist = pd.read_sql(f"SELECT id, fecha, t_max, t_min, h_max, h_min, co2 FROM registros WHERE inv_id = {inv_id}", conn)
    st.dataframe(df_hist.sort_values(by='fecha', ascending=False), use_container_width=True)
    
    col_del1, col_del2 = st.columns([1, 3])
    with col_del1:
        id_borrar = st.number_input("ID a eliminar", step=1, min_value=0)
        if st.button("Eliminar Registro", type="primary"):
            c.execute("DELETE FROM registros WHERE id = ?", (id_borrar,))
            conn.commit()
            st.rerun()
