# TODO — RAIES Plugin

## En cours
- [ ] Afficher la couche Map dans l'interface (nouveau widget dans ConstraintItemWidget)
  - Bouton "remplacer la couche" (au lieu de supprimer)
  - Résolution : boutons 10 / 100 / 1000 m (stockée dans SuricatesInstance, ligne Map du config)
  - Warning si résolution × surface > 4 M pixels

## Icônes / couleurs / renommage
- [x] Zone obligatoire : nouveau type `Mandatory` (damier vert), force 0 sur la couche
      finale via masquage post-cumul (`applyMandatoryZones`) — symétrique de Sanctuarized.
      (NB : implémenté comme type distinct, pas comme Included × 0.)
- [x] Type Sanctuarized : couleur rouge (damier), libellé UI « Forbidden ».
      (Comportement no-data de l'algo laissé tel quel — à vérifier côté Vincent.)
- [ ] Légendes des initiales affichées sur les icônes

## Buffer
- [ ] Valeur min du buffer calée sur la résolution (défaut = 75 % de la résolution)
- [ ] Vérifier que le buffer ne dépasse pas les limites de la couche Map

## Ergonomie
- [ ] Pouvoir annuler le calcul quand on clique sur X dans la fenêtre "Delete temporary files ?"
- [ ] Supprimer la fermeture automatique du widget lors de la désélection (déjà traité ?)

## Optionnel / ne pas faire
- [ ] Limiter la distance raster à 0–5 000 m (optionnel, décision à prendre)
