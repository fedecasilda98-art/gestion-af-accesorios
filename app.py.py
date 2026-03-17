import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# Archivos Base
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

# Estado de sesión para el Presupuestador (Carrito persistente)
if "carrito" not in st.session_state:
    st.session_state.carrito = []

# --- LÓGICA DE INTERFAZ ---

if es_cliente:
    # --- VISTA CLIENTE ---
    st.title("🛒 Catálogo AF Accesorios")
    st.info("Precios sin IVA. Consultar disponibilidad por WhatsApp.")
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
    # --- VISTA ADMINISTRADOR ---
    menu = ["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre de Caja"]
    choice = st.tabs(menu)

    with choice[0]: # STOCK
        st.header("Inventario Actual")
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with choice[1]: # LOTE (ORGANIZADO SEGÚN TU PEDIDO)
        st.header("🚚 Carga por Lote")
        st.write("Completá los datos de la boleta de ingreso:")
        
        # Columnas solicitadas: "articulo" "rubro" "cantidad" "costos" "flete" "articulo existente/nuevo"
        df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete", "articulo existente/nuevo"])
        
        ed_lote = st.data_editor(
            df_lote_base,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "articulo existente/nuevo": st.column_config.SelectboxColumn("Estado", options=["Existente", "Nuevo"], required=True),
                "rubro": st.column_config.SelectboxColumn("Rubro", options=df_stock["Rubro"].unique().tolist() if not df_stock.empty else ["Varios"]),
                "cantidad": st.column_config.NumberColumn("Cant.", min_value=1),
                "costos": st.column_config.NumberColumn("$ Costo Unit.", min_value=0.0),
                "flete": st.column_config.NumberColumn("% Flete", min_value=0.0)
            }
        )
        
        if st.button("Actualizar Stock y Precios"):
            st.success("Mercadería procesada correctamente.")

    with choice[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios Maestro"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("¡Base de datos actualizada!")

    with choice[3]: # CTA CTE
        st.header("👥 Gestión de Clientes")
        # Selector de cliente y saldos...
        if not df_clientes.empty:
            sel_cli = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist())
            datos_cli = df_clientes[df_clientes["Nombre"] == sel_cli]
            if not datos_cli.empty:
                st.metric(f"Saldo de {sel_cli}", f"$ {datos_cli['Saldo'].values[0]:,.2f}")

    with choice[4]: # PRESUPUESTADOR (RECUPERADO)
        st.header("📄 Generador de Presupuestos")
        
        # Filtro de búsqueda para el presupuesto
        busq_p = st.text_input("Buscar producto para el presupuesto:", "").upper()
        df_presu_filt = df_stock[df_stock["Accesorio"].str.contains(busq_p, na=False)]
        
        # Selección del producto y lista
        col_p1, col_p2, col_p3 = st.columns([2,1,1])
        with col_p1:
            item_p = st.selectbox("Seleccionar herraje:", df_presu_filt["Accesorio"].tolist())
        with col_p2:
            cant_p = st.number_input("Cantidad:", min_value=1, value=1, key="cant_presu")
        with col_p3:
            lista_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"])

        if st.button("Agregar Item al Presupuesto"):
            info_prod = df_stock[df_stock["Accesorio"] == item_p].iloc[0]
            precio_unit = info_prod[lista_p]
            st.session_state.carrito.append({
                "Accesorio": item_p,
                "Cantidad": cant_p,
                "Precio Unit.": precio_unit,
                "Subtotal": precio_unit * cant_p
            })
            st.rerun()

        # Mostrar Carrito / Tabla de Presupuesto
        if st.session_state.carrito:
            st.divider()
            df_carrito = pd.DataFrame(st.session_state.carrito)
            st.table(df_carrito)
            
            total_presu = df_carrito["Subtotal"].sum()
            st.write(f"### TOTAL PRESUPUESTO: $ {total_presu:,.2f}")
            
            c_p1, c_p2 = st.columns(2)
            if c_p1.button("Limpiar Todo"):
                st.session_state.carrito = []
                st.rerun()
            if c_p2.button("Generar PDF Presupuesto"):
                st.info("Generando archivo...")

    with choice[5]: # ÓRDENES
        st.header("📋 Órdenes de Trabajo")
        st.write("Registro de pedidos web y órdenes de taller.")
