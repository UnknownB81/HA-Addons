# Journal des modifications

## 0.2.4

- Remplacement du champ de zone par un menu déroulant compatible avec Home Assistant Ingress.
- Chargement automatique des zones lorsqu'un jeton Cloudflare est déjà enregistré.

## 0.2.3

- Correction de la détection des doublons pour permettre le même nom relatif dans des zones différentes.
- Détection des doublons équivalents comme `@` et le nom complet de la racine d'une même zone.

## 0.2.2

- Ajout du contrôle de santé Watchdog pour Home Assistant.
- Documentation du cycle de synchronisation automatique.

## 0.2.1

- Correction de la recherche des noms relatifs comme `www`.
- Ajout du libellé `@` pour cibler la racine d'une zone.

## 0.2.0

- Ajout d'une interface graphique intégrée à Home Assistant avec Ingress.
- Test du jeton et découverte des zones Cloudflare.
- Synchronisation immédiate et affichage du dernier résultat.
- Stockage privé de la configuration avec masquage du jeton.

## 0.1.0

- Première version.
- Gestion de plusieurs zones et enregistrements A/AAAA.
- Mode simulation et création facultative des enregistrements.
