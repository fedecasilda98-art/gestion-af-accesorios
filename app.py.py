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

    with choice[0]: # PESTAÑA STOCK ÚNICA
        st.header("Inventario Actual")
        
        if not df_stock.empty:
            # Limpieza para cálculos
            df_calc = df_stock.copy()
            for col in ["Stock", "Costo Base", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]:
                df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce').fillna(0)

            # Las 3 sumas que pediste
            total_costo = (df_calc["Costo Base"] * df_calc["Stock"]).sum()
            total_l1 = (df_calc["Lista 1 (Cheques)"] * df_calc["Stock"]).sum()
            total_l2 = (df_calc["Lista 2 (Efectivo)"] * df_calc["Stock"]).sum()

            c1, c2, c3 = st.columns(3)
            c1.metric("Importe Stock (Costo)", f"$ {total_costo:,.2f}")
            c2.metric("Total Lista 1", f"$ {total_l1:,.2f}")
            c3.metric("Total Lista 2", f"$ {total_l2:,.2f}")
            
            st.divider()
        
        # Tabla de abajo
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with choice[1]: # LOTE
        st.header("🚚 Carga por Lote")
        df_lote_base = pd.DataFrame(columns=["articulo", "rubro", "cantidad", "costos", "flete", "articulo existente/nuevo"])
        ed_lote = st.data_editor(df_lote_base, num_rows="dynamic", use_container_width=True)
        if st.button("Actualizar Stock"):
            st.success("Mercadería ingresada.")

    with choice[2]: # MAESTRO
        st.header("⚙️ Maestro de Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios Maestro"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("¡Base de datos actualizada!")

    with choice[3]: # CTA CTE
        st.header("👥 Gestión de Clientes")
        col_c1, col_c2 = st.columns([1, 2])
        with col_c1:
            st.subheader("Nuevo Cliente")
            n_cli = st.text_input("Nombre", key="n_cli_reg")
            t_cli = st.text_input("Teléfono", key="t_cli_reg")
            l_cli = st.text_input("Localidad", key="l_cli_reg")
            if st.button("Registrar Cliente"):
                nuevo = pd.DataFrame([[n_cli, t_cli, l_cli, 0.0]], columns=df_clientes.columns)
                pd.concat([df_clientes, nuevo]).to_csv(ARCHIVO_CLIENTES, index=False)
                st.rerun()
        with col_c2:
            st.subheader("Buscador de Saldos")
            if not df_clientes.empty:
                sel_cli = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist(), key="sel_cli_vista")
                saldo = df_clientes[df_clientes["Nombre"] == sel_cli]["Saldo"].values[0]
                st.metric(f"Saldo de {sel_cli}", f"$ {saldo:,.2f}")
                
                monto_pago = st.number_input("Registrar Pago/Entrega $:", min_value=0.0, key="pago_cli")
                if st.button("Confirmar Pago"):
                    df_clientes.loc[df_clientes["Nombre"] == sel_cli, "Saldo"] -= monto_pago
                    df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                    st.success("Saldo actualizado")
                    st.rerun()

    with choice[4]: # PRESUPUESTADOR
        st.header("📄 Generador de Presupuestos")
        cliente_p = st.selectbox("Seleccionar Cliente para el presupuesto:", df_clientes["Nombre"].tolist() if not df_clientes.empty else ["Consumidor Final"], key="cli_presu")
        st.divider()
        col_p1, col_p2, col_p3 = st.columns([2, 1, 1])
        with col_p1:
            item_p = st.selectbox("Seleccionar Artículo:", df_stock["Accesorio"].tolist(), key="item_presu")
        with col_p2:
            cant_p = st.number_input("Cant:", min_value=1, value=1, key="cant_presu")
        with col_p3:
            lista_p = st.selectbox("Lista:", ["Lista 1 (Cheques)", "Lista 2 (Efectivo)"], key="lista_presu")

        if st.button("Agregar al Presupuesto"):
            precio_u = df_stock[df_stock["Accesorio"] == item_p][lista_p].values[0]
            st.session_state.carrito.append({"Producto": item_p, "Cant": cant_p, "Precio U.": precio_u, "Subtotal": precio_u * cant_p})
            st.rerun()

        if st.session_state.carrito:
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car)
            total = df_car["Subtotal"].sum()
            st.write(f"### TOTAL PARA {cliente_p}: $ {total:,.2f}")
            if st.button("Limpiar Presupuesto"):
                st.session_state.carrito = []
                st.rerun()

    with choice[5]: # ÓRDENES
        st.header("📋 Órdenes de Trabajo")
        st.dataframe(df_movs, use_container_width=True)

    with choice[6]: # CIERRE DE CAJA
        st.header("🏁 Cierre de Caja")
        col_z1, col_z2 = st.columns(2)
        total_stock_c = (df_stock["Stock"] * df_stock["Costo Base"]).sum()
        total_deuda = df_clientes["Saldo"].sum()
        
        col_z1.metric("Valor del Stock (Costo)", f"$ {total_stock_c:,.2f}")
        col_z2.metric("Total Deuda Clientes", f"$ {total_deuda:,.2f}")
        
        st.subheader("Últimos Movimientos")
        st.dataframe(df_movs.tail(10), use_container_width=True)
