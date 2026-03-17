import streamlit as st
import pandas as pd
import os
from datetime import datetime
from fpdf import FPDF
import re
import urllib.parse

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="AF Accesorios - Pedidos", layout="wide")
ARCHIVO_ARTICULOS = "lista_articulos_interna.csv"
ARCHIVO_CLIENTES = "clientes_base.csv"
CARPETA_FOTOS = "fotos_productos" 
LOGO_PATH = "logo.jpg"
WHATSAPP_NUM = "5493413512049"

# Detectar si es modo cliente por la URL
query_params = st.query_params
es_cliente = query_params.get("modo") == "cliente"

# Crear carpetas si no existen
for carpeta in [CARPETA_FOTOS]:
    if not os.path.exists(carpeta): os.makedirs(carpeta)

# --- ESTADO DE SESIÓN ---
if "carrito_cliente" not in st.session_state:
    st.session_state.carrito_cliente = []

# --- FUNCIONES DE DATOS ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo)
            for col in ["Stock", "Lista 1 (Cheques)", "Lista 2 (Efectivo)"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except: return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

df_stock = cargar_datos(ARCHIVO_ARTICULOS, ["Rubro", "Accesorio", "Stock", "Lista 1 (Cheques)", "Lista 2 (Efectivo)", "Descripcion"])

# --- LÓGICA DE INTERFAZ ---

if es_cliente:
    # ---------------------------------------------------------
    # VISTA CLIENTE (SOBRIA)
    # ---------------------------------------------------------
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=150)
    st.title("🛒 Pedidos Online - AF Accesorios")
    st.write("Bienvenido a nuestra vidriera virtual. Armá tu pedido y envialo por WhatsApp.")
    st.info("⚠️ Nota: Los precios visualizados no incluyen IVA.")

    # Buscador y Filtro
    busqueda = st.text_input("Buscar producto (ej: T87, Rodamiento...)", "").upper()
    
    # Mostrar productos en tarjetas
    df_ver = df_stock[df_stock["Accesorio"].str.contains(busqueda, na=False)]
    
    cols = st.columns(3)
    for idx, row in df_ver.iterrows():
        with cols[idx % 3]:
            with st.container(border=True):
                # Imagen
                nombre_foto = re.sub(r'[^a-zA-Z0-9\s]', '', str(row['Accesorio']))
                foto_path = os.path.join(CARPETA_FOTOS, f"{nombre_foto}.jpg")
                if os.path.exists(foto_path):
                    st.image(foto_path, use_container_width=True)
                else:
                    st.caption("Sin imagen")
                
                st.subheader(row["Accesorio"])
                st.write(f"Ref: {row['Rubro']}")
                
                cant = st.number_input(f"Cantidad", min_value=0, step=1, key=f"cant_{idx}")
                if st.button(f"Añadir", key=f"btn_{idx}"):
                    if cant > row["Stock"]:
                        st.error(f"Lo sentimos, solo disponemos de {int(row['Stock'])} unidades.")
                    elif cant > 0:
                        st.session_state.carrito_cliente.append({
                            "item": row["Accesorio"],
                            "cantidad": cant,
                            "p1": row["Lista 1 (Cheques)"],
                            "p2": row["Lista 2 (Efectivo)"]
                        })
                        st.success("Agregado")

    # --- CARRITO FLOTANTE / FINALIZAR ---
    if st.session_state.carrito_cliente:
        st.divider()
        st.header("📋 Tu Pedido")
        
        # Selector de Lista (El comparador que querías)
        opcion_lista = st.radio(
            "Seleccioná tu condición de pago para ver el total:",
            ["Lista 1: Cheques (Consultar plazos)", "Lista 2: Efectivo / Transferencia"],
            index=0
        )
        
        # Mostrar resumen
        total_pedido = 0
        resumen_texto = ""
        for i, p in enumerate(st.session_state.carrito_cliente):
            precio = p["p1"] if "Lista 1" in opcion_lista else p["p2"]
            subtotal = precio * p["cantidad"]
            total_pedido += subtotal
            st.write(f"- {p['cantidad']} x {p['item']} : **$ {subtotal:,.2f}**")
            resumen_texto += f"- {p['cantidad']} x {p['item']} (%24 {precio:,.2f} c/u)%0A"

        st.subheader(f"Total Estimado: $ {total_pedido:,.2f}")
        st.caption("Precios sujetos a variación. Consultar disponibilidad final.")

        # Datos finales
        with st.container(border=True):
            nombre_c = st.text_input("Tu Nombre / Empresa")
            vendedor_c = st.text_input("Vendedor que lo visita / atiende")
            
            if st.button("🚀 ENVIAR PEDIDO POR WHATSAPP"):
                if nombre_c and vendedor_c:
                    # Armar link de WhatsApp
                    msg = f"Hola AF Accesorios! 👋 Soy *{nombre_c}*.%0A"
                    msg += f"Vendedor: {vendedor_c}%0A"
                    msg += f"Condición: {opcion_lista}%0A%0A"
                    msg += f"Detalle del pedido:%0A{resumen_texto}%0A"
                    msg += f"*TOTAL ESTIMADO: $ {total_pedido:,.2f}*%0A%0A"
                    msg += "Los productos están sin IVA. Aguardo confirmación de stock."
                    
                    link_wa = f"https://wa.me/{WHATSAPP_NUM}?text={msg}"
                    st.markdown(f'<a href="{link_wa}" target="_blank" style="text-decoration:none;"><button style="background-color:#25D366;color:white;padding:10px;border:none;border-radius:5px;width:100%;cursor:pointer;">Confirmar y Abrir WhatsApp</button></a>', unsafe_allow_html=True)
                else:
                    st.warning("Por favor, completá tu nombre y el vendedor.")

else:
    # ---------------------------------------------------------
    # VISTA GESTIÓN (INTERNA PARA VOS)
    # ---------------------------------------------------------
    st.title("⚙️ Gestión Interna - AF Accesorios")
    st.write("Estás en el modo administrativo.")
    
    # Aquí va tu código de gestión que ya teníamos...
    tabs = st.tabs(["📊 Stock", "⚙️ Maestro", "👥 Clientes", "📖 Fotos/Catálogo"])
    
    with tabs[0]:
        st.dataframe(df_stock, use_container_width=True)
    
    with tabs[1]:
        st.write("Acá podés editar precios y stock como siempre.")
        df_ed = st.data_editor(df_stock, use_container_width=True, key="editor_interno")
        if st.button("Guardar Cambios"):
            df_ed.to_csv(ARCHIVO_ARTICULOS, index=False)
            st.success("Guardado")

    with tabs[3]:
        st.subheader("Subir Fotos para el Cliente")
        art_sel = st.selectbox("Elegí el artículo:", sorted(df_stock["Accesorio"].tolist()))
        foto_subida = st.file_uploader("Saca una foto o elegí una", type=['jpg', 'jpeg', 'png'])
        if st.button("Guardar Foto"):
            if foto_subida:
                nom_limpio = re.sub(r'[^a-zA-Z0-9\s]', '', art_sel)
                path_f = os.path.join(CARPETA_FOTOS, f"{nom_limpio}.jpg")
                with open(path_f, "wb") as f: f.write(foto_subida.getbuffer())
                st.success(f"Foto de {art_sel} guardada.")

    st.sidebar.write("---")
    st.sidebar.write("🔗 **Link para Clientes:**")
    st.sidebar.code(f"https://tu-app.streamlit.app/?modo=cliente")
