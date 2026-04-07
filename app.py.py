import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURACIÓN DE BASE DE DATOS ---
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

# --- BLINDAJE ANTI-ERROR (LIMPIEZA DE EXCEL) ---
def limpiar_num(val):
    """Convierte cualquier texto o número sucio a un flotante puro."""
    if pd.isna(val) or str(val).strip() == "": return 0.0
    try:
        # Quitamos $, espacios, y normalizamos comas/puntos
        s = str(val).replace('$', '').replace(' ', '').replace(',', '.').strip()
        return float(s)
    except: return 0.0

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
st.set_page_config(layout="wide", page_title="AF Gestión Accesorios")

# --- CARGA INICIAL ---
if "carrito" not in st.session_state: st.session_state.carrito = []
df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")

# --- INTERFAZ ---
t = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

# PESTAÑA LOTE: CARGA MASIVA SIN ERRORES
with t[1]:
    st.header("🚚 Carga por Lote")
    st.write("Pegá los datos de Excel. El sistema limpiará los signos $ automáticamente.")
    df_vacio = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_vacio, num_rows="dynamic", use_container_width=True, key="ed_lote_final")
    
    if st.button("🚀 Procesar e Importar"):
        for _, r in ed_lote.iterrows():
            if r['accesorio'] and str(r['accesorio']).strip() != "":
                stk, cb, fl, ga = limpiar_num(r['stock']), limpiar_num(r['costo_base']), limpiar_num(r['flete']), limpiar_num(r['ganancia'])
                l1 = (cb + fl) * (1 + (ga / 100))
                ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                 VALUES (?,?,?,?,?,?,?,?,?)''', 
                               (str(r['rubro']), str(r['proveedor']), str(r['accesorio']), stk, cb, fl, ga, l1, l1*0.9), commit=True)
        st.success("¡Importación exitosa!"); st.rerun()

# PESTAÑA MAESTRO: EDICIÓN Y RECALCULO
with t[2]:
    st.header("⚙️ Editor Maestro")
    if not df_stock.empty:
        df_m = df_stock.copy(); df_m.insert(0, "Eliminar", False)
        res_m = st.data_editor(df_m, use_container_width=True, hide_index=True, key="maestro_ed_final")
        c1, c2 = st.columns(2)
        if c1.button("🗑️ Borrar Seleccionados"):
            for idx in res_m[res_m["Eliminar"] == True]["id"].tolist():
                ejecutar_query("DELETE FROM articulos WHERE id = ?", (idx,), commit=True)
            st.rerun()
        if c2.button("💾 Guardar y Saneamiento Total"):
            df_upd = res_m.drop(columns=["Eliminar"])
            for i, row in df_upd.iterrows():
                cb, fl, ga = limpiar_num(row["costo_base"]), limpiar_num(row["flete"]), limpiar_num(row["ganancia"])
                l1 = (cb + fl) * (1 + (ga / 100))
                df_upd.at[i, "lista1"], df_upd.at[i, "lista2"], df_upd.at[i, "costo_base"], df_upd.at[i, "flete"], df_upd.at[i, "ganancia"] = l1, l1*0.9, cb, fl, ga
                df_upd.at[i, "stock"] = limpiar_num(row["stock"])
            conn = sqlite3.connect(DB_NAME); df_upd.to_sql("articulos", conn, if_exists="replace", index=False); conn.close()
            st.success("Base de datos limpia y actualizada."); st.rerun()

# PESTAÑA VENTAS: CARRITO ACTIVO
with t[4]:
    st.header("📄 Nueva Venta")
    if not df_stock.empty:
        cli_v = st.selectbox("Cliente:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        col1, col2, col3 = st.columns([3,1,1])
        prod = col1.selectbox("Producto", df_stock["accesorio"].unique())
        cant = col2.number_input("Cant", 1)
        lst = col3.selectbox("Lista", ["lista1", "lista2"])
        if st.button("🛒 Agregar"):
            pu = float(df_stock[df_stock["accesorio"] == prod][lst].values[0])
            st.session_state.carrito.append({"Producto": prod, "Cant": cant, "Precio U.": pu, "Subtotal": pu * cant}); st.rerun()
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        if st.button("✅ Confirmar Venta"):
            total = sum(i['Subtotal'] for i in st.session_state.carrito)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total, cli_v), commit=True)
            for i in st.session_state.carrito:
                ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%y %H:%M"), cli_v, "VENTA", total, "Venta"), commit=True)
            st.session_state.carrito = []; st.rerun()

# PESTAÑA CIERRE
with t[6]:
    st.header("🏁 Resumen de Gestión")
    c1, c2 = st.columns(2)
    c1.metric("Deuda Clientes", f"$ {df_clientes['saldo'].sum() if not df_clientes.empty else 0:,.2f}")
    c2.metric("Inversión Stock (Costo)", f"$ {(df_stock['stock'] * df_stock['costo_base']).sum() if not df_stock.empty else 0:,.2f}")

# PESTAÑA REMITOS
with t[7]:
    st.header("📦 Remitos PDF")
    if st.session_state.carrito:
        if st.button("Generar PDF"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "AF ACCESORIOS - REMITO", ln=True, align="C")
            for i in st.session_state.carrito: pdf.cell(0, 10, f"{i['Cant']}x {i['Producto']} - ${i['Subtotal']:,.2f}", ln=True)
            st.download_button("Descargar PDF", pdf.output(dest='S').encode('latin-1'), "remito.pdf")

# OTRAS PESTAÑAS (HISTORIAL, STOCK, CTA CTE)
with t[0]: st.dataframe(df_stock, use_container_width=True, hide_index=True)
with t[3]: 
    st.header("Cuentas Corrientes")
    if not df_clientes.empty:
        sc = st.selectbox("Ver Cliente", df_clientes["nombre"].tolist())
        st.write(f"Saldo: **$ {df_clientes[df_clientes['nombre'] == sc]['saldo'].values[0]:,.2f}**")
    with st.expander("Nuevo Cliente"):
        nc = st.text_input("Nombre")
        if st.button("Crear"): ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (nc,), commit=True); st.rerun()
with t[5]: st.dataframe(ejecutar_query("SELECT * FROM movimientos").iloc[::-1], use_container_width=True)
