import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# Archivos y Variables
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos" 
WHATSAPP_NUM = "5493413512049"

# Detectar Modo Cliente
es_cliente = st.query_params.get("modo") == "cliente"

if not os.path.exists(CARPETA_FOTOS): os.makedirs(CARPETA_FOTOS)

# --- CARGA DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Tel", "Localidad", "Saldo"])
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Fecha", "Cliente", "Tipo", "Monto", "Detalle"])

if "carrito" not in st.session_state:
    st.session_state.carrito = []

# --- LÓGICA DE INTERFAZ ---

if es_cliente:
    st.title("🛒 Catálogo AF Accesorios")
    busqueda = st.text_input("Buscar producto...", "").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False)]
    cols = st.columns(3)
    for idx, row in df_ver.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                nombre_foto = re.sub(r'[^a-zA-Z0-9\s]', '', str(row['Accesorio']))
                fp = os.path.join(CARPETA_FOTOS, f"{nombre_foto}.jpg")
                if os.path.exists(fp): st.image(fp, use_container_width=True)
                st.subheader(row["Accesorio"])
                l_tipo = st.radio("Condición:", ["Cheques", "Efectivo/Transf."], key=f"c_{idx}")
                p = row["Lista 1 (Cheques)"] if l_tipo == "Cheques" else row["Lista 2 (Efectivo)"]
                st.write(f"**$ {p:,.2f}**")
                c = st.number_input("Cantidad", 0, key=f"n_{idx}")
                if st.button("Pedir", key=f"b_{idx}"):
                    msg = f"Hola AF Accesorios! Quiero pedir {c} de {row['Accesorio']} ({l_tipo})."
                    st.markdown(f"[Confirmar en WhatsApp](https://wa.me/{WHATSAPP_NUM}?text={msg})")
else:
    menu = ["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre de Caja"]
    choice = st.tabs(menu)

    with choice[0]: # PESTAÑA STOCK
        st.header("Análisis de Inventario")
        if not df_stock.empty:
            # Limpieza y conversión rápida
            df_s = df_stock.copy()
            for col in ["Stock", "Costo Base", "Flete", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]:
                df_s[col] = pd.to_numeric(df_s[col], errors='coerce').fillna(0)

            # Las 3 Variantes que pediste
            valor_real = ((df_s["Costo Base"] * (1 + df_s["Flete"] / 100)) * df_s["Stock"]).sum()
            valor_l1 = (df_s["Lista 1 (Cheques)"] * df_s["Stock"]).sum()
            valor_l2 = (df_s["Lista 2 (Efectivo)"] * df_s["Stock"]).sum()

            v1, v2, v3 = st.columns(3)
            v1.metric("Costos + Fletes (Capital)", f"$ {valor_real:,.2f}")
            v2.metric("Total Lista 1 (Cheques)", f"$ {valor_l1:,.2f}")
            v3.metric("Total Lista 2 (Efectivo)", f"$ {valor_l2:,.2f}")

            st.divider()
            st.dataframe(df_s[["Rubro", "Accesorio", "Stock", "Costo Base", "Flete", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]], use_container_width=True, hide_index=True)
        else:
            st.warning("Stock vacío.")

    with choice[1]: # PESTAÑA LOTE
        st.header("🚚 Carga por Lote")
        df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete", "articulo existente/nuevo"])
        st.data_editor(df_lote_base, num_rows="dynamic", use_container_width=True)
        if st.button("Procesar Ingreso"):
            st.info("Función de guardado en preparación.")

    with choice[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios Maestro"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("Base actualizada.")

    with choice[3]: # CTA CTE
        st.header("👥 Gestión de Clientes")
        if not df_clientes.empty:
            sel_cli = st.selectbox("Cliente:", df_clientes["Nombre"].tolist())
            datos_cli = df_clientes[df_clientes["Nombre"] == sel_cli]
            if not datos_cli.empty:
                st.metric(f"Saldo de {sel_cli}", f"$ {datos_cli['Saldo'].values[0]:,.2f}")
        else: st.info("Sin clientes.")

    with choice[4]: # PRESUPUESTADOR
        st.header("📄 Generador de Presupuestos")
        cli_p = st.selectbox("Cliente:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: it_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist())
        with c2: ca_p = st.number_input("Cant:", min_value=1, value=1)
        with c3: li_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        
        if st.button("Agregar"):
            pr_u = df_stock[df_stock["Accesorio"] == it_p][li_p].values[0]
            st.session_state.carrito.append({"Producto": it_p, "Cant": ca_p, "Precio U.": pr_u, "Subtotal": pr_u * ca_p})
            st.rerun()

        if st.session_state.carrito:
            df_ca = pd.DataFrame(st.session_state.carrito)
            st.table(df_ca)
            st.write(f"### TOTAL PARA {cli_p}: $ {df_ca['Subtotal'].sum():,.2f}")
            if st.button("Limpiar"):
                st.session_state.carrito = []
                st.rerun()

    with choice[5]: # ÓRDENES
        st.header("📋 Órdenes de Trabajo")
        st.dataframe(df_movs, use_container_width=True)

    with choice[6]: # CIERRE DE CAJA
        st.header("🏁 Cierre de Caja")
        st.metric("Total Deuda Clientes", f"$ {df_clientes['Saldo'].sum():,.2f}")
