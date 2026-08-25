# 🐝 webeeblocks - Visual Drone Programming for Webots

> **We be blocks. Bee free !**  
> An open-source plugin to **program drones visually** using Blockly, **simulate** in Webots, 
> and **deploy** to real Crazyflie quadcopters. Let your code take flight!

[![GPLv3 License](https://img.shields.io/badge/License-GPL_v3-green.svg)](https://choosealicense.com/licenses/gpl-3.0/)
[![Python Version](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)](https://www.python.org/)
[![Webots Compatibility](https://img.shields.io/badge/Webots-2025a%2B-blue)](https://cyberbotics.com)

## Why "WebeeBlocks"?

- **🐝 Bee** : Hommage au bourdonnement caractéristique des Crazyflies  
- **🌐 Web** : Intégration native avec **Webots**  
- **🧱 Blocks** : Programmation visuelle par blocs Blockly  
- **🎮 We be** : "Nous sommes des blocs" - philosophie collaborative open source 

## ✨ Features

- **🧩 Blockly Interface**  
  Glissez-déposez des blocs pour contrôler drones virtuels et réels
- **⚡ Webots Plugin**  
  Simulation réaliste des drones dans des environnements 3D
- **🚀 Crazyflie Deployment**  
  Téléversement sans couture vers les drones physiques
- **🔓 100% Open Source**  
  Licence GPLv3 - Pas de lock-in, pas de services cloud

## Structure du projet
```markdown
crazyflie-blockly/
├── blockly/                  # Version stable de Blockly (pré-incluse)
│   ├── blockly_compressed.js
│   ├── blocks_compressed.js
│   └── python_compressed.js
├── blocks/                   # Blocs personnalisés Crazyflie
│   └── crazyflie.js
├── generators/               # Générateur de code Python
│   └── python.js
├── plugin/                   # Intégration Webots
│   ├── index.html
│   ├── icon.png              # Icône 64x64
│   └── webots_plugin.py      # Script d'intégration
├── install/                  # Dossier d'installation
│   ├── install.sh            # Pour Linux/macOS
│   └── README_WINDOWS.txt    # Instructions Windows
├── .gitmodules               # Configuration sous-module
└── README.md                 # Documentation principale
```
