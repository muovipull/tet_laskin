#!/bin/bash

# Varmistetaan, että skripti ajetaan sudo-oikeuksilla (koska systemd vaatii sen)
if [ "$EUID" -ne 0 ]; then
  echo "Aja tämä skripti root-oikeuksilla komennolla: sudo ./asenna.sh"
  exit 1
fi

# Haetaan nykyinen kansio ja käyttäjä, joka komennon antoi
PROJECT_DIR="$(pwd)"
REAL_USER="${SUDO_USER:-$(whoami)}"

echo "==> Työskentelykansio: $PROJECT_DIR"
echo "==> Sovelluksen omistaja: $REAL_USER"

# 1. Luodaan virtuaaliympäristö ja asennetaan riippuvuudet oikean käyttäjän oikeuksilla
echo "==> Luodaan venv ja asennetaan Flask..."
sudo -u "$REAL_USER" python3 -m venv "$PROJECT_DIR/venv"
sudo -u "$REAL_USER" "$PROJECT_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$REAL_USER" "$PROJECT_DIR/venv/bin/pip" install flask

# 2. Luodaan systemd-palvelutiedosto
SERVICE_FILE="/etc/systemd/system/tyoaika.service"
echo "==> Luodaan Systemd-palvelu tiedostoon: $SERVICE_FILE"

cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Työaika Flask Server
After=network.target

[Service]
User=$REAL_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 3. Aktivoidaan palvelu
echo "==> Otetaan palvelu käyttöön ja käynnistetään..."
systemctl daemon-reload
systemctl enable tyoaika.service
systemctl start tyoaika.service

echo "==> Valmista! Palvelun tila:"
systemctl status tyoaika.service --no-pager