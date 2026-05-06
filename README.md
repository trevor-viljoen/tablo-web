# tablo-web

![CI](https://github.com/trevor-viljoen/tablo-web/actions/workflows/ci.yml/badge.svg)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/trevor-viljoen/tablo-web?style=flat-square)
![GitHub top language](https://img.shields.io/github/languages/top/trevor-viljoen/tablo-web?style=flat-square)
![GitHub language count](https://img.shields.io/github/languages/count/trevor-viljoen/tablo-web?style=flat-square)
![GitHub repo size](https://img.shields.io/github/repo-size/trevor-viljoen/tablo-web?style=flat-square)
![GitHub](https://img.shields.io/github/license/trevor-viljoen/tablo-web?style=flat-square)

> **Warning**  
> This is an unofficial web interface for Tablo devices. It is not affiliated with Nuvyyo Inc. or Tablo. Use at your own risk.

A modern, responsive web application for your Tablo (Gen 4) devices. Built with React, TypeScript, FastAPI, and FFmpeg for seamless live TV streaming and library management.

---

## Features

- **Live TV Streaming:** Smart transcoding (via FFmpeg) for high-compatibility browser playback.
- **Traditional Guide:** A full timeline/grid view of upcoming programs.
- **Library Management:** Browse and watch your recordings directly in the browser.
- **Auto-Discovery:** Automatically finds and connects to your Tablo devices on the local network.
- **Containerized:** Easy deployment using Docker or Podman.

---

## Prerequisites

- **Tablo Gen 4 Device** (with an active account).
- **Docker** or **Podman** with **Docker Compose / Podman Compose**.
- **FFmpeg** (included in the backend container).

---

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/trevor-viljoen/tablo-web.git
   cd tablo-web
   ```

2. **Launch the stack:**
   ```bash
   # Using Docker
   docker-compose up -d --build

   # Using Podman
   podman-compose up -d --build
   ```

3. **Access the app:**
   Open `http://localhost:7070` in your browser.

4. **Login:**
   Use your Tablo account email and password to authenticate.

---

## Architecture

- **Frontend:** React + Vite + Tailwind CSS + hls.js.
- **Backend:** FastAPI (Python) + FFmpeg for transcoding + [tablo-api](https://github.com/trevor-viljoen/tablo-api).
- **Proxy:** Nginx handles routing between the frontend and backend containers.

---

## Security

- This application proxies sensitive requests to your local Tablo device.
- Credentials (email/password) are stored locally in a `data/config.json` volume and are only used for authentication with the Tablo cloud API.
- Live streams are proxied and transcoded locally on your server.

---

## Support & Donations

If you find this project useful and would like to support its development, you can buy me a coffee!

[![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/trevorviljoen)
[![GitHub Sponsors](https://img.shields.io/badge/Sponsors-EA4AAA?style=for-the-badge&logo=github-sponsors&logoColor=white)](https://github.com/sponsors/trevor-viljoen)

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

> Tablo and the Tablo logo are trademarks of Nuvyyo Inc.
marks of Nuvyyo Inc.
