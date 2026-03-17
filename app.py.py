import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Tel", "Localidad", "Saldo"])

if "carrito" not in st.session_state:
    st.session_state.carrito = []

# --- INTERFAZ ---
menu = ["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "🏁 Cierre"]
choice = st.tabs(menu)

with choice[0]: # PESTAÑA STOCK
    st.header("Análisis de Inventario")
    if not df_stock.empty:
        # Aseguramos que todo sea número para que la suma no falle
        df_s = df_stock.copy()
        for c in ["Stock", "Costo Base", "Flete", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]:
            df_s[c] = pd.to_numeric(df_s[c], errors='coerce').fillna(0)

        # CÁLCULOS PRECISOS
        # Variante 1: Suma de (Costo + Flete) * Cantidad
        total_inversion = ((df_s["Costo Base"] * (1 + df_s["Flete"] / 100)) * df_s["Stock"]).sum()
        # Variante 2: Suma de Lista 1 * Cantidad
        total_l1 = (df_s["Lista 1 (Cheques)"] * df_s["Stock"]).sum()
        # Variante 3: Suma de Lista 2 * Cantidad
        total_l2 = (df_s["Lista 2 (Efectivo)"] * df_s["Stock"]).sum()

        v1, v2, v3 = st.columns(3)
        v1.metric("Capital (Costo + Flete)", f"$ {total_inversion:,.2f}")
        v2.metric("Venta Total L1", f"$ {total_l1:,.2f}")
        v3.metric("Venta Total L2", f"$ {total_l2:,.2f}")

        st.divider()
        st.dataframe(df_s, use_container_width=True, hide_index=True)

with choice[1]: # LOTE
    st.header("🚚 Carga por Lote")
    df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete", "articulo existente/nuevo"])
    st.data_editor(df_lote_base, num_rows="dynamic", use_container_width=True, key="editor_lote")

with choice[2]: # MAESTRO
    st.header("⚙️ Maestro de Artículos")
    df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True, key="editor_maestro")
    if st.button("Guardar Cambios"):
        df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
        st.success("Guardado.")

with choice[3]: # CTA CTE
    st.header("👥 Gestión de Clientes")
    if not df_clientes.empty:
        # Agregamos un key único ("cli_cta_cte") para evitar el error de la imagen
        sel_c = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="cli_cta_cte")
        s = df_clientes[df_clientes["Nombre"] == sel_c]["Saldo"].values[0]
        st.metric(f"Saldo de {sel_c}", f"$ {s:,.2f}")
    else: st.info("No hay clientes cargados.")

with choice[4]: # PRESUPUESTADOR
    st.header("📄 Generador de Presupuestos")
    # Agregamos otro key único ("cli_presu") para que no choque con el de Cta Cte
    cli_p = st.selectbox("Cliente para el presupuesto:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cli_presu")
    
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: it_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist(), key="item_p")
    with c2: ca_p = st.number_input("Cant:", min_value=1, value=1, key="cant_p")
    with c3: li_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="lista_p")
    
    if st.button("Agregar al presupuesto"):
        precio = df_stock[df_stock["Accesorio"] == it_p][li_p].values[0]
        st.session_state.carrito.append({"Producto": it_p, "Cant": ca_p, "Precio": precio, "Subtotal": precio * ca_p})
        st.rerun()

    if st.session_state.carrito:
        st.table(pd.DataFrame(st.session_state.carrito))
        st.write(f"### TOTAL: $ {sum(item['Subtotal'] for item in st.session_state.carrito):,.2f}")
        if st.button("Limpiar"):
            st.session_state.carrito = []
            st.rerun()

with choice[5]: # CIERRE
    st.header("🏁 Cierre")
    st.write("Resumen de saldos y stock listo.")
