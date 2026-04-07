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

# --- 2. UTILIDADES DE LIMPIEZA (EL "ESCUDO" CONTRA ERRORES) ---
def limpiar_num(val):
    """Evita el TypeError convirtiendo cualquier cosa a float seguro."""
    if pd.isna(val) or str(val).strip() == "": return 0.0
    try:
        # Quita $, espacios y arregla comas por puntos
        s = str(val).replace('$', '').replace(' ', '').replace(',', '.').strip()
        return float(s)
    except: return 0.0

def formatear_moneda(valor):
    try: return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
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
        txt = f"{item['Cant']}x {item['Producto']} - P.U: {formatear_moneda(item['Precio U.'])} - Sub: {formatear_moneda(item['Subtotal'])}"
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

# --- 4. INTERFAZ ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

with tabs[0]: # STOCK
    st.header("Inventario Actual")
    if not df_stock.empty:
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

with tabs[1]: # LOTE (PROTEGIDO)
    st.header("🚚 Carga Masiva")
    st.info("Pegá tus datos aquí. No importa si tienen símbolos de pesos o comas.")
    df_guia = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_guia, num_rows="dynamic", use_container_width=True)
    if st.button("🚀 Procesar e Importar"):
        for _, r in ed_lote.iterrows():
            if r['accesorio']:
                s, cb, fl, ga = limpiar_num(r['stock']), limpiar_num(r['costo_base']), limpiar_num(r['flete']), limpiar_num(r['ganancia'])
                l1 = (cb + fl) * (1 + ga/100)
                ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                 VALUES (?,?,?,?,?,?,?,?,?)''', (str(r['rubro']), str(r['proveedor']), str(r['accesorio']), s, cb, fl, ga, l1, l1*0.9), commit=True)
        st.success("Importación exitosa."); st.rerun()

with tabs[2]: # MAESTRO (CON ELIMINACIÓN MÚLTIPLE)
    st.header("⚙️ Editor Maestro")
    if not df_stock.empty:
        df_maestro = df_stock.copy()
        df_maestro.insert(0, "Seleccionar", False)
        ed_maestro = st.data_editor(df_maestro, use_container_width=True, hide_index=True, column_config={"Seleccionar": st.column_config.CheckboxColumn("Eliminar?")})
        c_m1, c_m2 = st.columns([1, 4])
        if c_m1.button("🗑️ Borrar Marcados"):
            for id_b in ed_maestro[ed_maestro["Seleccionar"] == True]["id"].tolist():
                ejecutar_query("DELETE FROM articulos WHERE id = ?", (id_b,), commit=True)
            st.rerun()
        if c_m2.button("💾 Guardar Cambios"):
            df_upd = ed_maestro.drop(columns=["Seleccionar"])
            # Recalcular precios por si se editó costo/ganancia
            df_upd["lista1"] = (df_upd["costo_base"].apply(limpiar_num) + df_upd["flete"].apply(limpiar_num)) * (1 + df_upd["ganancia"].apply(limpiar_num)/100)
            df_upd["lista2"] = df_upd["lista1"] * 0.9
            conn = sqlite3.connect(DB_NAME); df_upd.to_sql("articulos", conn, if_exists="replace", index=False); conn.close()
            st.success("Datos actualizados."); st.rerun()

with tabs[3]: # CTA CTE
    st.header("👥 Gestión de Clientes")
    if not df_clientes.empty:
        cli_sel = st.selectbox("Cliente:", df_clientes["nombre"].tolist())
        datos_cli = df_clientes[df_clientes["nombre"] == cli_sel].iloc[0]
        st.metric("Saldo Pendiente", formatear_moneda(datos_cli["saldo"]))
        m_pago = st.number_input("Registrar Pago $", min_value=0.0)
        if st.button("Confirmar Pago"):
            ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (m_pago, cli_sel), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y %H:%M"), cli_sel, "PAGO", m_pago, "Cobro"), commit=True)
            st.rerun()
    with st.expander("Nuevo Cliente"):
        n_n = st.text_input("Nombre"); 
        if st.button("Crear"): ejecutar_query("INSERT INTO clientes (nombre, saldo) VALUES (?,0.0)", (n_n,), commit=True); st.rerun()

with tabs[4]: # VENTAS (SOLUCIÓN AL INDEXERROR)
    st.header("📄 Ventas")
    if not df_stock.empty:
        c_ven = st.selectbox("Cliente:", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        col1, col2, col3 = st.columns([2,1,1])
        p_ven = col1.selectbox("Producto", df_stock["accesorio"].unique())
        q_ven = col2.number_input("Cantidad", 1)
        l_ven = col3.selectbox("Lista", ["lista1", "lista2"])
        if st.button("🛒 Añadir al Carrito"):
            match = df_stock[df_stock["accesorio"] == p_ven]
            if not match.empty:
                pre = float(match[l_ven].values[0])
                st.session_state.carrito.append({"Producto": p_ven, "Cant": q_ven, "Precio U.": pre, "Subtotal": pre * q_ven}); st.rerun()
    else: st.warning("Cargá stock para poder vender.")
    if st.session_state.carrito:
        st.table(st.session_state.carrito)
        if st.button("Finalizar Venta"):
            tot = sum(i['Subtotal'] for i in st.session_state.carrito)
            ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (tot, c_ven), commit=True)
            for i in st.session_state.carrito: ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
            ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y %H:%M"), c_ven, "VENTA", tot, "Venta"), commit=True)
            st.session_state.carrito = []; st.rerun()

with tabs[5]: # HISTORIAL
    st.header("📋 Movimientos")
    st.dataframe(df_movs.iloc[::-1], use_container_width=True)

with tabs[6]: # CIERRE (REINSTALADO)
    st.header("🏁 Caja y Resumen")
    c1, c2 = st.columns(2)
    c1.metric("Deuda Clientes", formatear_moneda(df_clientes["saldo"].sum()) if not df_clientes.empty else "$ 0")
    c2.metric("Inversión Stock", formatear_moneda((df_stock["stock"] * df_stock["costo_base"]).sum()) if not df_stock.empty else "$ 0")

with tabs[7]: # REMITOS
    st.header("📦 Generar Remito")
    if st.session_state.carrito:
        if st.button("Bajar PDF"):
            pdf_b = generar_pdf_binario("Cliente", st.session_state.carrito, sum(i['Subtotal'] for i in st.session_state.carrito))
            st.download_button("Descargar", pdf_b, "remito.pdf", "application/pdf")
