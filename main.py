"""
=============================================================
  Générateur de sujets de Brevet Blanc – Technologie
  Collège Jacques Prévert – M. de PAZ
  Backend FastAPI – Déployé sur Railway
=============================================================
"""

import os, ftplib, io, subprocess, tempfile, datetime, json, re, asyncio
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="Générateur de Sujets – Technologie")

# ── CORS : autorise ton site à appeler ce backend ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Remplace * par l'URL de ton site si tu veux restreindre
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Variables d'environnement (à remplir dans Railway > Variables) ────────────
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
NOTION_API_KEY     = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
FTP_HOST           = os.environ.get("FTP_HOST", "")
FTP_USER           = os.environ.get("FTP_USER", "")
FTP_PASS           = os.environ.get("FTP_PASS", "")
FTP_REMOTE_PATH    = os.environ.get("FTP_REMOTE_PATH", "/sujets_generes/")
FTP_PUBLIC_URL     = os.environ.get("FTP_PUBLIC_URL", "")

# ── Rate limiting en mémoire : 3 générations max par IP par jour ─────────────
usage: dict = defaultdict(lambda: defaultdict(int))


# ─────────────────────────────────────────────────────────────────────────────
#  PROMPT SYSTÈME – instruit Gemini sur le format LaTeX attendu
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = r"""
Tu es un expert en pédagogie technologique au collège en France (niveaux 4ème et 5ème).
Tu génères des sujets COMPLETS de brevet blanc de TECHNOLOGIE entièrement codés en LaTeX.

STRUCTURE OBLIGATOIRE DU SUJET :
1. En-tête : "Technologie – 4ème" (ou 5ème) + "Collège Jacques Prévert – Monsieur de PAZ"
2. Titre principal centré (objet technique du sujet)
3. Sous-titre "Brevet Blanc – Épreuve de Technologie" + durée 45 min + 25 points
4. Champs élève : Nom / Prénom / Classe
5. Contexte introductif (3-5 lignes) sur l'objet technique
6. 4 Documents numérotés :
   - Document 1 : texte de présentation du système + schéma fonctionnel TikZ
   - Document 2 : tableau comparatif de matériaux (tabularx)
   - Document 3 : données numériques pour un calcul
   - Document 4 : algorigramme TikZ complet
7. 5 Questions avec barème visible (total = 25 pts)
8. Page DOCUMENT ANNEXE (à rendre avec la copie) avec espaces de réponse

CONTRAINTES LaTeX STRICTES :
- Packages requis : geometry, tabularx, tikz, tcolorbox, enumitem, amsmath, babel[french]
- usetikzlibrary{shapes.geometric, arrows.meta, positioning, calc, fit}
- Les schémas sont UNIQUEMENT en TikZ, jamais d'images externes
- Total barème = exactement 25 points
- Tout en français avec accents LaTeX corrects (\'{e}, \`{a}, etc.)
- \newpage entre le sujet, les questions et l'annexe

THÈMES POSSIBLES (changer à chaque génération) :
Robot aspirateur autonome, Fontaine connectée, Vélo électrique, Serrure connectée,
Lampadaire solaire intelligent, Serre automatisée, Trottinette électrique,
Purificateur d'air, Bras robotisé pédagogique, Porte automatique de collège,
Système d'irrigation intelligent, Voiture autonome miniature.

RÉPONDS UNIQUEMENT avec le code LaTeX complet.
Commence par \documentclass et termine par \end{document}.
Aucun texte avant ni après le code LaTeX.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  APPEL GEMINI
# ─────────────────────────────────────────────────────────────────────────────
async def call_gemini(theme_hint: str = "") -> str:
    """Appelle l'API Gemini et retourne le LaTeX généré."""
    user_message = (
        "Génère un sujet de brevet blanc de technologie complet en LaTeX."
        + (f" Thème : {theme_hint}." if theme_hint else " Choisis un thème parmi la liste.")
        + " Le code doit être directement compilable avec pdflatex sans erreur."
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-3.1-flash-lite:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_message}]}],
        "generationConfig": {
            "temperature": 0.75,
            "maxOutputTokens": 8192,
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code != 200:
        raise HTTPException(502, f"Erreur Gemini ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    try:
        raw = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise HTTPException(502, "Réponse Gemini inattendue.")

    # Nettoie les balises ```latex … ``` si Gemini les ajoute quand même
    raw = re.sub(r"^```(?:latex)?\s*\n?", "", raw.strip())
    raw = re.sub(r"\n?```\s*$", "", raw.strip())
    return raw.strip()


# ─────────────────────────────────────────────────────────────────────────────
#  COMPILATION LATEX → PDF
# ─────────────────────────────────────────────────────────────────────────────
def compile_latex(latex_code: str) -> bytes:
    """Compile le LaTeX avec pdflatex et retourne les octets du PDF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "sujet.tex")
        pdf_path = os.path.join(tmpdir, "sujet.pdf")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_code)

        # Deux passes pour résoudre les références internes
        log = ""
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, tex_path],
                capture_output=True, text=True, timeout=60
            )
            log = result.stdout

        if not os.path.exists(pdf_path):
            raise HTTPException(
                500,
                f"Échec de la compilation LaTeX.\n\nLog (fin) :\n{log[-2000:]}"
            )

        with open(pdf_path, "rb") as f:
            return f.read()


# ─────────────────────────────────────────────────────────────────────────────
#  UPLOAD FTP
# ─────────────────────────────────────────────────────────────────────────────
def upload_ftp(pdf_bytes: bytes, filename: str) -> str:
    """Envoie le PDF sur le FTP. Retourne l'URL publique ou chaîne vide."""
    if not FTP_HOST:
        return ""
    try:
        with ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASS) as ftp:
            ftp.cwd(FTP_REMOTE_PATH)
            ftp.storbinary(f"STOR {filename}", io.BytesIO(pdf_bytes))
        return f"{FTP_PUBLIC_URL.rstrip('/')}/{filename}"
    except Exception as e:
        print(f"[FTP] Erreur : {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  SAUVEGARDE NOTION
# ─────────────────────────────────────────────────────────────────────────────
async def save_to_notion(theme: str, filename: str, ftp_url: str, ip: str):
    """Crée une entrée dans la base Notion (colonnes à créer au préalable)."""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    properties = {
        "Nom du fichier": {
            "title": [{"text": {"content": filename}}]
        },
        "Thème": {
            "rich_text": [{"text": {"content": theme or "Aléatoire"}}]
        },
        "Date de génération": {
            "date": {"start": now.isoformat()}
        },
        "IP anonymisée": {
            "rich_text": [{"text": {"content": ip[:8] + "***"}}]
        },
        "URL FTP": {
            "url": ftp_url if ftp_url else None
        },
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {NOTION_API_KEY}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            },
            json={
                "parent": {"database_id": NOTION_DATABASE_ID},
                "properties": properties,
            }
        )
    if resp.status_code not in (200, 201):
        print(f"[Notion] Erreur {resp.status_code}: {resp.text[:300]}")


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "Générateur Sujets Techno",
        "college": "Collège Jacques Prévert"
    }


@app.post("/generer")
async def generer_sujet(request: Request):
    """
    Endpoint principal appelé par le widget sur le site.
    Body JSON optionnel : { "theme": "Robot aspirateur" }
    Retourne le PDF en téléchargement direct.
    """

    # 1. Rate limiting ─────────────────────────────────────────────────────
    client_ip = request.client.host
    today = datetime.date.today().isoformat()
    usage[today][client_ip] += 1
    if usage[today][client_ip] > 3:
        raise HTTPException(
            429,
            "Limite atteinte : 3 sujets par jour par adresse IP. Reviens demain !"
        )

    # 2. Lecture du thème optionnel ────────────────────────────────────────
    try:
        body = await request.json()
        theme = str(body.get("theme", "")).strip()[:80]
    except Exception:
        theme = ""

    # 3. Génération LaTeX via Gemini ───────────────────────────────────────
    latex_code = await call_gemini(theme)

    # 4. Compilation PDF ───────────────────────────────────────────────────
    pdf_bytes = compile_latex(latex_code)

    # 5. Nommage du fichier ────────────────────────────────────────────────
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_theme = re.sub(r"[^a-zA-Z0-9]", "_", theme)[:30] if theme else "aleatoire"
    filename = f"brevet_blanc_{safe_theme}_{ts}.pdf"

    # 6. Upload FTP (non bloquant) ─────────────────────────────────────────
    ftp_url = await asyncio.to_thread(upload_ftp, pdf_bytes, filename)

    # 7. Sauvegarde Notion (fire and forget) ───────────────────────────────
    asyncio.create_task(save_to_notion(theme or "Aléatoire", filename, ftp_url, client_ip))

    # 8. Retourne le PDF ───────────────────────────────────────────────────
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Generated-Theme": theme or "aleatoire",
        }
    )


@app.get("/latex")
async def obtenir_latex_brut(theme: str = ""):
    """Route de débogage : retourne le LaTeX brut sans compiler."""
    latex_code = await call_gemini(theme)
    return JSONResponse({"latex": latex_code, "longueur": len(latex_code)})
