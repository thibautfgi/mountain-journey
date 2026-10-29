#### TODO


- [ ] cache thuile neige
- auth doit etre accesible uniquement depuis le front
- model three js sur map = Emplacement cabane, une reel cabane


Franchement, tu as déjà une base solide. Le combo carte 3D + couche neige satellite + modèles Blender pour les POI, c’est rare dans une app de rando perso. Pour la rendre vraiment unique, je te conseille de pousser dans une direction cohérente plutôt que d’empiler des features. Voici les pistes qui me semblent les plus différenciantes, en partant de ce que tu as déjà.

1. Rando “consciente de la neige” (ton vrai point fort)
   Tu as déjà la donnée neige, donc tu peux en faire un moteur de décision :

Un routing qui évite ou pénalise les zones enneigées selon la saison et le niveau de l’utilisateur (raquettes, crampons, rien).
Un indice de “faisabilité” par itinéraire : pourcentage du tracé sous neige, altitude de la limite pluie/neige, pente combinée à la neige (risque avalanche indicatif, avec un avertissement clair que ça ne remplace pas le bulletin officiel).
Une timeline : un slider pour voir l’évolution de la neige sur les dernières semaines, et prévoir si un col sera praticable.

2. Le temps comme dimension 3D

Simulation du soleil : ombres réelles sur le relief selon l’heure, pour savoir quand une face sera au soleil ou à l’ombre. Mapbox gère déjà bien le terrain, c’est faisable avec les données d’élévation.
Heure dorée / coucher de soleil : “à quelle heure je dois être au sommet pour avoir le meilleur éclairage”.

3. Vol virtuel de l’itinéraire
   Un mode “fly-through” 3D qui survole ton GPX avant de partir, avec le profil d’élévation synchronisé. C’est spectaculaire visuellement et très utile pour repérer les passages délicats.

4. Exploiter tes modèles Blender davantage

Des modèles qui changent d’état : cabane gardée/non gardée, ouverte/fermée selon la saison, avec de la neige sur le toit si la zone est enneigée.
Des modèles pour les points d’eau, cols, sommets, refuges, passages techniques.
Une petite fiche au clic : altitude, nombre de places, période d’ouverture, photo.

5. Mode hors-ligne
   Pour la montagne, c’est quasi indispensable : tuiles, GPX et couche neige mises en cache avant le départ. Ça peut vite devenir ton argument principal face à des apps généralistes.

6. Mémoire des sorties
   Enregistrer tes randos, les rejouer en 3D, comparer avec les conditions de neige du jour. Ça crée un journal de bord personnel qui rend l’app attachante.

Si je devais choisir un fil conducteur, ce serait “l’app qui te dit ce que la montagne est vraiment aujourd’hui” : neige, soleil, état des refuges, faisabilité. Tout ce que tu as déjà s’y rattache naturellement, et peu d’apps le font bien.

Dis-moi ce qui t’attire le plus (plus orienté sécurité, plus visuel, ou plus communauté), et on peut creuser l’architecture technique de la piste que tu choisis.