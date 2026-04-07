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

# --- 2. ESCUDO ANTI-ERRORES (CRÍTICO) ---
def forzar_num(val):
    """Convierte cualquier entrada a número float, eliminando basura de texto."""
    if pd.isna(val) or str(val).strip() == "": return 0.0
    try:
        # Limpia $, espacios, comas y puntos
        s = str(val).replace('$', '').replace(' ', '').replace(',', '.').strip()
        return float(s)
    except:
        return 0.0

def formatear_moneda(valor):
    try: return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

# --- 3. CARGA DE DATOS ---
df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")
df_movs = ejecutar_query("SELECT * FROM movimientos")

if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 4. INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

with tabs[0]: # STOCK
    st.header("Inventario")
    if not df_stock.empty:
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # LOTE
    st.header("🚚 Carga Masiva")
    df_guia = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_guia, num_rows="dynamic", use_container_width=True)
    if st.button("🚀 Importar Datos"):
        for _, r in ed_lote.iterrows():
            if r['accesorio']:
                s, cb, fl, ga = forzar_num(r['stock']), forzar_num(r['costo_base']), forzar_num(r['flete']), forzar_num(r['ganancia'])
                l1 = (cb + fl) * (1 + ga/100)
                ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                 VALUES (?,?,?,?,?,?,?,?,?)''', (str(r['rubro']), str(r['proveedor']), str(r['accesorio']), s, cb, fl, ga, l1, l1*0.9), commit=True)
        st.success("Cargado."); st.rerun()

with tabs[2]: # MAESTRO (CON ELIMINACIÓN Y RECALCULO SEGURO)
    st.header("⚙️ Editor Maestro")
    if not df_stock.empty:
        df_maestro = df_stock.copy()
        df_maestro.insert(0, "Seleccionar", False)
        ed_maestro = st.data_editor(df_maestro, use_container_width=True, hide_index=True, column_config={"Seleccionar": st.column_config.CheckboxColumn("Eliminar?")})
        
        c_m1, c_m2 = st.columns([1, 4])
        if c_m1.button("🗑️ Borrar"):
            for id_b in ed_maestro[ed_maestro["Seleccionar"] == True]["id"].tolist():
                ejecutar_query("DELETE FROM articulos WHERE id = ?", (id_b,), commit=True)
            st.rerun()
            
        if c_m2.button("💾 Guardar y Recalcular Precios"):
            df_upd = ed_maestro.drop(columns=["Seleccionar"])
            # AQUÍ ESTÁ EL ARREGLO: Forzamos número en cada fila antes de calcular
            for i, row in df_upd.iterrows():
                cb = forzar_num(row["costo_base"])
                fl = forzar_num(row["flete"])
                ga = forzar_num(row["ganancia"])
                l1 = (cb + fl) * (1 + ga/100)
                df_upd.at[i, "lista1"] = l1
                df_upd.at[i, "lista2"] = l1 * 0.9
                df_upd.at[i, "costo_base"] = cb
                df_upd.at[i, "flete"] = fl
                df_upd.at[i, "ganancia"] = ga
                df_upd.at[i, "stock"] = forzar_num(row["stock"])

            conn = sqlite3.connect(DB_NAME)
            df_upd.to_sql("articulos", conn, if_exists="replace", index=False)
            conn.close()
            st.success("Base de datos saneada y actualizada."); st.rerun()

with tabs[3]: # CTA CTE
    st.header("👥 Clientes")
    if not df_clientes.empty:
        cli_sel = st.selectbox("Cliente:", df_clientes["nombre"].tolist())
        datos_cli = df_clientes[df_clientes["nombre"] == cli_sel].iloc[0]
        st.metric("Saldo Pendiente", formatear_moneda(datos_cli["saldo"]))
        p = st.number_input("Pago $", min_value=0.0)
        if st.button("Cobrar"):
            ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (p, cli_sel), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y %H:%M"), cli_sel, "PAGO", p, "Cobro"), commit=True)
            st.rerun()
    with st.expander("Nuevo"):
        n = st.text_input("Nombre"); 
        if st.button("Crear Cliente"): ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (n,), commit=True); st.rerun()

with tabs[4]: # VENTAS
    st.header("📄 Ventas")
    if not df_stock.empty:
        c_v = st.selectbox("Vender a:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Final"])
        col1, col2 = st.columns([3,1])
        p_v = col1.selectbox("Producto", df_stock["accesorio"].unique())
        q_v = col2.number_input("Cant", 1)
        if st.button("🛒 Agregar"):
            m = df_stock[df_stock["accesorio"] == p_v]
            if not m.empty:
                pre = float(m["lista1"].values[0])
                st.session_state.carrito.append({"Producto": p_v, "Cant": q_v, "Precio U.": pre, "Subtotal": pre * q_v}); st.rerun()
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        if st.button("Cerrar Venta"):
            tot = sum(i['Subtotal'] for i in st.session_state.carrito)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (tot, c_v), commit=True)
            for i in st.session_state.carrito: ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y %H:%M"), c_v, "VENTA", tot, "Venta"), commit=True)
            st.session_state.carrito = []; st.rerun()

with tabs[5]: # HISTORIAL
    st.header("📋 Movimientos")
    st.dataframe(df_movs.iloc[::-1], use_container_width=True)

with tabs[6]: # CIERRE
    st.header("🏁 Resumen General")
    c1, c2 = st.columns(2)
    c1.metric("Deuda Clientes", formatear_moneda(df_clientes["saldo"].sum()) if not df_clientes.empty else "$ 0")
    c2.metric("Valor Stock", formatear_moneda((df_stock["stock"] * df_stock["costo_base"]).sum()) if not df_stock.empty else "$ 0")

with tabs[7]: # REMITOS
    st.header("📦 Remitos")
    if st.session_state.carrito:
        if st.button("Generar PDF"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", "B", 16); pdf.cell(40, 10, "AF Accesorios - Remito"); pdf_b = pdf.output(dest='S').encode('latin-1')
            st.download_button("Descargar", pdf_b, "remito.pdf")
