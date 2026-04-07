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
                 (id PRIMARY KEY, rubro TEXT, proveedor TEXT, accesorio TEXT, 
                  stock REAL, costo_base REAL, flete REAL, ganancia REAL, 
                  lista1 REAL, lista2 REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS clientes 
                 (id INTEGER PRIMARY KEY, nombre TEXT, saldo REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, tipo TEXT, 
                  monto REAL, detalle TEXT)''', commit=True)

init_db()

# --- 2. EL FILTRO DE SEGURIDAD ---
def limpiar_valor(val):
    """Convierte cualquier texto sucio de Excel a un número limpio."""
    if pd.isna(val) or str(val).strip() == "": return 0.0
    try:
        s = str(val).replace('$', '').replace(' ', '').replace(',', '.').strip()
        return float(s)
    except: return 0.0

# --- 3. CONFIGURACIÓN ---
st.set_page_config(layout="wide", page_title="AF Gestión Accesorios")
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 4. TABS ---
t = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

# TAB 1: LOTE (CARGA DESDE EXCEL SIN ERRORES)
with t[1]:
    st.header("🚚 Carga por Lote")
    st.info("Pegá tus columnas de Excel acá. El sistema limpiará los signos $ y comas al procesar.")
    df_lote = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_lote, num_rows="dynamic", use_container_width=True, key="editor_lote")
    
    if st.button("🚀 Procesar e Importar"):
        for _, r in ed_lote.iterrows():
            if r['accesorio'] and str(r['accesorio']).strip() != "":
                stk, cb, fl, ga = limpiar_valor(r['stock']), limpiar_valor(r['costo_base']), limpiar_valor(r['flete']), limpiar_valor(r['ganancia'])
                l1 = (cb + fl) * (1 + (ga / 100))
                ejecutar_query("INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) VALUES (?,?,?,?,?,?,?,?,?)",
                               (str(r['rubro']), str(r['proveedor']), str(r['accesorio']), stk, cb, fl, ga, l1, l1*0.9), commit=True)
        st.success("Artículos cargados."); st.rerun()

# TAB 2: MAESTRO (EDICIÓN Y ELIMINACIÓN)
with t[2]:
    st.header("⚙️ Maestro de Artículos")
    df_m = ejecutar_query("SELECT * FROM articulos")
    if not df_m.empty:
        df_m.insert(0, "Sel", False)
        res_m = st.data_editor(df_m, use_container_width=True, hide_index=True, key="editor_maestro")
        
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Eliminar Marcados"):
            for idx in res_m[res_m["Sel"] == True]["id"].tolist():
                ejecutar_query("DELETE FROM articulos WHERE id = ?", (idx,), commit=True)
            st.rerun()
        if c2.button("💾 Guardar y Recalcular Precios"):
            df_upd = res_m.drop(columns=["Sel"])
            for i, row in df_upd.iterrows():
                cb, fl, ga = limpiar_valor(row["costo_base"]), limpiar_valor(row["flete"]), limpiar_valor(row["ganancia"])
                l1 = (cb + fl) * (1 + (ga / 100))
                df_upd.at[i, "lista1"], df_upd.at[i, "lista2"], df_upd.at[i, "costo_base"], df_upd.at[i, "flete"], df_upd.at[i, "ganancia"] = l1, l1*0.9, cb, fl, ga
            conn = sqlite3.connect(DB_NAME); df_upd.to_sql("articulos", conn, if_exists="replace", index=False); conn.close()
            st.success("Datos actualizados."); st.rerun()

# TAB 4: VENTAS
with t[4]:
    st.header("📄 Ventas")
    df_s = ejecutar_query("SELECT * FROM articulos")
    df_c = ejecutar_query("SELECT * FROM clientes")
    if not df_s.empty:
        cli = st.selectbox("Cliente:", df_c["nombre"].tolist() if not df_c.empty else ["Consumidor Final"])
        col1, col2, col3 = st.columns([3,1,1])
        prod = col1.selectbox("Accesorio", df_s["accesorio"].unique())
        cant = col2.number_input("Cant", 1)
        lista = col3.selectbox("Lista", ["lista1", "lista2"])
        if st.button("🛒 Añadir"):
            p_u = float(df_s[df_s["accesorio"] == prod][lista].values[0])
            st.session_state.carrito.append({"Producto": prod, "Cant": cant, "Precio U.": p_u, "Subtotal": p_u * cant})
            st.rerun()
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        if st.button("Finalizar"):
            total = sum(i['Subtotal'] for i in st.session_state.carrito)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total, cli), commit=True)
            for i in st.session_state.carrito:
                ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%y %H:%M"), cli, "VENTA", total, "Venta"), commit=True)
            st.session_state.carrito = []; st.rerun()

# TAB 6: CIERRE
with t[6]:
    st.header("🏁 Cierre de Caja")
    df_s = ejecutar_query("SELECT * FROM articulos")
    df_c = ejecutar_query("SELECT * FROM clientes")
    c1, c2 = st.columns(2)
    c1.metric("Deuda Clientes", f"$ {df_c['saldo'].sum() if not df_c.empty else 0:,.2f}")
    c2.metric("Inversión Stock", f"$ {(df_s['stock'] * df_s['costo_base']).sum() if not df_s.empty else 0:,.2f}")

# TAB 7: REMITOS
with t[7]:
    st.header("📦 Remitos")
    if st.session_state.carrito:
        if st.button("Generar PDF"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "AF ACCESORIOS - REMITO", ln=True)
            for i in st.session_state.carrito: pdf.cell(0, 10, f"{i['Cant']}x {i['Producto']} - ${i['Subtotal']}", ln=True)
            st.download_button("Descargar", pdf.output(dest='S').encode('latin-1'), "remito.pdf")

# RESTO
with t[0]: st.dataframe(ejecutar_query("SELECT * FROM articulos"), use_container_width=True, hide_index=True)
with t[3]: # CTA CTE
    st.header("Cuentas Corrientes")
    if not df_c.empty:
        s_cli = st.selectbox("Seleccionar Cliente", df_c["nombre"].tolist(), key="c_sel")
        st.write(f"Saldo: **$ {df_c[df_c['nombre'] == s_cli]['saldo'].values[0]:,.2f}**")
        pago = st.number_input("Pago $", 0.0)
        if st.button("Cobrar"):
            ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (pago, s_cli), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%y %H:%M"), s_cli, "PAGO", pago, "Cobro"), commit=True)
            st.rerun()
    with st.expander("Nuevo Cliente"):
        nc = st.text_input("Nombre")
        if st.button("Crear"): ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (nc,), commit=True); st.rerun()
with t[5]: st.dataframe(ejecutar_query("SELECT * FROM movimientos").iloc[::-1], use_container_width=True)
