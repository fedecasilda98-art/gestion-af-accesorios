import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from fpdf import FPDF
from io import BytesIO

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
DB_PATH = "/app/data"
DB_NAME = os.path.join(DB_PATH, "gestion_af_accesorios.db")

if not os.path.exists(DB_PATH):
    try:
        os.makedirs(DB_PATH)
    except:
        DB_NAME = "gestion_af_accesorios.db" 

def ejecutar_query(query, params=(), commit=False):
    conn = sqlite3.connect(DB_NAME)
    try:
        if commit:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        else:
            return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error: {e}")
    finally:
        conn.close()

def init_db():
    ejecutar_query('''CREATE TABLE IF NOT EXISTS articulos 
                 (id INTEGER PRIMARY KEY, rubro TEXT, proveedor TEXT, accesorio TEXT, 
                  stock REAL, costo_base REAL, flete REAL, ganancia REAL, 
                  lista1 REAL, lista2 REAL, descripcion TEXT)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS clientes 
                 (id INTEGER PRIMARY KEY, nombre TEXT, tel TEXT, localidad TEXT, 
                  direccion TEXT, saldo REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, tipo TEXT, 
                  monto REAL, metodo TEXT, detalle TEXT)''', commit=True)

init_db()

# --- 2. CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="AF Accesorios - Gestión", layout="wide")

def formatear_moneda(valor):
    try:
        return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "AF ACCESORIOS - ALUMINIO", ln=True, align="C")
        self.ln(10)

def generar_pdf_binario(cliente, carrito, total, titulo="REMITO"):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"{titulo} - CLIENTE: {cliente}", ln=True)
    pdf.cell(0, 10, f"FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(5)
    for item in carrito:
        txt = f"{item['Cant']}x {item['Producto']} - Sub: {formatear_moneda(item['Subtotal'])}"
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, txt, ln=True, border=1)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"TOTAL: {formatear_moneda(total)}", align="R")
    return pdf.output(dest='S').encode('latin-1')

# --- 3. CARGA DE DATOS ---
df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")
df_movs = ejecutar_query("SELECT * FROM movimientos")

if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 4. INTERFAZ POR PESTAÑAS ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

with tabs[0]: # STOCK
    st.header("Inventario Actual")
    if not df_stock.empty:
        c1, c2 = st.columns(2)
        c1.metric("Costo Total Stock", formatear_moneda((df_stock['costo_base'] * df_stock['stock']).sum()))
        c2.metric("Artículos Únicos", len(df_stock))
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # LOTE (BLINDADO)
    st.header("🚚 Carga Masiva")
    df_lote = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_lote, num_rows="dynamic", use_container_width=True)
    if st.button("Procesar Lote"):
        for _, r in ed_lote.iterrows():
            if r['accesorio']:
                try:
                    s = float(r['stock']) if pd.notnull(r['stock']) else 0.0
                    cb = float(r['costo_base']) if pd.notnull(r['costo_base']) else 0.0
                    f = float(r['flete']) if pd.notnull(r['flete']) else 0.0
                    g = float(r['ganancia']) if pd.notnull(r['ganancia']) else 0.0
                    l1 = (cb + f) * (1 + g/100)
                    ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                     VALUES (?,?,?,?,?,?,?,?,?)''', (r['rubro'], r['proveedor'], r['accesorio'], s, cb, f, g, l1, l1*0.9), commit=True)
                except: continue
        st.success("Lote cargado")
        st.rerun()

with tabs[2]: # MAESTRO
    st.header("⚙️ Editor Maestro")
    if not df_stock.empty:
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios"):
            conn = sqlite3.connect(DB_NAME)
            df_ed.to_sql("articulos", conn, if_exists="replace", index=False)
            conn.close()
            st.rerun()

with tabs[3]: # CTA CTE
    st.header("👥 Cuentas Corrientes")
    if not df_clientes.empty:
        sel = st.selectbox("Cliente:", df_clientes["nombre"].tolist())
        cli = df_clientes[df_clientes["nombre"] == sel].iloc[0]
        st.subheader(f"Saldo: {formatear_moneda(cli['saldo'])}")
        m_p = st.number_input("Cobrar $", min_value=0.0)
        if st.button("Registrar Pago"):
            ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (m_p, sel), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                           (datetime.now().strftime("%d/%m/%Y %H:%M"), sel, "PAGO", m_p, "Cobro"), commit=True)
            st.rerun()
    with st.expander("Nuevo Cliente"):
        n_c = st.text_input("Nombre")
        if st.button("Crear"):
            ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0)", (n_c,), commit=True)
            st.rerun()

with tabs[4]: # VENTAS
    st.header("📄 Nueva Venta")
    if not df_stock.empty:
        c_v = st.selectbox("Vender a:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Final"])
        col1, col2 = st.columns([3,1])
        prod = col1.selectbox("Producto", df_stock["accesorio"].unique())
        cant = col2.number_input("Cantidad", 1)
        if st.button("Añadir"):
            match = df_stock[df_stock["accesorio"] == prod]
            if not match.empty:
                st.session_state.carrito.append({"Producto": prod, "Cant": cant, "Precio U.": match["lista1"].values[0], "Subtotal": cant * match["lista1"].values[0]})
                st.rerun()
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        if st.button("Finalizar Venta"):
            total = sum(i['Subtotal'] for i in st.session_state.carrito)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total, c_v), commit=True)
            for i in st.session_state.carrito:
                ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                           (datetime.now().strftime("%d/%m/%Y %H:%M"), c_v, "VENTA", total, "Venta"), commit=True)
            st.session_state.carrito = []
            st.rerun()

with tabs[5]: # HISTORIAL
    st.header("📋 Movimientos")
    st.dataframe(df_movs.iloc[::-1], use_container_width=True)

with tabs[6]: # CIERRE
    st.header("🏁 Caja")
    st.metric("Deuda Total Clientes", formatear_moneda(df_clientes['saldo'].sum()) if not df_clientes.empty else "$ 0")

with tabs[7]: # REMITOS
    st.header("📦 PDF")
    if st.session_state.carrito:
        if st.button("Descargar Remito"):
            pdf = generar_pdf_binario("Cliente", st.session_state.carrito, sum(i['Subtotal'] for i in st.session_state.carrito))
            st.download_button("Bajar PDF", pdf, "remito.pdf", "application/pdf")
