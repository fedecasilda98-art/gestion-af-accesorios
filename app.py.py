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

# --- 2. EL "BLINDAJE" CONTRA EL TYPEERROR ---
def asegurar_flotante(val):
    """Convierte cualquier entrada (texto con $, comas, espacios) en un número real."""
    if pd.isna(val) or str(val).strip() == "": return 0.0
    try:
        # Limpieza profunda: quita $, espacios, y cambia coma por punto
        s = str(val).replace('$', '').replace(' ', '').replace(',', '.').strip()
        return float(s)
    except:
        return 0.0

def init_db():
    ejecutar_query('''CREATE TABLE IF NOT EXISTS articulos 
                 (id INTEGER PRIMARY KEY, rubro TEXT, proveedor TEXT, accesorio TEXT, 
                  stock REAL, costo_base REAL, flete REAL, ganancia REAL, 
                  lista1 REAL, lista2 REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS clientes 
                 (id INTEGER PRIMARY KEY, nombre TEXT, saldo REAL)''', commit=True)
    ejecutar_query('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, tipo TEXT, monto REAL, detalle TEXT)''', commit=True)

init_db()
st.set_page_config(layout="wide", page_title="AF Gestión")

# --- 3. CARGA DE DATOS ---
df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 4. INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

# TAB 1: LOTE (CARGA SEGURA)
with tabs[1]:
    st.header("🚚 Carga por Lote")
    df_temp = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True)
    
    if st.button("🚀 Procesar e Importar"):
        for _, r in ed_lote.iterrows():
            if r['accesorio']:
                # Aquí aplicamos el blindaje a cada valor antes de calcular
                cb = asegurar_flotante(r['costo_base'])
                fl = asegurar_flotante(r['flete'])
                ga = asegurar_flotante(r['ganancia'])
                stk = asegurar_flotante(r['stock'])
                
                # Ahora el cálculo es 100% seguro porque cb, fl y ga son números (0.0 o más)
                l1 = (cb + fl) * (1 + (ga / 100))
                ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                 VALUES (?,?,?,?,?,?,?,?,?)''', 
                               (str(r['rubro']), str(r['proveedor']), str(r['accesorio']), stk, cb, fl, ga, l1, l1*0.9), commit=True)
        st.success("Datos importados con éxito."); st.rerun()

# TAB 2: MAESTRO (BORRAR Y RECALCULAR)
with tabs[2]:
    st.header("⚙️ Editor Maestro")
    if not df_stock.empty:
        df_edit = df_stock.copy(); df_edit.insert(0, "Sel", False)
        res_ed = st.data_editor(df_edit, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Borrar Marcados"):
            for idx in res_ed[res_ed["Sel"] == True]["id"].tolist():
                ejecutar_query("DELETE FROM articulos WHERE id = ?", (idx,), commit=True)
            st.rerun()
        if c2.button("💾 Guardar y Saneamiento Total"):
            df_upd = res_ed.drop(columns=["Sel"])
            for i, row in df_upd.iterrows():
                cb, fl, ga = asegurar_flotante(row["costo_base"]), asegurar_flotante(row["flete"]), asegurar_flotante(row["ganancia"])
                l1 = (cb + fl) * (1 + (ga / 100))
                df_upd.at[i, "lista1"], df_upd.at[i, "lista2"], df_upd.at[i, "costo_base"], df_upd.at[i, "flete"], df_upd.at[i, "ganancia"] = l1, l1*0.9, cb, fl, ga
                df_upd.at[i, "stock"] = asegurar_flotante(row["stock"])
            conn = sqlite3.connect(DB_NAME); df_upd.to_sql("articulos", conn, if_exists="replace", index=False); conn.close()
            st.success("Base de datos saneada."); st.rerun()

# TAB 4: VENTAS
with tabs[4]:
    st.header("📄 Nueva Venta")
    if not df_stock.empty:
        cli = st.selectbox("Cliente:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        c1, c2, c3 = st.columns([3,1,1])
        p_sel = c1.selectbox("Accesorio", df_stock["accesorio"].unique())
        cant = c2.number_input("Cant", 1)
        lista = c3.selectbox("Lista", ["lista1", "lista2"])
        if st.button("🛒 Agregar"):
            match = df_stock[df_stock["accesorio"] == p_sel]
            pu = float(match[lista].values[0])
            st.session_state.carrito.append({"Producto": p_sel, "Cant": cant, "Precio U.": pu, "Subtotal": pu * cant}); st.rerun()
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        if st.button("Finalizar Venta"):
            total = sum(i['Subtotal'] for i in st.session_state.carrito)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total, cli), commit=True)
            for i in st.session_state.carrito:
                ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%y %H:%M"), cli, "VENTA", total, "Venta"), commit=True)
            st.session_state.carrito = []; st.rerun()

# TAB 6: CIERRE
with tabs[6]:
    st.header("🏁 Resumen General")
    c1, c2 = st.columns(2)
    c1.metric("Deuda Clientes", f"$ {df_clientes['saldo'].sum() if not df_clientes.empty else 0:,.2f}")
    c2.metric("Inversión Stock", f"$ {(df_stock['stock'] * df_stock['costo_base']).sum() if not df_stock.empty else 0:,.2f}")

# TAB 7: REMITOS
with tabs[7]:
    st.header("📦 Generar Remito PDF")
    if st.session_state.carrito:
        if st.button("Exportar PDF"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, "AF Accesorios - Remito", ln=True)
            for i in st.session_state.carrito: pdf.cell(0, 10, f"{i['Cant']}x {i['Producto']} - ${i['Subtotal']}", ln=True)
            st.download_button("Bajar PDF", pdf.output(dest='S').encode('latin-1'), "remito.pdf")

# PESTAÑAS RESTANTES (STOCK, CTA CTE, HISTORIAL)
with tabs[0]: st.dataframe(df_stock, use_container_width=True, hide_index=True)
with tabs[3]: 
    st.header("Cuentas Corrientes")
    if not df_clientes.empty:
        s_cli = st.selectbox("Ver Cliente", df_clientes["nombre"].tolist(), key="ver_cli")
        st.write(f"Saldo actual: **$ {df_clientes[df_clientes['nombre'] == s_cli]['saldo'].values[0]:,.2f}**")
    with st.expander("Nuevo Cliente"):
        nc = st.text_input("Nombre")
        if st.button("Crear"): ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (nc,), commit=True); st.rerun()
with tabs[5]: st.dataframe(ejecutar_query("SELECT * FROM movimientos").iloc[::-1], use_container_width=True)
