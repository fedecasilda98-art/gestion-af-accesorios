import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
import re
from fpdf import FPDF
from io import BytesIO

# --- 1. CONFIGURACIÓN DE BASE DE DATOS (PROTEGIDA) ---
# Intentamos usar el volumen de Railway, si falla usamos la raíz
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
        st.error(f"Error de base de datos: {e}")
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
st.set_page_config(page_title="AF Accesorios - Gestión Nube", layout="wide")

# Carga de datos desde SQL (Se recargan al inicio de cada interacción)
df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")
df_movs = ejecutar_query("SELECT * FROM movimientos")

# Session States
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 3. UTILIDADES ---
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
        texto_item = f"{item['Cant']}x {item['Producto']} - P.U: {formatear_moneda(item['Precio U.'])} - Sub: {formatear_moneda(item['Subtotal'])}"
        pdf.cell(0, 8, texto_item, ln=True, border=1)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"TOTAL: {formatear_moneda(total)}", align="R")
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ ---
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
    else:
        st.info("No hay artículos en stock.")

# TAB 1: LOTE (BLINDADO CONTRA TYPEERROR)
with tabs[1]:
    st.header("🚚 Carga por Lote")
    st.write("Pegá desde Excel. El sistema limpiará errores de formato automáticamente.")
    df_lote = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_lote, num_rows="dynamic", use_container_width=True)
    
    if st.button("Procesar Lote"):
        for _, row in ed_lote.iterrows():
            if row['accesorio'] and str(row['accesorio']).strip() != "":
                try:
                    # Forzamos conversión a número para evitar el TypeError de las fotos
                    s_val = float(row['stock']) if pd.notnull(row['stock']) else 0.0
                    c_val = float(row['costo_base']) if pd.notnull(row['costo_base']) else 0.0
                    f_val = float(row['flete']) if pd.notnull(row['flete']) else 0.0
                    g_val = float(row['ganancia']) if pd.notnull(row['ganancia']) else 0.0
                    
                    l1 = (c_val + f_val) * (1 + g_val/100)
                    l2 = l1 * 0.90
                    
                    ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                     VALUES (?,?,?,?,?,?,?,?,?)''', 
                                   (str(row['rubro']), str(row['proveedor']), str(row['accesorio']), s_val, c_val, f_val, g_val, l1, l2), commit=True)
                except Exception as e:
                    st.error(f"Error en: {row['accesorio']}. Asegurate que costos y stock sean números.")
        st.success("Lote procesado correctamente")
        st.rerun()

# TAB 2: MAESTRO
with tabs[2]:
    st.header("⚙️ Editor Maestro")
    if not df_stock.empty:
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios Maestro"):
            df_ed["lista1"] = (df_ed["costo_base"] + df_ed["flete"]) * (1 + df_ed["ganancia"] / 100)
            df_ed["lista2"] = df_ed["lista1"] * 0.90
            conn = sqlite3.connect(DB_NAME)
            df_ed.to_sql("articulos", conn, if_exists="replace", index=False)
            conn.close()
            st.success("Base actualizada")
            st.rerun()

# TAB 3: CTA CTE (COMPLETO)
with tabs[3]:
    st.header("👥 Gestión de Cuentas Corrientes")
    if not df_clientes.empty:
        cli_sel = st.selectbox("🔍 Seleccionar Cliente:", df_clientes["nombre"].tolist())
        datos_cli = df_clientes[df_clientes["nombre"] == cli_sel].iloc[0]
        
        c_info1, c_info2 = st.columns(2)
        c_info1.metric("Saldo Pendiente", formatear_moneda(datos_cli["saldo"]))
        c_info2.write(f"📞 {datos_cli['tel']} | 📍 {datos_cli['localidad']}")
        
        st.divider()
        col_movs, col_ops = st.columns([2, 1])
        with col_movs:
            st.subheader("📜 Historial")
            hist = df_movs[df_movs["cliente"] == cli_sel].iloc[::-1]
            st.dataframe(hist[["fecha", "tipo", "monto", "detalle"]], use_container_width=True, hide_index=True)
        with col_ops:
            st.subheader("💰 Registrar Pago")
            monto_p = st.number_input("Monto $:", min_value=0.0)
            met_p = st.selectbox("Método:", ["Efectivo", "Transferencia", "Cheque"])
            if st.button("Confirmar Pago", type="primary"):
                ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (monto_p, cli_sel), commit=True)
                ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, metodo, detalle) VALUES (?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y %H:%M"), cli_sel, "PAGO", monto_p, met_p, f"Cobro en {met_p}"), commit=True)
                st.rerun()

    st.divider()
    with st.expander("➕ Nuevo Cliente"):
        n_n = st.text_input("Nombre")
        if st.button("Guardar Cliente"):
            ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (n_n,), commit=True)
            st.rerun()

# TAB 4: PRESUPUESTADOR (BLINDADO CONTRA INDEXERROR)
with tabs[4]:
    st.header("📄 Presupuestos y Ventas")
    if not df_stock.empty:
        cli_v = st.selectbox("Cliente para Venta:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Final"])
        col1, col2, col3 = st.columns([2,1,1])
        art_v = col1.selectbox("Producto", df_stock["accesorio"].tolist())
        cant_v = col2.number_input("Cant", 1)
        lst_v = col3.selectbox("Lista", ["lista1", "lista2"])
        
        if st.button("Agregar Item"):
            # Verificamos de forma segura que el artículo exista en df_stock
            match = df_stock[df_stock["accesorio"] == art_v]
            if not match.empty:
                p_u = float(match[lst_v].values[0])
                st.session_state.carrito.append({
                    "Producto": art_v, "Cant": cant_v, "Precio U.": p_u, "Subtotal": p_u * cant_v
                })
                st.rerun()
            else:
                st.error("Error al buscar el producto.")

        if st.session_state.carrito:
            st.table(st.session_state.carrito)
            total_v = sum(i["Subtotal"] for i in st.session_state.carrito)
            st.subheader(f"Total: {formatear_moneda(total_v)}")
            if st.button("Confirmar Venta"):
                ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total_v, cli_v), commit=True)
                for item in st.session_state.carrito:
                    ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (item["Cant"], item["Producto"]), commit=True)
                ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y %H:%M"), cli_v, "VENTA", total_v, "Venta de accesorios"), commit=True)
                st.session_state.carrito = []
                st.success("Venta Grabada")
                st.rerun()
            if st.button("Vaciar Carrito"):
                st.session_state.carrito = []
                st.rerun()
    else:
        st.warning("Cargá productos en la pestaña 'Lote' para poder vender.")

# TAB 5: HISTORIAL
with tabs[5]:
    st.header("📋 Historial Global")
    st.dataframe(df_movs.iloc[::-1], use_container_width=True, hide_index=True)

# TAB 6: CIERRE
with tabs[6]:
    st.header("🏁 Resumen")
    st.metric("Deuda Clientes", formatear_moneda(df_clientes["saldo"].sum()) if not df_clientes.empty else "$ 0,00")
    st.metric("Inversión Stock", formatear_moneda((df_stock["stock"] * df_stock["costo_base"]).sum()) if not df_stock.empty else "$ 0,00")

# TAB 7: REMITOS
with tabs[7]:
    st.header("📦 Generar Remito PDF")
    if st.session_state.carrito:
        cli_r = st.selectbox("Para el cliente:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        if st.button("Generar PDF"):
            total_r = sum(i["Subtotal"] for i in st.session_state.carrito)
            pdf_bytes = generar_pdf_binario(cli_r, st.session_state.carrito, total_r, "REMITO")
            st.download_button("Descargar Remito", pdf_bytes, f"Remito_{cli_r}.pdf", "application/pdf")
    else:
        st.info("El carrito está vacío. Agregá productos en 'Presupuestos' primero.")
