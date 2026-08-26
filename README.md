<h1 align="center">PC Telemetry Dashboard</h1> <p align="center">
<a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="Licence MIT"></a>
  <img src="https://img.shields.io/badge/status-active-brightgreen.svg" alt="Statut actif">
    

  <img src="https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Requests-2.x-2A6DB0?logo=python&logoColor=white" alt="Requests">
  <img src="https://img.shields.io/badge/LibreHardwareMonitor-compatible-2563EB" alt="LibreHardwareMonitor">
</p> <p align="center">
  Tableau de bord local de télémétrie matérielle, alimenté par LibreHardwareMonitor.  

  Interface web responsive avec jauges CPU, GPU, mémoire, stockage et capteurs auxiliaires.
</p>

---

## Présentation

**PC Telemetry Dashboard** est une application Flask légère qui interroge le serveur web local de LibreHardwareMonitor, normalise les mesures disponibles, puis les affiche dans une interface unique rafraîchie toutes les 1,5 secondes. LibreHardwareMonitor est un projet libre capable de suivre notamment les températures, vitesses de ventilateurs, tensions, charges et fréquences de l’ordinateur [1].

---

## Fonctionnalités

L’interface centralise les informations matérielles dans une vue sombre et responsive. Elle continue de s’afficher lorsqu’une mesure est indisponible ; les valeurs absentes sont représentées par `--`, ce qui évite de présenter une donnée estimée comme une mesure réelle.

| Bloc | Mesures affichées |
| --- | --- |
| **Processeur** | Température, charge, fréquence, puissance et tension. |
| **Carte graphique** | Température, charge, fréquence, vitesse de ventilation, puissance et VRAM. |
| **Mémoire** | Taux d’occupation, mémoire utilisée et disponible. |
| **Stockage** | Occupation, capacité disponible et température de deux volumes. |
| **Capteurs auxiliaires** | Température carte mère et VRM, pompe, ventilateurs boîtier et hotspot GPU. |

---

## Architecture

L’application se compose d’un serveur Flask, d’un endpoint JSON et d’une interface HTML/CSS/JavaScript embarquée. Flask associe des fonctions Python à des routes HTTP, ce qui permet ici d’exposer la page principale et l’API de télémétrie [2].

```
LibreHardwareMonitor Web Server
          │  GET /data.json
          ▼
  dashboard_pc.py
  ├── lecture et recherche des capteurs
  ├── configuration locale sensors.json
  └── API GET /api/data
          │  JSON, toutes les 1,5 s
          ▼
Interface web responsive
  ├── jauges SVG
  ├── cartes RAM et stockage
  └── statut de connexion
```

## Installation

Le projet nécessite **Python 3.10 ou une version ultérieure** ainsi qu’une instance locale de LibreHardwareMonitor avec son serveur web activé. Les mesures visibles dépendent du matériel et des capteurs effectivement exposés par LibreHardwareMonitor [1].

```bash
# 1. Cloner le dépôt
git clone https://github.com/nono271105/pc-dashboard.git
cd pc-dashboard

# 2. Créer et activer un environnement virtuel
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer sensors.json, puis lancer l'application
python dashboard_pc.py
```

L’application écoute par défaut uniquement sur `127.0.0.1:5000`. Ouvrez ensuite [http://127.0.0.1:5000](http://127.0.0.1:5000). La page officielle de Flask rappelle que son serveur intégré convient au développement et ne doit pas être utilisé tel quel en production [2].

---

## Configuration locale

| Variable | Valeur par défaut | Usage |
| --- | --- | --- |
| `LHM_URL` | `http://localhost:8085/data.json` | URL du serveur web LibreHardwareMonitor. |
| `LHM_USER` | Vide | Identifiant HTTP Basic optionnel. |
| `LHM_PASS` | Vide | Mot de passe HTTP Basic optionnel. |
| `SENSOR_CONFIG_FILE` | `sensors.json` | Emplacement des correspondances de capteurs. |
| `NAMES_FILE` | `names.json` | Fichier local de secours facultatif. |
| `APP_HOST` | `127.0.0.1` | Adresse d’écoute du dashboard. |
| `APP_PORT` | `5000` | Port d’écoute du dashboard. |

Le fichier `sensors.json` est également local et ignoré par Git. Chaque clé de `sensors` contient une liste de fragments qui doivent tous apparaître dans le chemin d’un capteur. Il faut remplacer les valeurs indicatives de `sensors.example.json` par les libellés réellement exposés sur votre ordinateur, puis conserver ce fichier en dehors du dépôt.

---

## Structure du projet

```
pc-telemetry-dashboard/
├── dashboard_pc.py        # Application Flask, API et interface web
├── requirements.txt       # Dépendances Python minimales
├── LICENSE                # Licence du projet
└── README.md              # Documentation
```

---

## Licence

Ce projet est distribué sous licence **MIT**. Consultez [`LICENSE`](LICENSE) pour le texte complet.

---

## Références

[1]: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor "LibreHardwareMonitor — dépôt officiel et capacités de monitoring"

[2]: https://flask.palletsprojects.com/en/stable/quickstart/ "Flask — Quickstart officiel et avertissements sur le serveur de développement"

*Dernière mise à jour : août 2026.*
