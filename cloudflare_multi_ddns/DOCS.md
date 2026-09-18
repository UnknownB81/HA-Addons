# Cloudflare Multi-DDNS

Cet add-on met à jour plusieurs enregistrements DNS Cloudflare avec l'adresse IP
publique de votre connexion. Une même configuration peut couvrir plusieurs zones.

## Créer le jeton Cloudflare

Dans **Cloudflare > My Profile > API Tokens > Create Token**, partez du modèle
**Edit zone DNS** et accordez :

- `Zone > Zone > Read`;
- `Zone > DNS > Edit`.

Limitez les ressources aux zones que l'add-on doit gérer. N'utilisez pas la clé API
globale.

## Configuration dans Home Assistant

Après le démarrage, sélectionnez **Ouvrir l'interface utilisateur Web** depuis la
page de l'add-on. Toute la configuration se fait dans cette interface :

1. saisissez le jeton Cloudflare et sélectionnez **Tester la connexion**;
2. ajoutez les enregistrements DNS à maintenir;
3. conservez le mode simulation pour le premier essai;
4. sélectionnez **Enregistrer la configuration**;
5. lancez **Synchroniser maintenant** et consultez le statut affiché.

La configuration est conservée dans le volume privé de l'add-on. Le jeton enregistré
n'est jamais renvoyé au navigateur.

## Synchronisation automatique

La synchronisation est automatique. L'add-on effectue une vérification au démarrage,
puis répète cette vérification selon l'intervalle configuré. La valeur par défaut de
`300` correspond à une vérification toutes les 5 minutes.

Cloudflare est modifié uniquement lorsque l'adresse IP publique diffère de la valeur
de l'enregistrement DNS. Le bouton **Synchroniser maintenant** est donc facultatif :
il sert principalement au premier test ou à une vérification manuelle.

Pour un fonctionnement autonome :

1. effectuez un premier essai avec **Mode simulation** activé;
2. vérifiez le résultat et désactivez ensuite **Mode simulation**;
3. enregistrez la configuration;
4. activez **Démarrer au démarrage** et **Watchdog** dans la page de l'add-on.

Le Watchdog permet à Home Assistant de redémarrer l'add-on si son interface de santé
ne répond plus. Les indicateurs **Dernière réussite**, **Modifiés** et **Inchangés**
permettent de contrôler son fonctionnement sans consulter les journaux.

### Format de référence

Exemple IPv4 sur deux zones :

```yaml
api_token: votre_jeton_cloudflare
interval: 300
create_missing: false
dry_run: false
ipv4_url: https://api.ipify.org
ipv6_url: https://api6.ipify.org
records:
  - name: maison.example.com
    type: A
  - name: vpn.autre-domaine.ca
    type: A
    proxied: false
    ttl: 300
```

Pour gérer aussi IPv6, ajoutez un enregistrement `AAAA` :

```yaml
  - name: maison.example.com
    type: AAAA
```

La zone est normalement découverte automatiquement. Le champ `zone` peut la
forcer si nécessaire :

```yaml
  - name: home.sous-zone.example.com
    type: A
    zone: sous-zone.example.com
```

Lorsque la zone est sélectionnée, le nom peut être un libellé relatif comme `www`.
Il sera converti en `www.example.com`. Utilisez `@` pour cibler directement la
racine de la zone. Un nom complet comme `maison.example.com` reste accepté.

## Options

| Option | Description |
|---|---|
| `api_token` | Jeton API Cloudflare. Obligatoire. |
| `interval` | Délai entre les vérifications, de 60 à 86400 secondes. |
| `create_missing` | Crée les enregistrements absents lorsqu'il vaut `true`. |
| `dry_run` | Affiche les changements sans écrire dans Cloudflare. |
| `ipv4_url` | Service texte utilisé pour détecter l'adresse IPv4. |
| `ipv6_url` | Service texte utilisé pour détecter l'adresse IPv6. |
| `records` | Liste des enregistrements `A` et `AAAA` à gérer. |

Si `proxied` ou `ttl` est omis, sa valeur actuelle est conservée lors d'une mise à
jour. Pour un nouvel enregistrement, les valeurs par défaut sont respectivement
`false` et `1` (automatique).

## Installation

### Depuis GitHub

1. Publiez ce dossier dans un dépôt GitHub.
2. Dans Home Assistant, ouvrez **Paramètres > Modules complémentaires > Boutique**.
3. Ouvrez le menu en haut à droite, puis **Dépôts**.
4. Ajoutez l'URL du dépôt GitHub.
5. Installez **Cloudflare Multi-DDNS**, démarrez-le, puis ouvrez son interface Web.

### Test local

Copiez le dossier `cloudflare_multi_ddns` dans `/addons`, puis rechargez la boutique
des modules complémentaires. Activez d'abord `dry_run` et vérifiez le journal.

## Dépannage

- `Aucune zone accessible` : vérifiez la portée du jeton et le droit `Zone Read`.
- `Enregistrement introuvable` : créez-le dans Cloudflare ou activez
  `create_missing`.
- erreur IPv6 : retirez les entrées `AAAA` si votre connexion n'a pas d'IPv6
  publique.
