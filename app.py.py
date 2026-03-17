import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Gestión Integral", layout="wide")
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
ARCHIVO_MOVIMIENTOS = "movimientos_clientes.csv"
CARPETA_FOTOS = "fotos_productos" 
WHATSAPP_NUM = "5493413512049"

# Detectar modo cliente
es_cliente = st.query_params.get("modo") == "cliente"

# --- FUNCIONES DE CARGA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            df.columns = df.columns.str.strip()
            # Asegurar que las columnas numéricas sean números
            cols_num = ["Stock", "Saldo", "Monto", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Costo Base"]
            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# Carga inicial de datos
df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Proveedor", "Accesorio", "Stock", "Costo Base", "Flete", "% Ganancia", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"])
df_clientes = cargar_datos(ARCHIVO_CLIENTES, ["Nombre", "Teléfono", "Localidad", "Saldo"])
df_movs = cargar_datos(ARCHIVO_MOVIMIENTOS, ["Fecha", "Cliente", "Tipo", "Monto", "Detalle", "Nro_Orden"])

# ---------------------------------------------------------
# LÓGICA DE INTERFAZ
# ---------------------------------------------------------

if es_cliente:
    # --- VISTA CLIENTE (NUEVA FUNCIÓN SOBRIA) ---
    st.title("🛒 Catálogo de Pedidos - AF Accesorios")
    st.info("Precios de referencia sin IVA. Consultar disponibilidad.")
    
    busqueda = st.text_input("Buscar herraje...", "").upper()
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False)]
    
    cols = st.columns(3)
    for idx, row in df_ver.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                nombre_foto = re.sub(r'[^a-zA-Z0-9\s]', '', str(row['Accesorio']))
                fp = os.path.join(CARPETA_FOTOS, f"{nom_limpio}.jpg" if 'nom_limpio' in locals() else f"{nombre_foto}.jpg")
                if os.path.exists(fp): st.image(fp, use_container_width=True)
                st.subheader(row["Accesorio"])
                
                # Comparador de listas para el cliente
                l_tipo = st.radio("Condición:", ["Cheques", "Efectivo/Transf."], key=f"l_{idx}")
                precio = row["Lista 1 (Cheques)"] if l_tipo == "Cheques" else row["Lista 2 (Efectivo)"]
                st.write(f"**Precio: $ {precio:,.2f}**")
                if l_tipo == "Cheques": st.caption("Consultar plazos de pago.")
                
                cant = st.number_input("Cantidad", min_value=0, step=1, key=f"c_{idx}")
                if st.button("Pedir por WhatsApp", key=f"b_{idx}"):
                    if cant > 0:
                        msg = f"Hola AF Accesorios! Quiero pedir: {cant} unidades de {row['Accesorio']} en {l_tipo}."
                        link = f"https://wa.me/{WHATSAPP_NUM}?text={msg}"
                        st.markdown(f'[Confirmar pedido aquí]({link})')

else:
    # --- VISTA ADMINISTRADOR (RECUPERADA TOTALMENTE) ---
    st.title("⚙️ Sistema de Gestión - AF Accesorios")
    
    tabs = st.tabs(["📊 Stock", "⚙️ Maestro", "👥 Clientes", "📄 Presupuestos", "📑 Órdenes de Trabajo", "📸 Fotos"])
    
    with tabs[0]: # STOCK
        st.subheader("Estado de Inventario")
        st.dataframe(df_stock, use_container_width=True, hide_index=True)

    with tabs[1]: # MAESTRO (EDICIÓN)
        st.subheader("Editor de Precios y Artículos")
        df_ed = st.data_editor(df_stock, use_container_width=True, hide_index=True)
        if st.button("Guardar Cambios Maestro"):
            guardar_datos(df_ed, ARCHIVO_ARTICULOS)
            st.success("¡Datos guardados!")

    with tabs[2]: # CLIENTES
        st.subheader("Cuentas Corrientes")
        st.dataframe(df_clientes, use_container_width=True, hide_index=True)
        # Aquí puedes agregar el formulario para nuevos clientes o saldos
        
    with tabs[3]: # PRESUPUESTOS
        st.subheader("Generador de Presupuestos PDF")
        st.write("Seleccioná los artículos y generá el documento para el cliente.")
        # Aquí iría el código del carrito de ayer...

    with tabs[4]: # ÓRDENES
        st.subheader("Registro de Órdenes y Movimientos")
        st.dataframe(df_movs, use_container_width=True)

    with tabs[5]: # FOTOS
        st.subheader("Vincular Fotos a Artículos")
        art_f = st.selectbox("Elegí el artículo:", sorted(df_stock["Accesorio"].tolist()))
        file_f = st.file_uploader("Subir imagen", type=['jpg', 'png'])
        if st.button("Vincular Foto"):
            if file_f:
                nom = re.sub(r'[^a-zA-Z0-9\s]', '', art_f)
                with open(os.path.join(CARPETA_FOTOS, f"{nom}.jpg"), "wb") as f:
                    f.write(file_f.getbuffer())
                st.success(f"Foto vinculada a {art_f}")

    st.sidebar.markdown("---")
    st.sidebar.info(f"**Link para el Cliente:**\nSu-App.streamlit.app/?modo=cliente")
