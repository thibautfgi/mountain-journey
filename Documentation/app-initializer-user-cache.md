# 🚀 User Cache avec provideAppInitializer — Angular 21

> Problème : `whoiam()` appelé dans le `ngOnInit` du header → requête réseau à chaque montage du composant.  
> Solution : `provideAppInitializer` + signal global → **1 seule requête au boot**, mise en cache réactive.

---

## Pourquoi `provideAppInitializer` ?

| Méthode | Angular | Verdict |
|---|---|---|
| `ngOnInit` dans le header | Toutes versions | ❌ Requête répétée, couplage fort |
| `APP_INITIALIZER` token | < Angular 19 | ⚠️ Verbeux, déprécié |
| **`provideAppInitializer`** | **Angular 19+** | ✅ **Recommandé — simple, natif, moderne** |
| `httpResource()` | Angular 19+ | ❌ Non adapté à l'auth (pas de contrôle login/logout) |
| NgRx Signal Store | Toutes versions | ⚠️ Over-engineering pour un seul user |

**`provideAppInitializer`** bloque le premier rendu de l'app jusqu'à résolution de la promesse → le signal `user` est peuplé **avant** que le moindre composant s'affiche.

---

## Flux

```
App démarre
    │
    ▼
provideAppInitializer()       ← exécuté avant le 1er rendu
    │
    ▼
authService.initUser()
    │
    ├── Token absent / expiré (côté client)
    │       └── of(null) → app charge → page /home
    │
    └── Token valide en sessionStorage
            │
            ▼
        GET /api/auth/whoiam
            │
            ├── 200 OK → _user signal peuplé ✅
            │             header affiche prénom / nom
            │
            └── 401 KO → logout() silencieux
                          redirection /connection

─────────────────────────────────────────
Après login ou register (switchMap)
─────────────────────────────────────────

POST /login (ou /register)
    │
    ▼
Token sauvegardé en sessionStorage
_isLoggedIn.set(true)
    │
    ▼  switchMap
GET /api/auth/whoiam
    │
    ▼
_user signal peuplé ✅  ← header réactif instantanément
```

---

## Fichiers modifiés

### 1. `auth.services.ts` — ajout de `initUser()`

```typescript
import { Observable, tap, catchError, of, switchMap } from 'rxjs';

// Méthode ajoutée
initUser(): Observable<WhoiamResponse | null> {
  if (!this.hasValidToken()) {
    return of(null); // pas de token → app charge directement
  }
  return this.whoiam().pipe(
    catchError(() => {
      this.logout(); // token expiré côté serveur → nettoyage silencieux
      return of(null);
    })
  );
}
```

`login()` et `register()` chaînent maintenant un `switchMap(() => whoiam())` pour peupler le signal immédiatement après connexion :

```typescript
login(credentials: LoginCredentials): Observable<WhoiamResponse> {
  return this.http.post<AuthResponse>(`${this.baseUrl}/login`, { ... }).pipe(
    tap((res) => {
      this.saveToken(res.userToken);
      this._isLoggedIn.set(true);
    }),
    switchMap(() => this.whoiam()) // ← signal user peuplé directement
  );
}
```

---

### 2. `app.config.ts` — enregistrement de `provideAppInitializer`

```typescript
import {
  ApplicationConfig,
  inject,
  provideBrowserGlobalErrorListeners,
  provideAppInitializer
} from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { routes } from './app.routes';
import { authInterceptor } from './components/interceptors/auth.interceptor';
import { AuthService } from './components/communs/services/auth.services';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    // ✅ Hydratation du signal user avant le 1er rendu
    provideAppInitializer(() => {
      const authService = inject(AuthService);
      return firstValueFrom(authService.initUser());
    })
  ]
};
```

---

### 3. `header.component.ts` — suppression du `ngOnInit`

```typescript
// AVANT ❌
export class HeaderComponent implements OnInit {
  protected authService = inject(AuthService);

  ngOnInit(): void {
    if (this.authService.isLoggedIn()) {
      this.authService.whoiam().subscribe(); // requête à chaque montage
    }
  }
}

// APRÈS ✅
export class HeaderComponent {
  protected authService = inject(AuthService);
  // authService.user() est déjà peuplé — aucune requête ici
}
```

**Template inchangé** — lit simplement le signal :
```html
@if (authService.user(); as user) {
  <span>{{ user.userFirstName }} {{ user.userLastName }}</span>
  <button (click)="authService.logout()">Déconnexion</button>
} @else {
  <a href="/login">
    <app-custom-buttons textButton="Se connecter"></app-custom-buttons>
  </a>
}
```

---

## Résumé des bénéfices

| | Avant | Après |
|---|---|---|
| Appels `whoiam()` | 1 par montage du header | **1 seul au boot** |
| Signal `user` disponible | Après `ngOnInit` | **Avant le 1er rendu** |
| Header détruit / remonté | Nouvelle requête réseau | Signal déjà en cache |
| Token expiré côté serveur | Erreur silencieuse | `logout()` automatique |
| Composant responsable | `HeaderComponent` | **`AuthService` seul** |

---

*Généré le 04/06/2026 — Mountain Journey*

