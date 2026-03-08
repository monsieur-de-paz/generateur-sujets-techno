"""
=============================================================
  Générateur de sujets de Brevet Blanc – Technologie
  Collège Jacques Prévert – M. de PAZ
=============================================================
"""

import os, io, datetime, re, asyncio, logging
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

# ── Logging propre (visible dans tous les environnements) ─────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
log = logging.getLogger("generateur")

app = FastAPI(title="Générateur de Sujets – Technologie")

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Variables d'environnement ─────────────────────────────────────────────────
NOTION_API_KEY     = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")

# ── Rate limiting ─────────────────────────────────────────────────────────────
usage: dict = defaultdict(lambda: defaultdict(int))


# ─────────────────────────────────────────────────────────────────────────────
#  CSS DE BASE injecté dans chaque sujet généré
# ─────────────────────────────────────────────────────────────────────────────
BASE_CSS = """
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    color: #1a1a1a;
    background: #f0f2f5;
    padding: 20px;
  }

  .sujet-wrapper {
    max-width: 860px;
    margin: 0 auto;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 16px rgba(0,0,0,0.10);
    overflow: hidden;
  }

  .print-bar {
    background: #1a73e8;
    padding: 14px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .print-bar span { color: white; font-size: 14px; font-weight: 500; }
  .btn-print {
    background: white;
    color: #1a73e8;
    border: none;
    border-radius: 6px;
    padding: 10px 22px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: background 0.15s;
  }
  .btn-print:hover { background: #e8f0fe; }

  .sujet { padding: 32px 40px; }

  .entete-meta {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    color: #555;
    margin-bottom: 18px;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 10px;
  }
  .entete-titre { text-align: center; margin-bottom: 20px; }
  .entete-titre h1 { font-size: 24px; font-weight: 800; color: #0d1b2a; margin-bottom: 4px; }
  .entete-titre .sous-titre { font-size: 15px; color: #444; margin-bottom: 4px; }
  .entete-titre .duree { font-size: 14px; color: #666; }

  .champs-eleve {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 16px;
    margin: 18px 0 28px 0;
  }
  .champ { border-bottom: 1.5px solid #333; padding-bottom: 4px; font-size: 14px; color: #333; }

  .contexte {
    background: #f8f9fa;
    border-left: 4px solid #1a73e8;
    padding: 14px 18px;
    margin-bottom: 28px;
    border-radius: 0 6px 6px 0;
    font-size: 14px;
    line-height: 1.7;
  }

  .document { margin-bottom: 36px; }
  .document-titre {
    background: #0d1b2a;
    color: white;
    padding: 8px 16px;
    font-size: 15px;
    font-weight: 700;
    border-radius: 4px;
    margin-bottom: 14px;
  }
  .document-texte { font-size: 14px; line-height: 1.75; margin-bottom: 16px; color: #222; }

  table { width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 14px; }
  th { background: #0d1b2a; color: white; padding: 10px 12px; text-align: left; font-weight: 600; }
  td { padding: 9px 12px; border: 1px solid #ddd; }
  tr:nth-child(even) td { background: #f5f7fa; }
  .note-tableau { font-size: 13px; color: #555; margin-top: 10px; font-style: italic; }

  .formule {
    background: #f0f4ff;
    border: 1px solid #c5d3f0;
    border-radius: 6px;
    padding: 14px 18px;
    font-family: 'Courier New', monospace;
    font-size: 16px;
    text-align: center;
    margin: 14px 0;
    font-weight: 700;
    color: #1a3a6b;
  }
  .donnees-liste { list-style: none; padding: 0; margin: 10px 0; }
  .donnees-liste li { padding: 5px 0; font-size: 14px; border-bottom: 1px dotted #ddd; }
  .donnees-liste li:last-child { border-bottom: none; }

  .chaine {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0;
    justify-content: center;
    margin: 18px 0;
  }
  .chaine-bloc {
    background: #1a73e8;
    color: white;
    padding: 12px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    text-align: center;
    min-width: 110px;
    max-width: 150px;
    line-height: 1.3;
  }
  .chaine-bloc.energie { background: #e8762b; }
  .chaine-bloc.vide {
    background: white;
    border: 2px dashed #aaa;
    color: #999;
    font-style: italic;
  }
  .chaine-fleche { font-size: 22px; color: #555; padding: 0 6px; flex-shrink: 0; }
  .chaine-section { margin: 12px 0; }
  .chaine-section-titre {
    font-size: 12px;
    font-weight: 700;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }

  .algo {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    margin: 18px auto;
    max-width: 520px;
  }
  .algo-fleche { font-size: 20px; color: #555; line-height: 1; margin: 3px 0; }
  .algo-debut, .algo-fin {
    background: #0d1b2a;
    color: white;
    padding: 10px 30px;
    border-radius: 50px;
    font-weight: 700;
    font-size: 14px;
    text-align: center;
  }
  .algo-action {
    background: #e8f0fe;
    border: 2px solid #1a73e8;
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 13px;
    text-align: center;
    width: 100%;
    max-width: 380px;
  }
  .algo-condition {
    background: #fff8e1;
    border: 2px solid #f9a825;
    padding: 10px 20px;
    clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);
    font-size: 13px;
    font-weight: 600;
    text-align: center;
    width: 240px;
    height: 90px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 4px 0;
  }
  .algo-branche {
    display: flex;
    width: 100%;
    gap: 20px;
    justify-content: center;
    margin: 4px 0;
  }
  .algo-branche-oui, .algo-branche-non {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex: 1;
    max-width: 220px;
  }
  .algo-branche-label { font-size: 12px; font-weight: 700; color: #888; }

  .separateur-partie { border: none; border-top: 3px solid #0d1b2a; margin: 36px 0 24px 0; }
  .titre-partie {
    text-align: center;
    font-size: 20px;
    font-weight: 800;
    color: #0d1b2a;
    margin-bottom: 24px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .question { margin-bottom: 28px; }
  .question-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
  .question-titre { font-size: 15px; font-weight: 700; color: #0d1b2a; }
  .question-points { font-size: 13px; color: #555; font-style: italic; white-space: nowrap; }
  .question-enonce { font-size: 14px; color: #333; margin-bottom: 10px; line-height: 1.7; }
  .zone-reponse {
    border: 1.5px solid #bbb;
    border-radius: 6px;
    width: 100%;
    min-height: 80px;
    padding: 10px;
    font-family: inherit;
    font-size: 14px;
    resize: vertical;
    background: #fafafa;
    color: #222;
  }
  .zone-reponse:focus { outline: 2px solid #1a73e8; background: white; }
  .lignes-calcul { margin-top: 8px; }
  .ligne-calcul { border-bottom: 1px solid #ccc; margin-bottom: 22px; height: 1px; }

  .corrige {
    background: #fff8e1;
    border: 1.5px solid #f9a825;
    border-radius: 8px;
    padding: 18px 22px;
    margin-top: 10px;
  }
  .corrige-item { margin-bottom: 14px; font-size: 14px; line-height: 1.7; }
  .corrige-item strong { color: #0d1b2a; }

  @media (max-width: 600px) {
    body { padding: 0; background: white; }
    .sujet-wrapper { border-radius: 0; box-shadow: none; }
    .sujet { padding: 18px 16px; }
    .champs-eleve { grid-template-columns: 1fr; }
    .chaine { flex-direction: column; }
    .chaine-fleche { transform: rotate(90deg); }
    .print-bar { flex-direction: column; align-items: flex-start; }
    .entete-titre h1 { font-size: 18px; }
    .algo-condition { width: 180px; height: 75px; font-size: 12px; }
    .chaine-bloc { min-width: 90px; font-size: 12px; }
    table { font-size: 12px; }
    th, td { padding: 7px 8px; }
  }

  @media print {
    body { background: white; padding: 0; font-size: 11pt; }
    .sujet-wrapper { box-shadow: none; border-radius: 0; max-width: 100%; }
    .print-bar { display: none !important; }
    .sujet { padding: 0; }
    .page-break { page-break-before: always; }
    .no-break { page-break-inside: avoid; }
    @page { size: A4; margin: 1.8cm; }
    .chaine-bloc, .algo-debut, .algo-fin, th, .document-titre {
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .zone-reponse { border: 1px solid #888; background: white !important; min-height: 80px; }
    .corrige { border: 1px solid #ccc; background: #fffdf0 !important; }
  }
</style>

<script>
function imprimerSujet() { window.print(); }
</script>
"""


# ─────────────────────────────────────────────────────────────────────────────
#  PROMPT SYSTÈME
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
Tu es un expert en pédagogie technologique au collège en France (niveau 3ème).
Tu génères des sujets COMPLETS de brevet blanc de TECHNOLOGIE entièrement en HTML.

════════════════════════════════════════════════
RÈGLES ABSOLUES
════════════════════════════════════════════════

1. RÉPONDS UNIQUEMENT avec le contenu HTML intérieur.
   - Commence directement par <div class="print-bar">
   - Termine par la dernière </div> du corrigé
   - ZÉRO texte avant ou après
   - PAS de <!DOCTYPE>, <html>, <head>, <body>, <style> ni <script>

2. UTILISE UNIQUEMENT ces classes CSS déjà définies :
   print-bar, btn-print, sujet, entete-meta, entete-titre, sous-titre, duree,
   champs-eleve, champ, contexte, document, document-titre, document-texte,
   table/th/td, formule, donnees-liste, chaine, chaine-section, chaine-section-titre,
   chaine-bloc, chaine-bloc energie, chaine-bloc vide, chaine-fleche,
   algo, algo-debut, algo-fin, algo-action, algo-condition,
   algo-branche, algo-branche-oui, algo-branche-non, algo-branche-label, algo-fleche,
   separateur-partie, titre-partie, question, question-header, question-titre,
   question-points, question-enonce, zone-reponse, lignes-calcul, ligne-calcul,
   corrige, corrige-item, note-tableau, page-break, no-break

3. CHAÎNES FONCTIONNELLES avec .chaine et .chaine-bloc :
   - class="chaine-bloc" = chaîne d'information (bleu)
   - class="chaine-bloc energie" = chaîne d'énergie (orange)
   - class="chaine-bloc vide" = blocs à compléter (blanc pointillé)
   - class="chaine-fleche" contient le caractère →

4. ALGORIGRAMME avec .algo — minimum 7 étapes :
   Début → initialisation → lecture capteur → condition (losange) → branches OUI/NON → action finale → Fin
   Les branches utilisent .algo-branche contenant .algo-branche-oui et .algo-branche-non

5. ZONES DE RÉPONSE :
   - Réponse ouverte : <textarea class="zone-reponse" rows="5"></textarea>
   - Calcul : <div class="lignes-calcul"> + 4x <div class="ligne-calcul"></div> </div>

6. PAGE-BREAK entre chaque partie : <div class="page-break"></div>

════════════════════════════════════════════════
STRUCTURE OBLIGATOIRE
════════════════════════════════════════════════

<div class="print-bar">
  <span>Collège – Sujet généré par IA – Brevet Blanc Technologie</span>
  <button class="btn-print" onclick="imprimerSujet()">🖨️ Imprimer / Enregistrer PDF</button>
</div>

<div class="sujet">

  <div class="entete-meta">
    <span>Technologie – 3ème</span>
    <span>Collège – Sujet généré par IA</span>
  </div>
  <div class="entete-titre">
    <h1>[TITRE EN MAJUSCULES]</h1>
    <div class="sous-titre">Brevet Blanc – Épreuve de Technologie</div>
    <div class="duree">Durée : 30 minutes &nbsp;|&nbsp; 25 points</div>
  </div>
  <div class="champs-eleve">
    <div class="champ">Nom : ___________________________</div>
    <div class="champ">Prénom : ________________________</div>
    <div class="champ">Classe : ________________________</div>
  </div>

  <div class="contexte">[CONTEXTE 6-8 lignes très détaillées : système, utilité, composants réels nommés, contexte d'usage]</div>

  <div class="document no-break">
    <div class="document-titre">Document 1 – Chaîne fonctionnelle : [titre]</div>
    <div class="document-texte">[5-6 lignes de description précise avec composants réels nommés (ex: Arduino Uno, capteur DHT22, moteur DC L298N...)]</div>
    <div class="chaine-section">
      <div class="chaine-section-titre">Chaîne d'information</div>
      <div class="chaine">
        [4-5 blocs .chaine-bloc avec noms réels, séparés par .chaine-fleche →]
      </div>
    </div>
    <div class="chaine-section">
      <div class="chaine-section-titre">Chaîne d'énergie</div>
      <div class="chaine">
        [3-4 blocs .chaine-bloc.energie avec noms réels, séparés par .chaine-fleche →]
      </div>
    </div>
  </div>

  <div class="page-break"></div>

  <div class="document no-break">
    <div class="document-titre">Document 2 – [Titre tableau comparatif]</div>
    <div class="document-texte">[3-4 lignes contexte]</div>
    <table>
      <tr><th>[Col1]</th><th>[Col2]</th><th>[Col3]</th><th>[Col4]</th><th>[Col5]</th></tr>
      [4-5 lignes avec vraies valeurs numériques et unités]
    </table>
    <div class="note-tableau">[Note explicative 2-3 lignes]</div>
  </div>

  <div class="document no-break">
    <div class="document-titre">Document 3 – [Titre calcul]</div>
    <div class="document-texte">[Contexte 3-4 lignes]</div>
    <div class="formule">[FORMULE] avec [variables expliquées]</div>
    <ul class="donnees-liste">
      <li><strong>[Var]</strong> = [valeur] [unité] – [explication]</li>
      [3-4 variables]
    </ul>
    <div class="document-texte">[Question de calcul posée clairement]</div>
  </div>

  <div class="page-break"></div>

  <div class="document no-break">
    <div class="document-titre">Document 4 – Algorigramme : [titre]</div>
    <div class="document-texte">[3-4 lignes d'introduction]</div>
    <div class="algo">
      <div class="algo-debut">DÉBUT</div>
      <div class="algo-fleche">↓</div>
      <div class="algo-action">[Initialisation système]</div>
      <div class="algo-fleche">↓</div>
      <div class="algo-action">[Lecture capteur nommé réellement]</div>
      <div class="algo-fleche">↓</div>
      <div class="algo-condition">[Condition avec seuil chiffré]</div>
      <div class="algo-branche">
        <div class="algo-branche-oui">
          <div class="algo-branche-label">OUI</div>
          <div class="algo-action">[Action si vrai]</div>
          <div class="algo-fleche">↓</div>
          <div class="algo-action">[Action complémentaire]</div>
        </div>
        <div class="algo-branche-non">
          <div class="algo-branche-label">NON</div>
          <div class="algo-action">[Action si faux]</div>
          <div class="algo-fleche">↓</div>
          <div class="algo-action">[État veille]</div>
        </div>
      </div>
      <div class="algo-fleche">↓</div>
      <div class="algo-action">[Envoi données / affichage]</div>
      <div class="algo-fleche">↓</div>
      <div class="algo-fin">FIN</div>
    </div>
  </div>

  <div class="page-break"></div>

  <hr class="separateur-partie">
  <div class="titre-partie">Questions</div>

  [5 questions avec .question > .question-header + .question-enonce + zone-reponse ou lignes-calcul]
  [Total = exactement 25 points]

  <div class="page-break"></div>

  <hr class="separateur-partie">
  <div class="titre-partie">Corrigé et Barème – Réservé à l'enseignant</div>
  <div class="corrige">
    [5 .corrige-item avec réponse complète + barème détaillé]
  </div>

</div>

════════════════════════════════════════════════
TYPES D'EXERCICES (choisir 5 parmi)
════════════════════════════════════════════════

TYPE A – ANALYSE FONCTIONNELLE : compléter la chaîne avec liste de termes fournie
TYPE B – MATÉRIAUX : choisir depuis le tableau + justifier 3 critères → rows="7"
TYPE C – CALCUL NUMÉRIQUE : formule Document 3, lignes-calcul + réponse finale
TYPE D – ALGORIGRAMME : compléter les trous OU décrire en français → rows="6"
TYPE E – PSEUDO-CODE : compléter code incomplet dans un <pre> → rows="5"
TYPE F – DÉVELOPPEMENT DURABLE : cycle de vie / impact → rows="5"
TYPE G – LECTURE DE SCHÉMA : identifier composants et fonctions → rows="5"
TYPE H – AVANTAGES/INCONVÉNIENTS : 2 avantages + 1 limite justifiés → rows="6"

════════════════════════════════════════════════
CONTRAINTES FINALES
════════════════════════════════════════════════
- 25 points EXACTEMENT répartis sur 5 questions
- Niveau 3ème, français intégral
- Composants nommés avec références réelles (Arduino Uno, DHT22, HC-SR04, L298N, servo SG90...)
- Tableau : minimum 5 colonnes, 4 lignes, valeurs numériques réelles avec unités
- Algorigramme : minimum 7 étapes avec 2 branches OUI/NON
- Contexte très détaillé : 6-8 lignes

THÈMES (varier à chaque appel) :
Robot aspirateur, Fontaine connectée, Vélo électrique, Serrure connectée,
Lampadaire solaire intelligent, Serre automatisée, Trottinette électrique,
Purificateur d'air, Bras robotisé pédagogique, Porte automatique,
Système d'irrigation, Voiture autonome miniature, Pont-levis connecté,
Distributeur automatique de gel, Station météo connectée,
Ascenseur intelligent, Barrière de parking automatique, Drone de livraison.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  APPEL GROQCLOUD
# ─────────────────────────────────────────────────────────────────────────────
async def call_groq(theme_hint: str = "") -> str:
    user_message = (
        "Génère un sujet de brevet blanc de technologie complet en HTML."
        + (f" Thème imposé : {theme_hint}." if theme_hint else " Choisis un thème varié.")
        + " Respecte exactement les classes CSS fournies."
        + " Ne génère QUE le contenu HTML intérieur, sans DOCTYPE ni html ni head ni body ni style ni script."
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message}
                ],
                "temperature": 0.75,
                "max_tokens": 8192,
            }
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"Erreur Groq ({resp.status_code}): {resp.text[:500]}")

    raw = resp.json()["choices"][0]["message"]["content"]
    raw = re.sub(r"^```(?:html)?\s*\n?", "", raw.strip())
    raw = re.sub(r"\n?```\s*$", "", raw.strip())
    return raw.strip()


# ─────────────────────────────────────────────────────────────────────────────
#  ASSEMBLAGE HTML FINAL
# ─────────────────────────────────────────────────────────────────────────────
def assemble_html(contenu: str, theme: str = "") -> str:
    titre_page = f"Brevet Blanc – {theme}" if theme else "Brevet Blanc Technologie"
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{titre_page} – Collège</title>
  {BASE_CSS}
</head>
<body>
  <div class="sujet-wrapper">
    {contenu}
  </div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
#  SAUVEGARDE NOTION — upload du fichier HTML + page de base de données
# ─────────────────────────────────────────────────────────────────────────────

NOTION_HEADERS = lambda: {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28",
}


async def upload_html_file(filename: str, html_bytes: bytes, client: httpx.AsyncClient) -> str | None:
    """
    Tente d'uploader le fichier HTML via l'API Notion File Upload.
    Retourne l'URL publique du fichier si succès, None sinon.

    L'API Notion File Upload fonctionne en 2 étapes :
      1. POST /v1/files  →  obtenir un upload_url signé
      2. PUT upload_url  →  envoyer le fichier binaire
    """
    try:
        # ── Étape 1 : demander une URL d'upload signée ────────────────────────
        r1 = await client.post(
            "https://api.notion.com/v1/files",
            headers={**NOTION_HEADERS(), "Content-Type": "application/json"},
            json={
                "name": filename,
                "content_type": "text/html",
            },
            timeout=15.0,
        )
        log.info("[Notion Upload] Étape 1 — status %s", r1.status_code)

        if r1.status_code not in (200, 201):
            log.warning("[Notion Upload] Étape 1 échouée : %s", r1.text[:300])
            return None

        data1 = r1.json()
        upload_url  = data1.get("upload_url")
        file_id     = data1.get("id")

        if not upload_url or not file_id:
            log.warning("[Notion Upload] Réponse étape 1 inattendue : %s", data1)
            return None

        # ── Étape 2 : envoyer le fichier ──────────────────────────────────────
        r2 = await client.put(
            upload_url,
            content=html_bytes,
            headers={"Content-Type": "text/html"},
            timeout=30.0,
        )
        log.info("[Notion Upload] Étape 2 — status %s", r2.status_code)

        if r2.status_code not in (200, 201, 204):
            log.warning("[Notion Upload] Étape 2 échouée : %s", r2.text[:300])
            return None

        # L'URL publique est soit dans la réponse étape 2, soit dans étape 1
        file_url = r2.json().get("url") or data1.get("url") or f"notion://file/{file_id}"
        log.info("[Notion Upload] ✅ Fichier uploadé → %s", file_url)
        return file_url

    except Exception as e:
        log.error("[Notion Upload] Exception : %s", e)
        return None


async def save_to_notion(theme: str, ip: str, html_content: str):
    """
    1. Upload le fichier HTML dans Notion
    2. Crée une page dans la base de données avec le fichier attaché
    """
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        log.warning("[Notion] Variables manquantes — sauvegarde ignorée.")
        return

    now         = datetime.datetime.now(datetime.timezone.utc)
    ts          = now.strftime("%Y%m%d_%H%M%S")
    theme_clean = theme or "Aléatoire"
    slug        = re.sub(r"[^a-zA-Z0-9]", "_", theme_clean)[:30]
    nom_fichier = f"sujet_{slug}_{ts}.html"
    html_bytes  = html_content.encode("utf-8")

    async with httpx.AsyncClient(timeout=30.0) as client:

        # ── 1. Upload du fichier HTML ─────────────────────────────────────────
        file_url = await upload_html_file(nom_fichier, html_bytes, client)

        # ── 2. Construction des propriétés de la page ─────────────────────────
        # ⚠️  Ces noms doivent correspondre EXACTEMENT aux colonnes de ta base Notion
        properties = {
            "Nom du fichier": {
                "title": [{"text": {"content": nom_fichier}}]
            },
            "Thème": {
                "rich_text": [{"text": {"content": theme_clean}}]
            },
            "Date de génération": {
                "date": {"start": now.isoformat()}
            },
            "IP anonymisée": {
                "rich_text": [{"text": {"content": ip[:8] + "***"}}]
            },
        }

        # ── 3. Blocs de la page ───────────────────────────────────────────────
        children = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {
                        "content": f"📄 {nom_fichier}"
                    }}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {
                        "content": (
                            f"Thème : {theme_clean} | "
                            f"Généré le {now.strftime('%d/%m/%Y à %H:%M')} UTC"
                        )
                    }}]
                }
            },
            {"object": "block", "type": "divider", "divider": {}},
        ]

        # Bloc fichier si l'upload a réussi, sinon un lien de téléchargement data-URI
        if file_url and not file_url.startswith("notion://"):
            children.append({
                "object": "block",
                "type": "file",
                "file": {
                    "type": "external",
                    "external": {"url": file_url},
                    "name": nom_fichier,
                }
            })
            log.info("[Notion] Bloc fichier externe ajouté : %s", file_url)
        else:
            # Fallback : stocker le HTML en blocs code (max 2000 chars chacun)
            log.info("[Notion] Fallback — stockage HTML en blocs code.")
            CHUNK = 2000
            for chunk in [html_content[i:i+CHUNK] for i in range(0, len(html_content), CHUNK)][:80]:
                children.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}],
                        "language": "html",
                    }
                })

        # ── 4. Création de la page ────────────────────────────────────────────
        resp = await client.post(
            "https://api.notion.com/v1/pages",
            headers={**NOTION_HEADERS(), "Content-Type": "application/json"},
            json={
                "parent": {"database_id": NOTION_DATABASE_ID},
                "properties": properties,
                "children": children,
            },
            timeout=20.0,
        )

        if resp.status_code in (200, 201):
            page_url = resp.json().get("url", "N/A")
            log.info("[Notion] ✅ Page créée : %s", page_url)
        else:
            log.error("[Notion] ❌ Erreur %s : %s", resp.status_code, resp.text[:500])


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "ok", "service": "Générateur Sujets Techno – HTML", "college": "Collège Jacques Prévert"}


@app.get("/test-notion")
async def test_notion():
    """
    Diagnostic Notion — ouvre cette URL dans le navigateur pour voir ce qui cloche.
    Ex : https://generateur-sujets-techno-production.up.railway.app/test-notion
    """
    rapport = {
        "NOTION_API_KEY_present": bool(NOTION_API_KEY),
        "NOTION_DATABASE_ID_present": bool(NOTION_DATABASE_ID),
        "NOTION_API_KEY_debut": NOTION_API_KEY[:8] + "..." if NOTION_API_KEY else "—",
        "NOTION_DATABASE_ID": NOTION_DATABASE_ID or "—",
    }

    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        rapport["erreur"] = "Variables d'environnement manquantes sur Railway."
        return JSONResponse(rapport, status_code=500)

    # Test 1 : accès à la base de données
    async with httpx.AsyncClient(timeout=10.0) as client:
        r_db = await client.get(
            f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}",
            headers=NOTION_HEADERS(),
        )
    rapport["test_database_status"] = r_db.status_code
    if r_db.status_code == 200:
        db_data = r_db.json()
        rapport["database_title"] = db_data.get("title", [{}])[0].get("plain_text", "?")
        rapport["database_properties"] = list(db_data.get("properties", {}).keys())
    else:
        rapport["test_database_erreur"] = r_db.text[:400]

    # Test 2 : endpoint file upload disponible ?
    async with httpx.AsyncClient(timeout=10.0) as client:
        r_file = await client.post(
            "https://api.notion.com/v1/files",
            headers={**NOTION_HEADERS(), "Content-Type": "application/json"},
            json={"name": "test.html", "content_type": "text/html"},
        )
    rapport["test_file_upload_status"] = r_file.status_code
    rapport["test_file_upload_reponse"] = r_file.json() if r_file.headers.get("content-type", "").startswith("application/json") else r_file.text[:300]

    return JSONResponse(rapport)



@app.post("/generer")
async def generer_sujet_post(request: Request, background_tasks: BackgroundTasks):
    """POST /generer — Body JSON optionnel : { "theme": "Robot aspirateur" }"""
    client_ip = request.client.host
    today = datetime.date.today().isoformat()
    usage[today][client_ip] += 1
    if usage[today][client_ip] > 15:
        raise HTTPException(429, "Limite atteinte : 15 sujets par jour. Reviens demain !")

    try:
        body = await request.json()
        theme = str(body.get("theme", "")).strip()[:80]
    except Exception:
        theme = ""

    contenu_html = await call_groq(theme)
    page_html = assemble_html(contenu_html, theme)

    # Sauvegarde Notion en arrière-plan (n'impacte pas la réponse à l'élève)
    background_tasks.add_task(save_to_notion, theme or "Aléatoire", client_ip, page_html)

    return HTMLResponse(content=page_html, status_code=200)


@app.get("/generer")
async def generer_sujet_get(request: Request, background_tasks: BackgroundTasks, theme: str = ""):
    """GET /generer?theme=Vélo+électrique — pour test direct depuis le navigateur"""
    client_ip = request.client.host
    today = datetime.date.today().isoformat()
    usage[today][client_ip] += 1
    if usage[today][client_ip] > 10:
        raise HTTPException(429, "Limite atteinte.")

    contenu_html = await call_groq(theme)
    page_html = assemble_html(contenu_html, theme)

    background_tasks.add_task(save_to_notion, theme or "Aléatoire", client_ip, page_html)

    return HTMLResponse(content=page_html, status_code=200)
