import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión AF Accesorios", layout="wide", initial_sidebar_state="collapsed")

# Definición de variables globales (Esto corrige el error de la Imagen 3)
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

# --- LÓGICA DE INTERFAZ ---

if es_cliente:
    # VISTA CLIENTE
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
    # VISTA ADMINISTRADOR (ESTILO ORIGINAL)
    menu = ["📊 Stock", "🚚 Lote", "⚙️ Maestro", "👥 Cta Cte", "📄 Presupuestador", "📋 Órdenes", "🏁 Cierre de Caja"]
    choice = st.tabs(menu)

    with choice[0]: # Stock
        st.header("Inventario Actual")
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with choice[2]: # Maestro
        st.header("Administración de Precios")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios Maestro"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("¡Datos guardados!")

    with choice[3]: # Cta Cte
        st.header("Gestión de Clientes")
        with st.expander("📝 Alta / Modificación de Cliente"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nombre")
            t = c2.text_input("Tel")
            l = c1.text_input("Localidad")
            s = c2.number_input("Saldo Inicial", 0.0)
            if st.button("Guardar Cliente"):
                nuevo = pd.DataFrame([[n, t, l, s]], columns=df_clientes.columns)
                df_clientes = pd.concat([df_clientes, nuevo], ignore_index=True)
                df_clientes.to_csv(ARCHIVO_CLIENTES, index=False)
                st.success("Cliente guardado")
                st.rerun()
        
        st.divider()
        if not df_clientes.empty:
            sel_cli = st.selectbox("Seleccionar Cliente:", df_clientes["Nombre"].tolist())
            datos_cli = df_clientes[df_clientes["Nombre"] == sel_cli]
            if not datos_cli.empty:
                saldo_actual = datos_cli["Saldo"].values[0]
                st.subheader(f"Saldo de {sel_cli}: $ {saldo_actual:,.2f}")
        else:
            st.warning("No hay clientes cargados.")

    # --- BARRA LATERAL (Sidebar) ---
    with st.sidebar:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH)
        else:
            st.write("AF Accesorios")
        st.header("Configuración de Fotos")
        art_f = st.selectbox("Producto:", sorted(df_stock["Accesorio"].tolist()))
        file_f = st.file_uploader("Subir imagen", type=['jpg', 'png'])
        if st.button("Vincular Foto"):
            if file_f:
                nom = re.sub(r'[^a-zA-Z0-9\s]', '', art_f)
                with open(os.path.join(CARPETA_FOTOS, f"{nom}.jpg"), "wb") as f:
                    f.write(file_f.getbuffer())
                st.success("Foto vinculada")
