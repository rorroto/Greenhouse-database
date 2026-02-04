import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fpdf import FPDF
from datetime import datetime
import os
import tempfile

# --- DATABASE SETUP ---
DB_NAME = "hongos.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS invernaderos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  nombre TEXT UNIQUE NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registros 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  invernadero_id INTEGER, 
                  fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  temp_max REAL, 
                  temp_min REAL, 
                  hum_max REAL, 
                  hum_min REAL, 
                  co2 REAL,
                  FOREIGN KEY (invernadero_id) REFERENCES invernaderos(id) ON DELETE CASCADE)''')
    conn.commit()
    conn.close()

# --- DB HELPER FUNCTIONS ---
def add_invernadero(nombre):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO invernaderos (nombre) VALUES (?)", (nombre,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def rename_invernadero(id, nuevo_nombre):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE invernaderos SET nombre = ? WHERE id = ?", (nuevo_nombre, id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_invernadero(id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("DELETE FROM invernaderos WHERE id = ?", (id,))
    conn.commit()
    conn.close()

def get_invernaderos():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM invernaderos", conn)
    conn.close()
    return df

def add_registro(inv_id, fecha, t_max, t_min, h_max, h_min, co2):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO registros 
                 (invernadero_id, fecha, temp_max, temp_min, hum_max, hum_min, co2) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (inv_id, fecha, t_max, t_min, h_max, h_min, co2))
    conn.commit()
    conn.close()

def get_registros(inv_id=None):
    conn = get_connection()
    query = '''SELECT r.id, i.nombre as Invernadero, r.fecha, r.temp_max, r.temp_min, r.hum_max, r.hum_min, r.co2 
               FROM registros r 
               JOIN invernaderos i ON r.invernadero_id = i.id'''
    params = []
    if inv_id:
        query += " WHERE r.invernadero_id = ?"
        params.append(inv_id)
    query += " ORDER BY r.fecha DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if not df.empty:
        df['fecha'] = pd.to_datetime(df['fecha'])
    return df

def delete_registro(reg_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM registros WHERE id = ?", (reg_id,))
    conn.commit()
    conn.close()

# --- PDF EXPORT FUNCTION ---
def export_to_pdf(df, fig_climo, fig_co2):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Reporte de Monitoreo de Invernaderos", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 10, f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    
    # Save charts as images
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp1:
        fig_climo.write_image(tmp1.name)
        pdf.image(tmp1.name, x=10, y=30, w=190)
        tmp1_path = tmp1.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp2:
        fig_co2.write_image(tmp2.name)
        pdf.image(tmp2.name, x=10, y=130, w=190)
        tmp2_path = tmp2.name

    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Datos Históricos Filtrados", ln=True)
    pdf.set_font("Arial", "", 8)
    
    # Simple table
    cols = ["Fecha", "Inv.", "T Máx", "T Mín", "H Máx", "H Mín", "CO2"]
    col_widths = [35, 25, 20, 20, 20, 20, 25]
    
    for i, col in enumerate(cols):
        pdf.cell(col_widths[i], 7, col, border=1)
    pdf.ln()
    
    for idx, row in df.iterrows():
        pdf.cell(col_widths[0], 6, str(row['fecha'].strftime('%Y-%m-%d %H:%M')), border=1)
        pdf.cell(col_widths[1], 6, str(row['Invernadero']), border=1)
        pdf.cell(col_widths[2], 6, str(row['temp_max']), border=1)
        pdf.cell(col_widths[3], 6, str(row['temp_min']), border=1)
        pdf.cell(col_widths[4], 6, str(row['hum_max']), border=1)
        pdf.cell(col_widths[5], 6, str(row['hum_min']), border=1)
        pdf.cell(col_widths[6], 6, str(row['co2']), border=1)
        pdf.ln()
        if pdf.get_y() > 270:
            pdf.add_page()

    pdf_output = pdf.output(dest='S')
    
    # Cleanup
    os.remove(tmp1_path)
    os.remove(tmp2_path)
    
    return pdf_output

# --- UI APP ---
st.set_page_config(page_title="Monitoreo Hongos", layout="wide")
init_db()

st.title("🍄 Monitoreo de Invernaderos de Hongos")

# Sidebar for Greenhouse Management
st.sidebar.header("Gestión de Invernaderos")
inv_df = get_invernaderos()

with st.sidebar.expander("Añadir Invernadero"):
    nuevo_inv = st.text_input("Nombre del Invernadero")
    if st.button("Añadir"):
        if nuevo_inv:
            if add_invernadero(nuevo_inv):
                st.success(f"Añadido: {nuevo_inv}")
                st.rerun()
            else:
                st.error("Ya existe o error.")
        else:
            st.warning("Escribe un nombre.")

if not inv_df.empty:
    with st.sidebar.expander("Editar/Borrar Invernadero"):
        inv_to_edit = st.selectbox("Seleccionar Invernadero", inv_df['nombre'].tolist(), key="edit_sel")
        inv_id_to_edit = inv_df[inv_df['nombre'] == inv_to_edit]['id'].values[0]
        
        nuevo_nombre = st.text_input("Nuevo nombre", value=inv_to_edit)
        if st.button("Renombrar"):
            if rename_invernadero(inv_id_to_edit, nuevo_nombre):
                st.success("Renombrado")
                st.rerun()
            else:
                st.error("Error al renombrar")
        
        if st.button("Eliminar Invernadero", help="Borrará también todos sus registros"):
            delete_invernadero(inv_id_to_edit)
            st.success("Eliminado")
            st.rerun()
else:
    st.sidebar.info("No hay invernaderos registrados.")

# Main navigation
menu = ["Registro de Datos", "Visualización y Reportes", "Histórico"]
choice = st.selectbox("Menú Principal", menu)

if choice == "Registro de Datos":
    st.header("📝 Registro de Datos Diarios")
    if inv_df.empty:
        st.warning("Primero crea un invernadero en el panel lateral.")
    else:
        with st.form("registro_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                inv_sel = st.selectbox("Invernadero", inv_df['nombre'].tolist())
                fecha = st.date_input("Fecha", datetime.now())
                hora = st.time_input("Hora", datetime.now().time())
            
            with col2:
                co2 = st.number_input("CO2 (ppm)", min_value=0.0, step=10.0, value=400.0)
            
            st.subheader("Temperatura (°C)")
            c_t1, c_t2 = st.columns(2)
            t_max = c_t1.number_input("Máxima", step=0.1, value=25.0)
            t_min = c_t2.number_input("Mínima", step=0.1, value=18.0)
            
            st.subheader("Humedad (%)")
            c_h1, c_h2 = st.columns(2)
            h_max = c_h1.number_input("Máxima Hum", min_value=0.0, max_value=100.0, step=1.0, value=90.0)
            h_min = c_h2.number_input("Mínima Hum", min_value=0.0, max_value=100.0, step=1.0, value=70.0)
            
            fecha_full = datetime.combine(fecha, hora).strftime("%Y-%m-%d %H:%M:%S")
            inv_id_sel = inv_df[inv_df['nombre'] == inv_sel]['id'].values[0]
            
            submit = st.form_submit_button("Guardar Registro")
            if submit:
                add_registro(inv_id_sel, fecha_full, t_max, t_min, h_max, h_min, co2)
                st.success("Registro guardado correctamente.")

elif choice == "Visualización y Reportes" or choice == "Histórico":
    st.sidebar.divider()
    st.sidebar.header("Filtros de Datos")
    all_regs = get_registros()
    
    if all_regs.empty:
        st.warning("No hay datos para filtrar.")
        filtered_df = all_regs
    else:
        years = sorted(all_regs['fecha'].dt.year.unique().tolist(), reverse=True)
        year_sel = st.sidebar.selectbox("Año", ["Ver todo"] + [str(y) for y in years])
        months_names = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        month_sel = st.sidebar.selectbox("Mes", ["Ver todo"] + months_names)
        inv_filter_sel = st.sidebar.selectbox("Invernadero", ["Todos"] + inv_df['nombre'].tolist())
        
        filtered_df = all_regs.copy()
        if year_sel != "Ver todo":
            filtered_df = filtered_df[filtered_df['fecha'].dt.year == int(year_sel)]
        if month_sel != "Ver todo":
            month_idx = months_names.index(month_sel) + 1
            filtered_df = filtered_df[filtered_df['fecha'].dt.month == month_idx]
        if inv_filter_sel != "Todos":
            filtered_df = filtered_df[filtered_df['Invernadero'] == inv_filter_sel]

    if choice == "Visualización y Reportes":
        st.header("📊 Análisis de Clima")
        if filtered_df.empty:
            st.info("No hay datos con los filtros seleccionados.")
        else:
            df_daily = filtered_df.copy()
            df_daily['fecha_dia'] = df_daily['fecha'].dt.date
            df_grouped = df_daily.groupby('fecha_dia').agg({
                'temp_max': 'max',
                'temp_min': 'min',
                'hum_max': 'max',
                'hum_min': 'min',
                'co2': 'mean'
            }).reset_index().sort_values('fecha_dia')

            # --- CLIMOGRAMA ---
            fig_climo = make_subplots(specs=[[{"secondary_y": True}]])
            fig_climo.add_trace(
                go.Bar(x=df_grouped['fecha_dia'], y=df_grouped['hum_max'], 
                       name="Humedad Máx", marker_color='rgba(0, 0, 255, 0.3)',
                       hovertemplate='%{y}%'),
                secondary_y=True
            )
            fig_climo.add_trace(
                go.Scatter(x=df_grouped['fecha_dia'], y=df_grouped['temp_max'], 
                           name="Temp Máxima", mode='lines+markers', marker_color='red',
                           hovertemplate='%{y}°C'),
                secondary_y=False
            )
            fig_climo.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig_climo.update_yaxes(title_text="Temperatura (°C)", range=[0, 50], secondary_y=False)
            fig_climo.update_yaxes(title_text="Humedad (%)", range=[0, 100], secondary_y=True)
            
            st.plotly_chart(fig_climo, use_container_width=True, config={'displayModeBar': False})

            # --- CO2 CHART ---
            fig_co2 = go.Figure()
            fig_co2.add_trace(go.Bar(x=df_grouped['fecha_dia'], y=df_grouped['co2'], name="CO2 Promedio", marker_color='green', hovertemplate='%{y} ppm'))
            fig_co2.update_layout(hovermode="x unified", xaxis_title="Fecha", yaxis_title="CO2 (ppm)")
            
            st.plotly_chart(fig_co2, use_container_width=True, config={'displayModeBar': False})

            # --- PDF EXPORT BUTTON ---
            st.divider()
            if st.button("Generar Reporte PDF"):
                with st.spinner("Generando PDF..."):
                    pdf_data = export_to_pdf(filtered_df, fig_climo, fig_co2)
                    st.download_button(
                        label="⬇️ Descargar Reporte PDF",
                        data=pdf_data,
                        file_name=f"reporte_hongos_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )

    elif choice == "Histórico":
        st.header("📜 Histórico de Registros")
        if filtered_df.empty:
            st.info("No hay registros para mostrar.")
        else:
            st.dataframe(filtered_df, use_container_width=True)
            
            st.subheader("Eliminar Registro")
            reg_id_to_del = st.number_input("ID del registro a eliminar", min_value=1, step=1)
            if st.button("Eliminar Registro"):
                if reg_id_to_del in all_regs['id'].values:
                    delete_registro(reg_id_to_del)
                    st.success(f"Registro {reg_id_to_del} eliminado.")
                    st.rerun()
                else:
                    st.error("ID no encontrado.")
