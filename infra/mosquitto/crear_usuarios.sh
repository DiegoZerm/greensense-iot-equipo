#!/usr/bin/env bash
# Genera infra/mosquitto/passwd con el usuario del servidor y uno por nodo,
# a partir de infra/.env. Se vuelve a correr cada vez que se agrega un nodo.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f ../.env ]]; then
  echo "Falta infra/.env (copiar de infra/.env.example)" >&2
  exit 1
fi
set -a
source ../.env
set +a

if [[ "${MQTT_USUARIO_SERVIDOR}" != "servidor" ]]; then
  echo "La ACL espera que el usuario del servidor se llame 'servidor'" >&2
  exit 1
fi

rm -f passwd
comandos="mosquitto_passwd -c -b /m/passwd '${MQTT_USUARIO_SERVIDOR}' '${MQTT_CONTRASENA_SERVIDOR}'"
for par in ${MQTT_NODOS}; do
  comandos+=" && mosquitto_passwd -b /m/passwd '${par%%:*}' '${par#*:}'"
done

docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/m" eclipse-mosquitto:2 sh -c "$comandos"
# Mosquitto corre con su propio usuario dentro del contenedor y necesita leerlo.
# Solo contiene hashes con sal, no las contraseñas.
chmod 644 passwd
echo "passwd generado con el servidor y $(wc -w <<<"${MQTT_NODOS}") nodo(s)"
