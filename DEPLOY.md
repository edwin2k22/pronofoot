# Deploiement public de PronoFoot

Objectif : obtenir une URL publique que tes amis peuvent ouvrir, sans dependre de
`localhost` ni d'un run local Codex.

## Option recommandee : 100% gratuit, statique

Cette option ne demande aucune cle API payante et aucun serveur qui tourne chez toi.

1. Mets le projet dans un repo GitHub.
2. Active GitHub Pages, Cloudflare Pages ou Vercel sur la branche `main`.
3. Dans GitHub, ouvre `Actions` puis lance manuellement le workflow
   `Free Static Refresh` une premiere fois.
4. Le workflow relance ensuite `python -m collector.refresh` toutes les 30 minutes,
   regenere `index.html` / `scouting.html`, puis commit les fichiers statiques.
5. Partage l'URL publique fournie par l'hebergeur statique.

Controle anti-payant :

```bash
python -m collector.sources.free_sources --audit
```

Le workflow execute aussi cet audit. Si une future modif ajoute une dependance a
cle payante type API-Football, Sportmonks, RapidAPI ou The Odds API, le refresh
echoue au lieu de publier une app qui ne respecte plus le mode gratuit.

Limite honnete : GitHub Actions planifie le refresh, mais ne garantit pas la
seconde exacte. Pour un live ultra-fin, un fournisseur payant ou un serveur dedie
reste meilleur; pour une app partageable gratuitement, c'est le meilleur compromis.

## Ce qui est pret

- `Dockerfile` : construit l'app dans une image Python portable.
- `deploy/start-public.sh` : lance le serveur web et, si active, le scheduler live.
- `collector.server` lit maintenant `PORT`, la variable standard fournie par les hebergeurs.
- `PRONOFOOT_READONLY=1` est le mode par defaut pour Internet : les endpoints admin
  (`refresh`, `sync`, `setscore`, `predict`) sont bloques.

## Test local avec Docker

```bash
docker build -t pronofoot .
docker run --rm -p 8077:8077 \
  -e PORT=8077 \
  -e PRONOFOOT_READONLY=1 \
  pronofoot
```

Puis ouvre :

```text
http://localhost:8077/index.html
```

## Variables utiles

| Variable | Defaut | Role |
| --- | --- | --- |
| `PORT` | `8077` | Port HTTP. Les hebergeurs le definissent souvent eux-memes. |
| `PRONOFOOT_READONLY` | `1` | Bloque les actions admin sur le site public. Garde `1` pour tes amis. |
| `PRONOFOOT_ENABLE_SCHEDULER` | `1` | Lance le scheduler live dans le container. |
| `LIVE_POLL` | `30` | Frequence de poll pendant un match live. |
| `PRONOFOOT_REFRESH_ON_START` | `0` | Lance un refresh complet au demarrage. Laisse `0` pour demarrer vite. |

## Option serveur : Render ou Railway

1. Mets le projet dans un repo GitHub.
2. Cree un nouveau Web Service depuis ce repo.
3. Choisis le deploiement Docker si la plateforme le demande.
4. Ajoute ou verifie ces variables :

```text
PRONOFOOT_READONLY=1
PRONOFOOT_ENABLE_SCHEDULER=1
PRONOFOOT_REFRESH_ON_START=0
PYTHONUTF8=1
PYTHONIOENCODING=utf-8
```

5. Health check conseille :

```text
/api/status
```

6. Une fois le deploy fini, partage l'URL publique fournie par la plateforme.

Note : sur certains hebergeurs, le disque est ephemere. L'app servira bien les donnees
embarquees dans `index.html`, mais les donnees recalculees par le scheduler peuvent etre
perdues lors d'un redeploiement ou redemarrage. Pour du vrai 24/7 avec historique durable,
ajoute un disque persistant monte sur :

```text
/app/collector/data
```

## Option robuste : VPS

Sur un VPS Linux avec Docker :

```bash
git clone <ton-repo-github> pronofoot
cd pronofoot
docker build -t pronofoot .
docker run -d --name pronofoot \
  --restart unless-stopped \
  -p 8077:8077 \
  -e PORT=8077 \
  -e PRONOFOOT_READONLY=1 \
  -e PRONOFOOT_ENABLE_SCHEDULER=1 \
  pronofoot
```

Puis pointe un domaine ou un reverse proxy HTTPS vers le port `8077`.

## Securite

Pour une URL partagee avec tes amis, garde :

```text
PRONOFOOT_READONLY=1
```

Ne passe pas `PRONOFOOT_READONLY=0` sur une URL publique sans authentification, sinon
n'importe qui pourrait declencher les actions admin.
