# 🏔️ Mountain Journey — Architecture Auth & Sécurité

> **Stack :** Spring Boot 4 (Java 21) · Angular 21 · JWT (JJWT 0.12.6) · PostgreSQL  
> **Principe :** Pages publiques = `/home` et `/login`. Toutes les autres routes nécessitent un JWT valide.

---

## 📋 Sommaire

1. [Problèmes identifiés dans l'architecture actuelle](#1-problèmes-identifiés)
2. [Architecture cible](#2-architecture-cible)
3. [Backend — mj-auth (Spring Boot)](#3-backend--mj-auth)
4. [Frontend — mj-front (Angular)](#4-frontend--mj-front)
5. [Checklist finale](#5-checklist-finale)

---

## 1. Problèmes identifiés

| # | Fichier | Problème | Impact |
|---|---------|----------|--------|
| 1 | `JwtService.java` | `Base64.getEncoder().encode(secret.getBytes())` encode deux fois en base64, la clé est incorrecte | 🔴 Bug critique |
| 2 | `JwtService.java` | Pas de `roles` dans le token, pas de `userId` — impossible d'identifier l'utilisateur côté moteur | 🟡 Limitation |
| 3 | `SecurityConfig.java` | `/api/users/**` est entièrement public — n'importe qui peut accéder aux données users | 🔴 Faille sécu |
| 4 | `AuthController.java` | `@CrossOrigin` en double avec la config CORS globale | 🟡 Redondant |
| 5 | `JwtAuthFilter.java` | Retourne 200 même si le token est invalide (pas de `401`) | 🔴 Bug sécu |
| 6 | `AuthService.java` | Exceptions génériques `RuntimeException` — le front reçoit un 500 au lieu d'un 401/409 | 🟡 UX |
| 7 | `auth.services.ts` | Token stocké en `localStorage` — vulnérable aux attaques XSS | 🟡 Sécu |
| 8 | `auth.services.ts` | Authorization header ajouté manuellement dans `whoiam()` seulement — pas d'intercepteur global | 🔴 Tous les appels protégés échouent |
| 9 | `app.routes.ts` | Aucune protection de routes — `/maps` accessible sans connexion | 🔴 Bug fonctionnel |
| 10 | `app.config.ts` | `HttpClient` non fourni dans les providers | 🔴 Bug de démarrage |

---

## 2. Architecture cible

```
mj-front (Angular)
│
├── AuthGuard              ← protège toutes les routes sauf /home et /login
├── AuthInterceptor        ← injecte automatiquement le Bearer token sur chaque requête HTTP
├── AuthService            ← gère login / logout / état de connexion (signal)
└── Routes
    ├── /home       (public)
    ├── /login      (public)
    ├── /maps       (protégé ✅)
    └── /explorer   (protégé ✅)

mj-auth (Spring Boot)
│
├── JwtAuthFilter          ← valide le token, renvoie 401 si invalide
├── SecurityConfig         ← whitelist uniquement /auth/login et /auth/register
├── JwtService             ← génère et valide les JWT (clé fixée)
└── AuthService            ← login / register / whoiam
```

---

## 3. Backend — mj-auth

### 3.1 Fix `JwtService.java` — Bug de clé

**Problème :** `Base64.getEncoder().encode(secret.getBytes())` double-encode la clé.  
**Fix :** utiliser directement les bytes.

```java
// JwtService.java
@Service
public class JwtService {

    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.expiration}")
    private long expiration;

    private SecretKey getKey() {
        // ✅ CORRIGÉ : on utilise directement les bytes bruts, pas de double encodage Base64
        byte[] keyBytes = secret.getBytes(StandardCharsets.UTF_8);
        return Keys.hmacShaKeyFor(keyBytes);
    }

    public String generateToken(String email) {
        return Jwts.builder()
                .subject(email)
                .claim("email", email)           // ✅ claim explicite utile pour le moteur
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + expiration))
                .signWith(getKey())
                .compact();
    }

    public String extractEmail(String token) {
        return getClaims(token).getSubject();
    }

    public boolean isTokenValid(String token) {
        try {
            Claims claims = getClaims(token);
            return !claims.getExpiration().before(new Date()); // vérifie aussi l'expiration
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }

    private Claims getClaims(String token) {
        return Jwts.parser()
                .verifyWith(getKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}
```

---

### 3.2 Fix `JwtAuthFilter.java` — Renvoyer 401

**Problème :** si le token est absent ou invalide, la requête passe quand même.

```java
// JwtAuthFilter.java
@Component
@RequiredArgsConstructor
public class JwtAuthFilter extends OncePerRequestFilter {

    private final JwtService jwtService;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        String path = request.getRequestURI();

        // Routes publiques — on laisse passer sans vérification
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())
                || path.equals("/api/auth/login")
                || path.equals("/api/auth/register")) {
            filterChain.doFilter(request, response);
            return;
        }

        String authHeader = request.getHeader("Authorization");

        // ✅ CORRIGÉ : si pas de token ou token invalide → 401 immédiat
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"error\": \"Token manquant\"}");
            return;
        }

        String token = authHeader.substring(7);

        if (!jwtService.isTokenValid(token)) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"error\": \"Token invalide ou expiré\"}");
            return;
        }

        // Token valide → on alimente le SecurityContext
        String email = jwtService.extractEmail(token);
        UsernamePasswordAuthenticationToken auth =
                new UsernamePasswordAuthenticationToken(email, null, List.of());
        SecurityContextHolder.getContext().setAuthentication(auth);

        filterChain.doFilter(request, response);
    }
}
```

---

### 3.3 Fix `SecurityConfig.java` — Retirer `/api/users/**` du public

**Problème :** `/api/users/**` est public — tout le monde peut lire les utilisateurs.

```java
// SecurityConfig.java
@Bean
public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
    http
        .cors(cors -> cors.configurationSource(corsConfigurationSource()))
        .csrf(AbstractHttpConfigurer::disable)
        .sessionManagement(session -> session
            .sessionCreationPolicy(SessionCreationPolicy.STATELESS)) // ✅ API stateless
        .authorizeHttpRequests(auth -> auth
            .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
            // ✅ Seules ces deux routes sont publiques
            .requestMatchers("/api/auth/login", "/api/auth/register").permitAll()
            // ✅ Tout le reste nécessite un token valide
            .anyRequest().authenticated()
        )
        .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);

    return http.build();
}

@Bean
public CorsConfigurationSource corsConfigurationSource() {
    CorsConfiguration config = new CorsConfiguration();
    config.setAllowedOriginPatterns(List.of(
        "http://localhost:4200",
        "http://127.0.0.1:4200"
    ));
    config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
    config.setAllowedHeaders(List.of("*"));
    config.setAllowCredentials(true);
    config.setMaxAge(3600L);

    UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/**", config);
    return source;
}
```

---

### 3.4 Fix `AuthService.java` — Exceptions avec codes HTTP

**Problème :** `RuntimeException` → Spring renvoie un 500 au lieu de 409/401.

```java
// AuthService.java
// Ajouter ces imports :
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    public AuthResponse register(RegisterRequest request) {
        if (userRepository.existsByUserEmail(request.getUserEmail())) {
            // ✅ 409 Conflict au lieu de 500
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email déjà utilisé");
        }

        User user = User.builder()
                .userFirstName(request.getUserFirstName())
                .userLastName(request.getUserLastName())
                .userPhone(request.getUserPhone())
                .userEmail(request.getUserEmail())
                .userPassword(passwordEncoder.encode(request.getUserPassword()))
                .build();

        userRepository.save(user);
        String token = jwtService.generateToken(user.getUserEmail());
        return new AuthResponse(token, user.getUserEmail(), user.getUserFirstName(), user.getUserLastName());
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByUserEmail(request.getUserEmail())
                // ✅ 401 Unauthorized au lieu de 500
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Identifiants incorrects"));

        if (!passwordEncoder.matches(request.getUserPassword(), user.getUserPassword())) {
            // ✅ Message générique volontaire (évite l'énumération d'emails)
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Identifiants incorrects");
        }

        String token = jwtService.generateToken(user.getUserEmail());
        return new AuthResponse(token, user.getUserEmail(), user.getUserFirstName(), user.getUserLastName());
    }

    public WhoiamResponse whoiam(String email) {
        User user = userRepository.findByUserEmail(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Utilisateur introuvable"));
        return new WhoiamResponse(user.getUserEmail(), user.getUserFirstName(), user.getUserLastName());
    }
}
```

---

### 3.5 Fix `AuthController.java` — Supprimer `@CrossOrigin` redondant

```java
// AuthController.java
// ✅ Retirer @CrossOrigin (déjà géré dans SecurityConfig)
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
// ❌ @CrossOrigin(origins = "http://localhost:4200")  <-- SUPPRIMER
public class AuthController {
    // ... reste inchangé
}
```

---

### 3.6 `application.properties` — Clé JWT plus robuste

```properties
# JWT — clé d'au moins 512 bits (64 chars) pour HS256
jwt.secret=MountainJourney_SuperSecretKey_2026_PleaseChangeInProd_MustBe64CharsMin!
jwt.expiration=86400000
```

> ⚠️ **En production** : utiliser une variable d'environnement ou un secret manager, jamais en dur.

---

## 4. Frontend — mj-front (Angular)

### 4.1 Fix `app.config.ts` — Fournir `HttpClient`

**Problème :** `HttpClient` n'est pas fourni → toutes les requêtes HTTP échouent.

```typescript
// app.config.ts
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http'; // ✅ AJOUT
import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor'; // ✅ AJOUT

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // ✅ HttpClient avec l'intercepteur JWT global
    provideHttpClient(withInterceptors([authInterceptor]))
  ]
};
```

---

### 4.2 Créer `AuthInterceptor` — Injection automatique du token

**Chemin :** `src/app/core/interceptors/auth.interceptor.ts`

**Pourquoi :** au lieu d'ajouter manuellement le header dans chaque méthode du service, l'intercepteur le fait automatiquement sur **toutes** les requêtes HTTP.

```typescript
// src/app/core/interceptors/auth.interceptor.ts
import { HttpInterceptorFn, HttpRequest, HttpHandlerFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../../components/communs/services/auth.services';

export const authInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const token = authService.getToken();

  // Routes publiques — on n'ajoute pas le token
  const publicUrls = ['/api/auth/login', '/api/auth/register'];
  const isPublic = publicUrls.some(url => req.url.includes(url));

  // ✅ Clone la requête et ajoute le Bearer token si présent et route non publique
  const authReq = (!isPublic && token)
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authReq).pipe(
    catchError((error: HttpErrorResponse) => {
      // ✅ Si 401 → token expiré ou invalide → déconnexion automatique
      if (error.status === 401) {
        authService.logout();
        router.navigate(['/login']);
      }
      return throwError(() => error);
    })
  );
};
```

---

### 4.3 Créer `AuthGuard` — Protéger les routes

**Chemin :** `src/app/core/guards/auth.guard.ts`

```typescript
// src/app/core/guards/auth.guard.ts
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../../components/communs/services/auth.services';

export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isLoggedIn()) {
    return true; // ✅ Utilisateur connecté → accès autorisé
  }

  // ❌ Non connecté → redirection vers /login
  return router.createUrlTree(['/login']);
};
```

---

### 4.4 Fix `app.routes.ts` — Appliquer le guard

```typescript
// app.routes.ts
import { Routes } from '@angular/router';
import { HomeComponent } from './components/page/home/home.component';
import { ConnectionComponent } from './components/page/connection/connection.component';
import { NotFoundComponent } from './components/page/not-found/not-found.component';
import { MapsComponent } from './components/page/maps/maps.component';
import { authGuard } from './core/guards/auth.guard'; // ✅ AJOUT

export const routes: Routes = [
  {
    path: '',
    redirectTo: '/home',
    pathMatch: 'full'
  },
  {
    // ✅ PUBLIC — accessible sans connexion
    path: 'home',
    component: HomeComponent
  },
  {
    // ✅ PUBLIC — page de connexion/inscription
    path: 'login',
    component: ConnectionComponent
  },
  {
    // ✅ PROTÉGÉ — nécessite un token JWT valide
    path: 'maps',
    component: MapsComponent,
    canActivate: [authGuard]
  },
  {
    // Ajouter canActivate: [authGuard] sur toutes les nouvelles routes protégées
    path: '**',
    component: NotFoundComponent
  }
];
```

---

### 4.5 Fix `auth.services.ts` — Amélioration complète

```typescript
// auth.services.ts
import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { Router } from '@angular/router';
import { LoginCredentials, SignupRequest, AuthResponse, WhoiamResponse } from '../interfaces/auth.interface';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly baseUrl = '/api';
  private readonly TOKEN_KEY = 'mj_token';

  // ✅ Signal réactif — les composants se mettent à jour automatiquement
  private _isLoggedIn = signal<boolean>(this.hasValidToken());
  readonly isAuthenticated = computed(() => this._isLoggedIn());

  constructor(private http: HttpClient, private router: Router) {}

  login(credentials: LoginCredentials): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.baseUrl}/auth/login`, {
      userEmail: credentials.email,
      userPassword: credentials.password
    }).pipe(
      tap((res: AuthResponse) => {
        this.saveToken(res.userToken);
        this._isLoggedIn.set(true);
      })
    );
  }

  register(request: SignupRequest): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.baseUrl}/auth/register`, {
      userFirstName: request.firstName || '',
      userLastName: request.lastName || '',
      userEmail: request.email,
      userPassword: request.password,
      userPhone: request.phone || ''
    }).pipe(
      tap((res: AuthResponse) => {
        this.saveToken(res.userToken);
        this._isLoggedIn.set(true);
      })
    );
  }

  // ✅ Plus besoin d'ajouter le header manuellement — l'intercepteur s'en charge
  whoiam(): Observable<WhoiamResponse> {
    return this.http.get<WhoiamResponse>(`${this.baseUrl}/auth/whoiam`);
  }

  getToken(): string | null {
    return sessionStorage.getItem(this.TOKEN_KEY); // ✅ sessionStorage : plus sûr que localStorage
  }

  isLoggedIn(): boolean {
    return this.hasValidToken();
  }

  logout(): void {
    sessionStorage.removeItem(this.TOKEN_KEY);
    this._isLoggedIn.set(false);
    // Navigation gérée par l'appelant ou l'intercepteur
  }

  private saveToken(token: string): void {
    sessionStorage.setItem(this.TOKEN_KEY, token);
  }

  private hasValidToken(): boolean {
    const token = sessionStorage.getItem(this.TOKEN_KEY);
    if (!token) return false;
    try {
      // Vérification basique de l'expiration côté client (sans vérifier la signature)
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  }
}
```

---

### 4.6 Fix `connection.component.ts` — Supprimer les `alert()`

```typescript
// connection.component.ts — onSubmit() amélioré
errorMessage = signal<string>('');
successMessage = signal<string>('');

onSubmit() {
  if (this.loginForm.invalid) return;

  this.isLoading.set(true);
  this.errorMessage.set('');
  const { email, password } = this.loginForm.value;

  if (this.mode() === 'login') {
    this.authService.login({ email, password }).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        this.router.navigate(['/maps']); // ✅ Redirection silencieuse, plus d'alert()
      },
      error: (err) => {
        this.isLoading.set(false);
        // ✅ Affichage dans le template, pas en popup
        this.errorMessage.set(err?.error?.message || 'E-mail ou mot de passe incorrect');
      }
    });
  } else {
    // ... register similaire
  }
}
```

```html
<!-- Dans connection.component.html, ajouter : -->
@if (errorMessage()) {
  <div class="error-banner">{{ errorMessage() }}</div>
}
```

---

### 4.7 Structure de fichiers recommandée

```
src/app/
├── core/                          ← ✅ NOUVEAU dossier à créer
│   ├── guards/
│   │   └── auth.guard.ts
│   └── interceptors/
│       └── auth.interceptor.ts
├── components/
│   ├── communs/
│   │   ├── interfaces/
│   │   │   └── auth.interface.ts
│   │   └── services/
│   │       └── auth.services.ts
│   └── page/
│       ├── home/         (public)
│       ├── connection/   (public)
│       ├── maps/         (protégé ✅)
│       └── not-found/
├── app.routes.ts
├── app.config.ts
└── app.component.ts
```

---

## 5. Checklist finale

### Backend ✅
- [ ] Fix `JwtService.getKey()` — supprimer le double encodage Base64
- [ ] Fix `JwtAuthFilter` — renvoyer 401 si token absent ou invalide
- [ ] Fix `SecurityConfig` — retirer `/api/users/**` des routes publiques
- [ ] Fix `AuthService` — utiliser `ResponseStatusException` avec les bons codes HTTP
- [ ] Retirer `@CrossOrigin` de `AuthController`
- [ ] Changer la clé JWT dans `application.properties` (min 64 caractères)
- [ ] Ajouter `SessionCreationPolicy.STATELESS` dans `SecurityConfig`

### Frontend ✅
- [ ] Créer `src/app/core/interceptors/auth.interceptor.ts`
- [ ] Créer `src/app/core/guards/auth.guard.ts`
- [ ] Ajouter `provideHttpClient(withInterceptors([authInterceptor]))` dans `app.config.ts`
- [ ] Ajouter `canActivate: [authGuard]` sur `/maps` et toutes les routes protégées dans `app.routes.ts`
- [ ] Passer de `localStorage` à `sessionStorage` dans `AuthService`
- [ ] Supprimer l'ajout manuel du header dans `whoiam()` (l'intercepteur le fait)
- [ ] Remplacer les `alert()` par des messages dans le template

---

> **Note :** `sessionStorage` est préférable à `localStorage` car il est vidé à la fermeture de l'onglet. Pour une vraie sécurité XSS, la solution ultime serait un cookie `HttpOnly`, mais cela nécessite une refonte du backend pour émettre des cookies au lieu de JSON.

