# Cloudflare Multi-DDNS pour Home Assistant

Ce dépôt contient un add-on Home Assistant qui maintient plusieurs enregistrements
DNS Cloudflare à jour avec l'adresse IP publique de votre connexion.

## Fonctionnalités

- plusieurs zones et noms de domaine avec un seul jeton API;
- enregistrements IPv4 (`A`) et IPv6 (`AAAA`);
- découverte automatique de la zone Cloudflare;
- aucune écriture lorsque l'adresse n'a pas changé;
- conservation du TTL et du statut de proxy existants;
- création facultative des enregistrements manquants;
- mode `dry_run` pour tester sans modifier Cloudflare.

Consultez [la documentation de l'add-on](DOCS.md) pour
l'installation et la configuration.
