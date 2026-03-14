"""
TechnoGen v2.0 — Backend FastAPI
Generateur de sujets de Brevet Blanc - Technologie
College Jacques Prevert - M. de PAZ
Deploye sur Railway
"""

import os, io, datetime, re, asyncio, logging, ftplib, random
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("technogen")

app = FastAPI(title="TechnoGen - Generateur de Sujets")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# -- Variables d'environnement -------------------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
FTP_HOST     = os.environ.get("FTP_HOST", "")
FTP_USER     = os.environ.get("FTP_USER", "")
FTP_PASSWORD = os.environ.get("FTP_PASSWORD", "")
FTP_PATH     = os.environ.get("FTP_PATH", "/www/generateur/sujets")
FTP_BASE_URL = os.environ.get("FTP_BASE_URL", "https://www.sandrodepaz.fr/generateur/sujets")

# -- Rate limiting en memoire --------------------------------------------------
usage: dict = defaultdict(lambda: defaultdict(int))

# -- Themes --------------------------------------------------------------------
THEMES = [
    "Robot aspirateur autonome", "Velo electrique", "Serrure connectee",
    "Lampadaire solaire intelligent", "Serre automatisee", "Trottinette electrique",
    "Purificateur d'air connecte", "Porte automatique", "Fontaine connectee",
    "Station meteo connectee", "Barriere de parking automatique", "Ascenseur intelligent",
    "Drone agricole", "Bras robotise pedagogique", "Serre agricole connectee",
    "Casier intelligent de college", "Systeme de recharge sans fil",
    "Banc public solaire connecte", "Detecteur de place de parking",
    "Piste cyclable chauffante", "Distributeur automatique de masques",
    "Tableau blanc interactif", "Borne de recharge pour velos electriques",
    "Systeme d'eclairage adaptatif de salle de classe",
    "Capteur de qualite de l'eau connecte", "Sac a dos connecte pour collegien",
    "Arroseur automatique solaire", "Passerelle pietonne intelligente",
    "Distributeur automatique de graines pour oiseaux",
    "Systeme anti-intrusion connecte", "Minuterie intelligente de douche",
    "Composteur automatique connecte", "Feu de signalisation adaptatif",
    "Casque de velo connecte",
]

# -- Types de questions --------------------------------------------------------
QUESTION_LABELS = {
    "A": "Analyse fonctionnelle",
    "B": "Choix de composant ou materiau",
    "C": "Calcul numerique",
    "D": "Lecture d'algorigramme",
    "E": "Pseudo-code",
    "F": "Developpement durable",
    "G": "Lecture de document technique",
    "H": "Avantages et inconvenients",
}

BAREMES = [
    [3, 4, 5, 6, 7], [4, 4, 5, 5, 7], [3, 5, 5, 5, 7],
    [4, 4, 4, 6, 7], [3, 3, 6, 6, 7], [2, 5, 5, 6, 7],
    [3, 4, 6, 6, 6], [4, 5, 5, 5, 6], [3, 4, 5, 5, 8],
    [2, 4, 6, 6, 7],
]

# -- CSS embarque -- Style LaTeX / Brevet authentique --------------------------
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,600;0,9..144,700;0,9..144,900;1,9..144,300;1,9..144,400&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Fraunces', Georgia, 'Times New Roman', serif;
  font-size: 11pt;
  line-height: 1.65;
  color: #1a1a1a;
  background: #dadada;
  padding: 24px;
}

.sujet-wrapper {
  max-width: 820px;
  margin: 0 auto;
  background: white;
  box-shadow: 0 1px 12px rgba(0,0,0,0.12);
}

/* -- BARRE D'IMPRESSION ---------------------------------------------------- */
.print-bar {
  background: #1a1a1a;
  padding: 12px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.print-bar span {
  color: #999;
  font-size: 11px;
  letter-spacing: 0.5px;
}
.btn-print {
  background: white;
  color: #333;
  border: none;
  border-radius: 3px;
  padding: 8px 20px;
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-print:hover { background: #eee; }

/* -- CONTENU DU SUJET ------------------------------------------------------ */
.sujet { padding: 44px 52px; }

/* -- EN-TETE --------------------------------------------------------------- */
.entete { text-align: center; margin-bottom: 28px; }
.entete-college {
  font-size: 10pt;
  font-weight: 400;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: #333;
}
.entete-hr { border: none; border-top: 2.5px solid #000; margin: 14px 0; }
.entete-hr-thin { border: none; border-top: 0.75px solid #000; margin: 10px 0; }
.entete-matiere { font-size: 11pt; font-weight: 400; margin: 6px 0; }
.entete-titre {
  font-size: 20pt;
  font-weight: 900;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin: 14px 0 4px;
}
.entete-sous-titre {
  font-size: 14pt;
  font-weight: 400;
  font-style: italic;
  margin: 4px 0 2px;
}
.entete-details {
  font-size: 10pt;
  margin-top: 6px;
  color: #333;
}

/* -- CHAMPS ELEVE ---------------------------------------------------------- */
.champs-eleve {
  display: flex;
  gap: 28px;
  margin: 24px 0;
  padding: 12px 0;
  border-top: 1px solid #000;
  border-bottom: 1px solid #000;
}
.champ {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex: 1;
  font-size: 10pt;
}
.champ-label { font-weight: 700; white-space: nowrap; }
.champ-ligne {
  flex: 1;
  border-bottom: 1px dotted #555;
  min-height: 1.1em;
}

/* -- THEME & CONTEXTE ------------------------------------------------------ */
.theme-titre {
  font-size: 14pt;
  font-weight: 700;
  text-align: center;
  margin: 20px 0 16px;
  font-style: italic;
}
.contexte {
  margin: 0 0 28px;
  text-align: justify;
  font-size: 10.5pt;
  line-height: 1.75;
}

/* -- DOCUMENTS ------------------------------------------------------------- */
.document {
  margin-bottom: 32px;
  page-break-inside: avoid;
}
.document-titre {
  font-size: 11.5pt;
  font-weight: 700;
  border-bottom: 1.5px solid #000;
  padding-bottom: 3px;
  margin-bottom: 10px;
}
.document-texte {
  font-size: 10.5pt;
  line-height: 1.7;
  text-align: justify;
  margin-bottom: 10px;
}

/* -- TABLEAUX -- style booktabs -------------------------------------------- */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
  font-size: 9.5pt;
}
th {
  padding: 8px 10px;
  text-align: left;
  font-weight: 700;
  background: none;
  color: #000;
  border-top: 2.5px solid #000;
  border-bottom: 1.2px solid #000;
}
td {
  padding: 6px 10px;
  border-bottom: 0.5px solid #bbb;
}
tbody tr:last-child td {
  border-bottom: 2.5px solid #000;
}
.note-tableau {
  font-size: 9pt;
  font-style: italic;
  color: #555;
  margin-top: 6px;
}

/* -- FORMULE --------------------------------------------------------------- */
.formule {
  text-align: center;
  margin: 18px auto;
  padding: 14px 24px;
  border-top: 1px solid #000;
  border-bottom: 1px solid #000;
  font-size: 13pt;
  font-style: italic;
  max-width: 520px;
}
.donnees-liste {
  list-style: none;
  padding: 0;
  margin: 12px 0 12px 8px;
  font-size: 10.5pt;
}
.donnees-liste li {
  padding: 3px 0;
  padding-left: 1.2em;
  text-indent: -1.2em;
}

/* -- CHAINE FONCTIONNELLE -------------------------------------------------- */
.chaine-section { margin: 14px 0; }
.chaine-section-titre {
  font-size: 9.5pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-bottom: 8px;
  text-align: center;
}
.chaine {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: center;
  margin: 8px 0;
  gap: 0;
}
.chaine-bloc {
  border: 1.5px solid #000;
  background: white;
  padding: 10px 12px;
  font-size: 8.5pt;
  font-weight: 600;
  text-align: center;
  min-width: 90px;
  max-width: 145px;
  line-height: 1.3;
}
.chaine-bloc.vide {
  border: 2px dashed #888;
  color: #aaa;
  font-style: italic;
  font-weight: 400;
}
.chaine-fleche {
  font-size: 20px;
  color: #000;
  padding: 0 5px;
  flex-shrink: 0;
}

/* -- ALGORIGRAMME ---------------------------------------------------------- */
.algo {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  margin: 16px auto;
  max-width: 480px;
}
.algo-fleche {
  font-size: 18px;
  color: #000;
  line-height: 1;
  margin: 3px 0;
}
.algo-debut, .algo-fin {
  border: 2px solid #000;
  background: white;
  padding: 8px 32px;
  border-radius: 50px;
  font-weight: 700;
  font-size: 10pt;
  text-align: center;
}
.algo-action {
  border: 1.5px solid #000;
  background: white;
  padding: 8px 16px;
  font-size: 9.5pt;
  text-align: center;
  width: 100%;
  max-width: 340px;
}
.algo-condition {
  border: 1.5px solid #000;
  background: white;
  padding: 10px 16px;
  transform: rotate(45deg);
  font-size: 8pt;
  font-weight: 600;
  text-align: center;
  width: 130px;
  height: 130px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 14px 0;
}
.algo-condition span {
  display: block;
  transform: rotate(-45deg);
  max-width: 120px;
  line-height: 1.3;
}
.algo-branche {
  display: flex;
  width: 100%;
  gap: 16px;
  justify-content: center;
  margin: 4px 0;
}
.algo-branche-oui, .algo-branche-non {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
  max-width: 200px;
}
.algo-branche-label {
  font-size: 9pt;
  font-weight: 700;
  text-transform: uppercase;
}

/* -- SEPARATEURS ----------------------------------------------------------- */
.page-break { page-break-before: always; }
.separateur-partie {
  border: none;
  border-top: 2.5px solid #000;
  margin: 28px 0 20px;
}
.titre-partie {
  text-align: center;
  font-size: 16pt;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 24px;
}

/* -- QUESTIONS ------------------------------------------------------------- */
.question {
  margin-bottom: 26px;
  page-break-inside: avoid;
}
.question-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 4px;
  border-bottom: 1px solid #000;
  padding-bottom: 3px;
}
.question-titre {
  font-size: 11pt;
  font-weight: 700;
}
.question-points {
  font-size: 10pt;
  font-style: italic;
  white-space: nowrap;
}
.question-type {
  font-size: 9pt;
  font-style: italic;
  color: #666;
  margin-bottom: 6px;
}
.question-enonce {
  font-size: 10.5pt;
  line-height: 1.7;
  margin-bottom: 10px;
  text-align: justify;
}
.zone-reponse {
  border: 1px solid #999;
  width: 100%;
  min-height: 80px;
  background: white;
}
.lignes-reponse { margin-top: 6px; }
.ligne {
  border-bottom: 0.5px solid #ccc;
  height: 28px;
  width: 100%;
}

/* -- CORRIGE --------------------------------------------------------------- */
.corrige {
  border: 2px solid #000;
  padding: 24px 28px;
  margin-top: 10px;
  page-break-before: always;
}
.corrige-titre {
  font-size: 12pt;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  text-align: center;
  margin-bottom: 18px;
  border-bottom: 1px solid #000;
  padding-bottom: 10px;
}
.corrige-item {
  margin-bottom: 14px;
  font-size: 10.5pt;
  line-height: 1.65;
}
.corrige-item strong { font-weight: 700; }

/* -- RESPONSIVE ------------------------------------------------------------ */
@media (max-width: 600px) {
  body { padding: 0; background: white; }
  .sujet-wrapper { box-shadow: none; }
  .sujet { padding: 20px 16px; }
  .champs-eleve { flex-direction: column; gap: 10px; }
  .chaine { flex-direction: column; }
  .chaine-fleche { transform: rotate(90deg); }
  .algo-condition { width: 110px; height: 110px; }
  .chaine-bloc { min-width: 80px; font-size: 8pt; }
  table { font-size: 8.5pt; }
  th, td { padding: 5px 6px; }
  .print-bar { flex-direction: column; gap: 8px; }
}

/* -- IMPRESSION ------------------------------------------------------------ */
@media print {
  body { background: white; padding: 0; font-size: 10.5pt; }
  .sujet-wrapper { box-shadow: none; max-width: 100%; }
  .print-bar { display: none !important; }
  .sujet { padding: 0; }
  .page-break { page-break-before: always; }
  .document, .question { page-break-inside: avoid; }
  @page { size: A4; margin: 1.8cm; }
  table, th {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .zone-reponse { border: 1px solid #888; min-height: 80px; }
  .corrige { border: 1.5px solid #000; }
}
"""

# -- Prompt systeme ------------------------------------------------------------
SYSTEM_PROMPT = (
    "Tu es un generateur expert de sujets de brevet blanc de technologie "
    "pour les eleves de 3eme au college en France. Tu produis des sujets "
    "realistes, varies et conformes au format officiel du DNB.\n\n"
    "==============================\n"
    "REGLE ABSOLUE - FORMAT DE SORTIE\n"
    "==============================\n\n"
    "- Reponds UNIQUEMENT avec du HTML brut.\n"
    "- Commence DIRECTEMENT par <div class=\"print-bar\">.\n"
    "- Termine par la DERNIERE </div> qui ferme le bloc .sujet.\n"
    "- ZERO texte, commentaire ou explication avant ou apres le HTML.\n"
    "- N'utilise JAMAIS : <!DOCTYPE>, <html>, <head>, <body>, <style>, <script>.\n"
    "- N'utilise JAMAIS d'attribut style=\"...\" (style inline).\n"
    "- Utilise EXCLUSIVEMENT les classes CSS listees ci-dessous. N'invente AUCUNE nouvelle classe.\n"
    "- N'utilise AUCUN emoji dans le contenu du sujet (seulement dans le bouton imprimer).\n\n"
    "==============================\n"
    "CLASSES CSS AUTORISEES\n"
    "==============================\n\n"
    "BARRE :        print-bar, btn-print\n"
    "SUJET :        sujet\n"
    "EN-TETE :      entete, entete-college, entete-hr, entete-hr-thin, "
    "entete-matiere, entete-titre, entete-sous-titre, entete-details\n"
    "ELEVE :        champs-eleve, champ, champ-label, champ-ligne\n"
    "THEME :        theme-titre\n"
    "CONTEXTE :     contexte\n"
    "DOCUMENT :     document, document-titre, document-texte\n"
    "TABLEAU :      note-tableau (+ balises table, thead, tbody, tr, th, td)\n"
    "FORMULE :      formule, donnees-liste (balise ul avec li)\n"
    "CHAINE :       chaine-section, chaine-section-titre, chaine, chaine-bloc, "
    "chaine-fleche (ajouter classe \"vide\" sur les blocs a completer)\n"
    "ALGORIGRAMME : algo, algo-debut, algo-fin, algo-action, algo-condition, "
    "algo-fleche, algo-branche, algo-branche-oui, algo-branche-non, algo-branche-label\n"
    "SEPARATION :   page-break, separateur-partie (balise hr), titre-partie\n"
    "QUESTIONS :    question, question-header, question-titre, question-points, "
    "question-type, question-enonce, zone-reponse, lignes-reponse, ligne\n"
    "CORRIGE :      corrige, corrige-titre, corrige-item\n\n"
    "==============================\n"
    "STRUCTURE HTML A SUIVRE - PAS DE DEVIATION\n"
    "==============================\n\n"
    "<div class=\"print-bar\">\n"
    "  <span>College Jacques Prevert - M. de PAZ - Brevet Blanc Technologie</span>\n"
    "  <button class=\"btn-print\" onclick=\"imprimerSujet()\">Imprimer / Enregistrer PDF</button>\n"
    "</div>\n\n"
    "<div class=\"sujet\">\n\n"
    "  <div class=\"entete\">\n"
    "    <p class=\"entete-college\">College Jacques Prevert - Saint-Genis-Pouilly</p>\n"
    "    <hr class=\"entete-hr\">\n"
    "    <p class=\"entete-matiere\">Technologie - Classe de 3<sup>eme</sup></p>\n"
    "    <h1 class=\"entete-titre\">Brevet Blanc - Epreuve de Technologie</h1>\n"
    "    <p class=\"entete-sous-titre\">[NOM DU THEME]</p>\n"
    "    <hr class=\"entete-hr-thin\">\n"
    "    <p class=\"entete-details\">Duree : 30 minutes - Bareme : 25 points - Calculatrice autorisee</p>\n"
    "  </div>\n\n"
    "  <div class=\"champs-eleve\">\n"
    "    <div class=\"champ\"><span class=\"champ-label\">Nom :</span>"
    "<span class=\"champ-ligne\"></span></div>\n"
    "    <div class=\"champ\"><span class=\"champ-label\">Prenom :</span>"
    "<span class=\"champ-ligne\"></span></div>\n"
    "    <div class=\"champ\"><span class=\"champ-label\">Classe :</span>"
    "<span class=\"champ-ligne\"></span></div>\n"
    "  </div>\n\n"
    "  <div class=\"contexte\">\n"
    "    <p>[Paragraphe introductif de 4 a 6 lignes]</p>\n"
    "  </div>\n\n"
    "  [DOCUMENT 1]\n"
    "  [DOCUMENT 2]\n"
    "  [DOCUMENT 3]\n"
    "  [DOCUMENT 4]\n\n"
    "  <div class=\"page-break\"></div>\n"
    "  <hr class=\"separateur-partie\">\n"
    "  <h2 class=\"titre-partie\">Questions</h2>\n\n"
    "  [5 QUESTIONS]\n\n"
    "  <div class=\"page-break\"></div>\n"
    "  <div class=\"corrige\">\n"
    "    <h2 class=\"corrige-titre\">Corrige et bareme - Reserve a l'enseignant</h2>\n"
    "    [CORRECTIONS DES 5 QUESTIONS]\n"
    "  </div>\n\n"
    "</div>\n\n"
    "==============================\n"
    "DOCUMENT 1 - CHAINE FONCTIONNELLE\n"
    "==============================\n\n"
    "<div class=\"document\">\n"
    "  <h3 class=\"document-titre\">Document 1 - Chaine fonctionnelle : [description]</h3>\n"
    "  <p class=\"document-texte\">[2-3 lignes de description technique]</p>\n"
    "  <div class=\"chaine-section\">\n"
    "    <div class=\"chaine-section-titre\">Chaine d'information</div>\n"
    "    <div class=\"chaine\">\n"
    "      <div class=\"chaine-bloc\">[Capteur reel avec reference]</div>\n"
    "      <div class=\"chaine-fleche\">&#8594;</div>\n"
    "      <div class=\"chaine-bloc\">[Traitement : microcontroleur]</div>\n"
    "      <div class=\"chaine-fleche\">&#8594;</div>\n"
    "      <div class=\"chaine-bloc\">[Communication / Interface]</div>\n"
    "    </div>\n"
    "  </div>\n"
    "  <div class=\"chaine-section\">\n"
    "    <div class=\"chaine-section-titre\">Chaine d'energie</div>\n"
    "    <div class=\"chaine\">\n"
    "      <div class=\"chaine-bloc\">[Source d'energie]</div>\n"
    "      <div class=\"chaine-fleche\">&#8594;</div>\n"
    "      <div class=\"chaine-bloc\">[Distribution]</div>\n"
    "      <div class=\"chaine-fleche\">&#8594;</div>\n"
    "      <div class=\"chaine-bloc\">[Conversion]</div>\n"
    "      <div class=\"chaine-fleche\">&#8594;</div>\n"
    "      <div class=\"chaine-bloc\">[Action mecanique]</div>\n"
    "    </div>\n"
    "  </div>\n"
    "</div>\n\n"
    "Composants reels a utiliser (VARIE d'un sujet a l'autre) :\n"
    "- Microcontroleurs : Arduino Uno, Arduino Nano, ESP32, Raspberry Pi Pico, STM32, Micro:bit\n"
    "- Capteurs : DHT22, DHT11, HC-SR04, BMP280, MPU6050, MQ-135, LDR, capteur PIR HC-SR501, "
    "KY-018, TCS3200, VL53L0X, ACS712\n"
    "- Actionneurs : servo SG90, servo MG996R, moteur DC, moteur pas-a-pas NEMA17, "
    "pompe peristaltique 12V, verin electrique, ventilateur 5V\n"
    "- Drivers : L298N, ULN2803, DRV8825, module relais 5V, MOSFET IRF520\n\n"
    "==============================\n"
    "DOCUMENT 2 - TABLEAU COMPARATIF\n"
    "==============================\n\n"
    "<div class=\"document\">\n"
    "  <h3 class=\"document-titre\">Document 2 - [Titre descriptif du tableau]</h3>\n"
    "  <p class=\"document-texte\">[1-2 lignes d'introduction]</p>\n"
    "  <table>\n"
    "    <thead><tr><th>[Col 1]</th><th>[Col 2]</th><th>[Col 3]</th>"
    "<th>[Col 4]</th><th>[Col 5]</th></tr></thead>\n"
    "    <tbody>\n"
    "      <tr><td>...</td><td>...</td><td>...</td><td>...</td><td>...</td></tr>\n"
    "      [MINIMUM 4 lignes de donnees avec des valeurs numeriques realistes et des unites]\n"
    "    </tbody>\n"
    "  </table>\n"
    "  <p class=\"note-tableau\">[Note explicative en italique]</p>\n"
    "</div>\n\n"
    "Le tableau DOIT contenir au minimum 5 colonnes et 4 lignes de donnees.\n"
    "Toutes les valeurs numeriques doivent etre realistes, avec des unites SI.\n\n"
    "==============================\n"
    "DOCUMENT 3 - FORMULE DE CALCUL\n"
    "==============================\n\n"
    "<div class=\"document\">\n"
    "  <h3 class=\"document-titre\">Document 3 - [Titre : Calcul de ...]</h3>\n"
    "  <p class=\"document-texte\">[Explication de la grandeur a calculer]</p>\n"
    "  <div class=\"formule\">[Formule : P = U x I   ou   E = P x t   etc.]</div>\n"
    "  <ul class=\"donnees-liste\">\n"
    "    <li>[Grandeur 1] = [valeur] [unite] - [description]</li>\n"
    "    <li>[Grandeur 2] = [valeur] [unite] - [description]</li>\n"
    "    <li>[Grandeur 3] = [valeur] [unite] - [description]</li>\n"
    "    <li>[Resultat] = ? [unite] - [a calculer]</li>\n"
    "  </ul>\n"
    "</div>\n\n"
    "Formules a utiliser (VARIE) : P = U x I, E = P x t, v = d / t, "
    "eta = Ps / Pe, C = E x prix_kWh, F = m x g, etc.\n\n"
    "==============================\n"
    "DOCUMENT 4 - ALGORIGRAMME\n"
    "==============================\n\n"
    "<div class=\"document\">\n"
    "  <h3 class=\"document-titre\">Document 4 - Algorigramme : [description]</h3>\n"
    "  <p class=\"document-texte\">[Description en 2-3 lignes]</p>\n"
    "  <div class=\"algo\">\n"
    "    <div class=\"algo-debut\">DEBUT</div>\n"
    "    <div class=\"algo-fleche\">&#8595;</div>\n"
    "    <div class=\"algo-action\">[Etape initiale]</div>\n"
    "    <div class=\"algo-fleche\">&#8595;</div>\n"
    "    <div class=\"algo-condition\"><span>[Condition ?]</span></div>\n"
    "    <div class=\"algo-branche\">\n"
    "      <div class=\"algo-branche-oui\">\n"
    "        <div class=\"algo-branche-label\">OUI</div>\n"
    "        <div class=\"algo-action\">[Action si oui]</div>\n"
    "      </div>\n"
    "      <div class=\"algo-branche-non\">\n"
    "        <div class=\"algo-branche-label\">NON</div>\n"
    "        <div class=\"algo-action\">[Action si non]</div>\n"
    "      </div>\n"
    "    </div>\n"
    "    <div class=\"algo-fleche\">&#8595;</div>\n"
    "    [... au moins 7 etapes au total, avec 2 conditions minimum ...]\n"
    "    <div class=\"algo-fin\">FIN</div>\n"
    "  </div>\n"
    "</div>\n\n"
    "IMPORTANT pour les losanges de condition : la classe .algo-condition utilise transform:rotate(45deg).\n"
    "Tu DOIS mettre le texte dans un <span> : <div class=\"algo-condition\"><span>Texte ?</span></div>\n"
    "Le texte de la condition doit etre COURT (max 6 mots).\n\n"
    "==============================\n"
    "QUESTIONS\n"
    "==============================\n\n"
    "Format d'une question :\n"
    "<div class=\"question\">\n"
    "  <div class=\"question-header\">\n"
    "    <span class=\"question-titre\">Question N</span>\n"
    "    <span class=\"question-points\">/ X points</span>\n"
    "  </div>\n"
    "  <p class=\"question-type\">[Type de question]</p>\n"
    "  <p class=\"question-enonce\">[Enonce detaille et precis. "
    "Fais reference au document concerne.]</p>\n"
    "  <div class=\"zone-reponse\"></div>\n"
    "</div>\n\n"
    "Pour le TYPE A (analyse fonctionnelle), la zone de reponse peut inclure "
    "une chaine avec des blocs vides :\n"
    "<div class=\"chaine\">\n"
    "  <div class=\"chaine-bloc vide\">?</div>\n"
    "  <div class=\"chaine-fleche\">&#8594;</div>\n"
    "  <div class=\"chaine-bloc\">[Composant donne]</div>\n"
    "  <div class=\"chaine-fleche\">&#8594;</div>\n"
    "  <div class=\"chaine-bloc vide\">?</div>\n"
    "</div>\n\n"
    "Pour le TYPE C (calcul), ajoute des lignes de reponse :\n"
    "<div class=\"lignes-reponse\">\n"
    "  <div class=\"ligne\"></div><div class=\"ligne\"></div>"
    "<div class=\"ligne\"></div><div class=\"ligne\"></div>\n"
    "</div>\n\n"
    "Le TOTAL des points DOIT faire EXACTEMENT 25.\n\n"
    "==============================\n"
    "CORRIGE\n"
    "==============================\n\n"
    "<div class=\"corrige\">\n"
    "  <h2 class=\"corrige-titre\">Corrige et bareme - Reserve a l'enseignant</h2>\n"
    "  <div class=\"corrige-item\"><strong>Question 1 (X pts) :</strong> "
    "[Reponse complete avec bareme decompose]</div>\n"
    "  ... pour chaque question ...\n"
    "</div>\n\n"
    "Le corrige DOIT contenir pour chaque question :\n"
    "- La reponse complete et detaillee\n"
    "- Le bareme decompose\n"
    "- Pour les calculs : toutes les etapes avec le resultat final et l'unite\n\n"
    "==============================\n"
    "REGLES DE VARIETE (CRITIQUE)\n"
    "==============================\n\n"
    "1. Les TYPES de questions te seront imposes dans le message utilisateur. Respecte-les.\n"
    "2. Le BAREME par question te sera impose. Respecte-le exactement.\n"
    "3. VARIE les composants techniques : n'utilise pas toujours Arduino Uno et HC-SR04.\n"
    "4. VARIE la structure de l'algorigramme.\n"
    "5. VARIE les formules de calcul.\n"
    "6. VARIE les contenus des tableaux comparatifs.\n"
    "7. Le contexte introductif doit etre UNIQUE et specifique au theme.\n"
    "8. Les donnees numeriques doivent etre REALISTES et VARIEES.\n\n"
    "==============================\n"
    "INTERDICTIONS\n"
    "==============================\n\n"
    "- AUCUN attribut style inline\n"
    "- AUCUNE classe CSS non listee ci-dessus\n"
    "- AUCUNE balise <img>, <svg>, <canvas>, <iframe>\n"
    "- AUCUN JavaScript\n"
    "- AUCUN commentaire HTML\n"
    "- AUCUN emoji (sauf bouton imprimer)\n"
    "- AUCUN texte en dehors des balises HTML\n"
    "- AUCUN bloc de code markdown (pas de ```)\n"
    "- NE REPETE PAS le mot Document dans les titres de question "
    "(dis \"En vous appuyant sur le document 2\" dans l'enonce)\n"
)

# -- Descriptions des types de questions pour le message utilisateur -----------
QUESTION_DESCRIPTIONS = {
    "A": (
        "TYPE A - Analyse fonctionnelle : completer ou analyser la chaine "
        "fonctionnelle du Document 1. Inclure une chaine avec des blocs "
        "vides (.chaine-bloc.vide) dans la zone de reponse."
    ),
    "B": (
        "TYPE B - Choix de composant/materiau : choisir un element dans le "
        "tableau du Document 2 en justifiant avec au moins 3 criteres techniques."
    ),
    "C": (
        "TYPE C - Calcul numerique : appliquer la formule du Document 3 pour "
        "effectuer un calcul. Montrer toutes les etapes. Inclure des lignes de reponse."
    ),
    "D": (
        "TYPE D - Lecture d'algorigramme : completer les cases vides de "
        "l'algorigramme du Document 4 ou decrire son fonctionnement en francais."
    ),
    "E": (
        "TYPE E - Pseudo-code : ecrire ou completer un petit programme en "
        "pseudo-code lie au fonctionnement du systeme."
    ),
    "F": (
        "TYPE F - Developpement durable : analyser l'impact environnemental, "
        "le cycle de vie ou la consommation energetique du systeme."
    ),
    "G": (
        "TYPE G - Lecture de document : identifier des composants, fonctions "
        "ou caracteristiques a partir des documents fournis."
    ),
    "H": (
        "TYPE H - Avantages/inconvenients : presenter 2 avantages et 1 limite "
        "du systeme, chacun justifie en 1-2 phrases."
    ),
}


# -- Appel API Groq ------------------------------------------------------------
async def call_groq(theme: str, question_types: list, bareme: list) -> str:
    """Appelle l'API Groq avec LLaMA 3.3 70B et retourne le HTML genere."""
    types_detail = "\n".join(
        f"  Question {i+1} ({bareme[i]} points) : {QUESTION_DESCRIPTIONS[t]}"
        for i, t in enumerate(question_types)
    )

    user_message = (
        f"Genere un sujet de brevet blanc de technologie complet "
        f"sur le theme : {theme}.\n\n"
        f"QUESTIONS IMPOSEES (respecte cet ordre et ce bareme EXACTEMENT) :\n"
        f"{types_detail}\n\n"
        f"Total : {sum(bareme)} points.\n\n"
        f"Rappel : commence directement par <div class=\"print-bar\"> "
        f"et utilise uniquement les classes CSS autorisees."
    )

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.78,
        "max_tokens": 8192,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        logger.error(f"Groq error {resp.status_code}: {resp.text[:500]}")
        raise HTTPException(502, f"Erreur Groq ({resp.status_code})")

    data = resp.json()
    try:
        raw = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise HTTPException(502, "Reponse Groq inattendue.")

    # Nettoyage des backticks markdown
    raw = re.sub(r"^```(?:html)?\s*\n?", "", raw.strip())
    raw = re.sub(r"\n?```\s*$", "", raw.strip())
    return raw.strip()


# -- Assemblage du HTML final --------------------------------------------------
def assemble_html(theme: str, content: str) -> str:
    return (
        '<!DOCTYPE html>\n<html lang="fr">\n<head>\n'
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '  <link href="https://fonts.googleapis.com/css2?family=Fraunces:'
        'ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,600;0,9..144,700;'
        '0,9..144,900;1,9..144,300;1,9..144,400&display=swap" rel="stylesheet">\n'
        f'  <title>Brevet Blanc - {theme} - College Jacques Prevert</title>\n'
        f'  <style>{BASE_CSS}</style>\n'
        '  <script>function imprimerSujet(){ window.print(); }</script>\n'
        '</head>\n<body>\n'
        '<div class="sujet-wrapper">\n'
        f'{content}\n'
        '</div>\n'
        '</body>\n</html>'
    )


# -- FTP Upload ----------------------------------------------------------------
def ftp_upload(filename: str, html_bytes: bytes):
    """Upload un fichier HTML sur le FTP OVH. Retourne l'URL publique ou None."""
    if not FTP_HOST:
        return None
    try:
        with ftplib.FTP(FTP_HOST, timeout=20) as ftp:
            ftp.login(FTP_USER, FTP_PASSWORD)
            try:
                ftp.mkd(FTP_PATH)
            except ftplib.error_perm:
                pass
            ftp.cwd(FTP_PATH)
            ftp.storbinary(f"STOR {filename}", io.BytesIO(html_bytes))
        url = f"{FTP_BASE_URL.rstrip('/')}/{filename}"
        logger.info(f"FTP upload OK: {url}")
        return url
    except Exception as e:
        logger.error(f"FTP upload failed: {e}")
        return None


# -- FTP Listing ---------------------------------------------------------------
def ftp_list_files() -> list:
    """Liste les fichiers HTML sur le FTP et retourne les metadonnees."""
    if not FTP_HOST:
        return []
    try:
        with ftplib.FTP(FTP_HOST, timeout=15) as ftp:
            ftp.login(FTP_USER, FTP_PASSWORD)
            ftp.cwd(FTP_PATH)
            lines = []
            ftp.retrlines("LIST", lines.append)

        sujets = []
        for line in lines:
            parts = line.split()
            if not parts:
                continue
            fname = parts[-1]
            if not fname.endswith(".html"):
                continue
            m = re.match(r"sujet_(.+?)_(\d{8})_(\d{6})\.html$", fname)
            if m:
                theme_raw = m.group(1).replace("_", " ")
                date_str = m.group(2)
                time_str = m.group(3)
                try:
                    dt = datetime.datetime.strptime(
                        date_str + time_str, "%Y%m%d%H%M%S"
                    )
                    date_display = dt.strftime("%d/%m/%Y %H:%M")
                except ValueError:
                    date_display = date_str
                sujets.append({
                    "filename": fname,
                    "url": f"{FTP_BASE_URL.rstrip('/')}/{fname}",
                    "theme": theme_raw,
                    "date": date_display,
                    "_sort": date_str + time_str,
                })
        sujets.sort(key=lambda s: s.get("_sort", "0"), reverse=True)
        for s in sujets:
            s.pop("_sort", None)
        return sujets
    except Exception as e:
        logger.error(f"FTP list failed: {e}")
        return []


# -- Background task pour l'upload FTP -----------------------------------------
def background_ftp_upload(filename: str, html_bytes: bytes):
    """Execute en background apres l'envoi de la reponse HTTP."""
    ftp_upload(filename, html_bytes)


# -- Routes --------------------------------------------------------------------

@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "TechnoGen v2.0",
        "college": "College Jacques Prevert",
    }


@app.post("/generer")
async def generer_sujet_post(request: Request, background_tasks: BackgroundTasks):
    """Route principale : genere un sujet HTML complet."""
    # Rate limiting
    client_ip = request.client.host
    today = datetime.date.today().isoformat()
    usage[today][client_ip] += 1
    if usage[today][client_ip] > 15:
        raise HTTPException(
            429, "Limite atteinte : 15 sujets par jour. Reviens demain !"
        )

    # Lecture du theme optionnel
    try:
        body = await request.json()
        theme = str(body.get("theme", "")).strip()[:80]
    except Exception:
        theme = ""

    if not theme:
        theme = random.choice(THEMES)

    # Selection aleatoire des types de questions et du bareme
    selected_types = random.sample(list(QUESTION_LABELS.keys()), 5)
    bareme = random.choice(BAREMES)[:]
    random.shuffle(bareme)

    # Generation via Groq
    content = await call_groq(theme, selected_types, bareme)

    # Assemblage HTML final
    html = assemble_html(theme, content)

    # Nommage du fichier
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-zA-Z0-9]", "_", theme)[:30]
    filename = f"sujet_{slug}_{ts}.html"

    # Upload FTP en arriere-plan
    html_bytes = html.encode("utf-8")
    background_tasks.add_task(background_ftp_upload, filename, html_bytes)

    return HTMLResponse(content=html)


@app.get("/generer")
async def generer_sujet_get(
    request: Request, background_tasks: BackgroundTasks, theme: str = ""
):
    """Route GET pour test direct depuis le navigateur."""
    client_ip = request.client.host
    today = datetime.date.today().isoformat()
    usage[today][client_ip] += 1
    if usage[today][client_ip] > 10:
        raise HTTPException(429, "Limite atteinte.")

    if not theme:
        theme = random.choice(THEMES)

    selected_types = random.sample(list(QUESTION_LABELS.keys()), 5)
    bareme = random.choice(BAREMES)[:]
    random.shuffle(bareme)

    content = await call_groq(theme, selected_types, bareme)
    html = assemble_html(theme, content)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-zA-Z0-9]", "_", theme)[:30]
    filename = f"sujet_{slug}_{ts}.html"

    html_bytes = html.encode("utf-8")
    background_tasks.add_task(background_ftp_upload, filename, html_bytes)

    return HTMLResponse(content=html)


@app.get("/sujets")
async def lister_sujets(request: Request):
    """Liste les sujets disponibles sur le FTP."""
    sujets = await asyncio.to_thread(ftp_list_files)
    return JSONResponse({
        "sujets": sujets,
        "total": len(sujets),
    })


@app.get("/test-ftp")
async def test_ftp(request: Request):
    """Diagnostic de la connexion FTP."""
    client_ip = request.client.host
    today = datetime.date.today().isoformat()
    usage[today][client_ip] += 1
    if usage[today][client_ip] > 10:
        raise HTTPException(429, "Limite atteinte.")

    if not FTP_HOST:
        return JSONResponse({
            "status": "skip",
            "message": "FTP non configure (FTP_HOST vide)",
        })

    try:
        with ftplib.FTP(FTP_HOST, timeout=15) as ftp:
            ftp.login(FTP_USER, FTP_PASSWORD)
            root = ftp.pwd()
            ftp.cwd(FTP_PATH)
            current = ftp.pwd()
            files = ftp.nlst()
        return JSONResponse({
            "status": "ok",
            "host": FTP_HOST,
            "repertoire_racine": root,
            "repertoire_sujets": current,
            "fichiers": files[:20],
        })
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": str(e)}, status_code=500
        )
