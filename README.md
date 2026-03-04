# RemoteControl Aula (MVP)

Aplicación base para administrar encendido/apagado y acceso a Internet de equipos Windows 11 Pro en un aula.

## Objetivo

Este proyecto implementa un **MVP funcional** con:

- Descubrimiento de equipos en una subred (ej. `192.168.50.0/24`).
- Panel del profesor con iconos por equipo y selección múltiple.
- Acciones remotas:
  - Apagar equipos.
  - Reiniciar equipos.
  - Encender equipos mediante Wake-on-LAN.
  - Bloquear Internet completamente.
  - Permitir Internet completo.
  - Permitir Internet parcial (lista blanca de dominios/IPs).
- Funcionamiento con o sin dominio de Active Directory (siempre que existan credenciales administrativas en los equipos destino).

> Nota: para ejecutar acciones remotas de apagado/reinicio y reglas de firewall, se usa PowerShell Remoting (WinRM).

## Arquitectura propuesta

- `remotecontrol/discovery.py`: detección de hosts por ICMP.
- `remotecontrol/ops.py`: creación y ejecución de comandos remotos + utilidades TrustedHosts/errores.
- `remotecontrol/policy.py`: generación de política de Internet (total/parcial).
- `remotecontrol/wol.py`: envío de paquetes Wake-on-LAN.
- `ui_panel.py`: panel Streamlit para el profesor.

## Requisitos

En el equipo del profesor:

- Python 3.11+
- Windows PowerShell 5.1+ o PowerShell 7+
- WinRM habilitado en destino y reglas de firewall correspondientes.
- Credenciales administrativas válidas en los equipos gestionados.

Instalación:

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run ui_panel.py
```

## Preparación de clientes (alumnos)

En cada cliente Windows 11 Pro (o por GPO):

1. Habilitar remoting WinRM:

```powershell
Enable-PSRemoting -Force
Set-Service WinRM -StartupType Automatic
Start-Service WinRM
```

2. Permitir conectividad remota por firewall (WinRM 5985/5986) y, si se usa descubrimiento por ping, ICMPv4 echo.
3. Conceder permisos administrativos remotos a la cuenta usada desde el panel.
4. Para encendido remoto, activar Wake-on-LAN en BIOS/NIC.

## Solución a error `ServerNotTrusted` / `TrustedHosts`

Si aparece un error indicando que el cliente WinRM no confía en el destino (equipos fuera de dominio Kerberos):

- Desde la propia app, usar el bloque lateral **Conectividad WinRM** y añadir la IP/DNS en TrustedHosts.
- O por PowerShell en el PC del profesor:

```powershell
Set-Item WSMan:\localhost\Client\TrustedHosts -Value "192.168.50.3" -Force
```

Para múltiples equipos:

```powershell
Set-Item WSMan:\localhost\Client\TrustedHosts -Value "192.168.50.*" -Force
```

## Seguridad y operación en dominio / sin dominio

- **Con dominio**: utilizar una cuenta de dominio con permisos de administración local en los equipos.
- **Sin dominio**: utilizar cuentas locales (mismo usuario/clave en todos los equipos o credenciales por equipo).
- Se recomienda limitar el acceso al panel por red/VPN y ejecutar con TLS en producción.

## Flujo de control de Internet parcial

1. Se bloquea tráfico saliente general.
2. Se crean reglas de salida permitiendo:
   - DNS (53 UDP/TCP) hacia DNS autorizados.
   - Dominios permitidos (cuando el sistema soporta `-RemoteFqdn`).
   - IPs permitidas explícitas.
3. Se mantiene acceso a servicios internos que se definan por IP/subred.

## Limitaciones de MVP

- El encendido depende de hardware/red (WOL activado en BIOS/NIC).
- El filtrado por dominio puede requerir Windows actualizado para soporte `RemoteFqdn`.
- No incluye aún inventario persistente en base de datos ni autenticación de usuarios del panel.
