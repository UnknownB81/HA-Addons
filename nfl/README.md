# Integration NFL pour Home Assistant

Ce dossier doit etre publie comme racine d'un depot GitHub dedie, par exemple
`UnknownB81/HA-NFL`. Ne l'ajoute pas directement depuis le depot `HA-Addons`,
qui est un depot d'add-ons Home Assistant.

Cette integration interroge les API publiques ESPN et expose les entites suivantes :

- `sensor.nfl_classement_complet`
- `sensor.nfl_classement_pre_saison`
- `sensor.nfl_classement_global`
- `sensor.nfl_matchs_du_jour`
- `sensor.nfl_matchs_pre_saison`

Les donnees detaillees sont disponibles dans l'attribut `teams` pour les classements
et `games` pour les matchs.

## Installation manuelle

1. Copier `custom_components/nfl` dans `/config/custom_components/nfl`.
2. Redemarrer Home Assistant.
3. Ouvrir **Parametres > Appareils et services > Ajouter une integration**.
4. Rechercher `NFL` et valider l'ajout.
5. Ajouter la carte presente dans `sample-card.yaml` au dashboard Lovelace.

## Installation avec HACS

1. Creer un depot GitHub dedie `UnknownB81/HA-NFL`.
2. Publier le contenu de ce dossier a la racine de ce nouveau depot.
3. Dans HACS, ajouter `UnknownB81/HA-NFL` comme depot personnalise de type
	**Integration**.
4. Installer `NFL`, puis redemarrer Home Assistant.

L'installation ne necessite aucune cle API ESPN.

## Migration depuis la configuration YAML

Supprimer l'ancien contenu NFL de `configuration.yaml` ou de `packages/nfl.yaml`
avant d'ajouter l'integration depuis l'interface. Les deux modes ne doivent pas
fonctionner en meme temps, sinon les entites seront dupliquees.

La carte Lovelace necessite `flex-table-card` et `tabbed-card`, installables via HACS.

## Developpement

Les donnees sont rafraichies toutes les cinq minutes. Les erreurs de recuperation
ESPN sont gerees par le coordinateur Home Assistant et rendent les entites
indisponibles jusqu'au prochain rafraichissement reussi.