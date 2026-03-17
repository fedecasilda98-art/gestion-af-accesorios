import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Gestión y Pedidos", layout="wide")
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos" 
LOGO_PATH = "logo.jpg"
WHATSAPP_NUM = "5493413512049"

# Detectar modo cliente
es_cliente = st.query_params.get("modo") == "cliente"

# --- FUNCIONES DE CARGA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            cols_num = ["Stock", "Saldo", "Monto", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]
            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Accesorio", "Stock", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Teléfono", "Localidad", "Saldo"])
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Fecha", "Cliente", "Tipo", "Monto", "Detalle"])

# ---------------------------------------------------------
# INTERFAZ
# ---------------------------------------------------------

if es_cliente:
    # --- MODO CLIENTE (LO QUE YA PROBAMOS) ---
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=120)
    st.title("🛒 Pedidos Online")
    st.info("Precios sin IVA. Elegí tus productos y confirmá por WhatsApp.")
    
    busqueda = st.text_input("Buscar producto...", "").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False)]
    
    # Grid de productos con fotos
    cols = st.columns(3)
    for idx, row in df_ver.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                nombre_foto = re.sub(r'[^a-zA-Z0-9\s]', '', str(row['Accesorio']))
                fp = os.path.join(CARPETA_FOTOS, f"{nombre_foto}.jpg")
                if os.path.exists(fp): st.image(fp, use_container_width=True)
                st.subheader(row["Accesorio"])
                
                # Selector de lista para que el cliente compare
                l_cli = st.radio("Lista:", ["Cheques", "Efectivo"], key=f"l_{idx}", horizontal=True)
                p_v = row["Lista 1 (Cheques)"] if l_cli == "Cheques" else row["Lista 2 (Efectivo)"]
                st.write(f"**Precio: $ {p_v:,.2f}**")
                
                if st.button("Añadir", key=f"add_{idx}"):
                    st.success(f"Agregado: {row['Accesorio']}")
                    # Aquí podés agregar lógica de carrito si querés, 
                    # pero por ahora mantenemos la sobriedad.

else:
    # --- MODO GESTIÓN TOTAL (RECUPERADO) ---
    st.title("⚙️ Administración General - AF Accesorios")
    
    pestanas = st.tabs(["📊 Stock y Maestro", "👥 Cuentas Corrientes", "📝 Órdenes y Movs", "📸 Config Catálogo"])
    
    with pestanas[0]:
        st.subheader("Inventario y Precios")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios Stock"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("¡Stock actualizado!")

    with pestanas[1]:
        st.subheader("Saldos de Clientes")
        st.dataframe(df_clientes, use_container_width=True, hide_index=True)
        # Aquí podés agregar el editor para cobrar o vender
    
    with pestanas[2]:
        st.subheader("Historial de Movimientos")
        st.dataframe(df_movs, use_container_width=True)

    with pestanas[3]:
        st.subheader("Cargar Fotos para Clientes")
        art = st.selectbox("Producto:", sorted(df_stock["Accesorio"].tolist()))
        f = st.file_uploader("Foto:", type=['jpg', 'png'])
        if st.button("Subir Foto"):
            if f:
                nom = re.sub(r'[^a-zA-Z0-9\s]', '', art)
                with open(os.path.join(CARPETA_FOTOS, f"{nom}.jpg"), "wb") as out:
                    out.write(f.getbuffer())
                st.success("Foto guardada.")

    st.sidebar.info(f"Link Cliente:\n`?modo=cliente`")
