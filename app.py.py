import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from fpdf import FPDF
from io import BytesIO

# --- 1. CONFIGURACIÓN DE BASE DE DATOS (PROTEGIDA) ---
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

# --- 2. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="AF Accesorios - Sistema Integral", layout="wide")

def formatear_moneda(valor):
    try:
        return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
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
        txt = f"{item['Cant']}x {item['Producto']} - P.U: {formatear_moneda(item['Precio U.'])} - Sub: {formatear_moneda(item['Subtotal'])}"
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

# --- 4. INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

# TAB 0: STOCK
with tabs[0]:
    st.header("Inventario Real-Time")
    if not df_stock.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Costo Stock", formatear_moneda((df_stock['costo_base'] * df_stock['stock']).sum()))
        c2.metric("Total L1", formatear_moneda((df_stock['lista1'] * df_stock['stock']).sum()))
        c3.metric("Total L2", formatear_moneda((df_stock['lista2'] * df_stock['stock']).sum()))
        st.dataframe(df_stock, use_container_width=True, hide_index=True)
    else: st.info("Sin artículos.")

# TAB 1: LOTE (REINSERTADO Y MEJORADO)
with tabs[1]:
    st.header("🚚 Carga por Lote")
    st.write("Pegá aquí tus artículos. Se limpian símbolos ($) y espacios automáticamente.")
    df_lote = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_lote, num_rows="dynamic", use_container_width=True)
    
    if st.button("Procesar Lote"):
        for _, row in ed_lote.iterrows():
            if row['accesorio'] and str(row['accesorio']).strip() != "":
                try:
                    def limpiar(v):
                        if pd.isna(v) or str(v).strip() == "": return 0.0
                        return float(str(v).replace('$', '').replace(',', '.').strip())
                    
                    s, cb, fl, ga = limpiar(row['stock']), limpiar(row['costo_base']), limpiar(row['flete']), limpiar(row['ganancia'])
                    l1 = (cb + fl) * (1 + ga/100)
                    ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                     VALUES (?,?,?,?,?,?,?,?,?)''', 
                                   (str(row['rubro']), str(row['proveedor']), str(row['accesorio']), s, cb, fl, ga, l1, l1*0.9), commit=True)
                except: continue
        st.success("Lote cargado")
        st.rerun()

# TAB 2: MAESTRO (EDITOR DIRECTO)
with tabs[2]:
    st.header("⚙️ Editor Maestro")
    df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
    if st.button("Guardar Cambios Maestro"):
        conn = sqlite3.connect(DB_NAME)
        df_ed.to_sql("articulos", conn, if_exists="replace", index=False)
        conn.close()
        st.success("Base actualizada")
        st.rerun()

# TAB 3: CTA CTE (COMPLETO CON PAGOS)
with tabs[3]:
    st.header("👥 Gestión de Cuentas Corrientes")
    if not df_clientes.empty:
        cli_sel = st.selectbox("Seleccionar Cliente:", df_clientes["nombre"].tolist())
        datos_cli = df_clientes[df_clientes["nombre"] == cli_sel].iloc[0]
        st.metric("Saldo Pendiente", formatear_moneda(datos_cli["saldo"]))
        
        col_h, col_p = st.columns([2, 1])
        with col_h:
            st.subheader("Historial")
            st.dataframe(df_movs[df_movs["cliente"] == cli_sel].iloc[::-1], use_container_width=True)
        with col_p:
            st.subheader("Cobrar")
            monto_p = st.number_input("Monto $:", min_value=0.0)
            if st.button("Registrar Pago"):
                ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (monto_p, cli_sel), commit=True)
                ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y %H:%M"), cli_sel, "PAGO", monto_p, "Pago recibido"), commit=True)
                st.rerun()
    with st.expander("Nuevo Cliente"):
        n_n = st.text_input("Nombre Completo")
        if st.button("Crear Cliente"):
            ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (n_n,), commit=True)
            st.rerun()

# TAB 4: VENTAS / PRESUPUESTOS (CON CARRITO)
with tabs[4]:
    st.header("📄 Ventas")
    cli_v = st.selectbox("Cliente:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Final"])
    c1, c2, c3 = st.columns([2,1,1])
    art_v = c1.selectbox("Producto", df_stock["accesorio"].tolist() if not df_stock.empty else [])
    cant_v = c2.number_input("Cant", 1)
    lst_v = c3.selectbox("Lista", ["lista1", "lista2"])
    
    if st.button("Agregar Item"):
        match = df_stock[df_stock["accesorio"] == art_v]
        if not match.empty:
            p_u = float(match[lst_v].values[0])
            st.session_state.carrito.append({"Producto": art_v, "Cant": cant_v, "Precio U.": p_u, "Subtotal": p_u * cant_v})
            st.rerun()

    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        total_v = sum(i["Subtotal"] for i in st.session_state.carrito)
        st.subheader(f"Total: {formatear_moneda(total_v)}")
        if st.button("Confirmar Venta (Afecta Stock y Saldo)"):
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total_v, cli_v), commit=True)
            for i in st.session_state.carrito:
                ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i["Cant"], i["Producto"]), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                           (datetime.now().strftime("%d/%m/%Y %H:%M"), cli_v, "VENTA", total_v, "Venta Accesorios"), commit=True)
            st.session_state.carrito = []
            st.success("Venta Grabada")
            st.rerun()

# TAB 5: HISTORIAL GLOBAL
with tabs[5]:
    st.header("📋 Movimientos")
    st.dataframe(df_movs.iloc[::-1], use_container_width=True)

# TAB 6: CIERRE
with tabs[6]:
    st.header("🏁 Resumen General")
    st.metric("Deuda Total de Clientes", formatear_moneda(df_clientes["saldo"].sum()) if not df_clientes.empty else "$ 0")
    st.metric("Valor Stock (Costo)", formatear_moneda((df_stock["stock"] * df_stock["costo_base"]).sum()) if not df_stock.empty else "$ 0")

# TAB 7: REMITOS (PDF)
with tabs[7]:
    st.header("📦 Generar Remito")
    if st.session_state.carrito:
        cli_r = st.selectbox("Cliente Remito:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        if st.button("Generar PDF"):
            total_r = sum(i["Subtotal"] for i in st.session_state.carrito)
            pdf_bytes = generar_pdf_binario(cli_r, st.session_state.carrito, total_r, "REMITO")
            st.download_button("Descargar Remito PDF", pdf_bytes, f"Remito_{cli_r}.pdf", "application/pdf")
    else: st.info("El carrito está vacío. Cargá items en 'Ventas' primero.")
