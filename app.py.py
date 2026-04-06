import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURACIÓN DE BASE DE DATOS ---
DB_NAME = "gestion_af_accesorios.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabla Artículos
    c.execute('''CREATE TABLE IF NOT EXISTS articulos 
                 (id INTEGER PRIMARY KEY, rubro TEXT, proveedor TEXT, accesorio TEXT, 
                  stock REAL, costo_base REAL, flete REAL, ganancia REAL, 
                  lista1 REAL, lista2 REAL, descripcion TEXT)''')
    # Tabla Clientes
    c.execute('''CREATE TABLE IF NOT EXISTS clientes 
                 (id INTEGER PRIMARY KEY, nombre TEXT, tel TEXT, localidad TEXT, 
                  direccion TEXT, saldo REAL)''')
    # Tabla Movimientos
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, tipo TEXT, 
                  monto REAL, metodo TEXT, detalle TEXT)''')
    conn.commit()
    conn.close()

def ejecutar_query(query, params=(), commit=False):
    conn = sqlite3.connect(DB_NAME)
    if commit:
        conn.execute(query, params)
        conn.commit()
        conn.close()
    else:
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

init_db()

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="AF Accesorios - Gestión Nube", layout="wide")

# Constantes
WHATSAPP_NUM = "5493413512049"

# Carga de datos desde SQL
df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")
df_movs = ejecutar_query("SELECT * FROM movimientos")

# Session States
if "carrito" not in st.session_state: st.session_state.carrito = []
if "remito_items" not in st.session_state: st.session_state.remito_items = []

# --- UTILIDADES ---
def formatear_moneda(valor):
    try:
        v = round(float(valor), 2)
        return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True, align="C")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 5, "Casilda, Santa Fe | Gestión en la Nube", ln=True, align="C")
        self.ln(10)

def generar_pdf_binario(cliente_nombre, carrito, total, titulo="PRESUPUESTO"):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"{titulo} - CLIENTE: {cliente_nombre}", ln=True)
    pdf.cell(0, 10, f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(5)
    for item in carrito:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, f"{item['Cant']}x {item['Producto']} - P.U: {formatear_moneda(item['Precio U.'])} - Sub: {formatear_moneda(item['Subtotal'])}", ln=True, border=1)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"TOTAL: {formatear_moneda(total)}", align="R")
    return bytes(pdf.output(dest='S'))

# --- INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestos", "📋 Órdenes", "🏁 Cierre", "📦 Remitos"])

# TAB 0: STOCK
with tabs[0]:
    st.header("Inventario Real-Time")
    if not df_stock.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Costo Stock", formatear_moneda((df_stock['costo_base'] * df_stock['stock']).sum()))
        c2.metric("Total L1", formatear_moneda((df_stock['lista1'] * df_stock['stock']).sum()))
        c3.metric("Total L2", formatear_moneda((df_stock['lista2'] * df_stock['stock']).sum()))
    st.dataframe(df_stock, use_container_width=True, hide_index=True)

# TAB 1: LOTE (RESTAURADO)
with tabs[1]:
    st.header("🚚 Carga por Lote")
    st.write("Pegá aquí tus artículos nuevos o actualizaciones de stock.")
    df_lote = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_lote, num_rows="dynamic", use_container_width=True)
    if st.button("Procesar Lote"):
        conn = sqlite3.connect(DB_NAME)
        # Lógica: Si el accesorio existe, actualiza; si no, inserta.
        for _, row in ed_lote.iterrows():
            l1 = (row['costo_base'] + row['flete']) * (1 + row['ganancia']/100)
            l2 = l1 * 0.90
            ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                              VALUES (?,?,?,?,?,?,?,?,?)''', 
                           (row['rubro'], row['proveedor'], row['accesorio'], row['stock'], row['costo_base'], row['flete'], row['ganancia'], l1, l2), commit=True)
        st.success("Lote procesado correctamente")
        st.rerun()

# TAB 2: MAESTRO
with tabs[2]:
    st.header("⚙️ Editor Maestro")
    df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
    if st.button("Guardar Cambios Maestro"):
        df_ed["lista1"] = (df_ed["costo_base"] + df_ed["flete"]) * (1 + df_ed["ganancia"] / 100)
        df_ed["lista2"] = df_ed["lista1"] * 0.90
        conn = sqlite3.connect(DB_NAME)
        df_ed.to_sql("articulos", conn, if_exists="replace", index=False)
        conn.close()
        st.success("Base actualizada")
        st.rerun()

# TAB 3: CTA CTE
with tabs[3]:
    st.header("👥 Clientes")
    if not df_clientes.empty:
        cli_sel = st.selectbox("Seleccionar Cliente", df_clientes["nombre"].tolist())
        datos_cli = df_clientes[df_clientes["nombre"] == cli_sel].iloc[0]
        st.metric("Saldo", formatear_moneda(datos_cli["saldo"]))
        # Registrar Pago
        pago = st.number_input("Registrar Entrega de Efectivo:", min_value=0.0)
        if st.button("Cargar Pago"):
            ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (pago, cli_sel), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                           (datetime.now().strftime("%d/%m/%Y %H:%M"), cli_sel, "PAGO", pago, "Pago efectivo"), commit=True)
            st.rerun()

# TAB 4: PRESUPUESTADOR
with tabs[4]:
    st.header("📄 Presupuestos y Ventas")
    cli_v = st.selectbox("Cliente para Venta:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Final"])
    col1, col2, col3 = st.columns([2,1,1])
    with col1: art_v = st.selectbox("Producto", df_stock["accesorio"].tolist())
    with col2: cant_v = st.number_input("Cant", 1, key="v_q")
    with col3: lst_v = st.selectbox("Lista", ["lista1", "lista2"], key="v_l")
    
    if st.button("Agregar Item"):
        p_u = df_stock[df_stock["accesorio"] == art_v][lst_v].values[0]
        st.session_state.carrito.append({"Producto": art_v, "Cant": cant_v, "Precio U.": p_u, "Subtotal": p_u * cant_v})
        st.rerun()
    
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        total_v = sum(i["Subtotal"] for i in st.session_state.carrito)
        st.subheader(f"Total: {formatear_moneda(total_v)}")
        if st.button("Confirmar Orden (Afecta Stock y Saldo)"):
            for item in st.session_state.carrito:
                ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (item["Cant"], item["Producto"]), commit=True)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total_v, cli_v), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                           (datetime.now().strftime("%d/%m/%Y %H:%M"), cli_v, "VENTA", total_v, "Venta de accesorios"), commit=True)
            st.session_state.carrito = []
            st.success("Venta Grabada")
            st.rerun()

# TAB 5: ÓRDENES / HISTORIAL (RESTAURADO)
with tabs[5]:
    st.header("📋 Historial Global de Movimientos")
    st.dataframe(df_movs.sort_index(ascending=False), use_container_width=True, hide_index=True)

# TAB 6: CIERRE
with tabs[6]:
    st.header("🏁 Resumen de Caja")
    st.metric("Total Deuda Clientes", formatear_moneda(df_clientes["saldo"].sum()))
    st.metric("Valorización de Stock (Costo)", formatear_moneda((df_stock["stock"] * df_stock["costo_base"]).sum()))

# TAB 7: REMITOS (FECHA ACTUAL)
with tabs[7]:
    st.header("📦 Remitos Rápidos")
    cli_r = st.selectbox("Cliente Remito:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
    # Lógica de Remito (Igual al presupuestador pero solo genera PDF)
    if st.button("Generar PDF Remito"):
        pdf_rem = generar_pdf_binario(cli_r, st.session_state.carrito, sum(i["Subtotal"] for i in st.session_state.carrito), "REMITO")
        st.download_button("Descargar Remito", pdf_rem, "Remito.pdf")
