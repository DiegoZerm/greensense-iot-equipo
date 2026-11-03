# Infraestructura local

Levanta el broker MQTT (Mosquitto) y la base de datos (PostgreSQL con TimescaleDB).

```bash
cd infra
cp .env.example .env              # cambiar las contraseñas
./mosquitto/crear_usuarios.sh     # genera mosquitto/passwd
docker compose up -d
docker compose ps                 # db debe aparecer como healthy
```

- Mosquitto no acepta conexiones anónimas. Cada nodo se conecta con su identificador como usuario, y la ACL (`mosquitto/acl`) solo le permite publicar en sus propios temas.
- Para agregar un nodo: se añade a `MQTT_NODOS` en `.env`, se vuelve a correr `crear_usuarios.sh` y se reinicia Mosquitto con `docker compose restart mosquitto`.
- Para borrar todos los datos: `docker compose down -v`.
