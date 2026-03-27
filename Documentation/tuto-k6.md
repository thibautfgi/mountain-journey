#### Tuto : Utiliser K6 pour tester les performances de mes API

Afin d'utiliser K6 pour tester les performances de mes API, je dois d'abord convertir mes collections de tests Postman en scripts k6.
J'utilise un outil appelé `postman-to-k6` qui me permet de convertir mes collections Postman en scripts k6.
Je n'oublie pas d'exporter mes collections Postman au format JSON avant de les convertir ainsi que mes environnements si j'en ai besoin.

###### Pour setup `postman-to-k6`, j'installe le package via npm :

```bash
npm install -D @apideck/postman-to-k6
```

###### Ensuite, je peux convertir ma collection Postman en script k6 :

```bash
postman-to-k6 documentation/postman/mj-postman-collection-local.json --environment documentation/postman/mj-postman-env-local.json -o documentation/k6/k6-script-prod.js
```

###### Script local

```bash
npm run k6:local
```

###### Script prod

```bash
npm run k6:prod
```
