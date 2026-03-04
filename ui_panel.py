from __future__ import annotations

import streamlit as st

from remotecontrol.discovery import discover_hosts
from remotecontrol.models import Host
from remotecontrol.ops import ClassroomController, Credentials
from remotecontrol.policy import InternetPolicy


st.set_page_config(page_title="RemoteControl Aula", layout="wide")
st.title("Panel de Control del Profesor")

cidr = st.text_input("Subred del aula", value="192.168.50.0/24")

with st.sidebar:
    st.header("Credenciales remotas")
    use_creds = st.checkbox("Usar credenciales explícitas", value=False)
    username = st.text_input("Usuario", value="") if use_creds else ""
    password = st.text_input("Contraseña", type="password", value="") if use_creds else ""

if st.button("Detectar equipos"):
    with st.spinner("Escaneando red..."):
        st.session_state["hosts"] = discover_hosts(cidr)

hosts: list[Host] = st.session_state.get("hosts", [])

if not hosts:
    st.info("No hay equipos detectados todavía. Pulsa 'Detectar equipos'.")
    st.stop()

st.subheader(f"Equipos detectados: {len(hosts)}")

options = {f"{h.ip} ({h.name or 'sin nombre'})": h.ip for h in hosts}
selected_labels = st.multiselect("Selecciona equipos", options=list(options.keys()), default=list(options.keys()))
selected_ips = [options[x] for x in selected_labels]

cols = st.columns(4)
for idx, host in enumerate(hosts):
    with cols[idx % 4]:
        marker = "🟢" if host.ip in selected_ips else "⚪"
        st.markdown(f"{marker} **{host.name or 'Equipo'}**  ")
        st.caption(host.ip)

creds = Credentials(username=username, password=password) if use_creds and username and password else None
controller = ClassroomController(credentials=creds)

with st.sidebar:
    st.divider()
    st.subheader("Conectividad WinRM")
    trusted_target = st.text_input("Añadir TrustedHost (IP o DNS)", value="")
    if st.button("Agregar a TrustedHosts"):
        if trusted_target.strip():
            trusted_result = controller.add_trusted_host(trusted_target.strip())
            if trusted_result.returncode == 0:
                st.success(f"TrustedHosts actualizado con: {trusted_target.strip()}")
            else:
                st.error(f"No se pudo actualizar TrustedHosts: {controller.format_error(trusted_result.stderr, trusted_result.stdout)}")
        else:
            st.warning("Indica una IP o nombre DNS para TrustedHosts")

st.divider()
left, mid, right = st.columns(3)

with left:
    if st.button("Apagar seleccionados", type="primary"):
        for ip in selected_ips:
            result = controller.shutdown(ip)
            if result.returncode == 0:
                st.success(f"Apagado enviado a {ip}")
            else:
                st.error(f"Error en {ip}: {controller.format_error(result.stderr, result.stdout)}")

with mid:
    if st.button("Bloquear Internet (total)"):
        policy = InternetPolicy(mode="block_all")
        for ip in selected_ips:
            result = controller.apply_internet_policy(ip, policy)
            if result.returncode == 0:
                st.success(f"Internet bloqueado en {ip}")
            else:
                st.error(f"Error en {ip}: {controller.format_error(result.stderr, result.stdout)}")

with right:
    if st.button("Abrir Internet (total)"):
        policy = InternetPolicy(mode="allow_all")
        for ip in selected_ips:
            result = controller.apply_internet_policy(ip, policy)
            if result.returncode == 0:
                st.success(f"Internet habilitado en {ip}")
            else:
                st.error(f"Error en {ip}: {controller.format_error(result.stderr, result.stdout)}")

st.divider()
st.subheader("Internet parcial (lista blanca)")
allowed_domains = st.text_area("Dominios permitidos (uno por línea)", value="educa.madrid.org\n*.wikipedia.org")
allowed_ips = st.text_area("IPs permitidas (una por línea)", value="8.8.8.8")
allowed_dns = st.text_input("DNS permitidos (coma separada)", value="8.8.8.8,1.1.1.1")

if st.button("Aplicar Internet parcial"):
    policy = InternetPolicy(
        mode="allow_list",
        allowed_domains=[x.strip() for x in allowed_domains.splitlines() if x.strip()],
        allowed_ips=[x.strip() for x in allowed_ips.splitlines() if x.strip()],
        allowed_dns_servers=[x.strip() for x in allowed_dns.split(",") if x.strip()],
    )
    for ip in selected_ips:
        result = controller.apply_internet_policy(ip, policy)
        if result.returncode == 0:
            st.success(f"Política parcial aplicada en {ip}")
        else:
            st.error(f"Error en {ip}: {controller.format_error(result.stderr, result.stdout)}")
