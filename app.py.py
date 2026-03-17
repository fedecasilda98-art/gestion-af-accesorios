import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# Definición de variables globales (Evita NameError de imagen 5a0367.png)
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos" 
LOGO_PATH = "logo.jpg"
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
    # VISTA CLIENTE (VIDRIERA)
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
    # VISTA ADMINISTRADOR
    menu = ["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre de Caja"]
    choice = st.tabs(menu)

with choice[0]: # PESTAÑA STOCK
        st.header("Análisis de Inventario")
        
        if not df_stock.empty:
            # 1. LIMPIEZA DE DATOS (Evita el error de la línea 115)
            # Convertimos a número y llenamos vacíos con 0 para que no falle la cuenta
            df_stock["Stock"] = pd.to_numeric(df_stock["Stock"], errors='coerce').fillna(0)
            df_stock["Costo Base"] = pd.to_numeric(df_stock["Costo Base"], errors='coerce').fillna(0)
            df_stock["Flete"] = pd.to_numeric(df_stock["Flete"], errors='coerce').fillna(0)
            df_stock["Lista 1 (Cheques)"] = pd.to_numeric(df_stock["Lista 1 (Cheques)"], errors='coerce').fillna(0)
            df_stock["Lista 2 (Efectivo)"] = pd.to_numeric(df_stock["Lista 2 (Efectivo)"], errors='coerce').fillna(0)

            # 2. CÁLCULOS DIRECTOS
            # Valor Real: (Costo + % Flete) * Stock
            valor_real_total = ((df_stock["Costo Base"] * (1 + df_stock["Flete"] / 100)) * df_stock["Stock"]).sum()
            
            # Valor Lista 1: Precio * Stock
            valor_lista1_total = (df_stock["Lista 1 (Cheques)"] * df_stock["Stock"]).sum()
            
            # Valor Lista 2: Precio * Stock
            valor_lista2_total = (df_stock["Lista 2 (Efectivo)"] * df_stock["Stock"]).sum()

            # 3. LAS TRES VARIANTES
            v1, v2, v3 = st.columns(3)
            
            v1.metric("Valor Real (Capital)", f"$ {valor_real_total:,.2f}")
            v2.metric("Total Lista 1 (Cheques)", f"$ {valor_lista1_total:,.2f}")
            v3.metric("Total Lista 2 (Efectivo)", f"$ {valor_lista2_total:,.2f}")

            st.divider()

            # 4. TABLA DETALLE
            st.subheader("Detalle de Inventario")
            st.dataframe(
                df_stock[["Rubro", "Accesorio", "Stock", "Costo Base", "Flete", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]], 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.warning("No hay artículos cargados.")
    with choice[1]: # PESTAÑA LOTE (Columnas ordenadas según pedido)
        st.header("🚚 Carga por Lote")
        df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete", "articulo existente/nuevo"])
        st.data_editor(df_lote_base, num_rows="dynamic", use_container_width=True)
        if st.button("Procesar Ingreso"):
            st.info("Función de guardado en preparación para el siguiente segmento.")

    with choice[2]: # PESTAÑA MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios Maestro"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("¡Base de datos actualizada!")

    with choice[3]: # PESTAÑA CTA CTE (Protección contra IndexError de imagen 5a07c3.png)
        st.header("👥 Gestión de Clientes")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("Nuevo Cliente")
            n_c = st.text_input("Nombre")
            t_c = st.text_input("Tel")
            l_c = st.text_input("Localidad")
            if st.button("Guardar"):
                nuevo = pd.DataFrame([[n_c, t_c, l_c, 0.0]], columns=df_clientes.columns)
                pd.concat([df_clientes, nuevo]).to_csv(ARCHIVO_CLIENTES, index=False)
                st.rerun()
        with c2:
            st.subheader("Saldos")
            if not df_clientes.empty:
                sel_cli = st.selectbox("Cliente:", df_clientes["Nombre"].tolist())
                datos_cli = df_clientes[df_clientes["Nombre"] == sel_cli]
                if not datos_cli.empty:
                    saldo = datos_cli["Saldo"].values[0]
                    st.metric(f"Saldo de {sel_cli}", f"$ {saldo:,.2f}")
            else: st.warning("No hay clientes.")

    with choice[4]: # PESTAÑA PRESUPUESTADOR (Selección de cliente y tabla)
        st.header("📄 Generador de Presupuestos")
        cli_p = st.selectbox("Cliente para el presupuesto:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"])
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1: it_p = st.selectbox("Artículo:", df_stock["Accesorio"].tolist())
        with col2: ca_p = st.number_input("Cant:", min_value=1, value=1)
        with col3: li_p = st.selectbox("Lista de Precio:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
        
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

    with choice[6]: # CIERRE DE CAJA
        st.header("🏁 Cierre de Caja")
        st.metric("Total Deuda Clientes", f"$ {df_clientes['Saldo'].sum():,.2f}")
        st.subheader("Últimos Movimientos")
        st.dataframe(df_movs.tail(10), use_container_width=True)
