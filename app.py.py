import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from fpdf import FPDF
import io

# --- 1. CONFIGURACIÓN DE RUTAS Y BASE DE DATOS ---
DB_PATH = "/app/data/"
DB_NAME = os.path.join(DB_PATH, "gestion_af_accesorios.db")

# Asegurar que la carpeta del volumen existe para no perder datos
if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH)

def ejecutar_query(query, params=(), commit=False):
    """Manejo centralizado de consultas SQL con cierre de conexión seguro"""
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
        st.error(f"Error en Base de Datos: {e}")
    finally:
        conn.close()

def init_db():
    """Inicializa las tablas si no existen"""
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

# --- 2. FUNCIÓN DE MIGRACIÓN (SOLO PRIMERA VEZ) ---
def migrar_datos_desde_csv():
    """Muda los datos de tus archivos CSV a la base de datos SQL de Railway"""
    try:
        # Migrar Artículos
        check_art = ejecutar_query("SELECT COUNT(*) as cuenta FROM articulos")
        if check_art["cuenta"].iloc[0] == 0 and os.path.exists("lista_articulos_interna.csv"):
            df_v = pd.read_csv("lista_articulos_interna.csv")
            conn = sqlite3.connect(DB_NAME)
            df_v.to_sql("articulos", conn, if_exists="replace", index=False)
            conn.close()
            st.toast("✅ Stock migrado desde CSV")

        # Migrar Clientes
        check_cli = ejecutar_query("SELECT COUNT(*) as cuenta FROM clientes")
        if check_cli["cuenta"].iloc[0] == 0 and os.path.exists("clientes_base.csv"):
            df_c = pd.read_csv("clientes_base.csv")
            conn = sqlite3.connect(DB_NAME)
            df_c.to_sql("clientes", conn, if_exists="replace", index=False)
            conn.close()
            st.toast("✅ Clientes migrados desde CSV")
    except Exception as e:
        st.error(f"Error en migración inicial: {e}")

# Ejecutar arranque
init_db()
migrar_datos_desde_csv()

# --- 3. UTILIDADES Y CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Gestión", layout="wide")

def formatear_moneda(valor):
    try:
        return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "$ 0,00"

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 15)
        self.cell(0, 10, "AF ACCESORIOS - REMITO DE ENTREGA", ln=True, align="C")
        self.set_font("Arial", "", 10)
        self.cell(0, 5, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
        self.ln(10)

# --- 4. CARGA DE DATOS PARA LA INTERFAZ ---
df_stock = ejecutar_query("SELECT * FROM articulos")
df_clientes = ejecutar_query("SELECT * FROM clientes")
df_movs = ejecutar_query("SELECT * FROM movimientos")

if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 5. INTERFAZ POR PESTAÑAS ---
tabs = st.tabs(["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Ventas", "📋 Historial", "🏁 Cierre", "📦 Remitos"])

# TAB 0: VISTA DE STOCK
with tabs[0]:
    st.header("Inventario en Tiempo Real")
    if not df_stock.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Valor Stock (Costo)", formatear_moneda((df_stock['costo_base'] * df_stock['stock']).sum()))
        c2.metric("Total Lista 1", formatear_moneda((df_stock['lista1'] * df_stock['stock']).sum()))
        c3.metric("Unidades en Depósito", int(df_stock['stock'].sum()))
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

# TAB 1: CARGA POR LOTE
with tabs[1]:
    st.header("Carga Masiva de Mercadería")
    st.write("Pegá desde Excel o cargá manualmente:")
    df_lote_template = pd.DataFrame(columns=["rubro", "proveedor", "accesorio", "stock", "costo_base", "flete", "ganancia"])
    ed_lote = st.data_editor(df_lote_template, num_rows="dynamic", use_container_width=True)
    
    if st.button("Guardar Lote en Base de Datos"):
        for _, r in ed_lote.iterrows():
            if r['accesorio']:
                l1 = (float(r['costo_base']) + float(r['flete'])) * (1 + float(r['ganancia'])/100)
                ejecutar_query('''INSERT INTO articulos (rubro, proveedor, accesorio, stock, costo_base, flete, ganancia, lista1, lista2) 
                                 VALUES (?,?,?,?,?,?,?,?,?)''',
                               (r['rubro'], r['proveedor'], r['accesorio'], r['stock'], r['costo_base'], r['flete'], r['ganancia'], l1, l1*0.9), commit=True)
        st.success("Lote procesado. Los precios se calcularon automáticamente.")
        st.rerun()

# TAB 2: EDITOR MAESTRO (MODIFICAR PRECIOS/STOCK EXISTENTE)
with tabs[2]:
    st.header("Editor Maestro de Artículos")
    if not df_stock.empty:
        ed_m = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="maestro_editor")
        if st.button("Aplicar Cambios Globales"):
            # Recalcular precios antes de guardar
            ed_m["lista1"] = (ed_m["costo_base"] + ed_m["flete"]) * (1 + ed_m["ganancia"] / 100)
            ed_m["lista2"] = ed_m["lista1"] * 0.90
            conn = sqlite3.connect(DB_NAME)
            ed_m.to_sql("articulos", conn, if_exists="replace", index=False)
            conn.close()
            st.success("Cambios guardados y precios actualizados.")
            st.rerun()

# TAB 3: CUENTAS CORRIENTES (COMPLETO)
with tabs[3]:
    st.header("Gestión de Clientes")
    c_alta, c_pago = st.columns([1, 2])
    
    with c_alta:
        with st.expander("➕ Nuevo Cliente"):
            n_n = st.text_input("Nombre")
            n_t = st.text_input("Tel")
            if st.button("Crear Cliente"):
                ejecutar_query("INSERT INTO clientes (nombre, tel, saldo) VALUES (?,?,0)", (n_n, n_t), commit=True)
                st.rerun()
                
    with c_pago:
        if not df_clientes.empty:
            sel_cli = st.selectbox("Seleccionar Cliente", df_clientes["nombre"].tolist())
            cli_data = df_clientes[df_clientes["nombre"] == sel_cli].iloc[0]
            st.subheader(f"Saldo Actual: {formatear_moneda(cli_data['saldo'])}")
            
            col_p1, col_p2 = st.columns(2)
            p_monto = col_p1.number_input("Monto del Pago $", min_value=0.0)
            p_metodo = col_p2.selectbox("Método", ["Efectivo", "Transferencia", "Cheque"])
            
            if st.button("Registrar Cobro"):
                ejecutar_query("UPDATE clientes SET saldo = saldo - ? WHERE nombre = ?", (p_monto, sel_cli), commit=True)
                ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, metodo, detalle) VALUES (?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y %H:%M"), sel_cli, "PAGO", p_monto, p_metodo, f"Cobro en {p_metodo}"), commit=True)
                st.success("Pago registrado correctamente.")
                st.rerun()

# TAB 4: VENTAS Y PRESUPUESTOS
with tabs[4]:
    st.header("Nueva Venta / Presupuesto")
    if not df_stock.empty:
        c_v_cli = st.selectbox("Cliente para la venta", df_clientes["nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        v_col1, v_col2, v_col3 = st.columns([3, 1, 1])
        
        v_prod = v_col1.selectbox("Elegir Accesorio", df_stock["accesorio"].tolist())
        v_cant = v_col2.number_input("Cant.", min_value=1)
        v_lista = v_col3.selectbox("Lista", ["lista1", "lista2"])
        
        if st.button("Agregar al Carrito"):
            p_match = df_stock[df_stock["accesorio"] == v_prod].iloc[0]
            precio_u = p_match[v_lista]
            st.session_state.carrito.append({
                "Producto": v_prod, "Cant": v_cant, "Precio U.": precio_u, "Subtotal": v_cant * precio_u
            })
            st.rerun()

        if st.session_state.carrito:
            st.table(st.session_state.carrito)
            total_v = sum(i['Subtotal'] for i in st.session_state.carrito)
            st.subheader(f"Total: {formatear_moneda(total_v)}")
            
            if st.button("CONFIRMAR VENTA (Afecta Stock y Saldo)"):
                for i in st.session_state.carrito:
                    ejecutar_query("UPDATE articulos SET stock = stock - ? WHERE accesorio = ?", (i['Cant'], i['Producto']), commit=True)
                ejecutar_query("UPDATE clientes SET saldo = saldo + ? WHERE nombre = ?", (total_v, c_v_cli), commit=True)
                ejecutar_query("INSERT INTO movimientos (fecha, cliente, tipo, monto, detalle) VALUES (?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y %H:%M"), c_v_cli, "VENTA", total_v, "Venta de mercadería"), commit=True)
                st.session_state.carrito = []
                st.success("Venta procesada con éxito.")
                st.rerun()
            
            if st.button("Vaciar Carrito"):
                st.session_state.carrito = []
                st.rerun()

# TAB 5: HISTORIAL GLOBAL
with tabs[5]:
    st.header("Historial de Movimientos")
    st.dataframe(df_movs.sort_values(by="id", ascending=False), use_container_width=True, hide_index=True)

# TAB 6: CIERRE Y MÉTRICAS
with tabs[6]:
    st.header("Resumen del Negocio")
    m1, m2 = st.columns(2)
    m1.metric("Total a cobrar (Cta Cte)", formatear_moneda(df_clientes['saldo'].sum()) if not df_clientes.empty else "$ 0,00")
    m2.metric("Inversión en Stock", formatear_moneda((df_stock['stock'] * df_stock['costo_base']).sum()) if not df_stock.empty else "$ 0,00")

# TAB 7: REMITOS PDF
with tabs[7]:
    st.header("Generación de Remitos")
    if st.session_state.carrito:
        st.write("Generando remito para los productos en el carrito actual...")
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        
        # Tabla simple en PDF
        pdf.cell(100, 10, "Producto", border=1)
        pdf.cell(30, 10, "Cant.", border=1)
        pdf.cell(40, 10, "Total", border=1, ln=True)
        
        for i in st.session_state.carrito:
            pdf.cell(100, 10, str(i['Producto']), border=1)
            pdf.cell(30, 10, str(i['Cant']), border=1)
            pdf.cell(40, 10, formatear_moneda(i['Subtotal']), border=1, ln=True)
            
        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        total_r = sum(i['Subtotal'] for i in st.session_state.carrito)
        pdf.cell(0, 10, f"TOTAL A PAGAR: {formatear_moneda(total_r)}", ln=True, align="R")
        
        buffer = io.BytesIO()
        pdf.output(buffer)
        st.download_button("📥 Descargar Remito PDF", data=buffer.getvalue(), file_name=f"Remito_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf")
    else:
        st.info("El carrito está vacío. Agregá productos en la pestaña 'Ventas' para generar un remito.")
