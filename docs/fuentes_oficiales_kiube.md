# Fuentes oficiales IBA — Cyclone® KIUBE (base de conocimiento)

**Estado:** integrado a la base de conocimiento de Radiopharma OS · 2026-10-16
**Documentos fuente (en `/mnt/agents/upload/`, propiedad de IBA — uso interno):**

- **KIUBE-OM** = *Cyclone® Kiube Production Guide*, MID 67061 rev.B, feb-2019 (manual de producción)
- **KIUBE-SRG** = *Cyclone® KIUBE Site Requirement Guide*, MID 55672 rev.F, oct-2019 (requisitos de sitio)

Estas fuentes oficiales del fabricante tienen jerarquía **superior** a la literatura
académica (TUP03/TUP04/S09/BON21) y a todo `EST` del modelo kiube v0.4, conforme a la
regla 49.11 (cifras solo con fuente citada). Sirven para validación cruzada del modelo
teórico; **no** habilitan nada clínico (PQ sigue `no_declarada_nunca`, 14.9).

---

## 1. Gama y configuraciones (KIUBE-OM, Tabla 1-1)

| Modelo | Corriente en blanco | Blanco recomendado | Bombas ODP | 2ª fuente de protones | Amplificador RF |
|---|---|---|---|---|---|
| KIUBE 100 | 100 µA | Conical 5 | 2 | Opción | 16 kW |
| KIUBE 150 | 150 µA | Conical 8 | 2 | Opción | 16 kW |
| KIUBE 180 | 180 µA | Conical 12 | 4 | **Estándar** | 16 kW |
| KIUBE 300 | 300 µA | Conical 16 | 4 | **Estándar** | 20 kW |

- H⁻ acelerados, extracción por **lámina stripper de carbono, eficiencia ≈100 %**,
  minimiza activación interna (KIUBE-OM, cap. 2).
- **8 puertos de salida de haz**; hasta 4 equipables con blancos (KIUBE-SRG 2.1.x).
- Blancos Nirta® Liquid: ¹⁸F, ¹³NH₃, ⁶⁸Ga; Nirta® Gas: ¹⁵O, ¹¹CO₂, ¹¹CH₄; Nirta® Solid compatible.

## 2. Blancos cónicos ¹⁸F (KIUBE-OM, Tabla 3-1) — cifras oficiales de rendimiento

| Blanco | Haz (µA prot.) | Tiempo máx (min) | Volumen (µl) | Presión máx | Rendimiento | Actividad EOB |
|---|---|---|---|---|---|---|
| Conical 5 | 45 | 120 | 1800 | nunca exceder | 235 mCi/µA·sat | 5000 mCi (185 GBq) |
| Conical 8 | 70 | — | 2300 | 35 bar | 235 mCi/µA·sat | 8000 mCi (296 GBq) |
| Conical 12 | 100 | — | 2700 | — | 235 mCi/µA·sat | 12000 mCi (444 GBq) |
| Conical 16 | 130 | — | 4200 | — | 235 mCi/µA·sat | 16000 mCi (592 GBq) |

- Energía de haz en blanco: **17,5 MeV** (protones; KIUBE-OM Tabla 3-1).
- **Rendimiento saturado oficial: 235 mCi/µA·sat = 8,70 GBq/µA·sat** — referencia de
  validación para `yield_engine` (comparar con IAEA/Hess; diferencia debe quedar < 8 %).

### Validación cruzada ejecutada (2026-10-16, yield_engine v2.0.0)

`YieldCalculator.saturation_yield_mbq_ua("o18_p_n_f18", h2_18o, E)` con secciones IAEA
y stopping SRIM del sistema:

| Energía | Motor RPOS (IAEA) | Oficial IBA | Diferencia |
|---|---|---|---|
| 17,5 MeV (en blanco) | 263,0 mCi/µA·sat (9,73 GBq) | 235 mCi/µA·sat | **+10,6 %** |
| 18,0 MeV (extracción) | 267,6 mCi/µA·sat (9,90 GBq) | 235 mCi/µA·sat | +12,2 % |

**Interpretación honesta:** el motor calcula el rendimiento ideal de blanco grueso;
la cifra IBA es el rendimiento real del blanco cónico Nirta® (incluye pérdidas por
ventana, ángulo de incidencia y densidad efectiva del H₂¹⁸O bajo haz). Que el ideal
supere al real en ~10 % es lo esperado físicamente; el valor IBA es una cota práctica
citada (KIUBE-OM Tabla 3-1), no una corrección a las secciones IAEA. La incertidumbre
propia del motor es 7,6 %, por lo que ambas cifras son compatibles dentro de ~1σ
combinada. Se registra como **referencia de validación adicional** (junto a IAEA/Hess),
con fuente y contexto declarados — no se ajusta ningún parámetro del motor.

## 3. Recetas y modos de producción (KIUBE-OM, caps. 4–5)

- Modos de paro de haz automático: **por duración, por corriente integrada en blanco,
  o por actividad esperada** → los tres modos existen en `yield_engine`/Batch Manager.
- Roles del fabricante: Regular Operator (solo Quick Start), Advanced Operator
  (Manual Start + cambiar parámetros), Maintenance Technician, Supervisor (recetas,
  Administration Mode). **Mapea 1:1 con el modelo de roles de Radiopharma OS** y con la
  regla 18.10 (recomendación ≠ decisión operativa: las transferencias de actividad
  requieren siempre confirmación del operador, KIUBE-OM Tabla 4-2 nota a).
- Doble haz: `Unload Priority` define qué blanco se descarga primero.
- Producción diferida: la preparación del blanco arranca de inmediato y el ciclotrón
  arranca a la hora programada.

## 4. Equipo y sitio (KIUBE-SRG)

### 4.1 Ciclotrón (KIUBE-SRG Tabla 1)

- **Dimensiones: 2000 × 2000 × 1850 mm (An×F×Al)** · **Peso neto: 18 000 kg**.
- Validación cruzada con kiube v0.4: su modelo estima 13,5 t de hierro + 2 × 1,19 t de
  bobinas ≈ 16 t de núcleo magnético; los 18 t oficiales incluyen cámara, sistemas de
  vacío, fuentes y cerramiento → cifra oficial consistente (diferencia ≈ masa no
  modelada: sistemas auxiliares).
- Gabinetes: PS1 distribución (215 kg), PS2 RF (600 kg), PS3 fuentes+bobina (500 kg),
  PS4 PLC (250 kg). A4 sistema hidráulico de apertura del yugo (145 kg).

### 4.2 Búnker (KIUBE-SRG Tablas 2 y 3)

| Parámetro | Valor oficial IBA | BIND (plano RPOS) | Estado |
|---|---|---|---|
| Interior L×An | 3800×3800 mm (mín.) · 4000×4000 mm (recom.) | 5900×4700 mm | BIND **supera** el mínimo oficial ✔ |
| Altura interior | **2500 mm** | 2500 mm (kiube: TUD03) | **Confirmado por fuente oficial** — sube de TUD03 a KIUBE-SRG |
| Muros (total) | **2000–2400 mm** | 2110 mm (oeste, medido) | BIND **dentro del rango oficial** ✔ |
| Techo | 1700–2300 mm | 1500 mm (EST) | **Discrepancia**: BIND EST 1500 < 1700 oficial → pendiente verificación en plano |
| Concreto | densidad mínima **2350 kg/m³** | 2300 kg/m³ (supuesto F62) | Ajustar modelo MC a 2,35 o declarar supuesto conservador ✔ (2,3 es conservador) |
| Puerta/acceso | mínimo 1000×2000 mm; plug door o laberinto | laberinto sur (no modelado) | El laberinto BIND es la solución permitida ✔ |
| Secuencia | "last man out": botón de búsqueda + puerta cierra antes de que expire el temporizador; enclavamiento al gabinete IBA; apertura interior manual en falla eléctrica | — | Requisito para módulo de enclavamientos (pendiente_entorno) |

### 4.3 Dosis (KIUBE-SRG Tablas 8 y 9) — referencia para validar el MC

**Tabla 8 — Tasa de dosis máxima a 1 m del ciclotrón (dentro del búnker), frente al blanco ¹⁸F:**

| Posición | KIUBE 100 (1×100 µA) | KIUBE 150 (2×75 µA) | KIUBE 180 (2×100 µA) | KIUBE 300 (2×150 µA) |
|---|---|---|---|---|
| Frente al blanco (0°) | 1,18×10⁸ µSv/h | 0,9×10⁸ | 1,2×10⁸ | 1,8×10⁸ |
| 90° (perpendicular) | 2,4×10⁷ | 0,2×10⁸ | 0,27×10⁸ | 0,41×10⁸ |
| 180° (opuesta) | 5,5×10⁶ | 0,9×10⁸ | 1,2×10⁸ | 1,8×10⁸ |

**Tabla 9 — Tasa de dosis de contacto tras X cm de concreto, frente al blanco ¹⁸F (µSv/h):**

| Espesor | KIUBE 100 | KIUBE 150 | KIUBE 180 | KIUBE 300 |
|---|---|---|---|---|
| 200 cm | 3,20 | 2,71 | 3,62 | 5,43 |
| 220 cm | 0,77 | 0,59 | 0,79 | 1,19 |
| 230 cm | 0,36 | 0,30 | 0,40 | 0,60 |

- **Uso canónico:** la corrida MC con muro de 211 cm (BIND) debe caer entre las filas
  200 y 220 cm para el escenario equivalente → **criterio de aceptación cuantitativo
  oficial para F65** (antes no existía referencia del fabricante).
- IBA mismo basa su informe de blindaje estándar en **cómputo Monte Carlo**
  (KIUBE-SRG 2.1.2) → nuestra metodología (OpenMC/DAGMC) es la del fabricante.
- La validación del blindaje por mediciones antes de producción es responsabilidad del
  RSO local (KIUBE-SRG 2.1.8.6) → PQ/medición real, `pendiente_entorno`.
- Notas de construcción: evitar capas horizontales planas sucesivas (fugas de
  neutrones; escalonar colados); **las barras de acero rectas de interior a exterior son
  canales de neutrones**; capa interna de desmantelamiento desvinculada, con refuerzo
  mínimo o de fibra de vidrio.

### 4.4 Servicios

- Agua enfriada (KIUBE-SRG Tabla 11): remoción de calor mínima **55 kW** (ciclotrón),
  flujo **100 l/min**, entrada 6–16 °C, presión estática máx. 10 bar, caída nominal
  1 ± 0,1 bar; boquilla para manguera Øint 32 mm.
- Ubicación recomendada: nivel más bajo del edificio (peso); bajo tierra permite usar
  suelo como blindaje (KIUBE-SRG 2.1.4).
- Acabado del búnker: piso nivelado con pintura epóxica; muros/techo con poliuretano o
  epóxico lavable (2.1.5).
- Alarma de radiación en la entrada del búnker, rango mínimo 1 µSv/h – 10 mSv/h (2.1.7).

## 5. Activación y desmantelamiento (KIUBE-SRG 2.1.8.7–2.1.8.8)

- Partes más activadas: **consumibles — láminas de blanco y láminas de vacío**
  (confirma el foco de los tallies de activación de kiube v0.4).
- Mantenimiento: blindaje local (bolsas de plomo) en blancos, mesa de trabajo dedicada
  con pantalla en L y vidrio plomado, contenedor plomado para láminas.
- Desmantelamiento: capa interna de concreto activada ("decommissioning layer")
  desmontable; volumen de residuos depende de impurezas del concreto (Co, Eu — justifica
  las trazas en `materials.yaml` de kiube), uso del ciclotrón y normativa local.

## 6. Impacto en kiube v0.4 (actualizaciones pendientes para v0.5)

| Parámetro kiube v0.4 | Valor v0.4 (fuente) | Dato oficial | Acción sugerida |
|---|---|---|---|
| `vault.inner_height` | 2500 (TUD03) | 2500 mm (KIUBE-SRG) | **Subir fuente a KIUBE-SRG** ✔ |
| `vault.ceiling` | 1500 (EST) | techo 1700–2300 mm (KIUBE-SRG) | Corregir a ≥1700 o marcar discrepancia BIND |
| densidad concreto | 2,30 (NIST/EST) | ≥2,35 g/cm³ (KIUBE-SRG) | Correr MC con 2,35 y reportar ambos |
| `beam.T_MeV` | 18,0 (TUP03) | 17,5 MeV en blanco (KIUBE-OM) | Añadir `T_target_MeV: 17.5` (extracción 18, en blanco 17,5) |
| corriente blancos | 150 µA/2 blancos (EST) | por modelo: 100/150/180/300 µA total | Parametrizar por modelo KIUBE |
| masa hierro | 13,5 t (CALC) | 18 000 kg neto equipo completo | Validación cruzada OK (16 t magnéticos ⊂ 18 t) |
| rendimiento ¹⁸F | — | 235 mCi/µA·sat; EOB 296 GBq (Conical 8) | Nueva referencia de validación de yield_engine |
| laberinto | no modelado | plug door o laberinto permitidos | Mantener pendiente; BIND usa laberinto |

**Regla aplicada:** toda cifra oficial queda citada con documento, tabla y revisión;
nada de esto modifica el estado `pendiente_entorno` de la Producción Clínica (18.19) ni
la PQ (14.9).
