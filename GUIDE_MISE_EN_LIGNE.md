# 🚀 Mettre Okeder en ligne sur okeder.com — Guide pas à pas

> Ce guide est écrit pour être suivi **sans connaissances techniques**. Prends ton temps,
> fais une étape à la fois. Si tu bloques, copie-colle ce que tu vois à Claude, il t'aide.

---

## 1. L'idée en 30 secondes

Pour qu'Okeder soit accessible à tous sur **okeder.com**, il faut **3 ingrédients** :

| Ingrédient | C'est quoi (image simple) | Où | État |
|---|---|---|---|
| **Le domaine** | L'adresse / le panneau « okeder.com » | Namecheap (déjà acheté ✅) | Fait |
| **Le serveur** | Le « bâtiment » où le programme tourne 24h/24 | **Render** (à créer) | À faire |
| **Les données** | La base de données + la mémoire rapide | Supabase + Upstash (déjà en ligne ✅) | Fait |

Il ne reste donc qu'à : **mettre le programme sur Render**, puis **relier okeder.com à Render**.

Entre les deux il y a une étape technique : **mettre le code sur GitHub** (un « coffre-fort » de code en ligne) parce que c'est là que Render va chercher le programme.

**Le chemin complet :**
```
Ton PC (le code)  →  GitHub (coffre du code)  →  Render (fait tourner le code)  →  okeder.com (l'adresse)
```

---

## 2. Petit lexique (pour ne pas être perdu)

- **GitHub** : un site qui stocke le code en ligne (comme Google Drive, mais pour du code).
- **Repository (ou “repo”)** : un dossier de projet sur GitHub.
- **Privé** : seul toi (et Render) peut le voir. ⚠️ On veut **privé**.
- **Render** : le service qui va exécuter Okeder en permanence.
- **Blueprint** : un fichier de recette (`render.yaml`) déjà préparé qui dit à Render quoi installer.
- **Variable d'environnement** : un réglage secret (mot de passe, clé) qu'on donne au serveur **à part**, jamais dans le code.
- **DNS** : l'annuaire qui relie l'adresse `okeder.com` au bon serveur.

---

## 3. ÉTAPE 1 — Mettre le code sur GitHub (le plus simple : l'application “GitHub Desktop”)

> On utilise l'application **GitHub Desktop** (avec des boutons), c'est beaucoup plus facile
> que les commandes. (Une méthode “en commandes” est donnée en annexe si tu préfères.)

1. **Crée un compte** sur https://github.com (gratuit) si tu n'en as pas.
2. **Installe GitHub Desktop** : https://desktop.github.com → installe → connecte-toi avec ton compte GitHub.
3. Dans GitHub Desktop : menu **File → Add Local Repository**.
4. Clique **Choose…** et sélectionne le dossier :
   `C:\Users\USER\OneDrive - Perenco\Okeder\okeder`
   puis **Add Repository**.
5. En haut, clique **Publish repository**.
   - **Décoche** “Keep this code private” ? → **NON, laisse la case “Keep this code private” COCHÉE.** (On veut privé.)
   - Nom : `okeder` → clique **Publish Repository**.
6. ✅ C'est fait : ton code est sur GitHub, en privé.

> ⚠️ **Important** : ne mets jamais tes mots de passe / clés dans le code.
> J'ai déjà fait le ménage : les fichiers secrets ne partent **pas** sur GitHub.

---

## 4. ÉTAPE 2 — Faire tourner Okeder sur Render

1. **Crée un compte** sur https://render.com (tu peux te connecter avec GitHub : bouton “GitHub”).
2. Autorise Render à accéder à ton repo `okeder` quand il le demande.
3. Clique **New +** (en haut à droite) → **Blueprint**.
4. Choisis le repo **okeder**. Render lit automatiquement le fichier `render.yaml` et propose de créer **3 services** :
   - `okeder-backend` (l'application + le site)
   - `okeder-worker` (le moteur en tâche de fond)
   - `okeder-bot` (le bot Telegram)
5. Render va te demander de **remplir les valeurs secrètes**. Ouvre sur ton PC le fichier
   `infra/env/backend.env` (avec le Bloc-notes) et **recopie chaque valeur** en face du bon nom :

   | Nom de la variable dans Render | Où trouver la valeur |
   |---|---|
   | `DATABASE_URL` | dans `infra/env/backend.env` |
   | `REDIS_URL` | dans `infra/env/backend.env` |
   | `TELEGRAM_BOT_TOKEN` | dans `infra/env/backend.env` |
   | `FOURSQUARE_API_KEY` | dans `infra/env/backend.env` |
   | `SMTP_USER` | dans `infra/env/backend.env` |
   | `SMTP_PASSWORD` | dans `infra/env/backend.env` |
   | `EMAIL_FROM` | dans `infra/env/backend.env` |
   | `VAPID_PUBLIC_KEY` | dans `infra/env/backend.env` |
   | `VAPID_PRIVATE_KEY` | dans `infra/env/backend.env` |
   | `STRIPE_SECRET_KEY` | ta clé `sk_test_...` |
   | `STRIPE_PUBLISHABLE_KEY` | ta clé `pk_test_...` |

   *(Les autres réglages, comme `SESSION_SECRET`, sont générés tout seuls. `STRIPE_WEBHOOK_SECRET` : on le fera plus tard, laisse vide.)*
6. Clique **Apply / Create** et attends quelques minutes (Render installe tout).
7. **Vérifie que ça marche** : ouvre l'adresse que Render te donne pour `okeder-backend`
   (du type `https://okeder-backend.onrender.com`) et ajoute `/health` à la fin.
   Tu dois voir : `{"status":"ok"}`. 🎉

---

## 5. ÉTAPE 3 — Relier ton adresse okeder.com

1. Dans Render → service **okeder-backend** → onglet **Settings** → section **Custom Domains** → **Add Custom Domain**.
2. Ajoute `okeder.com`, puis recommence pour `www.okeder.com`.
3. Render affiche alors **des enregistrements à copier** (des lignes type “A”, “CNAME” ou “ALIAS” avec une valeur).
4. Va sur **Namecheap** → **Domain List** → à côté de `okeder.com` clique **Manage** → onglet **Advanced DNS**.
5. Ajoute **exactement** les lignes que Render t'a montrées (bouton **Add New Record**).
   *(En général : une ligne pour `@` (le domaine nu) et une pour `www`.)*
6. Sauvegarde. ⏳ Patiente de 10 minutes à quelques heures (le temps que l'annuaire DNS se mette à jour).
7. Render activera **automatiquement le https** (le cadenas 🔒). Quand c'est prêt, **https://okeder.com** ouvre Okeder.

---

## 6. ÉTAPE 4 — Une fois en ligne

- Le **bot Telegram** marche tout seul depuis Render.
- La **mini-app** est servie en `https://okeder.com/...` (parfait pour Telegram).
- Tu peux **arrêter ton PC et le tunnel** (Cloudflare) : ce n'est plus nécessaire.
- *(Plus tard)* Paiements en conditions réelles : on configurera le “webhook” Stripe ensemble.

---

## 7. Combien ça coûte ?

- Render fait payer les services “en tâche de fond” (~**7 $/mois chacun**) → worker + bot = ~14 $/mois,
  le site (backend) peut être **gratuit** (avec un léger délai au premier chargement) ou ~7 $/mois.
- 💡 **Je peux fusionner le worker et le bot en un seul service** pour réduire à ~7 $/mois au lieu de ~14 $.
  Dis-le-moi et je le prépare.

---

## 8. Où Claude peut t'aider directement

Tu n'es pas seul. À chaque étape, tu peux :
- me dire **“j'ai fait l'étape 1”** et je vérifie / je passe à la suite ;
- me **coller le message d'erreur** ou ce que tu vois à l'écran, et je te dis quoi faire ;
- me demander de **fusionner worker+bot** (moins cher) ou de **préparer le nettoyage** pour rendre le repo public un jour.

> Astuce : dans cette fenêtre, tu peux taper une commande précédée de `!` (par ex. `! git status`)
> pour l'exécuter et que je voie le résultat.

---

## ✅ Check-list rapide

- [ ] Compte GitHub créé + GitHub Desktop installé
- [ ] Repo `okeder` publié en **privé**
- [ ] Compte Render créé + repo connecté
- [ ] Blueprint appliqué + variables secrètes remplies
- [ ] `/health` répond `ok`
- [ ] okeder.com ajouté dans Render + DNS configuré chez Namecheap
- [ ] https://okeder.com s'ouvre 🎉

---

## Annexe — Méthode “en commandes” (si tu n'utilises pas GitHub Desktop)

Après avoir créé un repo **privé** vide nommé `okeder` sur GitHub :
```
git remote add origin https://github.com/TON-UTILISATEUR/okeder.git
git push -u origin master
```
GitHub demandera de te connecter (un “token” fait office de mot de passe).
