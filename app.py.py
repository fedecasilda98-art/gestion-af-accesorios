import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from fpdf import FPDF

# --- 1. CONFIGURACIÓN DE BASE DE DATOS ---
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
                  lista1 REAL, lista2 REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS clientes 
                 (id INTEGER PRIMARY KEY, nombre TEXT, saldo REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, tipo TEXT, monto REAL, detalle TEXT)''', commit=True)

# --- 2. MOTOR DE LIMPIEZA (ANTI-ERROR) ---
def clean_num(val):
    """Limpia cualquier basura de Excel antes de calcular."""
    if pd.isna(val) or str(val).strip() == "": return 0.0
    try:
        s = str(val).replace('$', '').replace(' ', '').replace(',', '.').strip()
        return float(s)
    except: return 0.0

init_db()
st.set_page_config(layout="wide", page_title="AF Gestión")
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 3. CARGA DE DATOS ---
df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")

# --- 4. INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

# PESTAÑA STOCK
with tabs[0]:
    st.header("Inventario Actual")
    if not df_stock.empty:
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

# PESTAÑA LOTE (RECONSTRUIDA PARA NO FALLAR)
with tabs[1]:
    st.header("🚚 Carga por Lote")
    st.write("Pegá desde Excel. Los cálculos se procesan al Guardar.")
    df_new = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_new, num_rows="dynamic", use_container_width=True, key="editor_lote")
    
    if st.button("🚀 Guardar e Importar"):
        for _, r in ed_lote.iterrows():
            if r['accesorio'] and str(r['accesorio']).strip() != "":
                s, cb, fl, ga = clean_num(r['stock']), clean_num(r['costo_base']), clean_num(r['flete']), clean_num(r['ganancia'])
                l1 = (cb + fl) * (1 + (ga / 100))
                ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                 VALUES (?,?,?,?,?,?,?,?,?)''', 
                               (str(r['rubro']), str(r['proveedor']), str(r['accesorio']), s, cb, fl, ga, l1, l1*0.9), commit=True)
        st.success("¡Importado!"); st.rerun()

# PESTAÑA MAESTRO
with tabs[2]:
    st.header("⚙️ Maestro")
    if not df_stock.empty:
        df_m = df_stock.copy(); df_m.insert(0, "Borrar", False)
        res_m = st.data_editor(df_m, use_container_width=True, hide_index=True)
        if st.button("🗑️ Eliminar Seleccionados"):
            for idx in res_m[res_m["Borrar"] == True]["id"].tolist():
                ejecutar_query("DELETE FROM articulos WHERE id = ?", (idx,), commit=True)
            st.rerun()
        if st.button("💾 Actualizar y Recalcular"):
            for i, row in res_m.drop(columns=["Borrar"]).iterrows():
                cb, fl, ga = clean_num(row["costo_base"]), clean_num(row["flete"]), clean_num(row["ganancia"])
                l1 = (cb + fl) * (1 + (ga / 100))
                ejecutar_query("UPDATE articulos SET stock=?, costo_base=?, flete=?, ganancia=?, lista1=?, lista2=? WHERE id=?",
                               (clean_num(row["stock"]), cb, fl, ga, l1, l1*0.9, row["id"]), commit=True)
            st.success("Cambios guardados"); st.rerun()

# PESTAÑA CTA CTE
with tabs[3]:
    st.header("Cuentas Corrientes")
    if not df_clientes.empty:
        c_sel = st.selectbox("Cliente", df_clientes["nombre"].tolist())
        saldo = df_clientes[df_clientes["nombre"] == c_sel]["saldo"].values[0]
        st.metric("Saldo", f"$ {saldo:,.2f}")
        pago = st.number_input("Pago $", 0.0)
        if st.button("Registrar Pago"):
            ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (pago, c_sel), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                           (datetime.now().strftime("%d/%m/%y %H:%M"), c_sel, "PAGO", pago, "Pago recibido"), commit=True)
            st.rerun()
    with st.expander("Nuevo Cliente"):
        nc = st.text_input("Nombre")
        if st.button("Crear"): ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (nc,), commit=True); st.rerun()

# PESTAÑA VENTAS
with tabs[4]:
    st.header("Nueva Venta")
    if not df_stock.empty:
        cli = st.selectbox("Cliente:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Final"])
        col1, col2, col3 = st.columns([3,1,1])
        prod = col1.selectbox("Accesorio", df_stock["accesorio"].unique())
        cant = col2.number_input("Cant", 1)
        lst = col3.selectbox("Lista", ["lista1", "lista2"])
        if st.button("🛒 Sumar"):
            pu = float(df_stock[df_stock["accesorio"] == prod][lst].values[0])
            st.session_state.carrito.append({"Producto": prod, "Cant": cant, "PU": pu, "Subtotal": pu*cant}); st.rerun()
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        if st.button("✅ Confirmar Venta"):
            tot = sum(i['Subtotal'] for i in st.session_state.carrito)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (tot, cli), commit=True)
            for i in st.session_state.carrito:
                ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%y %H:%M"), cli, "VENTA", tot, "Venta"), commit=True)
            st.session_state.carrito = []; st.rerun()

# PESTAÑA HISTORIAL
with tabs[5]:
    st.header("Movimientos")
    st.dataframe(ejecutar_query("SELECT * FROM movimientos").iloc[::-1], use_container_width=True)

# PESTAÑA CIERRE
with tabs[6]:
    st.header("Balance")
    c1, c2 = st.columns(2)
    c1.metric("Deuda Clientes", f"$ {df_clientes['saldo'].sum() if not df_clientes.empty else 0:,.2f}")
    c2.metric("Inversión Stock", f"$ {(df_stock['stock'] * df_stock['costo_base']).sum() if not df_stock.empty else 0:,.2f}")

# PESTAÑA REMITOS
with tabs[7]:
    st.header("Remitos PDF")
    if st.session_state.carrito:
        if st.button("Bajar PDF"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "AF REMITO", ln=True)
            for i in st.session_state.carrito: pdf.cell(0, 10, f"{i['Cant']} x {i['Producto']} - ${i['Subtotal']}", ln=True)
            st.download_button("Descargar", pdf.output(dest='S').encode('latin-1'), "remito.pdf")
