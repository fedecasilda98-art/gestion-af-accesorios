import streamlit as st
import pandas as pd
import sqlite3
import os
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
                 (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, tipo TEXT, 
                  monto REAL, detalle TEXT)''', commit=True)

init_db()

# --- 2. MOTOR DE SEGURIDAD (LIMPIEZA DE DATOS) ---
def safe_num(val):
    if pd.isna(val) or str(val).strip() == "": return 0.0
    try:
        s = str(val).replace('$', '').replace(' ', '').replace(',', '.').strip()
        return float(s)
    except: return 0.0

def moneda(v):
    return f"$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- 3. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="AF Gestión")
if "carrito" not in st.session_state: st.session_state.carrito = []

df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")

# --- 4. INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

# TAB 0: STOCK ACTUAL
with tabs[0]:
    st.header("Inventario de Productos")
    if not df_stock.empty:
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

# TAB 1: LOTE (CARGA MASIVA SEGURA)
with tabs[1]:
    st.header("🚚 Carga por Lote")
    st.info("Pegá tus datos aquí. El cálculo se realizará al presionar el botón.")
    df_temp = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True, key="lote_full")
    
    if st.button("🚀 Procesar e Importar"):
        for _, r in ed_lote.iterrows():
            if r['accesorio']:
                stk, cb, fl, ga = safe_num(r['stock']), safe_num(r['costo_base']), safe_num(r['flete']), safe_num(r['ganancia'])
                l1 = (cb + fl) * (1 + (ga / 100))
                ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                 VALUES (?,?,?,?,?,?,?,?,?)''', 
                               (str(r['rubro']), str(r['proveedor']), str(r['accesorio']), stk, cb, fl, ga, l1, l1*0.9), commit=True)
        st.success("Importación exitosa."); st.rerun()

# TAB 2: MAESTRO (EDICIÓN Y ELIMINACIÓN)
with tabs[2]:
    st.header("⚙️ Editor Maestro")
    if not df_stock.empty:
        df_m = df_stock.copy(); df_m.insert(0, "Sel", False)
        res_m = st.data_editor(df_m, use_container_width=True, hide_index=True, key="maestro_full")
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Eliminar Marcados"):
            for idx in res_m[res_m["Sel"] == True]["id"].tolist():
                ejecutar_query("DELETE FROM articulos WHERE id = ?", (idx,), commit=True)
            st.rerun()
        if c2.button("💾 Guardar y Recalcular"):
            df_upd = res_m.drop(columns=["Sel"])
            for i, row in df_upd.iterrows():
                cb, fl, ga = safe_num(row["costo_base"]), safe_num(row["flete"]), safe_num(row["ganancia"])
                l1 = (cb + fl) * (1 + (ga / 100))
                df_upd.at[i, "lista1"], df_upd.at[i, "lista2"], df_upd.at[i, "costo_base"], df_upd.at[i, "flete"], df_upd.at[i, "ganancia"] = l1, l1*0.9, cb, fl, ga
                df_upd.at[i, "stock"] = safe_num(row["stock"])
            conn = sqlite3.connect(DB_NAME); df_upd.to_sql("articulos", conn, if_exists="replace", index=False); conn.close()
            st.success("Base de datos actualizada."); st.rerun()

# TAB 3: CTA CTE
with tabs[3]:
    st.header("👥 Gestión de Clientes")
    if not df_clientes.empty:
        sel_c = st.selectbox("Cliente:", df_clientes["nombre"].tolist())
        datos_c = df_clientes[df_clientes["nombre"] == sel_c].iloc[0]
        st.metric("Saldo Pendiente", moneda(datos_c["saldo"]))
        pago = st.number_input("Registrar Entrega de Dinero $", 0.0)
        if st.button("Confirmar Cobro"):
            ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (pago, sel_c), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                           (datetime.now().strftime("%d/%m/%y %H:%M"), sel_c, "PAGO", pago, "Entrega de efectivo"), commit=True)
            st.success("Pago registrado."); st.rerun()
    with st.expander("Dar de alta nuevo cliente"):
        new_c = st.text_input("Nombre Completo")
        if st.button("Crear"):
            ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (new_c,), commit=True); st.rerun()

# TAB 4: VENTAS (CARRITO)
with tabs[4]:
    st.header("📄 Nueva Venta")
    if not df_stock.empty:
        cli_v = st.selectbox("Seleccionar Cliente:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        col1, col2, col3 = st.columns([3,1,1])
        prod_v = col1.selectbox("Accesorio", df_stock["accesorio"].unique())
        cant_v = col2.number_input("Cantidad", 1)
        list_v = col3.selectbox("Lista", ["lista1", "lista2"])
        if st.button("🛒 Agregar"):
            match = df_stock[df_stock["accesorio"] == prod_v]
            pu = float(match[list_v].values[0])
            st.session_state.carrito.append({"Producto": prod_v, "Cant": cant_v, "Precio U.": pu, "Subtotal": pu * cant_v})
            st.rerun()
    
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        if st.button("✅ Finalizar Venta"):
            total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total_v, cli_v), commit=True)
            for i in st.session_state.carrito:
                ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", 
                           (datetime.now().strftime("%d/%m/%y %H:%M"), cli_v, "VENTA", total_v, "Venta de productos"), commit=True)
            st.session_state.carrito = []; st.success("Venta completada."); st.rerun()
        if st.button("🗑️ Vaciar Carrito"): st.session_state.carrito = []; st.rerun()

# TAB 5: HISTORIAL
with tabs[5]:
    st.header("📋 Historial de Movimientos")
    df_h = ejecutar_query("SELECT * FROM movimientos")
    if not df_h.empty:
        st.dataframe(df_h.iloc[::-1], use_container_width=True)

# TAB 6: CIERRE
with tabs[6]:
    st.header("🏁 Balance General")
    c_a, c_b = st.columns(2)
    c_a.metric("Total deudas de clientes", moneda(df_clientes["saldo"].sum() if not df_clientes.empty else 0))
    c_b.metric("Inversión estimada en stock", moneda((df_stock["stock"] * df_stock["costo_base"]).sum() if not df_stock.empty else 0))

# TAB 7: REMITOS (PDF)
with tabs[7]:
    st.header("📦 Generación de Remitos")
    if st.session_state.carrito:
        if st.button("Generar PDF"):
            pdf = FPDF()
            pdf.add_page(); pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "AF ACCESORIOS - REMITO", ln=True, align="C")
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
            pdf.ln(5)
            for i in st.session_state.carrito:
                pdf.cell(0, 10, f"{i['Cant']} x {i['Producto']} - {moneda(i['Subtotal'])}", ln=True)
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            st.download_button("Descargar Remito", pdf_bytes, "remito.pdf")
    else:
        st.info("Cargá una venta en la pestaña anterior para generar el remito.")
