#!/usr/bin/env bash
# Revisa que infra/.env no tenga valores de ejemplo o de desarrollo. Hay que correrlo antes
# de exponer el sistema a internet con el túnel. Nunca imprime los valores.
set -uo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Falta infra/.env" >&2
  exit 1
fi
set -a
source ./.env
set +a

graves=0
avisos=0
grave() {
  echo "CAMBIAR: $1"
  graves=$((graves + 1))
}
aviso() {
  echo "Aviso: $1"
  avisos=$((avisos + 1))
}

debil() {
  local valor="$1"
  [[ ${#valor} -lt 12 || "$valor" =~ ^(cambiar|prueba|admin|clave|password) ]]
}

# Lo que protege las sesiones de la app, que es lo único que el túnel expone.
[[ ${#JWT_SECRETO} -lt 32 ]] && grave "JWT_SECRETO está vacío o es corto"
[[ -z "${VAPID_PRIVADA:-}" || -z "${VAPID_PUBLICA:-}" ]] && grave "faltan las claves VAPID"
if [[ -n "${ADMIN_CONTRASENA:-}" ]] && debil "$ADMIN_CONTRASENA"; then
  grave "ADMIN_CONTRASENA es corta o de ejemplo: cámbiala aquí y en la app (Mi cuenta)"
fi

# La base y el broker no pasan por el túnel, pero sí se ven desde la red local.
debil "${DB_CONTRASENA:-}" && aviso "DB_CONTRASENA es corta o de ejemplo"
debil "${MQTT_CONTRASENA_SERVIDOR:-}" && aviso "MQTT_CONTRASENA_SERVIDOR es corta o de ejemplo"
for par in ${MQTT_NODOS:-}; do
  debil "${par#*:}" && aviso "la contraseña MQTT del nodo ${par%%:*} es corta o de ejemplo"
done

if ((graves)); then
  echo "$graves problema(s) que corregir antes de usar el túnel." >&2
  exit 1
fi
echo "Listo para el túnel ($avisos aviso(s)). Revisa también que cada usuario tenga una contraseña propia."
