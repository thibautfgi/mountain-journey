 ## Sécurité
 
L’unique artefact côté client est le Bearer token retourné par mj-auth. 
Ce token contient trois parties JWT classiques (header, payload, signature) et voyage dans l’en-tête Authorization: Bearer <token>.

Le token est signé avec une clé secrète (secretKey) définie dans le fichier de configuration de l’application et a une durée de vie limitée (expirationTime) pour renforcer la sécurité. 
Une fois expiré, le client doit se réauthentifier pour obtenir un nouveau token.

>En résumé notre app possède une double protection :

- **Bearer token** = le JWT complet ajouter à chaque requête après authentification.

- **jwt.secret** = la clé partagée qui permet de valider ce Bearer token via la signature.
Elle garantit que le token vient bien du service d’authentification et qu’il n’a pas été modifié.