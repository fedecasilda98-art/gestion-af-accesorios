import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from fpdf import FPDF

# --- 1. BASE DE DATOS ---
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
        st.error(f"Error de DB: {e}")
    finally:
        conn.close()

def init_db():
    ejecutar_query('''CREATE TABLE IF NOT EXISTS articulos 
                 (id INTEGER PRIMARY KEY, rubro TEXT, proveedor TEXT, accesorio TEXT, 
                  stock REAL, costo_base REAL, flete REAL, ganancia REAL, 
                  lista1 REAL, lista2 REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS clientes 
                 (id INTEGER PRIMARY KEY, nombre TEXT, saldo REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, tipo TEXT, 
                  monto REAL, detalle TEXT)''', commit=True)

init_db()

# --- 2. MOTOR DE SEGURIDAD (EL ESCUDO) ---
def forzar_num(val):
    if pd.isna(val) or str(val).strip() == "": return 0.0
    try:
        s = str(val).replace('$', '').replace(' ', '').replace(',', '.').strip()
        return float(s)
    except: return 0.0

def moneda(v):
    return f"$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- 3. CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="AF Accesorios")
if "carrito" not in st.session_state: st.session_state.carrito = []

df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")

# --- 4. INTERFAZ ---
t = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

# TAB 0: STOCK
with t[0]:
    st.header("Inventario Real")
    if not df_stock.empty:
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

# TAB 1: LOTE (CARGA DESDE EXCEL)
with t[1]:
    st.header("🚚 Carga Masiva")
    df_temp = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True)
    if st.button("🚀 Importar Lote"):
        for _, r in ed_lote.iterrows():
            if r['accesorio']:
                cb, fl, ga, stk = forzar_num(r['costo_base']), forzar_num(r['flete']), forzar_num(r['ganancia']), forzar_num(r['stock'])
                l1 = (cb + fl) * (1 + ga/100)
                ejecutar_query("INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) VALUES (?,?,?,?,?,?,?,?,?)",
                               (str(r['rubro']), str(r['proveedor']), str(r['accesorio']), stk, cb, fl, ga, l1, l1*0.9), commit=True)
        st.success("Importación terminada."); st.rerun()

# TAB 2: MAESTRO (BORRAR Y EDITAR)
with t[2]:
    st.header("⚙️ Maestro de Artículos")
    if not df_stock.empty:
        df_m = df_stock.copy(); df_m.insert(0, "Sel", False)
        res_m = st.data_editor(df_m, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Eliminar Seleccionados"):
            for idx in res_m[res_m["Sel"] == True]["id"].tolist():
                ejecutar_query("DELETE FROM articulos WHERE id = ?", (idx,), commit=True)
            st.rerun()
        if c2.button("💾 Guardar y Recalcular Precios"):
            df_upd = res_m.drop(columns=["Sel"])
            for i, row in df_upd.iterrows():
                cb, fl, ga = forzar_num(row["costo_base"]), forzar_num(row["flete"]), forzar_num(row["ganancia"])
                l1 = (cb + fl) * (1 + ga/100)
                df_upd.at[i, "lista1"], df_upd.at[i, "lista2"], df_upd.at[i, "costo_base"], df_upd.at[i, "flete"], df_upd.at[i, "ganancia"] = l1, l1*0.9, cb, fl, ga
            conn = sqlite3.connect(DB_NAME); df_upd.to_sql("articulos", conn, if_exists="replace", index=False); conn.close()
            st.success("Base de datos limpia."); st.rerun()

# TAB 3: CTA CTE (PAGOS Y SALDOS)
with t[3]:
    st.header("👥 Clientes y Deudas")
    if not df_clientes.empty:
        c_sel = st.selectbox("Cliente:", df_clientes["nombre"].tolist())
        saldo = df_clientes[df_clientes["nombre"] == c_sel]["saldo"].values[0]
        st.metric("Saldo Pendiente", moneda(saldo))
        m_pago = st.number_input("Registrar Pago $", 0.0)
        if st.button("Cobrar"):
            ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (m_pago, c_sel), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%y %H:%M"), c_sel, "PAGO", m_pago, "Pago en efectivo/transf"), commit=True)
            st.rerun()
    with st.expander("Crear Nuevo Cliente"):
        n_c = st.text_input("Nombre del Cliente")
        if st.button("Registrar Cliente"):
            ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (n_c,), commit=True); st.rerun()

# TAB 4: VENTAS (CON CARRITO)
with t[4]:
    st.header("📄 Nueva Venta")
    if not df_stock.empty:
        c_v = st.selectbox("Vender a:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Final"])
        col1, col2, col3 = st.columns([3,1,1])
        prod = col1.selectbox("Accesorio", df_stock["accesorio"].unique())
        cant = col2.number_input("Cant", 1)
        list_p = col3.selectbox("Lista", ["lista1", "lista2"])
        if st.button("🛒 Agregar al Carrito"):
            match = df_stock[df_stock["accesorio"] == prod]
            p_u = float(match[list_p].values[0])
            st.session_state.carrito.append({"Producto": prod, "Cant": cant, "Precio U.": p_u, "Subtotal": p_u * cant})
            st.rerun()
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        if st.button("✅ Confirmar Venta"):
            total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total_v, c_v), commit=True)
            for i in st.session_state.carrito:
                ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%y %H:%M"), c_v, "VENTA", total_v, "Venta de accesorios"), commit=True)
            st.session_state.carrito = []; st.success("Venta procesada."); st.rerun()
        if st.button("🗑️ Vaciar Carrito"): st.session_state.carrito = []; st.rerun()

# TAB 5: HISTORIAL
with t[5]:
    st.header("📋 Historial de Movimientos")
    df_h = ejecutar_query("SELECT * FROM movimientos")
    st.dataframe(df_h.iloc[::-1], use_container_width=True)

# TAB 6: CIERRE
with t[6]:
    st.header("🏁 Resumen de Gestión")
    c_a, c_b = st.columns(2)
    c_a.metric("Total a Cobrar (Clientes)", moneda(df_clientes["saldo"].sum() if not df_clientes.empty else 0))
    c_b.metric("Valor del Stock (Costo)", moneda((df_stock["stock"] * df_stock["costo_base"]).sum() if not df_stock.empty else 0))

# TAB 7: REMITOS (PDF)
with t[7]:
    st.header("📦 Generar Remito PDF")
    if st.session_state.carrito:
        if st.button("Descargar Remito"):
            pdf = FPDF()
            pdf.add_page(); pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "AF ACCESORIOS - REMITO", ln=True, align="C")
            pdf.set_font("Arial", "", 12); pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
            for item in st.session_state.carrito:
                pdf.cell(0, 10, f"{item['Cant']}x {item['Producto']} --- {moneda(item['Subtotal'])}", ln=True)
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            st.download_button("Click aquí para descargar", pdf_bytes, "remito.pdf", "application/pdf")
    else: st.info("El carrito está vacío. Cargá una venta para generar el remito.")
